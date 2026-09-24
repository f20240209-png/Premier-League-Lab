"""Explicit EPL club aliases and one source per season for combined modelling.

Provider rows keep their native identities. Only detached modelling views use
these reviewed aliases; no fuzzy matching or destructive identity merge occurs.
"""
from types import SimpleNamespace
from collections import Counter
from sqlalchemy import select
from .storage import Season, Team, Match
from .importer import FINISHED

REAL_PROVIDERS = ("api-football", "football-data", "bigballs")
ALIASES = {
    "arsenal": ["Arsenal", "Arsenal FC"],
    "aston-villa": ["Aston Villa", "Aston Villa FC"],
    "bournemouth": ["Bournemouth", "AFC Bournemouth"],
    "brentford": ["Brentford", "Brentford FC"],
    "brighton": ["Brighton", "Brighton & Hove Albion", "Brighton & Hove Albion FC"],
    "chelsea": ["Chelsea", "Chelsea FC"],
    "crystal-palace": ["Crystal Palace", "Crystal Palace FC"],
    "everton": ["Everton", "Everton FC"],
    "fulham": ["Fulham", "Fulham FC"],
    "ipswich": ["Ipswich", "Ipswich Town", "Ipswich Town FC"],
    "leicester": ["Leicester", "Leicester City", "Leicester City FC"],
    "liverpool": ["Liverpool", "Liverpool FC"],
    "man-city": ["Manchester City", "Manchester City FC", "Man City"],
    "man-united": ["Manchester United", "Manchester United FC", "Man United"],
    "newcastle": ["Newcastle", "Newcastle United", "Newcastle United FC"],
    "nottingham": ["Nottingham Forest", "Nottingham Forest FC"],
    "southampton": ["Southampton", "Southampton FC"],
    "tottenham": ["Tottenham", "Tottenham Hotspur", "Tottenham Hotspur FC"],
    "west-ham": ["West Ham", "West Ham United", "West Ham United FC"],
    "wolves": ["Wolves", "Wolverhampton Wanderers", "Wolverhampton Wanderers FC"],
    "leeds": ["Leeds", "Leeds United", "Leeds United FC"],
    "burnley": ["Burnley", "Burnley FC"],
    "sunderland": ["Sunderland", "Sunderland AFC"],
    "hull": ["Hull", "Hull City", "Hull City AFC"],
    "luton": ["Luton", "Luton Town", "Luton Town FC"],
    "sheffield-united": ["Sheffield United", "Sheffield United FC"],
    "watford": ["Watford", "Watford FC"],
    "norwich": ["Norwich", "Norwich City", "Norwich City FC"],
    "coventry": ["Coventry", "Coventry City", "Coventry City FC"],
    "middlesbrough": ["Middlesbrough", "Middlesbrough FC"],
    "west-brom": ["West Brom", "West Bromwich Albion", "West Bromwich Albion FC"],
    "birmingham": ["Birmingham", "Birmingham City", "Birmingham City FC"],
    "stoke": ["Stoke", "Stoke City", "Stoke City FC"],
    "swansea": ["Swansea", "Swansea City", "Swansea City AFC"],
    "blackburn": ["Blackburn", "Blackburn Rovers", "Blackburn Rovers FC"],
    "derby": ["Derby", "Derby County", "Derby County FC"],
    "sheffield-wednesday": ["Sheffield Wednesday", "Sheffield Wednesday FC"],
    "qpr": ["QPR", "Queens Park Rangers", "Queens Park Rangers FC"],
    "bristol-city": ["Bristol City", "Bristol City FC"],
    "wrexham": ["Wrexham", "Wrexham AFC"],
    "millwall": ["Millwall", "Millwall FC"],
    "preston": ["Preston", "Preston North End", "Preston North End FC"],
}
LOOKUP = {name.casefold(): club for club, names in ALIASES.items() for name in names}


def canonical_club(name):
    club = LOOKUP.get(name.strip().casefold())
    if club is None:
        raise ValueError(f"Unmapped club: {name!r}. Add an explicit verified alias in league/real_data.py; no fuzzy merge performed.")
    return club


def real_matches(db, source_map=None):
    seasons = list(db.scalars(select(Season).where(Season.provider.in_(REAL_PROVIDERS))))
    available = {(s.year, s.provider): s for s in seasons}
    if source_map is None:
        # Stable ownership: prevents overlapping providers from doubling a season.
        source_map = {str(year): ("api-football" if year <= 2024 else "football-data" if year == 2025 else "bigballs")
                      for year in sorted({s.year for s in seasons})}
        source_map = {year: source for year, source in source_map.items() if (int(year), source) in available}
    chosen = []
    for year, source in source_map.items():
        if source not in REAL_PROVIDERS or (int(year), source) not in available:
            raise ValueError("A model's recorded season source is missing; reimport it before forecasting.")
        chosen.append(available[(int(year), source)])
    if not chosen:
        raise ValueError("Import real seasons before training.")
    year_by_id = {s.id: s.year for s in chosen}
    rows = list(db.scalars(select(Match).where(Match.season_id.in_(year_by_id)).order_by(Match.kickoff, Match.id)))
    teams = {t.id: t for t in db.scalars(select(Team))}
    mapped, per_source = {}, {}
    for row in rows:
        for tid in (row.home_id, row.away_id):
            team = teams[tid]
            if team.provider != row.provider:
                raise ValueError("Match and club provider identities disagree.")
            club = canonical_club(team.name)
            key = (team.provider, club)
            if key in per_source and per_source[key] != tid:
                raise ValueError("Two provider club IDs resolve to the same club; review identities first.")
            per_source[key] = tid
            mapped[tid] = club
    detached, seen = [], set()
    for row in rows:
        home, away = mapped[row.home_id], mapped[row.away_id]
        identity = (year_by_id[row.season_id], home, away)
        if home == away or identity in seen:
            raise ValueError("Duplicate or invalid fixture in combined real data.")
        seen.add(identity)
        detached.append(SimpleNamespace(id=row.id, season_id=row.season_id, provider=row.provider,
            home_id=home, away_id=away, home_score=row.home_score, away_score=row.away_score,
            kickoff=row.kickoff, status=row.status))
    return detached, year_by_id, source_map


def require_complete_season(matches, years, year):
    rows = [m for m in matches if years[m.season_id] == year and m.status in FINISHED]
    appearances = Counter(t for m in rows for t in (m.home_id, m.away_id))
    if len(rows) != 380 or len(appearances) != 20 or set(appearances.values()) != {38}:
        raise ValueError(f"Season {year}/{year+1} is incomplete: need 380 results, 20 clubs and 38 games per club.")
