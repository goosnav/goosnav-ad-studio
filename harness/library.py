"""Relocatable asset identities and isolated, retryable local publication.

See docs/library.md for schemas and the controller's push/pin responsibilities.
Only push_publication pushes. Only adopt_publication changes a clean shared checkout.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tempfile
import wave

from .contracts import ContractError, digest
from .blender_dependencies import EXTERNAL_PATH_SCAN


class LibraryError(ContractError):
    """A catalog identity or publication precondition cannot be satisfied safely."""


_ARCHIVES = {'archive', 'archives', 'archived'}
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')


def _run(args, *, cwd=None, timeout=60, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True,
                            errors='replace', timeout=timeout)
    if result.returncode:
        raise LibraryError(f'{Path(args[0]).name} failed: {(result.stderr or result.stdout)[-2000:]}')
    return result.stdout.strip()


def _git(root, *args):
    # Ambient Git routing must not redirect an isolated worktree's index or repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_LFS_SKIP_SMUDGE='1')
    return _run(['git', '--literal-pathspecs', '-c', 'core.hooksPath=/dev/null',
                 '-C', str(root), *args], env=env)


def _git_optional(root, *args):
    try:
        return _git(root, *args)
    except LibraryError:
        return ''


def _archived(path):
    return any(part.lower() in _ARCHIVES for part in Path(path).parts)


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or ':' in value or value.startswith('/') or any(
                part in ('', '.', '..') or part.startswith('.') or part.lower() in _ARCHIVES
                for part in value.split('/'))):
        raise LibraryError(f'Unsafe relative path: {value!r}')
    return PurePosixPath(value)


def _inside(root, value):
    path = root.joinpath(*_relative(value).parts)
    if not path.resolve().is_relative_to(root):
        raise LibraryError(f'Symlink escapes library/workspace: {value}')
    # Reject internal aliases too: Git and filesystem paths must have one meaning.
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink():
            raise LibraryError(f'Symlink asset path: {value}')
    return path


def library_root(config):
    """Explicit folder, or the configured roots' own Git top-level (never this app's)."""
    explicit = config.get('library', {}).get('root', '')
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        app = _git_optional(Path(__file__).parent, 'rev-parse', '--show-toplevel')
        roots, repositories = set(), set()
        for value in config.get('sources', {}).get('assets', []):
            path = resolve_asset_root(value)
            top = _git_optional(path, 'rev-parse', '--show-toplevel')
            roots.add(path)
            if top and top != app:
                repositories.add(Path(top).resolve())
        choices = repositories or roots
        if len(choices) != 1:
            raise LibraryError('Configure library.root: expected one unambiguous asset root')
        root = choices.pop()
    if not root.is_dir():
        raise LibraryError(f'Missing asset root: {root}')
    return root


def resolve_asset_root(value):
    """Recover a moved configured folder only through its surviving independent Git repo."""
    path = Path(value).expanduser().resolve()
    if path.is_dir():
        return path
    ancestor = next((p for p in path.parents if p.is_dir()), None)
    top = _git_optional(ancestor, 'rev-parse', '--show-toplevel') if ancestor else ''
    app = _git_optional(Path(__file__).parent, 'rev-parse', '--show-toplevel')
    if top and top != app and path.is_relative_to(Path(top).resolve()):
        return Path(top).resolve()
    raise LibraryError(f'Missing asset library: {path}')


def _catalog_path(config, root):
    return _inside(root, config.get('library', {}).get('catalog', 'asset-catalog.json'))


def _json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise LibraryError(f'Cannot read JSON {path}: {exc}') from exc


def _document(path):
    data = _json(path)
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('entries'), list):
        raise LibraryError('Catalog requires schema_version: 1 and entries: []')
    seen = set()
    for record in data['entries']:
        if not isinstance(record, dict):
            raise LibraryError('Catalog entries must be objects')
        _identity_fields(record)
        if record['id'] in seen:
            raise LibraryError(f'Duplicate catalog ID: {record["id"]}')
        seen.add(record['id'])
        if record.get('status') not in ('active', 'retired'):
            raise LibraryError('Catalog status must be active or retired')
        # Tombstones may record old archive locations; they are never resolved.
        if record['status'] == 'active':
            _relative(record.get('path'))
    return data


def _identity_fields(record):
    if not isinstance(record, dict):
        raise LibraryError('Asset identity must be an object')
    if not isinstance(record.get('id'), str) or not _ID.fullmatch(record['id']):
        raise LibraryError('Asset id must be a stable, nonempty identifier')
    if not isinstance(record.get('sha256'), str) or not _SHA.fullmatch(record['sha256']):
        raise LibraryError('Asset sha256 must be 64 lowercase hexadecimal characters')
    if not isinstance(record.get('kind'), str) or not record['kind'].strip():
        raise LibraryError('Asset kind is required')


def _files(root):
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = sorted(f for f in folders if not f.startswith('.') and f.lower() not in _ARCHIVES
                            and not (Path(directory) / f).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if not name.startswith('.') and not path.is_symlink() and path.is_file():
                yield path


def _lfs_pointer(path):
    with path.open('rb') as handle:
        return handle.read(43).startswith(b'version https://git-lfs.github.com/spec/v1\n')


def _asset_digest(path):
    if _lfs_pointer(path):
        raise LibraryError(f'Unhydrated Git LFS asset: {path}; run git lfs pull with --include '
                           'restricted to the required active paths in its configured asset repository, '
                           'then retry (pointer text is not asset content)')
    return digest(path)


def _inventory_digest(path):
    """Record committed content identity without treating an LFS pointer as usable."""
    if not _lfs_pointer(path):
        return digest(path)
    with path.open('rb') as handle:
        pointer = handle.read(1025)
    match = re.fullmatch(
        rb'version https://git-lfs\.github\.com/spec/v1\n'
        rb'oid sha256:([0-9a-f]{64})\nsize (?:0|[1-9][0-9]*)\n', pointer)
    if len(pointer) > 1024 or not match:
        raise LibraryError(f'Invalid or unsupported Git LFS pointer: {path}; '
                           'hydrate/repair the committed asset before catalog bootstrap')
    return match[1].decode('ascii')


def _resolve(root, record, hashes):
    direct = _inside(root, record['path'])
    if direct.is_file() and _asset_digest(direct) == record['sha256']:
        return direct
    if not hashes:
        hashes.update({'indexed': True, 'paths': {}})
        for path in _files(root):
            if not _lfs_pointer(path):
                hashes['paths'].setdefault(digest(path), []).append(path)
    matches = hashes['paths'].get(record['sha256'], [])
    if len(matches) != 1:
        reason = 'Ambiguous' if matches else 'Missing'
        raise LibraryError(f'{reason} content for asset {record["id"]}: {record["path"]}')
    return matches[0]


def _legacy(config, root, *, committed_inventory=False):
    # Only isolated first-catalog publication may inventory pointer OIDs. Runtime
    # discovery still requires hydrated content and never returns a pointer asset.
    checksum_for = _inventory_digest if committed_inventory else _asset_digest
    entries = []
    seen = set()
    for value in config.get('sources', {}).get('characters', []):
        original = Path(value).expanduser().absolute()
        if _archived(original) or _archived(original.resolve()):
            continue
        try:
            relative = original.relative_to(root).as_posix()
        except ValueError as exc:
            raise LibraryError(f'Whitelisted character escapes library: {value}') from exc
        path = _inside(root, relative)
        if not path.is_file():
            raise LibraryError(f'Missing whitelisted character: {value}; reconcile sources first')
        checksum = checksum_for(path)
        identifier = 'legacy-' + checksum
        if identifier not in seen:
            entries.append({'id': identifier, 'kind': 'character', 'path': relative,
                            'sha256': checksum, 'status': 'active', 'capabilities': [], 'preview': None})
            seen.add(identifier)
    # A .blend is a reusable scene; only the explicit whitelist authorizes a cast
    # character. No filename or directory layout is used to infer that permission.
    for path in _files(root):
        if path.suffix.lower() != '.blend' or (not committed_inventory and _lfs_pointer(path)):
            continue
        relative = path.relative_to(root).as_posix()
        _inside(root, relative)
        checksum = checksum_for(path)
        identifier = 'legacy-' + checksum
        if identifier not in seen:
            entries.append({'id': identifier, 'kind': 'scene', 'path': relative,
                            'sha256': checksum, 'status': 'active', 'capabilities': [], 'preview': None})
            seen.add(identifier)
    return entries


def catalog_file(config, identifier, *, kind=None):
    """Resolve one active primary file without hydrating unrelated catalog assets.

    Metadata is validated normally. Only the requested file's content is verified;
    previews are not resolved. Relocation and archive rules match catalog().
    """
    root = library_root(config)
    record = next((e for e in _document(_catalog_path(config, root))['entries']
                   if e['id'] == identifier and e['status'] == 'active'), None)
    if record is None or (kind is not None and record['kind'] != kind):
        raise LibraryError(f'Asset unavailable, retired or wrong kind: {identifier}')
    return {**record, 'path': str(_resolve(root, record, {}))}


def catalog(config):
    """Return active entries with absolute verified paths; never write discovery results.

    First-catalog publication preserves committed LFS content OIDs even when files
    are unhydrated. Such records remain inventory, not usable assets: reads raise
    an actionable LFS error until their payloads are hydrated. Legacy optional
    discovery without a catalog still skips pointers; it does not authorize them.
    """
    if not config.get('library', {}).get('root') and not config.get('sources', {}).get('assets'):
        return []
    root = library_root(config)
    path = _catalog_path(config, root)
    legacy = not path.exists()
    records = _legacy(config, root) if legacy else _document(path)['entries']
    result, hashes = [], {}
    for record in records:
        if record['status'] != 'active':
            continue
        resolved = dict(record, path=str(root / record['path'] if legacy else _resolve(root, record, hashes)))
        resolved.setdefault('capabilities', [])
        resolved.setdefault('preview', None)
        if resolved['preview'] is not None:
            if record.get('preview_sha256'):
                preview = _resolve(root, dict(record, path=record['preview'], sha256=record['preview_sha256']), hashes)
            else:
                preview = _inside(root, resolved['preview'])
            if not preview.is_file():
                raise LibraryError(f'Missing preview for {record["id"]}')
            resolved['preview'] = str(preview)
        result.append(resolved)
    return result


def snapshot_identities(config):
    """JSON-ready, root-independent identities suitable for persisting in a run."""
    return [{key: entry[key] for key in ('id', 'kind', 'sha256')} for entry in catalog(config)]


def resolve_snapshot(config, identities):
    """Resolve frozen identities against today's active catalog, failing on any change."""
    active = {entry['id']: entry for entry in catalog(config)}
    result = []
    for identity in identities:
        _identity_fields(identity)
        entry = active.get(identity['id'])
        if entry is None:
            raise LibraryError(f'Asset retired or unavailable: {identity["id"]}')
        if any(entry[key] != identity[key] for key in ('kind', 'sha256')):
            raise LibraryError(f'Asset identity changed: {identity["id"]}')
        result.append(entry)
    return result


def resolve_identity(config, identity):
    return resolve_snapshot(config, [identity])[0]


def reconcile_saved_characters(config, identities, identity_paths):
    """Resolve only previously authorized configured characters, before path guesses.

    identity_paths is the run's persisted {asset_id: previous_absolute_path} map.
    Catalog identities remain authoritative. Legacy identities are recoverable
    by their saved content hash, without inventing authorization for another file.
    """
    saved = {}
    for identity in identities:
        _identity_fields(identity)
        if identity['kind'] == 'character':
            if identity['id'] not in identity_paths:
                raise LibraryError(f'Missing saved character path for {identity["id"]}')
            previous = str(Path(identity_paths[identity['id']]).expanduser().absolute())
            if previous in saved and saved[previous] != identity:
                raise LibraryError(f'Ambiguous saved character identity: {previous}')
            saved[previous] = identity
    root = library_root(config)
    has_catalog = _catalog_path(config, root).exists()
    available, warnings, hashes = [], [], {}
    for value in config['sources']['characters']:
        original = Path(value).expanduser().absolute()
        identity = saved.get(str(original))
        if identity is None:
            available.append(value)  # New explicit selections are checked by normal reconciliation.
            continue
        if _archived(original):
            raise LibraryError(f'Saved character is archived: {value}')
        if has_catalog:
            replacement = resolve_identity(config, identity)['path']
        else:
            if identity['id'] != 'legacy-' + identity['sha256']:
                raise LibraryError(f'Catalog unavailable for saved character: {identity["id"]}')
            hint = original.relative_to(root).as_posix() if original.is_relative_to(root) else original.name
            replacement = str(_resolve(root, dict(identity, path=hint), hashes))
        available.append(replacement)
        if replacement != value:
            warnings.append({'kind': 'relocated', 'group': 'characters', 'source': value,
                             'replacement': replacement, 'asset_id': identity['id']})
    return list(dict.fromkeys(available)), warnings


def reconcile_catalog_characters(config):
    """Return an authoritative whitelist/warnings, or None for a legacy library.

    Match the recorded path to its stable ID before looking at current resolved
    paths. A different file at the old path never changes the selected identity.
    Basenames are not identities and are never consulted when a catalog exists.
    """
    if not config.get('library', {}).get('root') and not config.get('sources', {}).get('assets'):
        return None
    root = library_root(config)
    path = _catalog_path(config, root)
    if not path.exists():
        return None
    records = _document(path)['entries']
    active = {entry['id']: entry for entry in catalog(config)}
    available, warnings = [], []
    for value in config['sources']['characters']:
        original = Path(value).expanduser().absolute()
        matches = [record for record in records if isinstance(record.get('path'), str)
                   and (root / record['path']).absolute() == original]
        if not matches:
            matches = [entry for entry in active.values() if Path(entry['path']) == original]
        if len(matches) > 1:
            raise LibraryError(f'Ambiguous catalog identity for configured character: {value}')
        selected = active.get(matches[0]['id']) if matches else None
        if (_archived(original) or _archived(original.resolve()) or original.is_symlink()
                or not original.resolve().is_relative_to(root)
                or not selected or selected['kind'] != 'character'):
            warnings.append({'kind': 'unavailable', 'group': 'characters', 'source': value,
                             'reason': 'character retired or unavailable in the active catalog'})
            continue
        replacement = selected['path']
        available.append(replacement)
        if replacement != value:
            warnings.append({'kind': 'relocated', 'group': 'characters', 'source': value,
                             'replacement': replacement, 'asset_id': selected['id']})
    return list(dict.fromkeys(available)), warnings


def _required_text(record, key):
    if not isinstance(record, dict) or not isinstance(record.get(key), str) or not record[key].strip():
        raise LibraryError(f'Missing metadata: {key}')


def _candidates(config, manifest, run_id, root):
    data = _json(manifest)
    if (not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('run_id') != run_id
            or not isinstance(data.get('candidates'), list) or not data['candidates']):
        raise LibraryError('Candidate manifest requires schema_version 1, matching run_id, and candidates')
    workspace = manifest.parent
    if workspace.is_relative_to(root) or root.is_relative_to(workspace):
        raise LibraryError('Run workspace and library must be separate directories')
    ids, targets = set(), {_catalog_path(config, root)}
    for item in data['candidates']:
        if not isinstance(item, dict):
            raise LibraryError('Candidate must be an object')
        _identity_fields(item)
        if item['id'] in ids:
            raise LibraryError('Duplicate candidate id')
        ids.add(item['id'])
        source = _inside(workspace, item.get('path'))
        if not source.is_file() or digest(source) != item['sha256']:
            raise LibraryError(f'Candidate missing or hash mismatch: {item["id"]}')
        if item.get('proxy') is not False or item.get('dependencies') != []:
            raise LibraryError('Candidates must declare proxy:false and dependencies:[] (packed/self-contained)')
        provenance = item.get('provenance')
        _required_text(provenance, 'method')
        if provenance.get('run_id') != run_id or not isinstance(provenance.get('sources'), list):
            raise LibraryError('Candidate provenance needs matching run_id and source identities')
        for identity in provenance['sources']:
            _identity_fields(identity)
        _required_text(item.get('reuse'), 'description')
        _required_text(item['reuse'], 'license')
        if not isinstance(item.get('capabilities'), list) or not all(
                isinstance(c, str) and c.strip() for c in item['capabilities']):
            raise LibraryError('Candidate capabilities must be a list of strings')
        destination = _inside(root, item.get('destination'))
        if destination.suffix.lower() != source.suffix.lower():
            raise LibraryError('Candidate destination must preserve its file extension')
        locations = [destination]
        if source.suffix.lower() == '.blend':
            preview = _inside(root, item.get('preview_destination'))
            if preview.suffix.lower() != '.png':
                raise LibraryError('Blender preview_destination must end in .png')
            locations.append(preview)
        for location in locations:
            if location in targets:
                raise LibraryError('Conflicting candidate destinations')
            targets.add(location)
    return data


# Blender runs with file auto-execution disabled. Dependencies must be packed;
# loading and rendering are real validation, never a worker's success assertion.
_BLENDER_VALIDATE = r'''
import bpy, json, sys
from mathutils import Vector
source, preview, report = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.open_mainfile(filepath=source)
''' + EXTERNAL_PATH_SCAN + r'''
if external or bpy.data.libraries:
    raise RuntimeError('External dependencies must be packed/local: ' + repr(external))
if any(o.get('proxy') or o.get('is_proxy') for o in bpy.data.objects):
    raise RuntimeError('Proxy objects are not publishable')
scene = bpy.context.scene
objects = [o for o in scene.objects if o.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'} and not o.hide_render]
if not objects:
    raise RuntimeError('No renderable asset geometry')
points = [o.matrix_world @ Vector(corner) for o in objects for corner in o.bound_box]
lo = Vector([min(p[i] for p in points) for i in range(3)])
hi = Vector([max(p[i] for p in points) for i in range(3)])
center = (hi + lo) / 2
radius = max((hi - lo).length, 0.1)
camera = bpy.data.objects.new('Validation camera', bpy.data.cameras.new('Validation camera'))
scene.collection.objects.link(camera)
camera.location = center + Vector((1, -1.5, 1)) * radius
camera.rotation_euler = (center - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'; camera.data.ortho_scale = radius * 1.3
scene.camera = camera
light = bpy.data.objects.new('Validation light', bpy.data.lights.new('Validation light', 'AREA'))
scene.collection.objects.link(light)
light.location = center + Vector((0, -1, 2)) * radius
light.rotation_euler = (center - light.location).to_track_quat('-Z', 'Y').to_euler()
light.data.energy = 300 * radius * radius; light.data.size = radius
scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 8
scene.cycles.use_denoising = False
scene.render.resolution_x = 256; scene.render.resolution_y = 256; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'; scene.render.filepath = preview
scene.render.use_compositing = False; scene.render.use_sequencer = False
bpy.ops.render.render(write_still=True)
with open(report, 'w') as handle:
    json.dump({'objects': [o.name for o in objects], 'actions': [a.name for a in bpy.data.actions],
               'armatures': [o.name for o in scene.objects if o.type == 'ARMATURE']}, handle)
'''


def _validate_media(config, source, preview, scratch):
    suffix = source.suffix.lower()
    if suffix == '.py':
        compile(source.read_bytes(), str(source), 'exec', dont_inherit=True)
        return {'format': 'py', 'executed': False}
    if suffix == '.json':
        _json(source)
        return {'format': 'json'}
    if suffix == '.glb':
        return _validate_glb(source)
    if suffix == '.blend':
        script = scratch / 'validate.py'; script.write_text(_BLENDER_VALIDATE)
        report = scratch / 'validation.json'
        _run([config.get('tools', {}).get('blender', 'blender'), '--background', '--factory-startup',
              '--disable-autoexec', '--threads', '2', '--python-exit-code', '1', '--python', str(script),
              '--', str(source), str(preview), str(report)], timeout=180)
        if not preview.is_file() or not preview.stat().st_size:
            raise LibraryError('Blender did not render a preview')
        return _json(report)
    if suffix == '.wav':
        with wave.open(str(source), 'rb') as sound:
            count = sound.getnframes()
            if count <= 0 or len(sound.readframes(count)) != count * sound.getnchannels() * sound.getsampwidth():
                raise LibraryError('Empty or truncated WAV candidate')
        return {'format': 'wav'}
    if suffix in ('.png', '.jpg', '.jpeg'):
        from PIL import Image
        with Image.open(source) as image:
            image.verify()
        return {'format': suffix[1:]}
    raise LibraryError(f'Unsupported candidate format: {suffix}; use .blend, .glb, .py, .json, PNG/JPEG, or PCM WAV')


def _validate_glb(source):
    """Validate the GLB container and portability without executing an importer."""
    size = source.stat().st_size
    with source.open('rb') as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise LibraryError('Truncated GLB header')
        magic, version, length = struct.unpack('<4sII', header)
        if magic != b'glTF' or version != 2 or length != size:
            raise LibraryError('Invalid GLB magic, version, or declared length')
        kinds, document, binary_length = [], None, 0
        while stream.tell() < size:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise LibraryError('Truncated GLB chunk header')
            count, kind = struct.unpack('<I4s', chunk_header)
            if count % 4 or stream.tell() + count > size:
                raise LibraryError('Invalid GLB chunk length')
            kinds.append(kind)
            if kinds == [b'JSON']:
                if count > 16 * 1024 * 1024:
                    raise LibraryError('GLB JSON metadata exceeds 16 MB')
                document = json.loads(stream.read(count))
            elif kinds == [b'JSON', b'BIN\x00']:
                binary_length = count
                stream.seek(count, 1)
            else:
                raise LibraryError('Unsupported GLB chunk order/type')
    if (not isinstance(document, dict) or not isinstance(document.get('asset'), dict)
            or document['asset'].get('version') != '2.0'):
        raise LibraryError('GLB requires glTF 2.0 asset metadata')
    def portable(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'uri' and (not isinstance(child, str) or not child.startswith('data:')):
                    raise LibraryError('GLB has an external resource URI; embed all buffers and images')
                portable(child)
        elif isinstance(value, list):
            for child in value:
                portable(child)
    portable(document)
    buffers = document.get('buffers', [])
    if not isinstance(buffers, list) or not all(isinstance(buffer, dict) for buffer in buffers):
        raise LibraryError('GLB buffers must be an array of objects')
    for index, buffer in enumerate(buffers):
        if 'uri' not in buffer and (index != 0 or not isinstance(buffer.get('byteLength'), int)
                                   or not 0 <= buffer['byteLength'] <= binary_length):
            raise LibraryError('GLB embedded buffer length does not match its binary chunk')
    return {'format': 'glb', 'version': 2, 'self_contained': True}


def _tracking(repo, head):
    branch = _git_optional(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
    branches = [branch] if branch else _git(repo, 'for-each-ref', '--points-at', head,
                                           '--format=%(refname:short)', 'refs/heads/').splitlines()
    candidates = []
    for name in branches:
        if name.startswith('asset-publication/'):
            continue
        remote = _git_optional(repo, 'config', '--get', f'branch.{name}.remote')
        merge = _git_optional(repo, 'config', '--get', f'branch.{name}.merge')
        if remote and remote != '.' and merge.startswith('refs/heads/'):
            candidates.append((remote, merge))
    if len(candidates) != 1:
        raise LibraryError('No unique tracked branch at the checked-out commit; configure a branch/upstream')
    remote, target = candidates[0]
    # Read-only reachability check. Never fetch/rebase another agent's refactor.
    listing = _git(repo, 'ls-remote', '--exit-code', remote, target)
    if not listing:
        raise LibraryError('Publication remote branch is unavailable')
    return remote, target


@contextmanager
def _publication_lock(repo):
    common = Path(_git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    with (common / 'asset-publication.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LibraryError('Another asset publication is running; retry later') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def publish_candidates(config, candidate_manifest_path, run_id):
    """Validate and commit in isolation; return published (local only) or pending.

    A deterministic local ref makes retries durable. Main must push the returned
    commit to the submodule remote BEFORE advancing/pushing the parent's gitlink.
    """
    result = {'status': 'pending', 'run_id': run_id, 'pushed': False, 'error': ''}
    try:
        if config.get('library', {}).get('publish', True) is not True:
            raise LibraryError('Automatic asset publication is disabled')
        if not isinstance(run_id, str) or not run_id.strip():
            raise LibraryError('run_id must be nonempty text')
        root = library_root(config)
        manifest = Path(candidate_manifest_path).expanduser().absolute()
        if manifest.is_symlink() or manifest != manifest.resolve():
            raise LibraryError('Candidate manifest must not use symlinks')
        data = _candidates(config, manifest, run_id, root)
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        repo = Path(_git(root, 'rev-parse', '--show-toplevel')).resolve()
        app = _git_optional(Path(__file__).parent, 'rev-parse', '--show-toplevel')
        if str(repo) == app:
            raise LibraryError('Publication requires a separate asset Git repository, not the application repository')
        with _publication_lock(repo):
            return _publish(config, root, repo, manifest.parent, data, run_id, fingerprint)
    except (LibraryError, OSError, ValueError, TypeError, KeyError, SyntaxError, subprocess.SubprocessError, wave.Error, ImportError) as exc:
        result['error'] = str(exc)
        return result


def _publish(config, root, repo, workspace, data, run_id, fingerprint):
    head = _git(repo, 'rev-parse', 'HEAD')
    remote, target = _tracking(repo, head)
    catalog_path = _catalog_path(config, root)
    catalog_relative = catalog_path.relative_to(repo).as_posix()
    ref_key = hashlib.sha256((catalog_relative + '\n' + run_id).encode()).hexdigest()[:24]
    ref = 'refs/heads/asset-publication/' + ref_key
    existing = _git_optional(repo, 'rev-parse', '--verify', ref)
    result = {'status': 'published', 'run_id': run_id, 'pushed': False, 'error': '',
              'repository': str(repo), 'ref': ref, 'remote': remote, 'target_ref': target,
              'ids': [c['id'] for c in data['candidates']]}
    if existing:
        stored = json.loads(_git(repo, 'show', f'{existing}:{catalog_relative}'))
        receipt = stored.get('publications', {}).get(run_id, {})
        if receipt.get('manifest_sha256') != fingerprint:
            raise LibraryError('Publication run_id already has a different manifest; use a new run_id')
        if head != receipt['base_commit']:
            try:
                _git(repo, 'merge-base', '--is-ancestor', existing, head)
            except LibraryError as exc:
                raise LibraryError('Publication base changed; reconcile the existing publication branch') from exc
        return dict(result, commit=existing, base_commit=receipt['base_commit'])
    prefix = root.relative_to(repo)
    with tempfile.TemporaryDirectory(prefix='asset-publication-') as temporary:
        scratch = Path(temporary)
        worktree = scratch / 'checkout'
        added = False
        try:
            _git(repo, 'worktree', 'add', '--detach', str(worktree), head); added = True
            publication_root = worktree / prefix
            publication_root.mkdir(parents=True, exist_ok=True)
            committed_config = json.loads(json.dumps(config))
            committed_config.setdefault('library', {})['root'] = str(publication_root)
            committed_config['sources'] = {'assets': [str(publication_root)], 'characters': []}
            for original in config.get('sources', {}).get('characters', []):
                try:
                    relative = Path(original).resolve().relative_to(root)
                except ValueError as exc:
                    raise LibraryError('Whitelisted character is outside the publication library') from exc
                committed_config['sources']['characters'].append(str(publication_root / relative))
            # Everything inherited comes from HEAD, never from a dirty index or working tree.
            committed_catalog = _catalog_path(committed_config, publication_root)
            doc = _document(committed_catalog) if committed_catalog.exists() else None
            hydrate = []
            if doc:
                for record in doc['entries']:
                    if record['status'] == 'active':
                        hydrate.extend((prefix / record[k]).as_posix() for k in ('path', 'preview') if record.get(k))
            else:
                hydrate = [Path(p).relative_to(worktree).as_posix() for p in committed_config['sources']['characters']]
            if hydrate and _git_optional(worktree, 'lfs', 'version'):
                _git(worktree, 'lfs', 'checkout', '--', *hydrate)
            if doc:
                catalog(committed_config)
            else:
                # A smudge-disabled checkout contains committed LFS pointers.
                # Preserve their content OIDs in the initial inventory; do not
                # silently seal a catalog that drops active products or sets.
                doc = {'schema_version': 1, 'entries': _legacy(
                    committed_config, publication_root, committed_inventory=True)}
            known = {r['id'] for r in doc['entries']}
            if known.intersection(result['ids']):
                raise LibraryError('Candidate id already exists (active or retired); never overwrite catalog identities')
            retired_hashes = {r['sha256'] for r in doc['entries'] if r['status'] == 'retired'}
            if any(item['sha256'] in retired_hashes for item in data['candidates']):
                raise LibraryError('Candidate content is retired; a new ID cannot reactivate it')
            paths = []
            for index, item in enumerate(data['candidates']):
                if item['provenance']['sources']:
                    resolve_snapshot(committed_config, item['provenance']['sources'])
                source = _inside(workspace, item['path'])
                destination = _inside(publication_root, item['destination'])
                if destination.exists() or _inside(root, item['destination']).exists():
                    raise LibraryError(f'Publication destination already exists: {item["destination"]}')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                if digest(destination) != item['sha256']:
                    raise LibraryError('Candidate changed during publication')
                preview = None
                if destination.suffix.lower() == '.blend':
                    preview = _inside(publication_root, item['preview_destination'])
                    if preview.exists() or _inside(root, item['preview_destination']).exists():
                        raise LibraryError('Publication would overwrite an existing preview')
                    preview.parent.mkdir(parents=True, exist_ok=True)
                validation_dir = scratch / str(index); validation_dir.mkdir()
                validation = _validate_media(config, destination, preview, validation_dir)
                record = {key: item[key] for key in ('id', 'kind', 'sha256', 'capabilities', 'provenance', 'reuse')}
                record.update(path=item['destination'], status='active',
                              preview=item.get('preview_destination') if preview else None,
                              validation=validation)
                if preview:
                    record['preview_sha256'] = digest(preview)
                doc['entries'].append(record)
                paths.append(destination.relative_to(worktree).as_posix())
                if preview:
                    paths.append(preview.relative_to(worktree).as_posix())
            doc.setdefault('publications', {})[run_id] = {'manifest_sha256': fingerprint, 'base_commit': head}
            output = _inside(publication_root, config.get('library', {}).get('catalog', 'asset-catalog.json'))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(doc, indent=2) + '\n')
            paths.append(catalog_relative)
            # Explicit LFS filters work even when the user's global LFS install is absent.
            for path in paths:
                attr = _git(worktree, 'check-attr', 'filter', '--', path)
                if attr.endswith(': lfs'):
                    _git(worktree, 'lfs', 'version')
            _git(worktree, '-c', 'filter.lfs.clean=git-lfs clean -- %f',
                 '-c', 'filter.lfs.process=git-lfs filter-process', '-c', 'filter.lfs.required=true',
                 'add', '--', *paths)
            staged = _git(worktree, 'diff', '--cached', '--name-only', '-z').split('\x00')
            if set(filter(None, staged)) != set(paths):
                raise LibraryError('Staged publication files differ from the approved candidate paths')
            # Abort if an agent moved the source checkout while validation was running.
            if _git(repo, 'rev-parse', 'HEAD') != head:
                raise LibraryError('Asset checkout changed during validation; retry after refactoring')
            for item in data['candidates']:
                for key in ('destination', 'preview_destination'):
                    if item.get(key) and _inside(root, item[key]).exists():
                        raise LibraryError('Publication destination appeared during validation; retry with unique names')
            _git(worktree, '-c', 'commit.gpgsign=false', 'commit', '-m', f'Publish reusable assets: {run_id}')
            commit = _git(worktree, 'rev-parse', 'HEAD')
            _git(repo, 'update-ref', ref, commit, '0' * 40)
            return dict(result, commit=commit, base_commit=head)
        finally:
            if added:
                _git(repo, 'worktree', 'remove', '--force', str(worktree))


def _publication_remote_tip(repo, remote, target, commit):
    """Prove the entire live-remote outgoing range is just this approved commit."""
    tip = _git(repo, 'ls-remote', '--exit-code', remote, target).split()[0]
    if tip == commit:
        return tip  # Idempotent retry: nothing is outgoing.
    try:
        _git(repo, 'merge-base', '--is-ancestor', tip, commit)
        outgoing = _git(repo, 'rev-list', f'{tip}..{commit}').splitlines()
    except LibraryError as exc:
        raise LibraryError('Outgoing publication ancestry diverges from the live remote tip') from exc
    if outgoing != [commit]:
        raise LibraryError('Outgoing ancestry includes unrelated unpushed commits; publish those separately first')
    return tip


def _remove_push_worktree(repo, worktree, temporary, admin):
    """Remove only this operation's checkout, including its nested Git metadata."""
    common = Path(_git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    if (worktree != Path(temporary) / 'checkout' or worktree.is_symlink()
            or admin.is_symlink() or admin.parent != common / 'worktrees'
            or Path((admin / 'gitdir').read_text().strip()) != worktree / '.git'):
        raise LibraryError('Refusing cleanup of an unowned publication worktree')
    try:
        _git(repo, 'worktree', 'remove', '--force', str(worktree))
    except LibraryError:
        # Git can refuse removal of worktrees containing initialized submodules.
        # Never deinit (shared source config) or prune other agents' worktrees.
        if worktree.is_symlink() or admin.is_symlink():
            raise LibraryError('Publication worktree ownership changed during cleanup')
        if admin.exists() and Path((admin / 'gitdir').read_text().strip()) != worktree / '.git':
            raise LibraryError('Publication worktree ownership changed during cleanup')
        if worktree.exists():
            shutil.rmtree(worktree)
        if admin.exists():
            shutil.rmtree(admin)


def push_publication(config, publication):
    """Push a retained publication and LFS objects; never advance the parent pin.

    Retry with the returned result after any pending failure. The source checkout
    may be dirty; checks execute only in a temporary checkout of the commit.
    """
    result = dict(publication, status='pending', pushed=False, error='')
    try:
        if config.get('library', {}).get('publish', True) is not True:
            raise LibraryError('Automatic asset publication is disabled')
        root = library_root(config)
        repo = Path(_git(root, 'rev-parse', '--show-toplevel')).resolve()
        if str(repo) != publication.get('repository'):
            raise LibraryError('Publication repository does not match the configured library')
        commit = publication.get('commit', '')
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40,64}', commit):
            raise LibraryError('Publication has no valid commit to push')
        with _publication_lock(repo):
            remote, target = _tracking(repo, _git(repo, 'rev-parse', 'HEAD'))
            if (remote, target) != (publication.get('remote'), publication.get('target_ref')):
                raise LibraryError('Publication upstream changed; reconcile before pushing')
            catalog_relative = _catalog_path(config, root).relative_to(repo).as_posix()
            run_id = publication.get('run_id', '')
            key = hashlib.sha256((catalog_relative + '\n' + run_id).encode()).hexdigest()[:24]
            ref = 'refs/heads/asset-publication/' + key
            if publication.get('ref') != ref or _git(repo, 'rev-parse', '--verify', ref) != commit:
                raise LibraryError('Publication ref no longer identifies the validated commit')
            stored = json.loads(_git(repo, 'show', f'{commit}:{catalog_relative}'))
            receipt = stored.get('publications', {}).get(run_id, {})
            base = _git(repo, 'rev-parse', commit + '^')
            if receipt.get('base_commit') != base or publication.get('base_commit') != base:
                raise LibraryError('Publication base/receipt mismatch')
            ids = publication.get('ids', [])
            selected = [entry for entry in stored['entries'] if entry['id'] in ids]
            if not ids or {r['id'] for r in selected} != set(ids):
                raise LibraryError('Publication IDs do not match the committed catalog')
            prefix = root.relative_to(repo)
            expected = {catalog_relative}
            for entry in selected:
                if entry['status'] != 'active' or entry.get('provenance', {}).get('run_id') != run_id:
                    raise LibraryError('Publication contains an inactive or unrelated asset')
                expected.update((prefix / _relative(entry[k])).as_posix()
                                for k in ('path', 'preview') if entry.get(k))
            changed = set(filter(None, _git(repo, 'diff-tree', '--no-commit-id', '--name-only',
                                            '-z', '-r', commit).split('\x00')))
            if changed != expected:
                raise LibraryError('Publication diff includes missing or unrelated files')
            _publication_remote_tip(repo, remote, target, commit)
            _git(repo, 'diff', '--check', base, commit)
            with tempfile.TemporaryDirectory(prefix='asset-push-') as temporary:
                worktree = Path(temporary) / 'checkout'
                added = False
                admin = None
                try:
                    _git(repo, 'worktree', 'add', '--detach', str(worktree), commit); added = True
                    admin = Path(_git(worktree, 'rev-parse', '--absolute-git-dir'))
                    lfs_paths = [path for path in expected if _git(worktree, 'check-attr', 'filter', '--', path).endswith(': lfs')]
                    if lfs_paths:
                        _git(worktree, 'lfs', 'version')
                        _git(worktree, 'lfs', 'checkout', '--', *lfs_paths)
                    for entry in selected:
                        asset = _inside(worktree, (prefix / _relative(entry['path'])).as_posix())
                        if digest(asset) != entry['sha256']:
                            raise LibraryError('Publication content differs from the catalog hash')
                        if entry.get('preview'):
                            preview = _inside(worktree, (prefix / _relative(entry['preview'])).as_posix())
                            if digest(preview) != entry.get('preview_sha256'):
                                raise LibraryError('Publication preview differs from the catalog hash')
                    # Check out the recorded gitlinks, never remote branch tips or
                    # dirty source submodules. Keep normal Git URL/protocol rules.
                    _git(worktree, 'submodule', 'update', '--init', '--recursive', '--checkout')
                    # Existing repository checks are run from the committed tree, not dirty files.
                    makefile = worktree / 'Makefile'
                    if makefile.is_file() and re.search(r'^check-layout\s*:', makefile.read_text(), re.M):
                        _run(['make', 'check-layout'], cwd=worktree, timeout=180)
                    tip = _publication_remote_tip(worktree, remote, target, commit)
                    if lfs_paths:
                        # Explicit LFS upload is necessary because isolated Git commands disable hooks.
                        _git(worktree, 'lfs', 'push', remote, commit)
                    # The explicit lease is a compare-and-swap guard for the
                    # fast-forward proven above, including remote rewinds racing
                    # the push. It must never authorize a non-fast-forward.
                    _git(worktree, 'push', '--porcelain', f'--force-with-lease={target}:{tip}',
                         remote, f'{commit}:{target}')
                    remote_commit = _git(worktree, 'ls-remote', '--exit-code', remote, target).split()[0]
                    if remote_commit != commit:
                        raise LibraryError('Remote tip changed before publication could be verified')
                finally:
                    if added:
                        if admin is None:
                            _git(repo, 'worktree', 'remove', '--force', str(worktree))
                        else:
                            _remove_push_worktree(repo, worktree, temporary, admin)
            result.update(status='published', pushed=True)
    except (LibraryError, OSError, ValueError, subprocess.SubprocessError, TypeError, KeyError) as exc:
        result['error'] = str(exc)
    return result


def adopt_publication(config, publication):
    """Fast-forward a clean source checkout after a verified push; preserve dirty work.

    Remote publication status is retained. Local outcome uses adopted,
    adoption_status, and adoption_error so a pending integration is not a failed push.
    """
    result = dict(publication, adopted=False, adoption_status='pending', adoption_error='')
    try:
        if publication.get('pushed') is not True:
            raise LibraryError('Push publication successfully before adopting its commit')
        root = library_root(config)
        repo = Path(_git(root, 'rev-parse', '--show-toplevel')).resolve()
        commit = publication.get('commit', '')
        if str(repo) != publication.get('repository') or not re.fullmatch(r'[0-9a-f]{40,64}', commit):
            raise LibraryError('Publication repository or commit does not match the configured library')
        with _publication_lock(repo):
            if _git(repo, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'):
                raise LibraryError('Asset checkout is dirty; local adoption is pending without changing it')
            head = _git(repo, 'rev-parse', 'HEAD')
            _git(repo, 'merge-base', '--is-ancestor', head, commit)
            comparison = head if head != commit else commit + '^'
            changed = list(filter(None, _git(repo, 'diff', '--name-only', '-z', '--diff-filter=AM',
                                             comparison, commit).split('\x00')))
            lfs_paths = []
            # Check LFS availability before advancing HEAD; hydrate only changed active assets.
            with tempfile.TemporaryDirectory(prefix='asset-adopt-') as temporary:
                worktree = Path(temporary) / 'checkout'
                added = False
                try:
                    _git(repo, 'worktree', 'add', '--detach', str(worktree), commit); added = True
                    for path in changed:
                        if not _archived(path) and _git(worktree, 'check-attr', 'filter', '--', path).endswith(': lfs'):
                            lfs_paths.append(path)
                    if lfs_paths:
                        _git(worktree, 'lfs', 'checkout', '--', *lfs_paths)
                        if any(_lfs_pointer(worktree / path) for path in lfs_paths):
                            raise LibraryError('LFS objects are missing locally; hydrate before adopting')
                finally:
                    if added:
                        _git(repo, 'worktree', 'remove', '--force', str(worktree))
            if (_git(repo, 'rev-parse', 'HEAD') != head
                    or _git(repo, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none')):
                raise LibraryError('Asset checkout changed before adoption; local integration is pending')
            _git(repo, 'merge', '--ff-only', '--no-edit', '--no-overwrite-ignore', commit)
            if lfs_paths:
                _git(repo, 'lfs', 'checkout', '--', *lfs_paths)
            result.update(adopted=True, adoption_status='adopted', checkout_commit=commit)
    except (LibraryError, OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        result['adoption_error'] = str(exc)
    return result
