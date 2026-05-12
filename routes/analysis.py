from flask import Blueprint, jsonify, request

from data.base_stats import _EVOLVE_CHAIN
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
    return jsonify(scored[:60])


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
