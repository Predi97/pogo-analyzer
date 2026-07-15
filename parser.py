from datetime import datetime
import csv
import io

from data.cpm import cpm_to_level
from data.pokedex import _FORM_SUFFIXES, _resolve_item_name


def _pokemon_name(pid: int, form_name: str) -> str:
    from data.pokedex import DEX
    base = DEX.get(pid, f"#{pid}")
    if not form_name or form_name == "Unset" or form_name == "Normal":
        return base
    
    # Check for predefined suffixes that get single-letter abbreviation
    from data.pokedex import _FORM_SUFFIXES
    for sfx in _FORM_SUFFIXES:
        if form_name.endswith(sfx):
            if sfx == "Normal":
                return base
            return f"{base} ({sfx[0]})"
            
    # Clean the form name (e.g. "ZacianCrownedSword" -> "Zacian Crowned Sword", "CROWNED_SWORD" -> "Crowned Sword")
    import re
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', form_name)
    clean_form = spaced.replace("_", " ").title()
    if clean_form.lower().startswith(base.lower()):
        clean_form = clean_form[len(base):].strip()
        
    if not clean_form:
        return base
    return f"{base} ({clean_form})"


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


def parse_pokegenie_csv(csv_content: str) -> dict:
    from data.pokedex import DEX
    from data.moves import MOVES
    
    move_map = {}
    for mid, mdata in MOVES.items():
        move_map[mdata["name"].lower().strip()] = mid
        
    f = io.StringIO(csv_content.strip())
    reader = csv.DictReader(f)
    
    pokemons = []
    
    form_map = {
        "Galar": "Galarian",
        "Alola": "Alolan",
        "Hisui": "Hisuian",
        "Paldea": "Paldean"
    }
    
    for row in reader:
        if "Pokemon" not in row or "CP" not in row:
            continue
            
        pid_str = row.get("Pokemon")
        if not pid_str or not pid_str.isdigit():
            continue
        pid = int(pid_str)
        
        cp = int(row.get("CP") or 0)
        
        try:
            lvl = float(row.get("Level Min") or row.get("Level Max") or 1.0)
        except ValueError:
            lvl = 1.0
            
        iv_avg_str = row.get("IV Avg", "").replace("%", "")
        try:
            iv_avg = float(iv_avg_str) if iv_avg_str else 0.0
        except ValueError:
            iv_avg = 0.0
            
        def parse_iv(val):
            if val is None or val.strip() == "":
                return None
            try:
                return int(val)
            except ValueError:
                return None
                
        iv_a = parse_iv(row.get("Atk IV"))
        iv_d = parse_iv(row.get("Def IV"))
        iv_s = parse_iv(row.get("Sta IV"))
        
        if iv_a is None or iv_d is None or iv_s is None:
            est = int(round(iv_avg * 15 / 100))
            iv_a = iv_a if iv_a is not None else est
            iv_d = iv_d if iv_d is not None else est
            iv_s = iv_s if iv_s is not None else est
            
        iv_pct = round((iv_a + iv_d + iv_s) / 45 * 100, 1)
        
        form_raw = row.get("Form", "").strip()
        form_mapped = form_map.get(form_raw, form_raw)
        name = _pokemon_name(pid, form_mapped)
        
        lucky = int(row.get("Lucky") or 0) == 1
        shadow_val = int(row.get("Shadow/Purified") or 0)
        shadow = shadow_val == 1
        purified = shadow_val == 2
        
        m1_name = row.get("Quick Move", "").lower().strip()
        m2_name = row.get("Charge Move", "").lower().strip()
        m3_name = row.get("Charge Move 2", "").lower().strip()
        
        move1 = move_map.get(m1_name, 0)
        move2 = move_map.get(m2_name, 0)
        move3 = move_map.get(m3_name, 0)
        
        pokemons.append({
            "pid": pid,
            "name": name,
            "cp": cp,
            "lvl": lvl,
            "iv_a": iv_a,
            "iv_d": iv_d,
            "iv_s": iv_s,
            "iv_pct": iv_pct,
            "shiny": False,
            "shadow": shadow,
            "purified": purified,
            "fav": int(row.get("Favorite") or 0) == 1,
            "lucky": lucky,
            "hundo": iv_pct == 100.0,
            "year": 0,
            "nick": row.get("Name", ""),
            "move1": move1,
            "move2": move2,
            "move3": move3,
        })
        
    pokemons.sort(key=lambda x: -x["cp"])
    
    player_info = {
        "name": "PokéGenie Import",
        "team": 0,
        "level": 0,
        "experience": 0,
        "kmWalked": 0.0,
        "pokemonsCaught": len(pokemons),
        "eggsHatched": 0,
        "evolutions": 0,
        "pokeStopsVisited": 0,
        "stardust": 0,
        "coins": 0,
        "maxPokeStorage": len(pokemons) + 100,
        "maxItemStorage": 500
    }
    
    pvp_info = {
        "season_rank": 0,
        "season_battles": 0,
        "season_wins": 0,
        "season_stardust": 0,
        "season_streak": 0,
        "season_longest_streak": 0,
        "lifetime_battles": 0,
        "lifetime_wins": 0,
        "lifetime_stardust": 0,
        "lifetime_longest_streak": 0,
        "gl_battles": 0,
        "gl_wins": 0,
        "ul_battles": 0,
        "ul_wins": 0,
        "ml_battles": 0,
        "ml_wins": 0,
    }
    
    return {
        "pokemons": pokemons,
        "items": [],
        "player": player_info,
        "pvp_stats": pvp_info
    }
