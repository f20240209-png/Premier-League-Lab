"""Reproducible synthetic fixtures for offline development, never real results."""
from datetime import datetime, timedelta
import numpy as np
from sqlalchemy import select
from .storage import Season, PlayerSeason, Team, utcnow
from .importer import upsert_fixtures

NAMES = ["Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Chelsea", "Crystal Palace",
         "Everton", "Fulham", "Ipswich Town", "Leicester City", "Liverpool", "Manchester City",
         "Manchester United", "Newcastle", "Nottingham Forest", "Southampton", "Tottenham", "West Ham", "Wolves"]


def seed_demo(factory):
    with factory() as db:
        if db.scalar(select(Season).where(Season.provider == "demo")):
            raise ValueError("Demo already exists; existing data was preserved.")
    rng = np.random.default_rng(42)
    order, schedule = list(range(20)), []
    for round_no in range(19):
        pairs = [(order[i], order[-i-1]) if round_no % 2 else (order[-i-1], order[i]) for i in range(10)]
        schedule.append(pairs)
        order = [order[0], order[-1], *order[1:-1]]
    schedule += [[(a, h) for h, a in pairs] for pairs in schedule[:19]]
    strength = rng.uniform(.7, 1.5, 20)
    now = utcnow().replace(hour=15, minute=0, second=0, microsecond=0)
    with factory.begin() as db:
        for year in (2022, 2023, 2024, 2025):
            rows = []
            for round_no, pairs in enumerate(schedule if year < 2025 else schedule[:8]):
                kickoff = datetime(year, 8, 12, 15) + timedelta(days=round_no * 7)
                if year == 2025:
                    kickoff = now + timedelta(days=(round_no - 5) * 7 + 2)
                finished = kickoff < now
                for i, (h, a) in enumerate(pairs):
                    rows.append({"fixture": {"id": year * 1000 + round_no * 10 + i,
                        "date": kickoff.isoformat() + "+00:00", "status": {"short": "FT" if finished else "NS"}},
                        "league": {"id": 39, "season": year},
                        "teams": {"home": {"id": h+1, "name": NAMES[h]}, "away": {"id": a+1, "name": NAMES[a]}},
                        "goals": {"home": int(rng.poisson(1.4 * strength[h] / strength[a])) if finished else None,
                                  "away": int(rng.poisson(1.0 * strength[a] / strength[h])) if finished else None}})
            upsert_fixtures(db, rows, year, provider="demo")
        db.flush()
        season = db.scalar(select(Season).where(Season.provider == "demo", Season.year == 2024))
        for team in db.scalars(select(Team).where(Team.provider == "demo")):
            db.add(PlayerSeason(season_id=season.id, external_id=team.external_id, team_id=team.id,
                name=f"Sample player {team.external_id}", position="Attacker", minutes=1800,
                goals=int(rng.integers(1, 20)), assists=int(rng.integers(0, 10))))
    return "Synthetic demo added. All demo results and player statistics are fictional."
