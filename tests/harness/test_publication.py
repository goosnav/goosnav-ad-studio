from harness.config import load_config
from harness.store import Store
import hashlib
import json
from pathlib import Path
import subprocess

import pytest


def accepted_publication(tmp_path):
    from harness.contracts import digest, promote
    store = Store(tmp_path / 'state')
    state = store.create(load_config())
    work = tmp_path / 'work'; work.mkdir()
    (work / 'candidates.json').write_text('{}')
    (work / 'prop.bin').write_bytes(b'approved reusable asset')
    accepted = tmp_path / 'accepted'
    result = promote({'summary': 'Approved reusable assets', 'candidate_manifest': 'candidates.json',
                      'files': [{'path': 'candidates.json', 'kind': 'notes'},
                                {'path': 'prop.bin', 'kind': 'asset'}]}, work, accepted)
    state.update(status='complete', tasks=[
        {'id': 'ad-01-assets', 'ad': 0, 'stage': 'assets', 'status': 'succeeded', 'result': result,
         'accepted_manifest': str(accepted / 'accepted.json'),
         'accepted_manifest_sha256': digest(accepted / 'accepted.json')},
        {'id': 'ad-01-package', 'ad': 0, 'stage': 'package', 'status': 'succeeded'}])
    return store, state


def test_publication_failure_preserves_completed_video_and_retries(tmp_path, monkeypatch):
    from harness import publication
    store, s = accepted_publication(tmp_path)
    def unavailable(*args):
        raise OSError('network unavailable')
    monkeypatch.setattr(publication, 'publish_candidates', unavailable)
    result = publication.publish_run(store, s)
    assert result['status'] == 'complete'
    assert result['asset_publications']['ad-01-assets']['status'] == 'pending'
    assert 'network unavailable' in result['asset_publications']['ad-01-assets']['error']


@pytest.mark.parametrize('step', ['publish', 'push', 'adopt', 'pin'])
@pytest.mark.parametrize('changed', ['candidate', 'asset', 'accepted_manifest', 'missing'])
def test_publication_reverifies_accepted_bytes_before_every_retry(tmp_path, monkeypatch, step, changed):
    from harness import publication
    store, state = accepted_publication(tmp_path)
    task = state['tasks'][0]
    receipt = {} if step == 'publish' else {'commit': 'a' * 40}
    if step in ('adopt', 'pin'):
        receipt['pushed'] = True
    if step == 'pin':
        receipt['adopted'] = True
    state['asset_publications'] = {task['id']: dict(receipt)}
    if changed == 'accepted_manifest':
        path = Path(task['accepted_manifest'])
    elif changed == 'asset':
        path = Path(task['result']['files'][1]['path'])
    else:
        path = Path(task['result']['candidate_manifest'])
    if changed == 'missing':
        path.unlink()
    else:
        path.chmod(0o600)
        path.write_bytes(path.read_bytes() + b'\n')
    invoked = []
    def must_not_publish(*args):
        invoked.append(True)
        raise AssertionError('Unverified accepted bytes reached publication')
    for name in ('publish_candidates', 'push_publication', 'adopt_publication', 'pin_parent'):
        monkeypatch.setattr(publication, name, must_not_publish)
    result = publication.publish_run(store, state)
    assert not invoked
    assert result['status'] == 'complete'  # Delivery stays valid; publication is pending.
    pending = result['asset_publications'][task['id']]
    assert pending['status'] == 'pending' and 'changed' in pending['error'].lower()
    assert pending.get('commit') == receipt.get('commit')
    assert store.get(state['id'])['asset_publications'][task['id']] == pending


def test_incomplete_ad_never_publishes_assets(tmp_path):
    from harness.publication import publish_run
    store = Store(tmp_path); s = store.create(load_config())
    s['tasks'] = [{'id':'ad-01-assets','ad':0,'stage':'assets','status':'succeeded',
                  'result':{'candidate_manifest':'missing.json'}}]
    assert publish_run(store,s)['asset_publications'] == {}


def test_parent_pin_preserves_unrelated_dirty_work(tmp_path):
    import subprocess
    from harness.publication import pin_parent
    subprocess.run(['git','init','-q',str(tmp_path)], check=True)
    source = tmp_path/'artists-work.txt'; source.write_text('ongoing refactor')
    result = pin_parent({'pushed':True, 'commit':'f'*40}, tmp_path)
    assert result['parent_status'] == 'pending'
    assert 'local work' in result['parent_error']
    assert source.read_text() == 'ongoing refactor'
    assert subprocess.check_output(['git','-C',str(tmp_path),'diff','--cached','--name-only']) == b''


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.rstrip('\n')


@pytest.fixture
def published_submodule(tmp_path, request):
    """Actual publication into a parent submodule; every remote is disposable/local."""
    from harness import library
    asset_remote = tmp_path / 'asset-remote.git'
    parent_remote = tmp_path / 'parent-remote.git'
    for remote in (asset_remote, parent_remote):
        remote.mkdir()
        git(remote, 'init', '--bare', '--initial-branch=main')
    seed = tmp_path / 'seed'; seed.mkdir()
    parent = tmp_path / 'parent'; parent.mkdir()
    for root in (seed, parent):
        git(root, 'init', '--initial-branch=main')
        git(root, 'config', 'user.name', 'Publication Test')
        git(root, 'config', 'user.email', 'publication@example.invalid')
        git(root, 'config', 'commit.gpgsign', 'false')
    (seed / 'asset-catalog.json').write_text(json.dumps({'schema_version': 1, 'entries': []}))
    git(seed, 'add', 'asset-catalog.json'); git(seed, 'commit', '-m', 'initial catalog')
    git(seed, 'remote', 'add', 'origin', str(asset_remote)); git(seed, 'push', '-u', 'origin', 'main')
    (parent / 'app.txt').write_text('application')
    git(parent, 'add', 'app.txt'); git(parent, 'commit', '-m', 'application')
    path = 'assets/library with spaces'
    git(parent, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-b', 'main', str(asset_remote), path)
    git(parent, 'commit', '-m', 'asset submodule')
    git(parent, 'remote', 'add', 'origin', str(parent_remote)); git(parent, 'push', '-u', 'origin', 'main')
    module = parent / path
    git(module, 'config', 'user.name', 'Publication Test')
    git(module, 'config', 'user.email', 'publication@example.invalid')
    if getattr(request, 'param', None) == 'lagging':
        for i in range(6):
            (module / 'sets.txt').write_text(f'approved sets through {i}')
            git(module, 'add', 'sets.txt'); git(module, 'commit', '-m', f'approved set {i}')
        git(module, 'push', 'origin', 'main')
    config = {'sources': {'assets': [str(module)], 'characters': []},
              'library': {'root': str(module), 'catalog': 'asset-catalog.json', 'publish': True}}
    workspace = tmp_path / 'candidate'; workspace.mkdir()
    source = workspace / 'preset.json'; source.write_text('{"preset": "small room"}')
    candidate = workspace / 'candidates.json'
    candidate.write_text(json.dumps({'schema_version': 1, 'run_id': 'pin-run', 'candidates': [{
        'id': 'small-room', 'kind': 'source', 'path': 'preset.json',
        'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'destination': 'reusable/preset.json',
        'proxy': False, 'dependencies': [], 'capabilities': ['preset'],
        'provenance': {'run_id': 'pin-run', 'method': 'generated locally', 'sources': []},
        'reuse': {'description': 'Small room preset', 'license': 'original'}}]}))
    receipt = library.publish_candidates(config, candidate, 'pin-run')
    assert receipt['status'] == 'published', receipt
    receipt = library.push_publication(config, receipt)
    assert receipt['pushed'] is True, receipt
    return parent, module, path, parent_remote, config, receipt


def test_publish_adopt_then_pin_parent_accepts_only_receipted_gitlink(published_submodule):
    from harness import library, publication
    parent, module, path, remote, config, receipt = published_submodule
    original = git(parent, 'rev-parse', 'HEAD')
    receipt = library.adopt_publication(config, receipt)
    assert receipt['adopted'], receipt
    assert git(module, 'rev-parse', 'HEAD') == receipt['commit']
    assert git(parent, 'rev-parse', 'HEAD:' + path) == receipt['base_commit']
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pushed', result
    assert git(parent, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD') == path
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['commit']
    assert git(parent, 'status', '--porcelain') == ''
    assert git(parent, 'rev-parse', 'HEAD^') == original
    again = publication.pin_parent(result, parent)
    assert again['parent_status'] == 'pushed', again
    assert again['parent_commit'] == result['parent_commit']


@pytest.mark.parametrize('fail_at', ['lfs', 'add', 'commit', 'push'])
def test_parent_pin_resumes_exact_transition_after_failure(published_submodule, monkeypatch, fail_at):
    from harness import publication
    parent, module, path, remote, _, receipt = published_submodule
    actual_git = publication._git
    def fail_once(root, *args):
        if args[0] == fail_at:
            raise ValueError('injected failure at ' + fail_at)
        return actual_git(root, *args)
    monkeypatch.setattr(publication, '_git', fail_once)
    pending = publication.pin_parent(receipt, parent)
    assert pending['parent_status'] == 'pending' and 'injected failure' in pending['parent_error'], pending
    assert git(module, 'rev-parse', 'HEAD') == receipt['commit']
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['base_commit']
    monkeypatch.setattr(publication, '_git', actual_git)
    result = publication.pin_parent(pending, parent)
    assert result['parent_status'] == 'pushed', result
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['commit']
    assert git(parent, 'status', '--porcelain') == ''


@pytest.mark.parametrize('change', ['staged', 'unstaged', 'untracked', 'submodule'])
def test_adopted_pin_preserves_unrelated_parent_and_submodule_changes(published_submodule, change):
    from harness import library, publication
    parent, module, path, remote, config, receipt = published_submodule
    receipt = library.adopt_publication(config, receipt)
    assert receipt['adopted'], receipt
    if change == 'untracked':
        (parent / 'untracked.txt').write_text('artist work')
    elif change == 'submodule':
        (module / 'asset-catalog.json').write_text('artist work')
    else:
        (parent / 'app.txt').write_text('artist work')
        if change == 'staged':
            git(parent, 'add', 'app.txt')
    before = git(parent, 'status', '--porcelain', '--ignore-submodules=none')
    index = git(parent, 'ls-files', '--stage')
    head = git(parent, 'rev-parse', 'HEAD')
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(parent, 'status', '--porcelain', '--ignore-submodules=none') == before
    assert git(parent, 'ls-files', '--stage') == index
    assert git(parent, 'rev-parse', 'HEAD') == head
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['base_commit']


def test_parent_work_appearing_after_checkout_is_not_staged(published_submodule, monkeypatch):
    from harness import publication
    parent, module, _, _, _, receipt = published_submodule
    actual_git = publication._git
    def concurrent_edit(root, *args):
        value = actual_git(root, *args)
        if args[0] == 'lfs':
            (parent / 'app.txt').write_text('concurrent unstaged work')
        return value
    monkeypatch.setattr(publication, '_git', concurrent_edit)
    before = git(parent, 'ls-files', '--stage')
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(module, 'rev-parse', 'HEAD') == receipt['commit']
    assert git(parent, 'ls-files', '--stage') == before
    assert (parent / 'app.txt').read_text() == 'concurrent unstaged work'


@pytest.mark.parametrize('mismatch', ['receipt_base', 'checkout', 'index'])
def test_parent_pin_rejects_unreceipted_gitlink_states(published_submodule, mismatch):
    from harness import library, publication
    parent, module, path, remote, config, receipt = published_submodule
    receipt = library.adopt_publication(config, receipt)
    if mismatch == 'receipt_base':
        receipt['base_commit'] = 'f' * 40
    else:
        git(module, 'commit', '--allow-empty', '-m', 'unrelated local commit')
        unrelated = git(module, 'rev-parse', 'HEAD')
        if mismatch == 'index':
            git(parent, 'update-index', '--cacheinfo', f'160000,{unrelated},{path}')
            git(module, 'checkout', '--detach', receipt['commit'])
    before = git(parent, 'status', '--porcelain')
    index = git(parent, 'ls-files', '--stage')
    remote_head = git(remote, 'rev-parse', 'main')
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(parent, 'status', '--porcelain') == before
    assert git(parent, 'ls-files', '--stage') == index
    assert git(remote, 'rev-parse', 'main') == remote_head


def test_unrelated_commit_racing_parent_commit_is_never_pushed(published_submodule, monkeypatch):
    from harness import publication
    parent, _, _, remote, _, receipt = published_submodule
    remote_head = git(remote, 'rev-parse', 'main')
    actual_git = publication._git
    def another_commit(root, *args):
        value = actual_git(root, *args)
        if root == parent and args[0] == 'commit':
            (parent / 'app.txt').write_text('another agent committed work')
            git(parent, 'add', 'app.txt')
            git(parent, 'commit', '-m', 'unrelated concurrent commit')
        return value
    monkeypatch.setattr(publication, '_git', another_commit)
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(remote, 'rev-parse', 'main') == remote_head
    assert (parent / 'app.txt').read_text() == 'another agent committed work'


def test_parent_remote_rewind_racing_push_is_not_overwritten(published_submodule, monkeypatch):
    from harness import publication
    parent, _, _, remote, _, receipt = published_submodule
    previous = git(remote, 'rev-parse', 'main^')
    actual_git = publication._git
    def remote_rewind(root, *args):
        if root == parent and args[0] == 'push':
            git(remote, 'update-ref', 'refs/heads/main', previous)
        return actual_git(root, *args)
    monkeypatch.setattr(publication, '_git', remote_rewind)
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(remote, 'rev-parse', 'main') == previous


def test_parent_git_commands_ignore_ambient_index_redirection(published_submodule, monkeypatch, tmp_path):
    from harness import publication
    parent, _, _, _, _, receipt = published_submodule
    alien = tmp_path / 'foreign-index'
    alien.write_bytes(b'not this repository index')
    monkeypatch.setenv('GIT_INDEX_FILE', str(alien))
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pushed', result
    assert alien.read_bytes() == b'not this repository index'


@pytest.mark.parametrize('published_submodule', ['lagging'], indirect=True)
def test_lagging_parent_pin_uses_its_own_persisted_asset_base_after_adoption(published_submodule, monkeypatch):
    from harness import library, publication
    parent, module, path, remote, config, receipt = published_submodule
    recorded = git(parent, 'rev-parse', 'HEAD:' + path)
    assert recorded != receipt['base_commit']
    receipt = library.adopt_publication(config, receipt)
    assert receipt['adopted'], receipt
    actual_git = publication._git
    def fail_after_adoption(root, *args):
        if args[0] == 'lfs':
            raise ValueError('temporary hydration failure')
        return actual_git(root, *args)
    monkeypatch.setattr(publication, '_git', fail_after_adoption)
    pending = publication.pin_parent(receipt, parent)
    assert pending['parent_status'] == 'pending' and 'hydration failure' in pending['parent_error'], pending
    assert pending['parent_asset_base'] == recorded
    assert pending['base_commit'] == receipt['base_commit']
    assert git(module, 'rev-parse', 'HEAD') == receipt['commit']
    monkeypatch.setattr(publication, '_git', actual_git)
    result = publication.pin_parent(pending, parent)
    assert result['parent_status'] == 'pushed', result
    assert result['parent_asset_base'] == recorded
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['commit']
    assert git(parent, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD') == path


@pytest.mark.parametrize('published_submodule', ['lagging'], indirect=True)
def test_lagging_pin_from_recorded_checkout_retries_parent_push(published_submodule, monkeypatch):
    from harness import publication
    parent, module, path, remote, _, receipt = published_submodule
    recorded = git(parent, 'rev-parse', 'HEAD:' + path)
    git(module, 'checkout', '--detach', recorded)
    actual_git = publication._git
    def fail_push(root, *args):
        if args[0] == 'push':
            raise ValueError('temporary parent push failure')
        return actual_git(root, *args)
    monkeypatch.setattr(publication, '_git', fail_push)
    pending = publication.pin_parent(receipt, parent)
    assert pending['parent_asset_base'] == recorded
    assert pending['parent_status'] == 'pending' and pending.get('parent_commit'), pending
    monkeypatch.setattr(publication, '_git', actual_git)
    result = publication.pin_parent(pending, parent)
    assert result['parent_status'] == 'pushed', result
    assert git(remote, 'rev-parse', 'main:' + path) == receipt['commit']


@pytest.mark.parametrize('published_submodule', ['lagging'], indirect=True)
def test_lagging_pin_still_rejects_unrelated_intermediate_checkout(published_submodule):
    from harness import publication
    parent, module, path, remote, _, receipt = published_submodule
    # The live checkout is the publication base, neither recorded pin nor target.
    before = git(parent, 'status', '--porcelain')
    result = publication.pin_parent(receipt, parent)
    assert result['parent_status'] == 'pending', result
    assert git(module, 'rev-parse', 'HEAD') == receipt['base_commit']
    assert git(parent, 'status', '--porcelain') == before
    assert git(remote, 'rev-parse', 'main:' + path) != receipt['commit']
