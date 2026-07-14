import hashlib
import json
import logging
import re
from datetime import timedelta

import requests

import config
from database import get_db
from utils import _now, _now_iso, _parse_dt
from data.pokedex import DEX
from data.base_stats import _EVOLVE_CHAIN

log = logging.getLogger(__name__)

_name_to_id = {name.lower(): pid for pid, name in DEX.items()}



def _events_refresh_needed() -> bool:
    with get_db() as db:
        row = db.execute("SELECT last_ok FROM scrape_log WHERE source='events'").fetchone()
    if not row or not row["last_ok"]:
        return True
    last = _parse_dt(row["last_ok"])
    return not last or _now() - last > timedelta(hours=config.EVENT_REFRESH_HOURS)


def fetch_events(force: bool = False) -> list[dict]:
    if not force and not _events_refresh_needed():
        return []
    try:
        resp = requests.get(config.SCRAPEDDUCK_URL, headers=config.SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        events_raw: list[dict] = resp.json()
        now_str = _now_iso()
        with get_db() as db:
            for ev in events_raw:
                ev_id = ev.get("id") or hashlib.md5(
                    (ev.get("name", "") + ev.get("start", "")).encode()
                ).hexdigest()[:12]
                db.execute(
                    "INSERT OR REPLACE INTO events "
                    "(id, name, start_time, end_time, event_type, raw_json, fetched_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        ev_id,
                        ev.get("name", ""),
                        ev.get("start", ""),
                        ev.get("end", ""),
                        ev.get("eventType") or ev.get("type") or "",
                        json.dumps(ev),
                        now_str,
                    ),
                )
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_ok) VALUES ('events', ?)",
                (now_str,),
            )
        log.info("Events fetched: %d", len(events_raw))
        return events_raw
    except Exception as exc:
        log.error("Events fetch failed: %s", exc)
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_err) VALUES ('events', ?)",
                (str(exc),),
            )
        return []


def get_events() -> list[dict]:
    fetch_events()
    from services.tiers import get_tier_list
    tier_list = get_tier_list()
    
    # Compile scan names from DEX and tier list
    scan_names = set(DEX.values())
    for t_name in tier_list.keys():
        scan_names.add(t_name)
    sorted_scan_names = sorted(list(scan_names), key=len, reverse=True)
    
    with get_db() as db:
        rows = db.execute(
            "SELECT id, name, start_time, end_time, event_type, raw_json "
            "FROM events ORDER BY start_time ASC LIMIT 80"
        ).fetchall()

    now = _now()
    upcoming, active, ended = [], [], []

    for row in rows:
        try:
            raw = json.loads(row["raw_json"]) if row["raw_json"] else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}

        start_dt = _parse_dt(row["start_time"])
        end_dt   = _parse_dt(row["end_time"])

        if start_dt and end_dt:
            if now < start_dt:
                status     = "upcoming"
                days_until = max(0, (start_dt - now).days)
            elif now > end_dt:
                status     = "ended"
                days_until = None
            else:
                status     = "active"
                days_until = 0
        else:
            status     = "unknown"
            days_until = None

        # Extract pokemons
        featured_pokemons = []
        extra = raw.get("extraData", {})
        
        def add_poke(p_name, source, image=None, can_be_shiny=None):
            if not p_name:
                return
            if any(x["name"].lower() == p_name.lower() for x in featured_pokemons):
                return
                
            tiers = None
            evolves_to = None
            is_evo = False
            
            # 1. Try direct lookup in tier list
            if p_name in tier_list:
                tiers = tier_list[p_name]
            else:
                # 2. Try lowercase direct lookup
                match_name = next((k for k in tier_list.keys() if k.lower() == p_name.lower()), None)
                if match_name:
                    tiers = tier_list[match_name]
                else:
                    # 3. Check if it's in DEX and has an evolution in _EVOLVE_CHAIN
                    pid = _name_to_id.get(p_name.lower())
                    if pid and pid in _EVOLVE_CHAIN:
                        evo_id = _EVOLVE_CHAIN[pid]
                        evo_name = DEX.get(evo_id)
                        if evo_name:
                            evolves_to = evo_name
                            is_evo = True
                            # Look up evolved form in tier list
                            if evo_name in tier_list:
                                tiers = tier_list[evo_name]
                            else:
                                match_name = next((k for k in tier_list.keys() if k.lower() == evo_name.lower()), None)
                                if match_name:
                                    tiers = tier_list[match_name]
                                    
            featured_pokemons.append({
                "name": p_name,
                "source": source,
                "image": image or f"https://img.pokemondb.net/sprites/sword-shield/icon/{p_name.lower().replace(' ', '-')}.png",
                "can_be_shiny": can_be_shiny,
                "tiers": tiers,
                "is_evolution": is_evo,
                "evolves_to": evolves_to
            })

        # 1. Raid battles
        if "raidbattles" in extra:
            for b in extra["raidbattles"].get("bosses", []):
                add_poke(b.get("name"), "Rajdy (Boss)", b.get("image"), b.get("canBeShiny"))

        # 2. Spotlight
        if "spotlight" in extra:
            sp = extra["spotlight"]
            for item in sp.get("list", []):
                add_poke(item.get("name"), "Spotlight Hour", item.get("image"), item.get("canBeShiny"))
            if not sp.get("list") and sp.get("name"):
                add_poke(sp.get("name"), "Spotlight Hour", sp.get("image"), sp.get("canBeShiny"))

        # 3. Community Day
        if "communityday" in extra:
            cd = extra["communityday"]
            for s in cd.get("spawns", []):
                add_poke(s.get("name"), "Community Day", s.get("image"), True)
            for s in cd.get("shinies", []):
                add_poke(s.get("name"), "Community Day", s.get("image"), True)

        # 4. Title Scan
        for p in sorted_scan_names:
            if re.search(r'\b' + re.escape(p) + r'\b', row["name"] or "", re.IGNORECASE):
                add_poke(p, "Wydarzenie")
            elif p.lower() in (row["name"] or "").lower():
                add_poke(p, "Wydarzenie")

        # Extract bonuses
        bonuses = raw.get("bonuses", [])
        if not bonuses:
            if "communityday" in extra and "bonuses" in extra["communityday"]:
                for b in extra["communityday"]["bonuses"]:
                    if isinstance(b, dict) and "text" in b:
                        bonuses.append(b["text"])
                    elif isinstance(b, str):
                        bonuses.append(b)
            elif "spotlight" in extra and "bonus" in extra["spotlight"]:
                bonus = extra["spotlight"]["bonus"]
                if bonus:
                    bonuses.append(bonus)

        entry = {
            "id":                 row["id"],
            "name":               row["name"],
            "start":              row["start_time"],
            "end":                row["end_time"],
            "type":               row["event_type"],
            "status":             status,
            "days_until":         days_until,
            "bonuses":            bonuses,
            "link":               raw.get("link", ""),
            "heading":            raw.get("heading", ""),
            "extraData":          extra,
            "featured_pokemons":  featured_pokemons,
        }
        (upcoming if status == "upcoming" else active if status == "active" else ended).append(entry)

    upcoming.sort(key=lambda e: e["start"] or "")
    active.sort(key=lambda e: e["start"] or "", reverse=True)
    ended.sort(key=lambda e: e["end"] or "", reverse=True)
    return upcoming + active + ended
