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
    'sources': {'assets': [], 'scripts': [], 'inspiration': []},
    'output': {'width': 1080, 'height': 1350, 'fps': 24, 'min_seconds': 7,
               'max_seconds': 20, 'cta': True},
    'workers': {'researcher': profiles('balanced'), 'writer': profiles('quality'),
                'critic': profiles('economy'), 'selector': profiles('quality'),
                'producer': profiles('balanced'), 'checker': profiles('economy')},
    'limits': {'timeout_seconds': 3600, 'production_timeout_seconds': 14400,
               'repairs': 2, 'provider_cooldown_seconds': 3600, 'log_mb': 32},
    'audio': {'python': '', 'voice_provider': 'kokoro', 'voice': 'af_heart',
              'effects_provider': '', 'music': [], 'allow_piper_fallback': False},
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
        if type(value) is not int or not (0 if key == 'repairs' else 1) <= value <= 86400:
            raise ConfigError(f'limits.{key} is out of range')
    o = c['output']
    for key in ('width', 'height', 'fps', 'min_seconds', 'max_seconds'):
        if type(o[key]) is not int or o[key] <= 0:
            raise ConfigError(f'output.{key} must be a positive integer')
    if any(o[k] % 2 or not 64 <= o[k] <= 4096 for k in ('width', 'height')):
        raise ConfigError('output dimensions must be even and between 64 and 4096')
    if o['min_seconds'] > o['max_seconds'] or o['max_seconds'] > 300 or o['fps'] > 60:
        raise ConfigError('invalid output duration or fps')
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
                       ('sources', 'inspiration'), ('audio', 'music')]:
        values = c[group][key]
        if not isinstance(values, list):
            raise ConfigError(f'{group}.{key} must be a list')
        c[group][key] = [local(v) for v in values]
    for group, keys in [('brand', ('name', 'direction')), ('audio', ('voice_provider', 'voice', 'effects_provider')),
                        ('tools', ('blender', 'ffmpeg', 'ffprobe'))]:
        for key in keys:
            if not isinstance(c[group][key], str):
                raise ConfigError(f'{group}.{key} must be text')
    for group, key in [('audio', 'python'), ('tools', 'frame_root'), ('tools', 'frame_python')]:
        value = c[group][key]
        if not isinstance(value, str):
            raise ConfigError(f'{group}.{key} must be a path string')
        # Resolving a venv Python symlink selects the base interpreter and loses its packages.
        c[group][key] = os.path.abspath(base / Path(value).expanduser()) if value else ''
    return c
