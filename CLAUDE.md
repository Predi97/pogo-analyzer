# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
source venv/bin/activate
python app.py
```

App runs at http://127.0.0.1:5000. On startup it calls `init_db()`, `load_last_state()` (restores last upload from SQLite), and optionally kicks off a background tier scrape.

## Setup from scratch

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in at least one AI key
```

Required `.env` keys: `AI_PROVIDER` (`gemini`|`openai`|`anthropic`|`azure`), the matching API key, and optionally `SECRET_KEY`.

## Architecture

**Single-user local Flask app** — no auth, no workers, no background tasks except the tier-list scrape thread.

### Data flow

1. User uploads `PGSStats.json` (from PGSharp) → `POST /api/upload`
2. `parser.parse_pgo_json()` walks the raw JSON tree (depth-first) to extract Pokémon and items — no schema assumed, works regardless of nesting
3. Parsed result is stored in the in-memory `_state` singleton (`state.py`) and persisted as raw JSON in `last_upload` SQLite table
4. On server restart `database.load_last_state()` re-parses from DB → `_state` is restored

### Module map

| Module | Role |
|---|---|
| `app.py` | Flask app, blueprint registration, startup hooks |
| `config.py` | All env vars and constants — single source of truth |
| `state.py` | Global `_state` dict (`pokemons`, `items`, `loaded`) — mutated in-place, imported by reference |
| `database.py` | `get_db()`, `init_db()`, AI response cache (hash→response), upload persistence |
| `parser.py` | `parse_pgo_json()` — pure function, no Flask dependency |
| `scoring.py` | Raid score, PvP score, `pvp_iv_rank()` (PvPoke stat-product method) |
| `data/` | Static game data: `DEX` (1000 Pokémon), `_BS` base stats (183 meta), `_CPM_VALUES` (CPM table), `_EVOLVE_CHAIN` |
| `services/ai.py` | `call_ai()` dispatches to Gemini/OpenAI/Anthropic/Azure; prompt builders for each analysis type |
| `services/events.py` | Fetches upcoming events from ScrapedDuck, caches in SQLite |
| `services/tiers.py` | Scrapes pokebase.app tier list, falls back to built-in snapshot, caches 24 h |
| `routes/pokemon.py` | `/api/upload`, `/api/pokemons`, `/api/items`, `/api/status` |
| `routes/analysis.py` | `/api/raid-candidates`, `/api/pvp-candidates`, `/api/develop-candidates` |
| `routes/ai_routes.py` | `/api/analyze-pokemon`, `/api/analyze-items`, `/api/event-strategy` |
| `routes/misc.py` | `/api/events`, `/api/tier-list`, `/api/config`, `/api/cache/stats` |
| `templates/index.html` | Entire frontend — HTML + CSS + vanilla JS in one file |

### Key design decisions

- **`_state` is a module-level singleton** — routes import it directly and mutate it in-place. Never replace the dict object, always mutate its keys.
- **AI cache key** is a SHA-256 hash of the Pokémon's IVs/CP/shadow/shiny flags so the same individual never costs a second API call.
- **Gemini fallback chain**: `services/ai.py` fetches available flash models at runtime and tries them in order on 429/404; the model list is cached 1 hour.
- **PvP IV rank** (`scoring.pvp_iv_rank`) builds a sorted table of all 4096 stat products for a species+CP cap, cached in `_rank_cache`. Rank 1 = highest stat product, matching PvPoke methodology — lower ATK IVs often rank better because they permit a higher level under the CP cap.
- **`baza_pogo.db`** is auto-created; uses WAL mode. Tables: `ai_cache`, `tier_list`, `events`, `event_strategies`, `scrape_log`, `last_upload`.
- **AI prompts are in Polish** — the system prompt and all user-facing prompt builders in `services/ai.py` produce Polish output.
