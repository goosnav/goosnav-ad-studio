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
import os
from pathlib import Path
import subprocess
import sys
import time

from .store import Busy, Store
from .streaming import deliver_ready
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
    """Attempt one due run per tick; load it only after acquiring the controller lock."""
    try:
        with store.worker_lock():
            for state in reversed(store.list()):
                info = state.get('delivery')
                info = info if isinstance(info, dict) else {}
                if (store.control_value(state['id']) != 'run' or not _pending(state)
                        or info.get('next_retry_at', 0) > time.time()):
                    continue
                deliver_ready(store, state)
                info = state.get('delivery', {})
                print(f'{state["id"]}: Drive {info.get("status")} | attempt {info.get("attempts", 0)} | '
                      f'next retry {info.get("next_retry_at", "none")} | {info.get("error", "")[:240]}',
                      flush=True)
                return 1
    except Busy:
        pass
    return 0


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
    count = len(info.get('verified', {}))
    status = info.get('status', 'not started')
    if status == 'retrying':
        action = store.control_value(state['id'])
        if action != 'run':
            return (f'{count}/{state["config"]["count"]} videos verified | automatic retries '
                    f'{"paused" if action == "pause" else "cancelled"} | '
                    f'Last error: {info.get("error", "unknown error")}')
        due = info.get('next_retry_at', time.time())
        health = 'worker running' if worker_running(store) else 'WARNING: retry worker not running'
        return (f'{count}/{state["config"]["count"]} videos verified | automatic retry '
                f'{time.strftime("%H:%M:%S", time.localtime(due))} '
                f'(in {max(0, int(due - time.time()))}s) | attempt {info.get("attempts", 0)} | {health}\n'
                f'Last error: {info.get("error", "unknown error")}')
    return f'{count}/{state["config"]["count"]} videos verified | {status} | {info.get("error", "")}'


def ensure_worker(store):
    """Transfer an exclusive lease to the child: concurrent launchers cannot race."""
    if not any(s['config'].get('delivery', {}).get('drive') for s in store.list()):
        return
    with (store.root / 'delivery-worker.lock').open('a+') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            with (store.root / 'delivery-worker.log').open('a') as log:
                return subprocess.Popen([sys.executable, '-m', 'harness.delivery_queue',
                                  str(store.root), str(lease.fileno())],
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


def serve(store, lease):
    print(f'Drive delivery worker started (pid {os.getpid()}, home {store.root})', flush=True)
    while True:
        try:
            pump(store)
        except Exception as exc:
            print(f'Drive queue error; retrying: {type(exc).__name__}: {exc}', flush=True)
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
