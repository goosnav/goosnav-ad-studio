"""Real multiprocessing coordination with only Blender/FFmpeg execution replaced."""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import runpy
import struct
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
import zlib

import pytest


def _png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0' * ((width * 3 + 1) * height))) + chunk(b'IEND', b''))


def _job(root, name, seconds, entered, release, started, events, hold='draw', studio=False,
         timeout=5, output_name=None, scene_name='scene.blend'):
    root = Path(root)
    # Real defaults must agree despite the environment set by worker supervision.
    os.environ['TMPDIR'] = str(root / name / '.tmp')
    Path(os.environ['TMPDIR']).mkdir(parents=True)
    os.chdir(root)
    os.environ['XDG_STATE_HOME'] = str(root / 'user-state')
    os.environ.pop('STUDIO_RENDER_LOCK', None)
    from studio import config
    config._LOCAL.pop('render_lock', None)
    from harness import render
    scene = SimpleNamespace(render=SimpleNamespace(image_settings=SimpleNamespace()), eevee=SimpleNamespace())
    scene.frame_set = lambda frame: setattr(scene, 'frame', frame)

    def draw(**kwargs):
        events.put((name, 'draw', scene.frame))
        if hold == 'draw':
            entered.set()
            assert release.wait(10)
        Path(scene.render.filepath).write_bytes(_png(scene.render.resolution_x, scene.render.resolution_y))

    bpy = SimpleNamespace(context=SimpleNamespace(scene=scene), data=SimpleNamespace(images=[], libraries=[]),
                          ops=SimpleNamespace(render=SimpleNamespace(render=draw)))

    def run(argv, **kwargs):
        if '--python-expr' in argv:
            return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')
        if '--python' in argv:
            with patch.object(sys, 'argv', argv), patch.dict(sys.modules, {'bpy': bpy}):
                runpy.run_path(argv[argv.index('--python') + 1])
        else:
            events.put((name, 'encode', kwargs.get('timeout')))
            entered.set()
            if hold == 'encode' or studio:
                assert release.wait(10)
            if not studio:
                Path(argv[-1]).write_bytes(b'encoded fixture')
        return subprocess.CompletedProcess(argv, 0)

    started.set()
    with patch.object(render.subprocess, 'run', run):
        if studio:
            from studio.__main__ import with_lock
            with_lock(['fixture-blender'])
        else:
            result = render.render(root / scene_name, root / 'audio.wav', root / (output_name or f'{name}.mp4'),
                                   width=64, height=64, fps=1, seconds=seconds, timeout=timeout)
            events.put((name, 'result', result))


def _launch(ctx, root, name, seconds, events, hold='draw', studio=False, **kwargs):
    entered, release, started = ctx.Event(), ctx.Event(), ctx.Event()
    child = ctx.Process(target=_job, args=(str(root), name, seconds, entered, release, started,
                                          events, hold, studio), kwargs=kwargs)
    child.start()
    assert started.wait(5)
    return child, entered, release


def _finish(jobs):
    for child, _, release in jobs:
        release.set()
    for child, _, _ in jobs:
        child.join(10)
        if child.is_alive():
            child.terminate()
            child.join(5)
        assert child.exitcode == 0


def _inputs(root):
    (root / 'scene.blend').write_bytes(b'fixture scene')
    (root / 'audio.wav').write_bytes(b'fixture audio')


def test_harness_and_studio_coordinate_despite_distinct_tmpdirs(tmp_path):
    _inputs(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events)
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 1, events, studio=True)
        jobs.append(second)
        assert not second[1].wait(.3), 'studio started while harness held the GPU'
        first[2].set()
        assert second[1].wait(5)
    finally:
        _finish(jobs)


@pytest.mark.parametrize('hold', ['draw', 'encode'])
def test_same_cache_writers_wait_and_reuse_verified_frames(tmp_path, hold):
    _inputs(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events, hold=hold)
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 2, events)
        jobs.append(second)
        assert not second[1].wait(.3), 'second cache writer entered before the first finished'
        first[2].set()
        assert second[1].wait(5)
    finally:
        _finish(jobs)
    messages = []
    while len([m for m in messages if m[1] == 'result']) < 2:
        messages.append(events.get(timeout=5))
    assert sorted(m[2] for m in messages if m[1] == 'draw') == [1, 2]
    cache = next((tmp_path / '.render-cache').iterdir())
    hashes = json.loads((cache / 'frames.json').read_text())
    assert set(hashes) == {'000001.png', '000002.png'}
    assert all(hashlib.sha256((cache / name).read_bytes()).hexdigest() == value for name, value in hashes.items())


def _wait_for_state(path, predicate):
    until = time.monotonic() + 6
    while time.monotonic() < until:
        if path.exists():
            value = json.loads(path.read_text())
            if predicate(value):
                return value
        time.sleep(.02)
    pytest.fail('Resource wait state did not reach the expected condition')


@pytest.mark.parametrize('gpu_wait', [True, False])
def test_wait_heartbeats_and_does_not_consume_render_timeout(tmp_path, gpu_wait):
    _inputs(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events, hold='encode', studio=gpu_wait)
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 2, events, timeout=.5)
        jobs.append(second)
        marker = tmp_path / '.resource-wait.json'
        initial = _wait_for_state(marker, lambda state: state['pid'] == second[0].pid)
        heartbeat = _wait_for_state(marker, lambda state: state['updated_at'] > initial['updated_at'] + 1)
        assert heartbeat['started_at'] == initial['started_at']
        assert not second[1].is_set()
        second[2].set()
        first[2].set()
    finally:
        _finish(jobs)
    messages = []
    while not any(m[:2] == ('second', 'result') for m in messages):
        messages.append(events.get(timeout=5))
    result = next(m[2] for m in messages if m[:2] == ('second', 'result'))
    assert result['resource_wait_seconds'] > 1
    assert result['frames'] == 2
    assert not marker.exists()


def test_same_output_with_different_caches_is_exclusive(tmp_path):
    _inputs(tmp_path)
    (tmp_path / 'other.blend').write_bytes(b'different scene')
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events, hold='encode', output_name='shared.mp4')
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 1, events, output_name='shared.mp4', scene_name='other.blend')
        jobs.append(second)
        state = _wait_for_state(tmp_path / '.resource-wait.json', lambda state: state['pid'] == second[0].pid)
        assert '.render-writers' in state['resource']
        assert not second[1].is_set()
        first[2].set()
        assert second[1].wait(5)
    finally:
        _finish(jobs)
    assert (tmp_path / 'shared.mp4').read_bytes() == b'encoded fixture'


def test_gpu_is_available_to_studio_during_harness_encoding(tmp_path):
    _inputs(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events, hold='encode')
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 1, events, studio=True)
        jobs.append(second)
        assert second[1].wait(5), 'FFmpeg encoding must not hold the global Blender lease'
    finally:
        _finish(jobs)


def test_wait_state_keeps_other_waiters_when_one_acquires(tmp_path):
    _inputs(tmp_path)
    ctx = multiprocessing.get_context('spawn')
    events = ctx.Queue()
    first = _launch(ctx, tmp_path, 'first', 1, events, studio=True)
    jobs = [first]
    try:
        assert first[1].wait(5)
        second = _launch(ctx, tmp_path, 'second', 1, events, studio=True)
        jobs.append(second)
        third = _launch(ctx, tmp_path, 'third', 1, events, studio=True)
        jobs.append(third)
        marker = tmp_path / '.resource-wait.json'
        state = _wait_for_state(marker, lambda state: len(state['waiters']) == 2)
        assert {r['pid'] for r in state['waiters']} == {second[0].pid, third[0].pid}
        first[2].set()
        state = _wait_for_state(marker, lambda state: len(state['waiters']) == 1)
        assert state['pid'] in {second[0].pid, third[0].pid}
    finally:
        _finish(jobs)
    assert not marker.exists()


def _probe_lease(lock, marker, started, acquired):
    from harness.resources import resource_lease
    started.set()
    with resource_lease(lock, wait_file=marker):
        acquired.set()


def test_resource_child_retains_lease_after_wrapper_closes_it(tmp_path):
    from harness.resources import resource_lease
    lock = tmp_path / 'render.lock'
    marker = tmp_path / '.resource-wait.json'
    ctx = multiprocessing.get_context('spawn')
    started, acquired = ctx.Event(), ctx.Event()
    with resource_lease(lock, wait_file=marker) as lease:
        child = subprocess.Popen([sys.executable, '-c',
                                  'import sys; print("ready",flush=True); sys.stdin.readline()'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                 pass_fds=(lease.fd,))
        import select
        assert select.select([child.stdout], [], [], 5)[0]
        assert child.stdout.readline().strip() == 'ready'
    probe = ctx.Process(target=_probe_lease, args=(str(lock), str(marker), started, acquired))
    probe.start()
    try:
        assert started.wait(5)
        _wait_for_state(marker, lambda state: state['pid'] == probe.pid)
        assert not acquired.is_set(), 'closing the wrapper must not release its child\'s lease'
        child.communicate('\n', timeout=5)
        assert acquired.wait(5)
    finally:
        if child.poll() is None:
            child.communicate('\n', timeout=5)
        probe.join(5)
        if probe.is_alive():
            probe.terminate()
            probe.join(5)
    assert child.returncode == probe.exitcode == 0
    assert not marker.exists()


def test_scene_changed_while_waiting_for_gpu_is_not_rendered(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from harness import render
    _inputs(tmp_path)
    gpu_path = tmp_path / 'gpu.lock'
    original = render.resource_lease

    @contextmanager
    def acquire(path):
        with original(path, wait_file=tmp_path / '.resource-wait.json') as lease:
            if path == gpu_path:
                (tmp_path / 'scene.blend').write_bytes(b'changed while queued')
            yield lease

    def run(argv, **kwargs):
        assert '--python-expr' in argv, 'Changed scene reached rendering'
        return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')

    monkeypatch.setattr(render, 'resource_lease', acquire)
    monkeypatch.setattr(render, 'render_lock_path', lambda: gpu_path)
    monkeypatch.setattr(render.subprocess, 'run', run)
    with pytest.raises(ValueError, match='Scene changed'):
        render.render(tmp_path / 'scene.blend', tmp_path / 'audio.wav', tmp_path / 'out.mp4')
