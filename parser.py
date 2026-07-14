from datetime import datetime

from data.cpm import cpm_to_level
from data.pokedex import _FORM_SUFFIXES, _resolve_item_name


def _pokemon_name(pid: int, form_name: str) -> str:
    from data.pokedex import DEX
    base = DEX.get(pid, f"#{pid}")
    if not form_name or form_name == "Unset":
        return base
    for sfx in _FORM_SUFFIXES:
        if form_name.endswith(sfx):
            return base if sfx == "Normal" else f"{base} ({sfx[0]})"
    return base


def parse_pgo_json(raw: dict) -> dict:
    """
    Walk the entire JSON tree and pull out:
      - arrays whose first element has 'individualAttack'  → pokemons
      - items from top-level 'items' key OR nested arrays  → items
    Works regardless of nesting depth.
    """
    pokemon_rows: list[dict] = []
    item_map: dict[int, int] = {}
    item_json_names: dict[int, str] = {}

    raw_items = raw.get("items", [])
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            iid   = it.get("item") or it.get("itemId")
            cnt   = it.get("count", 0)
            jname = it.get("itemName", "") or ""
            if iid is not None and cnt:
                item_map[iid] = item_map.get(iid, 0) + cnt
                if jname and iid not in item_json_names:
                    item_json_names[iid] = jname

    def _walk(node):
        if isinstance(node, list):
            if node and isinstance(node[0], dict):
                if "individualAttack" in node[0] and "pokemonId" in node[0]:
                    pokemon_rows.extend(node)
                    return
                if not item_map and "itemId" in node[0] and "count" in node[0]:
                    for it in node:
                        iid = it.get("itemId")
                        if iid is not None:
                            item_map[iid] = item_map.get(iid, 0) + it.get("count", 0)
                    return
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)

    _walk(raw)

    pokemons: list[dict] = []
    for p in pokemon_rows:
        if not p.get("pokemonId") or p.get("isEgg"):
            continue
        pid  = p["pokemonId"]
        pd   = p.get("pokemonDisplay") or {}
        iv_a = p.get("individualAttack", 0)
        iv_d = p.get("individualDefense", 0)
        iv_s = p.get("individualStamina", 0)
        iv   = round((iv_a + iv_d + iv_s) / 45 * 100, 1)
        cpm  = (p.get("cpMultiplier") or 0.0) + (p.get("additionalCpMultiplier") or 0.0)
        year = 0
        if p.get("creationTimeMs"):
            year = datetime.fromtimestamp(p["creationTimeMs"] / 1000).year

        pokemons.append({
            "pid":    pid,
            "name":   _pokemon_name(pid, pd.get("formName", "")),
            "cp":     p.get("cp", 0),
            "lvl":    cpm_to_level(cpm),
            "iv_a":   iv_a,
            "iv_d":   iv_d,
            "iv_s":   iv_s,
            "iv_pct": iv,
            "shiny":  bool(pd.get("shiny")),
            "shadow": pd.get("alignment", 0) == 1,
            "fav":    bool(p.get("favorite")),
            "lucky":  bool(p.get("isLucky")),
            "hundo":  iv == 100.0,
            "year":   year,
            "nick":   p.get("nickname") or "",
            "move1":  p.get("move1"),
            "move2":  p.get("move2"),
            "move3":  p.get("move3"),
        })

    pokemons.sort(key=lambda x: -x["cp"])

    items = [
        {"id": iid, "name": _resolve_item_name(iid, item_json_names.get(iid, "")), "count": cnt}
        for iid, cnt in sorted(item_map.items(), key=lambda kv: -kv[1])
    ]

    # ── Player Info & Currency ────────────────────────────────────────────────
    player_raw = raw.get("player", {})
    account_raw = raw.get("account", {})

    stardust = 0
    coins = 0
    currency = account_raw.get("currencyBalance", [])
    if isinstance(currency, list):
        for c in currency:
            if c.get("currencyType") == "STARDUST":
                stardust = c.get("quantity", 0)
            elif c.get("currencyType") == "POKECOIN":
                coins = c.get("quantity", 0)

    player_info = {
        "name": account_raw.get("name", ""),
        "team": account_raw.get("team", 0), # 1: Mystic, 2: Valor, 3: Instinct
        "level": player_raw.get("level", 0),
        "experience": player_raw.get("experience", 0),
        "kmWalked": round(player_raw.get("kmWalked", 0.0), 1),
        "pokemonsCaught": player_raw.get("numPokemonCaptured", 0),
        "eggsHatched": player_raw.get("numEggsHatched", 0),
        "evolutions": player_raw.get("numEvolutions", 0),
        "pokeStopsVisited": player_raw.get("pokeStopVisits", 0),
        "stardust": stardust,
        "coins": coins,
        "maxPokeStorage": account_raw.get("maxPokemonStorage", 500),
        "maxItemStorage": account_raw.get("maxItemStorage", 500)
    }

    # ── PVP Statistics ────────────────────────────────────────────────────────
    combat_log = account_raw.get("combatLog", {})
    curr_season = combat_log.get("currentSeasonResults", {})
    lifetime = combat_log.get("lifetimeResults", {})

    combat_stats = player_raw.get("combatStats", {})
    badges = combat_stats.get("badges", {})

    gl_data = badges.get("52", {}) or badges.get(52, {}) or {}
    ul_data = badges.get("53", {}) or badges.get(53, {}) or {}
    ml_data = badges.get("54", {}) or badges.get(54, {}) or {}

    pvp_info = {
        "season_rank": curr_season.get("rank", 0),
        "season_battles": curr_season.get("totalBattles", 0),
        "season_wins": curr_season.get("totalWins", 0),
        "season_stardust": curr_season.get("stardustEarned", 0),
        "season_streak": curr_season.get("currentStreak", 0),
        "season_longest_streak": curr_season.get("longestWinStreak", 0),

        "lifetime_battles": lifetime.get("totalBattles", 0),
        "lifetime_wins": lifetime.get("totalWins", 0),
        "lifetime_stardust": lifetime.get("stardustEarned", 0),
        "lifetime_longest_streak": lifetime.get("longestWinStreak", 0),

        "gl_battles": gl_data.get("numTotal", 0),
        "gl_wins": gl_data.get("numWon", 0),
        "ul_battles": ul_data.get("numTotal", 0),
        "ul_wins": ul_data.get("numWon", 0),
        "ml_battles": ml_data.get("numTotal", 0),
        "ml_wins": ml_data.get("numWon", 0),
    }

    return {
        "pokemons": pokemons,
        "items": items,
        "player": player_info,
        "pvp_stats": pvp_info
    }
