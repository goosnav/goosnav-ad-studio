"""THE LONGEST TURN: overlays for any format -> <work>/the_longest_turn/<fmt>/ov/
Title, war-documentary chyrons (Helvetica, bottom left), product lines, the white end card."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw, ImageFilter
from studio import config, typeset

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='4x5'); a = ap.parse_args()
W, H, _ = config.FORMATS[a.format]
out = config.path('work', 'the_longest_turn', a.format, 'ov'); out.mkdir(parents=True, exist_ok=True)
s, m = typeset.metrics(W, H)

def shadowed(path, radius=10, strength=0.75):
    """soft drop shadow from the overlay's own alpha, so white type holds over a busy picture"""
    im = Image.open(path).convert('RGBA')
    a = im.split()[3].filter(ImageFilter.GaussianBlur(radius * s)).point(lambda v: int(v * strength))
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); sh.putalpha(a)
    sh = Image.alpha_composite(Image.new('RGBA', im.size, (0, 0, 0, 0)), sh)
    Image.alpha_composite(sh, im).save(path)

def chyron(name, main, sub=None, size=46):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fb = config.font('font_sans_bold', int(size * s)); fr = config.font('font_sans', int(30 * s))
    y = H - int(0.12 * H) - (int(44 * s) if sub else 0)
    d.rectangle([m, y - int(16 * s), m + int(56 * s), y - int(12 * s)], fill=(255, 255, 255, 255))
    d.text((m, y), main, font=fb, fill=(255, 255, 255, 255))
    if sub:
        d.text((m, y + int(size * 1.25 * s)), sub, font=fr, fill=(255, 255, 255, 230))
    im.save(out / f'{name}.png')
    shadowed(out / f'{name}.png', 8, 0.6)

chyron('ov_title', 'THE LONGEST TURN', 'A Goosklerf game, in full.', size=52)
chyron('ov_2114', '21:14', 'The fortresses go up.')
chyron('ov_2120', '21:20', 'The dice come down.')
chyron('ov_2131', '21:31', 'A five.')
chyron('ov_book', 'Goosnav Book 2', 'The history of all of it. Hardcover.')
chyron('ov_patreon', 'The Patreon', 'Dispatches, monthly.')
lines = ['Goosklerf. Packs $13.95.', 'Kits $29.95 to $89.95.', 'Goosnav Book 2. $19.95.', 'The Patreon. $3 a month.']
typeset.lines_overlay(W, H, lines, out / 'ov_lines.png', url='www.goosnav.shop')
shadowed(out / 'ov_lines.png', 12, 0.85)
typeset.end_card(W, H, out / 'ov_end.png', 'Your roll.', ['www.goosnav.shop', 'www.patreon.com/goosnav'])
print('overlays ->', out)
