"""Process leases for render resources; waits are observable and never time out.

Pass the yielded fd to resource-using children. Close rather than LOCK_UN so a
surviving child retains ownership if its wrapper exits. Never unlink lease files.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid


def default_render_lock():
    """Stable within a user's state directory, independent of worker TMPDIR."""
    base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
    return base.expanduser().resolve() / 'goosnav-ad-studio' / 'render.lock'


def render_lock_path():
    # Resolve the same explicit environment/local override as the studio CLI.
    from studio.config import get
    return Path(get('render_lock')).expanduser().resolve()


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _wait_state(path, token, record=None):
    """Atomically maintain all waiters, with the oldest exposed at the top level."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as guard:
        fcntl.flock(guard, fcntl.LOCK_EX)
        try:
            rows = json.loads(path.read_text()).get('waiters', [])
        except (FileNotFoundError, ValueError):
            rows = []
        rows = [r for r in rows if r['wait_id'] != token and _alive(r['pid'])]
        if record is not None:
            rows.append(record)
        if not rows:
            path.unlink(missing_ok=True)
            return
        rows.sort(key=lambda r: r['started_at'])
        # Top-level updated_at reports the most recent heartbeat of any waiter.
        state = {**rows[0], 'updated_at': max(r['updated_at'] for r in rows), 'waiters': rows}
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.resource-wait-',
                                         delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(state, stream)
                stream.flush()
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)


@dataclass(frozen=True)
class Lease:
    fd: int
    wait_seconds: float


@contextmanager
def resource_lease(path, *, wait_file=None, heartbeat_seconds=2.0):
    """Wait for one resource, heartbeating cwd/.resource-wait.json every 2s.

    Marker fields: pid, started_at/updated_at (Unix seconds), resource (absolute
    lock path), wait_id, and waiters (all waiting records in this workspace).
    Acquisition/interruption removes only this waiter; the last removes the file.
    """
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    marker = Path(wait_file) if wait_file is not None else Path.cwd() / '.resource-wait.json'
    token = uuid.uuid4().hex
    started = time.monotonic()
    record = None
    with path.open('a') as handle:
        try:
            next_heartbeat = 0
            while True:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    now = time.monotonic()
                    if now >= next_heartbeat:
                        record = {'pid': os.getpid(), 'wait_id': token,
                                  'started_at': record['started_at'] if record else time.time(),
                                  'updated_at': time.time(), 'resource': str(path)}
                        _wait_state(marker, token, record)
                        print(f'waiting for render resource: {path}', file=sys.stderr, flush=True)
                        next_heartbeat = now + heartbeat_seconds
                    time.sleep(.1)
            if record is not None:
                _wait_state(marker, token)
                record = None
            yield Lease(handle.fileno(), time.monotonic() - started)
        finally:
            if record is not None:
                _wait_state(marker, token)
