"""Optional, incremental rclone delivery for completed ads.

Rendering never depends on Drive: failures are saved as delivery state so
`python -m harness upload RUN_ID` can retry without re-rendering.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import md5, sha1, sha256
from pathlib import Path
import json
import os
import re
import shutil
import signal
import subprocess
import unicodedata
from urllib.parse import urlparse


_NETWORK_FLAGS = ['--retries', '1', '--low-level-retries', '5',
                  '--contimeout', '10s', '--timeout', '30s',
                  '--tpslimit', '1', '--tpslimit-burst', '1',
                  '--transfers', '1', '--checkers', '1']


class _DeliveryStopped(RuntimeError):
    """A control change stops new I/O without discarding transport receipts."""


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
    return _file_details(path, name)[0]


def _file_details(path, name):
    """Keep the public receipt stable; content metadata is separate."""
    digests = {'sha256': sha256(), 'sha1': sha1(), 'md5': md5(usedforsecurity=False)}
    size = 0
    with path.open('rb') as video:
        for chunk in iter(lambda: video.read(1024 * 1024), b''):
            size += len(chunk)
            for digest in digests.values():
                digest.update(chunk)
    hashes = {key: digest.hexdigest() for key, digest in digests.items()}
    return {'name': name, 'sha256': hashes['sha256']}, {'size': size, 'hashes': hashes}


def _proof_matches(proof, details):
    if not isinstance(proof, dict) or not isinstance(proof.get('id'), str) or not proof['id'].strip():
        return False
    checksum = proof.get('checksum', {})
    return (type(proof.get('size')) is int and proof['size'] == details['size']
            and isinstance(checksum, dict) and checksum.get('algorithm') in details['hashes']
            and checksum.get('value') == details['hashes'][checksum['algorithm']])


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
    # Historical uploaded receipts already established name/hash/target trust.
    # Re-probing all of them on upgrade would flood Drive and delay new work.
    strict = info.get('verification_version', 1) >= 2
    try:
        for local, name in names.items():
            receipt, details = _file_details(folder / local, name)
            if (info.get('verified', {}).get(local) != receipt
                    or (strict and not _proof_matches(info.get('remote_proofs', {}).get(local), details))):
                return False
        return bool(names)
    except OSError:
        return False


def _error(exc):
    detail = getattr(exc, 'stderr', None) or str(exc)
    if isinstance(detail, bytes):
        detail = detail.decode(errors='replace')
    detail = detail.strip()
    if not detail:
        return type(exc).__name__
    # Keep the first diagnostic, rather than replacing it with trailing retry
    # noise. Preserve compact quota/project context for the durable retry policy.
    parts = [detail.splitlines()[0][:350]]
    for pattern in (r'ratelimitexceeded|rate_limit_exceeded|rate limit exceeded|quota exceeded|too many requests|429',
                    r'projects/[A-Za-z0-9_.:-]+|project[\s\"\x27:=]+[A-Za-z0-9_.:-]+'):
        match = re.search(pattern, detail, re.IGNORECASE)
        if match:
            line = detail[detail.rfind('\n', 0, match.start()) + 1:]
            line = line.splitlines()[0]
            if len(line) > 180:
                start = max(0, match.start() - 40)
                line = detail[start:start + 180].splitlines()[0]
            if line not in parts and line not in parts[0]:
                parts.append(line)
    return ' | '.join(parts)[:700]


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

    Copies are marked uncertain before transport. Recovery proves remote
    identity/content before repeating a copy whose outcome may have been lost.
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
        receipts, details, errors = {}, {}, []
        for local, name in names.items():
            try:
                receipts[local], details[local] = _file_details(folder / local, name)
            except OSError as exc:
                errors.append(_error(exc))
        same_target = previous.get('target') == target
        verified = {local: receipt for local, receipt in receipts.items()
                    if same_target and previous.get('verified', {}).get(local) == receipt
                    and _proof_matches(previous.get('remote_proofs', {}).get(local), details[local])}
        proofs = {local: previous['remote_proofs'][local] for local in verified}
        acknowledged = {local: receipt for local, receipt in receipts.items()
                        if same_target and previous.get('acknowledged', {}).get(local) == receipt}
        # Also reconcile old plans written by releases without uncertain markers.
        # A different current hash does not prove the previous transport failed.
        recovery = {local for local in receipts if same_target and local in previous.get('names', {})}
        uncertain = {local: receipt for local, receipt in receipts.items()
                     if same_target and local in previous.get('uncertain', {}) and local not in verified}
        # Old uploaded receipts verified names only. Re-list those names once;
        # never infer success from a failed legacy plan's `files` list.
        legacy = (not previous.get('target') and not drive_flags
                  and previous.get('remote') == remote and previous.get('status') == 'uploaded')
        if legacy:
            acknowledged.update({local: receipt for local, receipt in receipts.items()
                                 if previous.get('names', {}).get(local) == receipt['name']
                                 and receipt['name'] in previous.get('files', [])})
        recovery.update(acknowledged)
        recovery.update(uncertain)
        recovery.difference_update(verified)
        info.update(status='uploading', verification_version=2, remote=remote, target=target, names=names,
                    files=sorted(names.values()), hashes={k: v['sha256'] for k, v in receipts.items()},
                    verified=verified, acknowledged=acknowledged, uncertain=uncertain, remote_proofs=proofs)
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

        prefix = remote + ('' if remote.endswith(':') else '/')

        def check_control():
            action = store.control_value(state['id'])
            if action != 'run':
                raise _DeliveryStopped('Drive delivery ' + action + '; pending files and receipts retained')

        def inspect(local):
            check_control()
            name = receipts[local]['name']
            try:
                result = run([*command, 'lsjson', prefix + name, '--stat', '--hash'],
                             check=True, capture_output=True, text=True, timeout=60, **inheritance)
            except subprocess.CalledProcessError as exc:
                if exc.returncode in (3, 4) and not _rate_limited(exc):
                    return None, False  # rclone's directory/file-not-found exit codes.
                raise
            item = json.loads(result.stdout)
            if not isinstance(item, dict):
                raise ValueError('Ambiguous or duplicate remote objects: ' + name)
            if ('duplicate' in (getattr(result, 'stderr', '') or '').lower()
                    or item.get('Name') != name or item.get('IsDir') is not False
                    or not isinstance(item.get('ID'), str) or not item['ID'].strip()
                    or type(item.get('Size')) is not int or item['Size'] < 0):
                raise ValueError('Invalid or ambiguous remote identity: ' + name)
            # Drive's stat selects the first same-name object silently. Enumerate
            # the exact sibling name to prove uniqueness before trusting it.
            # Filtering may be client-side; this still enumerates the parent.
            check_control()
            siblings = run([*command, 'lsjson', remote, '--files-only', '--max-depth', '1',
                            '--include', '/' + name], check=True, capture_output=True,
                           text=True, timeout=60, **inheritance)
            entries = json.loads(siblings.stdout)
            if not isinstance(entries, list) or len(entries) != 1:
                raise ValueError('Missing or duplicate remote objects: ' + name)
            if (not isinstance(entries[0], dict) or entries[0].get('ID') != item['ID']
                    or entries[0].get('Name') != name):
                raise ValueError('Remote identity changed during verification: ' + name)
            hashes = item.get('Hashes')
            if not isinstance(hashes, dict):
                raise ValueError('Remote checksum unavailable: ' + name)
            hashes = {key.lower().replace('-', ''): value.lower() for key, value in hashes.items()
                      if isinstance(key, str) and isinstance(value, str) and value}
            common = [key for key in ('sha256', 'sha1', 'md5') if key in hashes]
            if not common:
                raise ValueError('Remote checksum unavailable: ' + name)
            proof = {'id': item['ID'], 'size': item['Size'],
                     'checksum': {'algorithm': common[0], 'value': hashes[common[0]]}}
            matches = (item['Size'] == details[local]['size']
                       and all(hashes[key] == details[local]['hashes'][key] for key in common))
            return proof, matches

        def verify(local):
            proof, matches = inspect(local)
            if matches:
                verified[local] = receipts[local]
                proofs[local] = proof
                uncertain.pop(local, None)
                store.save(state, 'delivery_verified', info)
            else:
                acknowledged.pop(local, None)
                uncertain[local] = receipts[local]
                store.save(state, 'delivery_reconciled', info)
            return matches

        def copy(local):
            check_control()
            receipt = receipts[local]
            uncertain[local] = receipt
            acknowledged.pop(local, None)
            # Must commit before the child can create or update any remote object.
            store.save(state, 'delivery_copy_started', info)
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
            uncertain.pop(local, None)
            store.save(state, 'delivery_acknowledged', info)

        # New completions go first, even when an older copy awaits verification.
        for local in receipts:
            if local not in verified and local not in recovery:
                copy(local)
        for local in receipts:
            if local in verified or (local not in recovery and local not in acknowledged):
                continue
            try:
                matches = verify(local)
                if not matches and local in recovery:
                    copy(local)  # Default rclone destination checks remain enabled.
                    if local in acknowledged:
                        matches = verify(local)
                if not matches:
                    errors.append('Remote content not verified: ' + local)
            except _DeliveryStopped:
                raise  # Stop the batch; the outer save preserves acknowledgements/uncertainty.
            except Exception as exc:
                if _rate_limited(exc):
                    raise RuntimeError(_error(exc)) from exc
                errors.append(local + ': ' + _error(exc))
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
