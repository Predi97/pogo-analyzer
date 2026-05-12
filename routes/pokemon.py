import json
import logging

from flask import Blueprint, jsonify, request

from database import get_db, save_upload
from parser import parse_pgo_json
from scoring import _best_tier, _tier_for, pvp_iv_rank
from services.events import get_events
from services.tiers import get_tier_list
from state import _state
from utils import _now_iso

log = logging.getLogger(__name__)
bp  = Blueprint("pokemon", __name__)


@bp.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Brak pliku w żądaniu"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Pusty plik"}), 400
    try:
        raw    = json.load(f)
        parsed = parse_pgo_json(raw)
        _state["pokemons"] = parsed["pokemons"]
        _state["items"]    = parsed["items"]
        _state["loaded"]   = True
        n = len(parsed["pokemons"])
        log.info("Uploaded: %d pokemons, %d item types", n, len(parsed["items"]))
        save_upload(raw)
        return jsonify({
            "ok": True,
            "stats": {
                "total":      n,
                "shinies":    sum(1 for p in parsed["pokemons"] if p["shiny"]),
                "shadows":    sum(1 for p in parsed["pokemons"] if p["shadow"]),
                "hundos":     sum(1 for p in parsed["pokemons"] if p["hundo"]),
                "luckies":    sum(1 for p in parsed["pokemons"] if p["lucky"]),
                "item_types": len(parsed["items"]),
            },
        })
    except Exception as exc:
        log.exception("Upload parse error")
        return jsonify({"error": str(exc)}), 400


@bp.route("/api/pokemons")
def api_pokemons():
    tiers = get_tier_list()

    event_spawn_index: dict[str, list[str]] = {}
    try:
        for ev in get_events():
            if ev["status"] not in ("active", "upcoming"):
                continue
            label = ev["name"][:22].rstrip()
            for s in ev.get("spawns", []):
                pname = (s if isinstance(s, str) else s.get("name", "")).strip().lower()
                if pname:
                    event_spawn_index.setdefault(pname, []).append(label)
    except Exception:
        pass

    result = []
    for p in _state["pokemons"]:
        tier_data  = _tier_for(p["name"], tiers)
        event_tags = event_spawn_index.get(p["name"].lower(), [])
        gl_rank, _, _gl_pct = pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], 1500)
        result.append({
            **p,
            "tiers":      tier_data,
            "best_tier":  _best_tier(tier_data),
            "event_tags": event_tags,
            "gl_rank":    gl_rank,
        })
    return jsonify(result)


@bp.route("/api/items")
def api_items():
    return jsonify(_state["items"])


@bp.route("/api/status")
def api_status():
    if not _state["loaded"]:
        return jsonify({"loaded": False})
    pokemons = _state["pokemons"]
    return jsonify({
        "loaded": True,
        "stats": {
            "total":      len(pokemons),
            "shinies":    sum(1 for p in pokemons if p["shiny"]),
            "shadows":    sum(1 for p in pokemons if p["shadow"]),
            "hundos":     sum(1 for p in pokemons if p["hundo"]),
            "luckies":    sum(1 for p in pokemons if p["lucky"]),
            "item_types": len(_state["items"]),
        },
    })
