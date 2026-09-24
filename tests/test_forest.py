from datetime import datetime, timedelta
from types import SimpleNamespace
import json
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sqlalchemy import select
from league.forest import fit_forest, SETTINGS
from league.prediction import probabilities, compare_candidates, train, record_forecasts
from league.storage import open_database, ModelRun


def rows(n=200):
    rng=np.random.default_rng(7)
    return [dict(x=rng.normal(size=6).tolist(),y=['A','D','H'][i%3],
                 match=SimpleNamespace(kickoff=datetime(2024,1,1)+timedelta(days=i//2))) for i in range(n)]


def test_json_forest_matches_sklearn_probabilities():
    training=rows()
    x=np.asarray([r['x'] for r in training],dtype=np.float32)
    original=RandomForestClassifier(**SETTINGS).fit(x,[r['y'] for r in training])
    parameters=json.loads(json.dumps(fit_forest(training)))
    for vector,expected in zip(x[:25],original.predict_proba(x[:25])):
        actual=probabilities(parameters,vector)
        assert list(actual)==list(original.classes_)
        assert list(actual.values())==pytest.approx(expected,abs=1e-12)
        assert sum(actual.values())==pytest.approx(1)


def test_selection_ignores_benchmark_labels_and_groups_dates():
    training=rows();test=rows(40)
    _,_,first=compare_candidates(training,test)
    for row in test:row['y']='H'
    _,_,second=compare_candidates(training,test)
    assert first['selected']==second['selected']
    for name in first['candidates']:
        assert first['candidates'][name]['validation']==second['candidates'][name]['validation']
    assert first['fit_count']==150 and first['validation_count']==50
    assert first['validation_start']=='2024-03-16'


def test_combined_comparison_and_forecasts(tmp_path):
    from test_real_data import seed_combined
    from app import create_app
    url=f'sqlite:///{tmp_path / "comparison.db"}'
    engine,factory=open_database(url);seed_combined(factory)
    mid,report=train(factory,'real',test_year=2025,compare=True)
    assert set(report['comparison']['candidates'])=={'logistic_regression','random_forest'}
    assert report['model']==report['comparison']['candidates'][report['algorithm']]['test']
    with factory() as db:
        run=db.get(ModelRun,mid)
        assert probabilities(run.parameters,[1]*6).keys()=={'A','D','H'}
    assert record_forecasts(factory,'real',now=datetime(2026,9,22))>0
    assert record_forecasts(factory,'real',now=datetime(2026,9,22))==0
    app=create_app({'TESTING':True,'DATABASE_URL':url})
    page=app.test_client().get('/predictions')
    assert page.status_code==200 and 'Model comparison' in page.text and 'Random Forest' in page.text
    app.extensions['league_engine'].dispose();engine.dispose()
