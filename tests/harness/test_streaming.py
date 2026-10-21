"""Incremental delivery uses real snapshots and fakes only external rclone."""
from copy import deepcopy
from pathlib import Path
import subprocess
import time

import pytest

from harness import delivery
from tests.harness.test_delivery import Drive, fixture


def ready(store, state):
    from harness.streaming import deliver_ready
    return deliver_ready(store, state)


@pytest.fixture
def drive(monkeypatch):
    external = Drive()
    monkeypatch.setattr(delivery, '_bounded_run', external)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: '/usr/bin/rclone')
    return external


def package(state, ad, status):
    next(t for t in state['tasks'] if t['stage'] == 'package' and t['ad'] == ad)['status'] = status


def copies(drive):
    return [Path(c[c.index('copyto') + 1]).name for c in drive.calls if 'copyto' in c]


def retry_due(monkeypatch, state):
    due = state['delivery']['next_retry_at']
    monkeypatch.setattr(time, 'time', lambda: due)


def test_first_finished_ad_uploads_immediately_then_only_next_completion(tmp_path, drive):
    store, state, _ = fixture(tmp_path, 3)
    state['status'] = 'running'
    package(state, 1, 'pending')
    package(state, 2, 'running')
    assert ready(store, state) is state
    assert copies(drive) == ['ad-01.mp4']
    assert state['status'] == 'running'
    assert set(store.get(state['id'])['delivery']['verified']) == {'ad-01.mp4'}
    state = store.get(state['id'])
    package(state, 1, 'succeeded')
    ready(store, state)
    assert copies(drive) == ['ad-01.mp4', 'ad-02.mp4']
    assert state['status'] == 'running'
    assert set(store.get(state['id'])['delivery']['verified']) == {'ad-01.mp4', 'ad-02.mp4'}
    count = len(drive.calls)
    events = len(store.events(state['id']))
    ready(store, store.get(state['id']))
    assert len(drive.calls) == count
    assert len(store.events(state['id'])) == events


def test_transient_quota_does_not_leave_a_finished_ad_waiting_many_minutes(tmp_path, monkeypatch):
    """Once Drive recovers, an old failure streak must not impose 18 minutes of silence."""
    clock = [1000.0]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    store, state, _ = fixture(tmp_path)
    external = Drive()
    unavailable = [True]
    def transport(cmd, **kwargs):
        if unavailable[0]:
            raise subprocess.CalledProcessError(1, cmd, stderr='403 rateLimitExceeded')
        return external(cmd, **kwargs)
    monkeypatch.setattr(delivery, '_bounded_run', transport)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: 'rclone')
    for _ in range(5):
        last_failure = clock[0]
        ready(store, state)
        clock[0] = state['delivery']['next_retry_at']
    unavailable[0] = False
    # Drive has recovered. The next scheduled check should be within a minute,
    # including after many failures, without an upload/resume command.
    assert state['delivery']['next_retry_at'] - last_failure <= 65
    clock[0] += 65
    ready(store, store.get(state['id']))
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


def test_old_long_delivery_cooldown_is_migrated_without_manual_reset(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'status': 'retrying', 'attempts': 5, 'retry_failures': 5,
                         'next_retry_at': 2700.0, 'error': '403 rateLimitExceeded'}
    store.cooldown('drive-delivery', 1700)
    store.cooldown('claude', 3600)
    store.save(state, 'old_policy')
    external = Drive()
    monkeypatch.setattr(delivery, '_bounded_run', external)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: 'rclone')
    ready(store, state)
    assert state['delivery']['next_retry_at'] <= 1065
    assert store.cooldown('drive-delivery') <= 65
    assert store.cooldown('claude') == 3600
    clock[0] = 1065
    ready(store, store.get(state['id']))
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


def test_packaged_ad_retries_while_next_animator_is_still_working(tmp_path, monkeypatch, drive):
    from harness.execution import Budget
    from harness.store import Store
    from harness.workflow import Engine, build_tasks
    from tests.harness.test_compact_production import script
    clock = [1000.0]
    monkeypatch.setattr('harness.workflow.time.monotonic', lambda: clock[0])
    store, state, _ = fixture(tmp_path, 2)
    state['config']['library']['root'] = str(tmp_path)
    state.update(tasks=build_tasks(2, compact=True), sources=[], asset_catalog=[],
                 models={'workers': {'animator': [{'provider': 'codex', 'model': 'fixture'}],
                                     'producer': [{'provider': 'codex', 'model': 'fixture'}]}})
    state['tasks'][0].update(status='succeeded', result={'scripts': [script(), script('two')]})
    package(state, 0, 'succeeded')
    next(t for t in state['tasks'] if t['stage'] == 'package' and t['ad'] == 0)['result'] = {}
    task = next(t for t in state['tasks'] if t['stage'] == 'animate' and t['ad'] == 1)
    task['status'] = 'running'
    def worker(profile, work, *args, **kwargs):
        # This callback runs while the native animator still owns its attempt.
        clock[0] += 10
        kwargs['cancelled']()
        assert task['status'] == 'running'
        assert state.get('delivery', {}).get('verified', {}).get('ad-01.mp4'), (
            'The first completed ad must upload before the next animator returns')
        return {'kind': 'cancelled'}
    engine = Engine(store, execute=worker, auth=lambda _: True)
    engine.budget = Budget(state, store.save)
    with Store(store.root).delivery_lock():
        engine.deliver_finished(state)
    assert drive.calls == []
    engine.agent_task(state, task, store.path(state['id']))
    assert copies(drive) == ['ad-01.mp4']


@pytest.mark.parametrize('attempts', ['broken', None, -3])
def test_malformed_attempt_counter_does_not_prevent_automatic_delivery(tmp_path, drive, attempts):
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'status': 'retrying', 'attempts': attempts}
    ready(store, state)
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'
    assert store.get(state['id'])['delivery']['attempts'] == 1
    assert copies(drive) == ['ad-01.mp4']


def test_transfer_lock_error_is_delivery_failure_without_aborting_animator(tmp_path, monkeypatch):
    store, state, _ = fixture(tmp_path)
    state['status'] = 'running'
    def unavailable():
        raise PermissionError('cannot open delivery transfer lease')
    monkeypatch.setattr(store, 'delivery_lock', unavailable)
    ready(store, state)
    assert state['status'] == 'running'
    assert state['delivery']['status'] == 'retrying'
    assert 'transfer lease' in state['delivery']['error']


@pytest.mark.parametrize('missing', ['drive', 'output', 'package'])
def test_noop_until_delivery_requirements_met(tmp_path, drive, missing):
    store, state, _ = fixture(tmp_path)
    if missing == 'package':
        package(state, 0, 'pending')
    elif missing == 'drive':
        state['config']['delivery']['drive'] = ''
    else:
        state['config']['output']['folder'] = ''
    before = deepcopy(state)
    ready(store, state)
    assert state == before
    assert drive.calls == []
    assert [e['kind'] for e in store.events(state['id'])] == ['created']


def test_failed_partial_retry_never_duplicates_verified_video(tmp_path, drive, monkeypatch):
    store, state, _ = fixture(tmp_path, 2)
    drive.fail_copy = 2
    ready(store, state)
    assert state['delivery']['status'] == 'retrying'
    assert set(store.get(state['id'])['delivery']['verified']) == {'ad-01.mp4'}
    retry_due(monkeypatch, state)
    ready(store, store.get(state['id']))
    assert copies(drive) == ['ad-01.mp4', 'ad-02.mp4', 'ad-02.mp4']
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


def test_unexpected_external_failure_is_persisted_without_changing_production(tmp_path, monkeypatch):
    store, state, _ = fixture(tmp_path)
    state['status'] = 'running'
    state['error'] = 'existing production diagnostic'
    tasks = deepcopy(state['tasks'])

    def unexpected(*args, **kwargs):
        raise TypeError('unexpected rclone boundary error')

    monkeypatch.setattr(delivery, '_bounded_run', unexpected)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: 'rclone')
    ready(store, state)
    persisted = store.get(state['id'])
    assert persisted['delivery']['status'] == 'retrying'
    assert 'unexpected rclone boundary error' in persisted['delivery']['error']
    assert persisted['status'] == 'running'
    assert persisted['error'] == 'existing production diagnostic'
    assert persisted['tasks'] == tasks


def test_helper_isolates_unexpected_uploader_exception(tmp_path, monkeypatch):
    from harness import streaming
    store, state, _ = fixture(tmp_path)

    def unexpected(*args, **kwargs):
        raise LookupError('unexpected uploader failure')

    monkeypatch.setattr(streaming, 'upload_run', unexpected)
    ready(store, state)
    assert store.get(state['id'])['delivery']['status'] == 'retrying'
    assert 'unexpected uploader failure' in state['delivery']['error']


def test_old_uploaded_receipt_is_not_mistaken_for_current_verified_set(tmp_path, drive):
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'status': 'uploaded', 'remote': 'old:folder',
                         'files': ['ad-01.mp4', 'ad-01.zip']}
    ready(store, state)
    assert copies(drive) == ['ad-01.mp4']
    assert set(store.get(state['id'])['delivery']['verified']) == {'ad-01.mp4'}


def test_helper_retries_pending_verification_without_recopy(tmp_path, monkeypatch, drive):
    store, state, _ = fixture(tmp_path)

    def timeout_listing(cmd, **kwargs):
        if 'lsjson' in cmd:
            raise subprocess.TimeoutExpired(cmd, 60)
        return drive(cmd, **kwargs)

    monkeypatch.setattr(delivery, '_bounded_run', timeout_listing)
    ready(store, state)
    assert state['delivery']['status'] == 'retrying'
    retry_due(monkeypatch, state)
    monkeypatch.setattr(delivery, '_bounded_run', drive)
    ready(store, store.get(state['id']))
    assert copies(drive) == ['ad-01.mp4']
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


def test_new_completion_uploads_even_if_old_acknowledgement_listing_times_out(tmp_path, monkeypatch, drive):
    store, state, _ = fixture(tmp_path, 2)
    package(state, 1, 'pending')

    def timeout_listing(cmd, **kwargs):
        if 'lsjson' in cmd:
            raise subprocess.TimeoutExpired(cmd, 60)
        return drive(cmd, **kwargs)

    monkeypatch.setattr(delivery, '_bounded_run', timeout_listing)
    ready(store, state)
    state = store.get(state['id'])
    package(state, 1, 'succeeded')
    retry_due(monkeypatch, state)
    ready(store, state)
    assert copies(drive) == ['ad-01.mp4', 'ad-02.mp4']
    assert set(store.get(state['id'])['delivery']['acknowledged']) == {'ad-01.mp4', 'ad-02.mp4'}


def test_missing_old_local_video_does_not_block_new_completion(tmp_path, drive):
    store, state, folder = fixture(tmp_path, 2)
    package(state, 1, 'pending')
    ready(store, state)
    state = store.get(state['id'])
    (folder / 'ad-01.mp4').unlink()
    package(state, 1, 'succeeded')
    ready(store, state)
    assert copies(drive) == ['ad-01.mp4', 'ad-02.mp4']
    assert 'ad-02.mp4' in store.get(state['id'])['delivery']['verified']


def test_changed_video_invalidates_helper_noop(tmp_path, drive):
    store, state, folder = fixture(tmp_path)
    ready(store, state)
    (folder / 'ad-01.mp4').write_bytes(b'new video')
    ready(store, store.get(state['id']))
    assert copies(drive) == ['ad-01.mp4', 'ad-01.mp4']


def test_changed_destination_invalidates_helper_noop(tmp_path, drive):
    store, state, _ = fixture(tmp_path)
    ready(store, state)
    state = store.get(state['id'])
    state['config']['delivery']['drive'] = 'drive:other'
    ready(store, state)
    assert copies(drive) == ['ad-01.mp4', 'ad-01.mp4']


def test_failed_persistence_stays_isolated_in_memory(tmp_path, monkeypatch):
    store, state, _ = fixture(tmp_path)

    def unavailable(*args, **kwargs):
        raise OSError('state disk unavailable')

    monkeypatch.setattr(store, 'save', unavailable)
    ready(store, state)
    assert state['delivery']['status'] == 'retrying'
    assert 'state disk unavailable' in state['delivery']['error']


@pytest.mark.parametrize('old_receipt', [None, ['malformed']])
def test_malformed_saved_receipt_cannot_escape_into_production(tmp_path, old_receipt):
    store, state, _ = fixture(tmp_path)
    state['delivery'] = old_receipt
    assert ready(store, state) is state
    assert store.get(state['id'])['delivery']['status'] == 'retrying'
