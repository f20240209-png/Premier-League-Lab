"""Bounded, non-destructive API-Football imports. Run outside web workers."""
from datetime import datetime, timezone
from sqlalchemy import select

from check_api_football import APIError, LEAGUE_ID
from .storage import Season, Team, Match, SyncRun, PlayerSeason, utcnow

FINISHED = {"FT", "AET", "PEN"}
SCHEDULED = {"NS", "TBD"}


def safe_logo(value):
    return value if isinstance(value, str) and value.startswith("https://") else None


def positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("Provider returned an invalid identifier.")
    return value


def score(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
        raise ValueError("Provider returned an invalid score.")
    return value


def validate_fixtures(rows, year):
    if not isinstance(rows, list) or not rows:
        raise ValueError("No fixtures returned. Existing data was preserved.")
    seen = set()
    for row in rows:
        fixture, league, teams = row["fixture"], row["league"], row["teams"]
        mid = positive_id(fixture["id"])
        if mid in seen:
            raise ValueError("Duplicate fixture ID in response.")
        seen.add(mid)
        if league["id"] != LEAGUE_ID or league["season"] != year:
            raise ValueError("Fixture belongs to a different league or season.")
        if positive_id(teams["home"]["id"]) == positive_id(teams["away"]["id"]):
            raise ValueError("A team cannot play itself.")
        for side in ("home", "away"):
            if not isinstance(teams[side].get("name"), str) or not teams[side]["name"].strip():
                raise ValueError("Team name missing.")
            score(row["goals"][side])
        if fixture["status"]["short"] in FINISHED and None in (row["goals"]["home"], row["goals"]["away"]):
            raise ValueError("Finished fixture has no full score.")
        timestamp = datetime.fromisoformat(fixture["date"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("Fixture timestamp is missing timezone.")
    return rows


def upsert_fixtures(db, rows, year, provider="api-football"):
    validate_fixtures(rows, year)
    season = db.scalar(select(Season).where(Season.provider == provider, Season.year == year))
    if season is None:
        season = Season(provider=provider, year=year)
        db.add(season)
        db.flush()
    teams = {t.external_id: t for t in db.scalars(select(Team).where(Team.provider == provider))}
    existing = {m.external_id: m for m in db.scalars(select(Match).where(Match.provider == provider))}
    for row in rows:
        for side in ("home", "away"):
            t = row["teams"][side]
            if t["id"] not in teams:
                teams[t["id"]] = Team(provider=provider, external_id=t["id"], name=t["name"])
                db.add(teams[t["id"]])
                db.flush()
            teams[t["id"]].name = t["name"]
            teams[t["id"]].logo = safe_logo(t.get("logo"))
        f = row["fixture"]
        match = existing.get(f["id"])
        home, away = teams[row["teams"]["home"]["id"]], teams[row["teams"]["away"]["id"]]
        if match is None:
            match = Match(provider=provider, external_id=f["id"], season_id=season.id,
                          home_id=home.id, away_id=away.id)
            db.add(match)
        elif (match.season_id, match.home_id, match.away_id) != (season.id, home.id, away.id):
            raise ValueError("Existing provider fixture identity changed; import rolled back.")
        match.kickoff = datetime.fromisoformat(f["date"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        match.status = f["status"]["short"]
        match.home_score, match.away_score = row["goals"]["home"], row["goals"]["away"]
    season.synced_at = utcnow()
    return len(rows)


def import_season(factory, client, year):
    with factory.begin() as db:
        run = SyncRun(year=year, kind="fixtures", status="running")
        db.add(run)
        db.flush()
        rid = run.id
    try:
        # Network fetch and validation precede all football data mutations.
        rows = validate_fixtures(client.get("fixtures", league=LEAGUE_ID, season=year)["response"], year)
        with factory.begin() as db:
            count = upsert_fixtures(db, rows, year)
            run = db.get(SyncRun, rid)
            run.status, run.count, run.ended_at = "success", count, utcnow()
        return count
    except Exception as error:
        with factory.begin() as db:
            run = db.get(SyncRun, rid)
            run.status, run.ended_at = "failed", utcnow()
            # Never persist requests, keys, raw SQL or database credentials.
            run.detail = str(error)[:1000] if isinstance(error, (APIError, ValueError)) else "Import failed; previous data preserved."
        raise


def import_stats(factory, client, year, limit=10):
    if not 1 <= limit <= 40:
        raise ValueError("Statistics request limit must be 1-40.")
    with factory() as db:
        season = db.scalar(select(Season).where(Season.provider == "api-football", Season.year == year))
        if season is None:
            raise ValueError("Import season fixtures first.")
        matches = list(db.scalars(select(Match).where(Match.season_id == season.id,
                      Match.status.in_(FINISHED), Match.stats_checked_at.is_(None)).order_by(Match.kickoff).limit(limit)))
        teams = {t.id: t.external_id for t in db.scalars(select(Team))}
    count = 0
    for match in matches:
        rows = client.get("fixtures/statistics", fixture=match.external_id)["response"]
        values = {r["team"]["id"]: {v["type"]: v["value"] for v in r.get("statistics", [])} for r in rows}
        if not {teams[match.home_id], teams[match.away_id]} <= values.keys():
            raise ValueError("Incomplete match statistics; this fixture remains pending.")
        def number(team_id, field):
            value = values[teams[team_id]].get(field)
            if value is None:
                return None
            value = float(str(value).rstrip("%"))
            if not 0 <= value <= (100 if field == "Ball Possession" else 200):
                raise ValueError("Invalid statistic.")
            return value
        with factory.begin() as db:
            target = db.get(Match, match.id)
            target.home_shots = number(match.home_id, "Total Shots")
            target.away_shots = number(match.away_id, "Total Shots")
            target.home_possession = number(match.home_id, "Ball Possession")
            target.away_possession = number(match.away_id, "Ball Possession")
            target.stats_checked_at = utcnow()
        count += 1
    return count


def import_players(factory, client, year, max_pages=5):
    """Atomic bounded snapshot; partial pages are explicitly marked incomplete."""
    if not 1 <= max_pages <= 40:
        raise ValueError("Player page limit must be 1-40.")
    with factory() as db:
        season = db.scalar(select(Season).where(Season.provider == "api-football", Season.year == year))
        if season is None:
            raise ValueError("Import fixtures first.")
        sid = season.id
    rows, complete = [], False
    for page in range(1, max_pages + 1):
        body = client.get("players", league=LEAGUE_ID, season=year, page=page)
        if not body["response"]:
            raise ValueError("Empty player page; previous player data preserved.")
        rows.extend(body["response"])
        total = int(body.get("paging", {}).get("total", 0))
        if total < page:
            raise ValueError("Invalid player pagination.")
        if page == total:
            complete = True
            break
    with factory.begin() as db:
        team_ids = {t.external_id: t.id for t in db.scalars(select(Team).where(Team.provider == "api-football"))}
        count = 0
        for row in rows:
            player = row["player"]
            positive_id(player["id"])
            for stats in row.get("statistics", []):
                if stats.get("league", {}).get("id") != LEAGUE_ID or stats["league"].get("season") != year:
                    continue
                tid = team_ids.get(stats["team"]["id"])
                if tid is None:
                    raise ValueError("Player team missing from fixture import.")
                record = db.scalar(select(PlayerSeason).where(PlayerSeason.season_id == sid,
                      PlayerSeason.external_id == player["id"], PlayerSeason.team_id == tid))
                if record is None:
                    record = PlayerSeason(season_id=sid, external_id=player["id"], team_id=tid)
                    db.add(record)
                record.name = player["name"]
                games, goals = stats.get("games") or {}, stats.get("goals") or {}
                record.position = games.get("position")
                record.minutes = score(games.get("minutes"))
                record.goals, record.assists = score(goals.get("total")), score(goals.get("assists"))
                count += 1
        if not count:
            raise ValueError("No matching player-season statistics; previous player data preserved.")
        db.get(Season, sid).players_complete = complete
    return count, complete
