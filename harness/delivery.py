"""Optional, incremental rclone delivery for completed ads.

Rendering never depends on Drive: failures are saved as delivery state so
`python -m harness upload RUN_ID` can retry without re-rendering.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import re
import shutil
import signal
import subprocess
import unicodedata
from urllib.parse import urlparse


_NETWORK_FLAGS = ['--retries', '1', '--low-level-retries', '1',
                  '--contimeout', '10s', '--timeout', '30s',
                  '--tpslimit', '1', '--tpslimit-burst', '1',
                  '--transfers', '1', '--checkers', '1']


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
    campaign = next((t.get('result') for t in reversed(succeeded)
                     if t.get('id') == 'campaign-script' or t['stage'] in ('script', 'campaign-script')), None)
    if isinstance(campaign, dict):
        scripts = campaign.get('scripts', [])
        if isinstance(scripts, list) and 0 <= ad < len(scripts):
            title = scripts[ad].get('title') if isinstance(scripts[ad], dict) else None
            if isinstance(title, str) and title.strip():
                return title
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


def _completed_ads(state):
    return sorted({t['ad'] for t in state['tasks']
                   if t['stage'] == 'package' and t['status'] == 'succeeded'
                   and (t.get('result') or {}).get('delivery_mode') != 'product_only'})


def _file_receipt(path, name):
    digest = sha256()
    with path.open('rb') as video:
        for chunk in iter(lambda: video.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'name': name, 'sha256': digest.hexdigest()}


def _already_verified(state):
    """Only trust receipts for these bytes, stable names and this exact target."""
    info = state.get('delivery', {})
    if info.get('status') != 'uploaded':
        return False
    remote, flags = _destination(state['config']['delivery']['drive'].strip())
    if info.get('target') != {'remote': remote, 'flags': flags}:
        return False
    names = _names(state, _completed_ads(state))
    folder = Path(state['config']['output']['folder']) / state['id']
    try:
        return bool(names) and all(
            info.get('verified', {}).get(local) == _file_receipt(folder / local, name)
            for local, name in names.items())
    except OSError:
        return False


def _error(exc):
    detail = getattr(exc, 'stderr', None) or str(exc)
    if isinstance(detail, bytes):
        detail = detail.decode(errors='replace')
    return detail.strip()[-700:] or type(exc).__name__


def _rate_limited(error):
    detail = str(getattr(error, 'stderr', None) or error).lower()
    return any(marker in detail for marker in (
        'ratelimitexceeded', 'rate_limit_exceeded', 'rate limit exceeded',
        'quota exceeded', 'userratelimitexceeded', 'too many requests', '429'))


def _bounded_run(command, **kwargs):
    """An independent watchdog keeps the deadline after controller death.

    GNU timeout owns a separate process group, including the inherited lock.
    Its TERM/KILL deadlines both precede the Python parent's outer deadline.
    Rclone's own --timeout is only an idle timeout, not an absolute deadline.
    """
    seconds = kwargs.pop('timeout')
    check = kwargs.pop('check', False)
    if kwargs.pop('capture_output', False):
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    guarded = ['timeout', '--signal=TERM', f'--kill-after={seconds * 0.05:g}s',
               f'{seconds * 0.9:g}s', *command]
    with subprocess.Popen(guarded, start_new_session=True, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(timeout=seconds)
        except BaseException:
            # A graceful Ctrl+C must kill the entire upload group before the
            # controller releases its lock, not just kill the watchdog itself.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result


def upload_run(store, state, *, run=None, which=None):
    with store.delivery_lock():
        return _upload_run(store, state, run=run, which=which)


def _upload_run(store, state, *, run=None, which=None):
    """Deliver finished MP4s, durably acknowledging each successful copy.

    Verified receipts survive partial failures. An acknowledged copy whose
    listing was interrupted is listed again before any retry copies it.
    Production callers must hold store.worker_lock(state['id']). The public
    wrapper also excludes transfers belonging to other runs.
    """
    run = _bounded_run if run is None else run
    which = shutil.which if which is None else which
    previous = state.get('delivery', {})
    # Preserve plans and successful receipts even on a preflight failure.
    info = deepcopy(previous)
    info.update(status='failed')
    info.pop('error', None)
    try:
        destination = state['config'].get('delivery', {}).get('drive', '').strip()
        if not destination:
            raise ValueError('Drive delivery is not configured: set delivery.drive in harness.local.json')
        remote, drive_flags = _destination(destination, state['id'])
        target = {'remote': remote, 'flags': drive_flags}
        output = state['config']['output']['folder']
        if not output:
            raise ValueError('output.folder is not configured')
        ads = _completed_ads(state)
        if not ads:
            raise ValueError('No packaged ads yet; finish a run before uploading')
        folder = Path(output) / state['id']
        names = _names(state, ads)
        receipts, errors = {}, []
        for local, name in names.items():
            try:
                receipts[local] = _file_receipt(folder / local, name)
            except OSError as exc:
                errors.append(_error(exc))
        same_target = previous.get('target') == target
        verified = {local: receipt for local, receipt in receipts.items()
                    if same_target and previous.get('verified', {}).get(local) == receipt}
        acknowledged = {local: receipt for local, receipt in receipts.items()
                        if same_target and previous.get('acknowledged', {}).get(local) == receipt}
        # Old uploaded receipts verified names only. Re-list those names once;
        # never infer success from a failed legacy plan's `files` list.
        legacy = (not previous.get('target') and not drive_flags
                  and previous.get('remote') == remote and previous.get('status') == 'uploaded')
        if legacy:
            acknowledged.update({local: receipt for local, receipt in receipts.items()
                                 if previous.get('names', {}).get(local) == receipt['name']
                                 and receipt['name'] in previous.get('files', [])})
        info.update(status='uploading', remote=remote, target=target, names=names,
                    files=sorted(names.values()), hashes={k: v['sha256'] for k, v in receipts.items()},
                    verified=verified, acknowledged=acknowledged)
        state['delivery'] = info
        # Save every intended name/hash before calling any remote operation.
        store.save(state, 'delivery_started', info)
        if len(verified) < len(receipts) and not which('rclone'):
            raise RuntimeError('rclone not found; install it and run rclone config')
        command = ['rclone', *drive_flags, *_NETWORK_FLAGS]
        # If the controller dies mid-copy, its uploader must retain exclusion
        # until it exits. Otherwise a restarted worker can overlap that copy.
        lock_fds = store.upload_lock_fds(state['id'])
        inheritance = {'pass_fds': lock_fds} if lock_fds else {}

        def verify(candidates):
            result = run([*command, 'lsf', '--max-depth', '1', remote, '--files-only'],
                         check=True, capture_output=True, text=True, timeout=60, **inheritance)
            found = set(result.stdout.splitlines())
            for local in candidates:
                if receipts[local]['name'] in found:
                    verified[local] = receipts[local]
                else:
                    acknowledged.pop(local, None)
            # Persist verified successes even if a sibling video is absent.
            store.save(state, 'delivery_verified', info)

        old_pending = set(acknowledged) - set(verified)
        prefix = remote + ('' if remote.endswith(':') else '/')

        def copy(local):
            receipt = receipts[local]
            try:
                run([*command, '--ignore-times', 'copyto', str(folder / local), prefix + receipt['name']],
                    check=True, capture_output=True, text=True, timeout=120, **inheritance)
            except Exception as exc:
                # A shared-project quota applies to the whole batch, not one
                # file. Stop here so the queue can cool down before any more I/O.
                if _rate_limited(exc):
                    raise RuntimeError(_error(exc)) from exc
                errors.append(local + ': ' + _error(exc))
                return
            acknowledged[local] = receipt
            store.save(state, 'delivery_acknowledged', info)

        # New completions go first, even when an older copy awaits verification.
        for local in receipts:
            if local not in verified and local not in acknowledged:
                copy(local)
        pending = set(acknowledged) - set(verified)
        if pending:
            verify(pending)
        # An interrupted copy may have been removed remotely. Only recopy old
        # acknowledgements after a successful listing has proved them absent.
        for local in sorted(old_pending - set(acknowledged) - set(verified)):
            copy(local)
        pending = set(acknowledged) - set(verified)
        if pending:
            verify(pending)
        missing = sorted(names[local] for local in names if local not in verified)
        if missing:
            errors.append('Upload not verified on Drive; missing: ' + ', '.join(missing))
        if errors:
            raise RuntimeError('; '.join(errors))
        info['status'] = 'uploaded'
    except Exception as exc:
        info['status'] = 'failed'
        info['error'] = _error(exc)
    state['delivery'] = info
    store.save(state, 'delivery_' + info['status'], info)
    return state
