"""Real process ownership checks; no production agents or remote transfers."""
import subprocess
import sys

import pytest

from harness.config import load_config
from harness.store import Busy, Store


def hold(root, run_id, transfer=False):
    child = subprocess.Popen([sys.executable, '-u', '-c', '''
import sys
from harness.store import Store
s = Store(sys.argv[1])
with s.worker_lock(sys.argv[2]):
    if sys.argv[3] == 'True':
        with s.delivery_lock():
            print('locked', flush=True)
            sys.stdin.readline()
    else:
        print('locked', flush=True)
        sys.stdin.readline()
''', str(root), run_id, str(transfer)], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Bounded handshake rather than sleeps or inferred process liveness.
    import select
    if not select.select([child.stdout], [], [], 10)[0]:
        child.kill()
        child.communicate()
        pytest.fail('Lock process did not become ready')
    assert child.stdout.readline().strip() == 'locked'
    return child


def release(child):
    stdout, stderr = child.communicate('\n', timeout=10)
    assert child.returncode == 0, (stdout, stderr)


def test_independent_processes_generate_concurrently_and_exclude_same_run(tmp_path):
    store = Store(tmp_path)
    a, b = [store.create(load_config())['id'] for _ in range(2)]
    first = hold(tmp_path, a)
    second = None
    try:
        second = hold(tmp_path, b)  # Must acquire while A is still held.
        for run_id in (a, b):
            with pytest.raises(Busy):
                with Store(tmp_path).worker_lock(run_id):
                    pass
        with pytest.raises(Busy):
            with Store(tmp_path).worker_lock():
                pass
    finally:
        release(first)
        if second is not None:
            release(second)
    with store.worker_lock(a), store.worker_lock(b):
        assert len(store.upload_lock_fds(a)) == 2


def test_legacy_controller_still_excludes_new_run_owners(tmp_path):
    store = Store(tmp_path)
    run_id = store.create(load_config())['id']
    with store.worker_lock():
        with pytest.raises(Busy):
            with Store(tmp_path).worker_lock(run_id):
                pass


def test_transfer_lease_excludes_other_transfers_not_generation(tmp_path):
    store = Store(tmp_path)
    a, b = [store.create(load_config())['id'] for _ in range(2)]
    child = hold(tmp_path, a, transfer=True)
    try:
        with store.worker_lock(b):
            with pytest.raises(Busy):
                with store.delivery_lock():
                    pass
    finally:
        release(child)
    with store.delivery_lock():
        assert store.delivery_lock_fd is not None
