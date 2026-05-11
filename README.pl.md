# ⚡ PokéGO Analyzer

> 🇬🇧 [English version](README.md)

Lokalna aplikacja webowa do analizy konta Pokemon GO na podstawie eksportu `PGSStats.json` z [PGSharp](https://www.pgsharp.com/).

---

## Funkcje

| Zakładka | Opis |
|---|---|
| 🎮 **Pokemony** | Tabela całego boxa z filtrowaniem, sortowaniem, search barem i generatorem regex do masowego transferu |
| ⚔️ **Raidy** | Ranking najlepszych attackerów (DPS×TDO proxy + tier bonus) |
| 🏆 **PvP** | Kandydaci do GL / UL / ML — tylko pokemon mieszczące się w limicie CP danej ligi |
| 🎒 **Ekwipunek** | Lista itemów z ilościami + analiza AI co i na kogo użyć |
| 📅 **Eventy** | Nadchodzące i aktywne eventy z ScrapedDuck + strategia AI na każdy event |
| 🥇 **Tier Lista** | Scraper pokebase.app + wbudowany snapshot (~65 meta pokemonów) |
| 🔧 **Rozwój** | Kandydaci do ewolucji, power-up, oczyszczenia (purify shadow) i Elite TM |
| ⚙️ **Ustawienia** | Zmiana providera AI, klucze API, statystyki cache |

### Generator regex do transferu
Pasek opcji nad tabelą Pokemonów generuje zapytanie zgodne z wyszukiwarką Pokemon GO:
- separator `,` (OR w PoGO)
- opcjonalnie: `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary`, `&cp-XXX`
- automatyczne wykluczanie gatunków, które mają cennego osobnika w boxie

### AI cache
Odpowiedzi AI zapisywane w SQLite wg hasha IV/CP/shadow/shiny — ta sama kombinacja nie kosztuje drugiego tokenu.

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

---

## Stack

- **Backend** — Flask + SQLite (WAL mode)
- **Frontend** — Vanilla JS, bez frameworków
- **AI** — Google Gemini (domyślnie), OpenAI, Anthropic, Azure OpenAI
- **Dane eventów** — [ScrapedDuck](https://github.com/bigfoott/ScrapedDuck)
- **Tier lista** — pokebase.app scraper + wbudowany snapshot

---

## Struktura plików

```
pogo-analyzer/
├── app.py              # cały backend Flask
├── templates/
│   └── index.html      # cały frontend (HTML + CSS + JS)
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
