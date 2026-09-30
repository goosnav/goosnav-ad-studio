"""Two-product white end card for Three Brags."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from studio import config
from studio.typeset import underline_text

FILM = 'three_brags'
WIDTH, HEIGHT = 1080, 1350
output = config.path('work', FILM, '4x5', 'ov')
output.mkdir(parents=True, exist_ok=True)
textures = config.textures()
canvas = Image.new('RGBA', (WIDTH, HEIGHT), (255, 255, 255, 255))
draw = ImageDraw.Draw(canvas)
headline_font = config.font('font_sans_bold', 74)
label_font = config.font('font_sans_bold', 43)
small_font = config.font('font_sans', 34)
url_font = config.font('font_serif', 47)

draw.text((94, 92), 'GOOSNAV', font=small_font, fill=(0, 0, 0))
draw.line((94, 160, 986, 160), fill=(12, 12, 12), width=3)
draw.text((94, 210), 'TWO OF THESE', font=headline_font, fill=(0, 0, 0))
draw.text((94, 292), 'ARE FOR SALE.', font=headline_font, fill=(0, 0, 0))

products = [
    ('book_front.png', 'BOOK TWO', '$19.95', (110, 460, 395, 410)),
    ('pack_front.png', 'GOOSKLERF', '$13.95', (590, 438, 365, 455)),
]
for filename, title, price, region in products:
    source = Image.open(textures / filename).convert('RGB')
    x_pos, y_pos, max_width, max_height = region
    source = ImageOps.contain(source, (max_width, max_height), Image.Resampling.LANCZOS)
    x_pos += (max_width - source.width) // 2
    y_pos += (max_height - source.height) // 2
    canvas.paste(source, (x_pos, y_pos))
    label_x = 94 if filename.startswith('book') else 565
    draw.text((label_x, 940), title, font=label_font, fill=(0, 0, 0))
    draw.text((label_x, 1000), price, font=label_font, fill=(0, 0, 0))

draw.line((94, 1100, 986, 1100), fill=(190, 190, 190), width=2)
underline_text(draw, (94, 1188), 'www.goosnav.shop', url_font, (0, 0, 238), 3)
canvas.save(output / 'ov_end.png')
canvas.convert('RGB').save(output / 'end_card.jpg', quality=95)
captions = {
    '01': ['I have a Goosklerf', 'training card deck.'],
    '02': ['Well, I have a Goosnav book.'],
    '03': ['Well, I have a bomb.'],
}
caption_font = config.font('font_sans_bold', 49)
for number, words in captions.items():
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    caption_draw = ImageDraw.Draw(overlay)
    start_y = 1120 - 29 * (len(words) - 1)
    for line_index, line in enumerate(words):
        line_width = caption_draw.textlength(line, font=caption_font)
        caption_draw.text(((WIDTH - line_width) / 2, start_y + line_index * 57), line,
                          font=caption_font, fill=(255, 255, 255, 255),
                          stroke_width=3, stroke_fill=(18, 18, 18, 255))
    overlay.save(output / f'ov_{number}.png')
print(output / 'ov_end.png')
