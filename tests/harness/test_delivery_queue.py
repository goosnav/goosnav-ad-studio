"""Delivery survives quota failures, controller exit and worker restart."""
import subprocess
import time
import os
import sys
import signal
from pathlib import Path

import pytest

from harness import delivery, streaming
from harness.store import Store
from tests.harness.test_delivery import Drive, fixture


@pytest.fixture
def remote(monkeypatch):
    clock = [1000.0]
    drive = Drive()
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    monkeypatch.setattr(delivery, '_bounded_run', drive)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: 'rclone')
    return clock, drive


def test_failed_upload_is_durable_and_never_retried_before_due(tmp_path, remote):
    clock, drive = remote
    store, state, _ = fixture(tmp_path)
    drive.fail_copy = 1
    streaming.deliver_ready(store, state)
    saved = Store(store.root).get(state['id'])
    info = saved['delivery']
    assert info['status'] == 'retrying'
    assert info['attempts'] == 1
    assert 1060 <= info['next_retry_at'] <= 1075
    calls = len(drive.calls)
    streaming.deliver_ready(Store(store.root), saved)
    assert len(drive.calls) == calls
    clock[0] = info['next_retry_at']
    streaming.deliver_ready(Store(store.root), saved)
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'
    assert store.get(state['id'])['delivery']['attempts'] == 2
    assert 'next_retry_at' not in store.get(state['id'])['delivery']


def test_quota_stops_batch_and_applies_shared_cooldown(tmp_path, remote, monkeypatch):
    clock, drive = remote
    store, state, _ = fixture(tmp_path, 3)

    def quota(cmd, **kwargs):
        drive.calls.append(cmd)
        raise subprocess.CalledProcessError(1, cmd, stderr='403 RATE_LIMIT_EXCEEDED rateLimitExceeded')

    monkeypatch.setattr(delivery, '_bounded_run', quota)
    streaming.deliver_ready(store, state)
    assert len(drive.calls) == 1  # Do not hammer the next two videos after a quota response.
    other = store.create(state['config'])
    other['tasks'] = state['tasks']
    folder = Path(other['config']['output']['folder']) / other['id']
    folder.mkdir()
    for i in range(3):
        (folder / f'ad-{i+1:02}.mp4').write_bytes(b'video')
    streaming.deliver_ready(store, other)
    assert len(drive.calls) == 1
    assert other['delivery']['status'] == 'retrying'
    assert other['delivery']['next_retry_at'] > clock[0]


def test_retry_has_no_attempt_limit_and_delay_is_capped(tmp_path, remote, monkeypatch):
    clock, drive = remote
    store, state, _ = fixture(tmp_path)

    def unavailable(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr(delivery, '_bounded_run', unavailable)
    for attempt in range(12):
        streaming.deliver_ready(store, state)
        info = store.get(state['id'])['delivery']
        assert info['status'] == 'retrying'
        assert info['attempts'] == attempt + 1
        assert 60 <= info['next_retry_at'] - clock[0] <= 1800.000001
        clock[0] = info['next_retry_at']
    monkeypatch.setattr(delivery, '_bounded_run', drive)
    streaming.deliver_ready(store, store.get(state['id']))
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


def test_background_queue_recovers_legacy_failure_and_interrupted_receipt(tmp_path, remote):
    from harness.delivery_queue import pump
    clock, drive = remote
    store, state, _ = fixture(tmp_path)
    state['status'] = 'complete'
    drive.fail_copy = 1
    delivery.upload_run(store, state)  # Simulate an old terminal failure on disk.
    drive.fail_copy = None
    assert pump(Store(store.root)) == 1
    saved = store.get(state['id'])
    assert saved['status'] == 'complete'
    assert saved['delivery']['status'] == 'uploaded'
    count = len(drive.calls)
    assert pump(Store(store.root)) == 0
    assert len(drive.calls) == count


def test_queue_reloads_under_controller_lock_and_respects_cancel(tmp_path, remote):
    from harness.delivery_queue import pump
    _, drive = remote
    store, state, _ = fixture(tmp_path)
    store.save(state, 'fixture')
    with store.worker_lock(state['id']):
        assert pump(Store(store.root)) == 0
        assert drive.calls == []
    store.control(state['id'], 'cancel')
    assert pump(Store(store.root)) == 0
    assert drive.calls == []


def test_queue_skips_busy_run_and_delivers_another(tmp_path, remote):
    from harness.delivery_queue import pump
    _, drive = remote
    store, first, _ = fixture(tmp_path)
    _, second, _ = fixture(tmp_path)
    store.save(first, 'fixture')
    store.save(second, 'fixture')
    with store.worker_lock(first['id']):
        assert pump(Store(store.root)) == 1
    assert store.get(second['id'])['delivery']['status'] == 'uploaded'
    assert 'delivery' not in store.get(first['id'])
    assert len([c for c in drive.calls if 'copyto' in c]) == 1


def test_transfer_contention_defers_inline_and_queue_without_state_writes(tmp_path, remote):
    from harness.delivery_queue import pump
    _, drive = remote
    store, state, _ = fixture(tmp_path)
    store.save(state, 'fixture')
    before = store.get(state['id'])
    events = store.events(state['id'])
    with Store(store.root).delivery_lock():
        with store.worker_lock(state['id']):
            assert streaming.deliver_ready(store, state) == before
        assert pump(Store(store.root)) == 0
    assert store.get(state['id']) == before
    assert store.events(state['id']) == events
    assert drive.calls == []


def test_queue_does_not_reupload_successful_legacy_folder_deliveries(tmp_path, remote):
    from harness.delivery_queue import pump
    _, drive = remote
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'status': 'uploaded', 'remote': 'agent-exchange:old-run-folder',
                         'files': ['ad-01.mp4', 'ad-01.zip']}
    store.save(state, 'legacy_success')
    assert pump(store) == 0
    assert drive.calls == []


@pytest.mark.parametrize('receipt', [None, ['malformed']])
def test_queue_repairs_malformed_receipt_instead_of_blocking_every_run(tmp_path, remote, receipt):
    from harness.delivery_queue import pump
    store, state, _ = fixture(tmp_path)
    state['delivery'] = receipt
    store.save(state, 'bad_old_receipt')
    assert pump(store) == 1
    assert store.get(state['id'])['delivery']['status'] in ('retrying', 'uploaded')


def test_verification_retry_after_restart_does_not_copy_acknowledged_video(tmp_path, remote, monkeypatch):
    from harness.delivery_queue import pump
    clock, drive = remote
    store, state, _ = fixture(tmp_path)

    def failed_listing(cmd, **kwargs):
        if 'lsf' in cmd:
            raise subprocess.TimeoutExpired(cmd, 30)
        return drive(cmd, **kwargs)

    monkeypatch.setattr(delivery, '_bounded_run', failed_listing)
    streaming.deliver_ready(store, state)
    clock[0] = store.get(state['id'])['delivery']['next_retry_at']
    monkeypatch.setattr(delivery, '_bounded_run', drive)
    pump(Store(store.root))
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'
    assert len([c for c in drive.calls if 'copyto' in c]) == 1


def test_quota_for_other_run_does_not_turn_verified_delivery_back_into_pending(tmp_path, remote):
    _, drive = remote
    store, state, _ = fixture(tmp_path)
    streaming.deliver_ready(store, state)
    store.cooldown('drive-delivery', 120)
    streaming.deliver_ready(store, state)
    assert state['delivery']['status'] == 'uploaded'
    assert len(drive.calls) == 2


@pytest.mark.parametrize('change', ['bytes', 'destination'])
def test_queue_checks_receipt_bytes_and_target_after_completed_render(tmp_path, remote, change):
    from harness.delivery_queue import pump
    _, drive = remote
    store, state, folder = fixture(tmp_path)
    state['status'] = 'complete'
    streaming.deliver_ready(store, state)
    saved = store.get(state['id'])
    if change == 'bytes':
        (folder / 'ad-01.mp4').write_bytes(b'repackaged')
    else:
        saved['config']['delivery']['drive'] = 'drive:new-folder'
    store.save(saved, 'controller_exited_before_delivery_hook')
    assert pump(Store(store.root)) == 1
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'
    assert len([c for c in drive.calls if 'copyto' in c]) == 2


def test_jitter_survives_at_backoff_ceiling(tmp_path, remote, monkeypatch):
    clock, drive = remote
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'retry_failures': 20}
    monkeypatch.setattr(streaming.random, 'uniform', lambda lo, hi: lo)
    drive.fail_copy = 1
    streaming.deliver_ready(store, state)
    low = state['delivery']['next_retry_at'] - clock[0]
    state['delivery'].pop('next_retry_at')
    monkeypatch.setattr(streaming.random, 'uniform', lambda lo, hi: hi)
    drive.fail_copy = 2
    streaming.deliver_ready(store, state)
    high = state['delivery']['next_retry_at'] - clock[0]
    assert 60 <= low < high <= 1800


def test_detached_worker_is_singleton_and_restarts_with_released_lease(tmp_path):
    from harness.delivery_queue import ensure_worker, worker_running
    store = Store(tmp_path)
    store.create({'delivery': {'drive': 'test-remote:'}})  # No packages: no external API calls.
    first = ensure_worker(store)
    try:
        assert first is not None
        assert worker_running(store)
        assert ensure_worker(Store(store.root)) is None
    finally:
        if first is not None:
            first.terminate()
            first.wait(timeout=5)
    assert not worker_running(store)
    second = ensure_worker(Store(store.root))
    try:
        assert second is not None
        assert worker_running(store)
    finally:
        if second is not None:
            second.terminate()
            second.wait(timeout=5)


def test_real_background_worker_recovers_after_restart_without_controller(tmp_path, monkeypatch):
    from harness.delivery_queue import ensure_worker
    store, state, _ = fixture(tmp_path)
    state['status'] = 'complete'
    store.save(state, 'finished_render')
    binary = tmp_path / 'bin'
    binary.mkdir()
    (binary / 'fail').touch()
    (binary / 'remote').mkdir()
    executable = binary / 'rclone'
    executable.write_text('''#!/usr/bin/env python3
import sys
from pathlib import Path
root = Path(__file__).parent
with (root / 'calls').open('a') as log:
    log.write(' '.join(sys.argv[1:]) + '\\n')
if (root / 'fail').exists():
    print('403 rateLimitExceeded', file=sys.stderr)
    sys.exit(1)
if 'copyto' in sys.argv:
    idx = sys.argv.index('copyto')
    (root / 'remote' / sys.argv[idx+2].split('/')[-1]).write_bytes(Path(sys.argv[idx+1]).read_bytes())
else:
    print('\\n'.join(p.name for p in (root / 'remote').iterdir()))
''')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(binary) + os.pathsep + os.environ['PATH'])

    def until(check):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if check():
                return
            time.sleep(0.05)
        pytest.fail('Background delivery did not reach the expected state')

    first = ensure_worker(store)
    try:
        until(lambda: store.get(state['id']).get('delivery', {}).get('status') == 'retrying')
    finally:
        first.terminate()
        first.wait(timeout=5)
    assert len((binary / 'calls').read_text().splitlines()) == 1
    second = ensure_worker(Store(store.root))
    try:
        time.sleep(0.2)
        assert len((binary / 'calls').read_text().splitlines()) == 1
        (binary / 'fail').unlink()
        with store.worker_lock():
            saved = store.get(state['id'])
            saved['delivery']['next_retry_at'] = 0
            store.save(saved, 'simulate_due_retry')
            store.clear_cooldowns('drive-delivery')
        until(lambda: store.get(state['id'])['delivery']['status'] == 'uploaded')
        assert store.get(state['id'])['status'] == 'complete'
        assert len(list((binary / 'remote').iterdir())) == 1
    finally:
        second.terminate()
        second.wait(timeout=5)


def test_worker_death_keeps_exclusion_until_outstanding_uploader_exits(tmp_path, monkeypatch):
    from harness.delivery_queue import ensure_worker
    from harness.store import Busy
    store, state, _ = fixture(tmp_path)
    state['status'] = 'complete'
    store.save(state, 'finished_render')
    binary = tmp_path / 'bin'
    binary.mkdir()
    executable = binary / 'rclone'
    executable.write_text('''#!/usr/bin/env python3
import os, time
from pathlib import Path
root = Path(__file__).parent
with (root / 'started').open('a') as out:
    out.write(str(os.getpid()) + '\\n')
while not (root / 'release').exists():
    time.sleep(0.05)
''')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(binary) + os.pathsep + os.environ['PATH'])
    first = ensure_worker(store)
    second = None
    try:
        deadline = time.monotonic() + 10
        while not (binary / 'started').exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert (binary / 'started').exists()
        first.terminate()
        first.wait(timeout=5)
        with pytest.raises(Busy):
            with Store(store.root).worker_lock(state['id']):
                pass
        with pytest.raises(Busy):
            with Store(store.root).delivery_lock():
                pass
        other = store.create(state['config'])
        with Store(store.root).worker_lock(other['id']):
            pass
        second = ensure_worker(Store(store.root))
        time.sleep(0.3)
        assert len((binary / 'started').read_text().splitlines()) == 1
    finally:
        (binary / 'release').touch()
        for child in (first, second):
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=5)


@pytest.mark.parametrize('stop_signal', [signal.SIGTERM, signal.SIGINT])
def test_orphan_uploader_has_independent_hard_deadline(tmp_path, stop_signal):
    store = Store(tmp_path / 'state')
    uploader = tmp_path / 'upload.py'
    marker = tmp_path / 'started'
    uploader.write_text('''import os, signal, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path(sys.argv[1]).write_text(str(os.getpid()))
while True:
    time.sleep(0.05)
''')
    controller = subprocess.Popen([sys.executable, '-c', '''import sys
from harness.store import Store
from harness.delivery import _bounded_run
store = Store(sys.argv[1])
with store.worker_lock():
    _bounded_run([sys.executable, sys.argv[2], sys.argv[3]], timeout=1,
                 check=True, capture_output=True, text=True, pass_fds=(store.worker_lock_fd,))
''', str(store.root), str(uploader), str(marker)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    upload_pid = None
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and controller.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), 'Hard-deadline wrapper did not start uploader'
        upload_pid = int(marker.read_text())
        controller.send_signal(stop_signal)
        controller.wait(timeout=5)
        from harness.store import Busy
        if stop_signal == signal.SIGTERM:
            with pytest.raises(Busy):
                with store.worker_lock():
                    pass
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                with Store(store.root).worker_lock():
                    break
            except Busy:
                time.sleep(0.05)
        else:
            pytest.fail('Orphan upload held the generation lock beyond its independent deadline')
        proc_status = Path(f'/proc/{upload_pid}/stat')
        assert not proc_status.exists() or proc_status.read_text().split()[2] == 'Z'
    finally:
        if controller.poll() is None:
            controller.kill()
            controller.wait(timeout=5)
        if upload_pid:
            try:
                os.kill(upload_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
