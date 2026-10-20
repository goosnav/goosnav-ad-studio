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
    assert budget.production_remaining() == 960
    clock[0] = 961
    with pytest.raises(execution.FinishRequired):
        budget.check_production()
    assert budget.remaining() == 539
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
    c = load_config(overrides={'count': count, 'output': {'target_seconds': 9, 'folder': str(tmp_path/'out'),
        'end_card_clips': [{'product': 'Example Book', 'asset_id': 'product-floating'}]}})
    s = store.create(c)
    s['tasks'] = build_tasks(count, modern=True)
    for t in s['tasks'][:3]:
        t.update(status='succeeded', result={'files': []})
    s['tasks'][1]['result']['scripts'] = [dict(id=f's{i}', title=f'Story {i}', product='Example Book') for i in range(count)]
    s['tasks'][2]['result']['selected'] = [f's{i}' for i in range(count)]
    s.update(sources=[], sources_ready=True)
    return store, s


def fake_film(script, config, work, cancelled):
    assert script['product'] == 'Example Book'
    assert not cancelled()
    (work/'final.mp4').write_bytes(b'validated film fixture')
    (work/'qa.json').write_text('{}')
    return {'summary': 'Product-only fallback', 'master': 'final.mp4', 'delivery_mode': 'product_only',
            'files': [{'path': 'final.mp4', 'kind': 'video'}, {'path': 'qa.json', 'kind': 'notes'}]}


def test_cutoff_finishes_packages_and_delivers_without_another_model(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    s['execution']['active_seconds'] = 970
    store.save(s, 'fixture')
    monkeypatch.setattr(finishing, 'product_film', fake_film)
    calls = []
    engine = Engine(store, execute=lambda *a, **k: pytest.fail('must not start a model'))
    monkeypatch.setattr(engine, 'deliver_finished', lambda state: calls.append(
        sum(t['stage'] == 'package' and t['status'] == 'succeeded' for t in state['tasks'])))
    result = engine.run(s['id'])
    assert result['status'] == 'complete'
    assert result['fallbacks']['0']['mode'] == 'product_only'
    assert next(t for t in result['tasks'] if t['stage'] == 'assets')['status'] == 'skipped'
    assert (Path(s['config']['output']['folder'])/s['id']/'ad-01.mp4').is_file()
    assert 1 in calls
    assert store.get(s['id'])['fallbacks'] == result['fallbacks']


def test_fallback_keeps_completed_ads_and_continues_after_one_unavailable_clip(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path, count=3)
    done = next(t for t in s['tasks'] if t['ad'] == 0 and t['stage'] == 'package')
    done.update(status='succeeded', result={'summary': 'original', 'files': []})
    def render(script, *args):
        if script['title'] == 'Story 1':
            raise ValueError('approved clip unavailable')
        return fake_film(script, *args)
    monkeypatch.setattr(finishing, 'product_film', render)
    engine = Engine(store)
    engine.budget = Budget(s, store.save)
    engine.finish_pending(s, 'creative time used up')
    assert done['result']['summary'] == 'original'
    assert s['fallbacks']['1']['status'] == 'failed'
    assert s['fallbacks']['2']['status'] == 'complete'
    assert engine.aggregate(s) == 'partial'


def test_cancel_does_not_render_or_deliver_fallback(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    store.control(s['id'], 'cancel')
    monkeypatch.setattr(finishing, 'product_film', lambda *a: pytest.fail('cancelled'))
    engine = Engine(store); engine.budget = Budget(s, store.save)
    engine.finish_pending(s, 'deadline')
    assert s['status'] == 'cancelled'
    assert not s.get('fallbacks')


def test_terminal_creative_failure_uses_reserve_without_waiting_for_cutoff(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    next(t for t in s['tasks'] if t['stage'] == 'assets').update(status='failed', feedback='repair limit')
    s['execution']['active_seconds'] = 600
    store.save(s, 'fixture')
    monkeypatch.setattr(finishing, 'product_film', fake_film)
    from test_workflow import fake_models
    engine = Engine(store, execute=lambda *a, **k: pytest.fail('blocked ad needs no models'), resolve=fake_models)
    result = engine.run(s['id'])
    assert result['status'] == 'complete'
    assert result['fallbacks']['0']['status'] == 'complete'


def test_creative_timeout_with_hard_time_left_finishes_and_reconciles_first(tmp_path, monkeypatch):
    from harness import finishing
    from harness.execution import BudgetExceeded
    from test_workflow import fake_models
    store, s = prepared_run(tmp_path)
    s['execution']['active_seconds'] = 959
    store.save(s, 'fixture')
    monkeypatch.setattr(finishing, 'product_film', fake_film)
    engine = Engine(store, execute=lambda *a, **k: None, resolve=fake_models)
    order = []
    monkeypatch.setattr(engine, 'reconcile', lambda state: order.append('reconciled'))
    def expired(*args):
        order.append('creative')
        raise BudgetExceeded('production deadline expired during validation')
    monkeypatch.setattr(engine, 'agent_task', expired)
    result = engine.run(s['id'])
    assert order == ['reconciled', 'creative']
    assert result['status'] == 'complete'
    assert result['execution']['hard_seconds'] - result['execution']['active_seconds'] > 500


def test_cutoff_reconciles_before_finishing_without_resolving_models(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    s['execution']['active_seconds'] = 970
    store.save(s, 'fixture')
    order = []
    engine = Engine(store, resolve=lambda *a: pytest.fail('no model lookup on finishing'))
    monkeypatch.setattr(engine, 'reconcile', lambda state: order.append('reconciled'))
    def render(*args):
        order.append('rendered')
        return fake_film(*args)
    monkeypatch.setattr(finishing, 'product_film', render)
    assert engine.run(s['id'])['status'] == 'complete'
    assert order == ['reconciled', 'rendered']


@pytest.mark.parametrize('action', ['pause', 'cancel'])
def test_control_during_finishing_wins_over_completion(tmp_path, monkeypatch, action):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    s['execution']['active_seconds'] = 970
    store.save(s, 'fixture')
    def render(*args):
        result = fake_film(*args)
        store.control(s['id'], action)
        return result
    monkeypatch.setattr(finishing, 'product_film', render)
    engine = Engine(store)
    s = engine.run(s['id'])
    assert s['status'] == ('paused' if action == 'pause' else 'cancelled')
    assert not any(t['stage'] == 'package' and t['status'] == 'succeeded' for t in s['tasks'])


def test_already_approved_film_is_packaged_not_replaced(tmp_path, monkeypatch):
    from harness import finishing
    store, s = prepared_run(tmp_path)
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] != 'package':
            t.update(status='succeeded', result={'files': []})
    next(t for t in s['tasks'] if t['stage'] == 'creative_qa')['result']['verdict'] = 'pass'
    package = next(t for t in s['tasks'] if t['stage'] == 'package')
    monkeypatch.setattr(finishing, 'product_film', lambda *a: pytest.fail('approved film exists'))
    engine = Engine(store); engine.budget = Budget(s, store.save)
    monkeypatch.setattr(engine, 'builtin_task', lambda state, task, root, **kw: task.update(status='succeeded', result={'files': []}))
    engine.finish_pending(s, 'deadline')
    assert package['status'] == 'succeeded'
    assert not s.get('fallbacks')


def test_approved_deadline_delivery_does_not_rearchive_heavy_story_sources(tmp_path):
    import zipfile
    from harness.contracts import digest
    store, s = prepared_run(tmp_path)
    for t in s['tasks']:
        if t['ad'] == 0 and t['stage'] != 'package':
            t.update(status='succeeded', result={'files': []})
    frame = next(t for t in s['tasks'] if t['stage'] == 'frame')
    original = tmp_path/'approved.mp4'; original.write_bytes(b'accepted film fixture')
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
    assert not s.get('fallbacks')


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


def test_product_alias_keeps_selected_name_even_when_footage_is_shared(tmp_path):
    from harness.finishing import product_film
    from test_end_card_clips import fixture
    _, source, work = fixture(tmp_path)
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame runtime unavailable')
    c = load_config('harness.local.json')
    c['output'].update(source['output'], width=216, height=270, target_seconds=2, min_seconds=2, max_seconds=2)
    c['output']['end_card_clips'].append({'product': 'Selected Edition', 'asset_id': 'product-floating'})
    r = product_film({'product': 'Selected Edition'}, c, work, lambda: False)
    assert r['product'] == 'Selected Edition'


def test_real_product_film_is_moving_silent_and_relocatable(tmp_path):
    from harness.finishing import product_film
    from test_end_card_clips import fixture
    _, source, work = fixture(tmp_path)
    if not Path('harness.local.json').is_file():
        pytest.skip('local Frame runtime unavailable')
    c = load_config('harness.local.json')
    c['output'].update(source['output'], width=216, height=270, target_seconds=2, min_seconds=2, max_seconds=2)
    result = product_film({'title': 'Unused story', 'product': 'Example Book', 'cta': 'Unused claim'}, c, work, lambda: False)
    report = json.loads((work/'qa.json').read_text())
    assert report['video']['distinct_sampled_frames'] > 1
    assert report['sound']['intentional_silence'] is True
    assert result['delivery_mode'] == 'product_only'
    request = json.loads((work/'frame.json').read_text())
    assert request['jobs'][0]['settings']['title']['text'] == 'Example Book'
    assert request['jobs'][0]['settings']['link']['color'] == '#0000ee'


def test_no_approved_product_clip_cannot_fake_a_success(tmp_path):
    from harness.finishing import product_film
    from harness.contracts import ContractError
    with pytest.raises(ContractError, match='approved|configured'):
        product_film({'product': 'Unknown'}, load_config(), tmp_path, lambda: False)
    assert not (tmp_path/'final.mp4').exists()
