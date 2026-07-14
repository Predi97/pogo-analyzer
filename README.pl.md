# ⚡ PokéGO Analyzer

<p align="center">
  <img src="https://img.shields.io/badge/python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Support" />
  <img src="https://img.shields.io/badge/framework-Flask-lightgrey.svg?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/database-SQLite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/AI-Gemini%20%7C%20OpenAI%20%7C%20Anthropic-orange.svg?style=for-the-badge&logo=google-gemini&logoColor=white" alt="AI Support" />
  <img src="https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge" alt="License" />
</p>

> 🇬🇧 **[English version (Wersja angielska)](README.md)**

Profesjonalna, lokalna aplikacja webowa do analizy Twojego konta Pokémon GO, zarządzania kandydatami do PvP/Raidów oraz planowania taktyki wydarzeń z personalizowanym trenerem AI. Zasilana eksportem pliku `PGSStats.json` z **PGSharp**.

---

## 🌟 Główne Funkcje

| Zakładka | Opis Funkcji |
| :--- | :--- |
| 🧑‍💼 **Profil Trenera** | Estetyczna karta profilowa w pasku bocznym wyświetlająca Twoją nazwę użytkownika, poziom trenera, przynależność do drużyny (Mystic ❄️, Valor 🔥, Instinct ⚡), PokéCoins oraz posiadany Stardust. |
| 🎮 **Box Pokémonów** | Tabela całego boxa z zaawansowanym wyszukiwaniem, filtrowaniem, sortowaniem oraz **Generatorem Regex do Transferu** do masowego zarządzania zasobami. |
| ⚔️ **Raid Attackery** | Ranking najlepszych attackerów PVE oparty na kalkulacji DPS×TDO proxy powiązanej z mnożnikami aktualnej tier listy. |
| 🏆 **Analiza PvP** | Ocena kandydatów do Great, Ultra i Master League z wyliczonym **IV Rankiem** (stat-product, zgodny z metodologią PvPoke) i kolorowymi wskaźnikami jakości. |
| 🤖 **Kreator Zespołów PvP** | Oparty na AI system budowania 3-osobowych składów PvP (Lead, Safe Switch, Closer) z Twojego plecaka, z analizą synergii typów i kontr na obecną metę. |
| 📅 **Kalendarz Wydarzeń** | Liczniki czasu na żywo dla aktywnych i nadchodzących eventów, spisy spawnów, bossów rajdowych oraz wskaźniki tierów Pokémonów zintegrowane bezpośrednio z wydarzeniami. |
| 🎒 **Ekwipunek** | Pełna lista przedmiotów z ilościami oraz inteligentna analiza AI doradzająca, które przedmioty (np. TM, Stardust, Rare Candy) i na które Pokémony warto zużyć. |
| 🔧 **Planer Rozwoju** | Panel ułatwiający podejmowanie decyzji o ewolucjach, power-upach, oczyszczaniu Pokémonów Shadow oraz użyciu Elite TM. |
| ⚙️ **Ustawienia** | Wybór dostawcy AI, wprowadzanie kluczy API oraz monitorowanie statystyk trafień w pamięć podręczną SQLite. |

---

## 🛡️ Metodologia PvP IV Rank

Każdy Pokémon w zakładce PvP wyświetla swój **rank stat-product** (rank 1 = najlepsza kombinacja IV pod dany limit CP ligi):
- **Wzór:** $\text{Stat Product} = \text{Effective Atk} \times \text{Effective Def} \times \lfloor\text{Effective HP}\rfloor$ na najwyższym możliwym poziomie pod limitem CP.
- **Optymalizacja defensywna:** Niższy Atak IV jest zazwyczaj preferowany, ponieważ pozwala osiągnąć wyższy poziom Pokémona w danym limicie ligowym, dając większą wytrzymałość (bulk).
- **Kolory odznak:**
  - 🥇 **Złota odznaka** — Rank 1 (Idealne IV pod PvP)
  - 🟢 **Zielona odznaka** — Top 1% (Świetna przeżywalność)
  - 🟡 **Żółta odznaka** — Top 5% (Bardzo dobra)
  - 🔵 **Niebieska odznaka** — Top 10% (Dobra)

---

## 📂 Generator zapytań do masowego transferu

Pasek filtrów nad tabelą Pokémonów generuje zapytania w pełni zgodne z wyszukiwarką w grze Pokémon GO:
- Rozdziela frazy znakiem `,` (logiczne LUB w grze).
- Opcjonalne filtry, takie jak `&!shiny&!shadow&!lucky&!favorite`, `&!3*&!4*`, `&!legendary` oraz `&cp-XXX`.
- **Inteligentna ochrona:** Automatycznie pomija gatunki, u których posiadasz wartościowego osobnika (np. Shiny, Shadow, Lucky, Hundo lub PvP Rank 1).

---

## 💾 Pamięć Podręczna SQLite i Lokalny Stan

- **Pełna Prywatność:** Wszystkie operacje odbywają się lokalnie. Twoje klucze API i pliki importu są zapisywane w bezpiecznej lokalnej bazie SQLite (`baza_pogo.db`).
- **Cache Odpowiedzi AI:** Analizy są buforowane na podstawie kryptograficznego hasha (kombinacji IV, CP, poziomu i statusu). Powtórne zapytanie o tego samego Pokémona pobierane jest natychmiast z bazy, oszczędzając tokeny API.
- **Odtwarzanie Sesji:** Po odświeżeniu strony serwer odczytuje ostatnio wgrany surowy JSON z bazy danych i automatycznie odtwarza Twój pulpit gracza.

---

## 📱 Źródło Danych — PGSharp

Aplikacja jest zaprojektowana do pracy wyłącznie z plikiem eksportu **`PGSStats.json`** generowanym przez aplikację [**PGSharp**](https://www.pgsharp.com/) — zmodyfikowanego klienta Pokémon GO.

### Jak uzyskać plik `PGSStats.json`?

1. Otwórz **PGSharp** na swoim urządzeniu.
2. Przejdź do **Menu → PGSStats** (lub ikony eksportu / udostępniania).
3. Kliknij **Eksportuj** i prześlij plik `PGSStats.json` na swój komputer (np. przez Google Drive, Discorda lub kabel USB).
4. Wgraj plik w dashboardzie **PokéGO Analyzer**, aby odblokować wszystkie funkcje.

> [!NOTE]
> `PGSStats.json` zawiera pełny box Pokémonów, ekwipunek przedmiotów, profil trenera i statystyki walk — wszystko w jednym pliku. Analizator przetwarza dane w całości **lokalnie** — żadne dane nie są wysyłane na zewnętrzny serwer.

---

## 🛠️ Szybki Start

### Wymagania
- Python 3.9+
- Klucz API Google Gemini (darmowy klucz pobierzesz na [Google AI Studio](https://aistudio.google.com/apikey)) lub klucz do OpenAI, Anthropic lub Azure OpenAI.

### Instalacja

1. **Sklonuj Repozytorium:**
   ```bash
   git clone https://github.com/Predi97/pogo-analyzer.git
   cd pogo-analyzer
   ```

2. **Utwórz Środowisko Wirtualne:**
   ```bash
   python -m venv venv
   source venv/bin/activate        # System Windows: venv\Scripts\activate
   ```

3. **Zainstaluj Zależności:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Skonfiguruj Środowisko:**
   ```bash
   cp .env.example .env
   # Otwórz plik .env i dodaj swój GEMINI_API_KEY
   ```

### Uruchomienie

```bash
python app.py
```
Otwórz adres **[http://127.0.0.1:5000](http://127.0.0.1:5000)** w przeglądarce i prześlij plik `PGSStats.json`, aby zainicjować pulpit analizy.

---

## 🗄️ Struktura Projektu

```
pogo-analyzer/
├── app.py                  # Główny punkt startowy aplikacji Flask
├── config.py               # Zmienne konfiguracyjne i adresy URL scraperów
├── utils.py                # Pomocnicze funkcje dat i formatowania
├── database.py             # Połączenie SQLite (tryb WAL) oraz obsługa cache i stanu
├── state.py                # Globalny stan sesji w pamięci RAM
├── parser.py               # Parser pliku PGSStats.json
├── scoring.py              # Obliczenia raidowe i stat-product PvP
├── data/
│   ├── pokedex.py          # Kompletny Pokédex (1000+ wpisów) i baza przedmiotów
│   ├── base_stats.py       # Statystyki bazowe, oceny meta i łańcuchy ewolucji
│   └── cpm.py              # Pełna tabela CPM (poziomy od 1 do 50, z połówkami)
├── services/
│   ├── ai.py               # Konfiguracja klientów AI i szablony promptów
│   ├── events.py           # Pobieranie i parsowanie eventów z ScrapedDuck
│   └── tiers.py            # Pobieranie tier listy meta z pokebase.app
├── routes/
│   ├── pokemon.py          # Endpointy wgrywania, eksportu CSV i statusu
│   ├── analysis.py         # Endpointy rankingowe dla PvP i Raidów
│   ├── ai_routes.py        # Obsługa zapytań AI oraz API kreatora zespołów PvP
│   └── misc.py             # Zarządzanie eventami, konfiguracją i statystykami cache
├── templates/
│   └── index.html          # Pulpit frontendowy (HTML + CSS + JS)
├── requirements.txt        # Zależności bibliotek Pythona
└── .env.example            # Szablon pliku konfiguracyjnego .env
```

---

## 📄 Licencja

Projekt dystrybuowany na licencji MIT. Zobacz plik `LICENSE` po więcej informacji.
