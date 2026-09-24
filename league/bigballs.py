"""Big Balls Data EPL fixtures: bounded fetch, validation, atomic upsert."""
from datetime import datetime, timezone
from uuid import UUID
import time

import requests
from sqlalchemy import select

from check_api_football import APIError, LEAGUE_ID
from .importer import score, upsert_fixtures
from .storage import ProviderIdentity, SyncRun, utcnow

PROVIDER = "bigballs"
BASE_URL = "https://api.bigballsdata.com/v1"
STATUS = {"scheduled": "NS", "live": "LIVE", "in_progress": "LIVE",
          "finished": "FT", "final": "FT", "cancelled": "CANC",
          "postponed": "PST", "suspended": "SUSP", "abandoned": "ABD"}


class BigBallsClient:
    def __init__(self, key, min_interval=0.7):
        if not key or not key.strip():
            raise APIError("Set BBS_API_KEY in the project's .env file.")
        self.key = key.strip()
        self.min_interval = max(0, min_interval)
        self.last_request = None

    def get(self, endpoint="stored/matches", **params):
        if endpoint not in {"stored/matches", "leagues/epl/top-scorers"}:
            raise ValueError("Unsupported Big Balls Data endpoint.")
        if self.last_request is not None:
            delay = self.min_interval - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
        self.last_request = time.monotonic()
        try:
            response = requests.get(
                f"{BASE_URL}/{endpoint}",
                headers={"Authorization": f"Bearer {self.key}"}, params=params,
                timeout=(5, 25), allow_redirects=False)
        except requests.RequestException:
            raise APIError("Big Balls Data network request failed; no matches changed.") from None
        try:
            body = response.json()
        except ValueError:
            raise APIError(f"Big Balls Data HTTP {response.status_code}: invalid JSON.") from None
        if not isinstance(body, dict):
            raise APIError("Big Balls Data returned an unexpected response.")
        if response.status_code != 200 or body.get("error"):
            error = body.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            # Fixed messages avoid printing/persisting secrets echoed by a server.
            if code == "history_not_included":
                raise APIError("Big Balls Data: this season is not included in your plan. "
                               "This account requires current-season access. Existing data preserved.")
            if response.status_code == 429:
                raise APIError("Big Balls Data request limit reached. Wait before retrying; no automatic retries.")
            raise APIError(f"Big Balls Data HTTP {response.status_code}: request rejected. Check key, plan and parameters.")
        return body


def uuid_text(value):
    if not isinstance(value, str):
        raise ValueError("Big Balls Data identifier must be a UUID string.")
    try:
        return str(UUID(value))
    except ValueError:
        raise ValueError("Big Balls Data returned an invalid UUID.") from None


def validate_rows(rows, year):
    if not isinstance(rows, list) or not rows:
        raise ValueError("No fixtures returned; existing data preserved.")
    seen = set()
    normalized = []
    try:
        for row in rows:
            mid = uuid_text(row["id"])
            if mid in seen:
                raise ValueError("Duplicate fixture UUID; pagination may have shifted. Retry later.")
            seen.add(mid)
            if row["sport"] != "football" or row["league"].lower() not in {"epl", "premier league", "english premier league"}:
                raise ValueError("Response contains another sport or league.")
            kickoff = datetime.fromisoformat(row["kickoff_utc"].replace("Z", "+00:00"))
            if kickoff.tzinfo is None:
                raise ValueError("Match timestamp has no timezone.")
            kickoff = kickoff.astimezone(timezone.utc)
            # Explicit season query selects the campaign; this catches an ignored
            # filter. It is not used to infer a season from an arbitrary match.
            if not datetime(year, 7, 1, tzinfo=timezone.utc) <= kickoff < datetime(year + 1, 7, 1, tzinfo=timezone.utc):
                raise ValueError("Match falls outside the requested EPL season; import refused.")
            status = row["status"]
            if status not in STATUS:
                raise ValueError("Unrecognized match status; update the importer before proceeding.")
            goals = row.get("score")
            if goals is not None and not isinstance(goals, dict):
                raise ValueError("Invalid score object.")
            goals = goals or {}
            hg, ag = score(goals.get("home")), score(goals.get("away"))
            if STATUS[status] == "FT" and (hg is None or ag is None or kickoff.replace(tzinfo=None) > utcnow()):
                raise ValueError("Finished match is missing scores or is dated in the future.")
            teams = {}
            for side in ("home", "away"):
                team = row[side]
                name = team["name"]
                if not isinstance(name, str) or not name.strip() or len(name) > 200:
                    raise ValueError("Missing or invalid club name.")
                logo = team.get("logo_url")
                if not isinstance(logo, str) or len(logo) > 500:
                    logo = None
                teams[side] = {"id": uuid_text(team["id"]), "name": name.strip(), "logo": logo}
            if teams["home"]["id"] == teams["away"]["id"]:
                raise ValueError("A club cannot play itself.")
            normalized.append({"fixture": {"id": mid, "date": kickoff.isoformat(), "status": {"short": STATUS[status]}},
                               "league": {"id": LEAGUE_ID, "season": year}, "teams": teams,
                               "goals": {"home": hg, "away": ag}})
    except (KeyError, TypeError, AttributeError):
        raise ValueError("Big Balls Data fixture is missing required fields; no matches changed.") from None
    return normalized


def fetch_season(client, year):
    if isinstance(year, bool) or not isinstance(year, int) or not 1992 <= year <= 2100:
        raise ValueError("Use an EPL season start year between 1992 and 2100.")
    rows, total = [], None
    # Maximum three requests, even if the server ignores pagination or lies.
    for _ in range(3):
        body = client.get(sport="football", league="epl", season=year,
                          sort="asc", limit=200, offset=len(rows))
        page, pagination = body.get("data"), body.get("pagination")
        if not isinstance(page, list) or not isinstance(pagination, dict):
            raise ValueError("Missing match data or pagination; no matches changed.")
        count = pagination.get("total")
        if type(count) is not int or not 1 <= count <= 462:
            raise ValueError("Empty or implausible EPL match count; existing data preserved.")
        if total is not None and count != total:
            raise ValueError("Match count changed while paging; retry later.")
        total = count
        if pagination.get("offset") != len(rows) or pagination.get("limit") != 200:
            raise ValueError("Unexpected pagination; no matches changed.")
        if len(page) != min(200, total - len(rows)):
            raise ValueError("Incomplete match page; no matches changed.")
        rows.extend(page)
        if len(rows) == total:
            return validate_rows(rows, year)
    raise ValueError("Pagination request limit reached; no matches changed.")


def import_bigballs_season(factory, client, year):
    with factory.begin() as db:
        run = SyncRun(year=year, kind="bigballs-fixtures", status="running")
        db.add(run)
        db.flush()
        rid = run.id
    try:
        rows = fetch_season(client, year)
        with factory.begin() as db:
            identities = {(i.kind, i.external_id): i.id for i in db.scalars(
                select(ProviderIdentity).where(ProviderIdentity.provider == PROVIDER))}

            def local_id(kind, external_id):
                key = (kind, external_id)
                if key not in identities:
                    identity = ProviderIdentity(provider=PROVIDER, kind=kind, external_id=external_id)
                    db.add(identity)
                    db.flush()
                    identities[key] = identity.id
                return identities[key]

            for row in rows:
                row["fixture"]["id"] = local_id("match", row["fixture"]["id"])
                for side in ("home", "away"):
                    team = row["teams"][side]
                    team["id"] = local_id("team", team["id"])
            count = upsert_fixtures(db, rows, year, provider=PROVIDER)
            run = db.get(SyncRun, rid)
            run.status, run.count, run.ended_at = "success", count, utcnow()
        return count
    except Exception:
        with factory.begin() as db:
            run = db.get(SyncRun, rid)
            run.status, run.ended_at = "failed", utcnow()
            run.detail = "Big Balls Data import failed; previous data preserved. See terminal for details."
        raise
