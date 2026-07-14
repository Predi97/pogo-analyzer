# ⚡ PokéGO Analyzer

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Support" />
  <img src="https://img.shields.io/badge/framework-Flask-lightgrey.svg?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/database-SQLite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/AI-Gemini%20%7C%20OpenAI%20%7C%20Anthropic-orange.svg?style=for-the-badge&logo=google-gemini&logoColor=white" alt="AI Support" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge" alt="License" />
</p>

> 🇵🇱 **[Wersja polska (Polish Version)](README.pl.md)**

A professional, local web application for analyzing your Pokémon GO account, managing PvP/Raid candidates, and planning event tactics with a personalized AI coach. Powered by the `PGSStats.json` export from **PGSharp**.

---

## 🌟 Key Features

| Tab | Feature Description |
| :--- | :--- |
| 🧑‍💼 **Player Profile** | Beautiful sidebar profile card displaying your username, trainer level, team affiliation (Mystic ❄️, Valor 🔥, Instinct ⚡), PokéCoins, and total Stardust. |
| 🎮 **Pokémon Box** | Full inventory dashboard with advanced searching, sorting, filters, and a **Transfer Regex Generator** for bulk box management. |
| ⚔️ **Raid Attackers** | PVE attacker ranks utilizing a custom DPS×TDO proxy combined with meta tier list multipliers to identify your top attackers. |
| 🏆 **PvP Analyzer** | Evaluates Great, Ultra, and Master League candidates with **IV Rank** (stat-product, matching PvPoke methodology) and displays detailed badge indicators. |
| 🤖 **PvP Team Builder** | AI-powered 3-pokemon team builder (Lead, Safe Switch, Closer) tailored to your box, analyzing type synergies and meta counters. |
| 📅 **Event Calendar** | Dynamic countdown timers, Pokémon spawn directories, raid boss trackers, and meta tier indicators synced with live events. |
| 🎒 **Items & Inventory** | Complete inventory breakdown with a smart AI analysis showing exactly which items to apply to which Pokémon. |
| 🔧 **Power-Up Planner** | Dedicated dashboard highlighting candidate priorities for evolution, power-ups, purification, and Elite TMs. |
| ⚙️ **Settings Panel** | Switch AI providers, configure API keys, and monitor SQLite response cache hits. |

---

## 🛡️ PvP IV Rank Methodology

Each Pokémon in the PvP tab displays its **stat-product rank** (rank 1 = best possible IV combination for the CP limit):
- **Formula:** $\text{Stat Product} = \text{Effective Atk} \times \text{Effective Def} \times \lfloor\text{Effective HP}\rfloor$ at the highest reachable level under the league CP cap.
- **Bulk Optimization:** Lower Attack IVs are preferred as they allow the Pokémon to reach a higher level, yielding higher defensive stats and total bulk.
- **Ranks and Badges:**
  - 🥇 **Gold Badge** — Rank 1 (Perfect PvP IVs)
  - 🟢 **Green Badge** — Top 1% (Excellent bulk)
  - 🟡 **Yellow Badge** — Top 5% (Very Good)
  - 🔵 **Cyan Badge** — Top 10% (Good)

---

## 📂 Bulk Transfer Query Generator

The search generator bar above the Pokémon table generates queries compatible with the in-game search box:
- Separates terms with `,` (logical OR in Pokémon GO).
- Optional toggles like `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary`, and `&cp-XXX`.
- **Smart Protection:** Automatically excludes any species where you hold a highly valuable individual (e.g., Shiny, Shadow, Lucky, Hundo, or PvP Rank 1).

---

## 💾 SQLite Caching & Local State

- **Zero Data Leakage:** All processing is done locally. Your credentials and file uploads are saved inside a secure local SQLite database (`baza_pogo.db`).
- **Response Cache:** AI responses are cached using a cryptographic hash of the input query (IVs, CP, shininess, level). Identical requests bypass the API and return instantly, saving request tokens.
- **Session Restoration:** Upon page reload, the server automatically reads the last uploaded raw JSON from the database and restores your dashboard.

---

## 🛠️ Quick Start

### Requirements
- Python 3.9+
- A Google Gemini API Key (obtain a free key at [Google AI Studio](https://aistudio.google.com/apikey)) or access to OpenAI, Anthropic, or Azure OpenAI.

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Predi97/pogo-analyzer.git
   cd pogo-analyzer
   ```

2. **Set up Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Open .env and add your GEMINI_API_KEY
   ```

### Execution

```bash
python app.py
```
Open **[http://127.0.0.1:5000](http://127.0.0.1:5000)** in your browser and upload your `PGSStats.json` export to initialize the dashboard.

---

## 🗄️ File Structure

```
pogo-analyzer/
├── app.py                  # Flask application entry point
├── config.py               # Configuration variables & external scrape URLs
├── utils.py                # Formatting and datetime helper utilities
├── database.py             # SQLite WAL-mode connection & caching database
├── state.py                # Global application in-memory state
├── parser.py               # PGSStats.json file parser
├── scoring.py              # Attacker calculations & PvP stat product math
├── data/
│   ├── pokedex.py          # Complete Pokédex (1000+ entries) & items mapping
│   ├── base_stats.py       # Stat formulas, meta ratings, and evolution chains
│   └── cpm.py              # Full CPM table (Levels 1 to 50, incl. half levels)
├── services/
│   ├── ai.py               # AI client initialization & prompt templates
│   ├── events.py           # ScrapedDuck event scrapper
│   └── tiers.py            # Pokebase meta tier list scrapper
├── routes/
│   ├── pokemon.py          # Box upload, CSV export, and status endpoints
│   ├── analysis.py         # Raid & PvP candidate ranking endpoints
│   ├── ai_routes.py        # Custom AI prompt calls & pvp team builder API
│   └── misc.py             # Event, config, and tier configuration routes
├── templates/
│   └── index.html          # Frontend dashboard (HTML + CSS + JS)
├── requirements.txt        # Python package dependencies
└── .env.example            # Environment template file
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
