import bisect
import math
from typing import Optional

from data.base_stats import _BS, _EVOLVE_CHAIN, _cpm
from data.cpm import _CPM_VALUES
from data.pokedex import DEX


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
    """All stat products for a species at a given CP cap, sorted ASC. Respects mythical floors. Cached."""
    key = (pid, cp_limit)
    if key in _rank_cache:
        return _rank_cache[key]
    bs = _BS.get(pid)
    if not bs:
        _rank_cache[key] = []
        return []
    ba, bd, bst = bs
    
    # Restrict untradeable research/raid mythicals to minimum IV floor of 10/10/10
    name = DEX.get(pid)
    iv_floor = 10 if (name and name in {
        "Mew", "Celebi", "Jirachi", "Victini", "Meloetta", "Shaymin", "Zarude", 
        "Diancie", "Keldeo", "Magearna", "Hoopa", "Deoxys", "Darkrai", "Genesect"
    }) else 0

    products: list[float] = []
    for id_ in range(iv_floor, 16):
        ed = bd + id_
        for is_ in range(iv_floor, 16):
            es = bst + is_
            for ia in range(iv_floor, 16):
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


def pvp_ideal_ivs(pid: int, cp_limit: int) -> tuple[int, int, int]:
    """Finds the Rank 1 (highest stat product) IV combination for a species, respecting mythical floors."""
    bs = _BS.get(pid)
    if not bs:
        return (0, 0, 0)
    ba, bd, bst = bs
    
    # Restrict untradeable research/raid mythicals to minimum IV floor of 10/10/10
    name = DEX.get(pid)
    iv_floor = 10 if (name and name in {
        "Mew", "Celebi", "Jirachi", "Victini", "Meloetta", "Shaymin", "Zarude", 
        "Diancie", "Keldeo", "Magearna", "Hoopa", "Deoxys", "Darkrai", "Genesect"
    }) else 0
    
    best_sp = -1.0
    best_cp = -1
    best_ivs = (0, 0, 0)
    for ia in range(iv_floor, 16):
        ea = ba + ia
        for id_ in range(iv_floor, 16):
            ed = bd + id_
            for is_ in range(iv_floor, 16):
                es = bst + is_
                idx = _best_cpm_idx(ea, ed, es, cp_limit)
                if idx >= 0:
                    sp = _stat_product(ea, ed, es, _CPM_VALUES[idx])
                    cp = math.floor(ea * math.sqrt(ed) * math.sqrt(es) / 10.0 * _CPM_VALUES[idx] * _CPM_VALUES[idx])
                    if sp > best_sp:
                        best_sp = sp
                        best_cp = cp
                        best_ivs = (ia, id_, is_)
                    elif abs(sp - best_sp) < 1e-5:
                        # Tie-breaker: choose higher CP, then higher Stamina, then higher Defense
                        if cp > best_cp or (cp == best_cp and is_ > best_ivs[2]) or (cp == best_cp and is_ == best_ivs[2] and id_ > best_ivs[1]):
                            best_sp = sp
                            best_cp = cp
                            best_ivs = (ia, id_, is_)
    return best_ivs


# ── Tier helpers (used by all scoring functions) ──────────────────────────────

_TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _tier_for(name: str, tiers: dict) -> dict:
    return tiers.get(name) or tiers.get(name.split(" (")[0]) or {}


def _best_tier(tier_dict: dict) -> Optional[str]:
    tiers = [t for t in tier_dict.values() if t in _TIER_ORDER]
    return min(tiers, key=lambda t: _TIER_ORDER[t]) if tiers else None


def calculate_cp_for_level(pid: int, iv_a: int, iv_d: int, iv_s: int, target_level: float) -> int:
    bs = _BS.get(pid)
    if not bs:
        return 0
    a, d, s = bs
    c = _cpm(target_level)
    return max(10, int((a + iv_a) * ((d + iv_d) ** 0.5) * ((s + iv_s) ** 0.5) * c * c / 10))


def get_best_pve_moveset(species_name: str):
    from data.pokemon_db import POKEMON_DB
    from data.moves import MOVES
    
    # Try exact match first (e.g. "zacian (crowned sword)")
    entry = POKEMON_DB.get(species_name.lower())
    if not entry:
        # Fallback to base name (e.g. "zacian")
        clean_name = species_name.lower().split(" (")[0].strip()
        entry = POKEMON_DB.get(clean_name)
    if not entry:
        # Fallback to substring fuzzy match
        matched_key = next((k for k in POKEMON_DB.keys() if k in species_name.lower() or species_name.lower() in k), None)
        if matched_key:
            entry = POKEMON_DB[matched_key]
            
    if not entry:
        return None
    
    elite_fast = entry.get("elite_quick_moves", [])
    elite_charged = entry.get("elite_cinematic_moves", [])
    
    fast_pool = entry.get("quick_moves", []) + elite_fast
    charged_pool = entry.get("cinematic_moves", []) + elite_charged
    
    if not fast_pool or not charged_pool:
        return None
        
    types = entry.get("types", [])
    
    combinations = []
    
    for f_id in fast_pool:
        f_move = MOVES.get(f_id)
        if not f_move:
            continue
        f_power = f_move.get("pve_power", 0.0)
        f_dur = f_move.get("pve_duration_ms", 0) / 1000.0
        f_energy = f_move.get("pve_energy_delta", 0)
        f_stab = 1.2 if f_move.get("type") in types else 1.0
        is_f_elite = f_id in elite_fast
        
        for c_id in charged_pool:
            c_move = MOVES.get(c_id)
            if not c_move:
                continue
            c_power = c_move.get("pve_power", 0.0)
            c_dur = c_move.get("pve_duration_ms", 0) / 1000.0
            c_energy = abs(c_move.get("pve_energy_delta", 100))
            c_stab = 1.2 if c_move.get("type") in types else 1.0
            is_c_elite = c_id in elite_charged
            
            if f_energy > 0:
                n = math.ceil(c_energy / f_energy)
            else:
                n = 5
            
            damage = (f_power * f_stab * n) + (c_power * c_stab)
            time = (f_dur * n) + c_dur
            cycle_dps = damage / time if time > 0 else 0.0
            
            # Apply a 1.15x type-synergy multiplier if Fast and Charged move types match (PvE meta values matching types)
            score = cycle_dps * 1.15 if f_move.get("type") == c_move.get("type") else cycle_dps
            
            combinations.append({
                "fast_id": f_id,
                "fast_name": f_move["name"],
                "fast_type": f_move["type"],
                "fast_elite": is_f_elite,
                "charged_id": c_id,
                "charged_name": c_move["name"],
                "charged_type": c_move["type"],
                "charged_elite": is_c_elite,
                "dps": round(cycle_dps, 1),
                "score": score
            })
            
    # Sort by score descending
    combinations.sort(key=lambda x: -x["score"])
    
    # Filter to remove duplicate pairs
    seen = set()
    unique_combos = []
    for c in combinations:
        key = (c["fast_name"], c["charged_name"])
        if key not in seen:
            seen.add(key)
            unique_combos.append(c)
            
    return unique_combos[:3]

