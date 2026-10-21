"""Production targets guide scope; they must not terminate useful work."""
from harness.config import load_config
from harness.execution import Budget, policy
from harness.workflow import build_tasks


def state():
    c = load_config(overrides={'generation': {'effort': 'low'}, 'output': {'target_seconds': 7}})
    return {'config': c, 'tasks': build_tasks(1, compact=True), 'execution': policy(c)}


def test_existing_compact_runs_migrate_without_resetting_time_or_work():
    s = state()
    s['execution'].update(version=1, active_seconds=590, hard_seconds=584)
    s['tasks'][1]['attempts'] = [{'kind': 'timeout', 'revision': 0}]
    b = Budget(s, lambda *a: None)
    b.check_production()
    assert b.data['version'] == 2
    assert b.spent() >= 590
    assert s['tasks'][1]['attempts'][0]['kind'] == 'timeout'
    assert b.remaining() == float('inf')


def test_target_overrun_never_starves_animation_repair_or_finishing():
    s = state()
    b = Budget(s, lambda *a: None)
    before = b.stage_seconds(s['tasks'][1], 14400)
    b.data['active_seconds'] = 10000
    b.check_production()
    assert b.stage_seconds(s['tasks'][1], 14400) == before
    assert b.stage_seconds(s['tasks'][2], 900) == 900
    assert b.production_remaining() == float('inf')
    b.tick(True)
    assert b.data['mode'] == 'finish_existing'
    assert len(b.data['changes']) == 1
    b.tick(True)
    assert len(b.data['changes']) == 1


def test_script_repair_has_real_allowance_not_a_subsecond_remainder():
    s = state()
    s['tasks'][0]['attempts'] = [{'started': 100, 'ended': 160, 'revision': 0}]
    assert Budget(s, lambda *a: None).stage_seconds(s['tasks'][0], 600) == 60


def test_legacy_graph_keeps_explicit_historical_ceiling():
    from harness.execution import BudgetExceeded
    import pytest
    s = state()
    s['tasks'] = build_tasks(1, modern=True)
    s['execution'].update(version=1, active_seconds=10000)
    with pytest.raises(BudgetExceeded):
        Budget(s, lambda *a: None).check()


def test_resource_wait_is_not_charged_to_active_target(monkeypatch):
    now = [0.0]
    monkeypatch.setattr('harness.execution.time.monotonic', lambda: now[0])
    b = Budget(state(), lambda *a: None)
    now[0] = 5
    b.tick(waiting=True)
    now[0] = 305
    assert b.spent() == 5
    b.tick(waiting=False)
    assert b.data['active_seconds'] == 5
    assert b.data['waiting_seconds'] == b.data['resource_wait_seconds'] == 300
    now[0] = 310
    b.tick(True)
    assert b.spent() == 10


def test_handoff_prioritizes_scene_and_audio_not_hundreds_of_frame_paths(tmp_path):
    from harness.workflow import continuation_note
    cache = tmp_path / '.render-cache' / ('a' * 64); cache.mkdir(parents=True)
    for i in range(100):
        (cache / f'{i:06}.png').write_bytes(b'frame')
    (cache / 'frames.json').write_text('{}')
    for path in ('scene.blend', 'build.py', 'plan.json', 'rigs.json'):
        (tmp_path / path).write_bytes(b'checkpoint')
    audio = tmp_path / 'audio'; audio.mkdir()
    (audio / 'production.json').write_text('{}')
    for i in range(20):
        (tmp_path / f'a{i:02}.log').write_text('diagnostic')
    attempt = {'started': 0, 'revision': 0, 'provider': 'codex', 'kind': 'timeout'}
    note = continuation_note({'revision': 0, 'attempts': [attempt]}, attempt, tmp_path)
    assert all(p in note for p in ('scene.blend', 'build.py', 'audio/production.json'))
    assert '000001.png' not in note
    assert 'frame cache' in note.lower()


def test_worker_wait_accounting_ends_before_controller_validation(tmp_path, monkeypatch):
    import json
    from harness.store import Store
    from harness.workflow import Engine
    from tests.harness.test_compact_production import script
    clock = [0.0]
    monkeypatch.setattr('harness.execution.time.monotonic', lambda: clock[0])
    store = Store(tmp_path)
    s = store.create(load_config())
    s.update(tasks=build_tasks(1, compact=True), sources=[],
             models={'workers': {'writer': [{'provider': 'codex', 'model': 'test'}]}})
    def worker(profile, work, *args, **kwargs):
        clock[0] = 5
        engine.budget.tick(waiting=True)
        clock[0] = 15
        (work / 'result.json').write_text(json.dumps({'summary': 'guide', 'files': [], 'scripts': [script()]}))
        return {'kind': 'ok'}
    engine = Engine(store, execute=worker, auth=lambda _: True)
    engine.budget = Budget(s, store.save)
    def validate(*args):
        assert not engine.budget.waiting
        clock[0] += 100
    monkeypatch.setattr(engine, 'validate_media', validate)
    engine.agent_task(s, s['tasks'][0], store.path(s['id']))
    engine.budget.tick(True)
    assert s['tasks'][0]['status'] == 'succeeded'
    assert s['execution']['active_seconds'] == 105
    assert s['execution']['resource_wait_seconds'] == 10


def test_attempt_ownership_is_durable_before_launch(tmp_path):
    from harness.store import Store
    from harness.workflow import Engine
    from tests.harness.test_workflow import fake_models, research_result
    store = Store(tmp_path); s = store.create(load_config())
    def worker(profile, work, *args, **kwargs):
        saved = store.get(s['id'])['tasks'][0]['attempts'][-1]
        assert saved['ownership_token'] == profile['ownership_token']
        assert len(saved['ownership_token']) == 32
        research_result(work)
        return {'kind': 'ok'}
    result = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True).run(s['id'], max_steps=1)
    assert result['tasks'][0]['status'] == 'succeeded'


def test_crash_reconcile_cleans_owned_children_before_reopening(tmp_path, monkeypatch):
    from harness.store import Store
    from harness.workflow import Engine
    import harness.workers
    store = Store(tmp_path); s = store.create(load_config())
    s['tasks'] = build_tasks(1, compact=True)
    task = s['tasks'][1]; task['status'] = 'running'
    task['attempts'] = [{'ownership_token': 'a' * 32}]
    calls = []
    def cleanup(token):
        assert task['status'] == 'running'
        calls.append(token)
    monkeypatch.setattr(harness.workers, 'cleanup_owned_attempt', cleanup, raising=False)
    Engine(store).reconcile(s)
    assert calls == ['a' * 32]
    assert task['status'] == 'pending'
    task['status'] = 'running'
    def blocked(token):
        raise TimeoutError('cannot confirm cleanup')
    monkeypatch.setattr(harness.workers, 'cleanup_owned_attempt', blocked)
    import pytest
    with pytest.raises(harness.workers.WorkerCleanupError):
        Engine(store).reconcile(s)
    assert task['status'] == 'failed'
    assert store.get(s['id'])['tasks'][1]['attempts'][0]['cleanup_pending'] is True


def test_cleanup_failure_blocks_fallback_and_survives_retry_and_resume(tmp_path, monkeypatch):
    import json
    import pytest
    from harness import workers
    from harness.store import Store
    from harness.workflow import Engine
    from tests.harness.test_compact_production import script

    cleanup_error = getattr(workers, 'WorkerCleanupError', None)
    assert cleanup_error is not None
    store = Store(tmp_path)
    s = store.create(load_config())
    s.update(tasks=build_tasks(1, compact=True), sources=[],
             models={'workers': {'writer': [
                 {'provider': 'codex', 'model': 'first'},
                 {'provider': 'claude', 'model': 'second'}]}})
    store.save(s, 'fixture')
    calls = []
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['ownership_token'])
        if len(calls) == 1:
            raise cleanup_error(profile['ownership_token'], 'owned pidfd signal denied')
        (work / 'result.json').write_text(json.dumps({'summary':'guide', 'files':[], 'scripts':[script()]}))
        return {'kind':'ok'}
    engine = Engine(store, execute=worker, auth=lambda _:True)
    engine.budget = Budget(s, store.save)
    task = s['tasks'][0]
    with pytest.raises(cleanup_error):
        engine.agent_task(s, task, store.path(s['id']))
    assert len(calls) == 1, 'cleanup failure must not launch the second provider'
    saved = store.get(s['id'])
    attempt = saved['tasks'][0]['attempts'][0]
    assert attempt['cleanup_pending'] is True
    assert attempt['ownership_token'] == calls[0]
    assert saved['tasks'][0]['status'] == 'failed'
    assert 'cleanup' in saved['tasks'][0]['feedback'].lower()

    cleaned = []
    def blocked(token):
        cleaned.append(token)
        raise TimeoutError('cleanup still blocked')
    monkeypatch.setattr(workers, 'cleanup_owned_attempt', blocked)
    revision = saved['tasks'][0]['revision']
    with pytest.raises(cleanup_error):
        engine.prepare_retry(s['id'], task['id'])
    saved = store.get(s['id'])
    assert saved['tasks'][0]['revision'] == revision
    assert saved['tasks'][0]['attempts'][0]['cleanup_pending'] is True

    # Neither an older retry command nor a pending status may bypass the flag.
    saved['tasks'][0]['status'] = 'pending'
    store.save(saved, 'pending_fixture')
    resumed = engine.run(s['id'], max_steps=1)
    assert resumed['status'] == 'failed'
    assert resumed['tasks'][0]['attempts'][0]['cleanup_pending'] is True
    assert len(calls) == 1
    with pytest.raises(cleanup_error):
        engine.agent_task(resumed, resumed['tasks'][0], store.path(s['id']))
    assert len(calls) == 1
    assert cleaned and set(cleaned) == {calls[0]}

    monkeypatch.setattr(workers, 'cleanup_owned_attempt', lambda token:cleaned.append(token))
    engine.prepare_retry(s['id'], task['id'])
    ready = store.get(s['id'])
    assert not ready['tasks'][0]['attempts'][0].get('cleanup_pending')
    assert ready['tasks'][0]['attempts'][0]['ownership_token'] == calls[0]
    monkeypatch.setattr('harness.library.catalog', lambda config:[])
    engine.resolve = lambda profiles: {'workers': profiles}
    ready = engine.run(s['id'], max_steps=1)
    assert ready['tasks'][0]['status'] == 'succeeded'
    assert len(calls) == 2 and calls[1] != calls[0]


def cleanup_resume_fixture(tmp_path, monkeypatch):
    import json
    from harness.store import Store
    from harness.workflow import Engine
    from tests.harness.test_compact_production import script

    store = Store(tmp_path)
    s = store.create(load_config())
    s.update(tasks=build_tasks(1, compact=True), sources=[],
             models={'workers': {'writer': [{'provider': 'codex', 'model': 'fixture', 'selector': 'fixture'}]}})
    calls = []
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['ownership_token'])
        (work / 'result.json').write_text(json.dumps({'summary': 'guide', 'files': [], 'scripts': [script()]}))
        return {'kind': 'ok'}
    engine = Engine(store, execute=worker, resolve=lambda profiles: {'workers': profiles}, auth=lambda _: True)
    monkeypatch.setattr('harness.library.catalog', lambda config: [])
    return store, s, engine, calls


def pending_cleanup_attempt(token='a' * 32):
    return {'number': 1, 'revision': 0, 'provider': 'codex', 'model': 'fixture',
            'ownership_token': token, 'kind': 'cleanup_failed', 'cleanup_pending': True}


def test_single_route_cleanup_failure_recovers_on_ordinary_run(tmp_path, monkeypatch):
    from harness.workers import WorkerCleanupError
    store, s, engine, calls = cleanup_resume_fixture(tmp_path, monkeypatch)
    good_worker = engine.execute
    def blocked_worker(profile, *args, **kwargs):
        calls.append(profile['ownership_token'])
        raise WorkerCleanupError(profile['ownership_token'], 'owned pidfd signal denied')
    engine.execute = blocked_worker
    store.save(s, 'fixture')
    failed = engine.run(s['id'], max_steps=1)
    assert failed['tasks'][0]['status'] == 'failed'
    assert len(calls) == 1
    token = calls[0]
    cleaned = []
    monkeypatch.setattr('harness.workers.cleanup_owned_attempt', lambda token: cleaned.append(token))
    engine.execute = good_worker
    resumed = engine.run(s['id'], max_steps=1)
    assert resumed['tasks'][0]['status'] == 'succeeded'
    assert resumed['tasks'][0]['revision'] == 0
    assert cleaned == [token]
    assert len(calls) == 2 and calls[1] != token
    assert not resumed['tasks'][0]['attempts'][0].get('cleanup_pending')


def test_cleanup_recovery_does_not_refund_earlier_route_failures(tmp_path, monkeypatch):
    store, s, engine, calls = cleanup_resume_fixture(tmp_path, monkeypatch)
    task = s['tasks'][0]
    earlier = {'number': 1, 'revision': 0, 'provider': 'codex', 'model': 'fixture', 'kind': 'crash'}
    task.update(status='failed', attempts=[earlier.copy(), {**pending_cleanup_attempt(), 'number': 2}])
    store.save(s, 'fixture')
    monkeypatch.setattr('harness.workers.cleanup_owned_attempt', lambda token: None)
    resumed = engine.run(s['id'], max_steps=1)
    assert calls == []
    assert resumed['tasks'][0]['revision'] == 0
    assert resumed['tasks'][0]['attempts'][0] == earlier


def test_cleanup_recovery_save_is_atomic_with_resume_eligibility(tmp_path, monkeypatch):
    import pytest
    # Crash after the first durable removal, including the explicit-retry path.
    for action in ('resume', 'retry'):
        store, s, engine, calls = cleanup_resume_fixture(tmp_path / action, monkeypatch)
        task = s['tasks'][0]
        task.update(status='failed', attempts=[pending_cleanup_attempt()])
        store.save(s, 'fixture')
        monkeypatch.setattr('harness.workers.cleanup_owned_attempt', lambda token: None)
        save = store.save
        class ControllerCrash(BaseException):
            pass
        def crash_after_clear(current, kind, data=None):
            save(current, kind, data)
            if not current['tasks'][0]['attempts'][0].get('cleanup_pending'):
                raise ControllerCrash()
        with monkeypatch.context() as patch:
            patch.setattr(store, 'save', crash_after_clear)
            with pytest.raises(ControllerCrash):
                if action == 'retry':
                    engine.prepare_retry(s['id'], task['id'])
                else:
                    engine.run(s['id'], max_steps=1)
        durable = store.get(s['id'])
        assert durable['tasks'][0]['status'] == 'pending', action
        assert durable['tasks'][0]['attempts'][0]['ownership_token'] == 'a' * 32
        resumed = engine.run(s['id'], max_steps=1)
        assert resumed['tasks'][0]['status'] == 'succeeded', action
        assert len(calls) == 1


def test_cleanup_failure_preserves_all_unconfirmed_tokens(tmp_path, monkeypatch):
    from harness.workers import WorkerCleanupError
    import pytest
    store, s, engine, calls = cleanup_resume_fixture(tmp_path, monkeypatch)
    tokens = ['a' * 32, 'b' * 32]
    s['tasks'][0].update(status='failed', attempts=[pending_cleanup_attempt(t) for t in tokens])
    store.save(s, 'fixture')
    cleaned = []
    def cleanup(token):
        cleaned.append(token)
        if token == tokens[-1]:
            raise TimeoutError('second token still owns files')
    monkeypatch.setattr('harness.workers.cleanup_owned_attempt', cleanup)
    with pytest.raises(WorkerCleanupError):
        engine.reconcile(s)
    durable = store.get(s['id'])
    assert cleaned == tokens
    assert all(a.get('cleanup_pending') for a in durable['tasks'][0]['attempts'])
    assert [a['ownership_token'] for a in durable['tasks'][0]['attempts']] == tokens
    assert durable['tasks'][0]['status'] == 'failed'
    assert calls == []
