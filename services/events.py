import hashlib
import json
import logging
from datetime import timedelta

import requests

import config
from database import get_db
from utils import _now, _now_iso, _parse_dt

log = logging.getLogger(__name__)


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
                        ev.get("type", ""),
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

        entry = {
            "id":         row["id"],
            "name":       row["name"],
            "start":      row["start_time"],
            "end":        row["end_time"],
            "type":       row["event_type"],
            "status":     status,
            "days_until": days_until,
            "bonuses":    raw.get("bonuses", []),
            "spawns":     raw.get("spawns", [])[:20],
            "shinies":    raw.get("shinies", [])[:20],
            "link":       raw.get("link", ""),
            "heading":    raw.get("heading", ""),
            "extraData":  raw.get("extraData", {}),
        }
        (upcoming if status == "upcoming" else active if status == "active" else ended).append(entry)

    upcoming.sort(key=lambda e: e["start"] or "")
    active.sort(key=lambda e: e["start"] or "", reverse=True)
    ended.sort(key=lambda e: e["end"] or "", reverse=True)
    return upcoming + active + ended
