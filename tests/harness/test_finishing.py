"""A creative deadline must leave time for a real, truthfully labelled deliverable."""
import json
import os
import sys
import subprocess
from pathlib import Path

import pytest

from harness.config import load_config
from harness.execution import Budget, policy
from harness.store import Store
from harness.workflow import Engine, build_tasks


def test_medium_reserves_finishing_before_hard_limit(monkeypatch):
    from harness import execution
    clock = [0.0]
    monkeypatch.setattr(execution.time, 'monotonic', lambda: clock[0])
    c = load_config(overrides={'generation': {'effort': 'medium'}, 'output': {'target_seconds': 9}})
    state = {'config': c, 'execution': policy(c), 'tasks': build_tasks(1, modern=True)}
    budget = Budget(state, lambda *a: None)
    assert budget.production_remaining() == 720
    clock[0] = 721
    with pytest.raises(execution.FinishRequired):
        budget.check_production()
    assert budget.remaining() == 779
    assert state['execution']['hard_seconds'] == 1500


def test_valid_animation_keeps_more_creative_time_for_editing():
    c = load_config(overrides={'generation': {'effort': 'high'}, 'output': {'target_seconds': 9}})
    state = {'config': c, 'execution': policy(c), 'tasks': build_tasks(1, modern=True)}
    budget = Budget(state, lambda *a: None)
    assert 2099 < budget.production_remaining() <= 2100
    next(t for t in state['tasks'] if t['stage'] == 'animate')['status'] = 'succeeded'
    assert 2699 < budget.production_remaining() <= 2700


def test_finishing_signal_terminates_real_worker(tmp_path):
    from harness.execution import FinishRequired
    from harness.workers import supervise
    pids = []
    def stop():
        raise FinishRequired('finish now')
    with pytest.raises(FinishRequired):
        supervise([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=tmp_path,
                  prompt='', log=tmp_path/'log', timeout=30, cancelled=stop, started=pids.append)
    with pytest.raises(ProcessLookupError):
        os.kill(pids[0], 0)


def prepared_run(tmp_path, count=1):
    store = Store(tmp_path/'home')
    c = load_config(overrides={'count': count, 'output': {'target_seconds': 9, 'cta': False, 'folder': str(tmp_path/'out'),
        'end_card_clips': [{'product': 'Example Book', 'asset_id': 'product-floating'}]}})
    s = store.create(c)
    s['tasks'] = build_tasks(count, modern=True)
    for t in s['tasks'][:3]:
        t.update(status='succeeded', result={'files': []})
    s['tasks'][1]['result']['scripts'] = [dict(id=f's{i}', title=f'Story {i}', product='Example Book') for i in range(count)]
    s['tasks'][2]['result']['selected'] = [f's{i}' for i in range(count)]
    s.update(sources=[], sources_ready=True)
    return store, s


def test_already_approved_film_is_packaged_not_replaced(tmp_path, monkeypatch):
    store, s = prepared_run(tmp_path)
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] != 'package':
            t.update(status='succeeded', result={'files': []})
    next(t for t in s['tasks'] if t['stage'] == 'creative_qa')['result']['verdict'] = 'pass'
    package = next(t for t in s['tasks'] if t['stage'] == 'package')
    engine = Engine(store); engine.budget = Budget(s, store.save)
    monkeypatch.setattr(engine, 'builtin_task', lambda state, task, root, **kw: task.update(status='succeeded', result={'files': []}))
    engine.finish_pending(s, 'deadline')
    assert package['status'] == 'succeeded'
    assert not s.get('fallbacks')


def test_approved_deadline_delivery_does_not_rearchive_heavy_story_sources(tmp_path):
    import zipfile
    from harness.contracts import digest
    store, s = prepared_run(tmp_path)
    s['fallbacks'] = {'0': {'status':'rejected'}}
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] != 'package':
            t.update(status='succeeded', result={'files': []})
    frame = next(t for t in s['tasks'] if t['stage'] == 'frame')
    original = tmp_path/'approved.mp4'; original.write_bytes(b'accepted film fixture')
    next(t for t in s['tasks'] if t['stage'] == 'edit')['result']['master'] = str(original)
    frame['result'] = {'master': str(original), 'files': [{'path': str(original), 'kind': 'video', 'sha256': digest(original)}]}
    source = tmp_path/'large-scene.blend'; source.write_bytes(b'accepted source fixture')
    next(t for t in s['tasks'] if t['stage'] == 'assets')['result']['files'] = [
        {'path': str(source), 'kind': 'source', 'sha256': digest(source)}]
    next(t for t in s['tasks'] if t['stage'] == 'creative_qa')['result']['verdict'] = 'pass'
    engine = Engine(store); engine.budget = Budget(s, store.save)
    engine.finish_pending(s, 'deadline')
    out = Path(s['config']['output']['folder'])/s['id']
    assert (out/'ad-01.mp4').read_bytes() == original.read_bytes()
    with zipfile.ZipFile(out/'ad-01.zip') as archive:
        assert not any('large-scene.blend' in name for name in archive.namelist())
    assert s['fallbacks']['0']['status'] == 'replaced_with_story'


def test_already_exhausted_resume_still_reaps_orphan_worker(tmp_path):
    from harness.workflow import process_identity
    store, s = prepared_run(tmp_path)
    worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
    try:
        s['tasks'][0].update(status='running', result=None,
            attempts=[{'pid': worker.pid, 'identity': process_identity(worker.pid)}])
        s['execution']['active_seconds'] = s['execution']['hard_seconds'] + 1
        store.save(s, 'fixture')
        assert Engine(store).run(s['id'])['status'] == 'budget_exhausted'
        assert worker.wait(timeout=1) != 0
    finally:
        if worker.poll() is None:
            worker.kill(); worker.wait()


def test_zip_deadline_is_checked_during_copy_not_only_before_it(tmp_path):
    from harness.media import package
    from harness.contracts import digest, ContractError
    source = tmp_path/'large.bin'; source.write_bytes(b'x' * (3 * 1024 * 1024))
    inputs = {'film': {'files': [{'path': str(source), 'sha256': digest(source)}]}}
    calls = []
    def checkpoint():
        calls.append(1)
        if len(calls) == 4:
            raise ContractError('cancelled during source copy')
    with pytest.raises(ContractError, match='cancelled during'):
        package(inputs, {'id': 'fixture', 'config': {}, 'models': {}}, tmp_path, checkpoint=checkpoint)
    assert len(calls) == 4


def test_promotion_checks_control_before_acceptance(tmp_path):
    from harness.contracts import ContractError, promote
    (tmp_path/'final.mp4').write_bytes(b'x' * (3 * 1024 * 1024))
    calls = []
    def checkpoint():
        calls.append(1)
        if len(calls) == 3:
            raise ContractError('paused during promotion')
    with pytest.raises(ContractError, match='paused during'):
        promote({'files': [{'path': 'final.mp4', 'kind': 'video'}]}, tmp_path, tmp_path/'accepted', checkpoint=checkpoint)
    assert not (tmp_path/'accepted/accepted.json').exists()


def test_history_hashes_also_poll_finishing_control(tmp_path):
    from harness.contracts import ContractError, digest
    store, s = prepared_run(tmp_path)
    source = tmp_path/'accepted.blend'; source.write_bytes(b'x' * (3 * 1024 * 1024))
    s['tasks'][0]['result']['files'] = [{'path': str(source), 'sha256': digest(source)}]
    calls = []
    def checkpoint():
        calls.append(1)
        if len(calls) == 3:
            raise ContractError('cancelled during history verification')
    with pytest.raises(ContractError, match='cancelled during history'):
        Engine(store).verify_history(s, checkpoint=checkpoint)


def test_completed_package_can_deliver_after_generation_budget_is_spent(tmp_path, monkeypatch):
    store, s = prepared_run(tmp_path)
    next(t for t in s['tasks'] if t['stage'] == 'package').update(status='succeeded', result={'files': []})
    s['status'] = 'complete'
    s['execution']['active_seconds'] = s['execution']['hard_seconds'] + 1
    store.save(s, 'fixture')
    delivered = []
    engine = Engine(store)
    monkeypatch.setattr(engine, 'deliver_finished', lambda state: delivered.append(state['id']))
    assert engine.run(s['id'])['status'] == 'complete'
    assert delivered == [s['id']]


def test_checked_copy_atomically_replaces_readonly_export(tmp_path):
    from harness.contracts import copy_checked, ContractError
    source=tmp_path/'corrected.mp4';source.write_bytes(b'full story')
    target=tmp_path/'ad-01.mp4';target.write_bytes(b'old end card');target.chmod(0o444)
    def cancelled():
        raise ContractError('cancelled')
    with pytest.raises(ContractError,match='cancelled'):
        copy_checked(source,target,cancelled)
    assert target.read_bytes()==b'old end card'
    copy_checked(source,target,lambda:None)
    assert target.read_bytes()==b'full story'
    assert sorted(p.name for p in tmp_path.iterdir())==['ad-01.mp4','corrected.mp4']
