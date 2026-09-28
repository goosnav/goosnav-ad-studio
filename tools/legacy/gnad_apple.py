#!/usr/bin/env python3
"""Compose Goosnav product stills into Apple-register advertisements."""
import argparse, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

LINK_BLUE = (0, 0, 238)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)

SANS_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
SANS_REG_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
]


def _pick(c):
    for p in c:
        if Path(p).exists():
            return p
    raise SystemExit("no font")


SANS_B, SANS_R, SERIF = _pick(SANS_CANDIDATES), _pick(SANS_REG_CANDIDATES), _pick(SERIF_CANDIDATES)


def sans(px, bold=True):
    p = SANS_B if bold else SANS_R
    if p.endswith(".ttc"):
        return ImageFont.truetype(p, px, index=1 if bold else 0)
    return ImageFont.truetype(p, px)


def serif(px):
    return ImageFont.truetype(SERIF, px)


def track(d, xy, text, font, fill, tracking=0.0):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking
    return x


def track_width(d, text, font, tracking=0.0):
    w = sum(d.textlength(c, font=font) for c in text)
    return w + tracking * max(0, len(text) - 1)


def place_product(canvas, still_path, box, bg):
    """Fit the rendered still into box=(x0,y0,x1,y1), preserving alpha."""
    im = Image.open(still_path)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    a = im.split()[-1]
    bbox = a.getbbox() if a.getextrema()[0] < 255 else None
    if bbox:
        im = im.crop(bbox)
    r = min(bw / im.width, bh / im.height)
    im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    px = bx0 + (bw - im.width) // 2
    py = by0 + (bh - im.height) // 2
    canvas.paste(im, (px, py), im)
    return canvas


def url_line(canvas, url, dark=False, W=None):
    """AD_STRATEGY.md §4: Times, underlined, bottom left on the margin."""
    W = W or canvas.width
    H = canvas.height
    d = ImageDraw.Draw(canvas)
    px = int(W * 0.032)
    f = serif(px)
    x = int(W * 0.115)
    baseline = H - int(W * 0.085)
    col = WHITE if dark else LINK_BLUE
    d.text((x, baseline), url, font=f, fill=col)
    w = d.textlength(url, font=f)
    uy = baseline + int(px * 1.10)
    d.line((x, uy, x + w, uy), fill=col, width=max(1, px // 16))
    return canvas


def ad_white(still, headline, url, out, W=1080, H=1350, sub=None):
    c = Image.new("RGB", (W, H), WHITE)
    place_product(c, still, (int(W * 0.075), int(H * 0.065), int(W * 0.925), int(H * 0.605)), WHITE)
    d = ImageDraw.Draw(c)
    fs = int(W * 0.062)
    f = sans(fs, True)
    tr = -fs * 0.022
    tw = track_width(d, headline, f, tr)
    while tw > W * 0.80 and fs > 20:
        fs -= 2
        f = sans(fs, True)
        tr = -fs * 0.022
        tw = track_width(d, headline, f, tr)
    track(d, ((W - tw) / 2, int(H * 0.665)), headline, f, BLACK, tr)
    if sub:
        fsub = sans(int(W * 0.030), False)
        sw = d.textlength(sub, font=fsub)
        d.text(((W - sw) / 2, int(H * 0.665) + int(fs * 1.42)), sub, font=fsub, fill=(110, 110, 112))
    url_line(c, url, dark=False)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c.save(out, quality=95)
    return out


def ad_dark(still, headline, url, out, W=1080, H=1350, sub=None, fit=False):
    c = Image.new("RGB", (W, H), BLACK)
    im = Image.open(still).convert("RGB")
    band = int(H * 0.625)
    if fit:
        r = min((W * 0.92) / im.width, band / im.height)
        im2 = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
        c.paste(im2, ((W - im2.width) // 2, (band - im2.height) // 2))
    else:
        r = W / im.width
        im2 = im.resize((W, max(1, int(im.height * r))), Image.LANCZOS)
        cy = int(im2.height * 0.47)
        y0 = max(0, min(im2.height - band, cy - band // 2))
        c.paste(im2.crop((0, y0, W, y0 + band)), (0, 0))
    d = ImageDraw.Draw(c)
    fs = int(W * 0.088)
    f = sans(fs, True)
    tr = -fs * 0.028
    tw = track_width(d, headline, f, tr)
    while tw > W * 0.82 and fs > 20:
        fs -= 2
        f = sans(fs, True)
        tr = -fs * 0.028
        tw = track_width(d, headline, f, tr)
    track(d, ((W - tw) / 2, int(H * 0.700)), headline, f, WHITE, tr)
    if sub:
        fsub = sans(int(W * 0.031), False)
        sw = d.textlength(sub, font=fsub)
        d.text(((W - sw) / 2, int(H * 0.700) + int(fs * 1.34)), sub, font=fsub, fill=(150, 150, 154))
    url_line(c, url, dark=True)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c.save(out, quality=95)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--outdir", default="ads")
    a = ap.parse_args()
    for s in json.loads(Path(a.spec).read_text()):
        fn = ad_dark if s["register"] == "dark" else ad_white
        for label, (W, H) in {"": (1080, 1350), "_9x16": (1080, 1920), "_1x1": (1080, 1080)}.items():
            out = Path(a.outdir) / ("%s%s.jpg" % (s["name"], label))
            if s["register"] == "dark":
                fn(s["still"], s["headline"], s["url"], out, W, H, s.get("sub"), s.get("fit", False))
            else:
                fn(s["still"], s["headline"], s["url"], out, W, H, s.get("sub"))
        print("AD %s" % s["name"], flush=True)


if __name__ == "__main__":
    main()
