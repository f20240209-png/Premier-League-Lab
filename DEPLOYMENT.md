# V9 deployment guide

Nothing has been published. The Render blueprint provisions PAID web,
PostgreSQL and Redis services. Review the quoted total before approving.
No cron jobs or paid AI calls are enabled.

## 1. Update locally

Stop Flask. Back up your `instance` folder outside the project. Copy these release
files into the existing project, keeping `.env`, `.venv` and `instance`. Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Keep local APP_ENV=development and COOKIE_SECURE=false. Check fixtures, squads
and model pages. If your local database is MySQL, stop before the migration:
the included migration tool supports SQLite sources only.

## 2. Push code to GitHub

Copy the updated files into your actual Git checkout; an extracted ZIP isn't a
Git repository. Review git status and commit only intended code changes. Never
push `.env`, `.venv`, `instance` or backups. Rotate previously committed secrets.
Push your chosen branch. Wait for the included GitHub Actions tests to pass,
including the disposable PostgreSQL migration test, before deployment.

## 3. Render setup

Connect the repository/branch with New > Blueprint, using render.yaml at its
root. The blueprint defines Singapore-region web, PostgreSQL 17 and Redis
services. Review costs before approval. Auto-deploy is off initially.
Generate an admin hash locally using `python manage.py hash-password`; provide
the hash (not your password) when Render prompts for ADMIN_PASSWORD_HASH.

The blueprint generates FLASK_SECRET_KEY and configures DATABASE_URL and
RATELIMIT_STORAGE_URI using private service URLs. It sets APP_ENV=production,
COOKIE_SECURE=true, installs requirements and initializes tables before starting
Gunicorn. Health checks use `/health`. Always use HTTPS in production.

API keys aren't needed to serve migrated data. Add API_FOOTBALL_KEY,
FOOTBALL_DATA_ORG_KEY and BBS_API_KEY privately in Render when enabling imports.
Leave GEMINI_API_KEY unset until you deliberately enable the analyst and review
its usage budget. Do not disable production safety settings to fix startup errors.

## 4. Migrate the existing SQLite database

Do not seed demo data or run cloud imports first: the target must be empty.
Put the cloud web service in maintenance mode and stop all imports. The
blueprint blocks external DB connections. Temporarily allow ONLY your current
public IP /32 in the database's networking settings.

Set MIGRATION_TARGET_URL in your LOCAL .env to Render's EXTERNAL PostgreSQL URL,
with `?sslmode=require` appended (or `&sslmode=require` if it has query parameters).
Do not change your local DATABASE_URL or paste credentials in chat. With local
Flask stopped and the instance folder backed up, run:

```powershell
.\.venv\Scripts\python.exe migrate_database.py --source .\instance\football.sqlite3
```

This dry run checks source schema and target emptiness and prints table counts.
It does not create tables or copy rows. Verify the counts before applying:

```powershell
.\.venv\Scripts\python.exe migrate_database.py --source .\instance\football.sqlite3 --apply
```

The source is opened read-only. All app tables are copied in foreign-key order,
row contents compared and PostgreSQL ID sequences reset. The copy is
transactional; populated targets are refused. IDs, model parameters and
forecast timestamps are preserved, including existing demo records. Legacy
non-fl_* tables aren't copied. This is a one-time migration, NOT a repeat sync.

After success remove MIGRATION_TARGET_URL, restore the DB external allowlist to
empty, restart the cloud service and disable maintenance mode. If migration
fails, keep your backup and check source, connectivity and target emptiness.
Never delete a populated target to force a retry.

## 5. Launch checks

- /health returns 200 with status ok.
- Real seasons, counts, model metrics and original forecast timestamps match local.
- Login and protected admin pages work over HTTPS.
- Squad photos/fallbacks, mobile layout and both model pages work.
- Redeploy once and confirm data persists.
- Configure DB backups and rehearse a restore into a separate database.
- Review image and football-data redistribution terms before public launch.

Redis shares rate limits across workers. Forwarded IP headers are not blindly
trusted; initially the hosting proxy may share one rate-limit bucket among
visitors. Verify Render's trusted proxy chain before enabling per-client
forwarded-IP handling. This conservative default can limit availability under
load but avoids spoofable limits. Do not blindly enable ProxyFix.

## 6. Refresh and rollback

Scheduling is deliberately deferred. After setting BBS_API_KEY, run these
manually in the Render shell, continuing only after each succeeds:

```sh
python manage.py import-season --provider bigballs --season 2026
python manage.py forecast --provider real
python manage.py sync-squads
```

Forecasting uses the existing trained model. Run compare-models explicitly when
choosing to retrain. Do not run sync-real daily: it reimports historical seasons.
Future cron jobs need quota checks, non-overlap protection and failure alerts.

Back up before schema changes. create_all adds missing tables but is NOT a
schema migration system. Roll back application code with a previous Render
deploy only if compatible with the database. Preserve new forecasts before
considering any database restore.

## Verification limits

The release includes local tests and a PostgreSQL integration test in GitHub
Actions. PostgreSQL installation was blocked in the local build runtime, so the
live integration test must pass in CI. Render/Redis connectivity and migration
of your actual database still require verification. No keys or database are
included in the ZIP.

Official references:
- https://render.com/docs/blueprint-spec
- https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg
