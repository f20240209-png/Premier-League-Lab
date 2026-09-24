"""Season-labelled FPL player lists, separate from historical club statistics."""
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import requests
from sqlalchemy import select
from .real_data import LOOKUP
from .storage import SquadSnapshot, utcnow

SOURCE_URL = 'https://fantasy.premierleague.com/api/bootstrap-static/'
BUNDLED = Path(__file__).resolve().parent.parent / 'data' / 'squads' / 'fpl.json'
ALIASES = {**LOOKUP, 'man utd': 'man-united', 'spurs': 'tottenham', "nott'm forest": 'nottingham'}
POSITIONS = {1:'Goalkeeper', 2:'Defender', 3:'Midfielder', 4:'Forward'}
STATUS = {'a':'Available', 'd':'Doubtful', 'i':'Injured', 's':'Suspended', 'u':'Unavailable', 'n':'Not available'}


def normalize_squads(body, fetched_at=None):
    if not isinstance(body, dict):
        raise ValueError('Invalid FPL response; previous squad data preserved.')
    try:
        events = body['events']
        dates = [datetime.fromisoformat(e['deadline_time'].replace('Z','+00:00')) for e in events]
        if len(dates) != 38 or any(d.tzinfo is None for d in dates):
            raise ValueError('FPL season could not be verified.')
        first, last = min(dates), max(dates)
        year = first.year
        if first.month not in (7,8,9) or last.year != year+1 or last.month not in (5,6):
            raise ValueError('Unexpected FPL season dates.')
        clubs, ids = {}, {}
        for t in body['teams']:
            slug = ALIASES.get(t['name'].strip().casefold())
            if slug is None or slug in clubs or type(t['id']) is not int or t['id'] in ids:
                raise ValueError('Unmapped or duplicate FPL club; import refused.')
            ids[t['id']] = slug
            clubs[slug] = {'name':t['name'], 'players':[]}
        if len(clubs) != 20:
            raise ValueError('Expected 20 FPL clubs; previous squad data preserved.')
        seen = set()
        for p in body['elements']:
            pid, code = p['id'], p['code']
            name = (p['first_name']+' '+p['second_name']).strip()
            if type(pid) is not int or pid <= 0 or pid in seen or type(code) is not int or code <= 0 or not name or len(name)>200:
                raise ValueError('Invalid or duplicate FPL player.')
            if p['team'] not in ids or p['element_type'] not in POSITIONS:
                raise ValueError('Unrecognized player club or position.')
            seen.add(pid)
            def count(key):
                v=p.get(key)
                if v is not None and (type(v) is not int or v<0):
                    raise ValueError('Invalid player statistic.')
                return v
            clubs[ids[p['team']]]['players'].append(dict(
                id=pid, code=code, name=name, display_name=p.get('web_name') or name,
                position=POSITIONS[p['element_type']], position_order=p['element_type'],
                status=STATUS.get(p.get('status'),'Not reported'), minutes=count('minutes'), goals=count('goals_scored'),
                photo=f'https://resources.premierleague.com/premierleague/photos/players/110x140/p{code}.png'))
        if not 300 <= len(seen) <= 1500 or any(len(c['players'])<11 for c in clubs.values()):
            raise ValueError('Incomplete FPL player list; previous squad data preserved.')
        for club in clubs.values():
            club['players'].sort(key=lambda p:(p['position_order'],p['name']))
        stamp=fetched_at or utcnow().isoformat()+'Z'
        return dict(version=1,year=year,source='Official Fantasy Premier League player list',source_url=SOURCE_URL,
                    fetched_at=stamp,first_deadline=first.isoformat(),last_deadline=last.isoformat(),clubs=clubs,
                    player_count=len(seen),coverage='FPL-listed players, not a verified official registration list. May include unavailable or recently transferred players. Positions follow FPL categories. Portrait kits may differ from this season.')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('Incomplete FPL response; previous squad data preserved.') from exc


def fetch_squads():
    try:
        response=requests.get(SOURCE_URL,timeout=(5,30),allow_redirects=False)
        response.raise_for_status()
        body=response.json()
    except (requests.RequestException,ValueError):
        raise ValueError('FPL squad request failed; previous squad data preserved.') from None
    return normalize_squads(body)


def sync_squads(factory):
    snapshot=fetch_squads()  # Validate the complete response before writing anything.
    with factory.begin() as db:
        old=db.scalar(select(SquadSnapshot).where(SquadSnapshot.year==snapshot['year']))
        if old is None:
            old=SquadSnapshot(year=snapshot['year'],data=snapshot)
            db.add(old)
        else:
            old.data=snapshot
    return snapshot


@lru_cache(maxsize=1)
def bundled_squads():
    if not BUNDLED.is_file():
        return None
    return json.loads(BUNDLED.read_text(encoding='utf-8'))


def squad_for_club(db, season, team):
    if not season or season.provider=='demo':
        return None
    slug=LOOKUP.get(team.name.strip().casefold())
    if not slug:
        return None
    stored=db.scalar(select(SquadSnapshot).where(SquadSnapshot.year==season.year))
    bundled=bundled_squads()
    choices=[s for s in [stored.data if stored else None,bundled] if s and s['year']==season.year]
    if not choices:
        return None
    data=max(choices,key=lambda s:datetime.fromisoformat(s['fetched_at'].replace('Z','+00:00')))
    club=data['clubs'].get(slug)
    if not club:
        return None
    return {**club, 'year':data['year'], 'source':data['source'], 'coverage':data['coverage'],
            'fetched_at':data['fetched_at'], 'date':data['fetched_at'][:10], 'positions':list(POSITIONS.values())}
