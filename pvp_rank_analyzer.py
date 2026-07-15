"""
PvP Rank Analyzer — standalone script (pandas + SQLite)
========================================================
Calculates pvp_gl_rank / pvp_ul_rank for hundreds of pokemon at once.

Mathematics (PvPoke-compatible):
  CP        = max(10, floor(EffAtk * sqrt(EffDef) * sqrt(EffSta) * CPM² / 10))
  EffAtk    = (BaseAtk + iv_a) * CPM
  EffDef    = (BaseDef + iv_d) * CPM
  EffHP     = floor((BaseSta + iv_s) * CPM)          ← game-accurate floor
  StatProd  = EffAtk * EffDef * EffHP
  Rank      = position in the ranking of 4096 IV combinations (rank 1 = max StatProd)

Lower Atk IVs often yield a higher rank — they allow the Pokemon to reach a higher level
under the same CP cap, gaining more bulk.
"""

from __future__ import annotations

import bisect
import math
import sqlite3
from pathlib import Path
from typing import NamedTuple

import pandas as pd
import requests

# ── Configuration ──────────────────────────────────────────────────────────────

GL_CAP = 1500
UL_CAP = 2500

DB_PATH   = Path(__file__).parent / "baza_pogo.db"    # SQLite from project
CSV_PATH  = Path(__file__).parent / "pokemons.csv"     # alternatively CSV: Species,CP,Lvl,iv_a,iv_d,iv_s

# ── Full CPM table (levels 1-51, step 0.5) ─────────────────────────────

_CPM_RAW = [
    (1,0.094),(1.5,0.135137432),(2,0.16639787),(2.5,0.192650919),(3,0.21573247),
    (3.5,0.236572661),(4,0.25572005),(4.5,0.273530381),(5,0.29024988),(5.5,0.306057377),
    (6,0.3210876),(6.5,0.335445036),(7,0.34921268),(7.5,0.362457751),(8,0.37523559),
    (8.5,0.387592406),(9,0.39956728),(9.5,0.411193551),(10,0.42250001),(10.5,0.432926419),
    (11,0.44310755),(11.5,0.4530599578),(12,0.46279839),(12.5,0.472336083),(13,0.48168495),
    (13.5,0.4908558),(14,0.49985844),(14.5,0.508701765),(15,0.51739395),(15.5,0.525942511),
    (16,0.53435433),(16.5,0.542635767),(17,0.55079269),(17.5,0.558830576),(18,0.56675452),
    (18.5,0.574569153),(19,0.58227891),(19.5,0.589877521),(20,0.59740001),(20.5,0.604823665),
    (21,0.61215729),(21.5,0.619399365),(22,0.62656713),(22.5,0.633644533),(23,0.64065295),
    (23.5,0.647576426),(24,0.65443563),(24.5,0.661214806),(25,0.667934),(25.5,0.674577537),
    (26,0.68116492),(26.5,0.687680648),(27,0.69414365),(27.5,0.700538673),(28,0.70688421),
    (28.5,0.713164996),(29,0.71939909),(29.5,0.725571552),(30,0.7317),(30.5,0.734741009),
    (31,0.73776948),(31.5,0.740785574),(32,0.74378943),(32.5,0.746781211),(33,0.74976104),
    (33.5,0.752729087),(34,0.75568551),(34.5,0.758630378),(35,0.76156384),(35.5,0.764486065),
    (36,0.76739717),(36.5,0.770297266),(37,0.7731865),(37.5,0.776064962),(38,0.77893275),
    (38.5,0.781790055),(39,0.78463697),(39.5,0.787473578),(40,0.79030001),(40.5,0.792803968),
    (41,0.79530001),(41.5,0.797800015),(42,0.80030001),(42.5,0.802799985),(43,0.80530001),
    (43.5,0.807800014),(44,0.81030001),(44.5,0.812799986),(45,0.81530001),(45.5,0.817800014),
    (46,0.82030001),(46.5,0.822799985),(47,0.82530001),(47.5,0.827800015),(48,0.83030001),
    (48.5,0.832799985),(49,0.83530001),(49.5,0.837800015),(50,0.84029999),
    (50.5,0.84280373),(51,0.84530001),
]

_CPM_TABLE: dict[float, float] = {lvl: c for lvl, c in _CPM_RAW}
_CPM_VALUES: list[float] = sorted(c for _, c in _CPM_RAW)


def _cpm(level: float) -> float:
    return _CPM_TABLE.get(level, _CPM_RAW[-1][1])


# ── Base Stats — PvPoke gamemaster with local cache ───────────────────────────
# Source: github.com/pvpoke/pvpoke (all ~900 pokemon + forms)
# Cache: SQLite table `pvpoke_base_stats`, refreshed every CACHE_TTL_DAYS days.

PVPOKE_URL     = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster/pokemon.json"
CACHE_TTL_DAYS = 7  # refresh once a week

# Map names from project parser → speciesId PvPoke
# PvPoke format: snake_case, forms separated by "_" (e.g. "ninetales_alolan")
_FORM_MAP: dict[str, str] = {
    "galarian":  "_galarian",
    "hisuian":   "_hisuian",
    "alolan":    "_alolan",
    "paldean":   "_paldean",
    "female":    "_female",
    "male":      "_male",
    "normal":    "",           # Normal form = base
}

_ABBREV_MAP = {
    "(g)": "galarian", "(h)": "hisuian", "(a)": "alolan",
    "(p)": "paldean",  "(f)": "female",  "(m)": "male",
}

# Pokemons with multiple forms — default form when specification is missing
_DEFAULT_FORM: dict[str, str] = {
    "oricorio":  "oricorio_baile",
    "pumpkaboo": "pumpkaboo_average",
    "gourgeist": "gourgeist_average",
    "lycanroc":  "lycanroc_midday",
    "minior":    "minior_red_meteor",
}

def _normalize_name(name: str) -> list[str]:
    """
    Translates display name to candidate PvPoke speciesIds.
    Supports full forms ('Alolan') and abbreviations ('(A)', '(G)', etc.).
    E.g. 'Meowth (G)' → ['meowth_galarian', 'meowth']
         'Ninetales (Alolan)' → ['ninetales_alolan', 'ninetales']
    """
    import re
    n = name.lower().strip()
    n = n.replace("♀", "_female").replace("♂", "_male")

    # single letter abbreviations in parentheses: (g)→galarian, (f)→female, etc.
    # remove space before parenthesis to avoid double underscores
    for abbrev, full in _ABBREV_MAP.items():
        n = re.sub(r"\s*" + re.escape(abbrev), "_" + full, n)

    # full form names in parentheses: (alolan), (galarian), etc.
    n = re.sub(r"\s*\(([^)]+)\)", lambda m: "_" + m.group(1).strip(), n)

    n = n.replace(" ", "_").replace("-", "_").replace("'", "").replace(".", "")
    # remove double underscores
    n = re.sub(r"_+", "_", n).strip("_")

    # default form for multi-form pokemon
    if n in _DEFAULT_FORM:
        return [_DEFAULT_FORM[n], n]

    # fallback: version without form suffix
    base = re.sub(
        r"_(galarian|hisuian|alolan|paldean|female|male|normal)$", "", n
    )
    return [n, base] if n != base else [n]


def _load_pvpoke_cache() -> dict[str, tuple[int, int, int]]:
    """Loads base stats from SQLite cache (pvpoke_base_stats table)."""
    if not DB_PATH.exists():
        return {}
    import json as _json
    con = sqlite3.connect(DB_PATH)
    try:
        row = con.execute(
            "SELECT data, fetched_at FROM pvpoke_base_stats LIMIT 1"
        ).fetchone()
        if not row:
            return {}
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) -
               datetime.fromisoformat(row[1])).days
        if age > CACHE_TTL_DAYS:
            return {}  # forces refresh
        return _json.loads(row[0])
    except sqlite3.OperationalError:
        return {}
    finally:
        con.close()


def _save_pvpoke_cache(bs_map: dict[str, tuple[int, int, int]]) -> None:
    """Saves base stats to SQLite cache."""
    import json as _json
    from datetime import datetime, timezone
    if not DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE IF NOT EXISTS pvpoke_base_stats "
        "(id INTEGER PRIMARY KEY, data TEXT, fetched_at TEXT)"
    )
    con.execute("DELETE FROM pvpoke_base_stats")
    con.execute(
        "INSERT INTO pvpoke_base_stats VALUES (1, ?, ?)",
        (_json.dumps(bs_map), datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


def _fetch_pvpoke() -> dict[str, tuple[int, int, int]]:
    """Fetches full PvPoke gamemaster and builds speciesId → (atk, def, hp) dictionary."""
    print(f"[INFO] Fetching PvPoke gamemaster ({PVPOKE_URL.split('/')[2]})…")
    resp = requests.get(PVPOKE_URL, timeout=20)
    resp.raise_for_status()
    result: dict[str, tuple[int, int, int]] = {}
    for p in resp.json():
        sid   = p.get("speciesId", "").lower()
        stats = p.get("baseStats", {})
        if sid and stats.get("atk"):
            result[sid] = (stats["atk"], stats["def"], stats["hp"])
    print(f"[INFO] Fetched {len(result)} entries from PvPoke gamemaster")
    return result


def load_base_stats() -> dict[str, tuple[int, int, int]]:
    """
    Returns pokemon_name → (BaseAtk, BaseDef, BaseSta) dictionary.
    Order: SQLite cache → fetch PvPoke → local fallback _BS.
    """
    # 1. Cache
    bs_raw = _load_pvpoke_cache()
    if not bs_raw:
        try:
            bs_raw = _fetch_pvpoke()
            _save_pvpoke_cache(bs_raw)
        except Exception as e:
            print(f"[WARN] Cannot fetch PvPoke: {e}")

    # 2. Fallback to local _BS from project if fetch failed
    if not bs_raw:
        print("[WARN] Using local base stats (183 meta)")
        try:
            import sys; sys.path.insert(0, str(Path(__file__).parent))
            from data.base_stats import _BS
            from data.pokedex import DEX
            return {DEX[pid].lower(): bs for pid, bs in _BS.items() if pid in DEX}
        except ImportError:
            return {}

    return bs_raw


def resolve_base_stats(
    name: str,
    bs_raw: dict[str, tuple[int, int, int]],
) -> tuple[int, int, int] | None:
    """
    Translates display name of a pokemon to base stats from bs_raw.
    Tries several name variants to support regional forms.
    """
    for candidate in _normalize_name(name):
        if candidate in bs_raw:
            return bs_raw[candidate]
    return None


# ── Stat Product & Rank ───────────────────────────────────────────────────────

_rank_cache: dict[tuple, list[float]] = {}


def _best_cpm_idx(ea: float, ed: float, es: float, cp_limit: int) -> int:
    """Bisection: index in _CPM_VALUES for the highest level where CP ≤ cp_limit."""
    cp_base = ea * math.sqrt(ed) * math.sqrt(es) / 10.0
    if cp_base <= 0:
        return -1
    max_cpm = math.sqrt((cp_limit + 1) / cp_base)
    idx = bisect.bisect_right(_CPM_VALUES, max_cpm) - 1
    if idx >= 0 and max(10, math.floor(cp_base * _CPM_VALUES[idx] ** 2)) > cp_limit:
        idx -= 1
    return idx


def _stat_product(ea: float, ed: float, es: float, c: float) -> float:
    """EffAtk × EffDef × floor(EffHP) — game-accurate HP floor."""
    return (ea * c) * (ed * c) * math.floor(es * c)


def _build_rank_table(ba: int, bd: int, bst: int, cp_limit: int) -> list[float]:
    """All 4096 stat products for a given species at the CP limit."""
    key = (ba, bd, bst, cp_limit)
    if key in _rank_cache:
        return _rank_cache[key]
    products: list[float] = []
    for id_ in range(16):
        ed = bd + id_
        for is_ in range(16):
            es = bst + is_
            for ia in range(16):
                ea  = ba + ia
                idx = _best_cpm_idx(ea, ed, es, cp_limit)
                products.append(
                    _stat_product(ea, ed, es, _CPM_VALUES[idx]) if idx >= 0 else 0.0
                )
    products.sort()
    _rank_cache[key] = products
    return products


def pvp_rank(ba: int, bd: int, bst: int,
             iv_a: int, iv_d: int, iv_s: int,
             cp_limit: int) -> tuple[int, int, float]:
    """
    Returns (rank, total, pct_of_max).
    rank 1 = highest stat product for the species in a given league.
    """
    table = _build_rank_table(ba, bd, bst, cp_limit)
    if not table:
        return (0, 0, 0.0)
    ea  = ba + iv_a
    ed  = bd + iv_d
    es  = bst + iv_s
    idx = _best_cpm_idx(ea, ed, es, cp_limit)
    if idx < 0:
        return (len(table), len(table), 0.0)
    sp   = _stat_product(ea, ed, es, _CPM_VALUES[idx])
    rank = len(table) - bisect.bisect_right(table, sp) + 1
    pct  = round(sp / table[-1] * 100, 2) if table[-1] > 0 else 0.0
    return (rank, len(table), pct)


# ── Loading data ─────────────────────────────────────────────────────────

def load_pokemons() -> pd.DataFrame:
    """
    Loads pokemons from SQLite (last_upload → parsed JSON) or CSV.
    Expected columns: name, iv_a, iv_d, iv_s
    """
    if DB_PATH.exists():
        import json
        con = sqlite3.connect(DB_PATH)
        row = con.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
        con.close()
        if not row:
            raise ValueError("Database exists but last_upload is empty — upload PGSStats.json through the app first.")
        raw = json.loads(row[0])
        # Parse raw PGSStats using project parser
        import sys; sys.path.insert(0, str(Path(__file__).parent))
        from parser import parse_pgo_json
        parsed = parse_pgo_json(raw)
        df = pd.DataFrame(parsed["pokemons"])
        if "species" in df.columns:
            df = df.rename(columns={"species": "name"})
    elif CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH)
    else:
        raise FileNotFoundError(
            f"No data source. Configure DB_PATH or CSV_PATH.\n"
            f"  DB:  {DB_PATH.absolute()}\n"
            f"  CSV: {CSV_PATH.absolute()}"
        )
    required = {"name", "iv_a", "iv_d", "iv_s"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}. Available: {list(df.columns)}")
    return df


# ── Main logic ─────────────────────────────────────────────────────────────

def enrich_with_pvp_ranks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds pvp_gl_rank, pvp_gl_pct, pvp_ul_rank, pvp_ul_pct columns to DataFrame.
    Optimization: rank table built once per (species, league), cached.
    """
    bs_raw = load_base_stats()

    # Coverage report
    unresolved = [n for n in df["name"].unique() if resolve_base_stats(n, bs_raw) is None]
    if unresolved:
        print(f"[WARN] Missing base stats for {len(unresolved)} species: {unresolved[:8]}{'…' if len(unresolved)>8 else ''}")

    # apply row-wise — cached rank table makes it O(n) instead of O(n×4096)
    def _row_ranks(row) -> pd.Series:
        bs = resolve_base_stats(row["name"], bs_raw)
        if not bs:
            return pd.Series({"pvp_gl_rank": 0, "pvp_gl_pct": 0.0,
                               "pvp_ul_rank": 0, "pvp_ul_pct": 0.0})
        ba, bd, bst = bs
        ia, id_, is_ = int(row["iv_a"]), int(row["iv_d"]), int(row["iv_s"])
        gl_rank, _, gl_pct = pvp_rank(ba, bd, bst, ia, id_, is_, GL_CAP)
        ul_rank, _, ul_pct = pvp_rank(ba, bd, bst, ia, id_, is_, UL_CAP)
        return pd.Series({"pvp_gl_rank": gl_rank, "pvp_gl_pct": gl_pct,
                           "pvp_ul_rank": ul_rank, "pvp_ul_pct": ul_pct})

    ranks = df.apply(_row_ranks, axis=1)
    return pd.concat([df, ranks], axis=1)


def save_results(df: pd.DataFrame) -> None:
    """Saves results back to SQLite and to CSV."""
    if DB_PATH.exists():
        con = sqlite3.connect(DB_PATH)
        df.to_sql("pokemons_ranked", con, if_exists="replace", index=False)
        con.close()
        print(f"[OK] Saved to {DB_PATH} (table: pokemons_ranked)")

    out_csv = Path("pokemons_ranked.csv")
    df.to_csv(out_csv, index=False)
    print(f"[OK] Saved to {out_csv}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("Loading data…")
    df = load_pokemons()
    print(f"  {len(df)} pokemons, {df['name'].nunique()} species")

    print("Calculating PvP ranks…")
    t0     = time.perf_counter()
    result = enrich_with_pvp_ranks(df)
    elapsed = time.perf_counter() - t0

    print(f"  Ready in {elapsed:.2f}s")
    print(f"  Rank tables in cache: {len(_rank_cache)}")

    cols = ["name", "iv_a", "iv_d", "iv_s",
            "pvp_gl_rank", "pvp_gl_pct",
            "pvp_ul_rank", "pvp_ul_pct"]
    avail = [c for c in cols if c in result.columns]
    print("\nPreview of results:")
    print(result[avail].head(20).to_string(index=False))

    save_results(result)
