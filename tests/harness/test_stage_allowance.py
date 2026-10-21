from harness.config import load_config
from harness.execution import Budget, policy
from harness.workflow import build_tasks
import pytest


def test_low_fast_director_has_setup_time_without_extending_global_budget():
    cfg = load_config(overrides={'generation': {'effort': 'low', 'fast': True},
                                 'output': {'target_seconds': 9}})
    state = {'config': cfg, 'execution': policy(cfg), 'tasks': build_tasks(1, modern=True)}
    state['execution']['active_seconds'] = 60
    for task in state['tasks']:
        if task['stage'] in ('research', 'write', 'select'):
            task['status'] = 'succeeded'
    direct = next(t for t in state['tasks'] if t['stage'] == 'direct')
    budget = Budget(state, lambda *args: None)
    assert 89 <= budget.stage_seconds(direct, 600) <= 90
    assert state['execution']['hard_seconds'] == 375
    state['execution']['active_seconds'] = 355
    assert 0 < budget.stage_seconds(direct, 600) <= 20
    assert budget.stage_seconds(direct, 5) <= 5


@pytest.mark.parametrize('effort,minimum', [('medium', 120), ('high', 180)])
def test_richer_fast_direction_has_capability_testing_room(effort, minimum):
    cfg = load_config(overrides={'generation': {'effort': effort, 'fast': True},
                                 'output': {'target_seconds': 9}})
    state = {'config': cfg, 'execution': policy(cfg), 'tasks': build_tasks(1, modern=True)}
    budget = Budget(state, lambda *args: None)
    direct = next(t for t in state['tasks'] if t['stage'] == 'direct')
    assert budget.stage_seconds(direct, 600) >= minimum
    assert budget.stage_seconds(direct, 600) <= budget.data['hard_seconds']


@pytest.mark.parametrize('stage', ['assets', 'animate'])
@pytest.mark.parametrize('effort,minimum', [('low', 120), ('medium', 180), ('high', 300)])
def test_scene_work_has_one_useful_attempt_but_cannot_overrun(stage, effort, minimum):
    cfg = load_config(overrides={'generation': {'effort': effort, 'fast': True},
                                 'output': {'target_seconds': 9}})
    state = {'config': cfg, 'execution': policy(cfg), 'tasks': build_tasks(1, modern=True)}
    budget = Budget(state, lambda *args: None)
    task = next(t for t in state['tasks'] if t['stage'] == stage)
    assert budget.stage_seconds(task, 600) >= minimum
    state['execution']['active_seconds'] = state['execution']['hard_seconds'] - 17
    assert 0 < budget.stage_seconds(task, 600) <= 17
