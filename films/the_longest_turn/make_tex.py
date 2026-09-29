"""THE LONGEST TURN: generic textures that don't exist in <assets>/textures yet.
A plain rulebook (owner rule: anything we can't render perfectly is generic Helvetica) and its inner page.

  python3 films/the_longest_turn/make_tex.py      -> <work>/the_longest_turn/tex/
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PIL import Image, ImageDraw
from studio import config

out = config.path('work', 'the_longest_turn', 'tex'); out.mkdir(parents=True, exist_ok=True)
PURPLE = (0x33, 0x00, 0x72)
W, H = 1500, 2100
logo = Image.open(config.path('assets', 'sources', 'GOOSKLERF.jpg')).convert('RGB')

# cover: purple board, the crisp logo, Helvetica "Goosklerf / Rulebook"
im = Image.new('RGB', (W, H), PURPLE)
d = ImageDraw.Draw(im)
lw = 1060
im.paste(logo.resize((lw, lw), Image.LANCZOS), ((W - lw) // 2, 260))
f = config.font('font_sans_bold', 150)
d.text((150, 1470), 'Goosklerf', font=f, fill=(255, 255, 255))
d.text((150, 1640), 'Rulebook', font=f, fill=(255, 255, 255))
im.save(out / 'rulebook_front.png')

# spine and back: plain purple with white type
sp = Image.new('RGB', (240, H), PURPLE)
t = Image.new('RGB', (H, 240), PURPLE)
ImageDraw.Draw(t).text((120, 55), 'Goosklerf Rulebook', font=config.font('font_sans_bold', 110), fill=(255, 255, 255))
sp.paste(t.rotate(-90, expand=True), (0, 0))
sp.save(out / 'rulebook_spine.png')
Image.new('RGB', (W, H), PURPLE).save(out / 'rulebook_back.png')

# inner page: cream paper, Helvetica. Only what is true of the game.
pg = Image.new('RGB', (W, H), (246, 240, 226))
d = ImageDraw.Draw(pg)
d.text((150, 230), 'Goosklerf', font=config.font('font_sans_bold', 120), fill=(20, 20, 20))
fb = config.font('font_sans', 76)
y = 560
for line in ['Roll for combat.', 'Use your items.', 'Shelter in fortresses.', 'Take the fortresses,', 'or take the enemy.']:
    d.text((150, y), line, font=fb, fill=(25, 25, 25)); y += 130
pg.save(out / 'rulebook_page.png')
print('textures ->', out)
