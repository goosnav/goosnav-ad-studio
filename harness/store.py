"""Durable run snapshots and events; one active worker on this host/root."""
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
        run_id = time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        state = {'id': run_id, 'config': json.loads(json.dumps(config)), 'status': 'ready',
                 'tasks': [], 'created': time.time(), 'models': {}, 'error': ''}
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

    def control_value(self, run_id):
        with self.connect() as db:
            return db.execute('SELECT control FROM runs WHERE id=?', (run_id,)).fetchone()[0]

    def cooldown(self, provider, seconds=None):
        with self.connect() as db:
            if seconds is not None:
                db.execute('INSERT OR REPLACE INTO cooldowns VALUES (?,?)', (provider, time.time() + seconds))
            row = db.execute('SELECT until FROM cooldowns WHERE provider=?', (provider,)).fetchone()
        return max(0, row[0] - time.time()) if row else 0

    @contextmanager
    def worker_lock(self):
        with (self.root / 'worker.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise Busy('Another controller owns this workspace; status/pause/cancel still work') from e
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
