"""Catalog identity and publication safety, using real disposable Git repositories."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import wave

import pytest


@pytest.fixture
def lib():
    assert importlib.util.find_spec('harness.library'), 'Asset library API is not implemented'
    return importlib.import_module('harness.library')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(root):
    return {'sources': {'assets': [str(root)], 'characters': []},
            'library': {'root': str(root), 'catalog': 'asset-catalog.json', 'publish': True}}


def entry(path, **extra):
    return dict(id='actor-one', kind='character', path=path.name, sha256=sha(path),
                status='active', capabilities=['talk'], preview=None, **extra)


def save_catalog(root, entries):
    (root / 'asset-catalog.json').write_text(json.dumps({'schema_version': 1, 'entries': entries}))


def git(root, *args, check=True):
    result = subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True)
    if check:
        assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    remote = tmp_path / 'remote.git'
    remote.mkdir()
    git(remote, 'init', '--bare')
    root = tmp_path / 'library'
    root.mkdir()
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'Library Test')
    git(root, 'config', 'user.email', 'library@example.invalid')
    (root / 'keep.txt').write_text('unrelated tracked content')
    save_catalog(root, [])
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'initial')
    git(root, 'remote', 'add', 'origin', str(remote))
    git(root, 'push', '-u', 'origin', 'main')
    return root, remote


@pytest.fixture
def candidate(tmp_path):
    work = tmp_path / 'run'
    work.mkdir()
    sound = work / 'tone.wav'
    with wave.open(str(sound), 'wb') as stream:
        stream.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\x01\x00' * 800)
    item = {'id': 'tone-one', 'kind': 'audio', 'path': 'tone.wav', 'sha256': sha(sound),
            'destination': 'reusable/sounds/tone.wav', 'proxy': False, 'dependencies': [],
            'provenance': {'run_id': 'run-one', 'method': 'synthesized locally', 'sources': []},
            'reuse': {'description': 'Short notification tone', 'license': 'original'},
            'capabilities': ['notification']}
    manifest = work / 'candidates.json'
    manifest.write_text(json.dumps({'schema_version': 1, 'run_id': 'run-one', 'candidates': [item]}))
    return manifest


def change_candidate(manifest, **changes):
    data = json.loads(manifest.read_text())
    data['candidates'][0].update(changes)
    manifest.write_text(json.dumps(data))


def test_catalog_relocates_by_hash_and_snapshots_survive_root_move(lib, tmp_path):
    root = tmp_path / 'old'; root.mkdir()
    actor = root / 'actor.blend'; actor.write_bytes(b'original')
    save_catalog(root, [entry(actor)])
    identities = lib.snapshot_identities(config(root))
    moved = root / 'new-layout' / 'renamed.blend'; moved.parent.mkdir(); actor.rename(moved)
    replacement = tmp_path / 'new'; root.rename(replacement)
    resolved = lib.resolve_snapshot(config(replacement), identities)
    assert resolved[0]['path'] == str(replacement / 'new-layout' / 'renamed.blend')
    assert resolved[0]['id'] == 'actor-one'
    assert resolved[0]['capabilities'] == ['talk']
    assert 'path' not in identities[0]
    assert json.loads((replacement / 'asset-catalog.json').read_text())['entries'][0]['path'] == 'actor.blend'


def test_retirement_invalidates_snapshot_and_prevents_rediscovery(lib, tmp_path):
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'original')
    record = entry(actor); save_catalog(tmp_path, [record])
    identity = lib.snapshot_identities(config(tmp_path))[0]
    record['status'] = 'retired'; save_catalog(tmp_path, [record])
    assert lib.catalog(config(tmp_path)) == []
    with pytest.raises(lib.LibraryError, match='retired|unavailable'):
        lib.resolve_identity(config(tmp_path), identity)


def test_changed_identity_and_missing_content_are_explicit_errors(lib, tmp_path):
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'original')
    record = entry(actor); save_catalog(tmp_path, [record])
    identity = lib.snapshot_identities(config(tmp_path))[0]
    actor.write_bytes(b'changed')
    with pytest.raises(lib.LibraryError, match='missing|Missing'):
        lib.catalog(config(tmp_path))
    record['sha256'] = sha(actor); save_catalog(tmp_path, [record])
    with pytest.raises(lib.LibraryError, match='changed|mismatch'):
        lib.resolve_identity(config(tmp_path), identity)


def test_relocation_rejects_ambiguity_and_ignores_archives(lib, tmp_path):
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'original')
    save_catalog(tmp_path, [entry(actor)]); actor.unlink()
    for folder in ['a', 'b', 'archive']:
        target = tmp_path / folder / 'copy.blend'; target.parent.mkdir(); target.write_bytes(b'original')
    with pytest.raises(lib.LibraryError, match='[Aa]mbiguous'):
        lib.catalog(config(tmp_path))
    (tmp_path / 'b' / 'copy.blend').unlink()
    assert lib.catalog(config(tmp_path))[0]['path'] == str(tmp_path / 'a' / 'copy.blend')
    (tmp_path / 'a' / 'copy.blend').unlink()
    with pytest.raises(lib.LibraryError, match='[Mm]issing'):
        lib.catalog(config(tmp_path))


@pytest.mark.parametrize('path', ['../outside.blend', '/tmp/outside.blend', '.git/config', 'archive/actor.blend'])
def test_catalog_rejects_unsafe_paths(lib, tmp_path, path):
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'original')
    record = entry(actor); record['path'] = path; save_catalog(tmp_path, [record])
    with pytest.raises(lib.LibraryError):
        lib.catalog(config(tmp_path))


def test_symlink_escape_cannot_satisfy_catalog_or_legacy_whitelist(lib, tmp_path):
    root = tmp_path / 'library'; root.mkdir()
    outside = tmp_path / 'outside.blend'; outside.write_bytes(b'outside')
    alias = root / 'actor.blend'; alias.symlink_to(outside)
    settings = config(root); settings['sources']['characters'] = [str(alias)]
    with pytest.raises(lib.LibraryError):
        lib.catalog(settings)
    save_catalog(root, [entry(alias)])
    with pytest.raises(lib.LibraryError):
        lib.catalog(settings)


def test_legacy_discovery_preserves_whitelist_and_skips_archived_characters(lib, tmp_path):
    active = tmp_path / 'actor.blend'; active.write_bytes(b'active')
    other = tmp_path / 'unapproved.blend'; other.write_bytes(b'unapproved')
    retired = tmp_path / 'archive' / 'old.blend'; retired.parent.mkdir(); retired.write_bytes(b'old')
    settings = config(tmp_path); settings['sources']['characters'] = [str(active), str(retired)]
    entries = lib.catalog(settings)
    assert [r['path'] for r in entries if r['kind'] == 'character'] == [str(active)]
    assert [r['path'] for r in entries if r['kind'] == 'scene'] == [str(other)]
    assert settings['sources']['characters'] == [str(active), str(retired)]
    assert str(retired) not in [r['path'] for r in entries]
    assert not (tmp_path / 'asset-catalog.json').exists()


def test_legacy_blend_discovery_is_layout_independent_and_does_not_hash_raw_media(lib, tmp_path, monkeypatch):
    scene = tmp_path / 'arbitrary-layout' / 'moon.blend'; scene.parent.mkdir(); scene.write_bytes(b'scene')
    movie = scene.with_suffix('.mp4'); movie.write_bytes(b'raw media')
    archived = tmp_path / 'ARCHIVED' / 'model.blend'; archived.parent.mkdir(); archived.write_bytes(b'retired')
    real_digest = lib.digest
    def checked_digest(path):
        assert Path(path).suffix.lower() == '.blend', 'Discovery hashed non-Blender media'
        assert 'ARCHIVED' not in Path(path).parts, 'Discovery read archived content'
        return real_digest(path)
    monkeypatch.setattr(lib, 'digest', checked_digest)
    first = lib.catalog(config(tmp_path))
    assert len(first) == 1 and first[0]['kind'] == 'scene'
    scene.rename(tmp_path / 'moved.blend')
    second = lib.catalog(config(tmp_path))
    assert second[0]['id'] == first[0]['id']
    assert second[0]['sha256'] == first[0]['sha256']
    assert second[0]['path'] == str(tmp_path / 'moved.blend')


def test_unhydrated_lfs_pointer_is_not_a_legacy_asset_identity(lib, tmp_path):
    actor = tmp_path / 'actor.blend'
    actor.write_text('version https://git-lfs.github.com/spec/v1\noid sha256:' + 'a' * 64 + '\nsize 123\n')
    settings = config(tmp_path); settings['sources']['characters'] = [str(actor)]
    with pytest.raises(lib.LibraryError, match='LFS|hydrate'):
        lib.catalog(settings)


def test_discovery_uses_nested_repository_top_not_containing_parent(lib, repo, tmp_path):
    root, _ = repo
    folder = root / 'totally-new-layout'; folder.mkdir()
    settings = config(folder); settings['library']['root'] = ''
    assert lib.library_root(settings) == root
    # An ordinary asset folder in the application repository must not select that repository.
    settings['sources']['assets'] = [str(Path(__file__).resolve().parents[2] / 'tests')]
    assert lib.library_root(settings) == Path(__file__).resolve().parents[2] / 'tests'


def test_discovery_coalesces_git_roots_and_ignores_extra_non_git_sources(lib, repo, tmp_path):
    root, _ = repo
    for name in ['models', 'exports']:
        (root / name).mkdir()
    extra = tmp_path / 'business-images'; extra.mkdir()
    settings = config(root); settings['library']['root'] = ''
    settings['sources']['assets'] = [str(root / 'models'), str(root / 'exports'), str(extra)]
    assert lib.library_root(settings) == root


def test_preview_relocates_with_its_hash(lib, tmp_path):
    asset = tmp_path / 'actor.blend'; asset.write_bytes(b'original')
    preview = tmp_path / 'preview.png'; preview.write_bytes(b'preview')
    record = entry(asset); record.update(preview='preview.png', preview_sha256=sha(preview))
    save_catalog(tmp_path, [record])
    preview.rename(tmp_path / 'moved.png')
    assert lib.catalog(config(tmp_path))[0]['preview'] == str(tmp_path / 'moved.png')


def test_publication_isolated_idempotent_and_remote_untouched(lib, repo, candidate):
    root, remote = repo; head = git(root, 'rev-parse', 'HEAD')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'published', result
    assert result['pushed'] is False
    assert git(root, 'rev-parse', 'HEAD') == head
    assert git(root, 'status', '--porcelain') == ''
    assert git(remote, 'rev-parse', 'refs/heads/main') == head
    changed = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', result['commit']).splitlines()
    assert sorted(changed) == ['asset-catalog.json', 'reusable/sounds/tone.wav']
    stored = json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))
    assert stored['entries'][0]['provenance']['run_id'] == 'run-one'
    retry = lib.publish_candidates(config(root), candidate, 'run-one')
    assert retry['status'] == 'published', retry
    assert retry['commit'] == result['commit']
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1


def test_publication_from_committed_tree_preserves_dirty_index_and_working_tree(lib, repo, candidate):
    root, _ = repo
    (root / 'keep.txt').write_text('staged refactor')
    git(root, 'add', 'keep.txt')
    (root / 'keep.txt').write_text('unstaged refactor')
    (root / 'untracked-environment.blend').write_bytes(b'in progress')
    save_catalog(root, [{'bad': 'uncommitted catalog must not be read'}])
    before = git(root, 'status', '--porcelain')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'published', result
    assert git(root, 'status', '--porcelain') == before
    assert git(root, 'show', ':keep.txt') == 'staged refactor'
    assert git(root, 'show', result['commit'] + ':keep.txt') == 'unrelated tracked content'
    assert len(json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))['entries']) == 1


def test_missing_configured_library_paths_recover_without_masking_other_missing_roots(lib, repo, tmp_path):
    from harness.sources import reconcile_sources
    root, _ = repo
    (root / 'asset-catalog.json').unlink()  # This exercises legacy basename recovery.
    actor = root / 'characters' / 'actor.blend'; actor.parent.mkdir(); actor.write_bytes(b'actor')
    settings = config(root); settings['library']['root'] = ''
    settings['sources'].update(assets=[str(root / 'old' / 'models'), str(root / 'old-exports')],
                               characters=[str(root / 'old' / 'actor.blend')], inspiration=[])
    assert lib.library_root(settings) == root
    warnings = reconcile_sources(settings)
    assert settings['sources']['assets'] == [str(root)]
    assert settings['sources']['characters'] == [str(actor)]
    assert any(w['group'] == 'assets' for w in warnings)
    settings['sources']['assets'].append(str(tmp_path / 'missing-required-images'))
    with pytest.raises(lib.ContractError, match='Missing asset'):
        reconcile_sources(settings)


def test_dirty_untracked_destination_is_never_overwritten_or_published(lib, repo, candidate):
    root, _ = repo
    destination = root / 'reusable/sounds/tone.wav'; destination.parent.mkdir(parents=True)
    destination.write_bytes(b'artist work')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'destination' in result['error'].lower()
    assert destination.read_bytes() == b'artist work'


def test_push_publication_retries_failed_remote_and_never_moves_shared_head(lib, repo, candidate):
    root, remote = repo; head = git(root, 'rev-parse', 'HEAD')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    git(root, 'remote', 'set-url', 'origin', str(remote.parent / 'missing.git'))
    pending = lib.push_publication(config(root), publication)
    assert pending['status'] == 'pending' and pending['commit'] == publication['commit']
    git(root, 'remote', 'set-url', 'origin', str(remote))
    pushed = lib.push_publication(config(root), pending)
    assert pushed['status'] == 'published' and pushed['pushed'] is True, pushed
    assert git(remote, 'rev-parse', 'refs/heads/main') == publication['commit']
    assert git(root, 'rev-parse', 'HEAD') == head
    assert lib.push_publication(config(root), pushed)['pushed'] is True


def test_push_publication_rejects_remote_divergence_without_force(lib, repo, candidate, tmp_path):
    root, remote = repo
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    (root / 'keep.txt').write_text('independent work')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'independent'); git(root, 'push')
    remote_head = git(remote, 'rev-parse', 'refs/heads/main')
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and result['pushed'] is False
    assert git(remote, 'rev-parse', 'refs/heads/main') == remote_head


def test_push_rejects_unrelated_unpushed_ancestry_even_when_source_is_clean(lib, repo, candidate):
    root, remote = repo
    remote_head = git(remote, 'rev-parse', 'refs/heads/main')
    (root / 'keep.txt').write_text('private unpushed refactor')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'unrelated local commit')
    assert git(root, 'status', '--porcelain') == ''
    source_head = git(root, 'rev-parse', 'HEAD')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    assert publication['status'] == 'published', publication
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and 'outgoing' in result['error'].lower(), result
    assert git(remote, 'rev-parse', 'refs/heads/main') == remote_head
    assert git(root, 'rev-parse', 'HEAD') == source_head


def test_push_uses_live_remote_tip_not_stale_tracking_ref(lib, repo, candidate):
    root, remote = repo
    initial = git(root, 'rev-parse', 'HEAD')
    (root / 'keep.txt').write_text('previously pushed refactor')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'refactor'); git(root, 'push')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    # Server-side rewind leaves origin/main locally pointing at the newer commit.
    git(remote, 'update-ref', 'refs/heads/main', initial)
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and 'outgoing' in result['error'].lower(), result
    assert git(remote, 'rev-parse', 'refs/heads/main') == initial


def test_push_rejects_remote_rewind_after_ancestry_validation(lib, repo, candidate, monkeypatch):
    root, remote = repo
    initial = git(root, 'rev-parse', 'HEAD')
    (root / 'keep.txt').write_text('already published refactor')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'refactor'); git(root, 'push')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    original_git = lib._git
    def rewind_before_push(directory, *args):
        if args[:2] == ('push', '--porcelain'):
            git(remote, 'update-ref', 'refs/heads/main', initial)
        return original_git(directory, *args)
    monkeypatch.setattr(lib, '_git', rewind_before_push)
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and not result['pushed'], result
    assert git(remote, 'rev-parse', 'refs/heads/main') == initial


@pytest.mark.parametrize('membership', ['retired', 'absent', 'scene'])
def test_catalog_excludes_unauthorized_configured_characters(lib, tmp_path, membership):
    from harness.sources import reconcile_sources
    allowed = tmp_path / 'allowed.blend'; allowed.write_bytes(b'allowed')
    other = tmp_path / 'other.blend'; other.write_bytes(b'other')
    records = [entry(allowed)]
    if membership != 'absent':
        record = entry(other); record['id'] = 'other'
        record['status' if membership == 'retired' else 'kind'] = membership
        records.append(record)
    save_catalog(tmp_path, records)
    settings = config(tmp_path)
    settings['sources'].update(characters=[str(allowed), str(other)], inspiration=[])
    warnings = reconcile_sources(settings)
    assert settings['sources']['characters'] == [str(allowed)]
    assert any(w['source'] == str(other) and w['kind'] == 'unavailable' for w in warnings)


def test_catalog_rejects_whitelist_with_no_active_authorized_character(lib, tmp_path):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'actor')
    record = entry(actor); record['status'] = 'retired'; save_catalog(tmp_path, [record])
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    for attempt in range(2):  # Failure must not erase the request and bypass validation on resume.
        with pytest.raises(lib.LibraryError, match='[Nn]o usable|retired|unavailable'):
            reconcile_sources(settings)


@pytest.mark.parametrize('impostor', [False, True])
def test_catalog_identity_relocates_before_basename_matching(lib, tmp_path, impostor):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'approved identity')
    save_catalog(tmp_path, [entry(actor)])
    moved = tmp_path / 'renamed-approved.blend'; actor.rename(moved)
    if impostor:
        actor.write_bytes(b'different character at the old path')
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    warnings = reconcile_sources(settings)
    assert settings['sources']['characters'] == [str(moved)]
    assert any(w.get('replacement') == str(moved) for w in warnings)


def test_catalog_character_missing_content_cannot_use_same_basename_substitute(lib, tmp_path):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'approved identity')
    save_catalog(tmp_path, [entry(actor)]); actor.unlink()
    substitute = tmp_path / 'other' / 'actor.blend'; substitute.parent.mkdir()
    substitute.write_bytes(b'unapproved substitute')
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    with pytest.raises(lib.LibraryError, match='[Mm]issing'):
        reconcile_sources(settings)


@pytest.mark.parametrize('with_catalog', [False, True])
def test_saved_character_identities_precede_basename_and_updated_catalog_paths(lib, tmp_path, with_catalog):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'approved saved identity')
    record = entry(actor)
    if with_catalog:
        save_catalog(tmp_path, [record])
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    identities = lib.snapshot_identities(settings)
    identity_paths = {identities[0]['id']: str(actor)}
    moved = tmp_path / 'renamed.blend'; actor.rename(moved)
    actor.write_bytes(b'wrong character reusing the old path')
    if with_catalog:
        record['path'] = moved.name; save_catalog(tmp_path, [record])
    warnings = reconcile_sources(settings, identities=identities, identity_paths=identity_paths)
    assert settings['sources']['characters'] == [str(moved)]
    assert any(w.get('asset_id') == identities[0]['id'] and w.get('replacement') == str(moved)
               for w in warnings)


def test_saved_identity_cannot_resurrect_retired_catalog_character(lib, tmp_path):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'approved saved identity')
    record = entry(actor); save_catalog(tmp_path, [record])
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    identities = lib.snapshot_identities(settings)
    record['status'] = 'retired'; save_catalog(tmp_path, [record])
    with pytest.raises(lib.LibraryError, match='retired|unavailable'):
        reconcile_sources(settings, identities=identities, identity_paths={record['id']: str(actor)})


def test_incomplete_saved_identity_paths_cannot_fall_back_to_a_changed_file(lib, tmp_path):
    from harness.sources import reconcile_sources
    actor = tmp_path / 'actor.blend'; actor.write_bytes(b'approved saved identity')
    settings = config(tmp_path); settings['sources'].update(characters=[str(actor)], inspiration=[])
    identities = lib.snapshot_identities(settings)
    actor.write_bytes(b'different character')
    with pytest.raises(lib.LibraryError, match='[Ss]aved.*path|[Mm]issing.*path'):
        reconcile_sources(settings, identities=identities, identity_paths={})


def test_push_stays_pending_when_committed_layout_check_fails(lib, repo, candidate):
    root, remote = repo
    (root / 'Makefile').write_text('check-layout:\n\t@echo "layout is invalid" >&2\n\t@exit 1\n')
    git(root, 'add', 'Makefile'); git(root, 'commit', '-m', 'layout check')
    git(root, 'push')
    remote_head = git(remote, 'rev-parse', 'refs/heads/main')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and 'layout is invalid' in result['error']
    assert git(remote, 'rev-parse', 'refs/heads/main') == remote_head
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1


@pytest.fixture
def nested_library(lib, repo, tmp_path, monkeypatch):
    """Two pinned submodule levels, backed by local disposable Git repositories."""
    root, remote = repo
    leaf = tmp_path / 'leaf'; leaf.mkdir()
    middle = tmp_path / 'middle'; middle.mkdir()
    for dependency in (leaf, middle):
        git(dependency, 'init', '-b', 'main')
        git(dependency, 'config', 'user.name', 'Library Test')
        git(dependency, 'config', 'user.email', 'library@example.invalid')
        (dependency / 'reference.txt').write_text('pinned original reference')
        git(dependency, 'add', '.'); git(dependency, 'commit', '-m', 'reference')
    git(middle, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(leaf), 'nested/leaf')
    git(middle, 'commit', '-am', 'pin nested reference')
    git(root, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(middle), 'references/brain')
    # The check requires the recursively pinned content, not either remote's newest commit.
    (root / 'Makefile').write_text(
        'check-layout:\n'
        '\t@test "$$(cat references/brain/reference.txt)" = "pinned original reference"\n'
        '\t@test "$$(cat references/brain/nested/leaf/reference.txt)" = "pinned original reference"\n')
    git(root, 'add', '.'); git(root, 'commit', '-m', 'layout with nested references'); git(root, 'push')
    for dependency in (leaf, middle):
        (dependency / 'reference.txt').write_text('newer remote reference must not be used')
        git(dependency, 'commit', '-am', 'newer reference')
    # Match production protocol defaults; permit file:// transport only for this local fixture.
    actual_git = lib._git
    def local_submodules(directory, *args):
        if args[:2] == ('submodule', 'update'):
            return actual_git(directory, '-c', 'protocol.file.allow=always', *args)
        return actual_git(directory, *args)
    monkeypatch.setattr(lib, '_git', local_submodules)
    return root, remote


@pytest.mark.parametrize('fail_remove', [False, True])
def test_push_initializes_pinned_nested_submodules_and_cleans_only_its_worktree(
        lib, nested_library, candidate, monkeypatch, fail_remove):
    root, remote = nested_library
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    assert publication['status'] == 'published', publication
    source_module = root / 'references/brain'
    (root / 'keep.txt').write_text('ongoing parent refactor')
    (source_module / 'reference.txt').write_text('ongoing submodule refactor')
    before_head = git(root, 'rev-parse', 'HEAD')
    before_index = git(root, 'ls-files', '--stage')
    before_status = git(root, 'status', '--porcelain')
    before_module_head = git(source_module, 'rev-parse', 'HEAD')
    common = Path(git(root, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    before_admin = set((common / 'worktrees').iterdir()) if (common / 'worktrees').exists() else set()
    owned = []
    actual_git = lib._git
    def track_owned_worktree(directory, *args):
        if args[:2] == ('worktree', 'add'):
            owned.append(Path(args[-2]))
        if fail_remove and args[:2] == ('worktree', 'remove'):
            raise lib.LibraryError('simulated Git refusal to remove nested submodules')
        return actual_git(directory, *args)
    monkeypatch.setattr(lib, '_git', track_owned_worktree)
    result = lib.push_publication(config(root), publication)
    assert result['pushed'] is True, result
    assert git(remote, 'rev-parse', 'refs/heads/main') == publication['commit']
    assert git(root, 'rev-parse', 'HEAD') == before_head
    assert git(root, 'ls-files', '--stage') == before_index
    assert git(root, 'status', '--porcelain') == before_status
    assert git(source_module, 'rev-parse', 'HEAD') == before_module_head
    assert (source_module / 'reference.txt').read_text() == 'ongoing submodule refactor'
    assert not (source_module / 'nested/leaf/reference.txt').exists()
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1
    assert owned and all(not path.exists() for path in owned)
    after_admin = set((common / 'worktrees').iterdir()) if (common / 'worktrees').exists() else set()
    assert after_admin == before_admin


@pytest.mark.parametrize('failure', ['layout', 'submodule'])
def test_nested_submodule_failure_leaves_no_worktree_or_remote_change(
        lib, nested_library, candidate, monkeypatch, failure):
    root, remote = nested_library
    with (root / 'Makefile').open('a') as handle:
        handle.write('\t@echo "deliberate layout failure" >&2; exit 1\n')
    git(root, 'commit', '-am', 'failing layout'); git(root, 'push')
    remote_head = git(remote, 'rev-parse', 'refs/heads/main')
    publication = lib.publish_candidates(config(root), candidate, 'run-one')
    actual_git = lib._git
    def fail_after_nested_checkout(directory, *args):
        if args[:2] == ('worktree', 'remove'):
            raise lib.LibraryError('simulated Git refusal to remove nested submodules')
        output = actual_git(directory, *args)
        if failure == 'submodule' and args[:2] == ('submodule', 'update'):
            raise lib.LibraryError('deliberate submodule failure after checkout')
        return output
    monkeypatch.setattr(lib, '_git', fail_after_nested_checkout)
    result = lib.push_publication(config(root), publication)
    assert result['status'] == 'pending' and f'deliberate {failure} failure' in result['error'], result
    assert git(remote, 'rev-parse', 'refs/heads/main') == remote_head
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1


def test_retired_content_cannot_be_reintroduced_with_a_new_id(lib, repo, candidate):
    root, _ = repo
    item = json.loads(candidate.read_text())['candidates'][0]
    record = {k: item[k] for k in ['kind', 'sha256']}
    record.update(id='retired-old-id', path='archive/old.wav', status='retired')
    save_catalog(root, [record]); git(root, 'add', '.'); git(root, 'commit', '-m', 'retire')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'retired' in result['error']


def test_explicit_subfolder_root_and_custom_catalog_path(lib, repo, candidate):
    root, _ = repo
    folder = root / 'collection'; folder.mkdir()
    settings = config(folder); settings['library']['catalog'] = 'metadata/library.json'
    result = lib.publish_candidates(settings, candidate, 'run-one')
    assert result['status'] == 'published', result
    files = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', result['commit']).splitlines()
    assert files == ['collection/metadata/library.json', 'collection/reusable/sounds/tone.wav']
    pushed = lib.push_publication(settings, result)
    assert pushed['pushed'] is True, pushed


def test_publication_remote_failure_retry_and_detached_safety(lib, repo, candidate):
    root, remote = repo
    git(root, 'remote', 'set-url', 'origin', str(remote.parent / 'missing.git'))
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and result['error']
    git(root, 'remote', 'set-url', 'origin', str(remote))
    git(root, 'checkout', '--detach')
    # A single tracked branch at exactly this commit is suitable for a detached submodule.
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'published', result
    git(root, 'config', '--unset', 'branch.main.remote')
    change_candidate(candidate, id='different-tone')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'branch' in result['error'].lower()


def test_publication_retry_does_not_ignore_a_changed_base(lib, repo, candidate):
    root, _ = repo
    first = lib.publish_candidates(config(root), candidate, 'run-one')
    assert first['status'] == 'published'
    (root / 'keep.txt').write_text('finished refactor')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'refactor')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'base changed' in result['error'].lower()


def test_candidate_symlink_escape_is_not_copied(lib, repo, candidate, tmp_path):
    root, _ = repo
    sound = candidate.parent / 'tone.wav'
    outside = tmp_path / 'outside.wav'; sound.rename(outside); sound.symlink_to(outside)
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'symlink' in result['error'].lower()


def test_retired_id_cannot_be_republished(lib, repo, candidate):
    root, _ = repo
    item = json.loads(candidate.read_text())['candidates'][0]
    record = {k: item[k] for k in ['id', 'kind', 'sha256']}
    record.update(path='archive/old.wav', status='retired')
    save_catalog(root, [record]); git(root, 'add', '.'); git(root, 'commit', '-m', 'retire')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'retired' in result['error']


@pytest.mark.parametrize('external_dependency', [False, True])
def test_blender_publication_loads_renders_and_rejects_external_dependencies(
        lib, repo, candidate, external_dependency):
    blender = shutil.which('blender')
    if not blender:
        pytest.skip('Blender is unavailable')
    root, _ = repo
    source = candidate.parent / 'prop.blend'
    expression = 'import bpy; bpy.ops.wm.read_factory_settings(use_empty=False); '
    if external_dependency:
        expression += "image = bpy.data.images.new('external', width=4, height=4); image.filepath = '//missing.png'; image.source = 'FILE'; image.use_fake_user = True; "
    expression += f'bpy.ops.wm.save_as_mainfile(filepath={str(source)!r})'
    subprocess.run([blender, '--background', '--factory-startup', '--threads', '2',
                    '--python-exit-code', '1', '--python-expr', expression],
                   check=True, capture_output=True, timeout=60)
    change_candidate(candidate, id='prop-one', kind='prop', path='prop.blend', sha256=sha(source),
                     destination='models/prop.blend', preview_destination='previews/prop.png')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    if external_dependency:
        assert result['status'] == 'pending' and 'External dependencies' in result['error'], result
    else:
        assert result['status'] == 'published', result
        record = json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))['entries'][0]
        assert record['preview'] == 'previews/prop.png'
        assert 'Cube' in record['validation']['objects']
        assert len(record['preview_sha256']) == 64


@pytest.mark.parametrize('changes', [
    {'path': '../outside.wav'}, {'destination': '../outside.wav'},
    {'destination': '.git/config'}, {'destination': '.gitattributes'},
    {'destination': 'archive/tone.wav'}, {'destination': 'keep.txt'},
    {'proxy': True}, {'sha256': '0' * 64}, {'dependencies': ['texture.png']},
    {'provenance': {'run_id': 'other', 'method': 'generated', 'sources': []}},
    {'reuse': {}},
])
def test_invalid_candidates_stay_pending_without_mutations(lib, repo, candidate, changes):
    root, _ = repo; before = git(root, 'rev-parse', 'HEAD')
    change_candidate(candidate, **changes)
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and result['error'], result
    assert git(root, 'rev-parse', 'HEAD') == before
    assert git(root, 'status', '--porcelain') == ''
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1


def test_publication_uses_existing_lfs_attributes(lib, repo, candidate):
    if not shutil.which('git-lfs'):
        pytest.skip('git-lfs is unavailable')
    root, _ = repo
    (root / '.gitattributes').write_text('*.wav filter=lfs diff=lfs merge=lfs -text\n')
    git(root, 'add', '.gitattributes'); git(root, 'commit', '-m', 'LFS policy')
    git(root, 'push')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'published', result
    pointer = git(root, 'show', result['commit'] + ':reusable/sounds/tone.wav')
    assert pointer.startswith('version https://git-lfs.github.com/spec/v1\n')
    assert 'oid sha256:' + json.loads(candidate.read_text())['candidates'][0]['sha256'] in pointer
    pushed = lib.push_publication(config(root), result)
    assert pushed['pushed'] is True, pushed
    _, remote = repo
    checksum = json.loads(candidate.read_text())['candidates'][0]['sha256']
    lfs_object = remote / 'lfs/objects' / checksum[:2] / checksum[2:4] / checksum
    assert lfs_object.read_bytes() == (candidate.parent / 'tone.wav').read_bytes()


def test_publication_hydrates_only_committed_legacy_lfs_assets(lib, repo, candidate):
    if not shutil.which('git-lfs'):
        pytest.skip('git-lfs is unavailable')
    root, _ = repo
    git(root, 'lfs', 'install', '--local')
    (root / '.gitattributes').write_text('*.blend filter=lfs diff=lfs merge=lfs -text\n')
    actor = root / 'actor.blend'; actor.write_bytes(b'committed opaque character fixture')
    product = root / 'product.blend'; product.write_bytes(b'committed product fixture')
    product_hash = sha(product)
    (root / 'asset-catalog.json').unlink()
    git(root, 'add', '.'); git(root, 'commit', '-m', 'legacy character')
    settings = config(root); settings['sources']['characters'] = [str(actor)]
    original_hash = sha(actor)
    actor.write_bytes(b'artist editing character')
    result = lib.publish_candidates(settings, candidate, 'run-one')
    assert result['status'] == 'published', result
    stored = json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))
    assert stored['entries'][0]['sha256'] == original_hash
    inherited = next(item for item in stored['entries'] if item['path'] == 'product.blend')
    assert inherited['sha256'] == product_hash and inherited['id'] == 'legacy-' + product_hash
    assert inherited['kind'] == 'scene'
    assert actor.read_bytes() == b'artist editing character'


@pytest.mark.parametrize('dirty_product', [False, True])
def test_first_catalog_preserves_committed_lfs_inventory_without_hydration(
        lib, repo, candidate, dirty_product):
    root, _ = repo
    (root / 'asset-catalog.json').unlink()
    actor = root / 'approved.blend'; actor.write_bytes(b'approved actor')
    content = b'original product geometry and artwork'
    checksum = hashlib.sha256(content).hexdigest()
    product = root / 'arbitrary-layout' / 'product.blend'; product.parent.mkdir()
    pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{checksum}\nsize {len(content)}\n'
    product.write_text(pointer)
    # Malformed cold-storage data must not even be parsed as inventory.
    archived = root / 'ARCHIVED' / 'old.blend'; archived.parent.mkdir()
    archived.write_text('version https://git-lfs.github.com/spec/v1\ninvalid\n')
    (root / 'alias.blend').symlink_to(product)
    (root / 'alias-directory').symlink_to(product.parent, target_is_directory=True)
    git(root, 'add', '.'); git(root, 'commit', '-m', 'uncataloged active inventory')
    settings = config(root); settings['sources']['characters'] = [str(actor)]
    # Ordinary uncataloged discovery still skips optional pointer payloads.
    assert [item['path'] for item in lib.catalog(settings)] == [str(actor)]
    if dirty_product:
        product.write_bytes(b'artist uncommitted product changes')
    (root / 'uncommitted.blend').write_bytes(b'untracked environment')
    before = git(root, 'status', '--porcelain')
    source_bytes = product.read_bytes()
    result = lib.publish_candidates(settings, candidate, 'run-one')
    assert result['status'] == 'published', result
    stored = json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))
    records = {item['path']: item for item in stored['entries']}
    assert set(records) == {'approved.blend', 'arbitrary-layout/product.blend', 'reusable/sounds/tone.wav'}
    record = records['arbitrary-layout/product.blend']
    assert record['id'] == 'legacy-' + checksum
    assert record['sha256'] == checksum and record['sha256'] != hashlib.sha256(pointer.encode()).hexdigest()
    assert record['kind'] == 'scene' and record['status'] == 'active'
    assert records['approved.blend']['kind'] == 'character'
    assert product.read_bytes() == source_bytes
    assert git(root, 'status', '--porcelain') == before
    assert not (root / 'asset-catalog.json').exists()
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1
    # Recording an inventory identity must NOT make a pointer consumable.
    product.write_text(pointer)
    save_catalog(root, [record])
    with pytest.raises(lib.LibraryError, match='Unhydrated Git LFS.*git lfs pull'):
        lib.catalog(settings)
    product.write_bytes(content)
    assert lib.catalog(settings)[0]['sha256'] == checksum


@pytest.mark.parametrize('pointer', [
    'version https://git-lfs.github.com/spec/v1\nsize 100\n',
    'version https://git-lfs.github.com/spec/v1\noid sha256:not-a-hash\nsize 100\n',
    'version https://git-lfs.github.com/spec/v1\noid sha256:' + 'a' * 64 + '\nsize -1\n',
])
def test_first_catalog_rejects_malformed_active_lfs_pointer(lib, repo, candidate, pointer):
    root, _ = repo
    (root / 'asset-catalog.json').unlink()
    (root / 'active.blend').write_text(pointer)
    git(root, 'add', '.'); git(root, 'commit', '-m', 'malformed active pointer')
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and 'LFS pointer' in result['error'], result
    assert git(root, 'worktree', 'list', '--porcelain').count('worktree ') == 1


def glb_bytes(external=False):
    document = {'asset': {'version': '2.0'}, 'scenes': [{'nodes': []}], 'scene': 0}
    if external:
        document['buffers'] = [{'uri': 'outside.bin', 'byteLength': 12}]
    encoded = json.dumps(document).encode()
    encoded += b' ' * (-len(encoded) % 4)
    return struct.pack('<4sIII4s', b'glTF', 2, 20 + len(encoded), len(encoded), b'JSON') + encoded


@pytest.mark.parametrize('extension,content', [
    ('py', b"raise RuntimeError('must never execute during validation')\n"),
    ('json', b'{"builder": "rebuild.py", "export": "scene.glb"}'),
    ('glb', glb_bytes()),
])
def test_publication_supports_rebuild_sources_manifests_and_portable_exports(lib, repo, candidate, extension, content):
    root, _ = repo
    source = candidate.parent / ('artifact.' + extension); source.write_bytes(content)
    change_candidate(candidate, id='bundle-' + extension, kind='source', path=source.name,
                     sha256=sha(source), destination='new-bundle/' + source.name)
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'published', result
    stored = json.loads(git(root, 'show', result['commit'] + ':asset-catalog.json'))
    assert stored['entries'][0]['validation']['format'] == extension


@pytest.mark.parametrize('extension,content', [
    ('py', b'def broken(: pass'), ('json', b'{malformed}'),
    ('glb', b'glTF\x02\x00\x00\x00\x10\x00\x00\x00'),
    ('glb', glb_bytes(external=True)), ('glb', glb_bytes() + b'trailing garbage'),
])
def test_malformed_or_external_bundle_artifacts_stay_pending(lib, repo, candidate, extension, content):
    root, _ = repo
    source = candidate.parent / ('artifact.' + extension); source.write_bytes(content)
    change_candidate(candidate, path=source.name, sha256=sha(source), destination='bundle/' + source.name)
    result = lib.publish_candidates(config(root), candidate, 'run-one')
    assert result['status'] == 'pending' and result['error'], result
    assert git(root, 'status', '--porcelain') == ''


def test_adoption_fast_forwards_clean_checkout_and_exposes_published_catalog(lib, repo, candidate):
    root, _ = repo
    result = lib.push_publication(config(root), lib.publish_candidates(config(root), candidate, 'run-one'))
    adopted = lib.adopt_publication(config(root), result)
    assert adopted['adopted'] is True and adopted['adoption_status'] == 'adopted', adopted
    assert git(root, 'rev-parse', 'HEAD') == result['commit']
    assert lib.catalog(config(root))[0]['id'] == 'tone-one'
    assert lib.adopt_publication(config(root), adopted)['adopted'] is True


def test_adoption_keeps_dirty_checkout_unchanged_and_preserves_pushed_result(lib, repo, candidate):
    root, _ = repo
    result = lib.push_publication(config(root), lib.publish_candidates(config(root), candidate, 'run-one'))
    head = git(root, 'rev-parse', 'HEAD')
    (root / 'keep.txt').write_text('refactor')
    before = git(root, 'status', '--porcelain')
    adopted = lib.adopt_publication(config(root), result)
    assert adopted['pushed'] is True and adopted['adopted'] is False
    assert adopted['adoption_status'] == 'pending' and 'dirty' in adopted['adoption_error'].lower()
    assert git(root, 'rev-parse', 'HEAD') == head
    assert git(root, 'status', '--porcelain') == before


def test_adoption_rejects_diverged_checkout(lib, repo, candidate):
    root, _ = repo
    result = lib.push_publication(config(root), lib.publish_candidates(config(root), candidate, 'run-one'))
    (root / 'keep.txt').write_text('new commit')
    git(root, 'add', 'keep.txt'); git(root, 'commit', '-m', 'refactor')
    head = git(root, 'rev-parse', 'HEAD')
    adopted = lib.adopt_publication(config(root), result)
    assert adopted['adoption_status'] == 'pending' and not adopted['adopted']
    assert git(root, 'rev-parse', 'HEAD') == head


def test_adoption_hydrates_new_lfs_assets(lib, repo, candidate):
    if not shutil.which('git-lfs'):
        pytest.skip('git-lfs is unavailable')
    root, _ = repo
    (root / '.gitattributes').write_text('*.wav filter=lfs diff=lfs merge=lfs -text\n')
    git(root, 'add', '.gitattributes'); git(root, 'commit', '-m', 'LFS')
    git(root, 'push')
    result = lib.push_publication(config(root), lib.publish_candidates(config(root), candidate, 'run-one'))
    adopted = lib.adopt_publication(config(root), result)
    assert adopted['adopted'] is True, adopted
    assert (root / 'reusable/sounds/tone.wav').read_bytes() == (candidate.parent / 'tone.wav').read_bytes()
