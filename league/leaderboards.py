"""Bounded, atomic imports of provider player leaderboards. Never fills missing stats."""
from datetime import datetime
from sqlalchemy import select
from check_api_football import APIError
from .importer import positive_id, score
from .storage import Season, PlayerLeaderboard, SyncRun, utcnow


def name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError("Missing or invalid player/club name.")
    return value.strip()


def normalize(body, provider, year, metric):
    """Return display-only aggregates; never join player identities across providers."""
    rows = []
    seen = set()
    try:
        if provider == 'football-data':
            if body['competition']['id'] != 2021 or body['competition']['code'] != 'PL' or datetime.fromisoformat(body['season']['startDate']).year != year:
                raise ValueError('Scorers response is for another league or season.')
            entries = body['scorers']
            coverage = ('Goals from the provider scorer list (up to 100 players).' if metric == 'goals' else
                        'Assists among the imported scorer list only. This is not a league-wide assists ranking.')
        elif provider == 'bigballs':
            if str(body['meta']['season']) != str(year) or body['meta']['league'].lower() != 'epl':
                raise ValueError('Leaderboard response is for another league or season.')
            entries = body['data']
            coverage = f'Provider {metric} leaderboard, up to 100 players; not a full league roster.'
        elif provider == 'api-football':
            entries = body['response']
            coverage = f'API-Football top {metric} list, up to 20 players; not a full league roster.'
        else:
            raise ValueError('Unsupported leaderboard provider.')
        if not isinstance(entries, list) or not entries or len(entries) > 100:
            raise ValueError('Empty or invalid leaderboard; previous data preserved.')
        for entry in entries:
            if provider == 'football-data':
                identity = positive_id(entry['player']['id'])
                player_name = name(entry['player']['name'])
                clubs = [name(entry['team']['name'])]
                value = score(entry.get(metric))
                incomplete = False
            elif provider == 'bigballs':
                identity = entry.get('id')
                player_name = name(entry['player_name'])
                clubs = [name(entry['team'])]
                value = score(entry.get(metric))
                incomplete = False
            else:
                identity = positive_id(entry['player']['id'])
                player_name = name(entry['player']['name'])
                stats = entry['statistics']
                if not stats or any(s['league']['id'] != 39 or s['league']['season'] != year for s in stats):
                    raise ValueError('Player statistics belong to another league or season.')
                clubs = [name(s['team']['name']) for s in stats]
                if len(set(s['team']['id'] for s in stats)) != len(stats):
                    raise ValueError('Duplicate player club spell in leaderboard.')
                values = [score(s['goals'].get('total' if metric == 'goals' else 'assists')) for s in stats]
                known = [v for v in values if v is not None]
                value = sum(known) if known else None
                incomplete = len(known) != len(values)
            if identity is not None:
                if identity in seen:
                    raise ValueError('Duplicate player identifier in leaderboard.')
                seen.add(identity)
            if value is not None:
                rows.append(dict(name=player_name, clubs=clubs, value=value, incomplete=incomplete))
        if not rows:
            raise ValueError(f'No known {metric} values returned; previous data preserved.')
        return sorted(rows, key=lambda r: (-r['value'], r['name'])), coverage
    except (KeyError, TypeError, AttributeError):
        raise ValueError('Leaderboard response is missing required fields; previous data preserved.') from None


def import_board(factory, client, provider, year, metric, body=None):
    if metric not in {'goals', 'assists'}:
        raise ValueError('Choose goals or assists.')
    with factory.begin() as db:
        season = db.scalar(select(Season).where(Season.provider == provider, Season.year == year))
        if season is None:
            raise ValueError('Import this real fixture season first.')
        sid = season.id
        run = SyncRun(year=year, kind=f'leaders-{provider}', status='running', detail=metric)
        db.add(run)
        db.flush()
        rid = run.id
    try:
        if body is None:
            if provider == 'football-data':
                body = client.scorers(year)
            elif provider == 'bigballs':
                body = client.get(endpoint='leagues/epl/top-scorers', season=year, category=metric, limit=100)
            else:
                endpoint = 'players/topscorers' if metric == 'goals' else 'players/topassists'
                body = client.get(endpoint, league=39, season=year)
        rows, coverage = normalize(body, provider, year, metric)
        with factory.begin() as db:
            board = db.scalar(select(PlayerLeaderboard).where(PlayerLeaderboard.season_id == sid, PlayerLeaderboard.metric == metric))
            if board is None:
                board = PlayerLeaderboard(season_id=sid, metric=metric)
                db.add(board)
            board.rows, board.coverage, board.imported_at = rows, coverage, utcnow()
            run = db.get(SyncRun, rid)
            run.status, run.count, run.ended_at = 'success', len(rows), utcnow()
        return len(rows)
    except Exception:
        with factory.begin() as db:
            run = db.get(SyncRun, rid)
            run.status, run.ended_at = 'failed', utcnow()
            run.detail = f'{metric} refresh failed; previous leaderboard preserved. See terminal.'
        raise


def sync_leaders(factory, clients, emit=print):
    failures = 0
    for provider, year in [('api-football', 2024), ('football-data', 2025), ('bigballs', 2026)]:
        body = None
        try:
            client = clients[provider]()
            if provider == 'football-data':
                body = client.scorers(year)  # One request supplies both subset boards.
        except (APIError, ValueError) as exc:
            emit(f'{year}/{year+1} {provider}: FAILED: {exc}')
            failures += 1
            continue
        for metric in ('goals', 'assists'):
            try:
                count = import_board(factory, client, provider, year, metric, body)
                emit(f'{year}/{year+1} {provider}: {count} {metric} leaderboard entries imported.')
            except (APIError, ValueError) as exc:
                emit(f'{year}/{year+1} {provider} {metric}: FAILED: {exc}')
                failures += 1
    return failures
