"""Real subprocess regressions: attempt cleanup and silent workspace progress."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import pytest

from harness.workers import supervise


def test_delivery_control_callback_does_not_consume_native_worker_watchdog(tmp_path):
    polls = [0]
    def controller():
        polls[0] += 1
        if polls[0] == 2:
            time.sleep(.5)  # A bounded upload while the animator continues.
        return False
    result = supervise([sys.executable, '-c', 'import time; time.sleep(.7)'],
                       cwd=tmp_path, prompt='', log=tmp_path / 'log',
                       timeout=.4, idle_timeout=.3, cancelled=controller)
    assert result['kind'] == 'ok', result
    assert result['elapsed'] >= .5


WRITER = """
from pathlib import Path
import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
deadline = time.monotonic() + 15
while time.monotonic() < deadline and not Path('stop').exists():
    with Path('writes').open('ab') as out:
        out.write(b'x')
    time.sleep(.03)
"""


def wait_for_writes(path):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size:
            return
        time.sleep(.02)
    pytest.fail(f'worker did not start writing: {path}')


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux ownership tracking')
@pytest.mark.parametrize('ending', ['timeout', 'cancelled', 'idle_timeout', 'ok', 'started_error'])
def test_detached_writer_stops_before_return_without_stopping_independent_worker(tmp_path, ending):
    owned = tmp_path / 'owned'; owned.mkdir()
    independent = tmp_path / 'independent'; independent.mkdir()
    cancel_independent = threading.Event()
    # This process has the same user and command as the owned detached writer.
    # Neither its ancestry, name nor user is sufficient evidence of ownership.
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(supervise, [sys.executable, '-c', WRITER],
                             cwd=independent, prompt='', log=independent / 'log',
                             timeout=15, cancelled=cancel_independent.is_set)
        try:
            wait_for_writes(independent / 'writes')
            parent = (
                'import subprocess, sys, time\n'
                'from pathlib import Path\n'
                f'subprocess.Popen([sys.executable, "-c", {WRITER!r}], start_new_session=True)\n'
                'while not Path("writes").exists(): time.sleep(.01)\n'
                + ('' if ending == 'ok' else 'time.sleep(15)\n')
            )

            def started(pid):
                if ending == 'started_error':
                    wait_for_writes(owned / 'writes')
                    raise RuntimeError('start callback failed')

            kwargs = dict(cwd=owned, prompt='', log=owned / 'log',
                          timeout=.5 if ending == 'timeout' else 5,
                          idle_timeout=.4 if ending == 'idle_timeout' else None,
                          cancelled=lambda: ending == 'cancelled' and (owned / 'writes').exists(),
                          started=started)
            begin = time.monotonic()
            if ending == 'started_error':
                with pytest.raises(RuntimeError, match='start callback failed'):
                    supervise([sys.executable, '-c', parent], **kwargs)
            else:
                result = supervise([sys.executable, '-c', parent], **kwargs)
                assert result['kind'] == ending, result
            assert time.monotonic() - begin < 5
            wait_for_writes(owned / 'writes')
            before = (owned / 'writes').stat().st_size
            other_before = (independent / 'writes').stat().st_size
            # Returning permits a retry immediately: no old attempt may still write.
            time.sleep(.2)
            assert (owned / 'writes').stat().st_size == before
            assert (independent / 'writes').stat().st_size > other_before
            assert not future.done()
        finally:
            (owned / 'stop').touch()
            (independent / 'stop').touch()
            cancel_independent.set()
            future.result(timeout=6)


@pytest.mark.parametrize('output', [
    'build.py', 'scene.blend', 'audio/production.json', 'audio/direction-result.json',
    '.render-cache/take/frames.json', 'render-cache/take/frames.json', 'preview.mp4',
    '.resource-wait.json',
])
def test_silent_workspace_output_changes_are_progress(tmp_path, output):
    path = tmp_path / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('0000')
    # Update an existing file at constant size; directory mtimes cannot detect this.
    program = (
        'from pathlib import Path\nimport time\n'
        f'p = Path({output!r})\n'
        'for i in range(12):\n'
        '    p.write_text(f"{i:04d}")\n'
        '    time.sleep(.08)\n'
    )
    result = supervise([sys.executable, '-c', program], cwd=tmp_path, prompt='',
                       log=tmp_path / 'log', timeout=5, idle_timeout=.35,
                       cancelled=lambda: False)
    assert result['kind'] == 'ok', result
    assert path.read_text() == '0011'


def test_frame_progress_discovers_new_cache_without_traversing_frames(tmp_path, monkeypatch):
    cache = tmp_path / '.render-cache'
    cache.mkdir()
    # A cache can hold millions of frames: enumerate cache keys, never their contents.
    original = os.scandir

    def shallow_scandir(path):
        assert Path(path).parent != cache, 'frame directory was scanned'
        return original(path)

    monkeypatch.setattr(os, 'scandir', shallow_scandir)
    program = (
        'from pathlib import Path\nimport time\n'
        'time.sleep(.15)\n'
        'p = Path(".render-cache/new/frames.json")\n'
        'p.parent.mkdir()\n'
        'for i in range(12):\n'
        '    p.write_text(str(i))\n'
        '    time.sleep(.08)\n'
    )
    result = supervise([sys.executable, '-c', program], cwd=tmp_path, prompt='',
                       log=tmp_path / 'log', timeout=5, idle_timeout=.35,
                       cancelled=lambda: False)
    assert result['kind'] == 'ok', result


@pytest.mark.parametrize('leader_exits', [False, True])
def test_original_group_cleanup_includes_children_with_scrubbed_environment(tmp_path, leader_exits):
    parent = (
        'import subprocess, sys, time\nfrom pathlib import Path\n'
        f'subprocess.Popen([sys.executable, "-c", {WRITER!r}], env={{}})\n'
        'while not Path("writes").exists(): time.sleep(.01)\n'
        + ('' if leader_exits else 'time.sleep(15)\n')
    )
    try:
        result = supervise([sys.executable, '-c', parent], cwd=tmp_path, prompt='',
                           log=tmp_path / 'log', timeout=.4, cancelled=lambda: False)
        assert result['kind'] == ('ok' if leader_exits else 'timeout')
        before = (tmp_path / 'writes').stat().st_size
        time.sleep(.2)
        assert (tmp_path / 'writes').stat().st_size == before
    finally:
        (tmp_path / 'stop').touch()


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux ownership recovery')
@pytest.mark.parametrize('leader_exits', [False, True])
def test_persisted_token_recovers_lease_after_supervisor_crash(tmp_path, leader_exits):
    import fcntl
    from harness import workers

    cleanup = getattr(workers, 'cleanup_owned_attempt', None)
    assert callable(cleanup), 'crash recovery needs a public ownership cleanup API'
    owned = tmp_path / 'owned'; owned.mkdir()
    other = tmp_path / 'independent'; other.mkdir()
    # Persistence precedes launching any process, as controller reconciliation requires.
    token = uuid.uuid4().hex
    persisted = tmp_path / 'attempt-token'
    persisted.write_text(token)
    holder = "import fcntl\nlease = open('resource.lock', 'a')\nfcntl.flock(lease, fcntl.LOCK_EX)\n" + WRITER
    leader = (
        'import subprocess, sys, time\n'
        f'subprocess.Popen([sys.executable, "-c", {holder!r}], start_new_session=True)\n'
        + ('' if leader_exits else 'time.sleep(15)\n')
    )
    supervisor = (
        'import sys, time\nfrom pathlib import Path\nfrom harness.workers import supervise\n'
        # Hold supervisor in a callback so it cannot clean up a normally exiting leader.
        'def started(pid):\n    time.sleep(15)\n'
        f'supervise([sys.executable, "-c", {leader!r}], cwd=".", prompt="", log="log", '
        f'timeout=15, cancelled=lambda:False, started=started, ownership_token=Path({str(persisted)!r}).read_text())\n'
    )
    independent = subprocess.Popen([sys.executable, '-c', WRITER], cwd=other)
    controller = subprocess.Popen([sys.executable, '-c', supervisor], cwd=owned,
                                  env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])},
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_for_writes(other / 'writes')
        wait_for_writes(owned / 'writes')
        with (owned / 'resource.lock').open('a') as lease:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            controller.kill()
            controller.wait(timeout=3)
            before = (owned / 'writes').stat().st_size
            time.sleep(.1)
            assert (owned / 'writes').stat().st_size > before, 'crash must leave a live detached writer'
            began = time.monotonic()
            assert cleanup(persisted.read_text()) is None
            assert time.monotonic() - began < 3.5
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = (owned / 'writes').stat().st_size
            other_before = (other / 'writes').stat().st_size
            time.sleep(.15)
            assert (owned / 'writes').stat().st_size == before
            assert (other / 'writes').stat().st_size > other_before
            assert independent.poll() is None
            assert cleanup(token) is None  # reconciliation may safely repeat
    finally:
        (owned / 'stop').touch()
        (other / 'stop').touch()
        if controller.poll() is None:
            controller.kill()
        controller.communicate(timeout=3)
        independent.wait(timeout=3)
        cleanup(token)


@pytest.mark.parametrize('token', ['', 'x' * 32, '1' * 31, '1' * 33,
                                  '11111111-1111-1111-1111-111111111111', 123])
def test_invalid_ownership_token_is_rejected_before_launch(tmp_path, token):
    from harness import workers
    with pytest.raises(ValueError, match='ownership'):
        supervise([sys.executable, '-c', 'raise SystemExit(99)'], cwd=tmp_path,
                  prompt='', log=tmp_path / 'log', timeout=1, cancelled=lambda:False,
                  ownership_token=token)
    assert not (tmp_path / 'log').exists()
    with pytest.raises(ValueError, match='ownership'):
        workers.cleanup_owned_attempt(token)


def test_recovery_skips_unidentified_unreadable_same_user_process(monkeypatch):
    import builtins
    from harness import workers
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'])
    try:
        original = builtins.open
        def denied(path, *args, **kwargs):
            if str(path) == f'/proc/{child.pid}/environ':
                raise PermissionError('cannot inspect unrelated same-user process')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(builtins, 'open', denied)
        assert workers.cleanup_owned_attempt(uuid.uuid4().hex) is None
        assert child.poll() is None
    finally:
        child.kill()
        child.wait(timeout=3)


def test_recovery_refuses_to_confirm_uninspectable_same_user_process(monkeypatch):
    from harness import workers
    def denied(*args):
        raise PermissionError('inspection facility unavailable')
    monkeypatch.setattr(os, 'pidfd_open', denied)
    with pytest.raises(OSError):
        workers.cleanup_owned_attempt(uuid.uuid4().hex)


@pytest.mark.parametrize('failure', ['signal', 'deadline'])
def test_recovery_fails_closed_for_proven_owned_process(tmp_path, monkeypatch, failure):
    from harness import workers
    token = uuid.uuid4().hex
    child = subprocess.Popen([sys.executable, '-c', WRITER], cwd=tmp_path,
                             env={**os.environ, 'GOOSNAV_WORKER_ATTEMPT': token})
    try:
        wait_for_writes(tmp_path / 'writes')
        with monkeypatch.context() as patch:
            def cannot_kill(*args):
                if failure == 'signal':
                    raise PermissionError('owned process signal denied')
                # Model an uninterruptible process: successful signal, no exit.
            patch.setattr(workers.signal, 'pidfd_send_signal', cannot_kill)
            began = time.monotonic()
            with pytest.raises(PermissionError if failure == 'signal' else TimeoutError):
                workers.cleanup_owned_attempt(token)
            assert time.monotonic() - began < 4
            assert child.poll() is None
    finally:
        child.kill()
        child.wait(timeout=3)


def test_recovery_refuses_to_confirm_unsupported_platform(monkeypatch):
    from harness import workers
    monkeypatch.setattr(workers, '_linux_ownership', lambda:False)
    with pytest.raises(OSError, match='Linux'):
        workers.cleanup_owned_attempt(uuid.uuid4().hex)


def test_live_cleanup_failure_is_not_a_retryable_dependency(tmp_path, monkeypatch):
    from harness import workers
    cleanup_error = getattr(workers, 'WorkerCleanupError', None)
    assert cleanup_error is not None, 'cleanup failures need a distinct non-retryable exception'
    token = uuid.uuid4().hex
    # The CLI has exited, but detached cleanup cannot be confirmed.
    def blocked(*args):
        raise PermissionError('owned pidfd signal denied')
    monkeypatch.setattr(workers, '_kill_detached', blocked)
    with pytest.raises(cleanup_error, match='owned pidfd signal denied') as error:
        supervise([sys.executable, '-c', 'pass'], cwd=tmp_path, prompt='',
                  log=tmp_path / 'log', timeout=5, cancelled=lambda:False,
                  ownership_token=token)
    assert error.value.ownership_token == token
