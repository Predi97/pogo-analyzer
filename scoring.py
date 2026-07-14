import bisect
import math
from typing import Optional

from data.base_stats import _BS, _EVOLVE_CHAIN, _cpm
from data.cpm import _CPM_VALUES


# ── Raid scoring ──────────────────────────────────────────────────────────────

def max_cp(pid: int, iv_a: int, iv_d: int, iv_s: int) -> int:
    bs = _BS.get(pid)
    if not bs:
        return 0
    a, d, s = bs
    c = _cpm(50)
    return max(10, int((a + iv_a) * ((d + iv_d) ** 0.5) * ((s + iv_s) ** 0.5) * c * c / 10))


def raid_score(pid: int, iv_a: int, iv_d: int, iv_s: int,
               tiers: dict, name: str) -> float:
    """DPS×TDO proxy + tier bonus. Higher = better raid attacker."""
    bs = _BS.get(pid)
    if not bs:
        return 0.0
    a, d, s = bs
    c     = _cpm(40)
    eff_a = (a + iv_a) * c
    eff_d = (d + iv_d) * c
    eff_s = (s + iv_s) * c
    score = (eff_a ** 1.5) * ((eff_s * eff_d) ** 0.5)
    tier  = _best_tier(_tier_for(name, tiers))
    return score * {"S": 2.0, "A": 1.5, "B": 1.2}.get(tier, 1.0)


# ── PvP scoring ───────────────────────────────────────────────────────────────

def pvp_cp(pid: int, iv_a: int, iv_d: int, iv_s: int,
           cp_limit: int) -> tuple[float, int]:
    """Return (level_used, best_cp) at or under cp_limit."""
    bs = _BS.get(pid)
    if not bs:
        return (0.0, 0)
    a, d, s = bs
    best_lvl, best_cp = 0.0, 0
    lvl = 1.0
    while lvl <= 51:
        c  = _cpm(lvl)
        cp = max(10, int((a + iv_a) * ((d + iv_d) ** 0.5) * ((s + iv_s) ** 0.5) * c * c / 10))
        if cp <= cp_limit:
            best_lvl, best_cp = lvl, cp
        else:
            break
        lvl += 0.5
    return (best_lvl, best_cp)


def pvp_score(pid: int, iv_a: int, iv_d: int, iv_s: int,
              cp_limit: int, tiers: dict, name: str, league_key: str) -> float:
    lvl, cp = pvp_cp(pid, iv_a, iv_d, iv_s, cp_limit)
    min_cp = 1500 if cp_limit > 9000 else (cp_limit // 5)
    if cp < max(10, min_cp):
        return 0.0
    bs = _BS.get(pid)
    if not bs:
        return 0.0
    a, d, s = bs
    c     = _cpm(lvl)
    eff_a = (a + iv_a) * c
    eff_d = (d + iv_d) * c
    eff_s = (s + iv_s) * c
    score     = eff_a * (eff_d ** 1.2) * (eff_s ** 1.2)
    tier_data = _tier_for(name, tiers)
    tier      = tier_data.get(league_key) or _best_tier(tier_data)
    return score * {"S": 2.2, "A": 1.6, "B": 1.2}.get(tier, 1.0)


# ── PvP IV Rank ───────────────────────────────────────────────────────────────
# Rank 1 = best possible IV combo at the given CP cap (PvPoke stat-product method).
# Lower ATK IVs often rank higher: they allow a higher level under the CP cap,
# increasing HP/bulk more than the lost attack hurts.

_rank_cache: dict[tuple, list] = {}  # (pid, cp_limit) → sorted ASC stat products


def _stat_product(ea: float, ed: float, es: float, c: float) -> float:
    """EffAtk × EffDef × EffHP; EffHP uses game's floor."""
    return ea * c * ed * c * math.floor(es * c)


def _best_cpm_idx(ea: float, ed: float, es: float, cp_limit: int) -> int:
    """Index into _CPM_VALUES for the highest level where CP ≤ cp_limit."""
    cp_base = ea * math.sqrt(ed) * math.sqrt(es) / 10.0
    if cp_base <= 0:
        return -1
    max_cpm = math.sqrt((cp_limit + 1) / cp_base)
    idx = bisect.bisect_right(_CPM_VALUES, max_cpm) - 1
    # Float rounding can push computed CP 1 over limit — guard against it
    if idx >= 0 and max(10, math.floor(cp_base * _CPM_VALUES[idx] ** 2)) > cp_limit:
        idx -= 1
    return idx


def _build_rank_table(pid: int, cp_limit: int) -> list:
    """All 4096 stat products for a species at a given CP cap, sorted ASC. Cached."""
    key = (pid, cp_limit)
    if key in _rank_cache:
        return _rank_cache[key]
    bs = _BS.get(pid)
    if not bs:
        _rank_cache[key] = []
        return []
    ba, bd, bst = bs
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


def pvp_iv_rank(pid: int, iv_a: int, iv_d: int, iv_s: int,
                cp_limit: int) -> tuple[int, int, float]:
    """Return (rank, total, pct_of_max).  rank 1 = best stat product."""
    table = _build_rank_table(pid, cp_limit)
    if not table:
        return (0, 0, 0.0)
    bs = _BS.get(pid)
    if not bs:
        return (0, 0, 0.0)
    ba, bd, bst = bs
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


# ── Tier helpers (used by all scoring functions) ──────────────────────────────

_TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _tier_for(name: str, tiers: dict) -> dict:
    return tiers.get(name) or tiers.get(name.split(" (")[0]) or {}


def _best_tier(tier_dict: dict) -> Optional[str]:
    tiers = [t for t in tier_dict.values() if t in _TIER_ORDER]
    return min(tiers, key=lambda t: _TIER_ORDER[t]) if tiers else None
