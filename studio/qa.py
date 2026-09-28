"""studio.qa: look before you ship. Every problem in the first films was caught by looking.

  python3 -m studio.qa frames DIR [--expect N]         # every PNG opens, one size, no gaps
  python3 -m studio.qa sheet DIR OUT.jpg [--cols 6]     # contact sheet of PNG stills (any aspect)
  python3 -m studio.qa video FILM.mp4 OUT.jpg [--every 1.5]   # stills from an encoded film -> sheet
  python3 -m studio.qa loudness FILM.mp4|MIX.wav        # integrated LUFS / LRA / true peak
  python3 -m studio.qa spectrum MIX.wav OUT.png         # spectrogram + waveform with 5 s ticks

Then open the JPG/PNG with an image viewer (agents: the Read tool) and actually look.
"""
import argparse, glob, json, re, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from studio import config

def check_frames(d, expect=None):
    fs = sorted(glob.glob(str(Path(d) / 'f_*.png')))
    bad, sizes = [], set()
    for f in fs:
        try:
            im = Image.open(f); im.load(); sizes.add(im.size)
        except Exception as e:
            bad.append((f, str(e)[:60]))
    nums = sorted(int(re.findall(r'(\d+)\.png$', f)[0]) for f in fs)
    missing = [i for i in range(nums[0], nums[-1] + 1) if i not in set(nums)] if nums else []
    if expect is not None:
        missing += [i for i in range(len(nums) and nums[-1] + 1, expect)]
    res = {'count': len(fs), 'sizes': sorted(sizes), 'bad': bad[:20], 'missing': missing[:50]}
    print(json.dumps(res, indent=1))
    return not bad and not missing and len(sizes) <= 1

def contact_sheet(paths, out, cols=6, thumb_w=360, labels=None):
    if not paths:
        raise SystemExit('no images')
    w0, h0 = Image.open(paths[0]).size
    tw, th = thumb_w, int(thumb_w * h0 / w0)
    rows = (len(paths) + cols - 1) // cols
    sh = Image.new('RGB', (cols * tw, rows * (th + 16)), 'white')
    d = ImageDraw.Draw(sh)
    for i, p in enumerate(paths):
        x, y = (i % cols) * tw, (i // cols) * (th + 16)
        sh.paste(Image.open(p).convert('RGB').resize((tw - 4, th)), (x, y + 16))
        d.text((x + 3, y + 2), labels[i] if labels else Path(p).name, fill=(0, 0, 0))
    sh.save(out, quality=86)
    return out

def video_sheet(film, out, every=1.5, cols=6, thumb_w=360):
    dur = float(subprocess.check_output([config.get('ffmpeg').replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries',
                                         'format=duration', '-of', 'csv=p=0', str(film)]).decode())
    tmp = Path(tempfile.mkdtemp())
    paths, labels = [], []
    t = every / 3
    while t < dur:
        p = tmp / f'{t:07.2f}.png'
        subprocess.run([config.get('ffmpeg'), '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', str(film), '-frames:v', '1', str(p)], check=True)
        paths.append(str(p)); labels.append(f'{t:.1f}s')
        t += every
    return contact_sheet(paths, out, cols, thumb_w, labels)

def loudness(path):
    r = subprocess.run([config.get('ffmpeg'), '-hide_banner', '-i', str(path), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True)
    summ = r.stderr[r.stderr.rfind('Summary'):]
    vals = {k: re.search(k + r':\s+(-?[\d.]+)', summ) for k in ('I', 'LRA', 'Peak')}
    out = {k: float(v.group(1)) for k, v in vals.items() if v}
    print(json.dumps(out), '(target: I about -14 LUFS, Peak below -1 dBFS)')
    return out

def spectrum(path, out):
    ff = config.get('ffmpeg')
    tmp = str(out) + '.raw.png'
    subprocess.run([ff, '-y', '-v', 'error', '-i', str(path), '-filter_complex',
                    '[0:a]showspectrumpic=s=1800x400:legend=0:scale=log[s];[0:a]showwavespic=s=1800x200:colors=white[w];'
                    '[s]format=rgb24[s2];[w]format=rgb24[w2];[s2][w2]vstack=inputs=2', tmp], check=True)
    dur = float(subprocess.check_output([ff.replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries', 'format=duration',
                                         '-of', 'csv=p=0', str(path)]).decode())
    im = Image.open(tmp); d = ImageDraw.Draw(im)
    for s in range(0, int(dur) + 1, 5):
        x = int(s / dur * 1800); d.line([(x, 0), (x, 600)], fill=(255, 255, 0)); d.text((x + 2, 2), str(s), fill=(255, 255, 0))
    im.save(out); Path(tmp).unlink()
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    a1 = sub.add_parser('frames'); a1.add_argument('dir'); a1.add_argument('--expect', type=int)
    a2 = sub.add_parser('sheet'); a2.add_argument('dir'); a2.add_argument('out'); a2.add_argument('--cols', type=int, default=6)
    a2.add_argument('--glob', default='*.png')
    a3 = sub.add_parser('video'); a3.add_argument('film'); a3.add_argument('out'); a3.add_argument('--every', type=float, default=1.5)
    a3.add_argument('--cols', type=int, default=6)
    a4 = sub.add_parser('loudness'); a4.add_argument('path')
    a5 = sub.add_parser('spectrum'); a5.add_argument('path'); a5.add_argument('out')
    a = ap.parse_args()
    if a.cmd == 'frames':
        sys.exit(0 if check_frames(a.dir, a.expect) else 1)
    if a.cmd == 'sheet':
        print(contact_sheet(sorted(glob.glob(str(Path(a.dir) / a.glob))), a.out, a.cols))
    if a.cmd == 'video':
        print(video_sheet(a.film, a.out, a.every, a.cols))
    if a.cmd == 'loudness':
        loudness(a.path)
    if a.cmd == 'spectrum':
        print(spectrum(a.path, a.out))
