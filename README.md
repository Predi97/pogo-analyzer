# ⚡ PokéGO Analyzer

> 🇵🇱 [Wersja polska](README.pl.md)

A local web app for analyzing your Pokémon GO account using the `PGSStats.json` export from [PGSharp](https://www.pgsharp.com/).

---

## Features

| Tab | Description |
|---|---|
| 🎮 **Pokémon** | Full box table with filtering, sorting, search and a transfer regex generator |
| ⚔️ **Raids** | Best attacker ranking (DPS×TDO proxy + tier bonus) |
| 🏆 **PvP** | Candidates for GL / UL / ML — only Pokémon that fit within the league CP limit |
| 🎒 **Items** | Item list with counts + AI analysis of what to use on whom |
| 📅 **Events** | Upcoming & active events from ScrapedDuck + AI strategy for each event |
| 🥇 **Tier List** | pokebase.app scraper with a built-in fallback snapshot (~65 meta Pokémon) |
| 🔧 **Development** | Candidates for evolution, power-up, shadow purification and Elite TM |
| ⚙️ **Settings** | Switch AI provider, manage API keys, view cache stats |

### Transfer Regex Generator
A filter bar above the Pokémon table generates a search query compatible with the in-game search:
- `,` separator (OR in Pokémon GO)
- Optional flags: `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary`, `&cp-XXX`
- Automatically skips species that have a valuable individual in the box

### AI Cache
AI responses are stored in SQLite by a hash of IV/CP/shadow/shiny — the same combination never costs a second API call.

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

---

## Tech Stack

- **Backend** — Flask + SQLite (WAL mode)
- **Frontend** — Vanilla JS, no frameworks
- **AI** — Google Gemini (default), OpenAI, Anthropic, Azure OpenAI
- **Event data** — [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck)
- **Tier list** — pokebase.app scraper + built-in snapshot

---

## File Structure

```
pogo-analyzer/
├── app.py              # full Flask backend
├── templates/
│   └── index.html      # full frontend (HTML + CSS + JS)
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
