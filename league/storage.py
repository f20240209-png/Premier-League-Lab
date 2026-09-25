from datetime import datetime, timezone
import os
from pathlib import Path

from sqlalchemy import (create_engine, event, String, Integer, Float, DateTime,
                        ForeignKey, UniqueConstraint, CheckConstraint, JSON, Text)
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Season(Base):
    __tablename__ = "fl_seasons"
    __table_args__ = (UniqueConstraint("provider", "year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    year: Mapped[int] = mapped_column(Integer)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    players_complete: Mapped[bool] = mapped_column(default=False)


class Team(Base):
    __tablename__ = "fl_teams"
    __table_args__ = (UniqueConstraint("provider", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    logo: Mapped[str | None] = mapped_column(String(500))


class ProviderIdentity(Base):
    """Lossless UUID mapping; preserves existing integer IDs without migration."""
    __tablename__ = "fl_provider_identities"
    __table_args__ = (UniqueConstraint("provider", "kind", "external_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(36))


class Match(Base):
    __tablename__ = "fl_matches"
    __table_args__ = (
        UniqueConstraint("provider", "external_id"),
        CheckConstraint("home_id <> away_id"),
        CheckConstraint("home_score IS NULL OR home_score >= 0"),
        CheckConstraint("away_score IS NULL OR away_score >= 0"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[int] = mapped_column(Integer)
    season_id: Mapped[int] = mapped_column(ForeignKey("fl_seasons.id"), index=True)
    home_id: Mapped[int] = mapped_column(ForeignKey("fl_teams.id"))
    away_id: Mapped[int] = mapped_column(ForeignKey("fl_teams.id"))
    kickoff: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(20))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    home_shots: Mapped[float | None] = mapped_column(Float)
    away_shots: Mapped[float | None] = mapped_column(Float)
    home_possession: Mapped[float | None] = mapped_column(Float)
    away_possession: Mapped[float | None] = mapped_column(Float)
    stats_checked_at: Mapped[datetime | None] = mapped_column(DateTime)


class PlayerSeason(Base):
    __tablename__ = "fl_player_seasons"
    __table_args__ = (UniqueConstraint("season_id", "external_id", "team_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("fl_seasons.id"))
    external_id: Mapped[int] = mapped_column(Integer)
    team_id: Mapped[int] = mapped_column(ForeignKey("fl_teams.id"))
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(80))
    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)


class PlayerLeaderboard(Base):
    """Provider league aggregates, deliberately separate from club-spell records."""
    __tablename__ = "fl_player_leaderboards"
    __table_args__ = (UniqueConstraint("season_id", "metric"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("fl_seasons.id"))
    metric: Mapped[str] = mapped_column(String(10))
    rows: Mapped[list] = mapped_column(JSON)
    coverage: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SquadSnapshot(Base):
    """FPL player pool keyed by verified season, never treated as historical stats."""
    __tablename__ = "fl_squad_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True)
    data: Mapped[dict] = mapped_column(JSON)


class SyncRun(Base):
    __tablename__ = "fl_sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    count: Mapped[int] = mapped_column(default=0)
    detail: Mapped[str | None] = mapped_column(Text)


class ModelRun(Base):
    __tablename__ = "fl_model_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    trained_through: Mapped[datetime] = mapped_column(DateTime)
    parameters: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)


class ValueModel(Base):
    __tablename__ = "fl_value_models"
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    parameters: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON)
    examples: Mapped[list] = mapped_column(JSON)


class Forecast(Base):
    __tablename__ = "fl_forecasts"
    __table_args__ = (UniqueConstraint("match_id", "model_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("fl_matches.id"))
    model_id: Mapped[int] = mapped_column(ForeignKey("fl_model_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    kickoff_at_creation: Mapped[datetime] = mapped_column(DateTime)
    probabilities: Mapped[dict] = mapped_column(JSON)


def database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if os.getenv("DB_HOST"):
        return URL.create("mysql+pymysql", username=os.getenv("DB_USER") or os.getenv("DB_USERNAME"),
                          password=os.getenv("DB_PASSWORD"), host=os.environ["DB_HOST"],
                          port=int(os.getenv("DB_PORT", "3306")),
                          database=os.getenv("DB_NAME") or os.getenv("DB_DATABASE"))
    root = Path(__file__).resolve().parent.parent / "instance"
    root.mkdir(exist_ok=True)
    return f"sqlite:///{root / 'football.sqlite3'}"


def normalized_url(url):
    parsed = make_url(url)
    if parsed.drivername in ('postgres', 'postgresql'):
        parsed = parsed.set(drivername='postgresql+psycopg')
    return parsed


def open_database(url=None):
    engine = create_engine(normalized_url(url or database_url()), pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)  # Only fl_* tables; never touches legacy tables.
    return engine, sessionmaker(engine, expire_on_commit=False)
