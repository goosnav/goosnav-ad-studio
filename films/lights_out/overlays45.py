"""Type for LIGHTS OUT 4:5 (1080x1350). All type between 12% and 88% of the height (162..1188 px)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
W, H = 1080, 1350
OUT = '/home/goosnav/goosnav-sessions/B_how_it_is_made/ov45/'
SANS = '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'
SANS_R = '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'
TIMES = '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf'
LINK_BLUE = (0, 0, 238)
os.makedirs(OUT, exist_ok=True)
X = 80
def shadowed(lines, path, x, y, gaps):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); ds = ImageDraw.Draw(sh); yy = y
    for (text, f), g in zip(lines, gaps):
        ds.text((x + 2, yy + 3), text, font=f, fill=(0, 0, 0, 170)); d.text((x, yy), text, font=f, fill=(255, 255, 255, 255))
        bottom = yy + f.getbbox(text)[3]; assert 162 <= yy and bottom <= 1188, (text, yy, bottom)
        assert x + d.textlength(text, font=f) <= W - 60, text
        yy += g
    sh = sh.filter(ImageFilter.GaussianBlur(6)); sh.alpha_composite(im); sh.save(path)
shadowed([('LIGHTS OUT', ImageFont.truetype(SANS, 80)), ('A Goosnav industrial film', ImageFont.truetype(SANS_R, 36))],
         OUT + 'title.png', X, 1040, [92, 0])
f = ImageFont.truetype(SANS, 44)
rows = [['Goosnav Book 2. $19.95.'], ['Goosklerf. Packs $13.95.', 'Kits from $29.95.'], ['The Patreon. $3 a month.']]
y = 200
for i, r in enumerate(rows):
    shadowed([(t, f) for t in r], OUT + 'price%d.png' % i, X, y, [58] * len(r))
    y += 58 * len(r) + 6
im = Image.new('RGBA', (W, H), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
f = ImageFont.truetype(SANS, 50)
for j, line in enumerate(['Made at the', 'Goosnav works.']):
    tw = d.textlength(line, font=f); d.text(((W - tw) / 2, H * 0.38 + j * 64), line, font=f, fill=(0, 0, 0, 255))
fl = ImageFont.truetype(TIMES, 44)
y = 1188 - 2 * 60
for url in ['www.goosnav.shop', 'www.patreon.com/goosnav']:
    d.text((X, y), url, font=fl, fill=LINK_BLUE + (255,)); w = d.textlength(url, font=fl)
    asc, desc = fl.getmetrics(); d.line([(X, y + asc + 5), (X + w, y + asc + 5)], fill=LINK_BLUE + (255,), width=3)
    assert y + asc + 8 <= 1188
    y += 60
im.save(OUT + 'end.png'); print('ov45 ok')
