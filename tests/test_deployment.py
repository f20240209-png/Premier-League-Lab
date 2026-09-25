import os
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from app import create_app
from league.storage import Base, Season, Team, Match, ModelRun, Forecast, SquadSnapshot, normalized_url, open_database
from migrate_database import migrate


@pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg'])
def test_postgres_url(scheme):
    url = normalized_url(f'{scheme}://user:p%40ss@localhost/db?sslmode=require')
    assert url.drivername == 'postgresql+psycopg'
    assert url.password == 'p@ss' and url.query['sslmode'] == 'require'


def test_health_is_independent_of_season_and_sanitizes_failure(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE_URL': f'sqlite:///{tmp_path}/test.db'})
    client = app.test_client()
    assert client.get('/health?season=9999').json == {'status': 'ok'}
    with patch.object(app.extensions['league_engine'], 'connect', side_effect=OperationalError('secret', {}, Exception('password'))):
        result = client.get('/health')
        assert result.status_code == 503
        assert result.json == {'status': 'unavailable'}


@pytest.mark.parametrize('missing', ['FLASK_SECRET_KEY', 'DATABASE_URL', 'COOKIE_SECURE', 'RATELIMIT_STORAGE_URI'])
def test_production_refuses_insecure_config(monkeypatch, missing):
    for key, value in dict(APP_ENV='production', FLASK_SECRET_KEY='x'*64, DATABASE_URL='postgresql://localhost/test', COOKIE_SECURE='true', RATELIMIT_STORAGE_URI='redis://localhost:6379').items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(missing, '')
    with patch('app.load_dotenv'), pytest.raises(RuntimeError):
        create_app()


def test_migration_refuses_missing_source_and_wrong_target(tmp_path):
    with pytest.raises(FileNotFoundError):
        migrate(tmp_path/'missing.db', 'postgresql://localhost/test')
    source = tmp_path/'source.db'
    engine, _ = open_database(f'sqlite:///{source}')
    engine.dispose()
    with pytest.raises(ValueError, match='PostgreSQL'):
        migrate(source, 'sqlite:///:memory:')


def test_all_tables_compile_for_postgres():
    for table in Base.metadata.sorted_tables:
        assert 'CREATE TABLE' in str(CreateTable(table).compile(dialect=postgresql.dialect()))


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Requires a disposable PostgreSQL test database')
def test_postgres_migration_roundtrip_and_ids(tmp_path):
    # TEST_POSTGRES_URL must refer only to a dedicated disposable test database.
    target = os.environ['TEST_POSTGRES_URL']
    engine = create_engine(normalized_url(target))
    assert not set(inspect(engine).get_table_names()) & set(Base.metadata.tables), 'Use an empty test DB'
    src = tmp_path/'source.db'
    source_engine, factory = open_database(f'sqlite:///{src}')
    with factory.begin() as db:
        db.add(Season(id=12, provider='test', year=2026))
        db.add_all([Team(id=1, provider='test', external_id=1, name='Bayındır FC'),
                    Team(id=2, provider='test', external_id=2, name='Away FC')])
        db.flush()
        db.add(Match(id=1, provider='test', external_id=1, season_id=12, home_id=1, away_id=2,
                     kickoff=datetime(2026, 10, 1), status='NS'))
        db.add(ModelRun(id=1, provider='test', trained_through=datetime(2026, 9, 1),
                        parameters={'weights': [0.1, 0.2]}, report={'nested': {'test': None}}))
        db.add(SquadSnapshot(year=2026, data={'name': 'Bayındır', 'players': []}))
        db.flush()
        db.add(Forecast(match_id=1, model_id=1, created_at=datetime(2026, 9, 20),
                        kickoff_at_creation=datetime(2026, 10, 1), probabilities={'home': 0.5, 'draw': 0.3, 'away': 0.2}))
    source_engine.dispose()
    try:
        counts = migrate(src, target)
        assert counts['fl_seasons'] == 1
        assert not inspect(engine).has_table('fl_seasons')
        migrate(src, target, apply=True)
        with engine.begin() as db:
            assert db.scalar(select(Season.year)) == 2026
            new_id = db.execute(Season.__table__.insert().values(provider='test', year=2025).returning(Season.id)).scalar_one()
            assert new_id == 13
        with pytest.raises(ValueError, match='contains app data'):
            migrate(src, target, apply=True)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
