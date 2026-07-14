import logging

from flask import Blueprint, jsonify, request

from database import get_cache, make_hash, set_cache
from scoring import _tier_for
from services.ai import (
    _SYSTEM_EXPERT, _SYSTEM_TACTICIAN,
    build_event_prompt, build_items_prompt, build_pokemon_prompt,
    build_pvp_teams_prompt, call_ai,
)
from services.tiers import get_tier_list
from state import _state

log = logging.getLogger(__name__)
bp  = Blueprint("ai_routes", __name__)


@bp.route("/api/analyze-pokemon", methods=["POST"])
def analyze_pokemon():
    body = request.json or {}
    p    = body.get("pokemon")
    if not p:
        return jsonify({"error": "Brak danych pokemona"}), 400

    h = make_hash(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"],
                  p.get("shadow"), p.get("shiny"), "v3")
    cached = get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    tiers     = get_tier_list()
    tier_data = _tier_for(p["name"], tiers)
    top_items = [f"{it['name']} ×{it['count']}" for it in _state["items"][:12]]

    try:
        resp = call_ai(build_pokemon_prompt(p, tier_data, top_items), _SYSTEM_EXPERT)
        set_cache(h, p["name"], resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        log.error("AI error: %s", exc)
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@bp.route("/api/analyze-items", methods=["POST"])
def analyze_items():
    items = _state["items"]
    if not items:
        return jsonify({"error": "Brak danych ekwipunku"}), 400

    top_pokes = [p for p in _state["pokemons"] if p["iv_pct"] >= 80][:15]
    h = make_hash(
        [(it["id"], it["count"]) for it in items[:25]],
        [(p["pid"], p["iv_pct"]) for p in top_pokes[:10]],
        "items_v3",
    )
    cached = get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    try:
        resp = call_ai(build_items_prompt(items, top_pokes), _SYSTEM_EXPERT)
        set_cache(h, "items_analysis", resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@bp.route("/api/event-strategy", methods=["POST"])
def api_event_strategy():
    body  = request.json or {}
    event = body.get("event")
    if not event:
        return jsonify({"error": "Brak danych eventu"}), 400

    acct_hash = make_hash(
        [(p["pid"], p["cp"], p["iv_pct"]) for p in _state["pokemons"][:25]],
        [(it["id"], it["count"]) for it in _state["items"][:15]],
    )
    h      = f"evt_{event['id']}_{acct_hash}"
    cached = get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})

    featured_pokes = event.get("featured_pokemons", [])
    featured_names = {p["name"].lower() for p in featured_pokes}

    def clean_name(n):
        n = n.replace("Mega ", "").replace("Shadow ", "").replace("Alolan ", "").replace("Galarian ", "").replace("Hisuian ", "")
        return n.split(" ")[0].strip().lower()

    clean_featured = {clean_name(name) for name in featured_names}

    matching_inventory = [
        p for p in _state["pokemons"]
        if clean_name(p["name"]) in clean_featured
    ]

    top_combat = sorted(
        [p for p in _state["pokemons"] if p.get("cp", 0) > 1500 or p.get("iv_pct", 0) >= 90],
        key=lambda p: (p.get("cp", 0), p.get("iv_pct", 0)),
        reverse=True
    )[:20]

    combined = []
    seen = set()
    for p in matching_inventory:
        if p["pid"] not in seen:
            combined.append(p)
            seen.add(p["pid"])
    for p in top_combat:
        if p["pid"] not in seen:
            combined.append(p)
            seen.add(p["pid"])

    relevant = combined[:30]

    try:
        resp = call_ai(
            build_event_prompt(event, relevant, _state["items"]),
            _SYSTEM_TACTICIAN,
        )
        set_cache(h, event["name"], resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        return jsonify({"error": f"Błąd AI: {exc}"}), 500


@bp.route("/api/analyze-pvp-teams", methods=["POST"])
def api_analyze_pvp_teams():
    body = request.json or {}
    league = body.get("league", "GL")
    
    limits = {"GL": 1500, "UL": 2500, "ML": 100000}
    keys = {"GL": "pvp_great", "UL": "pvp_ultra", "ML": "pvp_master"}
    cp_limit = limits.get(league, 1500)
    lkey = keys.get(league, "pvp_great")
    
    tiers = get_tier_list()
    scored = []
    
    for p in _state["pokemons"]:
        if p.get("isEgg"):
            continue
        if league != "ML" and p["cp"] > cp_limit:
            continue
        from scoring import pvp_score, pvp_cp, pvp_iv_rank
        score = pvp_score(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"],
                          cp_limit, tiers, p["name"], lkey)
        if score < 1:
            continue
        lvl, best_cp = pvp_cp(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        rank, total, rank_pct = pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], cp_limit)
        scored.append({
            **p,
            "pvp_score": round(score),
            "pvp_cp": best_cp,
            "pvp_lvl": lvl,
            "pvp_rank": rank,
            "pvp_rank_pct": rank_pct,
        })
        
    scored.sort(key=lambda x: -x["pvp_score"])
    top_candidates = scored[:25]
    
    h = make_hash(
        league,
        [(p["pid"], p["cp"], p["iv_pct"], p["pvp_rank"]) for p in top_candidates],
        "pvp_teams_v1"
    )
    cached = get_cache(h)
    if cached:
        return jsonify({"response": cached, "cached": True})
        
    prompt = build_pvp_teams_prompt(league, top_candidates)
    
    try:
        resp = call_ai(prompt, _SYSTEM_TACTICIAN)
        set_cache(h, f"pvp_teams_{league}", resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        log.error("AI error in pvp teams analysis: %s", exc)
        return jsonify({"error": f"Błąd AI: {exc}"}), 500
