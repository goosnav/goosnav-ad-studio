"""studio.assemble: frames + overlays + mix -> master and web MP4, from a JSON edit spec.

edit.json:
{
  "fps": 24, "duration": 90,
  "frames": "{work}/frames/f_%05d.png",          # {work} = <work>/<film>/<format>
  "audio": "{work}/mix.wav",
  "grain": 3, "vignette": true,
  "overlays": [                                   # PNGs with alpha, fades in seconds
     {"file": "{work}/ov/ov_lines.png", "in": 80.2, "fade_in": 0.6, "out": 85.3, "fade_out": 0.5},
     {"file": "{work}/ov/ov_end.png", "in": 86.45, "fade_in": 0.35}
  ],
  "fade_out": [89.3, 0.7],
  "crf": 16, "web_crf": 22
}

  python3 -m studio.assemble films/the_dilemma/edit.json --format 4x5 --name THE_DILEMMA
  -> <output>/<film>/<NAME>_Goosnav_<format>.mp4 and ..._web.mp4
"""
import argparse, json, subprocess
from pathlib import Path
from studio import config

def assemble(spec_path, fmt, name, film=None):
    spec = json.loads(Path(spec_path).read_text())
    film = film or Path(spec_path).parent.name
    work = config.path('work', film, fmt)
    outdir = config.path('output', film); outdir.mkdir(parents=True, exist_ok=True)
    sub = lambda s: s.replace('{work}', str(work))
    fps, dur = spec.get('fps', 24), spec['duration']
    ff = config.get('ffmpeg')
    cmd = [ff, '-y', '-v', 'warning', '-thread_queue_size', '64', '-framerate', str(fps), '-i', sub(spec['frames'])]
    ovs = spec.get('overlays', [])
    for o in ovs:
        cmd += ['-loop', '1', '-framerate', str(fps), '-t', str(dur), '-i', sub(o['file'])]
    cmd += ['-i', sub(spec['audio'])]
    fx = ['format=gbrp']
    if spec.get('vignette', True):
        fx.append('vignette=angle=PI/5:mode=forward')
    if spec.get('grain', 0):
        fx.append(f"noise=alls={spec['grain']}:allf=t")
    fx.append('format=yuv444p')
    chains = [f"[0:v]tpad=stop_mode=clone:stop_duration=10,trim=duration={dur},setpts=PTS-STARTPTS,{','.join(fx)}[b0]"]
    last = 'b0'
    for i, o in enumerate(ovs, start=1):
        f = ['format=rgba']
        if 'in' in o:
            f.append(f"fade=t=in:st={o['in']}:d={o.get('fade_in', 0.4)}:alpha=1")
        if 'out' in o:
            f.append(f"fade=t=out:st={o['out']}:d={o.get('fade_out', 0.4)}:alpha=1")
        chains.append(f"[{i}:v]{','.join(f)}[o{i}]")
        chains.append(f"[{last}][o{i}]overlay=0:0:format=auto[b{i}]")
        last = f'b{i}'
    tail = f"[{last}]"
    fo = spec.get('fade_out')
    tail += (f"fade=t=out:st={fo[0]}:d={fo[1]}," if fo else '') + 'format=yuv420p[v]'
    chains.append(tail)
    master = outdir / f'{name}_Goosnav_{fmt}.mp4'
    cmd += ['-filter_complex', ';'.join(chains), '-map', '[v]', '-map', f'{len(ovs) + 1}:a',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', str(spec.get('crf', 16)), '-profile:v', 'high',
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-af', spec.get('audio_filter', 'lowpass=f=18000,aresample=192000,alimiter=limit=0.79:level=false:attack=0.5:release=60,aresample=48000'),
            '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
            '-t', str(dur), str(master)]
    subprocess.run(cmd, check=True)
    web = outdir / f'{name}_Goosnav_{fmt}_web.mp4'
    subprocess.run([ff, '-y', '-v', 'error', '-i', str(master), '-c:v', 'libx264', '-preset', 'slow',
                    '-crf', str(spec.get('web_crf', 22)), '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    '-c:a', 'aac', '-b:a', '192k', str(web)], check=True)
    print(master); print(web)
    return master, web

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('--format', default='16x9'); ap.add_argument('--name', required=True)
    ap.add_argument('--film', default=None)
    a = ap.parse_args()
    assemble(a.spec, a.format, a.name, a.film)
