#!/usr/bin/env python3
"""Assemble a short film ad: type cards + a photographed object + an end card.

Deterministic, frame-accurate, no editor required. Type is rendered with Pillow,
motion is a slow eased push on a real photograph, sound is one sine tone with a fade.

  python3 make_film.py --shots shots.json --out film.mp4
  python3 make_film.py --selftest

shots.json is a list of:
  {"type":"text","text":"This wasn't.","seconds":1.8}
  {"type":"photo","file":"book.jpg","seconds":3.0,"push":0.05,"scale":0.82}   # eased push-in; "fill":true to crop edge-to-edge
  {"type":"end","text":"Goosnav Book Two. $19.95.","url":"www.goosnav.shop","seconds":2.2}
"""
import argparse, json, math, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
from studio import config as _cfg        # fonts resolve per machine (Helvetica on macOS, Nimbus Sans on Linux)
FONT = _cfg.font_spec('font_sans_bold')[0]
LINK_FONT = _cfg.font_spec('font_serif')[0]

W, H, FPS = 1080, 1920, 30
LINK_BLUE = (0, 0, 238)
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
GROUND, MARK = BLACK, WHITE          # set by --ground; white ground = black type


def font(px, bold=True):
    return _cfg.font('font_sans_bold' if bold else 'font_sans', px)


def text_frame(text, fg=None, bg=None, size=0.065, y=0.5):
    fg, bg = fg or MARK, bg or GROUND
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    f = font(int(W * size))
    lines = text.split("\n")
    lh = int(W * size * 1.35)
    top = int(H * y) - (len(lines) * lh) // 2
    for i, line in enumerate(lines):
        d.text(((W - d.textlength(line, font=f)) / 2, top + i * lh), line, font=f, fill=fg)
    return img


def end_frame(text, url):
    """Product and price in Helvetica; the URL as an old web link: Times, blue, underlined."""
    img = text_frame(text, size=0.05, y=0.47)
    d = ImageDraw.Draw(img)
    px = int(W * 0.034)
    f = ImageFont.truetype(LINK_FONT, px)
    w = d.textlength(url, font=f)
    x, y = (W - w) / 2, int(H * 0.56)
    d.text((x, y), url, font=f, fill=LINK_BLUE)
    d.line((x, y + int(px * 1.06), x + w, y + int(px * 1.06)), fill=LINK_BLUE, width=max(1, px // 18))
    return img


def photo_frames(path, n, push, fill=False, scale=0.82):
    """Eased push-in on a still. ponytail: ease-out cubic; swap for a spline if it ever reads mechanical."""
    src = Image.open(path).convert("RGB")
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        e = 1 - (1 - t) ** 3
        z = 1 + push * e
        cw, ch = int(src.width / z), int(src.height / z)
        box = ((src.width - cw) // 2, (src.height - ch) // 2, (src.width + cw) // 2, (src.height + ch) // 2)
        if fill:
            frame = ImageOps.fit(src.crop(box), (W, H), Image.LANCZOS)
        else:                                  # fit the whole object on the ground; product stays whole
            c = src.crop(box)
            c.thumbnail((int(W * scale), int(H * scale)), Image.LANCZOS)
            frame = Image.new("RGB", (W, H), GROUND)
            frame.paste(c, ((W - c.width) // 2, (H - c.height) // 2))
        out.append(frame)
    return out


def fade(img, k):
    return Image.blend(Image.new("RGB", img.size, GROUND), img, max(0.0, min(1.0, k)))


def build(shots, out, tone_hz=55):
    total = sum(s["seconds"] for s in shots)
    with tempfile.TemporaryDirectory() as t:
        n = 0
        for s in shots:
            count = int(s["seconds"] * FPS)
            if s["type"] == "photo":
                frames = photo_frames(s["file"], count, s.get("push", 0.05), s.get("fill", False), s.get("scale", 0.82))
            else:
                base = end_frame(s["text"], s["url"]) if s["type"] == "end" else text_frame(s["text"])
                frames = [base] * count
            hold = int(0.25 * FPS)             # quarter-second fades at both ends of every shot
            for i, fr in enumerate(frames):
                k = min(i / hold, (count - 1 - i) / hold, 1.0)
                fade(fr, k).save(Path(t, f"{n:05d}.png"))
                n += 1
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                        "-i", str(Path(t, "%05d.png")),
                        "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=48000",
                        "-af", f"volume=0.12,afade=in:d=0.6,afade=out:st={total-0.8:.2f}:d=0.8",
                        "-t", f"{total:.2f}", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    return total, n


def selftest():
    with tempfile.TemporaryDirectory() as t:
        photo = Path(t, "p.jpg")
        Image.new("RGB", (2000, 1500), (240, 240, 240)).save(photo)
        shots = [{"type": "text", "text": "Everything you looked at\ntoday was generated.", "seconds": 2.0},
                 {"type": "photo", "file": str(photo), "seconds": 2.0, "push": 0.06},
                 {"type": "end", "text": "Goosnav Book Two. $19.95.", "url": "www.goosnav.shop", "seconds": 2.0}]
        out = Path(t, "f.mp4")
        total, n = build(shots, out)
        assert n == 180, n
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "stream=width,height,codec_type,duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout
        assert "1080,1920" in probe and "audio" in probe, probe
        assert abs(float([l.split(",")[-1] for l in probe.strip().splitlines() if "video" in l][0]) - 6.0) < 0.2, probe
    print(f"selftest ok: {n} frames, {total:.1f}s, 1080x1920, audio present")


if __name__ == "__main__":
    # ponytail: module-level ground is fine for a one-shot CLI; make it a param if this ever gets imported twice
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--out", default="film.mp4")
    ap.add_argument("--tone", type=float, default=55)
    ap.add_argument("--ground", default="black", choices=["black", "white"])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.ground == "white":
        globals()["GROUND"], globals()["MARK"] = WHITE, BLACK
    if a.selftest:
        selftest(); sys.exit()
    if not a.shots:
        ap.error("--shots required")
    total, n = build(json.load(open(a.shots)), a.out, a.tone)
    print(f"{n} frames, {total:.1f}s -> {a.out}")
