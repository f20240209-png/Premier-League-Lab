from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select, func

from check_api_football import APIError
from league.storage import open_database, Season, Team, Match, ModelRun, Forecast
from league.football_data import FootballDataClient, import_football_data
from league.real_data import ALIASES, canonical_club, real_matches
from league.prediction import train, record_forecasts, tracker


@pytest.fixture
def database(tmp_path):
    engine, factory = open_database(f'sqlite:///{tmp_path / "real.sqlite3"}')
    yield factory
    engine.dispose()


def payload():
    return {'competition': {'id': 2021, 'code': 'PL'}, 'filters': {'season': 2025},
            'resultSet': {'count': 1}, 'matches': [{
                'id': 537785, 'competition': {'id': 2021}, 'season': {'startDate': '2025-08-15', 'endDate': '2026-05-24'},
                'status': 'FINISHED', 'utcDate': '2025-08-15T19:00:00Z',
                'homeTeam': {'id': 64, 'name': 'Liverpool FC'},
                'awayTeam': {'id': 1044, 'name': 'AFC Bournemouth'},
                'score': {'fullTime': {'home': 4, 'away': 2}}}]}


def test_fd_import_idempotent_and_failed_update_preserved(database):
    api = Mock()
    api.results.return_value = payload()
    assert import_football_data(database, api, 2025) == 1
    assert import_football_data(database, api, 2025) == 1
    with database() as db:
        original = db.scalar(select(Match)).id
        assert db.scalar(select(func.count()).select_from(Match)) == 1
    changed = payload()
    changed['matches'][0]['score']['fullTime']['home'] = 3
    api.results.return_value = changed
    import_football_data(database, api, 2025)
    api.results.side_effect = APIError('denied')
    with pytest.raises(APIError):
        import_football_data(database, api, 2025)
    with database() as db:
        assert db.get(Match, original).home_score == 3


@pytest.mark.parametrize('issue', ['season', 'competition', 'count', 'missing_score', 'duplicate', 'club_identity'])
def test_fd_invalid_responses_rollback(database, issue):
    api = Mock()
    api.results.return_value = payload()
    import_football_data(database, api, 2025)
    body = payload()
    if issue == 'season': body['filters']['season'] = 2024
    if issue == 'competition': body['matches'][0]['competition']['id'] = 2002
    if issue == 'count': body['resultSet']['count'] = 380
    if issue == 'missing_score': body['matches'][0]['score']['fullTime']['home'] = None
    if issue == 'duplicate':
        body['matches'].append(deepcopy(body['matches'][0]))
        body['resultSet']['count'] = 2
    if issue == 'club_identity': body['matches'][0]['homeTeam']['id'] = 99
    api.results.return_value = body
    with pytest.raises(ValueError): import_football_data(database, api, 2025)
    with database() as db:
        assert db.scalar(select(Match.home_score)) == 4
        assert db.scalar(select(func.count()).select_from(Team)) == 2


def test_fd_auth_and_errors(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = payload()
    request = Mock(return_value=response)
    monkeypatch.setattr('league.football_data.requests.get', request)
    assert FootballDataClient('secret').results(2025)['resultSet']['count'] == 1
    assert request.call_args.kwargs['headers'] == {'X-Auth-Token': 'secret'}
    assert request.call_args.kwargs['params'] == {'season': 2025, 'status': 'FINISHED'}
    assert request.call_args.kwargs['allow_redirects'] is False
    response.status_code = 403
    with pytest.raises(APIError): FootballDataClient('secret').results(2025)
    with pytest.raises(APIError): FootballDataClient('')
    assert request.call_count == 2


def seed_combined(factory):
    names = list(ALIASES.values())[:20]
    with factory.begin() as db:
        for year, provider in [(2024, 'api-football'), (2025, 'football-data'), (2026, 'bigballs')]:
            season = Season(provider=provider, year=year)
            db.add(season); db.flush()
            clubs = []
            for i, aliases in enumerate(names):
                club = Team(provider=provider, external_id=i+1, name=aliases[-1] if year == 2025 else aliases[0])
                db.add(club); db.flush(); clubs.append(club.id)
            # A circle schedule ensures every club plays once per round.
            order = list(range(20)); rounds = []
            for _ in range(19):
                rounds.append([(order[i], order[-i-1]) for i in range(10)])
                order = [order[0], order[-1], *order[1:-1]]
            pairs = [p for rnd in rounds for p in rnd] + [(a,h) for rnd in rounds for h,a in rnd]
            for i, (h, a) in enumerate(pairs):
                if year == 2026 and i >= 60: break
                future = year == 2026 and i >= 50
                kickoff = datetime(year, 8, 1, 15) + timedelta(days=(i//10)*7)
                if future: kickoff = datetime(2026, 10, 10, 15)
                hg, ag = [(2,0), (1,1), (0,2)][i%3]
                db.add(Match(provider=provider, external_id=i+1, season_id=season.id,
                    home_id=clubs[h], away_id=clubs[a], kickoff=kickoff,
                    status='NS' if future else 'FT', home_score=None if future else hg,
                    away_score=None if future else ag))
        # Neither demo nor an overlapping provider's season can enter real data.
        for provider in ('demo', 'football-data'):
            s = Season(provider=provider, year=2024 if provider == 'football-data' else 2027)
            db.add(s)


def test_real_mapping_sources_and_unknown_clubs(database):
    seed_combined(database)
    assert canonical_club('AFC Bournemouth') == canonical_club('Bournemouth')
    assert canonical_club('Manchester United FC') != canonical_club('Manchester City')
    with pytest.raises(ValueError, match='Unmapped club'): canonical_club('United')
    with database() as db:
        matches, years, sources = real_matches(db)
        assert sources == {'2024': 'api-football', '2025': 'football-data', '2026': 'bigballs'}
        assert len(matches) == 820
        assert len({m.home_id for m in matches}) == 20
        assert all(m.provider != 'demo' for m in matches)


def test_real_holdout_excludes_current_season_and_forecasts(database):
    seed_combined(database)
    mid, report = train(database, 'real', test_year=2025)
    assert report['training_years'] == [2024]
    assert report['test_year'] == 2025 and report['test_count'] == 380
    with database() as db:
        current = db.scalar(select(Season).where(Season.provider == 'bigballs'))
        ids = set(db.scalars(select(Match.id).where(Match.season_id == current.id)))
        assert not ids.intersection(p['match_id'] for p in report['predictions'])
    with database.begin() as db:
        for m in db.scalars(select(Match).where(Match.provider == 'bigballs', Match.status == 'FT')):
            m.home_score, m.away_score = 7, 0
    _, changed = train(database, 'real', test_year=2025)
    assert changed['model'] == report['model']
    assert changed['predictions'] == report['predictions']
    now = datetime(2026, 9, 22)
    assert record_forecasts(database, 'real', now=now) == 10
    assert record_forecasts(database, 'real', now=now) == 0
    with database() as db:
        result = tracker(db, 'real')
        assert result['count'] == 10 and result['scored'] == 0
        assert all(m.provider == 'bigballs' for f,m in result['pairs'])
        assert all(abs(sum(f.probabilities.values())-1) < 1e-9 for f,m in result['pairs'])
        for f,m in result['pairs']: assert f.created_at < m.kickoff


def test_real_training_requires_complete_holdout(database):
    seed_combined(database)
    with database.begin() as db:
        db.delete(db.scalar(select(Match).where(Match.provider == 'football-data')))
    with pytest.raises(ValueError, match='incomplete'):
        train(database, 'real', test_year=2025)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(ModelRun)) == 0


def test_combined_model_visible_on_real_pages_only(database):
    seed_combined(database)
    train(database, 'real', test_year=2025)
    record_forecasts(database, 'real', now=datetime(2026,9,22))
    from app import create_app
    app = create_app({'TESTING': True, 'DATABASE_URL': str(database.kw['bind'].url), 'RATELIMIT_ENABLED': False})
    browser = app.test_client()
    html = browser.get('/predictions').get_data(as_text=True)
    assert 'Season sources:' in html and 'football-data' in html
    assert '10 saved forecasts' in html
    with database() as db:
        demo = db.scalar(select(Season).where(Season.provider == 'demo'))
        historical = db.scalar(select(Season).where(Season.provider == 'football-data', Season.year == 2025))
        match = db.scalar(select(Match).where(Match.season_id == historical.id).order_by(Match.kickoff.desc()))
        assert browser.get(f'/match/{match.id}?season={historical.id}').status_code == 200
        assert 'No trained model yet' in browser.get(f'/predictions?season={demo.id}').get_data(as_text=True)
    app.extensions['league_engine'].dispose()


def test_sync_real_command_and_fail_fast(database, monkeypatch, capsys):
    import manage
    seed_combined(database)
    monkeypatch.setattr(manage, 'open_database', lambda: (database.kw['bind'], database))
    monkeypatch.setattr('sys.argv', ['manage.py', 'sync-real'])
    for name in ['API_FOOTBALL_KEY', 'FOOTBALL_DATA_ORG_KEY', 'BBS_API_KEY']:
        monkeypatch.setenv(name, 'test-only-key')
    calls = []
    for name, count in [('import_season', 380), ('import_football_data', 380), ('import_bigballs_season', 60)]:
        def fake(factory, client, year, name=name, count=count):
            calls.append((name, year))
            return count
        monkeypatch.setattr(manage, name, fake)
    assert manage.main() == 0
    assert calls == [('import_season', 2024), ('import_football_data', 2025), ('import_bigballs_season', 2026)]
    assert 'Ready:' in capsys.readouterr().out
    calls.clear()
    def denied(*args): raise APIError('Season denied')
    monkeypatch.setattr(manage, 'import_football_data', denied)
    assert manage.main() == 1
    assert calls == [('import_season', 2024)]
    assert 'Ready:' not in capsys.readouterr().out
