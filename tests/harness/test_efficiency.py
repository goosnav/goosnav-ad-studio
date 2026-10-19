"""Tests for the lean pipeline. None creates a real video or calls an LLM."""
import json

import pytest

from harness.briefs import brief
from harness.config import load_config
from harness.contracts import ContractError, validate
from harness.store import Store
from harness.workflow import Engine, build_tasks, ROLES, agent_deadline, HEAVY_STAGES


def test_pipeline_replaces_redundant_reviews_with_one_selection_and_final_gate():
    tasks = build_tasks(3)
    stages = [t['stage'] for t in tasks]
    assert [t['stage'] for t in tasks if t['ad'] is None] == ['research', 'write', 'select']
    assert [t['stage'] for t in tasks if t['ad'] == 0] == [
        'direct', 'assets', 'audio', 'animate', 'edit', 'frame', 'qa',
        'creative_qa', 'package']
    assert len([t for t in tasks if t['stage'] in ROLES]) == 3 + 3 * 6
    assert 'animate' in HEAVY_STAGES
    assert agent_deadline(load_config(), 'research')[0] == 180


def test_prompts_omit_unrelated_history_and_model_routing():
    c = load_config()
    sentinel = 'EXTRA_OLD_SCRIPT_' * 800
    inputs = {
        'campaign-research': {'brand_brief': 'Plain brief', 'creative_directions': 'Ordinary setup',
                              'references': [], 'summary': 'checked', 'files': []},
        'campaign-write': {'scripts': [sentinel], 'summary': 'unused', 'files': []},
        'ad-01-audio': {'mix': sentinel}
    }
    prompt = brief(build_tasks(1)[1], c, inputs, [])
    assert 'Plain brief' in prompt
    assert sentinel not in prompt
    assert '"workers"' not in prompt
    assert '"limits"' not in prompt
    assert '"delivery"' not in prompt
    assert len(prompt) < 12000


def test_final_editor_handoff_only_contains_needed_results():
    c = load_config()
    inputs = {
        'selected_script': {'id': 'A', 'script': 'One clear beat'},
        'ad-01-direct': {'direction': {'duration': 10}},
        'ad-01-assets': {'scene': '/accepted/scene.blend'},
        'ad-01-audio': {'mix': '/accepted/mix.wav'},
        'ad-01-animate': {'preview': '/accepted/preview.mp4'},
        'ad-01-qa': {'noise': 'SHOULD_NOT_REACH_EDITOR'},
        'campaign-write': {'scripts': ['OTHER_60_SCRIPTS']}
    }
    prompt = brief(next(t for t in build_tasks(1) if t['stage']=='edit'), c, inputs, [])
    assert '/accepted/scene.blend' in prompt
    assert '/accepted/mix.wav' in prompt
    assert 'OTHER_60_SCRIPTS' not in prompt
    assert 'SHOULD_NOT_REACH_EDITOR' not in prompt


def test_selection_rejection_is_a_hard_gate_and_rewinds_writing(tmp_path):
    cfg = load_config()
    store = Store(tmp_path)
    engine = Engine(store)
    store.save = lambda *args, **kwargs: None
    state = {'id': 'fixture', 'config': cfg, 'tasks': build_tasks(1)}
    for task in state['tasks']:
        task['status'] = 'succeeded'
    review = next(t for t in state['tasks'] if t['stage'] == 'select')
    review['result'] = {'verdict': 'revise', 'selected': [], 'findings': [
        {'target': 'first script', 'severity': 'blocking',
         'problem': 'nonsense exchange', 'fix': 'rewrite the second line'}]}
    engine.review_transition(state, review)
    assert next(t for t in state['tasks'] if t['stage'] == 'write')['status'] == 'pending'
    assert review['status'] == 'pending'
    state = {'id': 'fixture', 'config': cfg, 'tasks': build_tasks(1)}
    for task in state['tasks']:
        task['status'] = 'succeeded'
    review = next(t for t in state['tasks'] if t['stage'] == 'select')
    review.update(rounds=cfg['limits']['repairs'],
                  result={'verdict': 'revise', 'selected': [], 'findings': [
                      {'target': 'script', 'severity': 'minor',
                       'problem': 'no coherent ending', 'fix': 'rewrite ending'}]})
    engine.review_transition(state, review)
    assert review['status'] == 'needs_review'


def test_editor_requires_plan_and_declared_output(tmp_path):
    data = {'summary': 'done', 'files': []}
    with pytest.raises(ContractError, match='plan'):
        validate('edit', data, tmp_path, {})
    data['plan'] = {'segments': []}
    with pytest.raises(ContractError, match='master'):
        validate('edit', data, tmp_path, {})


def test_quick_invalid_worker_tries_only_one_time_per_route(tmp_path):
    cfg = load_config()
    store = Store(tmp_path)
    state = store.create(cfg)
    calls = []
    def resolver(workers):
        return {'workers': {role: [
            {'provider':'codex','model':'fixture-a'},
            {'provider':'claude','model':'fixture-b'}] for role in workers}}
    def run_worker(profile, *args, **kwargs):
        calls.append(profile['model'])
        return {'kind': 'ok', 'detail': 'failed to write result.json'}
    Engine(store, execute=run_worker, resolve=resolver, auth=lambda _:True,
           preflight=lambda _:[]).run(state['id'], max_steps=1)
    assert calls == ['fixture-a', 'fixture-b']


def test_review_severity_synonyms_are_normalized_and_unknown_still_rejected(tmp_path):
    def review(severity):
        return {'summary': 's', 'files': [], 'verdict': 'revise',
                'findings': [{'target': 'beat 2', 'severity': severity, 'problem': 'p', 'fix': 'f'}]}
    data = validate('creative_qa', review('Major'), tmp_path, {})
    assert data['findings'][0]['severity'] == 'important'
    assert validate('creative_qa', review('critical'), tmp_path, {})['findings'][0]['severity'] == 'blocking'
    with pytest.raises(ContractError, match='Unknown finding severity'):
        validate('creative_qa', review('spicy'), tmp_path, {})


def test_select_brief_states_the_exact_number_to_select():
    c = load_config(); c['count'] = 1
    task = next(t for t in build_tasks(1) if t['stage'] == 'select')
    assert 'Select EXACTLY 1 script ID' in brief(task, c, {}, [])


def test_direct_brief_states_where_the_beats_must_end():
    c = load_config()
    task = next(t for t in build_tasks(1) if t['stage'] == 'direct')
    o = c['output']
    assert f"end at {o['target_seconds'] - o['end_card_seconds']:g} s" in brief(task, c, {}, [])
