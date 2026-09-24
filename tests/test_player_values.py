from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
from sqlalchemy import select, func
from league.storage import open_database, ValueModel, Season
from league.value_data import build_dataset, download_source, POSITIONS
from league.value_model import fit_value_model, estimate_value, plot_bytes


def source_frames():
    players=pd.DataFrame([dict(player_id=i,name=f'Player {i}',date_of_birth='1998-02-01',position='Attack') for i in range(1,4)])
    games=[];appearances=[];valuations=[]
    for year in [2022,2023]:
        dates=pd.date_range(f'{year}-08-01',f'{year+1}-05-28',periods=380).normalize()
        for i,date in enumerate(dates):
            game_id=year*1000+i
            games.append(dict(game_id=game_id,competition_id='GB1',season=year,date=str(date.date())))
            if i<5:
                for player_id in [1,2,3]:
                    appearances.append(dict(game_id=game_id,player_id=player_id,goals=1,assists=0,minutes_played=90))
        for pid in [1,2,3]:
            valuations.extend([dict(player_id=pid,date=f'{year+1}-01-01',market_value_in_eur=1),
                               dict(player_id=pid,date=f'{year+1}-06-01',market_value_in_eur=10_000_000),
                               dict(player_id=pid,date=f'{year+1}-06-10',market_value_in_eur=99_000_000)])
    return dict(players=players,games=pd.DataFrame(games),appearances=pd.DataFrame(appearances),player_valuations=pd.DataFrame(valuations))


def training_rows():
    rng=np.random.default_rng(12)
    rows=[]
    for year,count in [(2021,120),(2022,120),(2023,60)]:
        for i in range(count):
            goals=int(rng.integers(0,25));assists=int(rng.integers(0,15));minutes=int(rng.integers(450,3421));age=int(rng.integers(18,38))
            rows.append(dict(player_id=i,name=f'Player {i}',season=year,goals=goals,assists=assists,minutes=minutes,age=age,
                             position=POSITIONS[i%4],actual_eur=10_000_000+goals*600_000+minutes*400-age*100_000,
                             valuation_date=pd.Timestamp(year+1,6,10),stats_through=pd.Timestamp(year+1,5,25),appearance_count=30))
    return pd.DataFrame(rows)


def manifest():
    return dict(coverage={},prepared_at='2026-09-22',eligibility='Test data only',position_note='Snapshot position',data_note='Synthetic test fixtures')


@pytest.fixture
def factory(tmp_path):
    engine,factory=open_database(f'sqlite:///{tmp_path / "values.db"}')
    yield factory
    engine.dispose()


def test_dates_and_first_post_season_label():
    frames=source_frames()
    rows,coverage=build_dataset(frames,2022,2023)
    assert len(rows)==6
    assert set(rows.actual_eur)=={10_000_000}
    assert set(rows.goals)=={5} and set(rows.minutes)=={450}
    assert (rows.stats_through<rows.valuation_date).all()
    assert coverage['2022']['games']==380
    assert rows.iloc[0].age==pytest.approx((pd.Timestamp('2023-06-01')-pd.Timestamp('1998-02-01')).days/365.2425)


def test_missing_stats_exclude_player_season_not_zero():
    frames=source_frames();frames['appearances'].loc[0,'assists']=np.nan
    rows,_=build_dataset(frames,2022,2023)
    assert len(rows)==5
    assert rows[(rows.player_id==1)&(rows.season==2022)].empty


def test_duplicate_appearances_and_incomplete_season_refused():
    frames=source_frames()
    frames['appearances']=pd.concat([frames['appearances'],frames['appearances'].iloc[:1]])
    with pytest.raises(ValueError,match='duplicate'):build_dataset(frames,2022,2023)
    frames=source_frames();frames['games']=frames['games'].iloc[:-1]
    with pytest.raises(ValueError,match='two complete'):build_dataset(frames,2022,2023)


def test_no_future_label_or_latest_profile_value():
    frames=source_frames()
    frames['players']['market_value_in_eur']=999_999_999
    mask=frames['player_valuations'].date.str.endswith('06-01')
    frames['player_valuations'].loc[mask,'date']=frames['player_valuations'].loc[mask,'date'].str.replace('2023','2100').str.replace('2024','2101')
    rows,_=build_dataset(frames,2022,2023)
    assert set(rows.actual_eur)=={99_000_000} # later June record, not future or current profile value


def test_holdout_labels_do_not_change_fit_and_json_predictions_match(factory):
    rows=training_rows()
    mid,report=fit_value_model(factory,rows,manifest(),2023)
    altered=rows.copy();altered.loc[altered.season==2023,'actual_eur']*=2
    other,_=fit_value_model(factory,altered,manifest(),2023)
    with factory() as db:
        first,second=db.get(ValueModel,mid),db.get(ValueModel,other)
        assert first.parameters==second.parameters
        for example in first.examples:
            estimate,_=estimate_value(first.parameters,example)
            assert estimate==pytest.approx(example['predicted_eur'])
        assert report['train_count']==240 and report['test_count']==60
        assert plot_bytes(first).getvalue().startswith(b'\x89PNG')


def test_failed_training_preserves_existing_and_success_is_idempotent(factory):
    rows=training_rows();mid,_=fit_value_model(factory,rows,manifest(),2023)
    again,_=fit_value_model(factory,rows,manifest(),2023)
    assert mid==again
    with pytest.raises(ValueError):fit_value_model(factory,rows.iloc[:50],manifest(),2023)
    with factory() as db:assert db.scalar(select(func.count()).select_from(ValueModel))==1


@pytest.mark.parametrize('key,value',[('age','nan'),('goals','inf'),('minutes','0'),('assists','2.5'),('position','Unknown')])
def test_invalid_manual_profile_rejected(factory,key,value):
    mid,_=fit_value_model(factory,training_rows(),manifest(),2023)
    with factory() as db:
        model=db.get(ValueModel,mid);profile=dict(model.examples[0]);profile[key]=value
        with pytest.raises(ValueError):estimate_value(model.parameters,profile)


def test_corrupt_download_preserves_previous_file(tmp_path,monkeypatch):
    target=tmp_path/'players.csv.gz';target.write_bytes(b'previous-good-file')
    response=Mock(status_code=200);response.iter_content.return_value=[b'not-a-gzip-file']
    response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=None)
    monkeypatch.setattr('league.value_data.requests.get',lambda *a,**k:response)
    with pytest.raises(ValueError):download_source(tmp_path,refresh=True,emit=lambda *a,**k:None)
    assert target.read_bytes()==b'previous-good-file'
    assert not (tmp_path/'players.csv.part').exists()


def test_value_page_uses_its_own_source_and_validates_post(tmp_path):
    from app import create_app
    app=create_app({'TESTING':True,'WTF_CSRF_ENABLED':False,'DATABASE_URL':f'sqlite:///{tmp_path / "web.db"}'})
    factory=app.extensions['league_factory'];web=app.test_client()
    assert 'not trained yet' in web.get('/player-values').text
    with factory.begin() as db:db.add(Season(provider='demo',year=2026))
    mid,_=fit_value_model(factory,training_rows(),manifest(),2023)
    response=web.get('/player-values?player=1')
    assert response.status_code==200
    assert 'Synthetic demo' not in response.text
    assert 'Player 1' in response.text and 'Recorded market valuation' in response.text
    assert web.get(f'/player-values/{mid}/plot.png').mimetype=='image/png'
    assert web.get('/player-values?player=missing').status_code==404
    assert web.post('/player-values',data=dict(goals='NaN',assists=1,minutes=1000,age=25,position='Attack')).status_code==400
    assert web.post('/player-values',data=dict(goals=5,assists=1,minutes=1000,age=25,position='Attack')).status_code==200
    app.extensions['league_engine'].dispose()
