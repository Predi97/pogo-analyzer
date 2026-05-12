import json
import logging
from datetime import timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config
from database import get_db
from scoring import _TIER_ORDER, _best_tier, _tier_for
from utils import _now, _now_iso, _parse_dt

log = logging.getLogger(__name__)

_FALLBACK_TIERS: dict[str, dict[str, str]] = {
    "Mewtwo":        {"raid": "S", "pvp_master": "S"},
    "Shadow Mewtwo": {"raid": "S"},
    "Rayquaza":      {"raid": "S", "pvp_master": "A"},
    "Kyogre":        {"raid": "S", "pvp_master": "A"},
    "Groudon":       {"raid": "S", "pvp_master": "A"},
    "Darkrai":       {"raid": "S"},
    "Giratina":      {"raid": "A", "pvp_master": "S", "pvp_ultra": "S"},
    "Dialga":        {"raid": "A", "pvp_master": "S"},
    "Palkia":        {"raid": "A", "pvp_master": "A"},
    "Garchomp":      {"raid": "A", "pvp_master": "S"},
    "Lucario":       {"raid": "A", "pvp_great": "A"},
    "Tyranitar":     {"raid": "A", "pvp_master": "A"},
    "Excadrill":     {"raid": "A", "pvp_great": "A"},
    "Machamp":       {"raid": "A"},
    "Swampert":      {"raid": "A", "pvp_great": "S", "pvp_ultra": "A"},
    "Mamoswine":     {"raid": "A"},
    "Rhyperior":     {"raid": "A"},
    "Dragonite":     {"raid": "A", "pvp_master": "A"},
    "Salamence":     {"raid": "A", "pvp_master": "A"},
    "Metagross":     {"raid": "A", "pvp_master": "A"},
    "Gengar":        {"raid": "A"},
    "Chandelure":    {"raid": "A"},
    "Roserade":      {"raid": "A"},
    "Togekiss":      {"pvp_great": "A", "pvp_ultra": "A", "pvp_master": "A"},
    "Altaria":       {"pvp_great": "S"},
    "Walrein":       {"pvp_great": "S", "pvp_ultra": "A"},
    "Bastiodon":     {"pvp_great": "S"},
    "Registeel":     {"pvp_great": "S", "pvp_ultra": "S"},
    "Cresselia":     {"pvp_ultra": "S", "pvp_great": "A"},
    "Gallade":       {"pvp_great": "A", "pvp_ultra": "A"},
    "Whimsicott":    {"pvp_great": "A"},
    "Galvantula":    {"pvp_great": "S"},
    "Toxapex":       {"pvp_great": "S"},
    "Azumarill":     {"pvp_great": "S"},
    "Medicham":      {"pvp_great": "S"},
    "Lanturn":       {"pvp_great": "A"},
    "Umbreon":       {"pvp_great": "S", "pvp_ultra": "A"},
    "Mew":           {"pvp_great": "A"},
    "Nihilego":      {"raid": "A", "pvp_ultra": "S"},
    "Xurkitree":     {"raid": "A"},
    "Buzzwole":      {"pvp_ultra": "A"},
    "Zacian":        {"pvp_master": "S"},
    "Ho-Oh":         {"pvp_master": "A"},
    "Lugia":         {"pvp_master": "A"},
    "Hydreigon":     {"raid": "A", "pvp_ultra": "A"},
    "Greninja":      {"pvp_great": "A", "pvp_ultra": "A"},
    "Corviknight":   {"pvp_ultra": "A"},
    "Goodra":        {"pvp_ultra": "S"},
    "Galarian Corsola": {"pvp_great": "S"},
}


def _tier_refresh_needed() -> bool:
    with get_db() as db:
        row = db.execute("SELECT last_ok FROM scrape_log WHERE source='pokebase'").fetchone()
    if not row or not row["last_ok"]:
        return True
    last = _parse_dt(row["last_ok"])
    return not last or _now() - last > timedelta(hours=config.TIER_REFRESH_HOURS)


def scrape_pokebase() -> dict[str, dict[str, str]]:
    tiers: dict[str, dict[str, str]] = {}
    try:
        resp = requests.get(config.POKEBASE_URL, headers=config.SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        next_tag = soup.find("script", id="__NEXT_DATA__")
        if next_tag and next_tag.string:
            try:
                page_data = json.loads(next_tag.string)
                props = (page_data.get("props") or {}).get("pageProps") or {}
                for key in ("tierList", "tiers", "data", "pokemonList"):
                    tier_data = props.get(key)
                    if isinstance(tier_data, list):
                        for entry in tier_data:
                            name = entry.get("name") or entry.get("pokemon")
                            tier = entry.get("tier") or entry.get("rank")
                            cat  = entry.get("category", "raid")
                            if name and tier:
                                tiers.setdefault(name, {})[cat] = tier.upper()
                        break
            except (json.JSONDecodeError, AttributeError):
                pass

        if not tiers:
            for tier_label in ("S", "A", "B", "C", "D"):
                for sel in (
                    f'[data-tier="{tier_label}"]',
                    f'.tier-{tier_label}',
                    f'[class*="tier-{tier_label.lower()}"]',
                ):
                    for div in soup.select(sel):
                        for el in div.select("span, p, .name, [class*='name']"):
                            name = el.get_text(strip=True)
                            if 2 < len(name) < 40:
                                tiers.setdefault(name, {})["raid"] = tier_label

        log.info("Pokebase scrape: %d Pokémon with tier data", len(tiers))
    except Exception as exc:
        log.warning("Pokebase scrape failed (%s) — using fallback data", exc)
        with get_db() as db:
            db.execute(
                "INSERT OR REPLACE INTO scrape_log (source, last_err) VALUES ('pokebase', ?)",
                (str(exc),),
            )

    merged = {k: dict(v) for k, v in _FALLBACK_TIERS.items()}
    for name, cats in tiers.items():
        merged.setdefault(name, {}).update(cats)

    now = _now_iso()
    with get_db() as db:
        for name, cats in merged.items():
            for cat, tier in cats.items():
                db.execute(
                    "INSERT OR REPLACE INTO tier_list (pokemon_name, tier, category, scraped_at) "
                    "VALUES (?, ?, ?, ?)",
                    (name, tier, cat, now),
                )
        db.execute(
            "INSERT OR REPLACE INTO scrape_log (source, last_ok) VALUES ('pokebase', ?)",
            (now,),
        )
    log.info("Tier list saved: %d entries total", sum(len(c) for c in merged.values()))
    return merged


def get_tier_list() -> dict[str, dict[str, str]]:
    if _tier_refresh_needed():
        scrape_pokebase()
    tiers: dict[str, dict[str, str]] = {}
    with get_db() as db:
        rows = db.execute("SELECT pokemon_name, tier, category FROM tier_list").fetchall()
    for row in rows:
        tiers.setdefault(row["pokemon_name"], {})[row["category"]] = row["tier"]
    return tiers
