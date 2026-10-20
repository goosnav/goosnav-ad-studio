"""Optional, verified rclone delivery for completed harness runs.

Rendering never depends on Drive: failures are saved as delivery state so
`python -m harness upload RUN_ID` can retry without re-rendering.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from urllib.parse import urlparse


def _destination(value, run_id=None):
    """Resolve an rclone path or a Google Drive folder link to upload arguments."""
    parsed = urlparse(value)
    if parsed.scheme in ('http', 'https'):
        match = re.fullmatch(r'/drive/folders/([A-Za-z0-9_-]+)/?', parsed.path)
        if parsed.netloc not in ('drive.google.com', 'www.drive.google.com') or not match:
            raise ValueError('delivery.drive must be an rclone destination or Google Drive folder link')
        folder_id = match.group(1)
        return 'agent-exchange:', ['--drive-root-folder-id', folder_id]
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*:[^\x00-\x1f\x7f]*', value):
        raise ValueError('delivery.drive must be an rclone destination or Google Drive folder link')
    return value.rstrip('/'), []


def _title(state, ad):
    """Follow production's selected ID and latest accepted script pool."""
    succeeded = [t for t in state['tasks'] if t['status'] == 'succeeded']
    selection = next((t.get('result') for t in reversed(succeeded) if t['stage'] == 'select'), None)
    writing = next((t.get('result') for t in reversed(succeeded)
                    if t['stage'] in ('write', 'revise')), None)
    if isinstance(selection, dict) and isinstance(writing, dict):
        selected, scripts = selection.get('selected'), writing.get('scripts')
        if isinstance(selected, list) and ad < len(selected) and isinstance(scripts, list):
            script = next((s for s in scripts if isinstance(s, dict) and s.get('id') == selected[ad]), {})
            title = script.get('title')
            if isinstance(title, str) and title.strip():
                return title
    return 'Ad Video'


def _names(state, ads):
    """Reuse persisted names, including a plan saved before an interrupted upload."""
    previous = state.get('delivery', {}).get('names', {})
    if not isinstance(previous, dict):
        raise ValueError('Invalid saved delivery names')
    timestamp = datetime.fromtimestamp(state['created'], timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    suffix = sha256(state['id'].encode()).hexdigest()[:12]
    names = {}
    for ad in ads:
        local = f'ad-{ad+1:02}.mp4'
        if local in previous:
            name = previous[local]
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*\.mp4', name) or len(name) > 180:
                raise ValueError('Unsafe saved delivery filename: ' + local)
        else:
            title = unicodedata.normalize('NFKD', _title(state, ad)).encode('ascii', 'ignore').decode()
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:100].rstrip('-') or 'ad-video'
            name = f'{slug}-{timestamp}-{suffix}-ad-{ad+1:02}.mp4'
        names[local] = name
    if len(set(names.values())) != len(names):
        raise ValueError('Duplicate saved delivery filenames')
    return names


def upload_run(store, state, *, run=subprocess.run, which=shutil.which):
    """Copy accepted MP4s into the configured folder; keep local packages intact."""
    destination = state['config'].get('delivery', {}).get('drive', '').strip()
    if not destination:
        raise ValueError('Drive delivery is not configured: set delivery.drive in harness.local.json')
    remote = destination
    info = {'status': 'failed', 'remote': remote}
    previous = state.get('delivery', {})
    if 'names' in previous:
        # Early failures (including missing rclone) must not discard an upload plan.
        info['names'] = previous['names']
        if 'files' in previous:
            info['files'] = previous['files']
    try:
        remote, drive_flags = _destination(destination, state['id'])
        info['remote'] = remote
        if not which('rclone'):
            raise RuntimeError('rclone not found; install it and run rclone config')
        output = state['config']['output']['folder']
        if not output:
            raise ValueError('output.folder is not configured')
        finished = [t for t in state['tasks'] if t['stage'] == 'package' and t['status'] == 'succeeded']
        if not finished:
            raise ValueError('No packaged ads yet; finish a run before uploading')
        folder = Path(output) / state['id']
        ads = sorted({t['ad'] for t in finished})
        names = _names(state, ads)
        info.update(names=names, files=sorted(names.values()))
        missing_local = sorted(name for name in names if not (folder / name).is_file())
        if missing_local:
            raise FileNotFoundError('Packaged local files missing: ' + ', '.join(missing_local))
        # Persist the entire plan before any remote side effect, even if copyto fails.
        info['status'] = 'uploading'
        state['delivery'] = info
        store.save(state, 'delivery_started', info)
        prefix = remote + ('' if remote.endswith(':') else '/')
        for local, name in names.items():
            run(['rclone', *drive_flags, 'copyto', str(folder / local), prefix + name],
                check=True, capture_output=True, text=True, timeout=3600)
        result = run(['rclone', *drive_flags, 'lsf', remote, '--files-only'],
                     check=True, capture_output=True, text=True, timeout=120)
        found = set(result.stdout.splitlines())
        missing_remote = sorted(set(names.values()) - found)
        if missing_remote:
            raise RuntimeError('Upload not verified on Drive; missing: ' + ', '.join(missing_remote))
        info['status'] = 'uploaded'
    except (OSError, ValueError, RuntimeError, OverflowError, subprocess.SubprocessError) as exc:
        info['status'] = 'failed'
        detail = (getattr(exc, 'stderr', None) or str(exc)).strip()
        info['error'] = detail[-700:] or type(exc).__name__
    state['delivery'] = info
    store.save(state, 'delivery_' + info['status'], info)
    return state
