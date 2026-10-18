"""Small, strict user configuration. No model releases or brand data in defaults."""
import copy
import json
import os
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    pass


def profiles(tier):
    return [{'provider': 'codex', 'model': f'auto:{tier}'},
            {'provider': 'claude', 'model': f'auto:{tier}'}]


DEFAULTS = {
    'website': '', 'products': [], 'concept': '', 'count': 1,
    'brand': {'name': '', 'direction': '', 'documents': []},
    'sources': {'assets': [], 'scripts': [], 'inspiration': [], 'characters': []},
    # min/max 0 = derive an accepted range around the target (80-130 %).
    'output': {'width': 1080, 'height': 1350, 'fps': 24, 'target_seconds': 10,
               'min_seconds': 0, 'max_seconds': 0, 'cta': True, 'folder': '',
               # Frame writes the end text. end_card: the last seconds become a Frame card
               # (title, picture, link); full: the whole ad is framed like a Frame post.
               'frame': 'end_card', 'end_card_seconds': 2.5,
               # Frame's treatment of picture and text: clean, or ps1 (late-90s console crunch).
               'look': 'clean', 'loudness': -14},
    # Faster/cheaper routes are a last resort for hung research or writing sessions.
    'workers': {'researcher': profiles('economy'),
                'writer': profiles('balanced'),
                'critic': profiles('economy'), 'selector': profiles('balanced'),
                'producer': profiles('balanced'),
                'animator': [{'provider': 'claude', 'model': 'opus'},
                             {'provider': 'codex', 'model': 'auto:quality'}],
                'director': profiles('balanced'),
                'editor': profiles('balanced'),
                'reviewer': profiles('economy')},
    'limits': {'timeout_seconds': 3600, 'production_timeout_seconds': 14400,
               'quick_timeout_seconds': 600, 'review_timeout_seconds': 900,
               'idle_timeout_seconds': 300,
               'repairs': 1, 'board_repairs': 4, 'provider_cooldown_seconds': 3600, 'log_mb': 32},
    # No default voice: the director casts every speaker (a default once voiced a man as af_heart).
    'audio': {'python': '', 'voice_provider': 'kokoro', 'voice': '', 'asr_model': 'openai/whisper-small.en',
              'effects_provider': '', 'music': [], 'allow_piper_fallback': False},
    'delivery': {'drive': ''},  # optional rclone remote path; empty = local-only
    'tools': {'blender': 'blender', 'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe',
              'frame_root': '', 'frame_python': ''},
}


def merge(base, incoming, prefix=''):
    if not isinstance(incoming, dict):
        raise ConfigError(f'{prefix or "config"} must be an object')
    for k, v in incoming.items():
        if k not in base:
            raise ConfigError(f'Unknown setting: {prefix}{k}')
        if isinstance(base[k], dict):
            merge(base[k], v, prefix + k + '.')
        else:
            base[k] = v


def website(value):
    if not isinstance(value, str):
        raise ConfigError('website must be a string')
    if not value:
        return ''
    value = value if '://' in value else 'https://' + value
    u = urlparse(value)
    if u.scheme not in ('https', 'http') or not u.hostname or u.username or u.password:
        raise ConfigError('website must be an HTTP(S) domain or URL without credentials')
    return value.rstrip('/')


def load_config(path=None, overrides=None):
    c = copy.deepcopy(DEFAULTS)
    base = Path.cwd()
    if path:
        p = Path(path).expanduser().resolve(); base = p.parent
        try:
            merge(c, json.loads(p.read_text()))
        except (OSError, ValueError) as e:
            raise ConfigError(f'{p}: {e}') from e
    if overrides:
        merge(c, overrides)
    c['website'] = website(c['website'])
    for key in ('concept',):
        if not isinstance(c[key], str):
            raise ConfigError(f'{key} must be text')
    if type(c['count']) is not int or not 1 <= c['count'] <= 50:
        raise ConfigError('count must be an integer from 1 to 50')
    if not isinstance(c['products'], list):
        raise ConfigError('products must be a list')
    for product in c['products']:
        if not isinstance(product, dict) or set(product) - {'name', 'description', 'url'}:
            raise ConfigError('products use name, description, and optional url')
        for key in ('name', 'description'):
            if not isinstance(product.get(key), str) or not product[key].strip():
                raise ConfigError(f'each product needs {key}')
        if 'url' in product:
            product['url'] = website(product['url'])
    for key, value in c['limits'].items():
        if type(value) is not int or not (0 if key in ('repairs', 'board_repairs') else 1) <= value <= 86400:
            raise ConfigError(f'limits.{key} is out of range')
    if not isinstance(c['delivery']['drive'], str):
        raise ConfigError('delivery.drive must be an rclone destination string')
    o = c['output']
    for key in ('width', 'height', 'fps', 'target_seconds', 'min_seconds', 'max_seconds'):
        if type(o[key]) is not int or o[key] < (0 if key.endswith(('min_seconds', 'max_seconds')) else 1):
            raise ConfigError(f'output.{key} must be a positive integer')
    o['min_seconds'] = o['min_seconds'] or max(1, round(o['target_seconds'] * .8))
    o['max_seconds'] = o['max_seconds'] or round(o['target_seconds'] * 1.3)
    if not o['min_seconds'] <= o['target_seconds'] <= o['max_seconds']:
        raise ConfigError('output.target_seconds must lie between min_seconds and max_seconds')
    if any(o[k] % 2 or not 64 <= o[k] <= 4096 for k in ('width', 'height')):
        raise ConfigError('output dimensions must be even and between 64 and 4096')
    if o['target_seconds'] > 300 or o['max_seconds'] > 390 or o['fps'] > 60:
        raise ConfigError('invalid output duration or fps')
    if type(o['loudness']) not in (int, float) or not -24 <= o['loudness'] <= -9:
        raise ConfigError('output.loudness is integrated LUFS between -24 and -9 (social video: -14)')
    if not isinstance(c['audio']['asr_model'], str) or not c['audio']['asr_model']:
        raise ConfigError('audio.asr_model must name a Hugging Face speech-recognition model')
    if o['look'] not in ('clean', 'ps1'):
        raise ConfigError('output.look must be clean or ps1')
    if o['frame'] not in ('end_card', 'full'):
        raise ConfigError('output.frame must be end_card or full')
    if type(o['end_card_seconds']) not in (int, float) or not 0.5 <= o['end_card_seconds'] <= 30:
        raise ConfigError('output.end_card_seconds must be from 0.5 to 30 (capped at half the ad)')
    if type(o['cta']) is not bool or type(c['audio']['allow_piper_fallback']) is not bool:
        raise ConfigError('cta and allow_piper_fallback must be booleans')
    for role, routes in c['workers'].items():
        if not isinstance(routes, list) or not routes:
            raise ConfigError(f'workers.{role} needs at least one profile')
        for p in routes:
            if not isinstance(p, dict) or set(p) - {'provider', 'model', 'effort'}:
                raise ConfigError('worker profiles use provider, model, optional effort')
            if p.get('provider') not in ('codex', 'claude') or not isinstance(p.get('model'), str) or not p['model']:
                raise ConfigError('worker profiles need codex/claude and a model selector')
    def local(value):
        if not isinstance(value, str):
            raise ConfigError('source paths must be strings')
        if value.startswith(('https://', 'http://')):
            return value
        p = Path(value).expanduser()
        return str((base / p).resolve()) if value else ''
    for group, key in [('brand', 'documents'), ('sources', 'assets'), ('sources', 'scripts'),
                       ('sources', 'inspiration'), ('sources', 'characters'), ('audio', 'music')]:
        values = c[group][key]
        if not isinstance(values, list):
            raise ConfigError(f'{group}.{key} must be a list')
        c[group][key] = [local(v) for v in values]
    for group, keys in [('brand', ('name', 'direction')), ('audio', ('voice_provider', 'voice', 'effects_provider')),
                        ('tools', ('blender', 'ffmpeg', 'ffprobe'))]:
        for key in keys:
            if not isinstance(c[group][key], str):
                raise ConfigError(f'{group}.{key} must be text')
    for group, key in [('audio', 'python'), ('tools', 'frame_root'), ('tools', 'frame_python'), ('output', 'folder')]:
        value = c[group][key]
        if not isinstance(value, str):
            raise ConfigError(f'{group}.{key} must be a path string')
        # Resolving a venv Python symlink selects the base interpreter and loses its packages.
        c[group][key] = os.path.abspath(base / Path(value).expanduser()) if value else ''
    return c
