"""studio.typeset: the type layer. Transparent PNG overlays sized for any format.

House rules (Goosnav): Helvetica Bold for product names and prices, stated like measurements.
URLs set as old web links: Times, #0000EE, underlined, bottom left, always with www.
White type over dark/saturated pictures; black type on the white end card.

  python3 -m studio.typeset --format 4x5 --out DIR \
      --lines "Goosnav Book 2. $19.95." "Goosklerf. From $13.95." "The Patreon. $3 a month." \
      --line-url www.goosnav.shop --headline "Goosnav continues." \
      --urls www.goosnav.shop www.patreon.com/goosnav
  -> DIR/ov_lines.png (transparent) and DIR/ov_end.png (opaque white card)
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from studio import config

LINK_BLUE = (0, 0, 238)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

def metrics(W, H):
    s = min(W, H) / 1080.0
    margin = int(0.115 * W) if H > W else int(132 * s)
    return s, margin

def underline_text(d, xy, text, f, fill, width):
    d.text(xy, text, font=f, fill=fill)
    asc, _ = f.getmetrics()
    x, y = xy
    d.line([(x, y + asc + 5 * width / 3), (x + d.textlength(text, font=f), y + asc + 5 * width / 3)], fill=fill, width=width)

def lines_overlay(W, H, lines, out, url=None, color=WHITE, top=None):
    """product lines (Helvetica Bold) top-left, optional URL beneath"""
    s, m = metrics(W, H)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = config.font('font_sans_bold', int(54 * s))
    y = int(top if top is not None else (0.12 * H if H > W else 104 * s))
    for line in lines:
        d.text((m, y), line, font=f, fill=color + (255,))
        y += int(70 * s)
    if url:
        fl = config.font('font_serif', int(44 * s))
        y += int(22 * s)
        underline_text(d, (m, y), url, fl, color + (255,), max(2, int(3 * s)))
    im.save(out)
    return out

def end_card(W, H, out, headline='Goosnav continues.', urls=('www.goosnav.shop', 'www.patreon.com/goosnav')):
    s, m = metrics(W, H)
    im = Image.new('RGBA', (W, H), WHITE + (255,))
    d = ImageDraw.Draw(im)
    if headline:
        f = config.font('font_sans_bold', int(64 * s))
        tw = d.textlength(headline, font=f)
        d.text(((W - tw) / 2, H * 0.40), headline, font=f, fill=BLACK + (255,))
    fl = config.font('font_serif', int(46 * s))
    step = int(62 * s)
    bottom = int(0.085 * W) if H > W else int(132 * s)
    y = H - bottom - len(urls) * step
    for u in urls:
        underline_text(d, (m, y), u, fl, LINK_BLUE + (255,), max(2, int(3 * s)))
        y += step
    im.save(out)
    return out

def title_card(W, H, text, out, color=WHITE, y_frac=0.45, size=64):
    """one centred Helvetica Bold line (use sparingly)"""
    s, _ = metrics(W, H)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = config.font('font_sans_bold', int(size * s))
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, H * y_frac), text, font=f, fill=color + (255,))
    im.save(out)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--format', default='16x9')
    ap.add_argument('--out', required=True)
    ap.add_argument('--lines', nargs='*', default=[])
    ap.add_argument('--line-url', default=None)
    ap.add_argument('--headline', default='Goosnav continues.')
    ap.add_argument('--urls', nargs='*', default=['www.goosnav.shop', 'www.patreon.com/goosnav'])
    a = ap.parse_args()
    W, H, _ = config.FORMATS[a.format]
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    if a.lines:
        print(lines_overlay(W, H, a.lines, o / 'ov_lines.png', url=a.line_url))
    print(end_card(W, H, o / 'ov_end.png', a.headline, a.urls))
