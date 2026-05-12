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

    return {"pokemons": pokemons, "items": items}
