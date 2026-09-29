"""goosnav-ad-studio command line.  python3 -m studio <command> ...

  config                              show resolved paths and fonts
  textures [all|generic|sheets]       rebuild textures in <assets>/textures
  vo FILM [--voice ...]               narration from films/FILM/lines.txt -> <work>/FILM/vo
  preview FILM --format 4x5 --times 5,20,48  [--every 12]
                                      low-res stills -> <work>/FILM/FMT/preview + contact sheet
  render FILM --format 4x5 [--start --end]   final frames (motion blur, resume) under the GPU lock
  sound FILM --format 4x5             runs films/FILM/sound.py
  type FILM --format 4x5              runs films/FILM/type.py (overlays)
  assemble FILM --format 4x5 --name NAME
  qa FILM --format 4x5 --name NAME    frame check + stills sheet + loudness of the master
  deliver FILM --name NAME [--dest FOLDER] [GLOB ...]   (globs limit which files upload)

A film lives in films/<film>/ with film.py (Blender scene exposing update(t)), sound.py, type.py,
lines.txt, edit.json and SCRIPT.md. See films/the_dilemma for the reference implementation.
"""
import argparse, fcntl, glob, os, subprocess, sys, time
from pathlib import Path
from studio import config

REPO = config.REPO

def blender_cmd(film, fmt, extra):
    return [config.get('blender'), '-b', '--factory-startup', '-P', str(REPO / 'films' / film / 'film.py'), '--',
            '--format', fmt] + extra

def with_lock(cmd, log=None):
    """serialize GPU renders across every agent and session on the machine"""
    lock = open(config.get('render_lock'), 'w')
    print('waiting for render lock', config.get('render_lock'), flush=True)
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        print('lock acquired', time.strftime('%H:%M:%S'), flush=True)
        out = open(log, 'a') if log else None
        return subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT if out else None).returncode
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)

def main():
    ap = argparse.ArgumentParser(prog='studio')
    ap.add_argument('cmd')
    ap.add_argument('film', nargs='?')
    ap.add_argument('--format', default='4x5')
    ap.add_argument('--times'); ap.add_argument('--every', type=int)
    ap.add_argument('--start', type=int); ap.add_argument('--end', type=int)
    ap.add_argument('--name'); ap.add_argument('--dest'); ap.add_argument('--voice', default=None)
    ap.add_argument('--no-lock', action='store_true')
    a, rest = ap.parse_known_args()
    a.rest = [x for x in rest if x != '--']
    work = config.path('work', a.film or '_', a.format)
    py = sys.executable

    if a.cmd == 'config':
        from studio.config import dump, font_spec
        import json
        print(json.dumps(dump(), indent=1))
        for k in ('font_sans_bold', 'font_sans', 'font_serif'):
            print(k, font_spec(k))
        return
    if a.cmd == 'textures':
        return subprocess.run([py, '-m', 'studio.textures', a.film or 'all'], cwd=REPO).returncode
    if a.cmd == 'vo':
        args = [py, '-m', 'studio.vo', str(REPO / 'films' / a.film / 'lines.txt'), str(config.path('work', a.film, 'vo'))]
        if a.voice:
            args += ['--voice', a.voice]
        return subprocess.run(args + a.rest, cwd=REPO).returncode
    if a.cmd == 'preview':
        out = work / 'preview'
        out.mkdir(parents=True, exist_ok=True)
        extra = ['--preview', '--out', str(out)]
        if a.times:
            extra += ['--times', a.times]
        else:
            extra += ['--step', str(a.every or 12)]
        rc = subprocess.run(blender_cmd(a.film, a.format, extra + a.rest)).returncode
        from studio.qa import contact_sheet
        sheet = work / 'preview_sheet.jpg'
        contact_sheet(sorted(glob.glob(str(out / '*.png'))), sheet, cols=8 if a.format != '16x9' else 6, thumb_w=240)
        print('sheet:', sheet)
        return rc
    if a.cmd == 'render':
        (work / 'logs').mkdir(parents=True, exist_ok=True)
        extra = ['--mblur', '--resume']
        if a.start is not None:
            extra += ['--start', str(a.start)]
        if a.end is not None:
            extra += ['--end', str(a.end)]
        cmd = blender_cmd(a.film, a.format, extra + a.rest)
        log = work / 'logs' / 'render.log'
        return subprocess.run(cmd).returncode if a.no_lock else with_lock(cmd, log)
    if a.cmd in ('sound', 'type'):
        script = REPO / 'films' / a.film / ('sound.py' if a.cmd == 'sound' else 'type.py')
        return subprocess.run([py, str(script), '--format', a.format] + a.rest, cwd=REPO).returncode
    if a.cmd == 'assemble':
        from studio.assemble import assemble
        assemble(REPO / 'films' / a.film / 'edit.json', a.format, a.name, a.film)
        return 0
    if a.cmd == 'qa':
        from studio import qa
        ok = qa.check_frames(work / 'frames')
        master = config.path('output', a.film) / f'{a.name}_Goosnav_{a.format}.mp4'
        qa.video_sheet(master, work / 'qa_sheet.jpg', cols=8 if a.format != '16x9' else 6, thumb_w=240)
        qa.loudness(master)
        print('look at:', work / 'qa_sheet.jpg')
        return 0 if ok else 1
    if a.cmd == 'deliver':
        from studio.deliver import deliver
        deliver(config.path('output', a.film), a.name, a.dest, include=a.rest or None)
        return 0
    ap.error('unknown command ' + a.cmd)

if __name__ == '__main__':
    sys.exit(main() or 0)
