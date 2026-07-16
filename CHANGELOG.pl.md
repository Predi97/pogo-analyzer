# Rejestr Zmian (Changelog)

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

Format opiera się na [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
a projekt stosuje się do [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-07-15

### Dodano
- **Weryfikator Ataków PvP & Raid (Moveset Optimizer)**: Analizuje szybkie i ładowane ataki Pokémonów z tieru S/A w odniesieniu do mety PvPoke oraz wyliczonego współczynnika PvE Cycle DPS, oznaczając potrzebę użycia Elite TM oraz zablokowane ruchy (Frustration/Return).
- **Interaktywny Kalkulator Kosztów Power-up**: Zintegrowano listy wyboru poziomu docelowego, wyliczające w czasie rzeczywistym zapotrzebowanie na Stardust, Candy i XL Candy oraz prognozujące CP po ulepszeniu na podstawie wartości CPM.
- **Prognoza CP po Ewolucji**: Oblicza CP dla kolejnych stadiów ewolucyjnych i weryfikuje zgodność z limitami Great League (1500 CP) i Ultra League (2500 CP).
- **Wykresy i Statystyki Boxa (Dashboard Box Analytics)**: Wdrożono zwijany panel wykresów (rozkład IV oraz typów) za pomocą biblioteki Chart.js, a także licznik i listę unikalnych okazów "Nando" (0% IV).
- **Import plików CSV z PokéGenie**: Dodano obsługę importu plików `.csv` wyeksportowanych z aplikacji PokéGenie, parsując zeskanowane gatunki, CP, poziomy, IV, płeć, statusy lucky/shadow/purified oraz zestawy ataków, w pełni integrując je ze wszystkimi widokami i analizami.
- **Rozszerzony Generator Regex**: Dodano przełączniki ochrony specyficznych statusów (Hundo, Nando, Shiny, Shadow, Lucky, Ulubione, Meta S/A, 3★+, PvP, Poziom >= 35) oraz przełączniki wykluczania grup (mityczne, UB, kostiumy, oczyszczone, pomocnicy/buddy, obrońcy gymów, mega) automatycznie dostosowywane do języka gry.
- **Zwijane Sekcje Panelu Rozwój**: Zastąpiono wysokie tabele w zakładce Rozwój zwijanymi szufladami, aby zoptymalizować widoczność i wysokość strony.
- **Udoskonalone Sugestie Składów PvP**: Przebudowano algorytm doboru ról na podstawie dynamicznego rozkładu współczynnika wytrzymałości, gwarantując generowanie składów w każdej lidze (w tym Master League) i dodano podsumowanie najlepszych Pokémonów dla każdej roli w plecaku.
- **Podgląd Zwiniętych Sekcji Rozwoju**: Dodano dynamiczne plakietki podglądu z nazwą i CP top 3 kandydatów, wyświetlane bezpośrednio pod zarysem zwiniętej karty w sekcji Rozwój.
- **Porównanie Idealnego IV w PvP**: Wprowadzono dynamiczne wyliczanie optymalnej kombinacji IV (Rank 1, np. `0/15/15` dla Umbreona w Great League), wyświetlanej bezpośrednio pod plakietką rangi w tabeli kandydatów PvP.
- **Aktualizacja Oficjalnych Statystyk Bazowych**: Zaktualizowano szacowane/przedpremierowe statystyki bazowe dla gatunków z Gen 8, Gen 9 i Hisui (Rillaboom, Cinderace, Inteleon, Greedent, Dubwool, Meltan, Coalossal, Flapple, Toxtricity, Cursola, Zacian, Zamazenta, Sneasler, Overqwil, Ursaluna, Pawmot, Revavroom) zgodnie z oficjalnym Game Masterem Pokémon GO, eliminując rozbieżności w kalkulacji CP.
- **Rozstrzyganie Remisów Iloczynu Statystyk (Tie-Breaker)**: Wdrożono algorytm rozstrzygania remisów identycznego stat productu na korzyść kombinacji z wyższym CP, a następnie wyższym IV obrony i zdrowia, uzyskując 100% zgodności z rankingami PvPoke.
- **Wyświetlanie Ataków w Raidach**: Wdrożono wyświetlanie posiadanych szybkich i ładowanych ataków w postaci kolorowych plakietek pod nazwą każdego Pokémona w tabeli kandydatów na rajdy. Dodano kolumnę „Najlepszy zestaw (PvE)” z optymalnymi ruchami oraz graficznym oznaczeniem statusu (✔️/⚠️) informującym, czy zestaw jest idealny czy wymaga zmiany za pomocą TM.
- **Prezentacja Top 3 Zestawów Ataków PvE**: Zastąpiono pojedynczą rekomendację ataku w tabeli Rajdów przejrzystym zestawieniem Top 3 najlepszych unikalnych zestawów ruchów dla każdego Pokémona. Każda pozycja wyświetla ataki szybkie/ładowane, typy oraz zielony znacznik (`✔️`), jeśli Pokémon aktualnie posiada te ruchy, ułatwiając ocenę przydatności (np. dla Rhyperiora z atakami ziemnymi vs kamiennymi).
- **Wyszukiwanie i Statystyki Form Specjalnych**: Skorygowano kolejność wyszukiwania ruchów, dając pierwszeństwo dokładnym nazwom form alternatywnych (np. `Zacian (Crowned Sword)`), a dopiero w razie ich braku nazwom bazowym. Uzupełniono bazę `POKEMON_DB` o oficjalne statystyki oraz zestawy ruchów dla alternatywnych form Zaciana, Zamazenty, Dialgi, Palkii i Giratiny (uwzględniając ich unikalne ataki, takie jak Behemoth Blade, Behemoth Bash, Roar of Time i Spacial Rend).
- **Interaktywne Sortowanie Kolumn**: Dodano uniwersalny skrypt sortowania tabel po stronie klienta (dla zakładek Pokemony, Raidy, PvP), pozwalający na kliknięcie nagłówków kolumn i sortowanie rosnąco/malejąco według nazwy, CP, poziomu, procentu IV oraz sumy statystyk IV.
- **Dynamiczne Parsowanie Form Pokémonów**: Usprawniono mechanizm parsowania gatunków, aby automatycznie rozpoznawał i poprawnie formatował złożone formy (np. `Zacian (Crowned Sword)`, `Giratina (Origin)`, `Landorus (Therian)`) z zapisu CamelCase.
- **Uporządkowanie Listy Wydarzeń**: Wdrożono domyślne sortowanie wydarzeń (najpierw aktywne kończące się najszybciej, następnie nadchodzące zaczynające się najwcześniej, na końcu zakończone). Naprawiono błąd językowy, przez który nadchodzące wydarzenia bez dokładnej liczby dni wyświetlały się jako `Za undefinedd`.
- **Dynamiczny Regex i Filtrowanie Transferu**: Zastąpiono statyczny filtr kandydatów do transferu w pełni dynamicznym silnikiem powiązanym z ustawieniami panelu „Regex PoGO”. Dodano stale aktualizowane pole tekstowe z wygenerowaną komendą regex, uproszczono nagłówek sekcji ochrony oraz wprowadzono czerwony przycisk `🗑️ Filtruj listę`, który automatycznie przełącza widok na zakładkę Pokémonów i filtruje ją, pokazując dokładnie te okazy, które zostaną zaznaczone do transferu.



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
