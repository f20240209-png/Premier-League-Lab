> **V7 visual update:** see [UPGRADE_V7.md](UPGRADE_V7.md) for the dark theme, football imagery and safe Windows update instructions. Keep your existing `.env`, `.venv` and `instance` folder. No reimport or retraining needed.

# Premier League Lab

**V9 deployment preparation:** follow [DEPLOYMENT.md](DEPLOYMENT.md). Includes
PostgreSQL support, shared production rate limiting, guarded database migration,
Render configuration and CI. Nothing is deployed automatically by this ZIP.

A Flask football analytics application with season-aware storage, API-Football
imports, team comparisons and an evaluated match-outcome model.

## V6: compare match prediction models

Stop Flask and back up your database. Copy the ZIP's project files into your
existing folder, keeping `.env`, `.venv` and `instance`. No new dependencies
or API keys are required beyond V5. Run:

```powershell
.\.venv\Scripts\python.exe manage.py compare-models
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/predictions. This command uses your already imported
real seasons and makes **no API calls**. It compares Logistic Regression with
a fixed Random Forest (150 trees, depth 5, minimum 12 samples per leaf).
Both use the existing six pre-match form features. Injuries, shots and
possession are not added because verified historical feature coverage is absent.

Selection uses the last quarter of earlier-season UTC dates as validation;
entire dates stay together. Lowest validation log loss wins (ties prefer
Logistic Regression). Both candidates then fit all earlier-season data and
score the same eligible 2025/26 matches. The comparison table displays accuracy
and log loss; the selected model's confusion matrix and calibration remain
visible. The previously viewed 2025/26 results are a historical benchmark,
not a new untouched test set. No accuracy improvement is guaranteed.

The selected algorithm refits all completed real matches for future forecasts.
Old models and forecasts remain; new forecasts are recorded only before kickoff.
Forest trees are stored as JSON, with no pickle loading. `sync-real` now also
runs this comparison after refreshing fixtures. `train --provider real
--test-season 2025` remains available for the legacy fixed logistic baseline.

Validation here used synthetic test fixtures; your database and API keys remain
on your computer. Run the command to see the actual comparison scores. Avoid
repeatedly choosing features or settings based on the already viewed benchmark.

## V5: player market-value predictor (real data included)

This release adds a working Linear Regression baseline, a real player comparison
page, a custom player-profile calculator and a matplotlib evaluation chart.
The target is **historical estimated market value in EUR**, not an actual
transfer fee. No new API key is needed: the small, prepared real dataset is
included in `data/player_values` with its source hashes and coverage report.

Stop Flask, back up your database, then copy the contents of the ZIP's
`football_league_upgrade` folder into your existing project folder. Keep your
`.env`, `.venv` and `instance` folder. From that folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py train-values
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/player-values or click **Player value** in the sidebar.
The new dependencies are pandas and matplotlib. Training uses the included
historical data without network access. It creates a separate `fl_value_models`
table and preserves match imports, leaderboard data and match predictions.
Re-training unchanged data reuses the existing model record.

The included run uses 2021/22–2024/25 for training (**1,595 examples**) and
2025/26 for testing (**399 examples**). Measured test MAE is **EUR 12,074,681**,
versus **EUR 17,059,649** for a training-median baseline; R² is **0.424**.
This is an educational baseline with substantial errors, especially for very
expensive players. It is not a live 2026/27 price feed. The page shows the
valuation date, model error, source limitations and eligible record counts.

Read `PLAYER_VALUE_MODEL.md` for selection rules, chronological evaluation,
source attribution and limitations. JSON reports and a PNG comparison plot
are also written to `instance/value-reports` after training.

Advanced: `python manage.py train-values --refresh` downloads the four public
source files (about 62 MB compressed in this release) and rebuilds the data.
The upstream dataset has paused updates; refreshing may return unchanged data.
Alternatively use `--source-dir PATH` for a folder containing `players.csv`,
`games.csv`, `appearances.csv` and `player_valuations.csv` (gzip also supported).
`--first-season` and `--test-season` use starting years; defaults are 2021 and
2025. At least two earlier training seasons and sufficient dated labels are
required. A failed import/training run preserves the last working value model.

To reproduce the bundled extract from the raw files:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_value_snapshot.py --source-dir instance/value-source
```

## V4: real player goals and assists

Your existing V3 real match imports and forecasts are retained. Stop Flask,
back up `instance/football.sqlite3`, then copy the contents of the ZIP's
`football_league_upgrade` folder into your existing project folder. Keep
`.env`, `.venv` and `instance`; they are deliberately excluded from this ZIP.
Do not run `demo` or delete your database. No new dependencies are required.

Run in PowerShell from your existing project folder:

```powershell
.\.venv\Scripts\python.exe manage.py sync-players
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/top-scorers and choose a real season. The Assists tab
uses the same season. `sync-players` makes at most five API requests:

| Season | Source | Coverage |
| --- | --- | --- |
| 2024/25 | API-Football | Separate top-20 goals and assists endpoints |
| 2025/26 | football-data.org | Up to 100 scorer-list players; assists only within that subset |
| 2026/27 | Big Balls Data | Separate goals and assists lists, up to 100 each |

The command needs the same three keys as V3. Provider access to player endpoints
is not established by fixture access. If an endpoint is denied or returns no
known values, the terminal reports the failure and retains any previous board.
Other boards continue; the command exits nonzero if any failed. Re-running
updates the same board rather than adding duplicates. Successful imports show
their timestamp and coverage on the page. API responses are cached in the local
database; browsing pages spends no API requests.

This completes the league leaderboard integration, not full squad datasets.
Missing values are never converted to zero. League aggregate stats are stored
separately from club spells, so transfers cannot duplicate totals across club
pages. Existing `import-players --season 2024 --limit 40` can import full
API-Football player pages if your account allows it; it consumes up to 40 calls
and reports whether pagination completed. Other seasons' full squads, detailed
match statistics and transfer fee training targets remain separate work.
The match prediction model continues using imported historical results; it does
not require player stats or retraining after this leaderboard update.

## V3: import the three verified real seasons

Update your existing folder with the contents of this ZIP's
`football_league_upgrade` folder after stopping Flask (Ctrl+C). Replace source
files, keeping `.env`, `.venv` and `instance`. None of those local files/folders
are included in this ZIP. Your existing database and settings remain in place.

Keep these **three separate keys** in `.env`:

```dotenv
API_FOOTBALL_KEY=your_api_football_key
FOOTBALL_DATA_ORG_KEY=your_football_data_org_key
BBS_API_KEY=your_bigballs_key
```

Then run from that project folder:

```powershell
.\.venv\Scripts\python.exe manage.py sync-real
.\.venv\Scripts\python.exe app.py
```

`sync-real` performs the following, stopping on failure:

1. Import 2024/25 from API-Football (one request).
2. Import 2025/26 completed results from football-data.org (one request).
3. Import available 2026/27 results and scheduled fixtures from Big Balls Data
   (200 matches/page, at most three requests).
4. Validate complete historical seasons: 380 unique home/away pairings, 20 clubs
   and 38 matches per club. Connect explicit club aliases across sources.
5. Evaluate a logistic-regression model on 2025/26 using earlier seasons only.
6. Fit a separate production model using all completed real matches and save
   eligible next-match forecasts before kickoff.

Each source import commits independently. If a later step fails, previous
successful source imports remain; no model is trained after an import failure.
You can retry the command without duplicating matches. All three keys are checked
for presence before any requests. No subscription upgrades or automatic retries.

Open http://127.0.0.1:5000/ (remove any old `?season=4`). The default is the newest
real season. Use the selector to view 2024/25 or 2025/26. Results, standings,
comparisons, club form and predictions now use imported real data. Predictions
show a clearly labelled **2025/26 historical evaluation**; future probabilities
are separate saved forecasts, not retrospective claims. The actual accuracy is
computed locally and is not guaranteed to beat the baseline.

Provider identities remain separate in storage. The modelling view selects
API-Football for years up to 2024, football-data.org for 2025, and Big Balls Data
for 2026 onward. This release's one-command flow imports only 2024–2026; later
seasons require explicit imports and verified access. Overlapping imports from
other sources are not counted twice. `league/real_data.py` contains the explicit
club aliases; an unknown or ambiguous club stops modelling rather than guessing.
Provider ownership per season is saved with each model for reproducibility.

### Refresh after new results

```powershell
.\.venv\Scripts\python.exe manage.py import-season --provider bigballs --season 2026
.\.venv\Scripts\python.exe manage.py train --provider real --test-season 2025
.\.venv\Scripts\python.exe manage.py forecast --provider real
```

Run each only after the preceding command succeeds. Forecasts are immutable per
model/match. Newly promoted clubs need at least three earlier imported matches;
we skip forecasts with insufficient history. If the API has no future fixtures,
zero new forecasts is a valid result.

### Scope of real data

These commands import **match results and fixtures**, not every endpoint offered
by the providers. Shots, possession, player leaders, injuries and transfer values
are not invented or copied from the synthetic demo. Player panels remain empty
until separately imported. The existing bounded API-Football player/stat imports
remain available for historical seasons, subject to your account's access.
Demo seasons are retained for development and remain explicitly labelled.

For a new installation without an existing virtual environment, first run
`python -m venv .venv` and `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
Create `.env` from `.env.example` **only if `.env` does not already exist**.
The offline demo quick start below is optional; it is not needed for real data.

## What changed

- New responsive dashboard, team profiles, comparisons, match centres and player leaders.
- Results and form calculated from the same fixture records.
- Non-destructive, transactional fixture imports with stable provider identifiers.
- Bounded statistics/player imports; missing values remain missing.
- Fixed logistic-regression baseline using earlier results, not same-match statistics.
- Chronological evaluation, baseline comparison, confusion matrix and calibration table.
- Separately recorded pre-kickoff forecasts, timestamps and model versions.
- What-if scores recalculate a temporary table without updating the database.
- Optional Gemini explanations grounded in selected-team statistics; no invented odds.
- Hashed admin password, CSRF protection, rate limits, safe chat rendering and no hardcoded keys.
- Offline synthetic demo, automated tests and a health endpoint.

## Optional offline demo — Windows / PowerShell

Python 3.11 or 3.12 recommended. Extract the upgrade into a **new folder** so your
original project and `.env` remain intact. Run these commands from the folder
containing `app.py` and `manage.py`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe manage.py demo
.\.venv\Scripts\python.exe manage.py train --provider demo
.\.venv\Scripts\python.exe manage.py forecast --provider demo
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000. The demo needs no keys or MySQL server. It creates
`instance/football.sqlite3`. All demo fixtures, player values and model scores are
**synthetic**, prominently labelled throughout. The 2025-labelled demo includes
relative dates around the day it was generated; it is not a real season calendar.
Running `demo` again refuses to overwrite the existing demo.

On macOS/Linux use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`.

## Big Balls Data importer details (introduced in V2)

The account was tested by the user on 22 September 2026: scheduled 2026 fixtures
were returned, and the completed 2026/27 query reported 50 matches. The same
account rejected 2025/26 with `history_not_included`. Actual account access takes
precedence over pricing-page descriptions. No paid subscription is needed to
import the verified current season.

To update V1, stop Flask with Ctrl+C, then copy the **contents** of the ZIP's
`football_league_upgrade` folder into your existing project folder, replacing
code files. The ZIP does not contain `.env`, `.venv` or `instance`, so those
remain in place. Do not delete your existing project folder. Back up your local
database before any software upgrade if it contains data you need to retain.

Your existing `.env` should include (keep your other variables):

```dotenv
BBS_API_KEY=your_full_saved_key
```

From the existing project folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py import-season --provider bigballs --season 2026
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:5000/ without an old `?season=4` query. The newest real season
is now the default. The selector and footer identify **2026/2027 · Big Balls Data**.
If you keep an old URL, explicitly choose that season and click View.

The import requests all available statuses, 200 matches per page, at most three
requests (normally two for a 380-match campaign). It verifies the reported total,
offsets, duplicate UUIDs, league, season window, scores and club identity before
committing any fixture updates. Empty, denied, malformed or incomplete responses
leave previous matches intact. Re-run the same command when you want to refresh
results; it updates stable records rather than duplicating them. Schedule totals
reflect the provider's available rows, not a guarantee the full schedule is loaded.

UUID mappings are stored in the new `fl_provider_identities` table. Existing
integer IDs, API-Football imports, synthetic data and legacy tables are retained.
No existing columns need alteration. Providers remain separate; matching display
names are not silently treated as the same database identity.

This release enables current results, calculated standings, form, comparisons,
fixtures, club logos and what-if scenarios. Detailed player/shot/possession data
are not imported from Big Balls Data yet. Logos remain external URLs and depend
on the provider's asset availability. V3 connects these fixtures to the combined real-data model described above.
Historical API-Football training also remains available separately.

The importer uses the documented REST endpoint `/v1/stored/matches`, Bearer auth,
season start years, and limit/offset pagination. No Node SDK is needed.
Reference: https://bigballsdata.com/openapi.json

## Import real API-Football results

Add your existing key locally to `.env`:

```dotenv
API_FOOTBALL_KEY=your_key_here
```

The user's account was verified externally to allow seasons starting 2022–2024.
The user's 2024 call returned 380 finished fixtures. Access to 2022/2023 and
match/player statistics must still be verified using that account. Permissions
may change; access-denied responses are reported without clearing existing data.

```powershell
.\.venv\Scripts\python.exe manage.py import-season --season 2022
.\.venv\Scripts\python.exe manage.py import-season --season 2023
.\.venv\Scripts\python.exe manage.py import-season --season 2024
.\.venv\Scripts\python.exe manage.py train
```

Each fixture import uses **one API request**. Successful repeated imports update
matching records without duplicating or renumbering them. All payloads are fetched
and validated before a transaction updates any football data. Failures are logged
in `fl_sync_runs`. A crashed process can leave a run labelled `running`; it does
not make a completed import successful. Run only one importer per database at a time.

Real API seasons and synthetic seasons remain separate. Select the desired season
at the top of the app. A trained real-data model never consumes synthetic data.

### Optional detailed statistics

The first model uses goals and recent form, so **you do not need to spend hundreds
of requests collecting shots and possession to train it**.

```powershell
.\.venv\Scripts\python.exe manage.py import-stats --season 2024 --limit 5
.\.venv\Scripts\python.exe manage.py import-players --season 2024 --limit 5
```

`--limit` caps requests at 1–40. Statistics imports save each completed fixture and
resume with unchecked fixtures on the next run. An incomplete/failed fixture
remains pending and stops the run; earlier successfully imported statistics remain.
Player imports start at page 1 and commit the fetched batch together. If the limit
stops before the final page, the UI explicitly labels the player rankings partial.
Increase the limit within your available quota to fetch a complete player snapshot;
the command does not bypass subscription restrictions. It does not assume that
missing assists are zero. Player club spells are aggregated for leaderboards.
API calls within one client are spaced at least 6.1 seconds apart. No automatic
retries, endless loops, live polling or web-request imports occur.

For connection diagnostics, `check_api_football.py` and the compatibility filename
`check_api_football_v2.py` remain available. See `API_FOOTBALL_SETUP.md`.

## Database compatibility and migration

The default local database is SQLite. To use MySQL, set `DATABASE_URL` to a
SQLAlchemy `mysql+pymysql://...` URL (URL-encode special password characters), or
retain the original `DB_HOST`, `DB_USER`/`DB_USERNAME`, `DB_PASSWORD`,
`DB_NAME`/`DB_DATABASE`, and optional `DB_PORT` variables.

`DATABASE_URL` takes precedence over those legacy variables. Use a separate test
database first. The upgrade creates only **`fl_*` tables** and never drops or
truncates your existing `teams`, `matches`, `players` or other legacy tables.
However, the new app **does not automatically migrate/display old-schema records**:
import the desired API seasons into the new tables. MySQL runtime verification is
pending; automated tests ran against SQLite.

`init_db.py` and `reset_db.py` now only create missing tables. Destructive legacy
helpers are retired. The old SQL dump is historical reference, not the new setup
path. Manual match/goal routes return 410 for admins; provider data is updated by
imports to prevent contradictions between manually entered results and API data.

## Model method and honest evaluation

- Six features: each club's points, goals scored and goals conceded per game over
  its previous five imported matches (minimum three).
- Historical features use **earlier UTC dates only**, so overlapping games on the
  same day cannot leak their final scores into predictions.
- Club history carries across seasons; newly promoted clubs need imported history.
- Training uses seasons before the final imported season. The final imported
  season is held out. Earlier held-out results may update form for later test
  fixtures, but are never used to fit the evaluation model.
- A fixed `StandardScaler` + `LogisticRegression(C=1)` is fitted on training data.
  All three outcomes, at least 50 training samples and 30 held-out samples are required.
- The comparison baseline always predicts training-set outcome frequencies.
  Metrics include accuracy, multiclass log loss, confusion matrix and home-win
  calibration. Small calibration buckets are not strong evidence of calibration.
- A separate production fit uses all completed data after evaluation. Parameters
  are stored as JSON coefficients, not executable pickle files.
- Model improvements/tuning need a separate earlier validation period; do not
  repeatedly tune against the displayed holdout and call it an untouched test.
- Future fixtures must occur after the model's training cutoff and forecast time.
  Run `python manage.py forecast` to record immutable probabilities. Only each
  club's next eligible fixture is considered, so later games are not presented as
  if intervening form were known.
- Forecast performance is calculated only after imported final results arrive.
  If multiple model versions predicted a match, the tracker uses the latest valid
  pre-kickoff forecast. Historical holdout predictions are labelled retrospective.
- Full score data, injuries, lineups, shots, possession and betting odds are **not**
  model inputs in this release. There is no transfer-valuation model without a
  separately verified target dataset. No claim of profitable betting is made.

## Admin and optional AI

Generate a persistent session secret locally:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe manage.py hash-password
```

Put the secret in `FLASK_SECRET_KEY` and the generated password hash in
`ADMIN_PASSWORD_HASH`. The password command uses a hidden prompt. Admin login is
disabled until a hash is set. Development otherwise uses an ephemeral session
secret, so restarting signs users out.

For the optional analyst, set `GEMINI_API_KEY` and an available `GEMINI_MODEL` in
`.env`. No Gemini calls are needed for comparisons, training or predictions. The
assistant is bounded to the selected team/season context, has a timeout and a
five-request/minute limit. User and model text render as plain text, not HTML.
Live Gemini compatibility has not been verified with your account.

## Deployment and recurring imports

The Procfile now uses `gunicorn 'app:create_app()'`. Configure a persistent database,
strong `FLASK_SECRET_KEY`, `APP_ENV=production`, and `COOKIE_SECURE=true` behind HTTPS.
Configure shared limiter storage (e.g. Redis, with the appropriate `limits` extra
installed) for multiple workers; the default memory limiter is per process and
not a durable production quota. Proxy IP forwarding must only be trusted when
configured for your actual trusted proxy. The app does not blindly trust headers.

Schedule `python manage.py import-season --season YEAR` with your host scheduler
or Windows Task Scheduler once access and quota have been confirmed. Schedule
`forecast` separately after imports. No external scheduler or deployment has been
created by this upgrade, and no automatic account charges have been authorized.
Current-season data requires an account/source that permits that season.

The standings are **calculated from results**; point deductions, qualification rules
and final official tiebreak decisions are not modelled. The UI states this rather
than misrepresenting the table as an official ranking.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q tests
```

See `VALIDATION.md` for what was run, evidence and remaining limitations.
Never commit `.env`, keys or database files. Credentials previously committed to
the original repo should be rotated: removing them from these files does not
remove them from Git history.

## V8: club squads and portraits

The 2026/27 club pages include a bundled snapshot of 667 FPL-listed players across
20 clubs, fetched on 24 September 2026 from the official Fantasy Premier League
bootstrap feed: https://fantasy.premierleague.com/api/bootstrap-static/ .
Search names or filter by position. Available portraits use the Premier League
CDN, with bundled portraits reused by photo identifier and initials on failure.
FPL lists can include unavailable or recently transferred players; they are not
verified official registration lists. Positions and snapshot minutes/goals follow
FPL. The current snapshot is never substituted for an older season's squad and
does not change model training data.

Refresh without another API key:

```powershell
.\.venv\Scripts\python.exe manage.py sync-squads
```

On update, stop Flask, copy the release files into the existing project, keeping
your `.env`, `.venv`, and `instance` folder. Restart `app.py`, select 2026/2027,
and open a club's **View squad** link. No fixture reimport or retraining is needed.
This release also explicitly reads the portrait JSON as UTF-8 on Windows.
