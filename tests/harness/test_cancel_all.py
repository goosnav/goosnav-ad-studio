"""Bulk cancel only targets unfinished runs in the chosen Ad Studio home."""
import json
import os
from pathlib import Path
import subprocess
import sys

from harness.cli import drive
from harness.config import load_config
from harness.store import Busy, Store


ROOT = Path(__file__).resolve().parents[2]


def command(home, *args):
    return subprocess.run([sys.executable, '-m', 'harness', '--home', str(home), *args],
                          cwd=ROOT, capture_output=True, text=True)


def test_cancel_all_marks_unfinished_runs_and_preserves_finished(tmp_path):
    store = Store(tmp_path / 'jobs')
    statuses = ('ready', 'running', 'waiting_provider', 'paused', 'complete',
                'partial', 'failed', 'needs_review', 'cancelled', 'interrupted')
    by_status = {}
    for status in statuses:
        run = store.create(load_config())
        run['status'] = status
        store.save(run, 'fixture')
        by_status[status] = run['id']

    ids = store.cancel_all()
    assert set(ids) == {by_status[status] for status in statuses[:4]}
    for status in statuses[:4]:
        assert store.control_value(by_status[status]) == 'cancel'
        assert store.get(by_status[status])['status'] == 'cancelled'
        events = store.events(by_status[status])
        assert events[-1]['kind'] == 'cancel_requested'
        assert events[-1]['data'] == {'all': True}
    for status in statuses[4:]:
        assert store.get(by_status[status])['status'] == status
    assert store.cancel_all() == []  # idempotent


def test_cancel_all_cli_accepts_flag_and_word(tmp_path):
    store = Store(tmp_path / 'jobs')
    first = store.create(load_config())
    second = store.create(load_config())
    r = command(store.root, 'cancel', '--all')
    assert r.returncode == 0, r.stderr
    output = json.loads(r.stdout)
    assert output['requested'] == 'cancel_all'
    assert set(output['runs']) == {first['id'], second['id']}
    assert output['count'] == 2
    r = command(store.root, 'cancel', 'all')
    assert r.returncode == 0
    assert json.loads(r.stdout)['count'] == 0

    r = command(store.root, 'cancel')
    assert r.returncode == 2 and 'RUN_ID' in r.stderr
    r = command(store.root, 'cancel', first['id'], '-a')
    assert r.returncode == 2


def test_ad_shortcuts_cancel_all_from_own_home(tmp_path):
    store = Store(tmp_path / 'jobs')
    run = store.create(load_config())
    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(store.root)}
    r = subprocess.run([sys.executable, str(ROOT / 'ad'), 'cancel', '-a'],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert 'Cancellation requested for 1' in r.stdout
    assert store.get(run['id'])['status'] == 'cancelled'
    second = store.create(load_config())
    r = subprocess.run([sys.executable, str(ROOT / 'ad'), 'cancel', 'all'],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert store.get(second['id'])['status'] == 'cancelled'


def test_queued_controller_exits_after_bulk_cancel_within_one_poll(tmp_path):
    store = Store(tmp_path / 'jobs')
    run = store.create(load_config())
    sleeps = []

    class AlwaysBusy:
        def run(self, run_id, max_steps=None):
            raise Busy('a different run is rendering')

    def sleep(seconds):
        sleeps.append(seconds)
        store.cancel_all()

    result = drive(AlwaysBusy(), store, run['id'], sleep=sleep)
    assert result['status'] == 'cancelled'
    assert sleeps == [1]


def test_cancel_all_scoped_to_store_home(tmp_path):
    one = Store(tmp_path / 'one')
    two = Store(tmp_path / 'two')
    a = one.create(load_config())
    b = two.create(load_config())
    assert one.cancel_all() == [a['id']]
    assert one.control_value(a['id']) == 'cancel'
    assert two.control_value(b['id']) == 'run'


def test_cancel_all_stops_queued_uploads_without_discarding_render_success(tmp_path):
    store = Store(tmp_path)
    run = store.create(load_config())
    run.update(status='complete', delivery={'status': 'retrying', 'next_retry_at': 9999999999})
    store.save(run, 'queued_delivery')
    assert store.cancel_all() == [run['id']]
    assert store.control_value(run['id']) == 'cancel'
    assert store.get(run['id'])['status'] == 'complete'
    assert store.get(run['id'])['delivery']['status'] == 'retrying'
    assert store.cancel_all() == []
