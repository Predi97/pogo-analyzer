from flask import Blueprint, jsonify, request

from data.base_stats import _EVOLVE_CHAIN, _BS
from data.pokedex import DEX
from scoring import (
    _TIER_ORDER, _best_tier, _tier_for,
    max_cp, pvp_cp, pvp_iv_rank, pvp_score, raid_score,
)
from services.tiers import get_tier_list
from state import _state

bp = Blueprint("analysis", __name__)


@bp.route("/api/raid-candidates")
def api_raid_candidates():
    tiers  = get_tier_list()
    scored = []
    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        score = raid_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], tiers, p["name"])
        if score < 1:
            continue
        tier_data = _tier_for(p["name"], tiers)
        scored.append({
            **p,
            "raid_score": round(score),
            "max_cp":     max_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"]),
            "tiers":      tier_data,
            "best_tier":  _best_tier(tier_data),
        })
    scored.sort(key=lambda x: -x["raid_score"])
    return jsonify(scored[:60])


def build_local_teams(candidates: list[dict], league: str) -> list[dict]:
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

    leads = []
    switches = []
    closers = []

    for c in candidates:
        name = c["name"]
        role = PVP_ROLES.get(name)
        if not role:
            bs = _BS.get(c["pid"])
            if bs:
                atk, dfs, sta = bs
                if dfs + sta > 2.2 * atk:
                    role = "Safe Switch"
                elif atk > 1.1 * dfs:
                    role = "Closer"
                else:
                    role = "Lead"
            else:
                role = "Lead"

        c_with_role = {**c, "pvp_role": role}

        if "Lead" in role:
            leads.append(c_with_role)
        if "Safe Switch" in role:
            switches.append(c_with_role)
        if "Closer" in role:
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

    if len(teams) < 2:
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

    return teams


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
        })
    scored.sort(key=lambda x: -x["pvp_score"])
    top_candidates = scored[:60]

    local_teams = build_local_teams(scored[:20], league)

    return jsonify({
        "candidates": top_candidates,
        "local_teams": local_teams
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
                evolve.append({**p, "final_name": final_name,
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
            elite_tm.append({**p, "tiers": own_tiers, "best_tier": own_tier})

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
