#!/usr/bin/env python3
"""One drawing -> one ad. Crop, clean, center on white, set the URL line.

  python3 make_ad.py SCAN.tiff --crop 0.13,0.22,0.42,0.58 --out ad.jpg [--url www.patreon.com/goosnav] [--size 4x5]
  python3 make_ad.py --selftest

--crop takes fractions of the source (left,top,right,bottom) so you can read them off a preview.
The crop is then auto-trimmed to the ink and given an exact optical margin, which is the part
people get wrong by hand.
"""
import argparse, sys
from PIL import Image, ImageDraw, ImageFont, ImageOps

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
from studio import config as _cfg        # fonts resolve per machine (Helvetica on macOS, Nimbus Sans on Linux)
FONT = _cfg.font_spec('font_sans_bold')[0]
LINK_FONT = _cfg.font_spec('font_serif')[0]

SIZES = {"4x5": (1080, 1350), "1x1": (1080, 1080), "9x16": (1080, 1920), "print": (2400, 3000)}
LINK_BLUE = (0, 0, 238)                        # the browser default, on purpose
INK = 150          # anything darker than this counts as drawing, not paper
MARGIN = 0.115     # side margin as a fraction of canvas width


def trim(img, pad_frac=0.012):
    """Crop to the ink, then give back a small even pad. Paper is never pure white; threshold first."""
    bbox = ImageOps.grayscale(img).point(lambda v: 255 if v < INK else 0).getbbox()
    if not bbox:
        sys.exit("crop contains no ink")
    pad = int(pad_frac * max(img.size))
    return img.crop((max(0, bbox[0] - pad), max(0, bbox[1] - pad),
                     min(img.width, bbox[2] + pad), min(img.height, bbox[3] + pad)))


def clean(img, white=205, black=60):
    """Paper -> white, ink -> black, nothing in between invented. Levels only, no retouching."""
    g = ImageOps.grayscale(img)
    return g.point(lambda v: 255 if v >= white else (0 if v <= black else int((v - black) * 255 / (white - black))))


def link(draw, xy, text, px):
    """The URL line: Times, browser-blue, underlined — an old web link, set as an artifact."""
    f = ImageFont.truetype(LINK_FONT, px)
    x, y = xy
    draw.text((x, y), text, font=f, fill=LINK_BLUE)
    w = draw.textlength(text, font=f)
    rule = max(1, px // 18)
    draw.line((x, y + int(px * 1.06), x + w, y + int(px * 1.06)), fill=LINK_BLUE, width=rule)
    return w


def build(src, crop, out, url, size="4x5", headline=None, no_clean=False):
    img = Image.open(src)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if crop:
        l, t, r, b = crop
        img = img.crop((int(l * img.width), int(t * img.height), int(r * img.width), int(b * img.height)))
    art = trim(img if no_clean else clean(img))

    W, H = SIZES[size]
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(canvas)
    url_size = int(W * 0.032)                          # Times reads smaller than Helvetica
    head_size = int(W * 0.052)
    f_head = _cfg.font('font_sans_bold', head_size)

    m = int(W * MARGIN)
    baseline = H - int(W * 0.085)                      # URL sits on this line
    art_bottom = baseline - int(W * 0.11) - (int(head_size * 2.2) if headline else 0)
    a = art.copy()
    a.thumbnail((W - 2 * m, art_bottom - m), Image.LANCZOS)
    canvas.paste(a, ((W - a.width) // 2, m + (art_bottom - m - a.height) // 2))

    if headline:                                        # optional; most ads need none
        d.text((m, art_bottom + int(W * 0.03)), headline, font=f_head, fill=(0, 0, 0))
    link(d, (m, baseline), url, url_size)
    canvas.save(out, quality=95, subsampling=0)
    return a.size, canvas.size


def selftest():
    import tempfile, os
    with tempfile.TemporaryDirectory() as t:
        im = Image.new("RGB", (2000, 1500), (248, 246, 240))     # off-white paper
        dd = ImageDraw.Draw(im)
        dd.ellipse((900, 400, 1500, 900), outline=(20, 20, 20), width=12)
        dd.rectangle((100, 100, 300, 200), fill=(30, 30, 30))    # ink elsewhere: must be cropped out
        src = os.path.join(t, "s.png"); im.save(src)
        p = os.path.join(t, "ad.jpg")
        art, canvas = build(src, (0.4, 0.2, 0.8, 0.7), p, "www.goosnav.shop")
        assert canvas == (1080, 1350), canvas
        rgb = Image.open(p).convert("RGB")
        out = rgb.convert("L")
        assert out.getpixel((5, 5)) > 250, "paper must render pure white"
        blues = [1 for px in rgb.crop((0, 1050, 1080, 1350)).getdata() if px[2] > 150 and px[0] < 90]
        assert len(blues) > 200, f"URL must render blue ({len(blues)} blue px)"
        # art is centered horizontally within 2 px
        art_only = out.crop((0, 0, 1080, 1050))          # exclude the URL line
        mask = art_only.point(lambda v: 255 if v < INK else 0).getbbox()
        assert abs((mask[0]) - (1080 - mask[2])) <= 2, mask
        assert mask[1] >= int(1080 * MARGIN) - 2, mask
    print("selftest ok: trim, levels, centering, margins, blue link")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("--crop", help="l,t,r,b as fractions of the source, e.g. 0.1,0.2,0.5,0.6")
    ap.add_argument("--out", default="ad.jpg")
    ap.add_argument("--url", default="www.goosnav.shop")
    ap.add_argument("--size", default="4x5", choices=SIZES)
    ap.add_argument("--headline", help="optional Helvetica Bold line under the art")
    ap.add_argument("--no-clean", action="store_true", help="skip the levels pass")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); sys.exit()
    if not a.src:
        ap.error("src required")
    crop = [float(v) for v in a.crop.split(",")] if a.crop else None
    art, canvas = build(a.src, crop, a.out, a.url, a.size, a.headline, a.no_clean)
    print(f"art {art[0]}x{art[1]} on {canvas[0]}x{canvas[1]} -> {a.out}")
