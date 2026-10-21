"""Post-production asset publication: failures are durable and independent of delivery."""
from pathlib import Path
import os
import re
import subprocess

from .library import publish_candidates, push_publication, adopt_publication
from .contracts import ContractError, digest, verify_accepted


def _git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1')
    result = subprocess.run(['git', '--literal-pathspecs', '-c', 'core.hooksPath=' + os.devnull,
                             '-c', 'commit.gpgsign=false', '-C', str(root), *args],
                            capture_output=True, text=True, timeout=120, env=env)
    if result.returncode:
        raise ValueError(result.stderr[-1000:])
    return result.stdout.rstrip('\n')  # Preserve porcelain status columns and NUL-delimited paths.


def _remote_id(url):
    from urllib.parse import urlparse
    if '://' in url:
        parsed = urlparse(url)
        return (parsed.hostname or '') + parsed.path.removesuffix('.git').rstrip('/')
    if '@' in url and ':' in url:
        return url.split('@',1)[1].replace(':','/',1).removesuffix('.git').rstrip('/')
    return str(Path(url).resolve())


def _pin_state(parent, path, base, commit, expected_head):
    """Allow only the receipt's gitlink transition, including interrupted staging."""
    if _git(parent, 'rev-parse', 'HEAD') != expected_head:
        raise ValueError('Parent HEAD changed during pin publication')
    status = _git(parent, 'status', '--porcelain=v1', '-z', '--untracked-files=all',
                  '--ignore-submodules=none')
    allowed = {' M ' + path, 'M  ' + path}
    if any(entry not in allowed for entry in status.split('\0') if entry):
        raise ValueError('Parent checkout has unrelated local work; pin update is pending')
    tree = _git(parent, 'ls-tree', '-z', 'HEAD', '--', path).split('\0')
    index = _git(parent, 'ls-files', '--stage', '-z', '--', path).split('\0')
    if len(tree) != 2 or len(index) != 2:
        raise ValueError('Expected one unconflicted gitlink in parent HEAD and index')
    recorded, indexed = tree[0].split('\t', 1)[0].split(), index[0].split('\t', 1)[0].split()
    if recorded[:2] != ['160000', 'commit'] or indexed[0] != '160000' or indexed[2] != '0':
        raise ValueError('Parent path must remain an unconflicted gitlink')
    recorded, indexed = recorded[2], indexed[1]
    submodule = (parent / path).resolve()
    checkout = _git(submodule, 'rev-parse', 'HEAD')
    if _git(submodule, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'):
        raise ValueError('Submodule has local work; pin update is pending')
    allowed_states = {(base, base, base), (base, base, commit), (base, commit, commit),
                      (commit, commit, commit)}
    if (recorded, indexed, checkout) not in allowed_states:
        raise ValueError('Gitlink/index/checkout do not match the publication receipt transition')
    return recorded, checkout


def _verify_parent_commit(parent, head, parent_base, path, base, commit):
    if (_git(parent, 'rev-list', '--parents', '-n', '1', head).split() != [head, parent_base]
            or _git(parent, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z', head) != path + '\0'
            or _git(parent, 'rev-parse', parent_base + ':' + path) != base
            or _git(parent, 'rev-parse', head + ':' + path) != commit):
        raise ValueError('Parent commit contains work outside the exact receipt gitlink transition')


def pin_parent(publication, parent=None):
    """Advance a matching gitlink through its independently receipted base -> commit.

    Adoption and failed checkout/add/commit/push steps may leave this exact change
    pending. All other parent/submodule work remains untouched and blocks staging.
    """
    result = dict(publication, parent_status='pending', parent_error='')
    parent = Path(parent or Path(__file__).resolve().parents[1]).resolve()
    try:
        if publication.get('pushed') is not True:
            raise ValueError('Asset commit must be pushed before updating its parent pin')
        if _git(parent, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=all'):
            raise ValueError('Parent checkout has local work; submodule pin update is pending')
        base, commit = publication.get('base_commit'), publication.get('commit')
        if not all(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{40,64}', sha) for sha in (base, commit)):
            raise ValueError('Publication requires exact base_commit and commit receipts')
        branch = _git(parent, 'symbolic-ref', '--short', 'HEAD')
        remote = _git(parent, 'config', '--get', f'branch.{branch}.remote')
        target = _git(parent, 'config', '--get', f'branch.{branch}.merge')
        if remote == '.' or not target.startswith('refs/heads/'):
            raise ValueError('Parent branch needs a remote upstream')
        head = _git(parent, 'rev-parse', 'HEAD')
        source_url = _git(publication['repository'], 'remote', 'get-url', publication['remote'])
        if _git(publication['repository'], 'ls-remote', '--exit-code', publication['remote'],
                publication['target_ref']).split()[0] != commit:
            raise ValueError('Asset remote no longer matches the pushed publication receipt')
        if _git(publication['repository'], 'rev-list', '--parents', '-n', '1', commit).split() != [commit, base]:
            raise ValueError('Asset commit ancestry differs from the receipt base_commit')
        submodules = _git(parent, 'config', '-z', '--file', '.gitmodules', '--get-regexp', r'^submodule\..*\.path$')
        matches = []
        for line in filter(None, submodules.split('\0')):
            key, path = line.split('\n', 1)
            url = _git(parent, 'config', '--file', '.gitmodules', '--get', key[:-4] + 'url')
            if _remote_id(url) == _remote_id(source_url):
                matches.append(path)
        if len(matches) != 1:
            raise ValueError('Expected one matching asset submodule; parent pin remains pending')
        path = matches[0]
        submodule = (parent / path).resolve()
        if not submodule.is_relative_to(parent.resolve()):
            raise ValueError('Submodule escapes parent checkout')
        parent_asset_base = publication.get('parent_asset_base')
        if parent_asset_base is None:
            recorded = _git(parent, 'rev-parse', 'HEAD:' + path)
            # A clean parent may legitimately lag several already-pushed asset
            # commits. Capture its own old pin once; do not substitute the asset
            # publication's immediate parent as the starting gitlink.
            parent_asset_base = recorded if recorded != commit else base
        if (not isinstance(parent_asset_base, str)
                or not re.fullmatch(r'[0-9a-f]{40,64}', parent_asset_base)):
            raise ValueError('Invalid parent_asset_base receipt')
        _git(publication['repository'], 'merge-base', '--is-ancestor', parent_asset_base, base)
        recorded, checkout = _pin_state(parent, path, parent_asset_base, commit, head)
        result['parent_asset_base'] = parent_asset_base
        remote_head = _git(parent, 'ls-remote', '--exit-code', remote, target).split()[0]
        if remote_head != head:
            parent_base = publication.get('parent_base_commit')
            if head != publication.get('parent_commit') or remote_head != parent_base or recorded != commit:
                raise ValueError('Parent has other unpushed commits; automatic pin publication is pending')
            _verify_parent_commit(parent, head, parent_base, path, parent_asset_base, commit)
        if _remote_id(_git(submodule, 'remote', 'get-url', 'origin')) != _remote_id(source_url):
            raise ValueError('Submodule origin differs from the publication remote')
        if recorded != commit:
            result.update(parent_base_commit=head, parent_path=path)
            if checkout != commit:
                _git(submodule, 'fetch', 'origin', commit)
                _git(submodule, 'merge-base', '--is-ancestor', parent_asset_base, commit)
                _pin_state(parent, path, parent_asset_base, commit, head)
                _git(submodule, 'checkout', '--detach', commit)
            _git(submodule, 'lfs', 'pull', '--include', '*', '--exclude', 'archive/**,**/archive/**,**/archived/**')
            _pin_state(parent, path, parent_asset_base, commit, head)
            _git(parent, 'add', '--', path)
            _pin_state(parent, path, parent_asset_base, commit, head)
            _git(parent, 'commit', '--only', '-m', 'Update validated reusable ad assets', '--', path)
            pinned = _git(parent, 'rev-parse', 'HEAD')
            _verify_parent_commit(parent, pinned, head, path, parent_asset_base, commit)
            result['parent_commit'] = pinned
        else:
            result['parent_commit'] = head
        _pin_state(parent, path, parent_asset_base, commit, result['parent_commit'])
        # We have proved this is the same remote tip or its one-commit pin child.
        # The explicit lease only guards races (including rewind); it never admits
        # a rewrite or an extra unreviewed ancestor.
        _git(parent, 'push', f'--force-with-lease={target}:{remote_head}', remote,
             f"{result['parent_commit']}:{target}")
        if _git(parent, 'ls-remote', '--exit-code', remote, target).split()[0] != result['parent_commit']:
            raise ValueError('Parent push could not be verified')
        result.update(parent_status='pushed', parent_path=path)
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as exc:
        result['parent_error'] = str(exc)
    return result


def publish_run(store, state):
    if not state['config'].get('library', {}).get('publish', True):
        return state
    publications = state.setdefault('asset_publications', {})
    for task in state['tasks']:
        if task['stage'] not in ('assets', 'animate') or task['status'] != 'succeeded':
            continue
        # Never promote assets from an ad whose creative/media checks did not finish.
        delivered = any(t['ad'] == task['ad'] and t['stage'] == 'package' and t['status'] == 'succeeded'
                        for t in state['tasks'])
        manifest = (task.get('result') or {}).get('candidate_manifest')
        if not delivered or not manifest:
            continue
        declared = {f['path'] for f in task['result'].get('files', [])}
        if manifest not in declared:
            publications[task['id']] = {'status': 'pending', 'error': 'Candidate manifest was not a declared accepted artifact'}
            continue
        result = publications.get(task['id'], {})
        try:
            verify_accepted(task['result'])
            if (task.get('accepted_manifest_sha256')
                    and digest(task['accepted_manifest']) != task['accepted_manifest_sha256']):
                raise ContractError('Accepted manifest changed: ' + task['accepted_manifest'])
            if not result.get('commit'):
                result = publish_candidates(state['config'], Path(manifest), state['id'] + ':' + task['id'])
            if result.get('commit') and not result.get('pushed'):
                result = push_publication(state['config'], result)
            if result.get('pushed') and not result.get('adopted'):
                result = adopt_publication(state['config'], result)
            if result.get('pushed') and result.get('parent_status') != 'pushed':
                result = pin_parent(result)
        except Exception as exc:
            result = {**result, 'status': 'pending', 'error': f'{type(exc).__name__}: {exc}'}
        publications[task['id']] = result
        store.save(state, 'asset_publication', {'task': task['id'], **result})
    return state
