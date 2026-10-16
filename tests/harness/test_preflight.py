from harness.config import load_config
from harness.preflight import check_dependencies
from harness.store import Store
from harness.workflow import Engine, execute_worker


def test_missing_dependencies_are_named_before_any_agent_starts(tmp_path):
    c = load_config(None, {'website': 'example.com', 'tools': {'blender': 'no-such-blender'},
                           'audio': {'python': str(tmp_path / 'missing-python')}})
    problems = check_dependencies(c)
    text = ' '.join(problems)
    assert 'no-such-blender' in text and 'audio.python' in text and 'Frame' in text


def test_engine_stops_on_preflight_without_spending_a_worker(tmp_path):
    store = Store(tmp_path); run = store.create(load_config())
    calls = []
    e = Engine(store, execute=lambda *a, **k: calls.append(1), auth=lambda _: True,
               resolve=lambda w: {'workers': {}}, preflight=lambda c: ['blender: not found'])
    state = e.run(run['id'])
    assert state['status'] == 'failed' and 'blender: not found' in state['error'] and not calls


def test_fake_workers_skip_the_real_preflight(tmp_path):
    e = Engine(Store(tmp_path), execute=lambda *a, **k: None)
    assert e.preflight(load_config()) == []
    assert Engine(Store(tmp_path)).execute is execute_worker
