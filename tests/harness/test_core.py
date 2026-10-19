import json
from pathlib import Path

import pytest

from harness.config import load_config, ConfigError
from harness.store import Store, Busy
from harness.contracts import validate, ContractError


def test_blank_config_and_minimal_product(tmp_path):
    p = tmp_path / 'config.json'
    p.write_text(json.dumps({'website': 'example.com', 'products': [
        {'name': 'Book', 'description': 'A book of drawings'}]}))
    c = load_config(p)
    assert c['website'] == 'https://example.com'
    assert c['count'] == 1
    assert c['workers']['writer'][0]['model']
    assert c['workers']['critic'][0]['model'] != c['workers']['writer'][0]['model']


@pytest.mark.parametrize('data', [{'count': 0}, {'count': True}, {'nonsense': 1},
    {'website': 'file:///etc/passwd'}, {'products': [{'name': 'Missing description'}]},
    {'limits': {'timeout_seconds': -1}}, {'workers': {'writer': []}}])
def test_invalid_config(tmp_path, data):
    p = tmp_path / 'config.json'
    p.write_text(json.dumps(data))
    with pytest.raises(ConfigError):
        load_config(p)


def test_malformed_config_is_not_ignored(tmp_path):
    p = tmp_path / 'config.json'; p.write_text('{broken')
    with pytest.raises(ConfigError):
        load_config(p)


def test_state_snapshot_and_control(tmp_path):
    s = Store(tmp_path)
    c = load_config(None)
    run = s.create(c)
    c['website'] = 'https://changed.example'
    assert s.get(run['id'])['config']['website'] == ''
    s.control(run['id'], 'cancel')
    assert s.control_value(run['id']) == 'cancel'
    assert s.events(run['id'])[0]['kind'] == 'created'


def test_single_worker_lock(tmp_path):
    s = Store(tmp_path)
    with s.worker_lock():
        with pytest.raises(Busy):
            with Store(tmp_path).worker_lock():
                pass


def test_artifact_cannot_escape_or_use_symlink(tmp_path):
    work = tmp_path / 'work'; work.mkdir()
    outside = tmp_path / 'outside.txt'; outside.write_text('secret')
    (work / 'link.txt').symlink_to(outside)
    for path in ['../outside.txt', 'link.txt']:
        with pytest.raises(ContractError):
            validate('assets', {'summary': 'ok', 'files': [{'path': path, 'kind': 'asset'}],
                'assets': [{'name': 'x', 'source': 'original', 'rights': 'owned', 'proxy': False}]}, work, {})


def test_selection_count_and_ids(tmp_path):
    data = {'summary': 'chosen', 'files': [], 'selected': ['x', 'x'], 'reason': 'best'}
    with pytest.raises(ContractError):
        validate('select', data, tmp_path, {'count': 2, 'candidate_ids': ['x', 'y']})


def test_empty_result_cannot_pass(tmp_path):
    with pytest.raises(ContractError):
        validate('animate', {'summary': 'done', 'files': []}, tmp_path, {})


def test_empty_diagnostic_log_can_be_promoted_and_verified(tmp_path):
    from harness.contracts import promote, verify_accepted
    work = tmp_path / 'work'; work.mkdir()
    (work / 'freeze_black.log').touch()  # FFmpeg emits nothing when there are no detections.
    data = validate('research', {'summary': 'checked', 'brand_brief': 'brand',
        'creative_directions': 'direction', 'references': [],
        'files': [{'path': 'freeze_black.log', 'kind': 'notes'}]}, work, {})
    accepted = promote(data, work, tmp_path / 'accepted')
    verify_accepted(accepted)
    assert accepted['files'][0]['bytes'] == 0
    assert Path(accepted['files'][0]['path']).is_file()


@pytest.mark.parametrize('path,kind', [('preview.mp4', 'video'), ('mix.wav', 'audio'),
                                      ('source.py', 'source'), ('scene.blend', 'source')])
def test_empty_production_artifacts_are_still_rejected(tmp_path, path, kind):
    (tmp_path / path).touch()
    with pytest.raises(ContractError, match='Missing/empty artifact'):
        validate('research', {'summary': 'checked', 'files': [{'path': path, 'kind': kind}]}, tmp_path, {})


def test_virtualenv_interpreter_symlink_is_preserved(tmp_path):
    venv=tmp_path/'venv/bin';venv.mkdir(parents=True)
    (venv/'python').symlink_to('/usr/bin/python3')
    cfg=tmp_path/'config.json';cfg.write_text(json.dumps({'audio':{'python':'venv/bin/python'}}))
    assert load_config(cfg)['audio']['python']==str(venv/'python')


def test_target_length_defaults_to_ten_seconds_and_derives_range():
    o = load_config()['output']
    assert (o['target_seconds'], o['min_seconds'], o['max_seconds']) == (10, 8, 13)
    o = load_config(None, {'output': {'target_seconds': 30}})['output']
    assert (o['min_seconds'], o['max_seconds']) == (24, 39)
    o = load_config(None, {'output': {'target_seconds': 15, 'min_seconds': 14, 'max_seconds': 16}})['output']
    assert (o['min_seconds'], o['max_seconds']) == (14, 16)
    for bad in ({'target_seconds': 0}, {'target_seconds': 20, 'max_seconds': 15}, {'target_seconds': 301}):
        with pytest.raises(ConfigError):
            load_config(None, {'output': bad})


def test_writer_brief_states_target_length():
    from harness.briefs import brief
    from harness.workflow import build_tasks
    c = load_config(None, {'output': {'target_seconds': 12}})
    text = brief(build_tasks(1)[1], c, {}, [])
    assert 'TARGET LENGTH: 12 seconds' in text and '10-16' in text


def test_promote_maps_declared_paths_inside_lists_and_boards(tmp_path):
    from harness.contracts import promote
    work = tmp_path / 'w'; (work / 'boards').mkdir(parents=True)
    for name in ('a.py', 'b.py', 'boards/0.png'):
        (work / name).write_text('x')
    data = {'summary': 's', 'files': [{'path': p, 'kind': 'source'} for p in ('a.py', 'b.py', 'boards/0.png')],
            'source': ['a.py', 'b.py'], 'boards': [{'beat': 0, 'image': 'boards/0.png'}]}
    out = promote(data, work, tmp_path / 'accepted')
    assert out['source'] == [str(tmp_path / 'accepted' / 'a.py'), str(tmp_path / 'accepted' / 'b.py')]
    assert out['boards'][0] == {'beat': 0, 'image': str(tmp_path / 'accepted' / 'boards/0.png')}


def test_unexpected_result_shapes_become_repairs_not_run_failures(tmp_path):
    from harness.workflow import Engine
    store = Store(tmp_path); c = load_config(); c['limits']['repairs'] = 0
    run = store.create(c); calls = []
    def worker(profile, work, *a, **k):
        calls.append(1)
        (work / 'result.json').write_text(json.dumps({'summary': 's', 'files': [], 'brand_brief': 'b',
            'creative_directions': 'c', 'references': [{'url': 'u', 'observation': 'o', 'application': 'a'}]}))
        return {'kind': 'ok'}
    e = Engine(store, execute=worker, resolve=lambda w: {'workers': {r: [{'provider': 'claude', 'model': 'm'}] for r in w}},
               auth=lambda _: True)
    def boom(*a, **k): raise TypeError("unhashable type: 'list'")
    e.validate_media = boom
    state = e.run(run['id'], max_steps=1)
    research = state['tasks'][0]
    assert state['status'] != 'failed' or 'TypeError' not in state.get('error', '')
    assert research['attempts'][-1]['kind'] == 'invalid' and 'unhashable' in research['feedback']
