from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import re

import pytest
from sqlalchemy import select, func, text

from check_api_football import APIError
from league.storage import open_database, Season, Team, Match, PlayerSeason, SyncRun, ModelRun, Forecast, utcnow
from league.importer import import_season, import_stats, import_players, upsert_fixtures
from league.analytics import standings, feature_rows
from league.prediction import train, record_forecasts, probabilities, tracker
from league.demo import seed_demo


@pytest.fixture
def db_factory(tmp_path):
    engine, factory = open_database(f'sqlite:///{tmp_path / "test.sqlite3"}')
    yield factory
    engine.dispose()


def fixture(mid=10, year=2024, home=1, away=2, hg=2, ag=1, status='FT', when='2024-08-16T19:00:00+00:00'):
    return {'fixture': {'id':mid, 'date':when,'status':{'short':status}},
            'league':{'id':39,'season':year},
            'teams':{'home':{'id':home,'name':f'Club {home}'},'away':{'id':away,'name':f'Club {away}'}},
            'goals':{'home':hg,'away':ag}}


def imported(factory, rows=None, year=2024):
    api = Mock()
    api.get.return_value = {'response': rows or [fixture()]}
    import_season(factory, api, year)
    return api


def test_import_is_idempotent_and_preserves_legacy_tables(db_factory):
    with db_factory.begin() as db:
        db.execute(text('CREATE TABLE legacy_marker (value INTEGER)'))
        db.execute(text('INSERT INTO legacy_marker VALUES (42)'))
    imported(db_factory)
    with db_factory() as db:
        mid = db.scalar(select(Match.id))
        tids = list(db.scalars(select(Team.id)))
    imported(db_factory, [fixture(hg=3)])
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Match)) == 1
        assert db.scalar(select(Match.id)) == mid
        assert list(db.scalars(select(Team.id))) == tids
        assert db.scalar(select(Match.home_score)) == 3
        assert db.execute(text('SELECT value FROM legacy_marker')).scalar() == 42


def test_api_denial_preserves_results_and_records_failure(db_factory):
    imported(db_factory)
    api = Mock()
    api.get.side_effect = APIError('Season access denied')
    with pytest.raises(APIError):
        import_season(db_factory, api, 2025)
    with db_factory() as db:
        assert db.scalar(select(Match.home_score)) == 2
        assert list(db.scalars(select(SyncRun.status).order_by(SyncRun.id))) == ['success','failed']
        assert db.scalar(select(func.count()).select_from(Season)) == 1


@pytest.mark.parametrize('bad', [fixture(home=1,away=1),fixture(hg=-1),fixture(hg=None),fixture(year=2023)])
def test_invalid_payload_is_rejected_before_writing(db_factory, bad):
    api = Mock()
    api.get.return_value = {'response':[fixture(),bad]}
    with pytest.raises(ValueError):
        import_season(db_factory,api,2024)
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(Match)) == 0


def test_changed_identity_rolls_back_even_earlier_updates(db_factory):
    imported(db_factory,[fixture(),fixture(mid=11,home=3,away=4)])
    api = Mock()
    api.get.return_value = {'response':[fixture(hg=9),fixture(mid=11,home=3,away=5)]}
    with pytest.raises(ValueError):
        import_season(db_factory,api,2024)
    with db_factory() as db:
        assert db.scalar(select(Match.home_score).where(Match.external_id==10)) == 2
        assert db.scalar(select(func.count()).select_from(Team)) == 4


def test_stats_are_bounded_resumable_and_keep_null(db_factory):
    imported(db_factory,[fixture(),fixture(mid=11,home=2,away=1)])
    api = Mock()
    api.get.return_value = {'response':[
        {'team':{'id':1},'statistics':[{'type':'Total Shots','value':0},{'type':'Ball Possession','value':'55%'}]},
        {'team':{'id':2},'statistics':[{'type':'Total Shots','value':None},{'type':'Ball Possession','value':'45%'}]}]}
    assert import_stats(db_factory,api,2024,1) == 1
    assert api.get.call_count == 1
    assert import_stats(db_factory,api,2024,1) == 1
    assert import_stats(db_factory,api,2024,1) == 0
    with db_factory() as db:
        m = db.scalar(select(Match).where(Match.external_id==10))
        assert m.home_shots == 0 and m.away_shots is None and m.home_possession == 55


def test_player_partial_import_is_marked_incomplete(db_factory):
    imported(db_factory)
    api = Mock()
    api.get.return_value = {'paging':{'current':1,'total':2},'response':[
        {'player':{'id':100,'name':'Player'},'statistics':[{
            'league':{'id':39,'season':2024},'team':{'id':1},
            'games':{'position':'Attacker','minutes':90},'goals':{'total':0,'assists':None}}]}]}
    assert import_players(db_factory,api,2024,1) == (1,False)
    with db_factory() as db:
        assert not db.scalar(select(Season.players_complete))
        p = db.scalar(select(PlayerSeason))
        assert p.goals == 0 and p.assists is None


def simple_match(i,home,away,hg,ag,day):
    return SimpleNamespace(id=i,home_id=home,away_id=away,home_score=hg,away_score=ag,
                           kickoff=datetime(2024,1,1)+timedelta(days=day),status='FT')


def test_features_exclude_own_and_same_kickoff_results():
    matches = [simple_match(i,1,2,i%3,1,i) for i in range(4)]
    original = deepcopy(feature_rows(matches)[0]['x'])
    matches[-1].home_score = 100
    assert feature_rows(matches)[0]['x'] == original
    matches.append(simple_match(5,1,2,9,0,3))
    matches[-1].kickoff += timedelta(hours=1)
    rows = feature_rows(matches)
    assert rows[0]['x'] == rows[1]['x']


def test_what_if_does_not_change_stored_results(db_factory):
    imported(db_factory,[fixture(),fixture(mid=11,hg=None,ag=None,status='NS')])
    with db_factory() as db:
        matches = list(db.scalars(select(Match).order_by(Match.id)))
        teams = {t.id:t for t in db.scalars(select(Team))}
        actual = standings(matches,teams)
        scenario = standings(matches,teams,{matches[1].id:(0,4)})
        assert actual[0]['points'] == 3
        assert len([r for r in scenario if r['points']==3]) == 2
        assert matches[1].home_score is None


@pytest.fixture(scope='module')
def demo_factory(tmp_path_factory):
    path = tmp_path_factory.mktemp('demo')/'demo.sqlite3'
    engine, factory = open_database(f'sqlite:///{path}')
    seed_demo(factory)
    yield factory
    engine.dispose()


def test_training_forecasts_and_tracking(demo_factory):
    mid, report = train(demo_factory, 'demo')
    assert report['train_count'] >= 50 and report['test_count'] >= 30
    assert max(report['training_years']) < report['test_year']
    assert sum(sum(row) for row in report['model']['confusion']) == report['test_count']
    with demo_factory() as db:
        run = db.get(ModelRun,mid)
        p = probabilities(run.parameters,[1,1,1,1,1,1])
        assert sum(p.values()) == pytest.approx(1)
        assert all(0<=value<=1 for value in p.values())
    count = record_forecasts(demo_factory,'demo')
    assert count > 0
    assert record_forecasts(demo_factory,'demo') == 0
    with demo_factory() as db:
        summary = tracker(db,'demo')
        assert summary['count'] == count
        assert summary['scored'] == 0
        for f,m in summary['pairs']:
            assert f.created_at < m.kickoff


@pytest.fixture
def webapp(demo_factory):
    from app import create_app
    url = str(demo_factory.kw['bind'].url)
    app = create_app({'TESTING':True,'DATABASE_URL':url,'SECRET_KEY':'test-secret',
                      'RATELIMIT_ENABLED':False,'GEMINI_API_KEY':''})
    yield app
    app.extensions['league_engine'].dispose()


def csrf(client,path='/login'):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"',html).group(1)


def test_all_pages_and_invalid_identifiers(webapp):
    client=webapp.test_client()
    for path in ['/', '/teams','/fixtures','/results','/compare','/predictions','/what-if',
                 '/top-scorers','/top-assists','/team/1','/match/1?season=1','/login','/health']:
        response=client.get(path)
        assert response.status_code==200,(path,response.get_data(as_text=True)[:400])
    assert client.get('/team/999999').status_code==404
    assert client.get('/?season=999999').status_code==404
    assert client.get('/compare?left=999999').status_code==404


def test_csrf_auth_and_ai_validation(webapp):
    client=webapp.test_client()
    assert client.post('/login',data={'password':'bad'}).status_code==400
    token=csrf(client)
    assert client.post('/login',data={'password':'bad','csrf_token':token}).status_code==401
    assert client.post('/admin/sync',headers={'X-CSRFToken':token}).status_code==403
    assert client.post('/ask-ai',json={'message':[]},headers={'X-CSRFToken':token}).status_code==400
    assert client.post('/ask-ai',json={'message':'How are Arsenal doing?','team_id':1},headers={'X-CSRFToken':token}).status_code==503
    assert client.get('/logout').status_code==405
    assert client.get('/').headers['X-Content-Type-Options']=='nosniff'


def test_admin_password_hash_login(webapp):
    from werkzeug.security import generate_password_hash
    webapp.config['ADMIN_PASSWORD_HASH']=generate_password_hash('a-long-test-password')
    client=webapp.test_client()
    token=csrf(client)
    response=client.post('/login',data={'password':'a-long-test-password','csrf_token':token})
    assert response.status_code==302 and response.location.endswith('/admin')
    assert client.get('/admin').status_code==200


def test_what_if_post_and_input_validation(webapp):
    client=webapp.test_client()
    with webapp.extensions['league_factory']() as db:
        season=db.scalar(select(Season).where(Season.provider=='demo',Season.year==2025))
        match=db.scalar(select(Match).where(Match.season_id==season.id,Match.status=='NS'))
        path=f'/what-if?season={season.id}'
        mid=match.id
    token=csrf(client,path)
    assert client.post(path,data={'csrf_token':token,f'home_{mid}':'2',f'away_{mid}':'1'}).status_code==200
    assert client.post(path,data={'csrf_token':token,f'home_{mid}':'-1',f'away_{mid}':'1'}).status_code==400
    with webapp.extensions['league_factory']() as db:
        assert db.get(Match,mid).home_score is None


def test_empty_database_renders(tmp_path):
    from app import create_app
    app=create_app({'TESTING':True,'DATABASE_URL':f'sqlite:///{tmp_path / "empty.sqlite3"}',
                    'RATELIMIT_ENABLED':False})
    client=app.test_client()
    for path in ['/', '/teams','/compare','/predictions','/fixtures','/results','/top-assists','/what-if']:
        assert client.get(path).status_code==200,path
    app.extensions['league_engine'].dispose()
