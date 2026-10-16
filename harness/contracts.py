"""Acceptance is controller code, not the worker's completion sentence."""
import hashlib
import json
from pathlib import Path
import shutil


class ContractError(ValueError):
    pass


# Where a review may send an ad back to. The reviewer picks the earliest stage that is
# actually wrong, so a bad cut does not re-render the animation and a bad mix does not re-cast.
RESTARTS = {'review': ('direct', 'assets', 'audio', 'animate'),
            'creative_qa': ('direct', 'assets', 'audio', 'animate', 'edit')}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def contained(workspace, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ContractError('Artifact paths must be nonempty relative paths')
    root = Path(workspace).resolve()
    p = root / value
    if '..' in Path(value).parts or any(q.is_symlink() for q in [p, *p.parents] if q != root.parent):
        raise ContractError(f'Unsafe artifact path: {value}')
    if not p.resolve().is_relative_to(root) or not p.is_file() or p.stat().st_size == 0:
        raise ContractError(f'Missing/empty artifact: {value}')
    return p


def text(d, key):
    if not isinstance(d.get(key), str) or not d[key].strip():
        raise ContractError(f'Missing text field: {key}')


def validate(stage, data, workspace, context):
    if not isinstance(data, dict):
        raise ContractError('result.json must be an object')
    text(data, 'summary')
    if not isinstance(data.get('files'), list):
        raise ContractError('files must be an array')
    paths = set()
    for f in data['files']:
        if not isinstance(f, dict):
            raise ContractError('file entries must be objects')
        text(f, 'kind'); text(f, 'path')
        if f['path'] in paths:
            raise ContractError('Duplicate artifact path')
        paths.add(f['path']); contained(workspace, f['path'])
    if stage == 'research':
        for key in ('brand_brief', 'creative_directions'):
            text(data, key)
        if not isinstance(data.get('references'), list):
            raise ContractError('Research needs a references list (empty only when research was unavailable)')
        for r in data['references']:
            for key in ('url', 'observation', 'application'):
                text(r, key)
    elif stage in ('write', 'revise'):
        scripts = data.get('scripts')
        if not isinstance(scripts, list) or len(scripts) < context.get('count', 1) * 3:
            raise ContractError('Need three distinct candidate scripts per requested ad')
        ids = []
        for script in scripts:
            for key in ('id', 'title', 'premise', 'script', 'visual_direction', 'product', 'cta'):
                text(script, key)
            ids.append(script['id'])
        if len(set(ids)) != len(ids):
            raise ContractError('Script IDs must be unique')
    elif stage in ('critique', 'critique_final', 'review', 'creative_qa'):
        if data.get('verdict') not in ('pass', 'revise'):
            raise ContractError('Review verdict must be pass or revise')
        if not isinstance(data.get('findings'), list):
            raise ContractError('Review needs concrete findings')
        for f in data['findings']:
            for key in ('target', 'problem', 'fix', 'severity'):
                text(f, key)
            if f['severity'] not in ('blocking', 'important', 'minor'):
                raise ContractError('Unknown finding severity')
        if data['verdict'] == 'pass' and any(f['severity'] == 'blocking' for f in data['findings']):
            raise ContractError('Review cannot pass unresolved blockers')
        if data['verdict'] == 'revise' and not data['findings']:
            raise ContractError('Revision needs actionable findings')
        if stage in RESTARTS and data['verdict'] == 'revise' and data.get('restart', 'audio') not in RESTARTS[stage]:
            raise ContractError(f'restart must be one of {", ".join(RESTARTS[stage])}')
    elif stage == 'direct':
        if not isinstance(data.get('direction'), dict):
            raise ContractError('Director needs a direction object')
    elif stage == 'select':
        selected = data.get('selected')
        if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
            raise ContractError('selected must be a list of script IDs')
        if len(selected) != context['count'] or len(set(selected)) != len(selected):
            raise ContractError('Select exactly count distinct scripts')
        if not set(selected) <= set(context['candidate_ids']):
            raise ContractError('Selection refers to an unknown script')
        text(data, 'reason')
    elif stage == 'assets':
        if not isinstance(data.get('assets'), list) or not data['assets']:
            raise ContractError('Asset manifest is required')
        for a in data['assets']:
            for key in ('name', 'source', 'rights'):
                text(a, key)
            if a.get('proxy') is not False:
                raise ContractError('Replace draft proxies before production')
        if not paths:
            raise ContractError('Asset stage needs a manifest/source artifact')
    elif stage in ('audio', 'animate', 'edit'):
        required = {'audio': ['mix', 'timeline'], 'animate': ['preview', 'source'], 'edit': ['master']}[stage]
        for key in required:
            if data.get(key) not in paths:
                raise ContractError(f'{key} must name a declared file')
    return data


def promote(data, workspace, destination):
    """Copy declared files; accepted artifacts never share a writable worker directory."""
    destination = Path(destination)
    if destination.exists():
        raise ContractError('Artifact destination already exists')
    destination.mkdir(parents=True)
    accepted = json.loads(json.dumps(data))
    mapping = {}
    for f in accepted['files']:
        source = contained(workspace, f['path'])
        target = destination / f['path']; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        target.chmod(0o444)
        mapping[f['path']] = str(target)
        f.update(path=str(target), sha256=digest(target), bytes=target.stat().st_size)
    for key in ('mix', 'timeline', 'preview', 'source', 'master'):
        if key in accepted:
            accepted[key] = mapping[accepted[key]]
    (destination / 'accepted.json').write_text(json.dumps(accepted, indent=2))
    return accepted


def verify_accepted(result):
    for f in result.get('files', []):
        p = Path(f['path'])
        if not p.is_file() or digest(p) != f['sha256']:
            raise ContractError(f'Accepted artifact changed or disappeared: {p}')
