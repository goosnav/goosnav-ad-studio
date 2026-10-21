"""Single background delivery queue for one harness home (Linux/WSL).

IN: Store containing run snapshots and completed packages.
OUT: Due deliveries attempted under the same lock as production/manual uploads.
GUARANTEES: no generation retries, no stale snapshot writes, no retry limit.
DECISION: Keep the worker detached/alive rather than sleep inside a renderer;
          queued delivery survives terminal/controller exit without blocking ads.
LIMITS: A powered-off host cannot upload. CLI/GUI startup recovers the saved queue.
TESTBENCH: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/harness/test_delivery_queue.py
"""
import fcntl
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from .store import Busy, Store
from . import streaming
from .delivery import _already_verified, _completed_ads


def _pending(state):
    if (not state['config'].get('delivery', {}).get('drive', '').strip()
            or not state['config'].get('output', {}).get('folder')):
        return False
    completed = {f'ad-{ad+1:02}.mp4' for ad in _completed_ads(state)}
    info = state.get('delivery')
    info = info if isinstance(info, dict) else {}
    # Historical successful folder/ZIP deliveries are not failed queue entries.
    # Recovering the queue must not upload them again under today's flat naming.
    if info.get('status') == 'uploaded' and not info.get('target'):
        return False
    if not completed:
        return False
    try:
        return not _already_verified(state)
    except (ValueError, TypeError, AttributeError):
        return True  # Let the attempt persist a diagnostic and a retry deadline.


def pump(store):
    """Attempt one run fairly; deferrals and broken entries do not consume a tick."""
    for candidate in sorted(store.list(), key=_priority):
        try:
            with store.worker_lock(candidate['id']):
                state = store.get(candidate['id'])
                try:
                    if store.control_value(state['id']) != 'run' or not _pending(state):
                        continue
                    with store.delivery_lock():
                        # Migration must happen under both leases, even when an old
                        # saved deadline would otherwise hide this run for 18 minutes.
                        due = streaming.prepare_retry(store, state)
                        if due > time.time():
                            continue
                        before = _attempt(state)
                        streaming.deliver_ready(store, state)
                    if _attempt(state) == before:
                        continue
                    info = state.get('delivery', {})
                    print(f'{state["id"]}: Drive {info.get("status")} | attempt {info.get("attempts", 0)} | '
                          f'next retry {info.get("next_retry_at", "none")} | {str(info.get("error", ""))[:240]}',
                          flush=True)
                    return 1
                except Busy:
                    continue
                except Exception as exc:
                    # Still own the run snapshot. Persist a visible diagnostic,
                    # without giving a malformed entry another scheduling turn.
                    info = state.get('delivery')
                    info = info if isinstance(info, dict) else {}
                    info.update(status='retrying', worker_error=f'{type(exc).__name__}: {exc}'[:700])
                    state['delivery'] = info
                    store.save(state, 'delivery_queue_error', {'error': info['worker_error']})
                    print(f'{state["id"]}: Drive queue entry error: {info["worker_error"]}', flush=True)
        except Busy:
            continue
        except Exception as exc:
            print(f'Drive queue entry unavailable: {type(exc).__name__}: {exc}', flush=True)
    return 0


def _number(value, default=0):
    if type(value) is int:
        return value if value >= 0 else default
    return value if type(value) is float and math.isfinite(value) and value >= 0 else default


def _attempt(state):
    info = state.get('delivery')
    info = info if isinstance(info, dict) else {}
    return (_number(info.get('last_attempt_at')), _number(info.get('attempts')))


def _priority(state):
    if not isinstance(state, dict):
        return (0, 0, '')
    return (_attempt(state)[0], _number(state.get('created')), str(state.get('id', '')))


def worker_running(store):
    """Read-only lease check for status displays; a PID alone can be stale."""
    try:
        with (store.root / 'delivery-worker.lock').open('r') as lease:
            try:
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
    except FileNotFoundError:
        pass
    return False


def describe(store, state):
    """One delivery summary shared by CLI and GUI, including a dead-worker warning."""
    info = state.get('delivery')
    info = info if isinstance(info, dict) else {}
    verified = info.get('verified')
    count = len(verified) if isinstance(verified, dict) else 0
    status = info.get('status', 'not started')
    if status == 'retrying':
        action = store.control_value(state['id'])
        if action != 'run':
            return (f'{count}/{state["config"]["count"]} videos verified | automatic retries '
                    f'{"paused" if action == "pause" else "cancelled"} | '
                    f'Last error: {info.get("error", "unknown error")}')
        now = time.time()
        # Display only: prepare_retry migrates persistent state and must never
        # be invoked from a read-only status description.
        due = max(_number(info.get('next_retry_at'), now), now + store.cooldown(streaming.DRIVE_COOLDOWN))
        health = _health_description(store)
        diagnostic = info.get('worker_error') or info.get('error', 'unknown error')
        return (f'{count}/{state["config"]["count"]} videos verified | automatic retry '
                f'{time.strftime("%H:%M:%S", time.localtime(due))} '
                f'(in {max(0, int(due - time.time()))}s) | attempt {info.get("attempts", 0)} | {health}\n'
                f'Last error: {diagnostic}')
    return f'{count}/{state["config"]["count"]} videos verified | {status} | {info.get("error", "")}'


def _worker_command(store, lease_fd):
    # -B disables writes but still reads timestamp-valid bytecode. An unused
    # prefix also prevents stale reads, including equal-size same-second edits.
    prefix = store.root / ('.delivery-pycache-' + uuid4().hex)
    return [sys.executable, '-B', '-X', f'pycache_prefix={prefix}',
            '-m', 'harness.delivery_queue', str(store.root), str(lease_fd)]


def ensure_worker(store):
    """Transfer an exclusive lease to the child: concurrent launchers cannot race."""
    if not any(s['config'].get('delivery', {}).get('drive') for s in store.list()):
        return
    from .delivery_service import recover_installed
    if recover_installed(store):
        return None
    with (store.root / 'delivery-worker.lock').open('a+') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            with (store.root / 'delivery-worker.log').open('a') as log:
                return subprocess.Popen(_worker_command(store, lease.fileno()),
                                 cwd=Path(__file__).resolve().parents[1],
                                 pass_fds=(lease.fileno(),), stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as exc:
            # Do not call a queue healthy if the OS couldn't start its worker.
            print(f'Drive retry worker could not start: {exc}. Saved uploads remain pending.',
                  file=sys.stderr, flush=True)
            raise


def recover_worker(store):
    """Startup failure is visible, but must not abort unrelated rendering."""
    try:
        return ensure_worker(store)
    except Exception as exc:
        print(f'Drive retry worker unavailable: {exc}. Check delivery-worker.log; '
              'pending videos are saved, not delivered.', file=sys.stderr, flush=True)


def source_fingerprint():
    """Content identity, including this queue, independent of timestamp resolution."""
    digest = sha256()
    for name in ('delivery_queue.py', 'delivery.py', 'streaming.py', 'store.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _heartbeat(store, fingerprint, phase, error=''):
    data = {'pid': os.getpid(), 'fingerprint': fingerprint, 'heartbeat_at': time.time(),
            'phase': phase, 'error': error}
    path = store.root / 'delivery-worker-health.json'
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    try:
        temporary.write_text(json.dumps(data))
        os.replace(temporary, path)
    except OSError as exc:
        # Telemetry failure must not strand a working durable delivery queue.
        print(f'Drive worker heartbeat unavailable: {exc}', flush=True)


def _health_description(store):
    if not worker_running(store):
        return 'WARNING: retry worker not running'
    try:
        data = json.loads((store.root / 'delivery-worker-health.json').read_text())
        age = max(0, int(time.time() - _number(data.get('heartbeat_at'))))
        health = (f'worker running | pid {data["pid"]} | code {str(data["fingerprint"])[:16]} | '
                  f'heartbeat {age}s ago ({data.get("phase", "unknown")})')
        if age > 15 and data.get('phase') != 'processing':
            health += ' | WARNING: stale worker heartbeat'
        if data.get('error'):
            health += f' | queue error: {data["error"]}'
        return health
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return 'worker running | heartbeat unavailable'


def serve(store, lease):
    fingerprint = source_fingerprint()
    print(f'Drive delivery worker started (pid {os.getpid()}, home {store.root})', flush=True)
    while True:
        error = ''
        try:
            if source_fingerprint() != fingerprint:
                # At this idle boundary pump has released all run/transfer
                # leases. Keep the singleton's same open file description over
                # exec: no release/reacquire race and no overlapping worker.
                _heartbeat(store, fingerprint, 'reloading', error)
                os.set_inheritable(lease.fileno(), True)
                os.execv(sys.executable, _worker_command(store, lease.fileno()))
        except OSError as exc:
            print(f'Drive worker reload unavailable: {exc}', flush=True)
        try:
            _heartbeat(store, fingerprint, 'processing')
            pump(store)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'[:700]
            print(f'Drive queue error; retrying: {type(exc).__name__}: {exc}', flush=True)
        _heartbeat(store, fingerprint, 'idle', error)
        time.sleep(5)


if __name__ == '__main__':
    home = Store(sys.argv[1])
    if len(sys.argv) > 2:
        with os.fdopen(int(sys.argv[2]), 'a+') as inherited_lease:
            serve(home, inherited_lease)
    else:
        with (home.root / 'delivery-worker.lock').open('a+') as own_lease:
            try:
                fcntl.flock(own_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                sys.exit('Drive delivery worker is already running')
            serve(home, own_lease)
