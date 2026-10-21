"""Durable run snapshots and events; independent runs have independent owners."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import sqlite3
import time
import uuid


class Busy(RuntimeError):
    pass


class Store:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.worker_lock_fd = None
        self._run_locks = {}
        self.delivery_lock_fd = None
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'state.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, control TEXT NOT NULL DEFAULT 'run');
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY, run TEXT, at REAL, kind TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS cooldowns (provider TEXT PRIMARY KEY, until REAL);
            ''')

    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.execute('PRAGMA busy_timeout=10000')
        return db

    def path(self, run_id):
        # An ID must already be registered; callers cannot turn this into a path API.
        self.get(run_id)
        return self.root / 'runs' / run_id

    def create(self, config):
        from .execution import policy
        run_id = time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        state = {'id': run_id, 'config': json.loads(json.dumps(config)), 'status': 'ready',
                    'tasks': [], 'created': time.time(), 'models': {}, 'error': ''}
        if config.get('generation') and config.get('output', {}).get('target_seconds'):
            state['execution'] = policy(config)
        with self.connect() as db:
            db.execute('INSERT INTO runs(id,state) VALUES (?,?)', (run_id, json.dumps(state)))
            self._event(db, run_id, 'created', {})
        (self.root / 'runs' / run_id).mkdir(parents=True)
        return state

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute('SELECT state FROM runs WHERE id=?', (run_id,)).fetchone()
        if row is None:
            raise ValueError(f'Unknown run: {run_id}')
        return json.loads(row[0])

    def list(self):
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT state FROM runs ORDER BY id DESC')]

    def save(self, state, kind, data=None):
        with self.connect() as db:
            db.execute('UPDATE runs SET state=? WHERE id=?', (json.dumps(state), state['id']))
            self._event(db, state['id'], kind, data or {})

    def _event(self, db, run_id, kind, data):
        db.execute('INSERT INTO events(run,at,kind,data) VALUES (?,?,?,?)',
                   (run_id, time.time(), kind, json.dumps(data)))

    def events(self, run_id):
        with self.connect() as db:
            return [dict(seq=r[0], at=r[1], kind=r[2], data=json.loads(r[3])) for r in
                    db.execute('SELECT seq,at,kind,data FROM events WHERE run=? ORDER BY seq', (run_id,))]

    def control(self, run_id, action):
        if action not in ('run', 'pause', 'cancel'):
            raise ValueError('Unknown control action')
        self.get(run_id)
        with self.connect() as db:
            db.execute('UPDATE runs SET control=? WHERE id=?', (action, run_id))
            self._event(db, run_id, action + '_requested', {})

    def cancel_all(self):
        """Cancel every unfinished run in this harness home, in one transaction.

        The control flag is authoritative for running workers and queued controllers.
        Snapshot statuses are updated for immediate visibility; an active controller
        will save its final cancelled status as soon as it observes the flag.
        """
        terminal = {'complete', 'partial', 'failed', 'needs_review', 'cancelled', 'interrupted'}
        cancelled = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for run_id, raw, control in db.execute('SELECT id, state, control FROM runs ORDER BY id DESC').fetchall():
                state = json.loads(raw)
                delivery_pending = (state.get('delivery') or {}).get('status') in ('retrying', 'uploading', 'failed')
                if state['status'] in terminal and (not delivery_pending or control == 'cancel'):
                    continue
                if state['status'] not in terminal:
                    state['status'] = 'cancelled'
                db.execute('UPDATE runs SET control=?, state=? WHERE id=?',
                           ('cancel', json.dumps(state), run_id))
                self._event(db, run_id, 'cancel_requested', {'all': True})
                cancelled.append(run_id)
        return cancelled

    def control_value(self, run_id):
        with self.connect() as db:
            return db.execute('SELECT control FROM runs WHERE id=?', (run_id,)).fetchone()[0]

    def cooldown(self, provider, seconds=None):
        with self.connect() as db:
            if seconds is not None:
                db.execute('''INSERT INTO cooldowns(provider, until) VALUES (?,?)
                              ON CONFLICT(provider) DO UPDATE
                              SET until = MAX(cooldowns.until, excluded.until)''',
                           (provider, time.time() + seconds))
            row = db.execute('SELECT until FROM cooldowns WHERE provider=?', (provider,)).fetchone()
        return max(0, row[0] - time.time()) if row else 0

    def clear_cooldowns(self, provider=None):
        """Clear cached quota cooldowns after a user confirms provider capacity is back."""
        with self.connect() as db:
            if provider is None:
                db.execute('DELETE FROM cooldowns')
            else:
                db.execute('DELETE FROM cooldowns WHERE provider=?', (provider,))

    @contextmanager
    def worker_lock(self, run_id=None):
        """Exclude writers of one run; no-argument legacy callers exclude all runs.

        Shared legacy leases coordinate with older controllers without serializing
        new controllers. Never unlink lock files (their inode is the lock).
        """
        path = self.path(run_id) / 'worker.lock' if run_id is not None else None
        with (self.root / 'worker.lock').open('a') as legacy:
            try:
                fcntl.flock(legacy, (fcntl.LOCK_SH if path else fcntl.LOCK_EX) | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise Busy('Another controller owns this workspace; status/pause/cancel still work') from e
            lock = path.open('a') if path else legacy
            previous = self.worker_lock_fd
            try:
                if path:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError as e:
                        raise Busy(f'Another controller owns run {run_id}; status/pause/cancel still work') from e
                self.worker_lock_fd = lock.fileno()
                self._run_locks[run_id] = (legacy.fileno(), lock.fileno())
                try:
                    yield
                finally:
                    self._run_locks.pop(run_id, None)
                    self.worker_lock_fd = previous
            finally:
                # Close, not LOCK_UN: an inherited uploader must keep its lease.
                if path:
                    lock.close()

    def upload_lock_fds(self, run_id):
        """Leases inherited by the deadline guard and its upload child."""
        descriptors = self._run_locks.get(run_id, self._run_locks.get(None, ()))
        if self.delivery_lock_fd is not None:
            descriptors = (*descriptors, self.delivery_lock_fd)
        return tuple(dict.fromkeys(descriptors))

    @contextmanager
    def delivery_lock(self):
        """Serialize all transfers, including inline hooks and manual uploads."""
        if self.delivery_lock_fd is not None:
            yield
            return
        with (self.root / 'delivery-transfer.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise Busy('Another delivery transfer is active') from e
            self.delivery_lock_fd = lock.fileno()
            try:
                yield
            finally:
                self.delivery_lock_fd = None
