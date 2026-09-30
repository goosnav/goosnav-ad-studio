"""SHOW AND TELL end card: tagline, product still, prices, address (9:16 frame, 4:5-safe band)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw
from studio import config, typeset
out = config.path('work', 'show_and_tell', 'lpv', 'ov'); out.mkdir(parents=True, exist_ok=True)
W, H = 1080, 1920
im = Image.new('RGBA', (W, H), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
fh = config.font('font_sans_bold', 60); fl = config.font('font_sans', 42); fu = config.font('font_serif', 44)
def centre(y, text, f, fill=(0, 0, 0, 255)):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)
centre(int(H * 0.25), 'Two of these are for sale.', fh)
prod = Image.open(out / 'products.png').convert('RGB').crop((230, 330, 1130, 790))
prod = prod.resize((int(W * 0.86), int(W * 0.86 * prod.height / prod.width)), Image.LANCZOS)
im.paste(prod, ((W - prod.width) // 2, int(H * 0.32)))
y = int(H * 0.32) + prod.height + 40
centre(y, 'Goosnav Book 2. $19.95.', fl); centre(y + 62, 'Goosklerf. From $13.95.', fl)
url = 'www.goosnav.shop'
typeset.underline_text(d, ((W - d.textlength(url, font=fu)) / 2, int(H * 0.72)), url, fu, typeset.LINK_BLUE + (255,), 3)
im.save(out / 'ov_end.png')
# the flash when the bomb goes off
Image.new('RGBA', (W, H), (255, 250, 235, 255)).save(out / 'ov_flash.png')
print(out)
