# ⚡ PokéGO Analyzer

> 🇬🇧 [English version](README.md)

Lokalna aplikacja webowa do analizy konta Pokemon GO na podstawie eksportu `PGSStats.json` z [PGSharp](https://www.pgsharp.com/).

---

## Funkcje

| Zakładka | Opis |
|---|---|
| 🎮 **Pokemony** | Tabela całego boxa z filtrowaniem, sortowaniem, search barem, generatorem regex i eksportem CSV |
| ⚔️ **Raidy** | Ranking najlepszych attackerów (DPS×TDO proxy + tier bonus) |
| 🏆 **PvP** | Kandydaci do GL / UL / ML z **IV Rankiem** (stat product, metodologia PvPoke) i % maksimum |
| 🎒 **Ekwipunek** | Lista itemów z ilościami + analiza AI co i na kogo użyć |
| 📅 **Eventy** | Nadchodzące i aktywne eventy z ScrapedDuck + strategia AI na każdy event |
| 🥇 **Tier Lista** | Scraper pokebase.app + wbudowany snapshot (~65 meta pokemonów) |
| 🔧 **Rozwój** | Kandydaci do ewolucji, power-up, oczyszczenia (purify shadow) i Elite TM |
| ⚙️ **Ustawienia** | Zmiana providera AI, klucze API, statystyki cache |

### PvP IV Rank
Każdy pokemon w zakładce PvP pokazuje swój **rank stat product** (rank 1 = najlepsze możliwe IV dla danej ligi):
- Stat Product = EffAtk × EffDef × floor(EffHP) przy najwyższym możliwym poziomie pod limitem CP
- Niższe IV Ataku często dają wyższy rank — pozwalają wejść na wyższy poziom pod tym samym limitem CP, zdobywając więcej bulk
- Przykład: Medicham GL → rank 1 to `0/13/15` (poziom 46, CP 1499), nie `15/15/15` (poziom 45.5, CP 1494)
- Kolory badge'a: 🥇 złoty (rank 1) · 🟢 zielony (top 1%) · 🟡 limonka (top 5%) · 🔵 cyan (top 10%)

### Generator regex do transferu
Pasek opcji nad tabelą Pokemonów generuje zapytanie zgodne z wyszukiwarką Pokemon GO:
- separator `,` (OR w PoGO)
- opcjonalnie: `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary`, `&cp-XXX`
- automatyczne wykluczanie gatunków, które mają cennego osobnika w boxie

### Tagi eventowe
Pokemony biorące udział w aktywnych lub nadchodzących eventach otrzymują badge 📅 z nazwą eventu w tooltip.

### AI cache
Odpowiedzi AI zapisywane w SQLite wg hasha IV/CP/shadow/shiny — ta sama kombinacja nie kosztuje drugiego tokenu.

### Persystencja stanu
Ostatnio wgrany JSON jest zapisywany w SQLite. Po odświeżeniu strony aplikacja przywraca dane automatycznie — nie trzeba wgrywać pliku ponownie.

---

## Wymagania

- Python 3.9+
- Konto Google AI Studio (darmowy klucz Gemini) — lub OpenAI / Anthropic / Azure OpenAI

---

## Instalacja

```bash
git clone https://github.com/Predi97/pogo-analyzer.git
cd pogo-analyzer

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # uzupełnij klucze API
```

### Plik `.env`

| Klucz | Opis |
|---|---|
| `AI_PROVIDER` | `gemini` \| `openai` \| `anthropic` \| `azure` |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/apikey) — darmowy tier |
| `OPENAI_API_KEY` | Opcjonalnie |
| `ANTHROPIC_API_KEY` | Opcjonalnie |
| `SECRET_KEY` | Losowy ciąg znaków dla sesji Flask |

---

## Uruchomienie

```bash
source venv/bin/activate
python app.py
```

Otwórz http://127.0.0.1:5000, wgraj `PGSStats.json` i gotowe.  
Przy kolejnym uruchomieniu dane są przywracane automatycznie.

---

## Stack

- **Backend** — Flask + SQLite (WAL mode)
- **Frontend** — Vanilla JS, bez frameworków; Syne + Manrope + JetBrains Mono przez Google Fonts
- **AI** — Google Gemini (domyślnie), OpenAI, Anthropic, Azure OpenAI
- **Dane eventów** — [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck)
- **Tier lista** — pokebase.app scraper + wbudowany snapshot

---

## Struktura plików

```
pogo-analyzer/
├── app.py                  # entry point Flask (~40 linii), rejestracja blueprintów
├── config.py               # env vars, stałe, URLs
├── utils.py                # helpers (_now, _parse_dt)
├── database.py             # get_db(), init_db(), cache AI, persystencja stanu
├── state.py                # singleton in-memory (_state dict)
├── parser.py               # parse_pgo_json() — bez dependencji Flask
├── scoring.py              # matematyka raid i PvP, pvp_iv_rank()
├── data/
│   ├── pokedex.py          # DEX (1000 pokemonów), ITEMS, resolver nazw
│   ├── base_stats.py       # statystyki bazowe 183 meta pokemonów, łańcuchy ewolucji
│   └── cpm.py              # pełna tabela CPM (99 poziomów), cpm_to_level()
├── services/
│   ├── ai.py               # call_ai(), 4 providerzy, buildery promptów
│   ├── events.py           # fetch_events(), get_events()
│   └── tiers.py            # scrape_pokebase(), get_tier_list()
├── routes/
│   ├── pokemon.py          # /api/upload, /api/pokemons, /api/items, /api/status
│   ├── analysis.py         # /api/raid-candidates, /api/pvp-candidates, /api/develop-candidates
│   ├── ai_routes.py        # /api/analyze-pokemon, /api/analyze-items, /api/event-strategy
│   └── misc.py             # /api/events, /api/tier-list, /api/config, /api/cache/stats
├── templates/
│   └── index.html          # cały frontend (HTML + CSS + JS, jeden plik)
├── requirements.txt
├── .env.example
└── .gitignore
```

`baza_pogo.db` tworzy się automatycznie przy pierwszym uruchomieniu.

---

## Uwagi

- Aplikacja działa **wyłącznie lokalnie** — dane nie opuszczają maszyny poza wywołaniami AI
- Darmowy tier Gemini: 15 req/min — przy rate limicie app automatycznie próbuje kolejnych dostępnych modeli
- Scraper tier listy pokebase.app może zwracać 0 wyników (strona renderuje JS) — działa fallback snapshot
- Ranki PvP IV są zgodne z metodologią [PvPoke](https://pvpoke.com/) (stat product z game-accurate floor na HP)
