"""Type for LIGHTS OUT: the title, the prices over the dock, the white end card."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W, H = 1920, 1080
OUT = '/home/goosnav/goosnav-sessions/B_how_it_is_made/ov/'
SANS = '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'
SANS_R = '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'
TIMES = '/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf'
LINK_BLUE = (0, 0, 238)
import os; os.makedirs(OUT, exist_ok=True)

def shadowed(lines, path, x, y, gap):
    """white type with a soft dark halo so it holds over any frame"""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im); ds = ImageDraw.Draw(sh)
    yy = y
    for text, f in lines:
        ds.text((x + 2, yy + 3), text, font=f, fill=(0, 0, 0, 170))
        d.text((x, yy), text, font=f, fill=(255, 255, 255, 255))
        yy += gap if isinstance(gap, int) else gap.pop(0)
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    sh.alpha_composite(im)
    sh.save(path)

# title: lower left, like a 1970s sponsored film
shadowed([('LIGHTS OUT', ImageFont.truetype(SANS, 84)), ('A Goosnav industrial film', ImageFont.truetype(SANS_R, 38))],
         OUT + 'title.png', 132, 820, [96, 0])
# prices, one per layer so they can arrive one at a time
f = ImageFont.truetype(SANS, 52)
for i, line in enumerate(['Goosnav Book 2. $19.95.', 'Goosklerf. Packs $13.95. Kits from $29.95.', 'The Patreon. $3 a month.']):
    shadowed([(line, f)], OUT + 'price%d.png' % i, 132, 110 + i * 72, 0)
# end card: white paper, one line, the two addresses as old web links (bottom left)
im = Image.new('RGBA', (W, H), (255, 255, 255, 255))
d = ImageDraw.Draw(im)
f = ImageFont.truetype(SANS, 60)
line = 'Made at the Goosnav works.'
tw = d.textlength(line, font=f)
d.text(((W - tw) / 2, H * 0.40), line, font=f, fill=(0, 0, 0, 255))
fl = ImageFont.truetype(TIMES, 46)
y = H - 132 - 2 * 62
for url in ['www.goosnav.shop', 'www.patreon.com/goosnav']:
    d.text((132, y), url, font=fl, fill=LINK_BLUE + (255,))
    w = d.textlength(url, font=fl)
    asc, desc = fl.getmetrics()
    d.line([(132, y + asc + 5), (132 + w, y + asc + 5)], fill=LINK_BLUE + (255,), width=3)
    y += 62
im.save(OUT + 'end.png')
print('overlays ok')
