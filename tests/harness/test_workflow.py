import json
from pathlib import Path

from harness.config import load_config
from harness.store import Store
from harness.workflow import Engine, build_tasks


def test_graph_has_independent_writing_and_review_steps():
    tasks = build_tasks(2)
    assert [t['stage'] for t in tasks[:7]] == [
        'research', 'write', 'critique', 'revise', 'critique_final', 'select', 'direct']
    assert [t['stage'] for t in tasks if t['ad'] == 0][:4] == ['direct', 'assets', 'board_review', 'audio']
    assert len([t for t in tasks if t['stage'] == 'package']) == 2


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
    target=next(t for t in r['tasks'] if t['stage']=='review')
    target['status']='needs_review';target['result']={'summary':'bad contact','verdict':'revise','files':[],
       'findings':[{'target':'2s','severity':'important','problem':'floating prop','fix':'ground it'}]}
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
    task = next(t for t in state['tasks'] if t['stage'] == 'critique_final')
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
    assert [p['model'] for p in load_config()['workers']['critic']] == [
        'auto:economy', 'auto:economy', 'auto:balanced', 'auto:balanced']
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
    assert ROLES['direct'] == ROLES['review'] == ROLES['creative_qa'] == 'director'
    assert [p['model'] for p in load_config()['workers']['director']] == ['auto:quality', 'auto:quality']


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


def test_storyboard_gets_more_repair_rounds_than_animation(tmp_path):
    e = Engine(Store(tmp_path))
    def exhausted(stage, revision):
        state = {'config': load_config(), 'tasks': build_tasks(1)}
        task = next(t for t in state['tasks'] if t['stage'] == stage)
        task.update(status='succeeded', rounds=revision, result={'summary': 's', 'verdict': 'revise', 'restart': 'assets',
            'files': [], 'findings': [{'target': 'b', 'severity': 'blocking', 'problem': 'p', 'fix': 'f'}]})
        state['id'] = 'x'
        e.store.save = lambda *a, **k: None
        e.review_transition(state, task)
        return task['status']
    assert exhausted('review', 2) == 'needs_review'          # limits.repairs (2)
    assert exhausted('board_review', 2) == 'pending'         # rewound: boards are cheap to redo
    assert exhausted('board_review', 4) == 'needs_review'    # limits.board_repairs (4)


def test_upstream_rewinds_do_not_use_up_a_review_budget(tmp_path):
    e = Engine(Store(tmp_path)); e.store.save = lambda *a, **k: None
    state = {'id': 'x', 'config': load_config(), 'tasks': build_tasks(1)}
    review = next(t for t in state['tasks'] if t['stage'] == 'review')
    review['revision'] = 5          # bumped by five storyboard rewinds before it ever ran
    review.update(status='succeeded', result={'summary': 's', 'verdict': 'revise', 'restart': 'animate', 'files': [],
                  'findings': [{'target': 't', 'severity': 'blocking', 'problem': 'p', 'fix': 'f'}]})
    e.review_transition(state, review)
    assert review['status'] == 'pending' and review['rounds'] == 1   # its first verdict gets a repair
