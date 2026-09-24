import json
from copy import deepcopy
from unittest.mock import patch
import pytest
from sqlalchemy import select
from league.squads import BUNDLED, normalize_squads, sync_squads, squad_for_club, bundled_squads
from league.storage import open_database, Season, Team, Match, SquadSnapshot
from datetime import datetime


def raw_snapshot():
    saved=json.loads(BUNDLED.read_text(encoding='utf-8'))
    return {'events':[{'deadline_time':saved['first_deadline']}]*37+[{'deadline_time':saved['last_deadline']}],
            'teams':[{'id':i,'name':c['name']} for i,c in enumerate(saved['clubs'].values(),1)],
            'elements':[dict(id=p['id'],code=p['code'],first_name=p['name'],second_name='',web_name=p['display_name'],
                             team=i,element_type=p['position_order'],status='a',minutes=p['minutes'],goals_scored=p['goals'])
                        for i,c in enumerate(saved['clubs'].values(),1) for p in c['players']]}


def test_live_snapshot_has_season_and_stable_photo_ids():
    data=normalize_squads(raw_snapshot())
    assert data['year']==2026 and len(data['clubs'])==20
    bruno=next(p for p in data['clubs']['man-united']['players'] if p['code']==141746)
    assert 'p141746.png' in bruno['photo']
    assert 'Fernandes' in bruno['name']


@pytest.mark.parametrize('change',['empty','duplicates','unknown-team','wrong-season','negative-stat'])
def test_bad_feed_preserves_existing_snapshot(tmp_path,change):
    engine,factory=open_database(f'sqlite:///{tmp_path / "db.sqlite3"}')
    raw=raw_snapshot();old=normalize_squads(raw)
    with factory.begin() as db:db.add(SquadSnapshot(year=old['year'],data=old))
    if change=='empty':raw['elements']=[]
    if change=='duplicates':raw['elements'].append(raw['elements'][0])
    if change=='unknown-team':raw['elements'][0]['team']=999
    if change=='wrong-season':raw['events'][-1]['deadline_time']='2030-05-01T00:00:00Z'
    if change=='negative-stat':raw['elements'][0]['goals_scored']=-1
    with patch('league.squads.fetch_squads',side_effect=lambda:normalize_squads(raw)):
        with pytest.raises(ValueError):sync_squads(factory)
    with factory() as db:assert db.scalar(select(SquadSnapshot)).data==old
    engine.dispose()


def test_current_roster_not_applied_to_demo_or_historical_clubs(tmp_path):
    engine,factory=open_database(f'sqlite:///{tmp_path / "db.sqlite3"}')
    with factory() as db:
        team=Team(name='Manchester United FC',provider='football-data',external_id=66)
        assert squad_for_club(db,Season(provider='football-data',year=2025),team) is None
        assert squad_for_club(db,Season(provider='demo',year=2026),team) is None
        roster=squad_for_club(db,Season(provider='bigballs',year=2026),team)
        assert roster and len(roster['players'])>=11
    engine.dispose()


def test_refresh_idempotent_and_utf8_view(tmp_path):
    from app import create_app
    app=create_app({'TESTING':True,'DATABASE_URL':f'sqlite:///{tmp_path / "db.sqlite3"}'})
    factory=app.extensions['league_factory'];snapshot=normalize_squads(raw_snapshot())
    with patch('league.squads.fetch_squads',return_value=snapshot):
        sync_squads(factory);sync_squads(factory)
    with factory.begin() as db:
        assert len(list(db.scalars(select(SquadSnapshot))))==1
        season=Season(provider='bigballs',year=2026);home=Team(provider='bigballs',external_id=1,name='Manchester United');away=Team(provider='bigballs',external_id=2,name='Arsenal')
        db.add_all([season,home,away]);db.flush();tid=home.id
        db.add(Match(provider='bigballs',external_id=1,season_id=season.id,home_id=home.id,away_id=away.id,kickoff=datetime(2026,10,1),status='NS'))
    page=app.test_client().get(f'/team/{tid}')
    assert page.status_code==200
    assert 'Fernandes' in page.text and 'squad-photo' in page.text
    assert 'FPL-listed players' in page.text and 'Snapshot' in page.text
    assert 'Bayındır' in page.text
