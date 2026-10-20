"""Ordinary review repairs must not become operator approval gates."""
import pytest

from harness.config import load_config
from harness.execution import Budget, policy
from harness.store import Store
from harness.workflow import Engine, build_tasks


def review_run(tmp_path, stage='board_review', rounds=1):
    store = Store(tmp_path)
    state = store.create(load_config(overrides={'count': 3, 'generation': {'effort': 'high'}}))
    state['execution'] = policy(state['config'])
    state['tasks'] = build_tasks(3, modern=True)
    for t in state['tasks']:
        t.update(status='succeeded', result={'summary': 'accepted', 'files': []})
    review = next(t for t in state['tasks'] if t['ad'] == 1 and t['stage'] == stage)
    review.update(rounds=rounds, result={'summary': 'repair', 'files': [], 'verdict': 'revise',
        'restart': 'assets' if stage == 'board_review' else 'frame',
        'findings': [{'severity': 'important', 'target': 'shot', 'problem': 'unreadable', 'fix': 'reframe'}]})
    return store, state, review


def test_high_board_review_uses_configured_repairs_without_one_round_clamp(tmp_path):
    store, state, review = review_run(tmp_path)
    Engine(store).review_transition(state, review)
    assert review['status'] == 'pending'
    assert review['rounds'] == 2
    assert next(t for t in state['tasks'] if t['ad'] == 1 and t['stage'] == 'assets')['status'] == 'pending'
    assert all(t['status'] == 'succeeded' for t in state['tasks'] if t['ad'] in (0, 2))


@pytest.mark.parametrize('stage,setting', [('board_review', 'board_repairs'), ('creative_qa', 'review_repairs')])
@pytest.mark.parametrize('allowance', [0, 1])
def test_exact_configured_review_limit_switches_to_bounded_replan(tmp_path, stage, setting, allowance):
    store, state, review = review_run(tmp_path, stage=stage, rounds=allowance)
    state['config']['limits'][setting] = allowance
    Engine(store).review_transition(state, review)
    assert state.get('autonomous_recovery', {}).get('1') == 1
    assert next(t for t in state['tasks'] if t['ad'] == 1 and t['stage'] == 'direct')['status'] == 'pending'


def test_exhausted_review_replans_automatically_and_has_durable_bound(tmp_path):
    store, state, review = review_run(tmp_path, rounds=99)
    engine = Engine(store)
    engine.review_transition(state, review)
    assert review['status'] == 'pending'
    assert next(t for t in state['tasks'] if t['ad'] == 1 and t['stage'] == 'direct')['status'] == 'pending'
    assert state['autonomous_recovery']['1'] == 1
    assert review['rounds'] == 0
    assert 'AUTONOMOUS' in review['feedback']
    # An explicit reset of stage counters cannot create unlimited replans.
    review.update(status='succeeded', rounds=99, result={'summary': 'still broken', 'files': [],
                  'verdict': 'revise', 'findings': [{'severity': 'blocking'}]})
    engine.review_transition(state, review)
    assert review['status'] == 'failed'
    assert state['autonomous_recovery']['1'] == 1
    assert not any(t['status'] == 'needs_review' for t in state['tasks'])


def test_saved_manual_gate_is_reopened_without_changing_successful_ads(tmp_path):
    store, state, review = review_run(tmp_path, stage='creative_qa')
    review['status'] = 'needs_review'
    Engine(store).resume_reviews(state)
    assert review['status'] == 'pending'
    assert all(t['status'] == 'succeeded' for t in state['tasks'] if t['ad'] in (0, 2))


def test_nearly_finished_ad_takes_precedence_over_earlier_long_repair(tmp_path):
    store, state, review = review_run(tmp_path)
    engine = Engine(store)
    engine.rewind(state, 1, 'assets', 'repair')
    engine.rewind(state, 2, 'frame', 'repair')
    assert engine.next_task(state)['id'] == 'ad-03-frame'


def test_delivery_time_is_not_charged_against_generation_budget(tmp_path, monkeypatch):
    import harness.execution as execution
    clock = [100.0]
    monkeypatch.setattr(execution.time, 'monotonic', lambda: clock[0])
    state = {'execution': {'active_seconds': 0, 'hard_seconds': 50}}
    budget = Budget(state, lambda *args: None)
    clock[0] += 5
    with budget.external('delivery_seconds'):
        clock[0] += 120
    clock[0] += 3
    assert budget.spent() == 8
    assert state['execution']['delivery_seconds'] == 120
    assert budget.remaining() == 42


def test_engine_uploads_first_package_before_starting_the_second(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import harness.delivery as delivery
    from tests.harness.test_workflow import fake_models
    config = load_config(overrides={'count': 2, 'output': {'folder': str(tmp_path / 'videos')},
                                    'delivery': {'drive': 'agent-exchange:ads'}})
    store = Store(tmp_path / 'state')
    state = store.create(config)
    state['tasks'] = [t for t in build_tasks(2) if t['stage'] == 'package']
    store.save(state, 'fixture')
    names, events = set(), []
    def remote(command, **kwargs):
        if 'copyto' in command:
            local, target = command[command.index('copyto')+1:command.index('copyto')+3]
            snapshot = store.get(state['id'])
            events.append(('upload', snapshot['tasks'][1]['status']))
            names.add(target.rsplit('/', 1)[-1])
        return SimpleNamespace(stdout='\n'.join(names))
    monkeypatch.setattr(delivery, '_bounded_run', remote)
    monkeypatch.setattr(delivery.shutil, 'which', lambda _: 'rclone')
    engine = Engine(store, resolve=fake_models, auth=lambda _: True, preflight=lambda _: [])
    def produce(snapshot, task, root):
        events.append(('package', task['ad']))
        folder = tmp_path / 'videos' / state['id']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"ad-{task['ad']+1:02}.mp4").write_bytes(b'accepted fixture video')
        task.update(status='succeeded', result={'summary': 'accepted package', 'files': []})
        store.save(snapshot, 'builtin_finished')
    engine.builtin_task = produce  # Only media generation is replaced; scheduler/delivery/store stay real.
    result = engine.run(state['id'])
    assert events == [('package', 0), ('upload', 'pending'), ('package', 1), ('upload', 'succeeded')]
    assert result['status'] == 'complete'
    assert len(result['delivery']['verified']) == 2
