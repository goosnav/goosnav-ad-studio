"""studio.textures: turn real Goosnav art into render-ready textures, and make generic products.

Rules (owner, 2026-09-26): drawings and comics are real scans, reproduced only (crop, rectify,
levels, upscale). PRODUCTS (book, cards, packs) are rendered GENERIC: plain colour + Helvetica,
or built around a crisp flat digital file (the Goosklerf logo). Never texture a product with a
photograph that is cropped, skewed or soft.

  python3 -m studio.textures all            # rebuild the standard set into <assets>/textures
  python3 -m studio.textures generic        # just the generic book / card / pack
  python3 -m studio.textures sheets         # drawing sheets + comics -> page_XX / comic_XX
"""
import glob, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps
from studio import config

Image.MAX_IMAGE_PIXELS = None
WHITE = (255, 255, 255)
BOOK2_BLUE = (0, 51, 160)            # PMS 286
GOOSKLERF = [(0, 178, 169), (254, 80, 0), (51, 0, 114)]   # PMS 326 / 021 / 2685

# ---------------------------------------------------------------- geometry
def coeffs(dst, src):
    """PIL perspective coeffs mapping output (dst) points -> input (src) points"""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()

def rectify(im, quad, size):
    """quad = TL, TR, BR, BL corners in the source image -> flat image of `size`"""
    w, h = size
    return im.transform(size, Image.PERSPECTIVE, coeffs([(0, 0), (w, 0), (w, h), (0, h)], quad), Image.BICUBIC)

# ---------------------------------------------------------------- scans
def ink_on_paper(im, size=None, paper=(253, 250, 242), ink=(18, 16, 20), lo_pct=0.5, hi_pct=60, gamma=1.6):
    """levels a pencil/ink scan to warm white paper and near-black ink"""
    g = np.asarray(im.convert('L')).astype(np.float32)
    lo, hi = np.percentile(g, lo_pct), np.percentile(g, hi_pct)
    a = np.clip((g - lo) / max(hi - lo, 1), 0, 1) ** gamma
    if size:
        a = np.asarray(ImageOps.fit(Image.fromarray((a * 255).astype(np.uint8)), size, Image.LANCZOS)).astype(np.float32) / 255
    rgb = np.stack([ink[c] + a * (paper[c] - ink[c]) for c in range(3)], -1)
    return Image.fromarray(rgb.astype(np.uint8))

def crop_to_panels(im, aspect=1.3, pad=0.07):
    """crop a comic board to its panel borders at a page aspect (w/h)"""
    g = np.asarray(im.convert('L')) < 110
    rows = np.where(g.sum(1) > 0.25 * g.shape[1])[0]; cols = np.where(g.sum(0) > 0.08 * g.shape[0])[0]
    if len(rows) < 2 or len(cols) < 2:
        return im
    x0, x1, y0, y1 = cols.min(), cols.max(), rows.min(), rows.max()
    p = int(pad * max(x1 - x0, y1 - y0)); W = x1 - x0 + 2 * p; H = y1 - y0 + 2 * p
    W, H = (W, W / aspect) if W / H > aspect else (H * aspect, H)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return im.crop((int(cx - W / 2), int(cy - H / 2), int(cx + W / 2), int(cy + H / 2)))

def hero_crop(src, box, out, size=(1400, 1080)):
    """close crop of one drawing (box in 0..1 fractions), upscaled with crisp ink"""
    im = Image.open(src).convert('L')
    W, H = im.size
    c = im.crop((int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H)))
    c = c.resize(size, Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 120, 3))
    a = np.clip((np.asarray(c).astype(np.float32) / 255 - 0.35) / 0.5, 0, 1) ** 1.3
    c = Image.fromarray((a * 255).astype(np.uint8))
    ink_on_paper(c, lo_pct=0, hi_pct=100, gamma=1.0).save(out)

# ---------------------------------------------------------------- generic products
def cloth(size, base, amp=6, seed=0):
    """fine book-cloth grain so a board is not a flat CG colour"""
    r = np.random.default_rng(seed)
    w, h = size
    n = r.normal(0, 1, (h // 2, w // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n).resize((w, h), Image.BICUBIC))
    weave = (np.sin(np.arange(w) * 1.9)[None, :] + np.sin(np.arange(h) * 2.3)[:, None]) * 0.35
    a = np.clip(np.array(base, np.float32)[None, None, :] + ((n + weave) * amp)[..., None], 0, 255)
    return Image.fromarray(a.astype(np.uint8))

def tight_text(d, xy, text, f, fill, tracking=-0.02):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tracking * f.size
    return x

def generic_book(outdir, title=('Goosnav', 'Book 2'), colour=BOOK2_BLUE, url='www.goosnav.shop',
                 board=(4096, 3072), spine=(640, 3200)):
    """front/back boards (aspect = board) and a spine whose title reads top to bottom"""
    outdir = Path(outdir)
    W, H = board
    m = int(W * 0.075)
    front = cloth((W, H), colour, seed=1)
    d = ImageDraw.Draw(front)
    f = config.font('font_sans_bold', int(H * 0.235))
    for i, line in enumerate(title):
        tight_text(d, (m, int(H * 0.08) + i * int(H * 0.255)), line, f, WHITE)
    front.save(outdir / 'gen_book_front.png')
    back = cloth((W, H), colour, seed=2)
    d = ImageDraw.Draw(back)
    tight_text(d, (m, int(H * 0.08)), ' '.join(title), config.font('font_sans_bold', int(H * 0.05)), WHITE)
    if url:
        d.text((m, int(H * 0.86)), url, font=config.font('font_sans', int(H * 0.04)), fill=WHITE)
    back.save(outdir / 'gen_book_back.png')
    SW, SH = spine
    sp = cloth((SW, SH), colour, seed=3).convert('RGBA')
    lab = Image.new('RGBA', (SH, SW), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lab)
    f5 = config.font('font_sans_bold', int(SW * 0.40))
    dl.text((int(SH * 0.07), (SW - f5.size) / 2 - f5.size * 0.08), ' '.join(title), font=f5, fill=WHITE + (255,))
    sp.alpha_composite(lab.rotate(-90, expand=True))
    sp.convert('RGB').save(outdir / 'gen_book_spine.png')

def load_logo(path):
    logo = Image.open(path).convert('RGB')
    a = np.asarray(logo).astype(int)
    ys, xs = np.where(a.min(axis=2) < 235)
    logo = logo.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    edge = tuple(int(v) for v in np.median(np.asarray(logo)[5:25, logo.width // 3: 2 * logo.width // 3].reshape(-1, 3), axis=0))
    return logo, edge

def generic_card(outdir, logo_path, size=(1260, 1760), radius=70):
    """portrait card: the flat logo file centred on its own border colour; transparent rounded corners"""
    logo, edge = load_logo(logo_path)
    CW, CH = size
    card = Image.new('RGBA', (CW, CH), edge + (255,))
    L = logo.resize((CW - 120, CW - 120), Image.LANCZOS)
    card.paste(L, (60, (CH - L.height) // 2))
    mask = Image.new('L', (CW, CH), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CW - 1, CH - 1], radius=radius, fill=255)
    card.putalpha(mask)
    card.save(Path(outdir) / 'gen_card.png')

def generic_pack(outdir, logo_path, label='12 cards', size=(1160, 1840)):
    logo, _ = load_logo(logo_path)
    PW, PH = size
    pk = Image.new('RGB', (PW, PH), (200, 204, 212))
    d = ImageDraw.Draw(pk)
    crimp = 150
    for y in list(range(0, crimp, 14)) + list(range(PH - crimp, PH, 14)):
        d.line([(0, y), (PW, y)], fill=(150, 154, 164), width=5)
        d.line([(0, y + 7), (PW, y + 7)], fill=(236, 238, 242), width=3)
    panel = (40, crimp + 20, PW - 40, PH - crimp - 20)
    bh = (panel[3] - panel[1]) // 3
    for i, c in enumerate(GOOSKLERF):
        d.rectangle([panel[0], panel[1] + i * bh, panel[2], panel[1] + (i + 1) * bh], fill=c)
    Lp = logo.resize((PW - 200, PW - 200), Image.LANCZOS)
    pk.paste(Lp, ((PW - Lp.width) // 2, panel[1] + 90))
    f = config.font('font_sans_bold', 66)
    d.text(((PW - d.textlength(label, font=f)) / 2, panel[3] - 130), label, font=f, fill=WHITE)
    pk.save(Path(outdir) / 'gen_pack.png')

def dice_faces(outdir, colours=None, size=512):
    PIPS = {1: [(.5, .5)], 2: [(.28, .28), (.72, .72)], 3: [(.26, .26), (.5, .5), (.74, .74)],
            4: [(.28, .28), (.72, .28), (.28, .72), (.72, .72)],
            5: [(.26, .26), (.74, .26), (.5, .5), (.26, .74), (.74, .74)],
            6: [(.28, .24), (.72, .24), (.28, .5), (.72, .5), (.28, .76), (.72, .76)]}
    colours = colours or dict(zip(['teal', 'orange', 'purple'], GOOSKLERF))
    for name, col in colours.items():
        for n, pts in PIPS.items():
            im = Image.new('RGB', (size, size), col)
            d = ImageDraw.Draw(im)
            r = size * 44 / 512
            for x, y in pts:
                d.ellipse([x * size - r, y * size - r, x * size + r, y * size + r], fill=(250, 248, 240))
            im.save(Path(outdir) / f'die_{name}_{n}.png')

# ---------------------------------------------------------------- standard set
def build_sheets(src, out):
    for i, p in enumerate(sorted(glob.glob(str(src / 'Drawing *.jpg')))):
        ink_on_paper(Image.open(p), (1400, 1080)).save(out / f'page_{i:02d}.png')
    for i, p in enumerate(sorted(glob.glob(str(src / '*COMICS*.tif')))):
        im = Image.open(p).convert('L'); im.thumbnail((2200, 2200))
        ink_on_paper(crop_to_panels(im), (1400, 1080)).save(out / f'comic_{i:02d}.png')
    if (out / 'page_05.png').exists():
        hero_crop(out / 'page_00.png', (0.04, 0.03, 0.56, 0.55), out / 'hero_foot.png')
        hero_crop(out / 'page_04.png', (0.0, 0.19, 0.50, 0.69), out / 'hero_emotion.png')
        hero_crop(out / 'page_05.png', (0.10, 0.27, 0.64, 0.84), out / 'hero_mug.png')

def build_generic(src, out):
    generic_book(out)
    generic_card(out, src / 'GOOSKLERF.jpg')
    generic_pack(out, src / 'GOOSKLERF.jpg')
    dice_faces(out)

if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    src, out = config.sources(), config.textures()
    out.mkdir(parents=True, exist_ok=True)
    if what in ('all', 'sheets'):
        build_sheets(src, out)
    if what in ('all', 'generic'):
        build_generic(src, out)
    print('textures ->', out)
