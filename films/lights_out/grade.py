"""16mm-ish grade for LIGHTS OUT: halation, a soft toe, a touch of softness, vignette, gate weave, grain.
python3 grade.py <in_dir> <out_dir> [workers] [--only f_00012.png ...]"""
import sys, os, glob, numpy as np
from PIL import Image, ImageFilter
from multiprocessing import Pool

W, H = (1080, 1350) if os.environ.get('LO_PORTRAIT') else (1920, 1080)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
VIG = (1 - 0.42 * r ** 2.4)[..., None]

def grade(src, dst, n):
    im = Image.open(src).convert('RGB')
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    # gate weave: sub-pixel drift, slightly over-scanned so edges never show
    dx = 1.6 * np.sin(n * 0.37) + 0.8 * np.sin(n * 1.13)
    dy = 1.2 * np.sin(n * 0.23) + 0.6 * np.sin(n * 0.91)
    s = 1.012
    im = im.transform((W, H), Image.AFFINE, (1 / s, 0, (W - W / s) / 2 + dx, 0, 1 / s, (H - H / s) / 2 + dy), resample=Image.BICUBIC)
    im = im.filter(ImageFilter.GaussianBlur(0.55))
    a = np.asarray(im).astype(np.float32) / 255.0
    # halation: red-orange bloom around bright things
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    hl = np.clip((lum - 0.62) / 0.38, 0, 1)
    small = Image.fromarray((hl * 255).astype(np.uint8)).resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    hb = np.asarray(small.resize((W, H), Image.BILINEAR)).astype(np.float32)[..., None] / 255.0
    a = a + hb * np.array([0.30, 0.11, 0.035], np.float32)
    # reversal stock: gentle toe lift, highlight roll-off, a little less saturation
    a = 0.014 + a * 0.97
    a = 1 - (1 - np.clip(a, 0, 1.5)) ** 1.0
    a = np.where(a > 0.85, 0.85 + (a - 0.85) * 0.6, a)
    g = a.mean(axis=2, keepdims=True)
    a = g + (a - g) * 0.93
    a = a * VIG
    # grain: luminance-weighted, a little clumped
    rng = np.random.default_rng(n * 7919 + 13)
    gr = rng.standard_normal((H // 2, W // 2)).astype(np.float32)
    gr = np.asarray(Image.fromarray(gr).resize((W, H), Image.BILINEAR))
    amp = 0.019 * (0.45 + 0.55 * np.sqrt(np.clip(g[..., 0], 0, 1)))
    a = a + (gr * amp)[..., None]
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst, compress_level=1)

def job(args):
    src, dst = args
    if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
        return
    n = int(os.path.basename(src)[2:7])
    grade(src, dst, n)

if __name__ == '__main__':
    ind, outd = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else 3
    os.makedirs(outd, exist_ok=True)
    fs = sorted(glob.glob(ind + '/f_*.png'))
    if '--only' in sys.argv:
        names = sys.argv[sys.argv.index('--only') + 1:]
        fs = [f for f in fs if os.path.basename(f) in names]
    with Pool(workers) as p:
        p.map(job, [(f, os.path.join(outd, os.path.basename(f))) for f in fs], chunksize=4)
    print('graded', len(fs))
