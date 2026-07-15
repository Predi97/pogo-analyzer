from flask import Blueprint, jsonify, request

from data.base_stats import _EVOLVE_CHAIN, _BS
from data.pokedex import DEX
from scoring import (
    _TIER_ORDER, _best_tier, _tier_for,
    max_cp, pvp_cp, pvp_iv_rank, pvp_score, raid_score,
    calculate_cp_for_level, pvp_ideal_ivs,
)
from services.tiers import get_tier_list
from state import _state

bp = Blueprint("analysis", __name__)


@bp.route("/api/raid-candidates")
def api_raid_candidates():
    from data.moves import MOVES
    from scoring import get_best_pve_moveset

    tiers  = get_tier_list()
    scored = []
    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        score = raid_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], tiers, p["name"])
        if score < 1:
            continue
        
        m1 = MOVES.get(p.get("move1"))
        m2 = MOVES.get(p.get("move2"))
        m3 = MOVES.get(p.get("move3"))
        
        curr_moves = [m1["name"]] if m1 else []
        if m2:
            curr_moves.append(m2["name"])
        if m3:
            curr_moves.append(m3["name"])
            
        species_name = p["name"].lower().replace(" (shadow)", "").replace(" (purified)", "")
        best_pve = get_best_pve_moveset(species_name)
        pve_optimal = []
        pve_standard = []
        if best_pve:
            elite_fast = best_pve.get("elite_fast", [])
            elite_charged = best_pve.get("elite_charged", [])
            
            best_tup = best_pve.get("best")
            if best_tup:
                bf_id, bc_id, _ = best_tup
                bf = MOVES.get(bf_id)
                bc = MOVES.get(bc_id)
                if bf:
                    name = bf["name"] + "*" if bf_id in elite_fast else bf["name"]
                    pve_optimal.append(name)
                if bc:
                    name = bc["name"] + "*" if bc_id in elite_charged else bc["name"]
                    pve_optimal.append(name)
                    
            std_tup = best_pve.get("standard")
            if std_tup:
                sf_id, sc_id, _ = std_tup
                sf = MOVES.get(sf_id)
                sc = MOVES.get(sc_id)
                if sf:
                    pve_standard.append(sf["name"])
                if sc:
                    pve_standard.append(sc["name"])

        tier_data = _tier_for(p["name"], tiers)
        scored.append({
            **p,
            "raid_score":   round(score),
            "max_cp":       max_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"]),
            "tiers":        tier_data,
            "best_tier":    _best_tier(tier_data),
            "move1_name":   m1["name"] if m1 else "",
            "move1_type":   m1["type"] if m1 else "",
            "move2_name":   m2["name"] if m2 else "",
            "move2_type":   m2["type"] if m2 else "",
            "move3_name":   m3["name"] if m3 else "",
            "move3_type":   m3["type"] if m3 else "",
            "curr_moves":   curr_moves,
            "pve_optimal":  pve_optimal,
            "pve_standard": pve_standard
        })
    scored.sort(key=lambda x: -x["raid_score"])
    return jsonify(scored[:60])


def build_local_teams(candidates: list[dict], league: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    # Typical PvP roles for top meta
    PVP_ROLES = {
        "Lickitung": "Safe Switch", "Cresselia": "Safe Switch", "Gligar": "Safe Switch",
        "Vigoroth": "Safe Switch", "Umbreon": "Safe Switch", "Sableye": "Safe Switch",
        "Dubwool": "Safe Switch", "Mandibuzz": "Safe Switch", "Dewgong": "Safe Switch",
        "Jellicent": "Safe Switch", "Pelipper": "Safe Switch",
        "Registeel": "Closer", "Bastiodon": "Closer", "Carbink": "Closer",
        "Talonflame": "Closer", "Charizard": "Closer", "Trevenant": "Closer",
        "Clodsire": "Closer", "Swampert": "Closer", "Greninja": "Closer",
        "Annihilape": "Closer", "Serperior": "Closer", "Dragonair": "Closer",
        "Froslass": "Closer", "Skeledirge": "Closer",
        "Medicham": "Lead", "Skarmory": "Lead", "Lanturn": "Lead",
        "Whiscash": "Lead", "Poliwrath": "Lead", "Pidgeot": "Lead",
        "Gliscor": "Lead", "Galarian Stunfisk": "Lead", "Stunfisk": "Lead"
    }

    META_TYPES = {
        "Medicham": ["fighting", "psychic"], "Skarmory": ["steel", "flying"],
        "Lanturn": ["water", "electric"], "Whiscash": ["water", "ground"],
        "Swampert": ["water", "ground"], "Registeel": ["steel"],
        "Bastiodon": ["rock", "steel"], "Carbink": ["rock", "fairy"],
        "Lickitung": ["normal"], "Cresselia": ["psychic"],
        "Gligar": ["ground", "flying"], "Gliscor": ["ground", "flying"],
        "Vigoroth": ["normal"], "Umbreon": ["dark"],
        "Sableye": ["dark", "ghost"], "Dubwool": ["normal"],
        "Mandibuzz": ["dark", "flying"], "Dewgong": ["water", "ice"],
        "Jellicent": ["water", "ghost"], "Pelipper": ["water", "flying"],
        "Talonflame": ["fire", "flying"], "Charizard": ["fire", "flying"],
        "Trevenant": ["ghost", "grass"], "Clodsire": ["poison", "ground"],
        "Greninja": ["water", "dark"], "Annihilape": ["fighting", "ghost"],
        "Serperior": ["grass"], "Dragonair": ["dragon"],
        "Froslass": ["ice", "ghost"], "Skeledirge": ["fire", "ghost"],
        "Steelix": ["steel", "ground"], "Altaria": ["dragon", "flying"],
        "Azumarill": ["water", "fairy"], "Obstagoon": ["dark", "normal"],
        "Venusaur": ["grass", "poison"], "Galarian Stunfisk": ["ground", "steel"],
        "Stunfisk": ["ground", "electric"], "Pidgeot": ["normal", "flying"]
    }

    # Dynamic classification helper
    candidates_with_ratio = []
    for c in candidates:
        name = c["name"]
        role = PVP_ROLES.get(name)
        ratio = 1.5
        bs = _BS.get(c["pid"])
        if bs:
            atk, dfs, sta = bs
            if atk > 0:
                ratio = (dfs + sta) / atk
        candidates_with_ratio.append((c, role, ratio))

    # Sort candidates by bulk ratio (low to high)
    candidates_with_ratio.sort(key=lambda x: x[2])

    leads = []
    switches = []
    closers = []

    n = len(candidates_with_ratio)
    for idx, (c, role, ratio) in enumerate(candidates_with_ratio):
        if not role:
            # lower 33% are closers, upper 33% are switches, middle are leads
            if idx < int(n * 0.33):
                role = "Closer"
            elif idx > int(n * 0.67):
                role = "Safe Switch"
            else:
                role = "Lead"

        c_with_role = {**c, "pvp_role": role}

        if role == "Lead":
            leads.append(c_with_role)
        elif role == "Safe Switch":
            switches.append(c_with_role)
        elif role == "Closer":
            closers.append(c_with_role)

    teams = []
    used_ids = set()

    for lead in leads:
        if len(teams) >= 3:
            break
        lead_key = (lead["pid"], lead["cp"])
        if lead_key in used_ids:
            continue

        for sw in switches:
            if len(teams) >= 3:
                break
            sw_key = (sw["pid"], sw["cp"])
            if sw_key in used_ids or sw["pid"] == lead["pid"]:
                continue

            lead_types = META_TYPES.get(lead["name"], [])
            sw_types = META_TYPES.get(sw["name"], [])
            if any(t in sw_types for t in lead_types if t):
                continue

            for closer in closers:
                if len(teams) >= 3:
                    break
                closer_key = (closer["pid"], closer["cp"])
                if closer_key in used_ids or closer["pid"] in (lead["pid"], sw["pid"]):
                    continue

                closer_types = META_TYPES.get(closer["name"], [])
                if any(t in closer_types for t in lead_types + sw_types if t):
                    continue

                teams.append({
                    "lead": lead,
                    "switch": sw,
                    "closer": closer,
                    "description": f"Zbalansowany skład z liderem {lead['name']}, bezpieczną zmianą {sw['name']} i finisherem {closer['name']}."
                })
                used_ids.add(lead_key)
                used_ids.add(sw_key)
                used_ids.add(closer_key)
                break

    if len(teams) < 3:
        for lead in leads:
            if len(teams) >= 3:
                break
            lead_key = (lead["pid"], lead["cp"])
            for sw in switches:
                if len(teams) >= 3:
                    break
                sw_key = (sw["pid"], sw["cp"])
                if sw["pid"] == lead["pid"]:
                    continue
                for closer in closers:
                    if len(teams) >= 3:
                        break
                    closer_key = (closer["pid"], closer["cp"])
                    if closer["pid"] in (lead["pid"], sw["pid"]):
                        continue
                    team_exists = any(
                        t["lead"]["pid"] == lead["pid"] and t["switch"]["pid"] == sw["pid"] and t["closer"]["pid"] == closer["pid"]
                        for t in teams
                    )
                    if not team_exists:
                        teams.append({
                            "lead": lead,
                            "switch": sw,
                            "closer": closer,
                            "description": f"Skład {lead['name']} + {sw['name']} + {closer['name']} (dobrany według ról)."
                        })
                        break

    return leads, switches, closers, teams


@bp.route("/api/pvp-candidates")
def api_pvp_candidates():
    league   = request.args.get("league", "GL")
    limits   = {"GL": 1500, "UL": 2500, "ML": 100000}
    keys     = {"GL": "pvp_great", "UL": "pvp_ultra", "ML": "pvp_master"}
    cp_limit = limits.get(league, 1500)
    lkey     = keys.get(league, "pvp_great")

    tiers  = get_tier_list()
    scored = []
    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        if league != "ML" and p["cp"] > cp_limit:
            continue
        score = pvp_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"],
                          cp_limit, tiers, p["name"], lkey)
        if score < 1:
            continue
        lvl, best_cp          = pvp_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        rank, total, rank_pct = pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        tier_data = _tier_for(p["name"], tiers)
        opt_a, opt_d, opt_s = pvp_ideal_ivs(p["pid"], cp_limit)
        scored.append({
            **p,
            "pvp_score":      round(score),
            "pvp_cp":         best_cp,
            "pvp_lvl":        lvl,
            "tiers":          tier_data,
            "best_tier":      _best_tier(tier_data),
            "pvp_rank":       rank,
            "pvp_rank_total": total,
            "pvp_rank_pct":   rank_pct,
            "pvp_ideal":      f"{opt_a}/{opt_d}/{opt_s}",
        })
    scored.sort(key=lambda x: -x["pvp_score"])
    top_candidates = scored[:60]

    leads, switches, closers, local_teams = build_local_teams(scored[:20], league)

    return jsonify({
        "candidates": top_candidates,
        "local_teams": local_teams,
        "best_by_role": {
            "leads": [{"name": p["name"], "cp": p["cp"], "pvp_rank": p["pvp_rank"]} for p in leads[:3]],
            "switches": [{"name": p["name"], "cp": p["cp"], "pvp_rank": p["pvp_rank"]} for p in switches[:3]],
            "closers": [{"name": p["name"], "cp": p["cp"], "pvp_rank": p["pvp_rank"]} for p in closers[:3]]
        }
    })


@bp.route("/api/develop-candidates")
def api_develop_candidates():
    tiers  = get_tier_list()
    evolve, power_up, purify, elite_tm = [], [], [], []

    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        own_tiers = _tier_for(p["name"], tiers)
        own_tier  = _best_tier(own_tiers)

        final_pid = _EVOLVE_CHAIN.get(p["pid"])
        if final_pid:
            final_name  = DEX.get(final_pid, f"#{final_pid}")
            final_tiers = _tier_for(final_name, tiers)
            final_tier  = _best_tier(final_tiers)
            if final_tier in ("S", "A") and p["iv_pct"] >= 80:
                final_cp = calculate_cp_for_level(final_pid, p["iv_a"], p["iv_d"], p["iv_s"], p["lvl"])
                evolve.append({**p, "final_name": final_name, "final_cp": final_cp,
                               "final_tier": final_tier, "tiers": final_tiers})

        if own_tier in ("S", "A") and p["iv_pct"] >= 80 and p["lvl"] < 40:
            power_up.append({**p, "tiers": own_tiers, "best_tier": own_tier})

        if p["shadow"]:
            pur_iv = round(
                (min(15, p["iv_a"] + 2) + min(15, p["iv_d"] + 2) + min(15, p["iv_s"] + 2))
                / 45 * 100, 1
            )
            if pur_iv >= 80:
                purify.append({**p, "purified_iv": pur_iv,
                               "tiers": own_tiers, "best_tier": own_tier})

        if own_tier in ("S", "A") and p["lvl"] >= 35:
            from data.pokemon_db import POKEMON_DB
            from data.moves import MOVES
            from scoring import get_best_pve_moveset
            
            m1 = MOVES.get(p.get("move1"))
            m2 = MOVES.get(p.get("move2"))
            m3 = MOVES.get(p.get("move3"))
            m1_name = m1["name"] if m1 else ""
            m2_name = m2["name"] if m2 else ""
            m3_name = m3["name"] if m3 else ""
            
            species_name = p["name"].lower().replace(" (shadow)", "").replace(" (purified)", "")
            db_entry = POKEMON_DB.get(species_name)
            if not db_entry:
                matched_key = next((k for k in POKEMON_DB.keys() if k in species_name or species_name in k), None)
                if matched_key:
                    db_entry = POKEMON_DB[matched_key]
            
            pvp_opt = []
            pve_opt = []
            pvp_warn = []
            pve_warn = []
            
            if db_entry:
                elite_fast = db_entry.get("elite_quick_moves", [])
                elite_charged = db_entry.get("elite_cinematic_moves", [])
                
                pvp_ids = db_entry.get("pvp_moveset", [])
                for mid in pvp_ids:
                    m = MOVES.get(mid)
                    if m:
                        pvp_opt.append(m["name"])
                        if m.get("is_fast") and mid in elite_fast and m1_name != m["name"]:
                            pvp_warn.append(f"Szybki: {m['name']} (Elite)")
                        elif not m.get("is_fast") and mid in elite_charged and m2_name != m["name"] and m3_name != m["name"]:
                            pvp_warn.append(f"Ładowany: {m['name']} (Elite)")
                            
                best_pve = get_best_pve_moveset(species_name)
                if best_pve and best_pve.get("best"):
                    bf_id, bc_id, _ = best_pve["best"]
                    bf = MOVES.get(bf_id)
                    bc = MOVES.get(bc_id)
                    if bf:
                        pve_opt.append(bf["name"])
                        if bf_id in elite_fast and m1_name != bf["name"]:
                            pve_warn.append(f"Szybki: {bf['name']} (Elite)")
                    if bc:
                        pve_opt.append(bc["name"])
                        if bc_id in elite_charged and m2_name != bc["name"] and m3_name != bc["name"]:
                            pve_warn.append(f"Ładowany: {bc['name']} (Elite)")
                            
            elite_tm.append({
                **p,
                "tiers": own_tiers,
                "best_tier": own_tier,
                "pvp_optimal": pvp_opt,
                "pve_optimal": pve_opt,
                "pvp_warnings": pvp_warn,
                "pve_warnings": pve_warn
            })

    evolve.sort(key=lambda x: (_TIER_ORDER.get(x["final_tier"], 9), -x["iv_pct"]))
    power_up.sort(key=lambda x: (_TIER_ORDER.get(x.get("best_tier", ""), 9), -x["iv_pct"]))
    purify.sort(key=lambda x: -x["purified_iv"])
    elite_tm.sort(key=lambda x: (_TIER_ORDER.get(x.get("best_tier", ""), 9), -x["lvl"]))

    return jsonify({
        "evolve":   evolve[:40],
        "power_up": power_up[:40],
        "purify":   purify[:40],
        "elite_tm": elite_tm[:40],
    })


@bp.route("/api/moveset-check", methods=["POST"])
def api_moveset_check():
    body = request.json or {}
    pid = body.get("pid")
    move1_id = body.get("move1")
    move2_id = body.get("move2")
    move3_id = body.get("move3")
    shadow = bool(body.get("shadow"))
    
    if not pid:
        return jsonify({"error": "Brak pid"}), 400
        
    from data.pokedex import DEX
    from data.pokemon_db import POKEMON_DB
    from data.moves import MOVES
    
    species_name = DEX.get(pid, f"#{pid}").lower()
    entry = POKEMON_DB.get(species_name)
    if not entry:
        # fallback by stripping parts
        matched_key = next((k for k in POKEMON_DB.keys() if k in species_name or species_name in k), None)
        if matched_key:
            entry = POKEMON_DB[matched_key]
            
    if not entry:
        return jsonify({"error": "Nie znaleziono pokemona w bazie"}), 404
        
    # Get current move names
    m1 = MOVES.get(move1_id)
    m2 = MOVES.get(move2_id)
    m3 = MOVES.get(move3_id)
    
    m1_name = m1["name"] if m1 else ""
    m2_name = m2["name"] if m2 else ""
    m3_name = m3["name"] if m3 else ""
    
    # 1. PvP optimal checking
    pvp_moveset_ids = entry.get("pvp_moveset", [])
    pvp_fast_optimal = []
    pvp_charged_optimal = []
    
    for mid in pvp_moveset_ids:
        m = MOVES.get(mid)
        if m:
            if m.get("is_fast"):
                pvp_fast_optimal.append(m["name"])
            else:
                pvp_charged_optimal.append(m["name"])
                
    pvp_fast_correct = m1_name in pvp_fast_optimal if pvp_fast_optimal else True
    pvp_charged_correct = (
        (m2_name in pvp_charged_optimal or m3_name in pvp_charged_optimal) 
        if pvp_charged_optimal else True
    )
    
    # Check Elite TMs requirements
    elite_fast = entry.get("elite_quick_moves", [])
    elite_charged = entry.get("elite_cinematic_moves", [])
    
    pvp_warnings = []
    for mid in pvp_moveset_ids:
        m = MOVES.get(mid)
        if m:
            if m.get("is_fast") and mid in elite_fast and m1_name != m["name"]:
                pvp_warnings.append(f"Szybki atak '{m['name']}' wymaga Elite Fast TM")
            elif not m.get("is_fast") and mid in elite_charged and m2_name != m["name"] and m3_name != m["name"]:
                pvp_warnings.append(f"Ładowany atak '{m['name']}' wymaga Elite Charged TM")
                
    if shadow and (move2_id == 5013 or move3_id == 5013 or m2_name == "Frustration" or m3_name == "Frustration"):
        pvp_warnings.append("Frustration blokuje Charged Move i może być usunięta tylko podczas specjalnych eventów Team GO Rocket")
        
    # 2. PvE (Raid) optimal checking
    from scoring import get_best_pve_moveset
    best_pve = get_best_pve_moveset(species_name)
    pve_fast_optimal = ""
    pve_charged_optimal = ""
    pve_fast_correct = True
    pve_charged_correct = True
    pve_warnings = []
    
    if best_pve:
        best_f_id, best_c_id, best_dps = best_pve
        bf_move = MOVES.get(best_f_id)
        bc_move = MOVES.get(best_c_id)
        if bf_move:
            pve_fast_optimal = bf_move["name"]
            pve_fast_correct = m1_name == pve_fast_optimal
            if best_f_id in elite_fast and not pve_fast_correct:
                pve_warnings.append(f"Szybki atak '{pve_fast_optimal}' wymaga Elite Fast TM")
        if bc_move:
            pve_charged_optimal = bc_move["name"]
            pve_charged_correct = m2_name == pve_charged_optimal or m3_name == pve_charged_optimal
            if best_c_id in elite_charged and not pve_charged_correct:
                pve_warnings.append(f"Ładowany atak '{pve_charged_optimal}' wymaga Elite Charged TM")
                
    return jsonify({
        "pvp_fast_optimal": pvp_fast_optimal,
        "pvp_charged_optimal": pvp_charged_optimal,
        "pvp_fast_correct": pvp_fast_correct,
        "pvp_charged_correct": pvp_charged_correct,
        "pvp_warnings": pvp_warnings,
        
        "pve_fast_optimal": pve_fast_optimal,
        "pve_charged_optimal": pve_charged_optimal,
        "pve_fast_correct": pve_fast_correct,
        "pve_charged_correct": pve_charged_correct,
        "pve_warnings": pve_warnings,
    })


@bp.route("/api/powerup-calculation", methods=["POST"])
def api_powerup_calculation():
    body = request.json or {}
    pid = body.get("pid")
    current_lvl = float(body.get("current_lvl", 1.0))
    target_lvl = float(body.get("target_lvl", 40.0))
    iv_a = int(body.get("iv_a", 0))
    iv_d = int(body.get("iv_d", 0))
    iv_s = int(body.get("iv_s", 0))
    shadow = bool(body.get("shadow"))
    lucky = bool(body.get("lucky"))
    purified = bool(body.get("purified"))
    
    if not pid:
        return jsonify({"error": "Brak pid"}), 400
        
    from data.powerup_costs import POWERUP_COSTS
    from scoring import calculate_cp_for_level
    
    import math
    
    stardust_sum = 0
    candy_sum = 0
    xl_candy_sum = 0
    
    lvl = current_lvl
    while lvl < target_lvl:
        key = str(lvl)
        if key.endswith(".0"):
            key_alt = key[:-2]
        else:
            key_alt = key
            
        cost = POWERUP_COSTS.get(key) or POWERUP_COSTS.get(key_alt)
        if cost:
            stardust_sum += cost.get("stardust_to_upgrade", 0)
            candy_sum += cost.get("candy_to_upgrade", 0)
            xl_candy_sum += cost.get("xl_candy_to_upgrade", 0)
        lvl += 0.5
        
    if shadow:
        stardust_sum = int(math.ceil(stardust_sum * 1.2))
        candy_sum = int(math.ceil(candy_sum * 1.2))
        xl_candy_sum = int(math.ceil(xl_candy_sum * 1.2))
    elif purified:
        stardust_sum = int(math.floor(stardust_sum * 0.9))
        candy_sum = int(math.floor(candy_sum * 0.9))
        xl_candy_sum = int(math.floor(xl_candy_sum * 0.9))
    elif lucky:
        stardust_sum = int(math.floor(stardust_sum * 0.5))
        
    target_cp = calculate_cp_for_level(pid, iv_a, iv_d, iv_s, target_lvl)
    
    return jsonify({
        "stardust": stardust_sum,
        "candy": candy_sum,
        "xl_candy": xl_candy_sum,
        "target_cp": target_cp
    })


@bp.route("/api/evolve-prediction", methods=["POST"])
def api_evolve_prediction():
    body = request.json or {}
    pid = body.get("pid")
    iv_a = int(body.get("iv_a", 0))
    iv_d = int(body.get("iv_d", 0))
    iv_s = int(body.get("iv_s", 0))
    lvl = float(body.get("lvl", 1.0))
    
    if not pid:
        return jsonify({"error": "Brak pid"}), 400
        
    from data.pokedex import DEX
    from scoring import calculate_cp_for_level
    
    evos = []
    curr = pid
    while curr in _EVOLVE_CHAIN:
        next_pid = _EVOLVE_CHAIN[curr]
        name = DEX.get(next_pid, f"#{next_pid}")
        cp = calculate_cp_for_level(next_pid, iv_a, iv_d, iv_s, lvl)
        
        fits_gl = cp <= 1500
        fits_ul = cp <= 2500
        
        evos.append({
            "pid": next_pid,
            "name": name,
            "cp": cp,
            "fits_gl": fits_gl,
            "fits_ul": fits_ul
        })
        curr = next_pid
        
    return jsonify({
        "evolutions": evos
    })
