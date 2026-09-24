"""Presentation-only identity lookup. Never changes provider IDs or model data."""
import json
import unicodedata
from pathlib import Path
from flask import url_for
from .real_data import LOOKUP

MEDIA = Path(__file__).resolve().parent.parent / 'static' / 'media'

def normalized(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name or '') if not unicodedata.combining(c)).casefold().strip()

PLAYER_IMAGES = {normalized(k): v for k, v in json.loads((MEDIA / 'players.json').read_text(encoding='utf-8')).items()}
FEATURED = ('Erling Haaland', 'Bryan Mbeumo', 'Bruno Fernandes', 'Harry Maguire', 'Declan Rice')

def club_image(name, provider_logo=None):
    club = LOOKUP.get((name or '').strip().casefold())
    if club and (MEDIA / 'clubs' / f'{club}.png').is_file():
        return url_for('static', filename=f'media/clubs/{club}.png')
    return provider_logo if isinstance(provider_logo, str) and provider_logo.startswith('https://') else None

def player_image(name):
    photo = PLAYER_IMAGES.get(normalized(name))
    if not photo:
        return None
    return url_for('static', filename=f"media/{photo['local']}") if photo['local'] else photo['url']

def featured_players(examples):
    by_name = {normalized(p['name']): p for p in examples}
    return [by_name[normalized(name)] for name in FEATURED if normalized(name) in by_name]


def squad_portrait(photo):
    """Reuse bundled portraits only when the provider photo identifier matches."""
    filename = photo.rsplit('/', 1)[-1]
    for entry in PLAYER_IMAGES.values():
        if entry.get('local') and entry['url'].rsplit('/', 1)[-1] == filename:
            return url_for('static', filename=f"media/{entry['local']}")
    return photo
