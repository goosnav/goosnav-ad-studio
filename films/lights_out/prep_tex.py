"""Generic Goosklerf kit box art: purple board, the flat logo file, Helvetica type. No product photos."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
TEX = '/home/goosnav/goosnav-sessions/B_how_it_is_made/tex/'
SANS = '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'
PURPLE = (51, 0, 114); WHITE = (255, 255, 255)
logo = Image.open(TEX + 'GOOSKLERF.jpg').convert('RGB')
a = np.asarray(logo).astype(int); nw = a.min(axis=2) < 235
ys, xs = np.where(nw); logo = logo.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
# top: 4:3 (0.30 x 0.225 m)
W, H = 2000, 1500
top = Image.new('RGB', (W, H), PURPLE)
L = logo.resize((1100, 1100), Image.LANCZOS)
top.paste(L, (110, (H - 1100) // 2))
d = ImageDraw.Draw(top)
f = ImageFont.truetype(SANS, 128)
d.text((1300, 560), 'Goosklerf', font=f, fill=WHITE)
d.text((1300, 720), 'Game Kit', font=f, fill=WHITE)
top.save(TEX + 'kit_top.png')
side = Image.new('RGB', (2000, 470), PURPLE)
d = ImageDraw.Draw(side)
d.text((90, 150), 'Goosklerf  Game Kit', font=ImageFont.truetype(SANS, 170), fill=WHITE)
side.save(TEX + 'kit_side.png')
print('ok')
