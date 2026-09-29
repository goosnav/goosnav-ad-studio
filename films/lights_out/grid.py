"""grid of preview frames: python3 grid.py dir out_prefix [cols] [w]"""
import sys, glob, os
from PIL import Image, ImageDraw
d, pre = sys.argv[1], sys.argv[2]
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 6
w = int(sys.argv[4]) if len(sys.argv) > 4 else 320
h = w * 9 // 16
fs = sorted(glob.glob(d + '/f_*.png'))
per = cols * 6
for p in range(0, len(fs), per):
    chunk = fs[p:p + per]
    rows = (len(chunk) + cols - 1) // cols
    s = Image.new('RGB', (cols * w, rows * h))
    dr = ImageDraw.Draw(s)
    for i, f in enumerate(chunk):
        im = Image.open(f).convert('RGB').resize((w, h))
        x, y = (i % cols) * w, (i // cols) * h
        s.paste(im, (x, y))
        fr = int(os.path.basename(f)[2:7])
        dr.text((x + 4, y + 2), '%.1f' % (fr / 24), fill=(255, 255, 0))
    s.save('%s_%02d.jpg' % (pre, p // per))
    print('%s_%02d.jpg' % (pre, p // per))
