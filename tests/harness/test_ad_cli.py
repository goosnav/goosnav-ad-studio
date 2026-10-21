"""Delivery presentation over real saved states; no upload worker or API calls."""
import copy
import runpy
import sys
import time
from pathlib import Path

import pytest

from harness import delivery_queue, gui
from harness.config import load_config
from harness.delivery import _file_receipt, _names
from harness.store import Store
from harness.workflow import build_tasks


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def saved_run(tmp_path, monkeypatch):
    store = Store(tmp_path / 'state')
    state = store.create(load_config(None, {
        'output': {'folder': str(tmp_path / 'videos')},
        'delivery': {'drive': 'test-drive:finished'},
    }))
    state.update(status='complete', tasks=build_tasks(1, modern=True, compact=True))
    for task in state['tasks']:
        task.update(status='succeeded', result={})
    folder = Path(state['config']['output']['folder']) / state['id']
    folder.mkdir(parents=True)
    (folder / 'ad-01.mp4').write_bytes(b'packaged-video')
    store.save(state, 'packaged_fixture')
    # UI tests never launch a queue worker or touch the user's live home/config.
    monkeypatch.setattr(delivery_queue, 'worker_running', lambda _: False)
    monkeypatch.setattr(gui, 'LOCAL_CONFIG', tmp_path / 'absent-config.json')
    module = runpy.run_path(str(ROOT / 'ad'))
    namespace = module['summary'].__globals__
    monkeypatch.setitem(namespace, 'HOME', store.root)

    def harness(command, *args, **kwargs):
        if command == 'list':
            return [{'id': s['id'], 'created': s['created'], 'status': s['status']}
                    for s in store.list()]
        assert command == 'status'
        return store.get(args[0])

    monkeypatch.setitem(namespace, 'harness', harness)
    handler = gui.Handler.__new__(gui.Handler)
    handler.store = store
    return store, state, module, handler


@pytest.mark.parametrize('delivery', [
    None,
    ['malformed-receipt'],
    {'status': 'retrying', 'attempts': 5, 'retry_failures': 5,
     'next_retry_at': time.time() + 900, 'error': 'rateLimitExceeded', 'verified': {}},
    {'status': 'uploading', 'verified': {}},
    {'status': 'failed', 'error': 'temporary Drive failure', 'verified': {}},
])
@pytest.mark.parametrize('worker_healthy', [False, True])
def test_complete_generation_displays_awaiting_upload_without_manual_step(
        saved_run, delivery, worker_healthy, monkeypatch, capsys):
    store, state, module, handler = saved_run
    monkeypatch.setattr(delivery_queue, 'worker_running', lambda _: worker_healthy)
    if delivery is not None:
        state['delivery'] = copy.deepcopy(delivery)
    store.save(state, 'pending_fixture')
    before = store.get(state['id'])
    events = store.events(state['id'])

    assert module['summary'](state['id']) == 'waiting_delivery'
    output = capsys.readouterr().out
    assert 'awaiting_upload' in output.splitlines()[0]
    assert 'Drive:' in output
    health = 'worker running' if worker_healthy else 'worker not running'
    assert health in output
    assert './ad upload' not in output
    for body in (handler.index(), handler.run_page(state['id'])):
        assert 'class="awaiting_upload">awaiting_upload' in body
        assert health in body
    assert store.get(state['id']) == before
    assert store.events(state['id']) == events


def test_list_uses_pending_delivery_status_from_saved_run(saved_run, monkeypatch, capsys):
    store, state, module, _ = saved_run
    monkeypatch.setattr(sys, 'argv', ['ad', 'list'])
    assert module['main']() == 0
    assert capsys.readouterr().out.strip().endswith('awaiting_upload')
    assert store.get(state['id'])['status'] == 'complete'


@pytest.mark.parametrize('control', ['pause', 'cancel'])
def test_pending_paused_delivery_is_explicit_and_watch_can_stop(saved_run, control, capsys):
    store, state, module, handler = saved_run
    store.control(state['id'], control)
    assert module['summary'](state['id']) == 'complete'
    output = capsys.readouterr().out
    assert 'awaiting_upload' in output.splitlines()[0]
    word = 'paused' if control == 'pause' else 'cancelled'
    assert word in output
    assert word in handler.run_page(state['id'])
    assert './ad upload' not in output


def test_watch_keeps_following_until_delivery_is_verified(saved_run, monkeypatch, capsys):
    store, state, module, handler = saved_run
    sleeps = []

    def finish_delivery(seconds):
        sleeps.append(seconds)
        names = _names(state, [0])
        state['delivery'] = {
            'status': 'uploaded', 'remote': 'test-drive:finished',
            'target': {'remote': 'test-drive:finished', 'flags': []},
            'names': names, 'files': list(names.values()),
            'verified': {'ad-01.mp4': _file_receipt(
                Path(state['config']['output']['folder']) / state['id'] / 'ad-01.mp4',
                names['ad-01.mp4'])},
        }
        store.save(state, 'verified_fixture')

    monkeypatch.setattr(sys, 'argv', ['ad', 'watch', state['id']])
    monkeypatch.setattr(module['main'].__globals__['time'], 'sleep', finish_delivery)
    assert module['main']() == 0
    output = capsys.readouterr().out
    assert 'awaiting_upload' in output
    assert 'videos uploaded' in output
    assert sleeps == [60]
    assert 'class="complete">complete' in handler.run_page(state['id'])
    assert module['summary'](state['id']) == 'complete'
    assert 'awaiting_upload' not in capsys.readouterr().out

    # A saved success must not mask changed local bytes while the queue catches up.
    folder = Path(state['config']['output']['folder']) / state['id']
    (folder / 'ad-01.mp4').write_bytes(b'repackaged-video')
    before = store.get(state['id'])
    assert module['summary'](state['id']) == 'waiting_delivery'
    output = capsys.readouterr().out
    assert 'awaiting_upload' in output.splitlines()[0]
    assert 'videos uploaded' not in output
    assert '0/1 videos verified' in output
    assert 'class="awaiting_upload">awaiting_upload' in handler.run_page(state['id'])
    assert store.get(state['id']) == before


def test_local_only_generation_remains_complete(saved_run, capsys):
    store, state, module, handler = saved_run
    state['config']['delivery']['drive'] = ''
    store.save(state, 'local_only_fixture')
    assert module['summary'](state['id']) == 'complete'
    output = capsys.readouterr().out
    assert 'awaiting_upload' not in output
    assert 'Drive:' not in output
    assert 'class="complete">complete' in handler.run_page(state['id'])


@pytest.mark.parametrize(('own_delay', 'effective_delay'), [(60, 300), (600, 600)])
def test_retry_display_uses_effective_queue_deadline(
        saved_run, own_delay, effective_delay, monkeypatch, capsys):
    store, state, module, handler = saved_run
    monkeypatch.setattr(time, 'time', lambda: 1700000000.0)
    state['delivery'] = {'status': 'retrying', 'next_retry_at': 1700000000.0 + own_delay,
                         'verified': {}, 'error': 'rateLimitExceeded'}
    store.save(state, 'retry_fixture')
    store.cooldown('drive-delivery', 300)
    before = store.get(state['id'])
    events = store.events(state['id'])
    module['summary'](state['id'])
    for text in (capsys.readouterr().out, handler.run_page(state['id']), handler.index()):
        assert f'(in {effective_delay}s)' in text
        assert time.strftime('%H:%M:%S', time.localtime(1700000000 + effective_delay)) in text
        assert 'rateLimitExceeded' in text
    assert store.get(state['id']) == before
    assert store.events(state['id']) == events
