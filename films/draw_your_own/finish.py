"""DRAW YOUR OWN: upscale, mux, and let Goosnav Frame set the end card.

python3 films/draw_your_own/finish.py films/draw_your_own/cut.json WORKDIR [OUTPUT_DIR]

The story frames are 540x675 natives; a single nearest-neighbour 2x keeps their early-3D
crunch at 1080x1350. The master is held on its last frame for the card window, then
harness.media.finish_frame replaces that window with Frame's stacked card over the
library's floating Book 2 clip (title above, blue Times link below). Audio runs through.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from harness.config import load_config  # noqa: E402
from harness.direction import check_mix  # noqa: E402
from harness.media import finish_frame  # noqa: E402


def run(*cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    cut = json.loads(Path(sys.argv[1]).read_text())
    work = Path(sys.argv[2]).expanduser()
    final_dir = work / 'final'
    if final_dir.exists():
        shutil.rmtree(final_dir)
    final_dir.mkdir(parents=True)
    frames = sorted((work / 'frames').glob('*.png'))
    expected = round(cut['end_card']['start'] * cut['fps'])
    if len(frames) != expected:
        raise SystemExit(f'{len(frames)} frames rendered; expected {expected}')
    mix = work / 'audio/mix.wav'
    check_mix(mix, json.loads((work / 'audio/timeline.json').read_text()))
    master = final_dir / 'master.mp4'
    run('ffmpeg', '-v', 'error', '-y', '-framerate', cut['fps'], '-i', work / 'frames/%04d.png', '-i', mix,
        '-vf', f"scale=1080:1350:flags=neighbor,tpad=stop_mode=clone:stop_duration={cut['end_card']['seconds']}",
        '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '15',
        '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-t', cut['duration'], master)
    config = load_config(REPO / 'harness.local.json')
    # Harness runs make 8-13 s ads; this hand-made film is longer by design.
    config['output'].update(target_seconds=cut['duration'], min_seconds=cut['duration'] - 0.5,
                            max_seconds=cut['duration'] + 0.5)
    script = {'product': 'Goosnav Book 2', 'cta': cut['end_card']['title']}
    direction = {'end_card': {'seconds': cut['end_card']['seconds'], 'title': cut['end_card']['title'],
                              'product': 'Goosnav Book 2'}}
    result = finish_frame(master, script, config, final_dir, cancelled=lambda: False, direction=direction)
    final = final_dir / result['master']
    out = Path(sys.argv[3]).expanduser() if len(sys.argv) > 3 else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, out / 'draw_your_own.mp4')
        shutil.copy2(final_dir / 'end_card.png', out / 'end_card.png')
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=1, default=str))


if __name__ == '__main__':
    main()
