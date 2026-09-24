# API-Football connection diagnostics

The upgraded app uses API-Football through the non-destructive importer described
in README.md. These standalone checks are optional diagnostics and never write to
MySQL or SQLite.

Add `API_FOOTBALL_KEY=your_key` to the `.env` beside the script, then run:

```powershell
python check_api_football.py
python check_api_football.py --season 2024
python check_api_football.py --season 2024 --sample-fixture 1208021
```

- No arguments: at most two requests, for status and league metadata.
- `--season`: at most three requests, including season fixtures.
- `--sample-fixture`: two requests only, for fixture statistics and one player page.
  Use a returned fixture ID from the specified season. Up to three players are shown.
- Calls within one client are spaced by at least 6.1 seconds, with no retries.
- Both `check_api_football.py` and `check_api_football_v2.py` support these arguments.
- Provider-listed seasons and coverage flags do not prove account access or data
  completeness. HTTP 200 responses with API errors are failures.
- Missing values remain `null`; transfer-value coverage is not assumed.

The user independently verified 380 completed fixtures for 2024–25. Their free
account denied 2025–26 and suggested start years 2022–2024. No live key was supplied
to this workspace, so account-specific checks here remain pending.

Official reference: https://www.api-football.com/documentation-v3
