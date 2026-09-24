from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy import select, func

from check_api_football import APIError
from league.bigballs import BigBallsClient, fetch_season, import_bigballs_season
from league.storage import open_database, Match, Team, Season, SyncRun, ProviderIdentity


def fixture(number=1, status="finished"):
    return {"id": str(UUID(int=number)), "sport": "football", "league": "EPL",
            "home": {"id": str(UUID(int=10001)), "name": "Fulham", "logo_url": "https://example.com/f.png"},
            "away": {"id": str(UUID(int=10002)), "name": "Manchester United"},
            "kickoff_utc": "2026-09-20T15:30:00.000Z", "status": status,
            "score": {"home": 1, "away": 1} if status == "finished" else None}


def page(rows, total=None, offset=0):
    return {"data": rows, "pagination": {"total": len(rows) if total is None else total,
                                         "limit": 200, "offset": offset}}


def client(rows):
    api = Mock()
    api.get.return_value = page(rows)
    return api


@pytest.fixture
def database(tmp_path):
    engine, factory = open_database(f"sqlite:///{tmp_path / 'bbs.sqlite3'}")
    yield factory
    engine.dispose()


def test_all_pages_fetched_with_explicit_season():
    api = Mock()
    api.get.side_effect = [page([fixture(i) for i in range(1, 201)], 201),
                           page([fixture(201)], 201, 200)]
    assert len(fetch_season(api, 2026)) == 201
    assert api.get.call_count == 2
    assert api.get.call_args.kwargs == dict(sport="football", league="epl", season=2026,
                                          sort="asc", limit=200, offset=200)


@pytest.mark.parametrize("failure", ["denied", "duplicate", "changed-total", "short-page"])
def test_failed_second_page_preserves_database(database, failure):
    import_bigballs_season(database, client([fixture()]), 2026)
    first = [fixture(i) for i in range(1, 201)]
    first[0]["score"]["home"] = 9
    second = {"denied": APIError("history_not_included"),
              "duplicate": page([fixture()], 201, 200),
              "changed-total": page([fixture(201)], 202, 200),
              "short-page": page([], 201, 200)}[failure]
    api = Mock()
    api.get.side_effect = [page(first, 201), second]
    with pytest.raises((APIError, ValueError)):
        import_bigballs_season(database, api, 2026)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Match)) == 1
        assert db.scalar(select(Match.home_score)) == 1
        assert db.scalar(select(func.count()).select_from(ProviderIdentity)) == 3
        assert list(db.scalars(select(SyncRun.status).order_by(SyncRun.id))) == ["success", "failed"]


def test_uuid_identity_reimport_scores_and_isolation(database):
    with database.begin() as db:
        db.add(Season(provider="api-football", year=2024))
        db.add(Team(provider="api-football", external_id=1, name="Fulham"))
    row = fixture(status="scheduled")
    import_bigballs_season(database, client([row]), 2026)
    with database() as db:
        original = db.scalar(select(Match))
        identity = (original.id, original.external_id, original.home_id, original.away_id)
        assert original.status == "NS" and original.home_score is None
    import_bigballs_season(database, client([fixture()]), 2026)
    with database() as db:
        updated = db.scalar(select(Match))
        assert (updated.id, updated.external_id, updated.home_id, updated.away_id) == identity
        assert updated.status == "FT" and updated.home_score == 1
        assert db.scalar(select(func.count()).select_from(Team)) == 3
        assert db.scalar(select(Team.name).where(Team.provider == "api-football")) == "Fulham"


def test_changed_identity_rolls_back_uuid_mappings(database):
    import_bigballs_season(database, client([fixture(), fixture(2)]), 2026)
    changed = fixture(2)
    changed["away"]["id"] = str(UUID(int=10003))
    earlier = fixture()
    earlier["score"]["home"] = 9
    with pytest.raises(ValueError, match="identity changed"):
        import_bigballs_season(database, client([earlier, changed]), 2026)
    with database() as db:
        assert list(db.scalars(select(Match.home_score))) == [1, 1]
        assert db.scalar(select(func.count()).select_from(ProviderIdentity)) == 4


@pytest.mark.parametrize("field,value", [
    ("id", "invalid"), ("sport", "basketball"), ("league", "La Liga"),
    ("kickoff_utc", "2025-09-20T15:30:00Z"), ("kickoff_utc", "2026-09-20T15:30:00"),
    ("status", "unknown"), ("score", None), ("score", {"home": True, "away": 1}),
    ("home", None),
])
def test_bad_rows_refused(database, field, value):
    row = fixture()
    row[field] = value
    with pytest.raises(ValueError):
        import_bigballs_season(database, client([row]), 2026)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Match)) == 0
        assert db.scalar(select(func.count()).select_from(ProviderIdentity)) == 0


def test_client_headers_denial_redaction_and_no_retries(monkeypatch):
    response = Mock(status_code=403)
    response.json.return_value = {"error": {"code": "history_not_included", "message": "secret-key"}}
    request = Mock(return_value=response)
    monkeypatch.setattr("league.bigballs.requests.get", request)
    with pytest.raises(APIError, match="not included") as caught:
        BigBallsClient("secret-key", min_interval=0).get(season=2025)
    assert "secret-key" not in str(caught.value)
    assert request.call_count == 1
    assert request.call_args.kwargs["headers"] == {"Authorization": "Bearer secret-key"}
    assert request.call_args.kwargs["allow_redirects"] is False
    assert request.call_args.kwargs["timeout"] == (5, 25)
    with pytest.raises(APIError):
        BigBallsClient("")
    assert request.call_count == 1


def test_real_season_default_and_pages(database):
    import_bigballs_season(database, client([fixture()]), 2026)
    with database.begin() as db:
        db.add_all([Season(provider="demo", year=2027), Season(provider="api-football", year=2024)])
    from app import create_app
    app = create_app({"TESTING": True, "DATABASE_URL": str(database.kw["bind"].url),
                      "RATELIMIT_ENABLED": False, "GEMINI_API_KEY": ""})
    browser = app.test_client()
    for path in ["/", "/teams", "/results", "/fixtures", "/compare", "/predictions", "/what-if", "/top-scorers"]:
        response = browser.get(path)
        assert response.status_code == 200, path
        text = response.get_data(as_text=True)
        assert "Source: Big Balls Data" in text
        assert "<strong>Synthetic demo</strong>" not in text
    assert "not connected yet" in browser.get("/predictions").get_data(as_text=True)
    assert "Fulham" in browser.get("/results").get_data(as_text=True)
    app.extensions["league_engine"].dispose()
