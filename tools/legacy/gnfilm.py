#!/usr/bin/env python3
"""Assemble a Goosnav Family III film: type cards, rendered sequences, photos, end card."""
import argparse, json, math, os, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
LINK_BLUE = (0, 0, 238)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)

SANS_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
SERIF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]


def _pick(cands):
    for p in cands:
        if Path(p).exists():
            return p
    raise SystemExit("no usable font found among: %s" % cands)


SANS, SERIF = _pick(SANS_CANDIDATES), _pick(SERIF_CANDIDATES)
SANS_IS_TTC = SANS.endswith(".ttc")


def sans(px):
    return ImageFont.truetype(SANS, px, index=1) if SANS_IS_TTC else ImageFont.truetype(SANS, px)


def serif(px):
    return ImageFont.truetype(SERIF, px)


def text_frame(text, fg, bg, size=0.065, y=0.46):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    f = sans(int(W * size))
    lines = text.split("\n")
    lh = int(W * size * 1.34)
    top = int(H * y) - (len(lines) * lh) // 2
    for i, line in enumerate(lines):
        d.text(((W - d.textlength(line, font=f)) / 2, top + i * lh), line, font=f, fill=fg)
    return img


def end_frame(text, url, fg, bg):
    img = text_frame(text, fg, bg, size=0.05, y=0.44)
    d = ImageDraw.Draw(img)
    px = int(W * 0.034)
    f = serif(px)
    w = d.textlength(url, font=f)
    x, y = (W - w) / 2, int(H * 0.545)
    d.text((x, y), url, font=f, fill=LINK_BLUE)
    d.line((x, y + int(px * 1.12), x + w, y + int(px * 1.12)), fill=LINK_BLUE, width=max(1, px // 16))
    return img


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def photo_frames(path, n, push=0.08, fill=True, scale=0.82, bg=WHITE):
    src = Image.open(path).convert("RGB")
    out = []
    for i in range(n):
        t = ease_out_cubic(i / max(1, n - 1))
        z = 1.0 + push * t
        if fill:
            r = max(W / src.width, H / src.height) * z
            im = src.resize((max(1, int(src.width * r)), max(1, int(src.height * r))), Image.LANCZOS)
            frame = im.crop(((im.width - W) // 2, (im.height - H) // 2,
                             (im.width - W) // 2 + W, (im.height - H) // 2 + H))
        else:
            r = min(W * scale / src.width, H * scale / src.height) * z
            im = src.resize((max(1, int(src.width * r)), max(1, int(src.height * r))), Image.LANCZOS)
            frame = Image.new("RGB", (W, H), bg)
            frame.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        out.append(frame)
    return out


def seq_frames(pattern, n, start=1, bg=BLACK):
    out = []
    for i in range(n):
        p = pattern % (start + i)
        if not Path(p).exists():
            if out:
                out.append(out[-1].copy())
                continue
            raise SystemExit("missing rendered frame: %s" % p)
        im = Image.open(p).convert("RGB")
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        out.append(im)
    return out


def apply_fades(frames, fade_frames, bg):
    n = len(frames)
    k = min(fade_frames, n // 2)
    if k <= 0:
        return frames
    base = Image.new("RGB", (W, H), bg)
    for i in range(k):
        a = (i + 1) / (k + 1)
        frames[i] = Image.blend(base, frames[i], a)
        frames[n - 1 - i] = Image.blend(base, frames[n - 1 - i], a)
    return frames


def build(shots, ground, fade=0.22):
    bg = WHITE if ground == "white" else BLACK
    fg = BLACK if ground == "white" else WHITE
    fade_n = int(FPS * fade)
    all_frames = []
    for s in shots:
        n = max(1, int(round(s.get("seconds", 2.0) * FPS)))
        kind = s["type"]
        sbg = tuple(s["bg"]) if "bg" in s else bg
        sfg = tuple(s["fg"]) if "fg" in s else fg
        if kind == "text":
            fr = [text_frame(s["text"], sfg, sbg, s.get("size", 0.065), s.get("y", 0.46)) for _ in range(n)]
        elif kind == "photo":
            fr = photo_frames(s["file"], n, s.get("push", 0.08), s.get("fill", True), s.get("scale", 0.82), sbg)
        elif kind == "seq":
            fr = seq_frames(s["pattern"], n, s.get("start", 1), sbg)
        elif kind == "end":
            fr = [end_frame(s["text"], s["url"], sfg, sbg) for _ in range(n)]
        else:
            raise SystemExit("unknown shot type: %s" % kind)
        all_frames += apply_fades(fr, fade_n, sbg)
    return all_frames


def encode(frames, out, tone=60, tone_db=-22):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dur = len(frames) / FPS
    with tempfile.TemporaryDirectory() as td:
        for i, f in enumerate(frames):
            f.save("%s/%06d.png" % (td, i + 1))
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(FPS), "-i", "%s/%%06d.png" % td,
        ]
        if tone:
            cmd += ["-f", "lavfi", "-i",
                    "sine=frequency=%d:duration=%.3f" % (tone, dur),
                    "-filter_complex",
                    "[1:a]volume=%ddB,afade=t=in:st=0:d=0.6,afade=t=out:st=%.3f:d=0.8[a]" % (tone_db, max(0.0, dur - 0.8)),
                    "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "128k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "slow", "-crf", "17",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
    return out, dur


def selftest():
    shots = [
        {"type": "text", "text": "Selftest.", "seconds": 1.0},
        {"type": "end", "text": "Goosnav.", "url": "www.goosnav.shop", "seconds": 1.0},
    ]
    fr = build(shots, "white")
    p, dur = encode(fr, "/tmp/gnfilm_selftest.mp4")
    print("selftest ok: %d frames, %.1fs, %dx%d, audio present" % (len(fr), dur, W, H))
    print("sans=%s\nserif=%s" % (SANS, SERIF))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--out")
    ap.add_argument("--ground", default="black", choices=["white", "black"])
    ap.add_argument("--tone", type=int, default=60)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.shots and a.out):
        raise SystemExit("need --shots and --out")
    shots = json.loads(Path(a.shots).read_text())
    frames = build(shots, a.ground)
    p, dur = encode(frames, a.out, a.tone)
    print("wrote %s  %d frames  %.2fs" % (p, len(frames), dur))


if __name__ == "__main__":
    main()
