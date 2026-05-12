import logging

from flask import Blueprint, jsonify, request

from database import get_cache, make_hash, set_cache
from scoring import _tier_for
from services.ai import (
    _SYSTEM_EXPERT, _SYSTEM_TACTICIAN,
    build_event_prompt, build_items_prompt, build_pokemon_prompt,
    call_ai,
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

    spawn_names = {
        (s.get("name") or s).lower()
        for s in event.get("spawns", []) + event.get("shinies", [])
        if s
    }
    relevant = [
        p for p in _state["pokemons"]
        if any(sn in p["name"].lower() for sn in spawn_names if sn)
    ][:12]

    try:
        resp = call_ai(
            build_event_prompt(event, relevant, _state["items"]),
            _SYSTEM_TACTICIAN,
        )
        set_cache(h, event["name"], resp)
        return jsonify({"response": resp, "cached": False})
    except Exception as exc:
        return jsonify({"error": f"Błąd AI: {exc}"}), 500
