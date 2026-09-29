"""studio.deliver: put a finished film folder on Drive (rclone) and verify it server-side.

  python3 -m studio.deliver <output>/<film> --name THE_DILEMMA [--dest EXISTING_FOLDER_NAME] [--dry-run]

Copies every file in the folder to <rclone_remote><rclone_subdir>/<UTC>-claude-<NAME>/ (or --dest),
lists it back with `rclone lsl` (the listing comes from the Drive API, so it proves the upload),
and mirrors to <local_delivery> when configured. Never deletes anything remotely.
"""
import argparse, datetime, shutil, subprocess
from pathlib import Path
from studio import config

def deliver(folder, name, dest=None, dry=False, include=None):
    folder = Path(folder)
    stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    dest = dest or f'{stamp}-claude-{name}'
    remote = f"{config.get('rclone_remote')}{config.get('rclone_subdir')}/{dest}"
    import fnmatch
    files = [p for p in folder.iterdir() if p.is_file() and not p.name.startswith('.')
             and (not include or any(fnmatch.fnmatch(p.name, g) for g in include))]
    print('delivering', len(files), 'files ->', remote)
    if dry:
        return remote
    flt = sum([['--include', g] for g in include], []) if include else ['--exclude', '.*']
    subprocess.run(['rclone', 'copy', str(folder), remote, '--transfers', '3'] + flt, check=True)
    listing = subprocess.run(['rclone', 'lsl', remote], capture_output=True, text=True, check=True).stdout
    print(listing)
    missing = [p.name for p in files if p.name not in listing]
    if missing:
        raise SystemExit(f'NOT on Drive: {missing}')
    local = config.get('local_delivery')
    if local:
        tgt = Path(local) / dest
        tgt.mkdir(parents=True, exist_ok=True)
        for p in files:
            shutil.copy2(p, tgt / p.name)
        print('mirrored to', tgt)
    return remote

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--name', required=True)
    ap.add_argument('--dest', default=None); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--include', nargs='*', default=None, help='only files matching these globs')
    a = ap.parse_args()
    deliver(a.folder, a.name, a.dest, a.dry_run, a.include)
