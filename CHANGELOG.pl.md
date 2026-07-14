# Rejestr Zmian (Changelog)

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

Format opiera się na [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
a projekt stosuje się do [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-07-14

### Dodano
- **Kalendarz Wydarzeń**: Zintegrowano kalendarz aktywnych, nadchodzących i zakończonych wydarzeń pobierany na żywo z API ScrapedDuck. Zawiera odliczanie czasu i filtry meta Pokémonów.
- **Kreator Zespołów PvP AI**: Dodano analizę AI dla zespołów PvP (Great, Ultra i Master League), która analizuje 25 najlepszych kandydatów gracza, przypisuje role (Lead, Safe Switch, Closer), ocenia synergie i wskazuje brakujące meta-kontry (z cache w bazie SQLite).
- **Lokalne Sugestie Zespołów PvP**: Dodano działający w 100% offline rule-based kreator składów, który dobiera role i unika nakładania się słabości typów (nie wymaga klucza API).
- **Panel Profilu Gracza**: Wyciągnięto podstawowe parametry profilu (nazwa, poziom, monety, stardust, dystans) oraz statystyki walk PvP per liga z importowanych plików PGSharp.
- **Przełącznik Językowy (Language Switcher)**: Wdrożono dynamiczny dwuflagowy selektor językowy (`🇺🇸` / `🇵🇱`) obsługujący całą stronę (zakładki, tabele, opisy, alerty i opisy składów).

### Zmieniono
- **Układ Sugestii PvP**: Przeniesiono kartę sugerowanych zespołów na samą górę zakładki PvP (nad tabelę kandydatów) w celu lepszej czytelności.

### Naprawiono
- **Filtrowanie Master League**: Naprawiono błąd pustej listy Master League wywołany niepoprawnym progiem odcięcia 20 000 CP. Ustawiono minimalny próg na 1500 CP dla lig bez limitów.

## [1.0.0] - 2026-07-13

### Dodano
- Główna aplikacja PokéGO Analyzer.
- Wczytywanie plików PGSStats.json i lokalny parser.
- Matematyka obliczeń rankingu PvP IV (wzór Stat Product).
- Ocena atakujących PvE w raidach (estymacja DPS×TDO).
- Baza SQLite do zapisywania stanu sesji.
- Ciemny interfejs dashboardu.
