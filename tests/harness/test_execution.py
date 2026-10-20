import json
import subprocess
import sys

import pytest

from harness.config import load_config
from harness.store import Store
from harness.workflow import Engine, build_tasks
from tests.harness.test_workflow import fake_models, research_result


def test_fast_plan_keeps_model_tier_and_halves_budget(tmp_path):
    import os
    env = {**os.environ, 'STUDIO_HARNESS_HOME': str(tmp_path / 'state')}
    r = subprocess.run([sys.executable, 'ad', '--config', 'harness.example.json',
                        '-e', 'high', '--fast', '-s', '9', '--plan'],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    state = json.loads(r.stdout)
    assert state['config']['workers']['writer'][0]['model'] == 'auto:quality'
    assert state['execution']['target_seconds'] == 1200
    assert state['execution']['hard_seconds'] == 1500


def test_exhausted_run_cannot_spend_again_on_resume(tmp_path):
    from harness.execution import policy
    store = Store(tmp_path)
    s = store.create(load_config(overrides={'output': {'target_seconds': 9}}))
    s['execution'] = policy(s['config'])
    s['execution']['active_seconds'] = 1500
    store.save(s, 'fixture')
    calls = []
    e = Engine(store, execute=lambda *a, **k: calls.append(1), resolve=fake_models,
               auth=lambda _: True)
    result = e.run(s['id'])
    assert result['status'] == 'budget_exhausted'
    assert calls == []
    assert e.run(s['id'])['status'] == 'budget_exhausted'


def test_budget_bounds_worker_but_preserves_provider_fallback(tmp_path):
    from harness.execution import policy
    store = Store(tmp_path)
    s = store.create(load_config(overrides={'generation': {'effort': 'low', 'fast': True},
                                           'output': {'target_seconds': 9}}))
    s['execution'] = policy(s['config'])
    store.save(s, 'fixture')
    calls = []
    def worker(profile, work, prompt, log, cancelled, timeout, started):
        calls.append((profile['provider'], timeout))
        if len(calls) == 1:
            return {'kind': 'timeout', 'detail': 'hung session'}
        research_result(work)
        return {'kind': 'ok'}
    e = Engine(store, execute=worker, resolve=fake_models, auth=lambda _: True)
    result = e.run(s['id'], max_steps=1)
    assert result['tasks'][0]['status'] == 'succeeded'
    assert [c[0] for c in calls] == ['codex', 'claude']
    assert all(0 < c[1] < 90 for c in calls)


def test_targeted_rewind_preserves_assets_for_audio_and_frame_for_cta(tmp_path):
    store = Store(tmp_path)
    s = store.create(load_config())
    s['tasks'] = build_tasks(1, modern=True)
    for t in s['tasks']:
        t.update(status='succeeded', result={'summary': t['stage']})
    engine = Engine(store)
    engine.rewind(s, 0, 'audio', 'fix line timing')
    states = {t['stage']: t['status'] for t in s['tasks']}
    assert states['assets'] == 'succeeded'
    assert states['audio'] == states['animate'] == states['frame'] == 'pending'


def test_subprocess_deadline_is_enforced():
    from harness.execution import deadline, bounded_timeout, BudgetExceeded
    with deadline(0):
        with pytest.raises(BudgetExceeded):
            bounded_timeout(1000)


def test_timeout_can_change_model_when_other_provider_is_cooling(tmp_path):
    store = Store(tmp_path)
    c = load_config(overrides={'generation': {'effort': 'low'}})
    s = store.create(c)
    store.cooldown('claude', 100)
    calls = []
    def resolve(workers):
        return {'workers': {role: [dict(p, model='luna' if p['model']=='auto:economy' else 'sol') for p in profiles]
                            for role, profiles in workers.items()}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['model'])
        if profile['model'] == 'luna':
            return {'kind':'timeout', 'detail':'checkpoint saved'}
        research_result(work)
        return {'kind':'ok'}
    result = Engine(store, execute=worker, resolve=resolve, auth=lambda _:True).run(s['id'], max_steps=1)
    assert result['tasks'][0]['status'] == 'succeeded'
    assert calls == ['luna', 'sol']


def test_alternate_worker_is_persisted_running_before_attempt_started(tmp_path):
    store = Store(tmp_path)
    state = store.create(load_config(overrides={'generation': {'effort': 'low'}}))
    store.cooldown('claude', 100)
    observed = []

    def resolve(workers):
        return {'workers': {role: [dict(p, model='luna' if p['model'] == 'auto:economy' else 'sol')
                                   for p in profiles] for role, profiles in workers.items()}}

    def worker(profile, work, *args, **kwargs):
        # Read the real durable state before started(pid) can save another event.
        snapshot = store.get(state['id'])
        event = store.events(state['id'])[-1]
        observed.append((profile['model'], snapshot['tasks'][0]['status'],
                         event['kind'], event['data']['model']))
        if profile['model'] == 'luna':
            return {'kind': 'timeout', 'detail': 'primary stalled'}
        research_result(work)
        return {'kind': 'ok'}

    result = Engine(store, execute=worker, resolve=resolve, auth=lambda _: True).run(state['id'], max_steps=1)
    assert observed == [('luna', 'running', 'attempt_started', 'luna'),
                        ('sol', 'running', 'attempt_started', 'sol')]
    assert result['tasks'][0]['status'] == 'succeeded'


def test_recovery_routes_do_not_collide_with_alternate_on_resume(tmp_path):
    from harness.execution import Budget
    store = Store(tmp_path)
    s = store.create(load_config(overrides={'generation': {'effort': 'medium'}}))
    s['execution']['mode'] = 'recovery'
    s['tasks'] = [build_tasks(1)[0]]
    s['sources'] = {}
    s['models'] = {'workers': {'researcher': [{'provider':'codex','model':'original'},
                                            {'provider':'claude','model':'blocked'}]}}
    s['recovery_models'] = {'workers': {'researcher': [{'provider':'codex','model':'cheap'}]}}
    store.cooldown('claude', 100)
    calls = []
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['model'])
        if profile['model'] != 'alternate':
            return {'kind':'timeout', 'detail':'stalled'}
        research_result(work)
        return {'kind':'ok'}
    engine = Engine(store, execute=worker, auth=lambda _:True,
                    resolve=lambda _: {'workers': {'researcher': [{'provider':'codex','model':'alternate'}]}})
    engine.budget = Budget(s, store.save)
    engine.agent_task(s, s['tasks'][0], store.path(s['id']))
    assert s['tasks'][0]['status'] == 'succeeded'
    assert calls == ['cheap', 'original', 'alternate']
    assert len({a['route_id'] for a in s['tasks'][0]['attempts']}) == 3


def test_legacy_heavy_stage_keeps_unlimited_idle(tmp_path):
    store = Store(tmp_path)
    s = store.create(load_config()); s.pop('execution')
    task = build_tasks(1)[0]; task.update(stage='animate')
    s.update(tasks=[task], sources={}, models=fake_models(s['config']['workers']))
    store.save(s, 'fixture')
    calls = []
    def worker(profile, *args, **kwargs):
        calls.append(profile['idle_timeout'])
        return {'kind':'timeout','detail':'test'}
    result = Engine(store, execute=worker, auth=lambda _:True).run(s['id'])
    assert result['status'] == 'failed'
    assert calls == [None, None]


@pytest.mark.parametrize('stage', ['frame', 'qa'])
def test_builtin_timeout_at_hard_ceiling_checkpoints(tmp_path, monkeypatch, stage):
    import harness.workflow as workflow
    from harness.execution import Budget
    store = Store(tmp_path)
    s = store.create(load_config()); task = build_tasks(1)[0]
    task.update(stage=stage, ad=0, status='running')
    s.update(tasks=[task], sources={}, models=fake_models(s['config']['workers']))
    engine = Engine(store, execute=lambda *a,**kw:None)
    monkeypatch.setattr(engine, 'inputs', lambda *a: {})
    def timeout(*args):
        s['execution']['active_seconds'] = s['execution']['hard_seconds'] + 1
        raise subprocess.TimeoutExpired('ffmpeg', 1)
    monkeypatch.setattr(engine, 'direction', timeout)
    # Frame fails while reading direction; QA fails during video validation.
    monkeypatch.setattr('harness.media.check_video', timeout)
    # Accepted edit/frame input stubs suffice to reach the timed operation.
    for upstream in ('edit','frame'):
        if upstream != stage:
            t = build_tasks(1)[0]; t.update(stage=upstream, ad=0, status='succeeded', result={'master':'fixture'})
            s['tasks'].insert(0,t)
    engine.budget = Budget(s, store.save)
    with pytest.raises(workflow.BudgetExceeded):
        engine.builtin_task(s, task, store.path(s['id']))


def test_cli_budget_exhaustion_is_nonzero(tmp_path, capsys):
    from harness.cli import main
    store = Store(tmp_path); s = store.create(load_config())
    s['execution']['active_seconds'] = s['execution']['hard_seconds'] + 1
    store.save(s, 'fixture')
    assert main(['--home',str(tmp_path),'resume',s['id'],'--no-wait']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'budget_exhausted'


def test_alternate_model_searches_both_providers_not_only_last(tmp_path):
    store = Store(tmp_path)
    s = store.create(load_config(overrides={'generation':{'effort':'low'}}))
    calls = []
    def resolve(workers):
        return {'workers':{r:[dict(p, model=('luna' if p['model']=='auto:economy' else 'sol')
                                        if p['provider']=='codex' else 'sonnet') for p in ps]
                            for r,ps in workers.items()}}
    def worker(profile, work, *args, **kwargs):
        calls.append(profile['model'])
        if profile['model'] != 'sol': return {'kind':'timeout','detail':'stalled'}
        research_result(work)
        return {'kind':'ok'}
    state = Engine(store, execute=worker, resolve=resolve, auth=lambda _:True).run(s['id'], max_steps=1)
    assert state['tasks'][0]['status']=='succeeded'
    assert calls==['luna','sonnet','sol']


def test_resume_resolves_saved_identity_before_old_config_basename(tmp_path):
    from harness.contracts import digest
    root = tmp_path/'library'; root.mkdir()
    original = str(root/'old'/'actor.blend')
    previous = str(root/'intermediate'/'actor.blend')
    moved = root/'renamed.blend'; moved.write_bytes(b'approved actor')
    (root/'actor.blend').write_bytes(b'wrong replacement')
    config = load_config(overrides={'sources':{'assets':[str(root)],'characters':[original]},
                                    'library':{'root':str(root)}})
    path = tmp_path/'config.json'; path.write_text(json.dumps(config))
    store=Store(tmp_path/'state'); s=store.create(config)
    identity={'id':'legacy-'+digest(moved),'kind':'character','sha256':digest(moved)}
    s.update(config_path=str(path), asset_identities=[identity], asset_paths={identity['id']:previous},
             source_warnings=[{'group':'characters','kind':'relocated','source':original,'replacement':previous}])
    store.save(s,'fixture')
    result=Engine(store, execute=lambda *a,**k:None, resolve=fake_models).run(s['id'],max_steps=0)
    assert result['status']=='ready', result['error']
    assert result['config']['sources']['characters']==[str(moved)]


def test_stage_budget_reserves_time_for_other_ads(tmp_path):
    from harness.execution import Budget
    allowances=[]
    for count in (1,2):
        store=Store(tmp_path/str(count)); s=store.create(load_config(overrides={'count':count}))
        s['tasks']=build_tasks(count, modern=True)
        task=next(t for t in s['tasks'] if t['stage']=='assets')
        allowances.append(Budget(s,store.save).stage_seconds(task,9999))
    assert allowances[1] < allowances[0] * 1.2
