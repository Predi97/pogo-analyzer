# ⚡ PokéGO Analyzer

> 🇵🇱 [Wersja polska](README.pl.md)

A local web app for analyzing your Pokémon GO account using the `PGSStats.json` export from [PGSharp](https://www.pgsharp.com/).

---

## Features

| Tab | Description |
|---|---|
| 🎮 **Pokémon** | Full box table with filtering, sorting, search, transfer regex generator and CSV export |
| ⚔️ **Raids** | Best attacker ranking (DPS×TDO proxy + tier bonus) |
| 🏆 **PvP** | Candidates for GL / UL / ML with **IV Rank** (stat product, PvPoke-compatible) and % of max |
| 🎒 **Items** | Item list with counts + AI analysis of what to use on whom |
| 📅 **Events** | Upcoming & active events from ScrapedDuck + AI strategy for each event |
| 🥇 **Tier List** | pokebase.app scraper with a built-in fallback snapshot (~65 meta Pokémon) |
| 🔧 **Development** | Candidates for evolution, power-up, shadow purification and Elite TM |
| ⚙️ **Settings** | Switch AI provider, manage API keys, view cache stats |

### PvP IV Rank
Each Pokémon in the PvP tab shows its **stat-product rank** (rank 1 = best possible IVs for that league):
- Stat Product = EffAtk × EffDef × floor(EffHP) at the highest reachable level under the CP cap
- Lower ATK IVs often rank higher — they allow a higher level under the cap, gaining more bulk
- Example: Medicham GL → rank 1 is `0/13/15` (level 46, CP 1499), not `15/15/15` (level 45.5, CP 1494)
- Badge colours: 🥇 gold (rank 1) · 🟢 green (top 1%) · 🟡 lime (top 5%) · 🔵 cyan (top 10%)

### Transfer Regex Generator
A filter bar above the Pokémon table generates a search query compatible with the in-game search:
- `,` separator (OR in Pokémon GO)
- Optional flags: `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary`, `&cp-XXX`
- Automatically skips species that have a valuable individual in the box

### Event Tags
Pokémon that appear in active or upcoming events get a 📅 badge with the event name as tooltip.

### AI Cache
AI responses are stored in SQLite by a hash of IV/CP/shadow/shiny — the same combination never costs a second API call.

### State Persistence
The last uploaded JSON is saved to SQLite. On page refresh the app restores automatically — no need to re-upload.

---

## Requirements

- Python 3.9+
- A Google AI Studio account (free Gemini key) — or OpenAI / Anthropic / Azure OpenAI

---

## Installation

```bash
git clone https://github.com/Predi97/pogo-analyzer.git
cd pogo-analyzer

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # fill in your API keys
```

### `.env` keys

| Key | Description |
|---|---|
| `AI_PROVIDER` | `gemini` \| `openai` \| `anthropic` \| `azure` |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/apikey) — free tier |
| `OPENAI_API_KEY` | Optional |
| `ANTHROPIC_API_KEY` | Optional |
| `SECRET_KEY` | Random string for Flask sessions |

---

## Usage

```bash
source venv/bin/activate
python app.py
```

Open http://127.0.0.1:5000, upload your `PGSStats.json` and you're good to go.  
On subsequent runs the last upload is restored automatically.

---

## Tech Stack

- **Backend** — Flask + SQLite (WAL mode)
- **Frontend** — Vanilla JS, no frameworks; Syne + Manrope + JetBrains Mono via Google Fonts
- **AI** — Google Gemini (default), OpenAI, Anthropic, Azure OpenAI
- **Event data** — [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck)
- **Tier list** — pokebase.app scraper + built-in snapshot

---

## File Structure

```
pogo-analyzer/
├── app.py                  # Flask entry point (~40 lines), blueprint registration
├── config.py               # env vars, constants, URLs
├── utils.py                # shared helpers (_now, _parse_dt)
├── database.py             # get_db(), init_db(), AI cache, state persistence
├── state.py                # in-memory singleton (_state dict)
├── parser.py               # parse_pgo_json() — no Flask dependency
├── scoring.py              # raid & PvP math, pvp_iv_rank()
├── data/
│   ├── pokedex.py          # DEX (1000 Pokémon), ITEMS, item name resolver
│   ├── base_stats.py       # base stats for 183 meta Pokémon, evolution chains
│   └── cpm.py              # full CPM table (99 levels), cpm_to_level()
├── services/
│   ├── ai.py               # call_ai(), all 4 providers, prompt builders
│   ├── events.py           # fetch_events(), get_events()
│   └── tiers.py            # scrape_pokebase(), get_tier_list()
├── routes/
│   ├── pokemon.py          # /api/upload, /api/pokemons, /api/items, /api/status
│   ├── analysis.py         # /api/raid-candidates, /api/pvp-candidates, /api/develop-candidates
│   ├── ai_routes.py        # /api/analyze-pokemon, /api/analyze-items, /api/event-strategy
│   └── misc.py             # /api/events, /api/tier-list, /api/config, /api/cache/stats
├── templates/
│   └── index.html          # full frontend (HTML + CSS + JS, single file)
├── requirements.txt
├── .env.example
└── .gitignore
```

`baza_pogo.db` is created automatically on first run.

---

## Notes

- The app runs **entirely locally** — your data never leaves your machine except for AI API calls
- Gemini free tier: 15 req/min — on rate limit the app automatically tries the next available model
- The pokebase.app tier list scraper may return 0 results (JS-rendered site) — the built-in snapshot is used as fallback
- PvP IV ranks match [PvPoke](https://pvpoke.com/) methodology (stat product with game-accurate CP floor)
