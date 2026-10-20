"""New-run contracts; live production evidence is recorded separately."""
import json

import pytest

from harness.config import load_config
from harness.contracts import ContractError, validate
from harness.execution import Budget, policy
from harness.store import Store
from harness.workflow import Engine, build_tasks


def script(identifier='one'):
    return dict(id=identifier, title='The Last Copy', premise='A clerk keeps reading the lost book',
                script='Customer: My book? Clerk: One more page.',
                visual_direction='Two characters at a counter; book is clearly visible.',
                product='Book', cta='See the book')


def test_script_contract_needs_exactly_one_usable_guide_per_ad(tmp_path):
    context = {'count': 1, 'compact': True}
    good = {'summary': 'One guide', 'files': [], 'scripts': [script()]}
    assert validate('script', good, tmp_path, context)['scripts'][0]['title'] == 'The Last Copy'
    for scripts in ([], [script(), script('two')], [{'id': 'broken'}]):
        with pytest.raises(ContractError):
            validate('script', {**good, 'scripts': scripts}, tmp_path, context)


def test_new_graph_reaches_animator_immediately_after_script(tmp_path):
    store = Store(tmp_path)
    state = store.create(load_config())
    state['tasks'] = build_tasks(2, modern=True, compact=True)
    first = state['tasks'][0]
    first.update(status='succeeded', result={'scripts': [script(), script('two')], 'files': []})
    engine = Engine(store)
    task = engine.next_task(state)
    assert task['stage'] == 'animate' and task['ad'] == 0
    assert engine.inputs(state, task)['selected_script']['id'] == 'one'
    assert [t['stage'] for t in state['tasks'] if t['ad'] == 0] == [
        'animate', 'edit', 'frame', 'qa', 'package']


def test_editor_can_request_one_focused_animation_repair_without_media(tmp_path):
    review = {'summary': 'The product is hidden', 'files': [], 'verdict': 'revise',
              'restart': 'animate', 'findings': [{'target': '0.5 s', 'severity': 'blocking',
                    'problem': 'The counter hides the book', 'fix': 'Raise the existing book'}]}
    assert validate('edit', review, tmp_path, {'compact': True})['verdict'] == 'revise'
    with pytest.raises(ContractError):
        validate('edit', {**review, 'restart': 'script'}, tmp_path, {'compact': True})


def test_animator_keeps_its_budget_at_old_storyboard_cutoff():
    c = load_config(overrides={'output': {'target_seconds': 9}})
    state = {'config': c, 'execution': policy(c), 'tasks': [
        {'stage': 'script', 'status': 'succeeded', 'ad': None},
        {'stage': 'animate', 'status': 'running', 'ad': 0},
        {'stage': 'edit', 'status': 'pending', 'ad': 0},
        {'stage': 'package', 'status': 'pending', 'ad': 0}]}
    state['execution']['active_seconds'] = 721
    budget = Budget(state, lambda *a: None)
    budget.check_production()
    assert budget.production_remaining() > 700
    assert budget.stage_seconds(state['tasks'][1], 3600) > 300


def test_script_time_is_bounded_and_animator_gets_most_available_time():
    c = load_config(overrides={'output': {'target_seconds': 9}})
    state = {'config': c, 'execution': policy(c), 'tasks': [
        {'stage': 'script', 'status': 'running', 'ad': None},
        {'stage': 'animate', 'status': 'pending', 'ad': 0},
        {'stage': 'edit', 'status': 'pending', 'ad': 0},
        {'stage': 'frame', 'status': 'pending', 'ad': 0},
        {'stage': 'qa', 'status': 'pending', 'ad': 0},
        {'stage': 'package', 'status': 'pending', 'ad': 0}]}
    budget = Budget(state, lambda *a: None)
    assert budget.stage_seconds(state['tasks'][0], 3600) <= 60
    assert budget.stage_seconds(state['tasks'][1], 3600) >= 900


def test_actual_script_job_is_short_and_retains_chosen_model(tmp_path):
    store = Store(tmp_path)
    config = load_config()
    state = store.create(config)
    state.update(tasks=build_tasks(1, compact=True), sources=[],
                 models={'workers': {'writer': [{'provider': 'codex', 'model': 'chosen-writer',
                                                'effort': 'high'}]}})
    calls = []
    def worker(profile, work, prompt, log, **kwargs):
        calls.append((profile, prompt, kwargs))
        (work/'result.json').write_text(json.dumps({'summary': 'Chosen guide', 'files': [],
                                                  'scripts': [script()]}))
        return {'kind': 'ok'}
    engine = Engine(store, execute=worker, auth=lambda _: True)
    engine.budget = Budget(state, store.save)
    engine.agent_task(state, state['tasks'][0], store.path(state['id']))
    assert state['tasks'][0]['status'] == 'succeeded'
    profile, prompt, kwargs = calls[0]
    assert profile['model'] == 'chosen-writer' and profile['effort'] == 'low'
    assert state['models']['workers']['writer'][0]['effort'] == 'high'
    assert len(prompt) < 4500 and kwargs['timeout'] <= 60
    assert 'exactly COUNT guides' in prompt
    assert 'Do not repeat a recent premise' in prompt


def test_editor_repair_is_bounded_and_never_restarts_scripting(tmp_path):
    store = Store(tmp_path)
    state = store.create(load_config()); state['tasks'] = build_tasks(1, compact=True)
    script_task, animator, editor = state['tasks'][:3]
    script_task.update(status='succeeded', result={'scripts': [script()]})
    animator.update(status='succeeded', result={'preview': 'accepted-preview'})
    editor.update(status='succeeded', result={'verdict': 'revise', 'findings': ['visible blocker']})
    engine = Engine(store)
    engine.review_transition(state, editor)
    assert script_task['status'] == 'succeeded'
    assert animator['status'] == 'pending' and animator['previous']['preview'] == 'accepted-preview'
    assert engine.next_task(state) == animator
    editor.update(status='succeeded', result={'verdict': 'revise', 'findings': ['still broken']})
    engine.review_transition(state, editor)
    assert editor['status'] == 'failed' and editor['rounds'] == 1


def test_explicit_script_resume_gets_new_stage_allowance_not_new_run_budget():
    config = load_config(overrides={'output': {'target_seconds': 9}})
    state = {'config': config, 'tasks': build_tasks(1, compact=True), 'execution': policy(config)}
    task = state['tasks'][0]
    task.update(status='pending', revision=1, attempts=[
        {'revision': 0, 'started': 100, 'ended': 160, 'kind': 'timeout'}])
    state['execution']['active_seconds'] = 60
    budget = Budget(state, lambda *args: None)
    assert 59 <= budget.stage_seconds(task, 3600) <= 60
    assert budget.remaining() < state['execution']['hard_seconds'] - 59


def test_full_frame_cta_brief_agrees_with_existing_direction_contract(tmp_path):
    from harness.production import production_brief
    config = load_config(overrides={'output': {'target_seconds': 9, 'frame': 'full', 'cta': True}})
    state = {'config': config, 'tasks': build_tasks(1, compact=True)}
    prompt = production_brief(state, state['tasks'][0], tmp_path, 60, tmp_path)
    project = json.loads(prompt.split('\nPROJECT\n')[1])
    assert project['CARD_SECONDS'] == config['output']['end_card_seconds']
