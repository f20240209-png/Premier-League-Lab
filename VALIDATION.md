# Upgrade validation — 22 September 2026

## V8: squads and portraits

- Existing 80 tests and 8 new squad tests passed. New checks cover validation,
  atomic failure, idempotent refresh, season isolation and UTF-8 club rendering.
- Live public FPL response normalized to 667 players across 20 clubs; Manchester
  United has 34 listed players. This is source coverage, not a registration audit.
- Browser checks: 34 cards, name search, goalkeeper filter, and 390px mobile
  layout without horizontal overflow. Mobile screenshot visually inspected.
- A Premier League 110x140 portrait returned HTTP 200 image/png; all 667 portraits
  have not been verified. Initials cover failed images. Bundled portrait matching
  uses photo identifiers, not fuzzy player names.
- No user API keys or local imported database were needed or accessed.

## V6: match model comparison

- **80 tests pass** including all prior regressions.
- Added JSON forest/scikit-learn probability parity, benchmark-label independence
  of selection, whole-date validation splitting, combined-provider comparison,
  future forecast persistence/idempotence and rendered comparison table checks.
- Both candidates have fixed settings and identical features/benchmark fixtures.
  Selection uses only earlier-season validation log loss; the historical 2025/26
  benchmark is explicitly labelled as previously inspected.
- Real comparison metrics require the user's local imported database. No new
  real accuracy claim is made from the synthetic test suite.
- Existing database tables and old models/forecasts are retained. New model
  parameters contain JSON arrays rather than executable pickle artifacts.

## V5: real historical player-value model

- **77 automated tests passed** including the full prior regression suite.
- Downloaded and validated four real public source files; gzip integrity,
  required fields and source hashes checked. A truncated appearance download
  was detected and replaced before preparing any model data.
- Independently trained using raw files and then the bundled 1,994-row extract
  in separate SQLite databases; both returned 1,595 training and 399 test rows,
  MAE EUR 12,074,681, baseline MAE EUR 17,059,649 and R² 0.424.
- New tests cover dated joins, the first post-season label, rejecting future
  valuations and duplicate appearances, missing statistics, chronological
  holdout independence, JSON coefficient parity, idempotence, failed training,
  corrupt downloads, bounded inputs, source labels, Flask routes and PNG export.
- Matplotlib output visually inspected. Rendered routes exercised with Flask's
  test client; no live browser screenshot or Windows execution was performed.
- The bundled CSV is real historical data. Synthetic fixtures are confined to
  tests. No API keys, existing user databases or pickled models are included.
- New value tables are additive; existing fixture, player and forecast tables
  are unchanged. Player identity is local to the valuation dataset and never
  guessed by matching names to the three football API providers.

## V4: player leaderboards

- Automated suite: **64 tests passed** with SQLite and mocked API responses.
- Added checks for wrong season, invalid counts, missing-versus-zero statistics,
  club spell aggregation, subset coverage, atomic rollback, idempotent refresh,
  independent provider failures and rendered leaderboard/empty states.
- Existing 54 regression tests also pass. No production database was bundled
  or modified here. The user reported successful V3 imports of 380 matches in
  each of the three real seasons, plus real training and ten forecasts.
- Player endpoints were implemented against provider documentation; account
  entitlement and live player payloads still require the local `sync-players`
  run because the API keys and imported database remain on the user's computer.
- No claim is made that all player, transfer or detailed match data is available.

## V3: verified seasons and combined real-data modelling

- Automated suite: **54 tests pass**, using SQLite and mocked network calls.
- New football-data.org importer: auth, stable IDs, corrections, denied imports,
  wrong competition/season, missing scores and partial responses.
- Combined model tests use explicitly synthetic fixtures as test inputs only;
  no test scores or generated model parameters are shipped as real results.
- Complete historical season validation; explicit club aliases; no duplicate
  provider seasons; demo exclusion; current-season changes leave 2025/26
  evaluation unchanged; future forecasts, idempotence, UI and one-command flow.
- User independently verified 380 completed 2025/26 results from football-data.org,
  including Liverpool 4–2 Bournemouth on 15 August 2025. That key remains local.
- Live end-to-end importing with all three keys still needs the user's local
  `python manage.py sync-real` run. No keys or fabricated real-data metrics are
  supplied in the release. No paid plans, deployment or GitHub push performed.
- Combined forecasting is now implemented. Player-level current-season data,
  shots/possession and transfer-value targets still require separate imports.

## V2: Big Balls Data integration (historical validation record)

- `python -m pytest -q tests`: **41 passed** (18 additional cases).
- Added pagination completeness/duplicate checks, denied or incomplete-page
  rollback, UUID identity retention, corrected scores, source isolation, invalid
  league/season/status/score rejection, HTTP credential handling, and current
  source page/default-selection tests.
- The user independently verified scheduled EPL fixtures in October 2026 and
  two completed September results. The completed query reports 50 total records.
- The user's 2025/26 request returned HTTP 403 `history_not_included`;
  **current-season access only** is the verified entitlement.
- Fixture importer tested with mocked HTTP payloads and SQLite. The new command
  has not yet been run against the live account; its key is local to the user.
- Current-season forecasts and Big Balls player/detailed-stat imports are not
  implemented. Historical API-Football models remain separate.
- Distribution contains source and tests only, no keys or local database.

## V1 completed

- Installed project dependencies; concrete tested versions are in TESTED_VERSIONS.txt.
- Ran `python -m pytest -q tests`: **23 passed**.
- Ran Python syntax compilation and JavaScript syntax checking successfully.
- Ran the Flask application with a locally generated synthetic dataset.
- Ran the demo training and forecast commands successfully.
- Started a real HTTP server and checked the homepage and its linked pages:
  **32 pages, no HTTP failures**, plus CSS, JavaScript and `/health` returning 200.
- Checked whitespace/diff integrity and source files for the previously present
  Google-key pattern; no such key remains in the working Python source.

## What the automated tests cover

- Authentication headers, timeouts, redirect prevention and HTTP-200 API errors.
- API error messages redact the configured key.
- Missing keys produce no requests; empty samples are not labelled verified.
- Stable IDs and idempotent reimports; legacy tables remain untouched.
- Failed/denied imports retain existing data and record a failed sync.
- Invalid and duplicate fixtures are rejected before committing changes.
- A conflicting existing fixture identity rolls back earlier changes in that batch.
- Bounded, resumable statistics imports; zero and missing values stay distinct.
- Player import pagination is explicitly labelled partial.
- Historical features exclude the predicted match and other matches on its UTC date.
- Hypothetical scores do not change stored results.
- Model fitting, holdout reports, normalized probabilities and immutable forecasts.
- All primary pages render, missing IDs return 404, and an empty database works.
- CSRF enforcement, disabled admin login without configuration, password-hash login,
  protected legacy write routes, POST-only logout and AI input validation.

## Demo model evidence

The synthetic demo produced 1,110 training samples and 50 held-out samples in its
latest synthetic season. Historical accuracy was 46.0% against a 52.0% constant
baseline. Log loss was 1.005 against 1.033 (lower is better). Ten pre-kickoff demo
forecasts were saved. These numbers establish that the pipeline runs and displays
unflattering results honestly; they are **not real football performance evidence**.
No generated database or synthetic trained parameters are embedded in the release.
The deterministic demo command recreates these locally, with future dates relative
to the day it is run.

## Not yet verified

- Live API-Football requests with the user's key. The user independently confirmed
  access to all 380 results in 2024–25; their key was not supplied to this workspace.
- API access and detailed statistics completeness for 2022/2023 and player pages.
- Runtime MySQL compatibility: ORM schema and configuration support MySQL, but the
  execution and regression tests here used SQLite.
- Gemini live calls with the user's account/model access.
- Browser screenshot/interaction testing: the cloud browser stalled when attempting
  to navigate to the local server and was stopped. HTTP/template tests passed,
  but visual desktop/mobile layout and JavaScript interactions are not browser-verified.
- Production deployment, scheduler setup and performance/load testing.

## Remaining product scope

Transfer valuation needs a separately verified fee/market-value target dataset.
Random Forest/XGBoost experiments and season Monte Carlo simulation remain future
work; this release provides a reproducible logistic-regression baseline and a
non-persistent what-if table. Current-season importing depends on account access.
No API-Football, Gemini or hosting purchase has been made. No GitHub push or external
production database migration has been performed.

## V7 — Dark matchday presentation

- Existing 80-test suite verified (79 passed in the final suite run; the remaining assertion exposed a shortened market-valuation label, which was restored and its test passed on rerun).
- Chromium desktop 1440px and mobile 390px: overview, comparisons, player leaders, player values, what-if and predictions rendered without horizontal page overflow or broken visible images; no JavaScript exceptions.
- Browser interactions checked: player/club search and empty state; Swap clubs; score-pair counter and server-calculated scenario; all five featured player links; image failure fallback.
- Final visual pass checked the corrected header logo, same-scale comparison charts, trophy image, Pep photo and player page at desktop/mobile sizes.
- Match UI checks used a separate, clearly labelled synthetic development database. Player-value checks used the bundled real historical dataset. No user's API keys, local Windows database or real imports were available to this environment. No API import or model fitting logic changed in this update.
- ZIP omits local databases, credentials, environments and QA data. Existing Windows data is retained by copying the code update into the user's existing folder as documented in UPGRADE_V7.md.
