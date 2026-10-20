"""Drive delivery is video-only, flat, non-destructive and retryable."""
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import pytest

from harness.config import load_config
from harness.delivery import upload_run
from harness.store import Store
from harness.workflow import build_tasks


def fixture(tmp_path, count=1):
    store = Store(tmp_path / 'state')
    output = tmp_path / 'output'
    config = load_config(None, {'count': count, 'output': {'folder': str(output)},
                                'delivery': {'drive': 'agent-exchange:deliverables/ad-studio'}})
    state = store.create(config)
    state['created'] = 0  # UTC epoch, independent of wall clock and local timezone.
    state['tasks'] = build_tasks(count)
    for task in state['tasks']:
        if task['stage'] == 'write':
            task.update(status='succeeded', result={'scripts': [
                {'id': f'script-{i}', 'title': 'Chosen Title'} for i in range(count)]})
        elif task['stage'] == 'select':
            task.update(status='succeeded', result={'selected': [f'script-{i}' for i in range(count)]})
        elif task['stage'] == 'package':
            task['status'] = 'succeeded'
    target = output / state['id']
    target.mkdir(parents=True)
    for i in range(count):
        (target / f'ad-{i+1:02}.mp4').write_bytes(b'video')
        (target / f'ad-{i+1:02}.zip').write_bytes(b'archive')
    return store, state, target


class Drive:
    """Replace only the external process; local files and receipts are real."""
    def __init__(self):
        self.calls = []
        self.files = {'old-upload.zip', 'unrelated.mp4'}
        self.fail_copy = None

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        assert kwargs['check'] and kwargs['capture_output'] and kwargs['text']
        if 'copyto' in cmd:
            index = cmd.index('copyto')
            source, destination = cmd[index+1:index+3]
            assert Path(source).is_file()
            if self.fail_copy == len([c for c in self.calls if 'copyto' in c]):
                raise subprocess.CalledProcessError(1, cmd, stderr='temporary Drive failure')
            self.files.add(destination.rsplit('/', 1)[-1].rsplit(':', 1)[-1])
            return SimpleNamespace(stdout='')
        assert 'lsf' in cmd, f'Unexpected remote mutation: {cmd}'
        return SimpleNamespace(stdout='\n'.join(sorted(self.files)) + '\n')


def deliver(store, state, drive):
    return upload_run(store, state, run=drive, which=lambda _: '/usr/bin/rclone')


def test_upload_only_video_to_flat_folder_and_persist_names(tmp_path):
    store, state, folder = fixture(tmp_path)
    drive = Drive()
    result = deliver(store, state, drive)
    receipt = store.get(state['id'])['delivery']
    assert result['delivery']['status'] == 'uploaded'
    name = receipt['names']['ad-01.mp4']
    assert re.fullmatch(r'chosen-title-19700101T000000Z-[a-z0-9]+-ad-01\.mp4', name)
    assert receipt['files'] == [name]
    assert receipt['remote'] == 'agent-exchange:deliverables/ad-studio'
    assert drive.calls == [
        ['rclone', 'copyto', str(folder / 'ad-01.mp4'), receipt['remote'] + '/' + name],
        ['rclone', 'lsf', receipt['remote'], '--files-only'],
    ]
    assert drive.files == {'old-upload.zip', 'unrelated.mp4', name}
    assert (folder / 'ad-01.mp4').read_bytes() == b'video'
    assert (folder / 'ad-01.zip').read_bytes() == b'archive'


def test_missing_zip_is_ok_for_existing_config_snapshot(tmp_path):
    store, state, folder = fixture(tmp_path)
    state['config']['delivery'] = {'drive': 'agent-exchange:deliverables/ad-studio'}
    (folder / 'ad-01.zip').unlink()
    assert deliver(store, state, Drive())['delivery']['status'] == 'uploaded'


def test_missing_rclone_does_not_change_render_status(tmp_path):
    store, state, _ = fixture(tmp_path)
    state['status'] = 'complete'
    result = upload_run(store, state, which=lambda _: None)
    assert result['status'] == 'complete'
    assert result['delivery']['status'] == 'failed'
    assert 'rclone' in result['delivery']['error']


def test_missing_mp4_prevents_any_upload_even_when_other_ads_exist(tmp_path):
    store, state, folder = fixture(tmp_path, 2)
    (folder / 'ad-02.mp4').unlink()
    drive = Drive()
    state['status'] = 'complete'
    result = deliver(store, state, drive)
    assert result['status'] == 'complete'
    assert result['delivery']['status'] == 'failed'
    assert 'ad-02.mp4' in result['delivery']['error']
    assert drive.calls == []


def test_remote_listing_must_verify_every_named_video_then_retry_succeeds(tmp_path):
    store, state, _ = fixture(tmp_path)
    drive = Drive()

    def missing_listing(cmd, **kwargs):
        result = drive(cmd, **kwargs)
        if 'lsf' in cmd:
            return SimpleNamespace(stdout='ad-01.mp4\nad-01.zip\n')
        return result

    result = upload_run(store, state, run=missing_listing, which=lambda _: '/usr/bin/rclone')
    assert result['delivery']['status'] == 'failed'
    assert 'not verified' in result['delivery']['error']
    names = dict(result['delivery']['names'])
    assert deliver(store, store.get(state['id']), drive)['delivery']['names'] == names
    assert store.get(state['id'])['delivery']['status'] == 'uploaded'


@pytest.mark.parametrize('destination', ['/tmp/other-directory', 'https://evil.test/drive/folders/id',
                                         'https://drive.google.com/file/d/id', '--flag:path'])
def test_unsafe_destination_never_invokes_rclone(tmp_path, destination):
    store, state, _ = fixture(tmp_path)
    state['config']['delivery']['drive'] = destination
    drive = Drive()
    result = deliver(store, state, drive)
    assert result['delivery']['status'] == 'failed'
    assert 'rclone destination' in result['delivery']['error']
    assert drive.calls == []


def test_partial_run_uploads_only_succeeded_packages(tmp_path):
    store, state, _ = fixture(tmp_path, 2)
    state['status'] = 'partial'
    next(t for t in state['tasks'] if t['stage'] == 'package' and t['ad'] == 1)['status'] = 'failed'
    drive = Drive()
    result = deliver(store, state, drive)
    assert result['status'] == 'partial'
    assert result['delivery']['status'] == 'uploaded'
    assert set(result['delivery']['names']) == {'ad-01.mp4'}
    assert len([c for c in drive.calls if 'copyto' in c]) == 1


def test_selection_order_and_latest_succeeded_revision_determine_titles(tmp_path):
    store, state, _ = fixture(tmp_path, 2)
    select = next(t for t in state['tasks'] if t['stage'] == 'select')
    select['result']['selected'] = ['script-1', 'script-0']
    state['tasks'].extend([
        {'stage': 'revise', 'status': 'succeeded', 'result': {'scripts': [
            {'id': 'script-0', 'title': 'Revised First'},
            {'id': 'script-1', 'title': 'Revised Second'}]}},
        {'stage': 'revise', 'status': 'failed', 'result': {'scripts': [
            {'id': 'script-1', 'title': 'Rejected Title'}]}},
        {'stage': 'select', 'status': 'failed', 'result': {'selected': ['script-0', 'script-1']}},
    ])
    receipt = deliver(store, state, Drive())['delivery']
    assert receipt['status'] == 'uploaded'
    assert receipt['names']['ad-01.mp4'].startswith('revised-second-')
    assert receipt['names']['ad-02.mp4'].startswith('revised-first-')


@pytest.mark.parametrize('title', ['../../evil\\name\n--flag : x', '🔥 / ..', 'A' * 1000,
                                  'Café — Déjà Vu', '', None, {'title': 'bad'}])
def test_unsafe_or_missing_titles_make_safe_bounded_unique_names(tmp_path, title):
    store, state, _ = fixture(tmp_path, 2)
    for script in next(t for t in state['tasks'] if t['stage'] == 'write')['result']['scripts']:
        script['title'] = title
    receipt = deliver(store, state, Drive())['delivery']
    assert receipt['status'] == 'uploaded'
    assert len(set(receipt['files'])) == 2
    for name in receipt['files']:
        assert re.fullmatch(r'[a-z0-9-]+-19700101T000000Z-[a-z0-9]+-ad-0[12]\.mp4', name)
        assert len(name.encode()) <= 180


@pytest.mark.parametrize('legacy', ['missing-select', 'failed-select', 'missing-writer', 'missing-id'])
def test_legacy_missing_script_metadata_uses_descriptive_fallback(tmp_path, legacy):
    store, state, _ = fixture(tmp_path)
    if legacy == 'missing-select':
        state['tasks'] = [t for t in state['tasks'] if t['stage'] != 'select']
    elif legacy == 'failed-select':
        next(t for t in state['tasks'] if t['stage'] == 'select')['status'] = 'failed'
    elif legacy == 'missing-writer':
        next(t for t in state['tasks'] if t['stage'] == 'write')['result'] = None
    else:
        next(t for t in state['tasks'] if t['stage'] == 'select')['result']['selected'] = ['unknown']
    receipt = deliver(store, state, Drive())['delivery']
    assert receipt['status'] == 'uploaded'
    assert receipt['names']['ad-01.mp4'].startswith('ad-video-19700101T000000Z-')


def test_same_title_and_creation_time_across_runs_do_not_collide(tmp_path):
    store, state, _ = fixture(tmp_path / 'first')
    first = deliver(store, state, Drive())['delivery']['files']
    store, state, _ = fixture(tmp_path / 'second')
    second = deliver(store, state, Drive())['delivery']['files']
    assert set(first).isdisjoint(second)


def test_failed_copy_persists_plan_before_upload_and_retry_keeps_names(tmp_path):
    store, state, _ = fixture(tmp_path, 2)
    state['status'] = 'complete'
    drive = Drive()
    drive.fail_copy = 2

    def checked_process(cmd, **kwargs):
        if 'copyto' in cmd:
            persisted = store.get(state['id'])['delivery']
            assert len(persisted['names']) == 2
            assert persisted['status'] != 'uploaded'
        return drive(cmd, **kwargs)

    first = upload_run(store, state, run=checked_process, which=lambda _: '/usr/bin/rclone')
    assert first['delivery']['status'] == 'failed'
    assert 'temporary Drive failure' in first['delivery']['error']
    assert first['status'] == 'complete'
    names = dict(first['delivery']['names'])
    state = store.get(state['id'])
    state['created'] = 99999999
    next(t for t in state['tasks'] if t['stage'] == 'write')['result']['scripts'][0]['title'] = 'Changed'
    second = deliver(store, state, drive)
    assert second['delivery']['status'] == 'uploaded'
    assert second['delivery']['names'] == names
    assert drive.calls[0] == drive.calls[2]
    assert drive.calls[1] == drive.calls[3]


@pytest.mark.parametrize(('destination', 'remote', 'flags'), [
    ('https://drive.google.com/drive/folders/folder123?usp=sharing', 'agent-exchange:',
     ['--drive-root-folder-id', 'folder123']),
    ('agent-exchange:deliverables/ad-studio/', 'agent-exchange:deliverables/ad-studio', []),
    ('drive:', 'drive:', []),
])
def test_destinations_use_configured_folder_without_run_subfolder(tmp_path, destination, remote, flags):
    store, state, folder = fixture(tmp_path)
    state['config']['delivery']['drive'] = destination
    drive = Drive()
    receipt = deliver(store, state, drive)['delivery']
    assert receipt['status'] == 'uploaded'
    assert receipt['remote'] == remote
    joiner = '' if remote.endswith(':') else '/'
    assert drive.calls == [
        ['rclone', *flags, 'copyto', str(folder / 'ad-01.mp4'), remote + joiner + receipt['files'][0]],
        ['rclone', *flags, 'lsf', remote, '--files-only'],
    ]


def test_unsafe_saved_name_never_invokes_rclone(tmp_path):
    store, state, _ = fixture(tmp_path)
    state['delivery'] = {'names': {'ad-01.mp4': '../someone-elses.mp4'}}
    drive = Drive()
    assert deliver(store, state, drive)['delivery']['status'] == 'failed'
    assert drive.calls == []


def test_no_succeeded_packages_never_uploads_stale_files(tmp_path):
    store, state, _ = fixture(tmp_path)
    next(t for t in state['tasks'] if t['stage'] == 'package')['status'] = 'failed'
    drive = Drive()
    assert deliver(store, state, drive)['delivery']['status'] == 'failed'
    assert drive.calls == []


def test_retry_preflight_failure_does_not_erase_previously_planned_names(tmp_path):
    store, state, _ = fixture(tmp_path)
    drive = Drive()
    drive.fail_copy = 1
    first = deliver(store, state, drive)
    names = dict(first['delivery']['names'])
    second = upload_run(store, store.get(state['id']), which=lambda _: None)
    assert second['delivery']['status'] == 'failed'
    state = store.get(state['id'])
    next(t for t in state['tasks'] if t['stage'] == 'write')['result']['scripts'][0]['title'] = 'Changed Title'
    assert deliver(store, state, drive)['delivery']['names'] == names


def test_old_uploaded_zip_receipt_does_not_reenable_zip_delivery(tmp_path):
    store, state, folder = fixture(tmp_path)
    state['delivery'] = {'status': 'uploaded', 'remote': 'agent-exchange:old-run',
                         'files': ['ad-01.mp4', 'ad-01.zip']}
    (folder / 'ad-01.zip').unlink()
    drive = Drive()
    result = deliver(store, state, drive)
    assert result['delivery']['status'] == 'uploaded'
    assert all(name.endswith('.mp4') for name in result['delivery']['files'])
    assert 'old-upload.zip' in drive.files
