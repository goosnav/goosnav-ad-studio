"""contact sheet: python3 sheet.py out.jpg tag t1 t2 ... (reads prev/<tag>_<t>.png)"""
import sys
from PIL import Image, ImageDraw
out, tag, ts = sys.argv[1], sys.argv[2], sys.argv[3:]
cols = 3 if len(ts) > 4 else 2
w, h = 640, 360
rows = (len(ts) + cols - 1) // cols
s = Image.new('RGB', (cols * w, rows * h))
d = ImageDraw.Draw(s)
for i, t in enumerate(ts):
    im = Image.open('prev/%s_%06.2f.png' % (tag, float(t))).convert('RGB').resize((w, h))
    s.paste(im, ((i % cols) * w, (i // cols) * h))
    d.text(((i % cols) * w + 6, (i // cols) * h + 4), t, fill=(255, 255, 0))
s.save(out)
