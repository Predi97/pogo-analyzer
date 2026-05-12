from flask import Blueprint, jsonify, request

import config
from database import get_db
from services.events import fetch_events, get_events
from services.tiers import get_tier_list, scrape_pokebase

bp = Blueprint("misc", __name__)


@bp.route("/api/events")
def api_events():
    return jsonify(get_events())


@bp.route("/api/events/refresh", methods=["POST"])
def api_refresh_events():
    evs = fetch_events(force=True)
    return jsonify({"ok": True, "count": len(evs)})


@bp.route("/api/tier-list")
def api_tier_list():
    return jsonify(get_tier_list())


@bp.route("/api/tier-list/refresh", methods=["POST"])
def api_refresh_tiers():
    data = scrape_pokebase()
    return jsonify({"ok": True, "count": len(data)})


@bp.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        body = request.json or {}
        if "provider"       in body: config.AI_PROVIDER       = body["provider"]
        if "gemini_key"     in body: config.GEMINI_API_KEY    = body["gemini_key"]
        if "openai_key"     in body: config.OPENAI_API_KEY    = body["openai_key"]
        if "anthropic_key"  in body: config.ANTHROPIC_API_KEY = body["anthropic_key"]
        if "azure_key"      in body: config.AZURE_API_KEY     = body["azure_key"]
        if "azure_endpoint" in body: config.AZURE_ENDPOINT    = body["azure_endpoint"]
        return jsonify({"ok": True, "provider": config.AI_PROVIDER})

    return jsonify({
        "provider":         config.AI_PROVIDER,
        "has_gemini":       bool(config.GEMINI_API_KEY),
        "has_openai":       bool(config.OPENAI_API_KEY),
        "has_anthropic":    bool(config.ANTHROPIC_API_KEY),
        "has_azure":        bool(config.AZURE_API_KEY and config.AZURE_ENDPOINT),
        "azure_deployment": config.AZURE_DEPLOYMENT,
    })


@bp.route("/api/cache/stats")
def api_cache_stats():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
        today = db.execute(
            "SELECT COUNT(*) FROM ai_cache WHERE created_at > datetime('now', '-24 hours')"
        ).fetchone()[0]
    return jsonify({"total": total, "today": today, "est_saved_usd": round(total * 0.002, 2)})
