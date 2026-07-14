import csv
import io
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

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
        _state["pokemons"]  = parsed["pokemons"]
        _state["items"]     = parsed["items"]
        _state["player"]    = parsed["player"]
        _state["pvp_stats"] = parsed["pvp_stats"]
        _state["loaded"]    = True
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
            "player": parsed["player"],
            "pvp_stats": parsed["pvp_stats"]
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


@bp.route("/api/export/raw-csv")
def export_raw_csv():
    """Eksport 1:1 z surowego PGSStats.json — wszystkie pola + nazwa gatunku."""
    db = get_db()
    row = db.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
    if not row:
        return jsonify({"error": "Brak danych — wgraj najpierw PGSStats.json"}), 404

    raw      = json.loads(row["raw_json"])
    pokemons = raw.get("pokemons", [])
    if not pokemons:
        return jsonify({"error": "Brak pokemonów w danych"}), 404

    # DEX: pid → name
    try:
        from data.pokedex import DEX
    except ImportError:
        DEX = {}

    def _cell(v):
        """Spłaszcz zagnieżdżone struktury do stringa."""
        if v is None or v == "" or v == [] or v == {}:
            return ""
        if isinstance(v, bool):
            return "TAK" if v else ""
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        return v

    def _ms_to_date(ms):
        if not ms:
            return ""
        try:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return ms

    # zbierz wszystkie unikalne klucze (zachowaj kolejność: ważne pola pierwsze)
    priority = [
        "name", "pokemonId", "nickname", "cp", "cpMultiplier",
        "individualAttack", "individualDefense", "individualStamina",
        "move1", "move2", "move3",
        "isLucky", "favorite", "isBad", "isEgg", "isFusion",
        "hatchedFromEgg", "hasMegaEvolved",
        "numUpgrades", "stamina", "maxStamina",
        "heightM", "weightKg", "size",
        "pokeball", "pokemonDisplay",
        "battlesAttacked", "battlesDefended",
        "buddyKmWalked", "buddyCandyAwarded",
        "creationTimeMs", "tradedTimeMs",
        "originEvents", "originDetail",
        "capturedS2CellId", "fromFort",
        "id",
    ]
    all_keys = list(dict.fromkeys(
        priority + [k for p in pokemons for k in p if k not in priority]
    ))

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(all_keys)

    for p in pokemons:
        pid  = p.get("pokemonId", 0)
        name = DEX.get(pid, f"#{pid}")
        row_data = []
        for k in all_keys:
            if k == "name":
                row_data.append(name)
            elif k == "creationTimeMs":
                row_data.append(_ms_to_date(p.get(k)))
            elif k == "tradedTimeMs":
                row_data.append(_ms_to_date(p.get(k)))
            else:
                row_data.append(_cell(p.get(k)))
        writer.writerow(row_data)

    csv_bytes = ("﻿" + out.getvalue()).encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pogo_raw_export.csv"'},
    )


@bp.route("/api/export/inventory-csv")
def export_inventory_csv():
    """Eksport ekwipunku: stardust, coiny, rare candy + pełna lista itemów."""
    db  = get_db()
    row = db.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
    if not row:
        return jsonify({"error": "Brak danych — wgraj najpierw PGSStats.json"}), 404

    raw     = json.loads(row["raw_json"])
    items   = raw.get("items", [])
    account = raw.get("account", {})

    # stardust / coiny z currencyBalance
    currencies = {c["currencyType"]: c["quantity"]
                  for c in account.get("currencyBalance", [])
                  if "currencyType" in c}

    out    = io.StringIO()
    writer = csv.writer(out)

    # ── Sekcja 1: podsumowanie walut ─────────────────────────────────────────
    writer.writerow(["=== WALUTY ===", ""])
    writer.writerow(["Zasób", "Ilość"])
    writer.writerow(["Stardust",    currencies.get("STARDUST", 0)])
    writer.writerow(["PokéCoiny",   currencies.get("POKECOIN", 0)])
    writer.writerow([])

    # ── Sekcja 2: pełna lista ekwipunku ──────────────────────────────────────
    writer.writerow(["=== EKWIPUNEK ===", "", "", ""])
    if items:
        all_keys = list(dict.fromkeys(k for it in items for k in it))
        writer.writerow(all_keys)
        for it in sorted(items, key=lambda x: x.get("count", 0), reverse=True):
            writer.writerow([it.get(k, "") for k in all_keys])
    else:
        writer.writerow(["brak itemów"])

    csv_bytes = ("﻿" + out.getvalue()).encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pogo_inventory.csv"'},
    )


@bp.route("/api/status")
def api_status():
    if not _state["loaded"]:
        return jsonify({"loaded": False})
    pokemons = _state["pokemons"]

    stardust = 0
    try:
        db  = get_db()
        row = db.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
        if row:
            raw      = json.loads(row["raw_json"])
            balances = raw.get("account", {}).get("currencyBalance", [])
            stardust = next((c["quantity"] for c in balances
                             if c.get("currencyType") == "STARDUST"), 0)
    except Exception:
        pass

    return jsonify({
        "loaded": True,
        "stats": {
            "total":      len(pokemons),
            "shinies":    sum(1 for p in pokemons if p["shiny"]),
            "shadows":    sum(1 for p in pokemons if p["shadow"]),
            "hundos":     sum(1 for p in pokemons if p["hundo"]),
            "luckies":    sum(1 for p in pokemons if p["lucky"]),
            "item_types": len(_state["items"]),
            "stardust":   _state["player"].get("stardust", 0) if _state.get("player") else stardust,
        },
        "player": _state.get("player"),
        "pvp_stats": _state.get("pvp_stats")
    })
