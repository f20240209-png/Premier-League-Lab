"""Build dated EPL valuation examples from the published Transfermarkt dataset."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import time
import requests
import pandas as pd
import numpy as np

SOURCE_URL = 'https://github.com/dcaribou/transfermarkt-datasets'
DATA_URL = 'https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data'
FILES = {
    'players': ['player_id', 'name', 'date_of_birth', 'position'],
    'games': ['game_id', 'competition_id', 'season', 'date'],
    'appearances': ['game_id', 'player_id', 'goals', 'assists', 'minutes_played'],
    'player_valuations': ['player_id', 'date', 'market_value_in_eur'],
}
POSITIONS = ['Attack', 'Defender', 'Goalkeeper', 'Midfield']


def download_source(folder, refresh=False, emit=print):
    """Four public files, bounded downloads, atomic per-file replacement. No API keys."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for table in FILES:
        target = folder / f'{table}.csv.gz'
        if target.exists() and not refresh:
            emit(f'Using cached {target.name}', flush=True)
            continue
        partial = target.with_suffix('.part')
        emit(f'Downloading {target.name} …', flush=True)
        try:
            started, size = time.monotonic(), 0
            with requests.get(f'{DATA_URL}/{target.name}', stream=True,
                              timeout=(45, 45), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError(f'Dataset download returned HTTP {response.status_code}. Try again later or supply local CSV files.')
                with partial.open('wb') as out:
                    for chunk in response.iter_content(1024 * 1024):
                        size += len(chunk)
                        if size > 150 * 1024 * 1024 or time.monotonic() - started > 300:
                            raise ValueError('Dataset download exceeded its size/time limit.')
                        out.write(chunk)
            # Validate gzip trailer/CRC, including the final chunk, before replacement.
            with gzip.open(partial, 'rb') as stream:
                while stream.read(1024 * 1024):
                    pass
            # Verify required columns before replacing an existing cached file.
            pd.read_csv(partial, compression='gzip', usecols=FILES[table], nrows=1)
            partial.replace(target)
        except (requests.RequestException, EOFError, gzip.BadGzipFile):
            raise ValueError('Public dataset download failed. Retry later or use --source-dir with the four downloaded CSV files.') from None
        finally:
            partial.unlink(missing_ok=True)
    return folder


def file_path(folder, table):
    for suffix in ('.csv.gz', '.csv'):
        path = Path(folder) / (table + suffix)
        if path.is_file():
            return path
    raise ValueError(f'Missing {table}.csv or {table}.csv.gz in the source folder.')


def load_source(folder):
    frames, hashes = {}, {}
    for table, columns in FILES.items():
        path = file_path(folder, table)
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        hashes[table] = digest.hexdigest()
        try:
            frames[table] = pd.read_csv(path, usecols=columns)
        except (EOFError, gzip.BadGzipFile, pd.errors.ParserError):
            raise ValueError(f'{path.name} is incomplete or invalid. Download it again with --refresh.') from None
    return frames, hashes


def _dates(series):
    return pd.to_datetime(series, format='mixed', errors='coerce', utc=True).dt.tz_localize(None).dt.normalize()


def build_dataset(frames, first_season=2021, last_season=2025):
    """One player-season example, first post-season valuation within 75 days.

    Entire EPL season must contain 380 games. All appearance dates precede the
    label date. Latest/current market value and club membership are never used.
    """
    if not 1995 <= first_season < last_season <= 2100:
        raise ValueError('Supply at least two EPL seasons, using start years.')
    p, g, a, v = (frames[k][FILES[k]].copy() for k in FILES)
    for frame, keys in [(p,['player_id']), (g,['game_id']), (a,['game_id','player_id']), (v,['player_id','date'])]:
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise ValueError('Source has missing or duplicate identifiers; import refused.')
    g['date'] = _dates(g['date'])
    g['season'] = pd.to_numeric(g['season'], errors='coerce')
    g = g[(g.competition_id == 'GB1') & g.season.between(first_season, last_season)].copy()
    if g.empty or g['date'].isna().any():
        raise ValueError('No valid EPL seasons found in the dataset.')
    season_sizes = g.groupby('season').size()
    complete = [int(y) for y,n in season_sizes.items() if n == 380]
    g = g[g.season.isin(complete)]
    if len(complete) < 2:
        raise ValueError('Need at least two complete EPL seasons (380 matches each).')
    joined = a.merge(g[['game_id','season','date']], on='game_id', how='inner', validate='many_to_one')
    stat_columns = ['goals','assists','minutes_played']
    for col in stat_columns:
        joined[col] = pd.to_numeric(joined[col], errors='coerce')
        valid = np.isfinite(joined[col]) & (joined[col] >= 0) & (joined[col] % 1 == 0)
        joined.loc[~valid, col] = np.nan
    joined.loc[joined.minutes_played > 130, 'minutes_played'] = np.nan
    # Exclude an entire player-season if any contributing appearance stat is missing.
    joined['missing'] = joined[stat_columns].isna().any(axis=1)
    agg = joined.groupby(['player_id','season'], as_index=False).agg(
        goals=('goals','sum'), assists=('assists','sum'), minutes=('minutes_played','sum'),
        appearance_count=('game_id','count'), stats_through=('date','max'), missing=('missing','any'))
    eligible = agg[(~agg.missing) & (agg.minutes >= 450) & (agg.minutes <= 5000)].copy()
    p['date_of_birth'] = _dates(p.date_of_birth)
    eligible = eligible.merge(p, on='player_id', how='inner', validate='many_to_one')
    eligible = eligible[eligible.position.isin(POSITIONS) & eligible.name.notna() & eligible.date_of_birth.notna()]
    v['date'] = _dates(v['date'])
    v['market_value_in_eur'] = pd.to_numeric(v.market_value_in_eur, errors='coerce')
    v = v[v.date.notna() & np.isfinite(v.market_value_in_eur) & (v.market_value_in_eur > 0)]
    rows = []
    coverage = {}
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    for year in sorted(complete):
        season_end = g.loc[g.season == year, 'date'].max()
        label_end = min(season_end + pd.Timedelta(days=75), pd.Timestamp(year+1, 8, 1), today)
        labels = v[(v.date > season_end) & (v.date <= label_end)].sort_values('date').drop_duplicates('player_id', keep='first')
        group = eligible[eligible.season == year].merge(labels, on='player_id', validate='one_to_one')
        group['age'] = (group.date - group.date_of_birth).dt.days / 365.2425
        group = group[group.age.between(16,45) & (group.stats_through < group.date)].copy()
        group = group.rename(columns={'date':'valuation_date','market_value_in_eur':'actual_eur'})
        coverage[str(year)] = {'games':380, 'player_seasons':int((agg.season == year).sum()),
                              'eligible_stats':int((eligible.season == year).sum()), 'labelled':len(group),
                              'season_end':str(season_end.date()), 'label_window_end':str(label_end.date())}
        rows.append(group)
    result = pd.concat(rows, ignore_index=True)
    if result.empty:
        raise ValueError('No eligible post-season valuation records. Previous value model preserved.')
    columns = ['player_id','name','season','goals','assists','minutes','age','position','appearance_count','stats_through','valuation_date','actual_eur']
    result = result[columns].sort_values(['season','name','player_id']).reset_index(drop=True)
    return result, coverage


def prepare_dataset(folder, first_season=2021, last_season=2025):
    frames, hashes = load_source(folder)
    rows, coverage = build_dataset(frames, first_season, last_season)
    manifest = {'source':SOURCE_URL, 'download_base':DATA_URL, 'source_sha256':hashes,
                'prepared_at':datetime.now(timezone.utc).isoformat(), 'coverage':coverage,
                'position_note':'Position is the downloaded profile position, not a dated historical position.',
                'target':'Transfermarkt estimated market value in EUR, not a transfer fee.',
                'eligibility':'At least 450 EPL minutes with complete known goals, assists and minutes. First valuation after final league match, within 75 days and by August 1.',
                'data_note':'Published data is historical and may be incomplete. Dataset updates were paused in July 2026; 2026/27 is not covered.'}
    return rows, manifest


BUNDLED_DIR = Path(__file__).resolve().parent.parent / 'data' / 'player_values'


def export_prepared(source_folder, destination, first_season=2021, last_season=2025):
    rows, manifest = prepare_dataset(source_folder, first_season, last_season)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    csv = rows.to_csv(index=False).encode('utf-8')
    manifest.update(format_version=1, dataset_sha256=hashlib.sha256(csv).hexdigest(),
                    row_count=len(rows), seasons=sorted(int(y) for y in rows.season.unique()))
    (destination / 'epl_values.csv').write_bytes(csv)
    (destination / 'provenance.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return rows, manifest


def load_prepared(folder=BUNDLED_DIR, first_season=2021, last_season=2025):
    """Load the small, reproducible real-data extract bundled with the release."""
    folder = Path(folder)
    raw = (folder / 'epl_values.csv').read_bytes()
    manifest = json.loads((folder / 'provenance.json').read_text(encoding='utf-8'))
    if manifest.get('format_version') != 1 or hashlib.sha256(raw).hexdigest() != manifest.get('dataset_sha256'):
        raise ValueError('Prepared dataset checksum/version mismatch. Restore the bundled data or use --refresh.')
    if not 1995 <= first_season < last_season <= 2100:
        raise ValueError('Supply at least two EPL seasons, using start years.')
    if not {first_season,last_season}.issubset(set(manifest['seasons'])):
        raise ValueError('Requested seasons are not in the bundled snapshot. Use --source-dir or --refresh.')
    rows = pd.read_csv(folder / 'epl_values.csv')
    if len(rows) != manifest['row_count']:
        raise ValueError('Prepared dataset row count mismatch.')
    for key in ['valuation_date','stats_through']:
        rows[key] = _dates(rows[key])
    rows = rows[rows.season.between(first_season,last_season)].copy()
    manifest = dict(manifest, coverage={y:c for y,c in manifest['coverage'].items() if first_season<=int(y)<=last_season})
    return rows, manifest
