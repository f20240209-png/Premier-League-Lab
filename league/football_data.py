"""Import completed EPL results from football-data.org, using its own IDs."""
from datetime import datetime, timezone
import requests

from check_api_football import APIError, LEAGUE_ID
from .importer import positive_id, upsert_fixtures, validate_fixtures
from .storage import SyncRun, utcnow

PROVIDER = "football-data"


class FootballDataClient:
    def __init__(self, key):
        if not key or not key.strip():
            raise APIError("Set FOOTBALL_DATA_ORG_KEY in .env.")
        self.key = key.strip()

    def results(self, year):
        return self._get("matches", season=year, status="FINISHED")

    def scorers(self, year):
        return self._get("scorers", season=year, limit=100)

    def _get(self, endpoint, **params):
        if endpoint not in {"matches", "scorers"}:
            raise ValueError("Unsupported football-data.org endpoint.")
        try:
            response = requests.get(
                f"https://api.football-data.org/v4/competitions/PL/{endpoint}",
                headers={"X-Auth-Token": self.key},
                params=params,
                timeout=(5, 30), allow_redirects=False)
        except requests.RequestException:
            raise APIError("football-data.org network request failed.") from None
        if response.status_code != 200:
            raise APIError(f"football-data.org HTTP {response.status_code}: check your key, season access or quota.")
        try:
            body = response.json()
        except ValueError:
            raise APIError("football-data.org returned invalid JSON.") from None
        if not isinstance(body, dict) or body.get("errorCode") or body.get("error"):
            raise APIError("football-data.org rejected the request or returned an unexpected body.")
        return body


def normalize_results(body, year):
    if type(year) is not int or not 1995 <= year <= 2100:
        raise ValueError("Use an EPL season start year from 1995 onward.")
    try:
        if body["competition"]["id"] != 2021 or body["competition"]["code"] != "PL":
            raise ValueError("Unexpected competition in football-data.org response.")
        if str(body["filters"]["season"]) != str(year):
            raise ValueError("football-data.org returned a different season.")
        matches = body["matches"]
        if not isinstance(matches, list) or not matches or len(matches) > 380:
            raise ValueError("Empty or invalid EPL results list.")
        if body["resultSet"]["count"] != len(matches):
            raise ValueError("Incomplete results response; existing data preserved.")
        normalized = []
        pairings = set()
        for match in matches:
            if match["competition"]["id"] != 2021 or match["status"] != "FINISHED":
                raise ValueError("Unexpected competition or non-final match in results.")
            if datetime.fromisoformat(match["season"]["startDate"]).year != year:
                raise ValueError("Match belongs to another season.")
            when = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
            if when.tzinfo is None or when.astimezone(timezone.utc).replace(tzinfo=None) > utcnow():
                raise ValueError("Invalid completed-match timestamp.")
            season_start = datetime.fromisoformat(match["season"]["startDate"]).date()
            season_end = datetime.fromisoformat(match["season"]["endDate"]).date()
            if not season_start <= when.astimezone(timezone.utc).date() <= season_end:
                raise ValueError("Match date is outside its reported season.")
            teams = {}
            for side in ("home", "away"):
                team = match[side + "Team"]
                teams[side] = {"id": positive_id(team["id"]), "name": team["name"], "logo": team.get("crest")}
            pair = (teams["home"]["id"], teams["away"]["id"])
            if pair in pairings:
                raise ValueError("Duplicate home/away pairing in the EPL season.")
            pairings.add(pair)
            normalized.append({"fixture": {"id": positive_id(match["id"]), "date": match["utcDate"],
                                            "status": {"short": "FT"}},
                               "league": {"id": LEAGUE_ID, "season": year}, "teams": teams,
                               "goals": match["score"]["fullTime"]})
        return validate_fixtures(normalized, year)
    except (KeyError, TypeError, AttributeError):
        raise ValueError("football-data.org response is missing required result fields.") from None


def import_football_data(factory, client, year):
    with factory.begin() as db:
        run = SyncRun(year=year, kind="football-data-results", status="running")
        db.add(run)
        db.flush()
        rid = run.id
    try:
        rows = normalize_results(client.results(year), year)
        with factory.begin() as db:
            count = upsert_fixtures(db, rows, year, provider=PROVIDER)
            run = db.get(SyncRun, rid)
            run.status, run.count, run.ended_at = "success", count, utcnow()
        return count
    except Exception:
        with factory.begin() as db:
            run = db.get(SyncRun, rid)
            run.status, run.ended_at = "failed", utcnow()
            run.detail = "football-data.org import failed; existing results preserved."
        raise
