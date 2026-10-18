import json
from pathlib import Path

from harness.config import load_config
from harness.store import Store
from harness.workflow import Engine, build_tasks


def test_graph_has_independent_writing_and_review_steps():
    tasks = build_tasks(2)
    assert [t['stage'] for t in tasks[:4]] == ['research', 'write', 'select', 'direct']
    assert [t['stage'] for t in tasks if t['ad'] == 0][:4] == ['direct', 'assets', 'audio', 'animate']
    assert len([t for t in tasks if t['stage'] == 'package']) == 2


def test_animator_starts_with_opus_and_falls_back_to_codex_on_timeout(tmp_path):
    from harness.workflow import ROLES
    config = load_config()
    assert ROLES['animate'] == 'animator'
    assert config['workers']['animator'] == [
        {'provider': 'claude', 'model': 'opus'},
        {'provider': 'codex', 'model': 'auto:quality'}]
    store = Store(tmp_path)
    state = store.create(config)
    task = build_tasks(1)[0]
    task.update(id='test-animate', stage='animate')
    state.update(tasks=[task], models={'workers': config['workers']}, sources={})
    calls = []
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['provider'])
        if profile['provider'] == 'claude':
            (work / 'handoff.md').write_text('Reuse the accepted idle and measured speech.')
            return {'kind': 'timeout', 'detail': 'test timeout'}
        if len(calls) > 1:
            assert (work / 'handoff.md').is_file()
        (work / 'preview.mp4').write_bytes(b'fixture')
        (work / 'scene.py').write_text('# fixture')
        (work / 'result.json').write_text(json.dumps({
            'summary': 'routing fixture', 'preview': 'preview.mp4', 'source': 'scene.py',
            'files': [{'path': 'preview.mp4', 'kind': 'video'}, {'path': 'scene.py', 'kind': 'source'}]}))
        return {'kind': 'ok'}
    engine = Engine(store, execute=worker, auth=lambda _: True)
    engine.validate_media = lambda *args: None  # this test checks routing, not a render
    engine.agent_task(state, task, store.path(state['id']))
    assert calls == ['claude', 'codex']
    assert task['status'] == 'succeeded'
    # A saved pre-upgrade run has no animator entry and keeps its old routing.
    old_workers = dict(config['workers']); old_workers.pop('animator')
    legacy = store.create(config)
    old_task = build_tasks(1)[0]; old_task.update(id='legacy-animate', stage='animate')
    legacy.update(tasks=[old_task], models={'workers': old_workers}, sources={})
    calls.clear()
    engine.agent_task(legacy, old_task, store.path(legacy['id']))
    assert calls == ['codex'] and old_task['status'] == 'succeeded'


def fake_models(workers):
    return {'workers': {role: [{'provider': 'codex', 'model': 'test-quality'},
                             {'provider': 'claude', 'model': 'test-backup'}] for role in workers}}


def research_result(work):
    (work / 'result.json').write_text(json.dumps({'summary': 'researched', 'files': [],
        'brand_brief': 'Fictional demonstration', 'creative_directions': 'Visual contrast', 'references': []}))


def test_quota_handoff_and_resume_without_repeating_success(tmp_path):
    store = Store(tmp_path)
    c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c)
    calls = []
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        calls.append(profile['provider'])
        if profile['provider'] == 'codex':
            (work / 'handoff.md').write_text('Keep the work')
            return {'kind': 'quota', 'detail': 'usage limit'}
        assert (work / 'handoff.md').read_text() == 'Keep the work'
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    e = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    state = store.get(run['id'])
    assert state['tasks'][0]['status'] == 'succeeded'
    assert calls == ['codex', 'claude']
    e.run(run['id'], max_steps=0)
    assert calls == ['codex', 'claude']
    assert store.cooldown('codex') > 0


def test_exit_zero_without_result_fails_closed(tmp_path):
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    r = store.create(c)
    e = Engine(store, execute=lambda *a, **k: {'kind': 'ok', 'detail': ''},
               resolve=fake_models, auth=lambda _: True)
    e.run(r['id'])
    state = store.get(r['id'])
    assert state['status'] == 'failed'
    assert state['tasks'][0]['status'] == 'failed'
    assert all(t['status'] == 'pending' for t in state['tasks'][1:])


def test_all_providers_unavailable_wait_without_spinning(tmp_path):
    store = Store(tmp_path); r = store.create(load_config())
    e = Engine(store, resolve=fake_models, auth=lambda _: False, preflight=lambda c: [])
    e.run(r['id'])
    assert store.get(r['id'])['status'] == 'waiting_provider'


def test_accepted_output_tampering_is_detected(tmp_path):
    store = Store(tmp_path); r = store.create(load_config())
    def worker(profile, work, *a, **k):
        (work/'notes.md').write_text('sources')
        research_result(work)
        d=json.loads((work/'result.json').read_text()); d['files']=[{'path':'notes.md','kind':'notes'}]
        (work/'result.json').write_text(json.dumps(d))
        return {'kind':'ok'}
    e=Engine(store, execute=worker, resolve=fake_models, auth=lambda _:True)
    e.run(r['id'], max_steps=1)
    s=store.get(r['id']);p=Path(s['tasks'][0]['result']['files'][0]['path']);p.chmod(0o644);p.write_text('changed')
    e.run(r['id'], max_steps=0)
    assert store.get(r['id'])['status']=='failed'
    assert 'changed' in store.get(r['id'])['error']


def test_mid_run_tampering_rejects_next_result(tmp_path):
    store=Store(tmp_path);r=store.create(load_config())
    counter=[0]
    def worker(profile,work,*a,**k):
        if counter[0]==0:
            (work/'notes.md').write_text('original');research_result(work)
            d=json.loads((work/'result.json').read_text());d['files']=[{'path':'notes.md','kind':'notes'}]
            (work/'result.json').write_text(json.dumps(d))
        else:
            s=store.get(r['id']);p=Path(s['tasks'][0]['result']['files'][0]['path'])
            p.chmod(0o644);p.write_text('tampered')
            scripts=[dict(id=str(i),title='a',premise='b',script='c',visual_direction='d',product='e',cta='none') for i in range(3)]
            (work/'result.json').write_text(json.dumps({'summary':'written','files':[],'scripts':scripts}))
        counter[0]+=1;return {'kind':'ok'}
    e=Engine(store,execute=worker,resolve=fake_models,auth=lambda _:True)
    e.run(r['id'],max_steps=2)
    s=store.get(r['id']);assert s['status']=='failed' and s['tasks'][1]['status']!='succeeded'


def test_review_retry_reopens_producer_with_findings(tmp_path):
    store=Store(tmp_path);r=store.create(load_config());r['tasks']=build_tasks(1)
    target=next(t for t in r['tasks'] if t['stage']=='creative_qa')
    target['status']='needs_review';target['result']={'summary':'bad contact','verdict':'revise','files':[],
       'restart':'assets', 'findings':[{'target':'2s','severity':'important','problem':'floating prop','fix':'ground it'}]}
    for t in r['tasks']:
        if t['ad']==0 and t['stage'] in ('assets','audio','animate'):t['status']='succeeded'
    store.save(r,'fixture')
    Engine(store).prepare_retry(r['id'],target['id'])
    state=store.get(r['id'])
    assert all(t['status']=='pending' for t in state['tasks'] if t['ad']==0)
    assert 'floating prop' in next(t for t in state['tasks'] if t['stage']=='animate')['feedback']


def test_cancelled_task_cannot_be_skipped(tmp_path):
    store=Store(tmp_path);s=store.create(load_config());s['tasks']=build_tasks(1)
    s['tasks'][0]['status']='cancelled'
    assert Engine(store).next_task(s) is None


def exhausted_review(severity):
    state ={'config': load_config(), 'tasks': build_tasks(1)}
    task = next(t for t in state['tasks'] if t['stage'] == 'creative_qa')
    task.update(status='succeeded', rounds=state['config']['limits']['repairs'], result={
        'summary': 'still flawed', 'verdict': 'revise', 'files': [],
        'findings': [{'target': 'A', 'severity': severity, 'problem': 'p', 'fix': 'f'}]})
    return state, task


def test_exhausted_review_proceeds_on_nonblocking_and_stops_on_blocking(tmp_path):
    engine = Engine(Store(tmp_path))
    state, task = exhausted_review('important')
    engine.review_transition(state, task)
    assert task['status'] == 'succeeded' and task['result']['accepted_with_notes'] is True
    state, task = exhausted_review('blocking')
    engine.review_transition(state, task)
    assert task['status'] == 'needs_review'


def test_cheap_reviewer_escalates_to_stronger_route_on_contract_failures(tmp_path):
    assert [p['model'] for p in load_config()['workers']['critic']] == ['auto:economy', 'auto:economy']
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c); calls = []
    routes = [{'provider': 'claude', 'model': 'cheap'}, {'provider': 'claude', 'model': 'strong'}]
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        calls.append(profile['model'])
        if profile['model'] == 'strong':
            research_result(work)
        return {'kind': 'ok', 'detail': ''}
    e = Engine(store, execute=worker, resolve=lambda w: {'workers': {r: routes for r in w}}, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    assert calls == ['cheap', 'strong'] and store.get(run['id'])['tasks'][0]['status'] == 'succeeded'


def test_quota_attempts_do_not_consume_repair_budget(tmp_path):
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c); calls = []
    routes = [{'provider': 'claude', 'model': 'only'}]
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        calls.append(1)
        if len(calls) == 1:
            return {'kind': 'quota', 'detail': 'session limit'}
        research_result(work); return {'kind': 'ok', 'detail': ''}
    e = Engine(store, execute=worker, resolve=lambda w: {'workers': {r: routes for r in w}}, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    assert store.get(run['id'])['tasks'][0]['status'] == 'waiting_provider'
    with store.connect() as db:
        db.execute('DELETE FROM cooldowns')
    e.run(run['id'], max_steps=1)
    assert store.get(run['id'])['tasks'][0]['status'] == 'succeeded'


def test_review_restart_rewinds_only_from_the_named_stage(tmp_path):
    store = Store(tmp_path); state = store.create(load_config()); state['tasks'] = build_tasks(1)
    for t in state['tasks']:
        t['status'] = 'succeeded'
    task = next(t for t in state['tasks'] if t['stage'] == 'creative_qa')
    task['result'] = {'summary': 'cut drags', 'verdict': 'revise', 'files': [], 'restart': 'edit',
                      'findings': [{'target': '4s', 'severity': 'important', 'problem': 'slow', 'fix': 'trim'}]}
    Engine(store).review_transition(state, task)
    status = {t['stage']: t['status'] for t in state['tasks'] if t['ad'] == 0}
    assert status['animate'] == 'succeeded' and status['audio'] == 'succeeded'
    assert status['edit'] == 'pending' and status['frame'] == 'pending'
    assert 'slow' in next(t for t in state['tasks'] if t['stage'] == 'edit')['feedback']


def test_director_and_final_reviews_use_the_director_role():
    from harness.workflow import ROLES
    assert ROLES['direct'] == 'director' and ROLES['creative_qa'] == 'reviewer'
    assert [p['model'] for p in load_config()['workers']['director']] == ['auto:balanced', 'auto:balanced']
    assert [p['model'] for p in load_config()['workers']['reviewer']] == ['auto:economy', 'auto:economy']


def test_a_repair_that_changes_nothing_is_rejected(tmp_path):
    from harness.contracts import ContractError
    import pytest
    e = Engine(Store(tmp_path))
    (tmp_path / 'b0.png').write_bytes(b'same pixels')
    previous = {'boards': [{'beat': 0, 'image': str(tmp_path / 'b0.png')}],
                'files': [{'path': str(tmp_path / 'b0.png'), 'sha256': __import__('harness.contracts', fromlist=['digest']).digest(tmp_path / 'b0.png')}]}
    task = {'stage': 'assets', 'previous': previous, 'revision': 1}
    work = tmp_path / 'w'; work.mkdir(); (work / 'b0.png').write_bytes(b'same pixels')
    data = {'boards': [{'beat': 0, 'image': 'b0.png'}], 'files': [{'path': 'b0.png', 'kind': 'image'}]}
    with pytest.raises(ContractError, match='nothing changed'):
        e.check_changed(task, data, work)
    (work / 'b0.png').write_bytes(b'new pixels')
    e.check_changed(task, data, work)
    state = {'tasks': build_tasks(1)}
    for t in state['tasks']:
        t['result'] = {'summary': 'old'}
    e.rewind(state, 0, 'assets', 'fix it')
    assert next(t for t in state['tasks'] if t['id'] == 'ad-01-assets')['previous'] == {'summary': 'old'}


def test_only_necessary_review_stages_are_scheduled():
    stages = {t['stage'] for t in build_tasks(1)}
    assert not stages.intersection({'critique', 'revise', 'critique_final', 'script_sense',
                                    'board_review', 'review', 'edit_plan', 'edit_review'})
    assert load_config()['limits']['repairs'] == 1


def test_upstream_rewinds_do_not_use_up_a_review_budget(tmp_path):
    e = Engine(Store(tmp_path)); e.store.save = lambda *a, **k: None
    state = {'id': 'x', 'config': load_config(), 'tasks': build_tasks(1)}
    review = next(t for t in state['tasks'] if t['stage'] == 'creative_qa')
    review['revision'] = 5          # bumped by five storyboard rewinds before it ever ran
    review.update(status='succeeded', result={'summary': 's', 'verdict': 'revise', 'restart': 'animate', 'files': [],
                  'findings': [{'target': 't', 'severity': 'blocking', 'problem': 'p', 'fix': 'f'}]})
    e.review_transition(state, review)
    assert review['status'] == 'pending' and review['rounds'] == 1   # its first verdict gets a repair


def test_retry_on_a_finished_stage_redoes_it_and_everything_after(tmp_path):
    store = Store(tmp_path); r = store.create(load_config()); r['tasks'] = build_tasks(1)
    for t in r['tasks']:
        t.update(status='succeeded', result={'summary': 'done', 'files': []})
    qa = next(t for t in r['tasks'] if t['stage'] == 'qa'); qa.update(status='failed', result=None)
    store.save(r, 'fixture')
    Engine(store).prepare_retry(r['id'], 'ad-01-frame')
    after = {t['stage']: t['status'] for t in store.get(r['id'])['tasks'] if t['ad'] == 0}
    assert after['edit'] == 'succeeded'
    assert all(after[s] == 'pending' for s in ('frame', 'qa', 'creative_qa', 'package'))


def test_quick_stage_timeout_and_heavy_animation_budget():
    from harness.workflow import agent_deadline
    c = load_config()
    assert agent_deadline(c, 'research') == (180, 180)
    assert agent_deadline(c, 'select') == (240, 240)
    assert agent_deadline(c, 'write') == (600, 300)
    assert agent_deadline(c, 'direct') == (600, 300)
    assert agent_deadline(c, 'animate') == (14400, None)
    assert agent_deadline(c, 'edit') == (14400, None)
    # Old run configurations remain usable after introducing new limits.
    del c['limits']['quick_timeout_seconds']
    del c['limits']['review_timeout_seconds']
    del c['limits']['idle_timeout_seconds']
    assert agent_deadline(c, 'research') == (180, 180)


def test_idle_research_falls_back_without_repeating_same_model(tmp_path):
    store = Store(tmp_path); c = load_config()
    run = store.create(c)
    calls = []
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        calls.append((profile['model'], timeout, profile.get('idle_timeout')))
        if profile['model'] == 'first':
            (work / 'handoff.md').write_text('Facts found before the stall')
            return {'kind': 'idle_timeout', 'detail': 'no activity'}
        assert (work / 'handoff.md').read_text() == 'Facts found before the stall'
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    def routes(workers):
        return {'workers': {role: [{'provider': 'codex', 'model': 'first'},
                                  {'provider': 'claude', 'model': 'fallback'}] for role in workers}}
    e = Engine(store, execute=worker, resolve=routes, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    assert store.get(run['id'])['tasks'][0]['status'] == 'succeeded'
    assert calls == [('first', 600, 300), ('fallback', 600, 300)]
    assert store.get(run['id'])['tasks'][0]['attempts'][0]['kind'] == 'idle_timeout'


def test_timeout_accepts_only_complete_valid_checkpoint(tmp_path):
    store = Store(tmp_path); c = load_config()
    run = store.create(c)
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        research_result(work)  # Worker produced valid deliverable before timing out
        return {'kind': 'timeout', 'detail': 'time budget hit'}
    e = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    task = store.get(run['id'])['tasks'][0]
    assert task['status'] == 'succeeded'
    assert task['attempts'][0]['recovered_from'] == 'timeout'
    assert len(task['attempts']) == 1


def test_unexpected_worker_exception_moves_to_backup(tmp_path):
    store = Store(tmp_path); run = store.create(load_config())
    calls = []
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['provider'])
        if profile['provider'] == 'codex':
            raise OSError('CLI failed to launch')
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    e = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True)
    e.run(run['id'], max_steps=1)
    assert store.get(run['id'])['tasks'][0]['status'] == 'succeeded'
    assert calls == ['codex', 'claude']


def test_research_has_cheaper_route_after_balanced_and_writer_after_quality():
    c = load_config()
    assert [p['model'] for p in c['workers']['researcher']] == ['auto:economy', 'auto:economy']
    assert [p['model'] for p in c['workers']['writer']] == ['auto:balanced', 'auto:balanced']


def test_claude_quota_hands_off_to_codex_without_waiting(tmp_path):
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c); calls = []
    def resolver(workers):
        return {'workers': {role: [{'provider': 'claude', 'model': 'sonnet'},
                                   {'provider': 'codex', 'model': 'codex-working'}]
                            for role in workers}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['provider'])
        if profile['provider'] == 'claude':
            (work / 'handoff.md').write_text('Research gathered before hitting Claude limits')
            return {'kind': 'quota', 'detail': 'usage limit'}
        assert (work / 'handoff.md').read_text().startswith('Research gathered')
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    engine = Engine(store, execute=worker, resolve=resolver, auth=lambda _: True)
    engine.run(run['id'], max_steps=1)
    state = store.get(run['id'])
    assert state['tasks'][0]['status'] == 'succeeded'
    assert state['status'] != 'waiting_provider'
    assert calls == ['claude', 'codex']
    assert store.cooldown('claude') > 0


def test_resuming_stale_codex_discovery_recovers_and_skips_claude_cooldown(tmp_path):
    store = Store(tmp_path); c = load_config()
    run = store.create(c); run['tasks'] = build_tasks(1)
    run['status'] = 'waiting_provider'
    run['tasks'][0]['status'] = 'waiting_provider'
    run['tasks'][0]['attempts'] = [
        {'provider': 'claude', 'model': 'sonnet', 'kind': 'quota',
         'revision': 0, 'route': 1, 'detail': 'usage limit'}]
    run['models'] = {'workers': {
        role: [{'provider': 'codex', 'model': 'auto:balanced',
                'unavailable': 'Codex app-server catalog timed out'},
               {'provider': 'claude', 'model': 'sonnet'}]
        for role in c['workers']}}
    store.save(run, 'fixture')
    store.cooldown('claude', 3600)
    calls = []
    def resolver(workers):
        return {'workers': {
            role: [{'provider': 'codex', 'model': 'cli-default'},
                   {'provider': 'claude', 'model': 'sonnet'}] for role in workers}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['provider'])
        assert profile['provider'] == 'codex'
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    engine = Engine(store, execute=worker, resolve=resolver, auth=lambda _: True)
    engine.run(run['id'], max_steps=1)
    saved = store.get(run['id'])
    assert saved['tasks'][0]['status'] == 'succeeded'
    assert saved['status'] != 'waiting_provider'
    assert calls == ['codex']
    assert saved['models']['workers']['researcher'][0]['model'] == 'cli-default'
    assert not saved['models']['workers']['researcher'][0].get('unavailable')
    assert 'codex_routes_refreshed' in [event['kind'] for event in store.events(run['id'])]


def test_codex_missing_model_falls_back_to_default_without_waiting(tmp_path):
    from harness.workers import CODEX_CLI_DEFAULT
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c)
    store.cooldown('claude', 3600)
    calls = []
    def resolver(workers):
        return {'workers': {role: [
            {'provider': 'codex', 'model': 'retired-codex-model'},
            {'provider': 'claude', 'model': 'sonnet'}] for role in workers}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['model'])
        if profile['model'] != CODEX_CLI_DEFAULT:
            return {'kind': 'model', 'detail': 'model not found'}
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    engine = Engine(store, execute=worker, resolve=resolver, auth=lambda _: True)
    engine.run(run['id'], max_steps=1)
    saved = store.get(run['id'])
    assert saved['tasks'][0]['status'] == 'succeeded'
    assert calls == ['retired-codex-model', CODEX_CLI_DEFAULT]
    assert saved['models']['workers']['researcher'][0]['model'] == CODEX_CLI_DEFAULT
    assert len(saved['tasks'][0]['attempts']) == 2
    assert 'codex_model_fallback' in [event['kind'] for event in store.events(run['id'])]


def test_real_auth_gate_does_not_skip_codex_on_uncertain_status(tmp_path, monkeypatch):
    import harness.workflow as workflow
    from harness.workers import CODEX_CLI_DEFAULT
    store = Store(tmp_path); c = load_config()
    run = store.create(c); calls = []
    def unauthenticated(_provider):
        return False  # Codex CLI itself must be allowed to verify this.
    monkeypatch.setattr(workflow, 'subscription_status', unauthenticated)
    def resolver(workers):
        return {'workers': {role: [{'provider': 'codex', 'model': CODEX_CLI_DEFAULT},
                                   {'provider': 'claude', 'model': 'sonnet'}] for role in workers}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['provider'])
        research_result(work)
        return {'kind': 'ok', 'detail': ''}
    engine = Engine(store, execute=worker, resolve=resolver, auth=workflow.subscription_status)
    engine.run(run['id'], max_steps=1)
    assert calls == ['codex']
    assert store.get(run['id'])['tasks'][0]['status'] == 'succeeded'
