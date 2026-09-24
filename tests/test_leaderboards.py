from copy import deepcopy
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from league.storage import open_database, Season, PlayerLeaderboard, SyncRun
from league.leaderboards import normalize, import_board, sync_leaders
from check_api_football import APIError


def fd():
    return {'competition': {'id':2021,'code':'PL'}, 'season':{'startDate':'2025-08-15'},
            'scorers':[{'player':{'id':1,'name':'Player A'},'team':{'name':'Club A'},'goals':4,'assists':None},
                       {'player':{'id':2,'name':'Player B'},'team':{'name':'Club B'},'goals':2,'assists':0}]}


def bbs():
    return {'meta':{'league':'epl','season':2026},'data':[{'id':None,'player_name':'Player C','team':'Club C','goals':2,'assists':1}]}


def api():
    return {'response':[{'player':{'id':1,'name':'Player A'},'statistics':[
        {'league':{'id':39,'season':2024},'team':{'id':1,'name':'Club A'},'goals':{'total':2,'assists':None}},
        {'league':{'id':39,'season':2024},'team':{'id':2,'name':'Club B'},'goals':{'total':1,'assists':1}}]}]}


def test_missing_not_zero_and_subset_label():
    rows, label = normalize(fd(), 'football-data',2025,'assists')
    assert len(rows)==1 and rows[0]['value']==0
    assert 'not a league-wide' in label
    rows, _ = normalize(api(),'api-football',2024,'assists')
    assert rows[0]['value']==1 and rows[0]['incomplete']
    assert normalize(api(),'api-football',2024,'goals')[0][0]['value']==3
    assert normalize(bbs(),'bigballs',2026,'goals')[0][0]['value']==2


@pytest.mark.parametrize('provider,body,year', [('football-data',fd(),2024),('bigballs',bbs(),2025),('api-football',api(),2023)])
def test_wrong_season_rejected(provider,body,year):
    with pytest.raises(ValueError):
        normalize(body,provider,year,'goals')


@pytest.mark.parametrize('value',[True,-1,'3'])
def test_invalid_stats(value):
    body=bbs();body['data'][0]['goals']=value
    with pytest.raises(ValueError): normalize(body,'bigballs',2026,'goals')


def test_atomic_refresh_and_idempotency(tmp_path):
    engine,factory=open_database(f'sqlite:///{tmp_path / "players.db"}')
    with factory.begin() as db: db.add(Season(provider='football-data',year=2025))
    client=Mock();client.scorers.return_value=fd()
    for _ in range(2): assert import_board(factory,client,'football-data',2025,'goals')==2
    bad=fd();bad['scorers'][1]['goals']=-1
    client.scorers.return_value=bad
    with pytest.raises(ValueError): import_board(factory,client,'football-data',2025,'goals')
    client.scorers.side_effect=APIError('Quota reached')
    with pytest.raises(APIError): import_board(factory,client,'football-data',2025,'goals')
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlayerLeaderboard))==1
        assert db.scalar(select(PlayerLeaderboard)).rows[0]['value']==4
        assert list(db.scalars(select(SyncRun.status).order_by(SyncRun.id)))==['success','success','failed','failed']
    engine.dispose()


def test_sync_continues_and_reuses_scorers_response(tmp_path):
    engine,factory=open_database(f'sqlite:///{tmp_path / "players.db"}')
    with factory.begin() as db:
        db.add_all([Season(provider=p,year=y) for p,y in [('api-football',2024),('football-data',2025),('bigballs',2026)]])
    a,f,b=Mock(),Mock(),Mock()
    a.get.side_effect=APIError('Denied');f.scorers.return_value=fd();b.get.return_value=bbs()
    assert sync_leaders(factory,{'api-football':lambda:a,'football-data':lambda:f,'bigballs':lambda:b},emit=lambda _:None)==2
    f.scorers.assert_called_once_with(2025)
    assert b.get.call_count==2
    with factory() as db: assert db.scalar(select(func.count()).select_from(PlayerLeaderboard))==4
    engine.dispose()


def test_leaderboard_web_scope_and_empty_state(tmp_path):
    from app import create_app
    app=create_app({'TESTING':True,'DATABASE_URL':f'sqlite:///{tmp_path / "web.db"}'})
    factory=app.extensions['league_factory']
    with factory.begin() as db: db.add(Season(provider='football-data',year=2025))
    web=app.test_client()
    html=web.get('/top-assists').text
    assert 'No imported assists' in html and 'Partial player coverage' not in html
    import_board(factory,None,'football-data',2025,'assists',fd())
    html=web.get('/top-assists').text
    assert 'Player B' in html and 'Player A' not in html
    assert 'not a league-wide assists ranking' in html and 'Last successful import' in html
    app.extensions['league_engine'].dispose()
