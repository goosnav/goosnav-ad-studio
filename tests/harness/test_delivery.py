"""Drive upload must be opt-in, non-destructive and retryable."""
from pathlib import Path
from types import SimpleNamespace

from harness.config import load_config
from harness.delivery import upload_run
from harness.store import Store
from harness.workflow import build_tasks


def fixture(tmp_path):
    store = Store(tmp_path / 'state')
    output = tmp_path / 'output'
    config = load_config(None, {'output': {'folder': str(output)},
                                'delivery': {'drive': 'agent-exchange:deliverables/ad-studio'}})
    state = store.create(config)
    state['tasks'] = build_tasks(1)
    package = next(t for t in state['tasks'] if t['stage'] == 'package')
    package['status'] = 'succeeded'
    target = output / state['id']
    target.mkdir(parents=True)
    (target / 'ad-01.mp4').write_bytes(b'video')
    (target / 'ad-01.zip').write_bytes(b'archive')
    return store, state, target


def test_upload_copies_and_verifies_then_saves_status(tmp_path):
    store, state, folder = fixture(tmp_path)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == 'lsf':
            return SimpleNamespace(stdout='ad-01.mp4\nad-01.zip\n')
        return SimpleNamespace(stdout='')

    output = upload_run(store, state, run=fake_run, which=lambda _: '/usr/bin/rclone')
    remote = 'agent-exchange:deliverables/ad-studio/' + state['id']
    assert calls[0][:4] == ['rclone', 'copy', str(folder), remote]
    assert '--include' in calls[0]
    assert calls[1][:3] == ['rclone', 'lsf', remote]
    assert output['delivery']['status'] == 'uploaded'
    assert store.get(state['id'])['delivery']['files'] == ['ad-01.mp4', 'ad-01.zip']


def test_missing_rclone_does_not_change_render_status(tmp_path):
    store, state, _ = fixture(tmp_path)
    state['status'] = 'complete'
    result = upload_run(store, state, which=lambda _: None)
    assert result['status'] == 'complete'
    assert result['delivery']['status'] == 'failed'
    assert 'rclone' in result['delivery']['error']


def test_missing_local_output_does_not_invoke_rclone(tmp_path):
    store, state, folder = fixture(tmp_path)
    (folder / 'ad-01.zip').unlink()

    def never_run(*args, **kwargs):
        raise AssertionError('should not upload incomplete deliverables')

    result = upload_run(store, state, run=never_run, which=lambda _: '/usr/bin/rclone')
    assert result['delivery']['status'] == 'failed'
    assert 'ad-01.zip' in result['delivery']['error']


def test_server_listing_must_contain_every_file_and_retry_succeeds(tmp_path):
    store, state, _ = fixture(tmp_path)
    listed = ['ad-01.mp4\n', 'ad-01.mp4\nad-01.zip\n']

    def fake_run(cmd, **kwargs):
        if cmd[1] == 'lsf':
            return SimpleNamespace(stdout=listed.pop(0))
        return SimpleNamespace(stdout='')

    first = upload_run(store, state, run=fake_run, which=lambda _: '/usr/bin/rclone')
    assert first['delivery']['status'] == 'failed'
    assert 'ad-01.zip' in first['delivery']['error']
    second = upload_run(store, first, run=fake_run, which=lambda _: '/usr/bin/rclone')
    assert second['delivery']['status'] == 'uploaded'


def test_rclone_destination_must_be_a_remote(tmp_path):
    store, state, _ = fixture(tmp_path)
    state['config']['delivery']['drive'] = '/tmp/other-directory'
    result = upload_run(store, state, which=lambda _: '/usr/bin/rclone')
    assert result['delivery']['status'] == 'failed'
    assert 'rclone destination' in result['delivery']['error']
