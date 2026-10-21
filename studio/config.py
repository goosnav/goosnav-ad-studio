"""Where things live. Nothing in this repo hardcodes a machine path.

Resolution order for every setting:
  1. environment variable (STUDIO_<KEY>, e.g. STUDIO_ASSETS)
  2. studio.local.json in the repo root (gitignored; copy studio.example.json)
  3. a default relative to the repo or the user's home

Works in system Python and inside Blender's bundled Python (no third-party imports).
"""
import json, os, shutil, glob
from pathlib import Path
from harness.resources import default_render_lock

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()

DEFAULTS = {
    'assets': str(REPO / 'assets'),                      # textures/ and sources/ (real art, generic products)
    'work': str(HOME / 'goosnav-studio-work'),           # frames, previews, intermediate audio (large)
    'output': str(REPO / 'output'),                      # finished films, one folder per film
    'cache': str(HOME / '.cache' / 'goosnav-studio'),    # piper venv + voices
    'blender': shutil.which('blender') or 'blender',
    'ffmpeg': shutil.which('ffmpeg') or 'ffmpeg',
    'rclone_remote': 'agent-exchange:',                  # Drive delivery target (root = Agent Exchange folder)
    'rclone_subdir': 'deliverables/claude',
    'local_delivery': '',                                # optional mirror folder for deliveries
    'render_lock': str(default_render_lock()),
    'font_sans_bold': '',                                # auto-discovered when empty
    'font_sans': '',
    'font_serif': '',
}

def _local():
    p = REPO / 'studio.local.json'
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}

_LOCAL = _local()

def get(key):
    env = os.environ.get('STUDIO_' + key.upper())
    if env:
        return os.path.expanduser(env)
    if key in _LOCAL and _LOCAL[key]:
        return os.path.expanduser(str(_LOCAL[key]))
    return DEFAULTS[key]

def path(key, *parts):
    p = Path(get(key)).joinpath(*parts)
    return p

def textures(*parts):
    return path('assets', 'textures', *parts)

def sources(*parts):
    return path('assets', 'sources', *parts)

# ---------------------------------------------------------------- fonts
# Helvetica = system register, Times = document register (Goosnav type system).
_FONT_CANDIDATES = {
    'font_sans_bold': [
        '/System/Library/Fonts/Helvetica.ttc#1',
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf',
        '/usr/share/fonts/type1/urw-base35/NimbusSans-Bold.t1',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
    ],
    'font_sans': [
        '/System/Library/Fonts/Helvetica.ttc#0',
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
        'C:/Windows/Fonts/arial.ttf',
    ],
    'font_serif': [
        '/System/Library/Fonts/Supplemental/Times New Roman.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf',
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf',
        'C:/Windows/Fonts/times.ttf',
    ],
}

def font_spec(key):
    """returns (path, index) for PIL.ImageFont.truetype"""
    v = get(key)
    cands = [v] if v else _FONT_CANDIDATES[key]
    for c in cands:
        p, _, idx = c.partition('#')
        if os.path.exists(p):
            return p, int(idx or 0)
    raise FileNotFoundError(f'no font for {key}; set STUDIO_{key.upper()}')

def font(key, px):
    from PIL import ImageFont
    p, idx = font_spec(key)
    return ImageFont.truetype(p, px, index=idx)

# ---------------------------------------------------------------- tools
def piper():
    p = path('cache', 'venv', 'bin', 'piper')
    if p.exists():
        return str(p)
    return shutil.which('piper') or str(p)

def voice(name):
    return str(path('cache', 'voices', name + '.onnx'))

# ---------------------------------------------------------------- formats
# name: (width, height, lens scale). Blender's sensor_fit AUTO fits the 36 mm sensor to the LARGER
# dimension, so in portrait the horizontal field narrows; the lens scale restores the 16:9
# horizontal framing (0.8 for 4:5) and gives extra headroom/footroom instead.
FORMATS = {
    '16x9': (1920, 1080, 1.0),
    '4x5': (1080, 1350, 0.8),
    '1x1': (1080, 1080, 1.0),
    '9x16': (1080, 1920, 0.72),
    # monumental low-poly vignettes (GLPV-001): render 540x960, upscale exactly 2x to 1080x1920.
    # Lenses are authored directly for this frame (lens scale 1.0).
    'lpv': (540, 960, 1.0),
}

def film_dirs(film, fmt):
    work = path('work', film, fmt)
    out = path('output', film)
    return work, out

def dump():
    keys = list(DEFAULTS)
    return {k: get(k) for k in keys}

if __name__ == '__main__':
    print(json.dumps(dump(), indent=1))
    for k in _FONT_CANDIDATES:
        try:
            print(k, font_spec(k))
        except Exception as e:
            print(k, 'MISSING', e)
