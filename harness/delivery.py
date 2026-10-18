"""Optional, verified rclone delivery for completed harness runs.

Rendering never depends on Drive: failures are saved as delivery state so
`python -m harness upload RUN_ID` can retry without re-rendering.
"""
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse


def _destination(value, run_id):
    """Resolve an rclone path or a Google Drive folder link to upload arguments."""
    parsed = urlparse(value)
    if parsed.scheme in ('http', 'https'):
        match = re.fullmatch(r'/drive/folders/([A-Za-z0-9_-]+)', parsed.path)
        if parsed.netloc not in ('drive.google.com', 'www.drive.google.com') or not match:
            raise ValueError('delivery.drive must be an rclone destination or Google Drive folder link')
        folder_id = match.group(1)
        return f'agent-exchange:{run_id}', ['--drive-root-folder-id', folder_id]
    if not re.fullmatch(r'[A-Za-z0-9_.-]+:.*', value):
        raise ValueError('delivery.drive must be an rclone destination or Google Drive folder link')
    return value.rstrip('/') + ('' if value.endswith(':') else '/') + run_id, []


def upload_run(store, state, *, run=subprocess.run, which=shutil.which):
    """Copy packaged MP4/ZIP pairs to an rclone remote; persist delivery result."""
    destination = state['config'].get('delivery', {}).get('drive', '').strip()
    if not destination:
        raise ValueError('Drive delivery is not configured: set delivery.drive in harness.local.json')
    remote = destination
    info = {'status': 'failed', 'remote': remote}
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
        expected = {f'ad-{t["ad"]+1:02}.{ext}' for t in finished for ext in ('mp4', 'zip')}
        missing_local = sorted(name for name in expected if not (folder / name).is_file())
        if missing_local:
            raise FileNotFoundError('Packaged local files missing: ' + ', '.join(missing_local))
        # Copy only this run's accepted packages, never stale files left by a retry.
        filters = [arg for name in sorted(expected) for arg in ('--include', name)]
        run(['rclone', *drive_flags, 'copy', str(folder), remote, *filters, '--transfers', '2'],
            check=True, capture_output=True, text=True, timeout=3600)
        result = run(['rclone', *drive_flags, 'lsf', remote, '--files-only'],
                     check=True, capture_output=True, text=True, timeout=120)
        found = set(result.stdout.splitlines())
        missing_remote = sorted(expected - found)
        if missing_remote:
            raise RuntimeError('Upload not verified on Drive; missing: ' + ', '.join(missing_remote))
        info = {'status': 'uploaded', 'remote': remote, 'files': sorted(expected)}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        detail = (getattr(exc, 'stderr', None) or str(exc)).strip()
        info['error'] = detail[-700:] or type(exc).__name__
    state['delivery'] = info
    store.save(state, 'delivery_' + info['status'], info)
    return state
