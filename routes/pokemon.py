import csv
import io
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from database import get_db, save_upload
from parser import parse_pgo_json, parse_pokegenie_csv
from scoring import _best_tier, _tier_for, pvp_iv_rank
from services.events import get_events
from services.tiers import get_tier_list
from state import _state
from utils import _now_iso
from data.moves import MOVES

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
        filename = f.filename.lower()
        if filename.endswith(".csv"):
            csv_content = f.read().decode("utf-8")
            parsed = parse_pokegenie_csv(csv_content)
            raw_to_save = {
                "source": "pokegenie",
                "data": parsed
            }
        else:
            raw = json.load(f)
            parsed = parse_pgo_json(raw)
            raw_to_save = raw

        _state["pokemons"]  = parsed["pokemons"]
        _state["items"]     = parsed["items"]
        _state["player"]    = parsed["player"]
        _state["pvp_stats"] = parsed["pvp_stats"]
        _state["loaded"]    = True
        n = len(parsed["pokemons"])
        log.info("Uploaded: %d pokemons, %d item types", n, len(parsed["items"]))
        save_upload(raw_to_save)
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
    from data.pokemon_db import POKEMON_DB
    for p in _state["pokemons"]:
        tier_data  = _tier_for(p["name"], tiers)
        event_tags = event_spawn_index.get(p["name"].lower(), [])
        gl_rank, _, _gl_pct = pvp_iv_rank(p["pid"], p["iv_a"], p["iv_d"], p["iv_s"], 1500)
        
        move1_id = p.get("move1")
        move2_id = p.get("move2")
        move3_id = p.get("move3")
        
        m1 = MOVES.get(move1_id) if move1_id else None
        m2 = MOVES.get(move2_id) if move2_id else None
        m3 = MOVES.get(move3_id) if move3_id else None
        
        name_key = p["name"].lower().replace(" (shadow)", "").replace(" (purified)", "")
        db_entry = POKEMON_DB.get(name_key)
        if not db_entry:
            matched_key = next((k for k in POKEMON_DB.keys() if k in name_key or name_key in k), None)
            if matched_key:
                db_entry = POKEMON_DB[matched_key]
        types = db_entry.get("types", ["normal"]) if db_entry else ["normal"]
        
        result.append({
            **p,
            "tiers":      tier_data,
            "best_tier":  _best_tier(tier_data),
            "event_tags": event_tags,
            "gl_rank":    gl_rank,
            "types":      types,
            "move1_name": m1["name"] if m1 else "",
            "move1_type": m1["type"] if m1 else "",
            "move2_name": m2["name"] if m2 else "",
            "move2_type": m2["type"] if m2 else "",
            "move3_name": m3["name"] if m3 else "",
            "move3_type": m3["type"] if m3 else "",
        })
    return jsonify(result)


@bp.route("/api/items")
def api_items():
    return jsonify(_state["items"])


@bp.route("/api/export/raw-csv")
def export_raw_csv():
    """1:1 export from raw PGSStats.json — all fields + species name."""
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
        """Flatten nested structures to a string."""
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

    # Gather all unique keys (preserve order: important fields first)
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
    """Export inventory: stardust, coins, rare candy + complete items list."""
    db  = get_db()
    row = db.execute("SELECT raw_json FROM last_upload WHERE id=1").fetchone()
    if not row:
        return jsonify({"error": "Brak danych — wgraj najpierw PGSStats.json"}), 404

    raw     = json.loads(row["raw_json"])
    items   = raw.get("items", [])
    account = raw.get("account", {})

    # stardust / coins from currencyBalance
    currencies = {c["currencyType"]: c["quantity"]
                  for c in account.get("currencyBalance", [])
                  if "currencyType" in c}

    out    = io.StringIO()
    writer = csv.writer(out)

    # ── Section 1: currency summary ─────────────────────────────────────────
    writer.writerow(["=== CURRENCIES ===", ""])
    writer.writerow(["Resource", "Quantity"])
    writer.writerow(["Stardust",    currencies.get("STARDUST", 0)])
    writer.writerow(["PokéCoins",   currencies.get("POKECOIN", 0)])
    writer.writerow([])

    # ── Section 2: complete inventory list ──────────────────────────────────
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
            "nandos":     sum(1 for p in pokemons if p["iv_a"] == 0 and p["iv_d"] == 0 and p["iv_s"] == 0),
            "item_types": len(_state["items"]),
            "stardust":   _state["player"].get("stardust", 0) if _state.get("player") else stardust,
        },
        "player": _state.get("player"),
        "pvp_stats": _state.get("pvp_stats")
    })


@bp.route("/api/raid-counters")
def api_raid_counters():
    boss_name = request.args.get("boss", "").strip()
    if not boss_name:
        return jsonify({"error": "Brak nazwy bossa"}), 400
        
    from data.pokemon_db import POKEMON_DB
    from data.moves import MOVES
    from data.cpm import level_to_cpm
    import math
    
    # 1. Resolve Boss Types
    def clean_name(raw_name: str) -> str:
        s = raw_name.lower()
        s = s.replace(" (shadow)", "")
        s = s.replace(" (mega)", "")
        s = s.replace(" (primal)", "")
        s = s.replace(" (mega x)", "")
        s = s.replace(" (mega y)", "")
        s = s.replace("♀", "♀").replace("♂", "♂")
        s = s.replace("mr. mime", "mr. mime")
        s = s.replace("mime jr.", "mime jr.")
        s = s.replace("ho-oh", "ho-oh")
        s = s.replace("porygon-z", "porygon-z")
        s = s.replace("jangmo-o", "jangmo-o")
        s = s.replace("hakamo-o", "hakamo-o")
        s = s.replace("kommo-o", "kommo-o")
        s = s.replace("farfetch'd", "farfetch'd")
        s = s.replace("sirfetch'd", "sirfetch'd")
        s = s.replace("flabébé", "flabébé")
        return s.strip()
        
    boss_key = clean_name(boss_name)
    boss_entry = POKEMON_DB.get(boss_key)
    if not boss_entry:
        # Try matching by checking if any key is contained in boss_key or vice versa
        matched_key = next((k for k in POKEMON_DB.keys() if k in boss_key or boss_key in k), None)
        if matched_key:
            boss_entry = POKEMON_DB[matched_key]
            
    if not boss_entry:
        return jsonify({"error": f"Nie znaleziono danych o bossie: {boss_name}"}), 404
        
    boss_types = boss_entry["types"]
    
    # 2. Type chart
    TYPE_CHART = {
        "normal":   {"rock": 0.625, "ghost": 0.39, "steel": 0.625},
        "fire":     {"fire": 0.625, "water": 0.625, "grass": 1.6, "ice": 1.6, "bug": 1.6, "rock": 0.625, "dragon": 0.625, "steel": 1.6},
        "water":    {"fire": 1.6, "water": 0.625, "grass": 0.625, "ground": 1.6, "rock": 1.6, "dragon": 0.625},
        "electric": {"water": 1.6, "electric": 0.625, "grass": 0.625, "ground": 0.39, "flying": 1.6, "dragon": 0.625},
        "grass":    {"fire": 0.625, "water": 1.6, "grass": 0.625, "poison": 0.625, "ground": 1.6, "flying": 0.625, "bug": 0.625, "rock": 1.6, "dragon": 0.625, "steel": 0.625},
        "ice":      {"fire": 0.625, "water": 0.625, "grass": 1.6, "ice": 0.625, "ground": 1.6, "flying": 1.6, "dragon": 1.6, "steel": 0.625},
        "fighting": {"normal": 1.6, "ice": 1.6, "poison": 0.625, "flying": 0.625, "psychic": 0.625, "bug": 0.625, "rock": 1.6, "ghost": 0.39, "dark": 1.6, "steel": 1.6, "fairy": 0.625},
        "poison":   {"grass": 1.6, "poison": 0.625, "ground": 0.625, "rock": 0.625, "ghost": 0.625, "steel": 0.39, "fairy": 1.6},
        "ground":   {"fire": 1.6, "electric": 1.6, "grass": 0.625, "poison": 1.6, "flying": 0.39, "bug": 0.625, "rock": 1.6, "steel": 1.6},
        "flying":   {"electric": 0.625, "grass": 1.6, "fighting": 1.6, "bug": 1.6, "rock": 0.625, "steel": 0.625},
        "psychic":  {"fighting": 1.6, "poison": 1.6, "psychic": 0.625, "dark": 0.39, "steel": 0.625},
        "bug":      {"fire": 0.625, "grass": 1.6, "fighting": 0.625, "poison": 0.625, "flying": 0.625, "ghost": 0.625, "steel": 0.625, "fairy": 0.625},
        "rock":     {"fire": 1.6, "ice": 1.6, "fighting": 0.625, "ground": 0.625, "flying": 1.6, "bug": 1.6, "steel": 0.625},
        "ghost":    {"normal": 0.39, "psychic": 1.6, "ghost": 1.6, "dark": 0.625},
        "dragon":   {"dragon": 1.6, "steel": 0.625, "fairy": 0.39},
        "dark":     {"fighting": 0.625, "psychic": 1.6, "ghost": 1.6, "dark": 0.625, "fairy": 0.625},
        "steel":    {"fire": 0.625, "water": 0.625, "electric": 0.625, "ice": 1.6, "rock": 1.6, "steel": 0.625, "fairy": 1.6},
        "fairy":    {"fire": 0.625, "fighting": 1.6, "poison": 0.625, "dragon": 1.6, "dark": 1.6, "steel": 0.625}
    }
    
    def get_effectiveness(atk_type: str, def_types: list[str]) -> float:
        mult = 1.0
        for dt in def_types:
            mult *= TYPE_CHART.get(atk_type, {}).get(dt, 1.0)
        return mult

    # 3. Rate pokemons in user's box
    rated = []
    for p in _state["pokemons"]:
        # Get base stats of attacker
        name_key = clean_name(p["name"])
        att_entry = POKEMON_DB.get(name_key)
        if not att_entry:
            # Fallback
            att_entry = {"types": ["normal"], "stats": [150, 150, 150]}
            
        base_atk, base_def, base_sta = att_entry["stats"]
        lvl_mult = level_to_cpm(p["lvl"])
        
        # Attacker stats
        atk = (base_atk + p["iv_a"]) * lvl_mult
        dfn = (base_def + p["iv_d"]) * lvl_mult
        sta = (base_sta + p["iv_s"]) * lvl_mult
        
        # Shadow adjustments
        if p["shadow"]:
            atk *= 1.2
            dfn *= 0.8333
            
        tankiness = dfn * sta
        
        # Moves
        move1_id = p.get("move1")
        move2_id = p.get("move2")
        move3_id = p.get("move3")
        
        m1 = MOVES.get(move1_id) if move1_id else None
        m2 = MOVES.get(move2_id) if move2_id else None
        m3 = MOVES.get(move3_id) if move3_id else None
        
        # Calculate move DPS
        def get_move_score(move, is_fast_default):
            if not move:
                return 0.0
            m_type = move.get("type", "normal")
            m_power = move.get("power", 6.0 if is_fast_default else 50.0)
            eff = get_effectiveness(m_type, boss_types)
            stab = 1.2 if m_type in att_entry["types"] else 1.0
            return m_power * eff * stab

        m1_score = get_move_score(m1, True)
        m2_score = get_move_score(m2, False)
        m3_score = get_move_score(m3, False)
        
        ch_score = max(m2_score, m3_score)
        
        # Combined moves score (weighted cycle DPS proxy)
        cycle_dps = 0.25 * m1_score + 0.75 * ch_score
        
        # Score combining DPS and tankiness (TDO)
        counter_score = int(atk * cycle_dps * math.sqrt(tankiness) / 10.0)
        
        rated.append({
            "pid": p["pid"],
            "name": p["name"],
            "cp": p["cp"],
            "lvl": p["lvl"],
            "iv_pct": p["iv_pct"],
            "iv_a": p["iv_a"],
            "iv_d": p["iv_d"],
            "iv_s": p["iv_s"],
            "shiny": p["shiny"],
            "shadow": p["shadow"],
            "lucky": p["lucky"],
            "counter_score": counter_score,
            "fast_move": m1["name"] if m1 else "Unknown",
            "fast_move_type": m1["type"] if m1 else "",
            "charged_move": (m2["name"] if m2_score >= m3_score else m3["name"]) if (m2 or m3) else "Unknown",
            "charged_move_type": (m2["type"] if m2_score >= m3_score else m3["type"]) if (m2 or m3) else ""
        })
        
    # Sort and take top 6
    rated.sort(key=lambda x: -x["counter_score"])
    top_counters = rated[:6]
    
    return jsonify({
        "boss": boss_name,
        "boss_types": boss_types,
        "counters": top_counters
    })
