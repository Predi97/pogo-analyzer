# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2026-07-16

### Refactored
- **Modularized Frontend Templates**: Refactored the massive 153 KB `index.html` file into lightweight, decoupled partial components (sidebar, regex bar, tabs) under `templates/partials/` and externalized all styling to `static/css/app.css` and application script logic to `static/js/app.js`. This aligns the frontend architecture with Flask/Jinja2 template inheritance best practices and enables browser caching of assets.

### Added
- **Automated JSON Post / Sync API**: Enhanced the `/api/upload` endpoint to support direct HTTP POST requests with a raw JSON payload (representing `pgsstats.json` contents). Added an expandable instructions block (`<details>`) to the upload zone with native localizations and copy-pasteable curl command references, allowing users to easily automate account data synchronization via shell scripts or webhooks.

### Fixed
- **Sub-tier Badge Styling and Filters**: Fixed sub-tier badges (e.g. S+, A+, B+) failing to render background styling by extracting the base tier level character for CSS class bindings. Corrected meta filter matches so that sub-tier rankings are properly protected and selectable in S/A filters.
- **Silph Road Style POGO Search String Generator**: Replaced the long list of explicit Pokedex IDs to transfer with standard, short search strings natively supported by Pokémon GO (e.g. starting with `0*,1*,2*` or `0*,1*,2*,3*` and appending native exclusions like `!shiny&!shadow&!lucky`). It only appends Pokedex ID exclusions (`!<pid>`) for species with protected specimens that are not covered by status filters, keeping the string extremely short and copy-pasteable in one go.

## [1.2.0] - 2026-07-15

### Added
- **PvP & Raid Moveset Optimizer**: Analyzes quick and cinematic attacks of S/A tier Pokémon against optimal setups from PvPoke and computed PvE Cycle DPS, highlighting Elite TM requirements and event-locked moves (Frustration/Return).
- **Interactive Power-up Cost Calculator**: Integrated dropdowns on candidate panels to dynamically compute precise Stardust, Candy, and XL Candy upgrades, along with target CP predictions using CPM values.
- **Evolution CP Predictor**: Analyzes evolution stages and predicts post-evolution CP while validating compatibility with Great League (1500 CP) and Ultra League (2500 CP) limits.
- **Dashboard Box Analytics**: Added collapsible visual charts (IV distribution and type distribution) built with Chart.js, alongside a Nando (0% IV) tracker displaying rare specimens.
- **PokéGenie CSV Import Support**: Enabled importing `.csv` export files from the PokéGenie app, parsing scanned species, CP, levels, gender, lucky/shadow/purified statuses, and movesets, integrating fully with all dashboard features.
- **Advanced Transfer Regex Generator**: Expanded options to protect specific statuses (Hundos, Nandos, Shiny, Shadow, Lucky, Favorites, Meta, 3*+, PvP GL, Level >= 35) and added exclusion keywords (Mythical, UB, Costume, Purified, Buddy, Defender, Mega) dynamically localized in Polish and English.
- **Collapsible Develop Panels**: Replaced full-height tables in the Develop panel with toggleable card drawers to optimize page layout.
- **Robust PvP Team Suggestions**: Restructured local team algorithms using dynamic stat-ratio sorting to consistently calculate optimal lead, safe switch, and closer combinations for all leagues (including Master League), rendering role summaries in the PvP panel.
- **Develop Tab Previews**: Added collapsed previews displaying the top 3 candidate Pokémon name and CP for each category in the Develop panel, improving visibility at a glance.
- **Ideal PvP IV Comparison**: Integrated Rank 1 ideal PvP IV combinations (e.g., `0/15/15` for Great League Umbreon) dynamically calculated and displayed underneath the candidate's Rank badge in the PvP candidates table.
- **Official Base Stats Update**: Updated estimated/pre-release base stats for Gen 8, Gen 9, and Hisuian species (Rillaboom, Cinderace, Inteleon, Greedent, Dubwool, Meltan, Coalossal, Flapple, Toxtricity, Cursola, Zacian, Zamazenta, Sneasler, Overqwil, Ursaluna, Pawmot, Revavroom) to match official Pokémon GO game master data, eliminating CP calculation discrepancies.
- **PvP Stat Product Tie-Breaker**: Added a tie-breaker algorithm that resolves exact stat product match ties by choosing combinations with higher CP, then higher stamina and defense IVs, ensuring 100% parity with PvPoke's Rank 1 listings.
- **Raid Moveset Optimizer display**: Rendered active quick and cinematic moves tags underneath Pokémon names in the Raids table. Added a 'Najlepszy zestaw (PvE)' column showing the optimal PvE moveset, using a visual status icon (✔️/⚠️) to indicate if the current moveset is optimal or needs TM modification.
- **Top 3 Movesets Dashboard**: Replaced the single moveset indicator in the Raids table with a multi-row view listing the Top 3 distinct movesets for each Pokémon. Each entry displays its fast/charged move names, type combination, and an active green checkmark (`✔️`) if the user's Pokémon has that moveset, allowing trainers to easily evaluate dual-type utility (e.g. Rock vs Ground Rhyperior).
- **Fuzzy Species Lookup & Form Statistics**: Corrected moveset lookup priority so that exact alternate form entries (e.g., `Zacian (Crowned Sword)`) are evaluated before falling back to base entries. Populated `POKEMON_DB` with official stats and move pools for alternate forms of Zacian, Zamazenta, Dialga, Palkia, and Giratina (including their signature moves like Behemoth Blade, Behemoth Bash, Roar of Time, and Spacial Rend).
- **Interactive Column Sorting**: Implemented a generic client-side table sorting script for the Pokemony, Raidy, and PvP tables, allowing users to click table headers to sort rows ascending/descending by name, CP, level, IV percentage, and stats.
- **Dynamic Pokémon Form Parsing**: Rewrote the parser's species naming module to dynamically detect and format all Pokémon forms (e.g., `Zacian (Crowned Sword)`, `Giratina (Origin)`, `Landorus (Therian)`) by handling CamelCase names and stripping redundant prefixes.
- **Improved Events Dashboard**: Restructured the events card sorting to default-display active events first (ordered by ending soonest), followed by upcoming events (ordered by starting soonest), and ended events last. Fixed a localization bug where upcoming events without a day count showed as `Za undefinedd`.
- **Dynamic Regex & Transfer Filtering**: Replaced the static transfer candidate rules with a fully dynamic filtering engine synced with the "Regex PoGO" control bar. Added a readonly text input showing the current regex query in real-time, shortened the "Protect" section title, and added a red `🗑️ Filtruj listę` button that instantly switches to the Pokémon tab and shows exactly the list of candidate species slated for transfer.



## [1.1.0] - 2026-07-14

### Added
- **Live Event Calendar**: Integrated active, upcoming, and ended events calendar sourced from ScrapedDuck API. Includes dynamic countdown timers and meta Pokémon filters.
- **AI PvP Team Builder**: Added AI-powered analysis for PvP teams (Great, Ultra, and Master League) analyzing the user's top 25 candidate Pokémon, identifying roles (Lead, Safe Switch, Closer), synergies, and missing counters (with SQLite database caching).
- **Local PvP Team Suggestions**: Added fully offline rule-based 3-Pokémon team builder that assigns roles and avoids type overlap (no AI API keys required).
- **Player Profiles Dashboard**: Extracted player information (Username, level, PokéCoins, Stardust, distance walked) and PvP league battle stats/win rates from PGSharp account file uploads.
- **Language Switcher**: Implemented dual-flag dynamic translation switcher (`🇺🇸` / `🇵🇱`) for sidebars, tabs, tables, tooltips, and suggestions.

### Changed
- **Suggested PvP Teams layout**: Moved the suggested teams card to the top of the PvP tab (above the candidates list) for better visibility.

### Fixed
- **Master League Candidates Limit**: Fixed a bug where Master League candidates list returned empty due to an incorrect 20k CP minimum threshold filtering. Updated threshold to 1500 CP for unlimited leagues.

## [1.0.0] - 2026-07-13

### Added
- Core PokéGO Analyzer application.
- PGSStats.json file uploads and local parser.
- PvP IV Rank calculations (Stat Product formula).
- Raids PvE attackers scoring (DPS×TDO estimation).
- SQLite storage database for session state recovery.
- Beautiful dark-themed dashboard.
