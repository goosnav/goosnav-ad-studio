"""Acceptance is controller code, not the worker's completion sentence."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile


class ContractError(ValueError):
    pass


# Where a review may send an ad back to. The reviewer picks the earliest stage that is
# actually wrong, so a bad cut does not re-render the animation and a bad mix does not re-cast.
RESTARTS = {'board_review': ('direct', 'assets', 'audio'),
            'review': ('direct', 'assets', 'audio', 'animate'),
            'edit_review': ('direct', 'assets', 'audio', 'animate', 'edit_plan', 'edit'),
            'creative_qa': ('direct', 'assets', 'audio', 'animate', 'edit_plan', 'edit', 'frame')}


def digest(path, checkpoint=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            if checkpoint:
                checkpoint()
            h.update(block)
    return h.hexdigest()


def contained(workspace, value, *, allow_empty=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ContractError('Artifact paths must be nonempty relative paths')
    root = Path(workspace).resolve()
    p = root / value
    if '..' in Path(value).parts or any(q.is_symlink() for q in [p, *p.parents] if q != root.parent):
        raise ContractError(f'Unsafe artifact path: {value}')
    if not p.resolve().is_relative_to(root) or not p.is_file() or (not allow_empty and p.stat().st_size == 0):
        raise ContractError(f'Missing/empty artifact: {value}')
    return p


SEVERITY_SYNONYMS = {'critical': 'blocking', 'blocker': 'blocking', 'major': 'important',
                     'moderate': 'important', 'medium': 'important', 'low': 'minor', 'nit': 'minor'}


def text(d, key):
    if not isinstance(d.get(key), str) or not d[key].strip():
        raise ContractError(f'{key} must be a nonempty plain-text string, not an object or list. '
                            f'Use "{key}": "your text", not "{key}": {{"text": "..."}}.')


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
        paths.add(f['path'])
        # Silence from a diagnostic command (e.g. FFmpeg black/freeze detection)
        # can mean no defects. Only notes logs may be empty, never production media.
        try:
            contained(workspace, f['path'], allow_empty=f['kind'] == 'notes' and Path(f['path']).suffix.lower() == '.log')
        except ContractError as exc:
            if stage in ('select', 'critique', 'critique_final', 'script_sense', 'board_review',
                         'review', 'edit_review', 'creative_qa'):
                raise ContractError(f'{exc}. For a review, use files: [] unless you wrote new local '
                                    'review artifacts. Cite accepted input images in findings.target, '
                                    'not files; do not invent relative paths or copy input media.') from exc
            raise
    if stage == 'research':
        for key in ('brand_brief', 'creative_directions'):
            text(data, key)
        if not isinstance(data.get('references'), list):
            raise ContractError('Research needs a references list (empty only when research was unavailable)')
        for r in data['references']:
            for key in ('url', 'observation', 'application'):
                text(r, key)
    elif stage == 'script':
        scripts = data.get('scripts')
        count = context.get('count', 1)
        if not isinstance(scripts, list) or len(scripts) != count:
            raise ContractError(f'Return exactly {count} script guides, one per ad; no candidate contest.')
        ids = set()
        for script in scripts:
            if not isinstance(script, dict):
                raise ContractError('Each script guide must be an object')
            for key in ('id', 'title', 'premise', 'script', 'visual_direction', 'product', 'cta'):
                text(script, key)
            if script['id'] in ids:
                raise ContractError('Script guide IDs must be unique')
            ids.add(script['id'])
    elif stage in ('write', 'revise'):
        scripts = data.get('scripts')
        count = context.get('count', 1)
        required = count * 2
        if not isinstance(scripts, list):
            raise ContractError(f'scripts must be an array of at least {required} candidate objects '
                                f'for {count} ads (two per ad), not an object or plain text.')
        if len(scripts) < required:
            raise ContractError(f'Need two distinct candidate scripts per requested ad: '
                                f'{count} ads require at least {required}; received {len(scripts)}. '
                                f'Preserve existing valid candidates and add {required - len(scripts)} '
                                'distinct candidates with unique IDs. Ad count is not product count. '
                                'Resubmit the complete scripts array in result.json.')
        ids = []
        for index, script in enumerate(scripts):
            if not isinstance(script, dict):
                raise ContractError(f'scripts[{index}] must be an object with id, title, premise, '
                                    'script, visual_direction, product, and cta as plain-text fields.')
            try:
                for key in ('id', 'title', 'premise', 'script', 'visual_direction', 'product', 'cta'):
                    text(script, key)
            except ContractError as exc:
                raise ContractError(f'scripts[{index}]: {exc}') from exc
            ids.append(script['id'])
        if len(set(ids)) != len(ids):
            raise ContractError('Script IDs must be unique')
    elif stage in ('critique', 'critique_final', 'script_sense', 'board_review',
                  'review', 'edit_review', 'creative_qa'):
        if data.get('verdict') not in ('pass', 'revise'):
            raise ContractError('Review verdict must be pass or revise')
        if not isinstance(data.get('findings'), list):
            raise ContractError('Review needs concrete findings')
        for f in data['findings']:
            for key in ('target', 'problem', 'fix', 'severity'):
                text(f, key)
            severity = f['severity'].strip().lower()
            f['severity'] = SEVERITY_SYNONYMS.get(severity, severity)
            if f['severity'] not in ('blocking', 'important', 'minor'):
                raise ContractError('Unknown finding severity. Expected blocking, important, or minor; '
                                    'use summary for unverified observations that are not defects.')
        if data['verdict'] == 'pass' and any(f['severity'] == 'blocking' for f in data['findings']):
            raise ContractError('Review cannot pass unresolved blockers')
        strict = stage in ('script_sense', 'edit_review') or (
            context.get('strict_review') and stage in ('board_review', 'creative_qa'))
        if strict and data['verdict'] == 'pass' and any(
                f['severity'] == 'important' for f in data['findings']):
            raise ContractError('Review cannot pass unresolved important problems')
        if data['verdict'] == 'revise' and not data['findings']:
            raise ContractError('Revision needs actionable findings')
        if stage == 'script_sense':
            logic = data.get('logic')
            chosen = context.get('selected_ids', [])
            if not isinstance(logic, list) or len(logic) != len(chosen) or \
                    {x.get('script_id') for x in logic if isinstance(x, dict)} != set(chosen):
                raise ContractError('script_sense must justify the story logic of every selected script')
            for entry in logic:
                for field in ('script_id', 'setup', 'cause', 'reaction', 'payoff', 'product_connection'):
                    text(entry, field)
        if stage in RESTARTS and data['verdict'] == 'revise' and data.get('restart', RESTARTS[stage][-1]) not in RESTARTS[stage]:
            raise ContractError(f'restart must be one of {", ".join(RESTARTS[stage])}')
    elif stage == 'direct':
        if not isinstance(data.get('direction'), dict):
            raise ContractError('Director needs a direction object')
    elif stage == 'select':
        # The selection pass also replaces two extra LLM story-review agents.
        if data.get('verdict') not in ('pass', 'revise'):
            raise ContractError('Selection requires a verdict')
        if not isinstance(data.get('findings'), list):
            raise ContractError('Selection requires findings (can be empty)')
        for finding in data['findings']:
            for key in ('target', 'problem', 'fix', 'severity'):
                text(finding, key)
            if finding['severity'] not in ('blocking', 'important', 'minor'):
                raise ContractError('Invalid selection finding severity')
        selected = data.get('selected')
        if not isinstance(selected, list) or not all(isinstance(x, str) for x in selected):
            raise ContractError('selected must be a list of script IDs')
        if data['verdict'] == 'revise':
            if not data['findings']:
                raise ContractError('Rejected scripts require actionable findings')
            if selected:
                raise ContractError('Rejected selection must not authorize production')
        elif len(selected) != context['count'] or len(set(selected)) != len(selected):
            raise ContractError(f'Select exactly {context["count"]} distinct script ID(s) in total; '
                                f'received {len(selected)}: {selected}. Keep only the best '
                                'requested number and matching logic entries.')
        if not set(selected) <= set(context['candidate_ids']):
            raise ContractError('Selection refers to an unknown script')
        if data['verdict'] == 'pass' and any(f['severity'] in ('blocking', 'important') for f in data['findings']):
            raise ContractError('Selection cannot pass unresolved important problems')
        if data['verdict'] == 'pass':
            logic = data.get('logic')
            if not isinstance(logic, list) or len(logic) != len(selected) or \
                    {entry.get('script_id') for entry in logic if isinstance(entry, dict)} != set(selected):
                raise ContractError('Selection must substantiate the story logic of each chosen script')
            for entry in logic:
                for field in ('script_id', 'setup', 'cause', 'reaction', 'payoff', 'product_connection'):
                    text(entry, field)
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
    elif stage == 'edit_plan':
        if not isinstance(data.get('plan'), dict):
            raise ContractError('edit_plan must return a structured cut plan')
    elif stage == 'edit':
        if context.get('compact'):
            validate('creative_qa', data, workspace, {**context, 'strict_review': True})
            if data['verdict'] == 'revise':
                if data.get('restart') != 'animate':
                    raise ContractError('Editor repair must target animate; preserve the script guide')
                return data
        if not isinstance(data.get('plan'), dict):
            raise ContractError('Editor must return its approved cut plan')
        for key in ('master', 'timeline'):
            if data.get(key) not in paths:
                raise ContractError(f'{key} must name a declared editor file')
    elif stage in ('audio', 'animate', 'edit'):
        required = {'audio': ['mix', 'timeline'], 'animate': ['preview', 'source'],
                    'edit': ['master', 'timeline']}[stage]
        for key in required:
            if data.get(key) not in paths:
                raise ContractError(f'{key} must name a declared file')
    return data


def copy_checked(source, target, checkpoint):
    """Checked atomic copy; a prior read-only export is safely replaceable."""
    checkpoint()
    target=Path(target)
    with tempfile.NamedTemporaryFile(dir=target.parent,prefix=f'.{target.name}.',delete=False) as dst:
        temporary=Path(dst.name)
        try:
            with Path(source).open('rb') as src:
                for block in iter(lambda: src.read(1024 * 1024), b''):
                    checkpoint()
                    dst.write(block)
            dst.close()
            shutil.copystat(source,temporary)
            checkpoint()
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def promote(data, workspace, destination, checkpoint=None):
    """Copy declared files; accepted artifacts never share a writable worker directory."""
    destination = Path(destination)
    if destination.exists():
        raise ContractError('Artifact destination already exists')
    destination.mkdir(parents=True)
    accepted = json.loads(json.dumps(data))
    mapping = {}
    for f in accepted['files']:
        if checkpoint:
            checkpoint()
        source = contained(workspace, f['path'],
                           allow_empty=f['kind'] == 'notes' and Path(f['path']).suffix.lower() == '.log')
        target = destination / f['path']; target.parent.mkdir(parents=True, exist_ok=True)
        if checkpoint:
            copy_checked(source, target, checkpoint)
        else:
            shutil.copy2(source, target)
        target.chmod(0o444)
        mapping[f['path']] = str(target)
        f.update(path=str(target), sha256=digest(target, checkpoint), bytes=target.stat().st_size)
    def remap(value):
        # Any declared relative path, wherever it appears (scene, source lists, board images...).
        if isinstance(value, str):
            return mapping.get(value, value)
        if isinstance(value, list):
            return [remap(v) for v in value]
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        return value
    for key in list(accepted):
        if key not in ('summary', 'files'):
            accepted[key] = remap(accepted[key])
    if checkpoint:
        checkpoint()
    (destination / 'accepted.json').write_text(json.dumps(accepted, indent=2))
    return accepted


def verify_accepted(result, checkpoint=None):
    for f in result.get('files', []):
        if checkpoint:
            checkpoint()
        p = Path(f['path'])
        if not p.is_file() or digest(p, checkpoint) != f['sha256']:
            raise ContractError(f'Accepted artifact changed or disappeared: {p}')
