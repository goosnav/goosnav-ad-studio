"""Deterministic animator sidecars. Completion receipts never imply creative approval.

Run audio with the configured audio interpreter. Artifact paths in production.json
are relative to its directory; submit/edit receipts are relative to --output's parent.
"""
import argparse
import copy
from contextlib import redirect_stdout
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

from . import creative, editing, mix, voice
from .contracts import contained, digest, validate
from .direction import check_direction, check_scratch_takes
from .lipsync import mouth_curves


def _read(path):
    return json.loads(Path(path).read_text())


def _write(path, value):
    """Publish complete JSON atomically without replacing caller-owned artifacts."""
    encoded = json.dumps(value, indent=2, allow_nan=False) + '\n'
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.production-',
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.link(temporary, path)  # Exclusive atomic creation, never replace.
        finally:
            temporary.unlink(missing_ok=True)


def _safe(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f'Unsafe path: {path}')
    return path


def _record(root, path, kind):
    relative = Path(path).relative_to(root).as_posix()
    actual = contained(root, relative)
    return {'path': relative, 'kind': kind, 'sha256': digest(actual),
            'bytes': actual.stat().st_size}


def _verified(receipt, root):
    """Also accept controller-promoted absolute declarations inside the artifact root."""
    entries = {}
    for entry in receipt['files']:
        path = _safe(root / entry['path'])
        relative = path.relative_to(root).as_posix()
        actual = contained(root, relative)
        if relative in entries:
            raise ValueError(f'Duplicate dependency: {relative}')
        if ('sha256' in entry and digest(actual) != entry['sha256']) or (
                'bytes' in entry and actual.stat().st_size != entry['bytes']):
            raise ValueError(f'Changed dependency: {relative}')
        entries[relative] = entry
    return entries


def _number(value, label):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite seconds')
    return value


def audio(plan_path, config_path, output, cache_dir=None):
    """Measure one take per line, align without truncation, and save portable audio."""
    plan, config = _read(plan_path), _read(config_path)
    direction = copy.deepcopy(plan['direction'])
    if not isinstance(plan.get('summary'), str) or not plan['summary'].strip():
        raise ValueError('Plan needs a nonempty summary')
    for key in ('duration', 'cast', 'lines', 'end_card', 'mix'):
        if key not in direction:
            raise ValueError(f'direction.{key} is required')
    if not isinstance(direction['mix'], str) or not direction['mix'].strip():
        raise ValueError('direction.mix must explain the sound design')
    story_end = _number(direction['duration'], 'duration')
    if config['output']['cta']:
        story_end -= _number(direction['end_card']['seconds'], 'end_card.seconds')
    root = _safe(output)
    fingerprint = hashlib.sha256(json.dumps({'plan': plan, 'config': config},
                                 sort_keys=True, allow_nan=False).encode()).hexdigest()
    checkpoint = root / 'checkpoint.json'
    if root.exists() and any(root.iterdir()):
        if not checkpoint.is_file() or _read(checkpoint) != {'input_sha256': fingerprint}:
            raise ValueError('Output collision: plan/config changed or folder is unowned; choose a fresh output folder')
    root.mkdir(parents=True, exist_ok=True)
    if not checkpoint.exists():
        _write(checkpoint, {'input_sha256': fingerprint})
    complete = root / 'production.json'
    if complete.exists():
        result = _read(complete)
        if result.get('input_sha256') != fingerprint:
            raise ValueError('Production checkpoint mismatch; choose a fresh output folder')
        _verified(result, root)
        if result['direction'] != _read(root / 'measured-plan.json')['direction']:
            raise ValueError('Production direction differs from measured checkpoint')
        check_direction(result['direction'], config)
        check_scratch_takes(result, root)
        return result

    cast = {c['speaker']: c for c in direction['cast']}
    if len(cast) != len(direction['cast']):
        raise ValueError('Duplicate cast speaker')
    request_lines = []
    for i, line in enumerate(direction['lines']):
        for key in ('speaker', 'text', 'delivery'):
            if not isinstance(line.get(key), str) or not line[key].strip():
                raise ValueError(f'Line {i}: {key} is required text')
        actor = cast[line['speaker']]
        row = {k: line[k] for k in ('speaker', 'text', 'delivery')}
        row.update(id=line.get('id', f'line-{i + 1}'), voice=actor['voice'])
        if 'selected_take' in line:
            row['selected_take'] = line['selected_take']
        # Explicit controls constrain reused takes too; never invent speed/auditions.
        for key in ('speed', 'seed', 'model', 'revision', 'language', 'reference',
                    'exaggeration', 'cfg', 'phrasing', 'pauses', 'polish'):
            # cast.model is a character .blend, not the TTS model.
            if key != 'model' and key in actor:
                row[key] = actor[key]
            if key in line:
                row[key] = line[key]
        request_lines.append(row)
    manifest = root / 'scratch/manifest.json'
    if request_lines:
        if not manifest.exists():
            request = {'provider': config['audio']['voice_provider'], 'effort': 'low',
                       'fast': True, 'lines': request_lines,
                       'cache_dir': str(_safe(cache_dir) if cache_dir is not None
                                        else root / 'voice-cache')}
            # run_batch keeps completed recipes in its cache even if a later line
            # fails. Retrying the same request reuses those WAVs, not synthesis.
            voice.run_batch(request, manifest.parent)
        _, _, rows = creative._read_selected(manifest)
        if len(rows) != len(request_lines):
            raise ValueError('Scratch checkpoint line count mismatch')
        cursor = 0
        for line, requested, (entry, take) in zip(direction['lines'], request_lines, rows):
            if any(entry[k] != requested[k] for k in ('id', 'speaker', 'text', 'voice')):
                raise ValueError('Scratch checkpoint does not match authored dialogue')
            start = _number(line.get('start', cursor / 48000), 'line.start')
            start_sample = round(start * 48000)
            if start_sample < cursor:
                raise ValueError('Explicit line start precedes measured cursor; move it later or shorten dialogue')
            end_sample = start_sample + take['polished']['frames']
            if end_sample > round(story_end * 48000):
                raise ValueError('Shorten dialogue: full measured WAVs and reply gaps do not fit before the story end; use a fresh output folder for the revised plan')
            line.update(id=requested['id'], start=start_sample / 48000, end=end_sample / 48000)
            cursor = end_sample + 8640  # 0.18 seconds between full takes.
    if 'beats' not in direction:
        direction['beats'] = [{'start': 0, 'end': story_end, 'shot': 'Two-shot',
                               'picture': 'Cast faces visible in a shared two-shot.',
                               'sound': direction['mix'], 'faces': list(cast)}]
    check_direction(direction, config)
    measured_plan = {'summary': plan['summary'], 'direction': direction}
    local_plan = root / 'measured-plan.json'
    if not local_plan.exists():
        _write(local_plan, measured_plan)
    elif _read(local_plan) != measured_plan:
        raise ValueError('Measured plan checkpoint mismatch')
    direct = root / 'direction-result.json'
    if not direct.exists():
        if request_lines:
            creative.submit_direction(local_plan, manifest, direct, root)
        else:
            _write(direct, {**measured_plan, 'scratch_takes': None,
                           'files': [_record(root, local_plan, 'direction_source')]})
    direct_data = _read(direct)
    if direct_data['direction'] != direction or direct_data['summary'] != plan['summary']:
        raise ValueError('Direction receipt differs from measured checkpoint')
    _verified(direct_data, root)
    check_scratch_takes(direct_data, root)
    # A failed mix remains available for diagnosis. Resume a complete mix, or
    # use a fresh local attempt without deleting any partial artifacts.
    candidates = sorted(root.glob('mix-*/result.json'))
    if candidates:
        mixed_dir = candidates[-1].parent
        _verified(_read(candidates[-1]), mixed_dir)
    else:
        index = 0
        while (root / f'mix-{index:04d}').exists():
            index += 1
        mixed_dir = root / f'mix-{index:04d}'
        mix.assemble(direct, mixed_dir, fps=config['output']['fps'], no_bed=True)
    if _read(mixed_dir / 'audit.json')['source_direct_sha256'] != digest(direct):
        raise ValueError('Mix checkpoint belongs to a different direction receipt')
    staged = root / 'audio-result.json'
    if not staged.exists():
        mix.stage_result(mixed_dir, staged)
    mixed = _read(staged)
    _verified(mixed, root)
    mouths = mouth_curves(root / mixed['dialogue_stem'], _read(root / mixed['timeline']),
                          config['output']['fps'])
    mouth_path = root / 'mouths.json'
    if not mouth_path.exists():
        _write(mouth_path, mouths)
    elif _read(mouth_path) != mouths:
        raise ValueError('Mouth checkpoint mismatch')
    result = {**measured_plan, 'input_sha256': fingerprint,
              'scratch_takes': direct_data.get('scratch_takes'),
              **{k: mixed[k] for k in ('mix', 'dialogue_stem', 'timeline')}, 'mouths': 'mouths.json'}
    declarations = {f['path']: f for f in direct_data['files'] + mixed['files']}
    for path, kind in ((direct, 'direction'), (staged, 'audio_receipt'),
                       (mouth_path, 'timeline'), (checkpoint, 'checkpoint')):
        declarations[path.relative_to(root).as_posix()] = _record(root, path, kind)
    result['files'] = [_record(root, root / name, entry['kind'])
                       for name, entry in sorted(declarations.items())]
    _write(complete, result)
    return result


def _import_receipt(path, workspace, folder):
    """Keep local trees in place; copy external accepted trees preserving relative links."""
    path = _safe(path)
    root = path.parent
    data = _read(path)
    entries = _verified(data, root)
    destination = root if root.is_relative_to(workspace) else workspace / folder
    if destination != root:
        destination = _safe(destination)
        identity = {'receipt_sha256': digest(path), 'files': {
            relative: digest(root / relative) for relative in entries}}
        marker = destination / '.import-checkpoint.json'
        if '.import-checkpoint.json' in entries:
            raise ValueError('Reserved import checkpoint filename in dependencies')
        if destination.exists():
            if not marker.is_file() or _read(marker) != identity:
                raise ValueError(f'Input copy collision at {destination}; choose a fresh output workspace')
        else:
            destination.mkdir()
            _write(marker, identity)
        for relative in entries:
            target = _safe(destination / relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if digest(target) != identity['files'][relative]:
                    raise ValueError(f'Changed imported dependency: {relative}')
                continue
            # Never publish a partial dependency under its final name.
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.import-', delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(root / relative, temporary)
                if digest(temporary) != identity['files'][relative]:
                    raise ValueError(f'Source dependency changed during import: {relative}')
                os.link(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
    mapping = {relative: (destination / relative).relative_to(workspace).as_posix()
               for relative in entries}
    for key in ('scratch_takes', 'mix', 'dialogue_stem', 'timeline', 'mouths',
                'scene', 'source', 'preview', 'master'):
        if data.get(key) is not None:
            relative = _safe(root / data[key]).relative_to(root).as_posix()
            if relative not in mapping:
                raise ValueError(f'{key} is not a declared dependency')
            data[key] = mapping[relative]
    data['files'] = [_record(workspace, workspace / mapping[p], f['kind'])
                     for p, f in entries.items()]
    return data


def _destination(output):
    target = _safe(output)
    if target.exists():
        raise ValueError('Output exists; choose a fresh result filename')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target, target.parent


def submit(production, scene, source, preview, rigs, assets, output, catalog=None):
    target, work = _destination(output)
    local = {key: _safe(value) for key, value in
             dict(scene=scene, source=source, preview=preview, rigs=rigs, assets=assets).items()}
    for path in local.values():
        contained(work, path.relative_to(work).as_posix())
        if path == target:
            raise ValueError('Output cannot also be an input')
    rig_map, used = _read(local['rigs']), _read(local['assets'])
    if not isinstance(rig_map, dict) or any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
            for k, v in rig_map.items()):
        raise ValueError('rigs.json needs a speaker-to-armature mapping')
    ids = used.get('used_asset_ids') if isinstance(used, dict) else used
    if not isinstance(ids, list) or any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('used_asset_ids must be unique nonempty catalog ID strings')
    if catalog is not None:
        known = {entry['id'] for entry in _read(_safe(catalog))}
        unknown = sorted(set(ids) - known)
        if unknown:
            raise ValueError(f'Unknown active asset IDs: {unknown}. Copy exact IDs from {catalog}; '
                             'fix the asset list and resubmit, without rerendering the film.')
    if local['scene'].suffix.lower() != '.blend':
        raise ValueError('scene must be a .blend file')
    result = _import_receipt(production, work, target.stem + '-audio-inputs')
    if not {c['speaker'] for c in result['direction']['cast']}.issubset(rig_map):
        raise ValueError('rigs.json must include every cast speaker, including listeners')
    result.update(rigs=rig_map, used_asset_ids=ids)
    for key in ('scene', 'source', 'preview'):
        result[key] = local[key].relative_to(work).as_posix()
    files = {f['path']: f for f in result['files']}
    for key, path in local.items():
        record = _record(work, path, key)
        files[record['path']] = record
    result['files'] = list(files.values())
    validate('animate', result, work, {})
    _write(target, result)
    return result


def edit(accepted, plan_path, config_path, output):
    plan, config = _read(plan_path), _read(config_path)
    review = plan.get('review')
    if (not isinstance(review, dict) or review.get('verdict') != 'pass' or
            not isinstance(review.get('findings'), list) or not isinstance(review.get('summary'), str)
            or not review['summary'].strip()):
        raise ValueError('Caller plan must include review:{verdict:pass,findings:[...],summary}; no approval inferred')
    # Validate before expensive media work; no approval is inferred by this helper.
    validate('creative_qa', {**review, 'files': []}, Path(output).absolute().parent,
             {'strict_review': True})
    target = _safe(output)
    work = target.parent
    accepted = _safe(accepted)
    original = _read(accepted)
    entries = _verified(original, accepted.parent)
    identity = {'plan': plan, 'config': config, 'accepted_sha256': digest(accepted),
                'dependencies': {p: digest(accepted.parent / p) for p in entries}}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
    work.mkdir(parents=True, exist_ok=True)
    state = _safe(work / (target.stem + '-edit-work'))
    checkpoint = state / 'checkpoint.json'
    version = ''
    if checkpoint.is_file() and _read(checkpoint) != {'input_sha256': fingerprint}:
        if target.exists() and _read(target).get('input_sha256') != fingerprint:
            raise ValueError('Editor input collision: archive the previous result before submitting a new revision')
        # A new controller revision deliberately changes its accepted source/plan.
        # Preserve the old media and continue into an independently owned version.
        version = '-' + fingerprint
        state = _safe(work / (target.stem + '-edit-work' + version))
        checkpoint = state / 'checkpoint.json'
    if state.exists():
        if not checkpoint.is_file() or _read(checkpoint) != {'input_sha256': fingerprint}:
            raise ValueError('Editor input collision; choose a fresh result filename for changed inputs')
    else:
        if target.exists():
            raise ValueError('Output exists without an owned checkpoint; choose a fresh result filename')
        state.mkdir()
        _write(checkpoint, {'input_sha256': fingerprint})
    if target.exists():
        result = _read(target)
        if result.get('input_sha256') != fingerprint or result.get('plan') != plan:
            raise ValueError('Editor result checkpoint mismatch')
        _verified(result, work)
        validate('creative_qa', result, work, {'strict_review': True})
        validate('edit', result, work, {'compact': True, 'strict_review': True})
        return result
    inputs = _import_receipt(accepted, work, target.stem + '-animate-inputs' + version)
    completed = sorted(state.glob('attempt-*/complete.json'))
    if completed:
        result = _read(completed[-1])
        if result.get('input_sha256') != fingerprint or result.get('plan') != plan:
            raise ValueError('Completed edit checkpoint mismatch')
        _verified(result, work)
    else:
        index = 0
        while (state / f'attempt-{index:04d}').exists():
            index += 1
        attempt = state / f'attempt-{index:04d}'
        attempt.mkdir()
        master, timeline = attempt / 'master.mp4', attempt / 'timeline.json'
        editing.assemble(work / inputs['preview'], work / inputs['mix'], plan,
                         _read(work / inputs['timeline']), config, inputs['direction'], master, timeline)
        result = {'summary': review['summary'], 'review': review, 'verdict': 'pass',
                  'findings': review['findings'], 'plan': plan, 'input_sha256': fingerprint,
                  'master': master.relative_to(work).as_posix(),
                  'timeline': timeline.relative_to(work).as_posix(),
                  'files': [_record(work, master, 'video'), _record(work, timeline, 'timeline')]}
        validate('edit', result, work, {'compact': True, 'strict_review': True})
        _write(attempt / 'complete.json', result)
    validate('creative_qa', result, work, {'strict_review': True})
    validate('edit', result, work, {'compact': True, 'strict_review': True})
    _write(target, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    a = commands.add_parser('audio')
    a.add_argument('plan'); a.add_argument('--config', required=True); a.add_argument('--output', required=True)
    a.add_argument('--cache-dir', help='Shared caller-owned voice cache (default: OUTPUT/voice-cache)')
    s = commands.add_parser('submit')
    s.add_argument('production')
    for key in ('scene', 'source', 'preview', 'rigs', 'assets', 'output'):
        s.add_argument('--' + key, required=True)
    s.add_argument('--catalog', help='Validate used IDs against this run\'s active-assets.json before submission')
    e = commands.add_parser('edit')
    e.add_argument('accepted')
    for key in ('plan', 'config', 'output'):
        e.add_argument('--' + key, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop('command')
    try:
        # Provider initialization chatter must not corrupt the JSON CLI receipt.
        with redirect_stdout(sys.stderr):
            if command == 'audio':
                result = audio(args['plan'], args['config'], args['output'], args['cache_dir'])
            elif command == 'submit':
                result = submit(**args)
            else:
                result = edit(args['accepted'], args['plan'], args['config'], args['output'])
        print(json.dumps(result, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Production {command} failed: {exc}\n')


if __name__ == '__main__':
    main()
