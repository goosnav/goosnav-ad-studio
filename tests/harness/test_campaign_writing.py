"""Campaign cardinality must reach writers and survive bounded repair/resume."""
import json

import pytest

from harness.briefs import brief
from harness.cli import reopen
from harness.config import load_config
from harness.contracts import ContractError, validate
from harness.store import Store
from harness.workflow import Engine, build_tasks


def scripts(count):
    return [{'id': f'script-{i}', 'title': f'Story {i}', 'premise': f'Premise {i}',
             'script': f'Dialogue {i}', 'visual_direction': 'Two shots',
             'product': 'Book', 'cta': 'Visit the shop'} for i in range(count)]


def result(count):
    return {'summary': 'Candidate scripts', 'files': [], 'scripts': scripts(count)}


@pytest.mark.parametrize('modern', [False, True])
@pytest.mark.parametrize('stage', ['write', 'revise'])
@pytest.mark.parametrize('count,required', [(1, 2), (3, 6)])
def test_writer_receives_campaign_count_independent_of_product_count(modern, stage, count, required):
    config = load_config()
    config['count'] = count
    config['products'] = ['Book', 'Cards']
    prompt = brief({'stage': stage, 'ad': None}, config, {}, [], modern=modern)
    project = json.loads(prompt.split('\nPROJECT\n')[1].split('\nREPAIR\n')[0])
    assert project['config']['count'] == count
    assert f'{required} candidate scripts in total' in prompt


@pytest.mark.parametrize('stage', ['write', 'revise'])
def test_short_batch_error_explains_expected_actual_and_missing(stage, tmp_path):
    with pytest.raises(ContractError) as caught:
        validate(stage, result(4), tmp_path, {'count': 3})
    message = str(caught.value)
    assert '3 ads' in message
    assert 'at least 6' in message
    assert 'received 4' in message
    assert 'add 2' in message
    assert 'Preserve' in message


@pytest.mark.parametrize('bad', [None, {}, 'scripts'])
def test_non_array_scripts_get_actionable_contract_error(bad, tmp_path):
    data = result(6)
    data['scripts'] = bad
    with pytest.raises(ContractError, match='scripts must be an array'):
        validate('write', data, tmp_path, {'count': 3})


def test_bad_script_entry_gets_indexed_contract_error(tmp_path):
    data = result(6)
    data['scripts'][4] = 'not an object'
    with pytest.raises(ContractError, match=r'scripts\[4\] must be an object'):
        validate('write', data, tmp_path, {'count': 3})


def test_script_field_error_identifies_candidate(tmp_path):
    data = result(6)
    data['scripts'][4]['script'] = {'text': 'Dialogue'}
    with pytest.raises(ContractError, match=r'scripts\[4\].*script must be'):
        validate('write', data, tmp_path, {'count': 3})


@pytest.mark.parametrize('repair_succeeds', [True, False])
def test_three_ad_writer_repairs_partial_batch_and_resume_keeps_upstream(tmp_path, repair_succeeds):
    config = load_config()
    config['count'] = 3
    store = Store(tmp_path)
    state = store.create(config)
    research, task = build_tasks(3)[:2]
    research.update(status='succeeded', result={'summary': 'Accepted research', 'files': [],
                    'brand_brief': 'Facts', 'creative_directions': 'World', 'references': []})
    state.update(tasks=[research, task], sources=[], models={'workers': {'writer': [
        {'provider': 'codex', 'model': 'fixture-primary'},
        {'provider': 'claude', 'model': 'fixture-fallback'}]}})
    calls = []

    def worker(profile, work, prompt, log, **kwargs):
        calls.append(profile['provider'])
        if len(calls) == 1:
            data = result(4)
        elif len(calls) == 2:
            data = result(2)  # Reproduce the real fallback dropping candidates.
        else:
            previous = work / f'result.previous-{len(calls)}.json'
            data = json.loads(previous.read_text())
            assert data['scripts'] == scripts(2 if len(calls) == 3 else 4)
            assert f"received {len(data['scripts'])}" in prompt
            assert f"add {6 - len(data['scripts'])}" in prompt
            assert 'Preserve' in prompt
            data['scripts'].extend(scripts(6 if repair_succeeds or len(calls) == 4 else 4)[len(data['scripts']):])
        (work / 'result.json').write_text(json.dumps(data))
        return {'kind': 'ok'}

    engine = Engine(store, execute=worker, auth=lambda _: True)
    engine.agent_task(state, task, store.path(state['id']))
    assert calls == ['codex', 'claude', 'claude']
    assert task['attempts'][-1]['contract_repair'] is True
    if not repair_succeeds:
        assert task['status'] == 'failed'
        assert all(a['kind'] == 'invalid' and a['failure_phase'] == 'contract' for a in task['attempts'])
        # Automatic retries stay bounded; explicit resume gets a fresh revision.
        engine.agent_task(state, task, store.path(state['id']))
        assert len(calls) == 3
        reopen(state)
        engine.agent_task(state, task, store.path(state['id']))
        assert len(calls) == 4
    assert research['status'] == 'succeeded'
    assert research['attempts'] == []
    assert task['status'] == 'succeeded'
    accepted = json.loads(open(task['accepted_manifest']).read())
    assert accepted['scripts'] == scripts(6)
    assert accepted['scripts'][:2] == scripts(2)
