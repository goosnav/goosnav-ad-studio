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
                product='Book', cta='See the book', viewer_takeaway='A book worth continuing to read.',
                cast=[{'speaker': 'Customer', 'character': 'ordinary', 'reason': 'Customer in a shop'},
                      {'speaker': 'Clerk', 'character': 'ordinary', 'reason': 'Clerk in a shop'}],
                dialogue=[{'speaker': 'Customer', 'text': 'My book?'},
                          {'speaker': 'Clerk', 'text': 'One more page.'}])


def test_script_contract_needs_exactly_one_usable_guide_per_ad(tmp_path):
    context = {'count': 1, 'compact': True}
    good = {'summary': 'One guide', 'files': [], 'scripts': [script()]}
    assert validate('script', good, tmp_path, context)['scripts'][0]['title'] == 'The Last Copy'
    for scripts in ([], [script(), script('two')], [{'id': 'broken'}]):
        with pytest.raises(ContractError):
            validate('script', {**good, 'scripts': scripts}, tmp_path, context)


def test_script_needs_explicit_dialogue_and_cast_not_a_visual_riddle(tmp_path):
    import copy
    for key in ('dialogue', 'cast', 'viewer_takeaway'):
        bad = script(); bad.pop(key)
        with pytest.raises(ContractError):
            validate('script', {'summary': 'guide', 'files': [], 'scripts': [bad]}, tmp_path, {})
    bad = copy.deepcopy(script()); bad['dialogue'][0]['speaker'] = 'Mystery person'
    with pytest.raises(ContractError, match='speaker'):
        validate('script', {'summary': 'guide', 'files': [], 'scripts': [bad]}, tmp_path, {})


def test_animator_brief_prioritizes_conversation_framing_over_prop_mechanics():
    from harness.production import ANIMATOR_JOB
    assert 'Frame speakers\' upper bodies and faces clearly at phone size' in ANIMATOR_JOB
    assert 'Start near their eye level' in ANIMATOR_JOB
    assert 'not at distant environment spawn anchors' in ANIMATOR_JOB
    assert 'without constructing or manipulating another prop' in ANIMATOR_JOB


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


def test_script_word_estimate_is_advisory_and_never_truncates_dialogue(tmp_path):
    import copy
    from harness.production import validate_production_media
    config = load_config(overrides={'output': {'target_seconds': 7}})
    guide = script()
    guide['dialogue'] = [{'speaker': 'Customer', 'text': 'Lend me the book tonight?'},
                         {'speaker': 'Clerk', 'text': "No, I'm keeping these drawings."}]
    before = copy.deepcopy(guide)
    validate_production_media(None, {}, {'stage': 'script'}, {'scripts': [guide]}, tmp_path, config)
    assert guide['timing_guidance'] == {'spoken_words': 10, 'target_words': 9,
                                       'story_seconds': 4.5, 'over_target': True}
    assert {k: v for k, v in guide.items() if k != 'timing_guidance'} == before


def test_one_script_above_word_target_does_not_discard_ten_ad_batch(tmp_path):
    import copy
    store = Store(tmp_path)
    config = load_config(overrides={'count': 10, 'output': {'target_seconds': 7}})
    state = store.create(config)
    state.update(tasks=build_tasks(10, compact=True), sources=[],
                 models={'workers': {'writer': [{'provider': 'codex', 'model': 'chosen-writer'}]}})
    guides = [script(f'ad-{i}') for i in range(10)]
    guides[-1]['dialogue'] = [{'speaker': 'Customer', 'text': 'Lend me the book tonight?'},
                             {'speaker': 'Clerk', 'text': "No, I'm keeping these drawings."}]
    before = copy.deepcopy(guides)

    def worker(profile, work, prompt, log, **kwargs):
        (work / 'result.json').write_text(json.dumps({'summary': 'Ten guides', 'files': [],
                                                    'scripts': guides}))
        return {'kind': 'ok'}

    engine = Engine(store, execute=worker, auth=lambda _: True)
    task = state['tasks'][0]
    engine.agent_task(state, task, store.path(state['id']))
    assert task['status'] == 'succeeded'
    assert len(task['attempts']) == 1
    assert [s['id'] for s in task['result']['scripts']] == [s['id'] for s in before]
    assert [s['dialogue'] for s in task['result']['scripts']] == [s['dialogue'] for s in before]
    animator = next(t for t in state['tasks'] if t['stage'] == 'animate' and t['ad'] == 9)
    selected = engine.inputs(state, animator)['selected_script']
    assert selected['timing_guidance']['over_target'] is True
    assert selected['dialogue'] == before[-1]['dialogue']


def test_obsolete_word_limit_is_corrected_even_when_saved_feedback_is_long(tmp_path):
    from harness.production import production_brief
    state = {'config': load_config(), 'tasks': build_tasks(1, compact=True)}
    task = state['tasks'][0]
    task['feedback'] = ('Previous claude attempt: invalid. Script has 10 spoken words; '
                        'maximum 9 for the story window. ' + 'Keep complete thoughts. ' * 150)
    prompt = production_brief(state, task, tmp_path, 60, tmp_path)
    repair = prompt.split('\nREPAIR: Continue existing local files; resubmit a complete result.json.\n')[1]
    assert 'word-count-only rejection is obsolete' in repair
    assert len(repair) <= 2200


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
    assert len(prompt) < 6500 and kwargs['timeout'] <= 60
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
    assert budget.remaining() == float('inf')
    assert budget.spent() >= 60


def test_full_frame_cta_brief_agrees_with_existing_direction_contract(tmp_path):
    from harness.production import production_brief
    config = load_config(overrides={'output': {'target_seconds': 9, 'frame': 'full', 'cta': True}})
    state = {'config': config, 'tasks': build_tasks(1, compact=True)}
    prompt = production_brief(state, state['tasks'][0], tmp_path, 60, tmp_path)
    project = json.loads(prompt.split('\nPROJECT\n')[1])
    assert project['CARD_SECONDS'] == config['output']['end_card_seconds']
