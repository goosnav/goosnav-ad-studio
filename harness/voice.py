"""Measured local voice auditions and verified reuse: python -m harness.voice REQUEST OUTPUTDIR.

REQUEST is a JSON path (or '-' for stdin). See dev/WORKER_GUIDE.md for the schema.
The default selection is provisional; listening and caller selection accept a take.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import wave

from . import audio


CONTROLS = {'voice', 'speed', 'seed', 'threads', 'device', 'model', 'revision',
            'language', 'reference', 'exaggeration', 'cfg', 'phrasing', 'pauses',
            'polish', 'local_files_only'}
VARIATIONS = {'speed', 'seed', 'exaggeration', 'cfg', 'phrasing', 'pauses', 'delivery'}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value


def _normalize(request):
    if not isinstance(request, dict):
        raise ValueError('Voice request must be an object')
    unknown = set(request) - CONTROLS - {'provider', 'lines', 'voice_profiles', 'cache_dir', 'effort', 'fast'}
    if unknown:
        raise ValueError(f'Unknown batch settings: {sorted(unknown)}')
    effort = request.get('effort', 'medium')
    if effort not in ('low', 'medium', 'high') or type(request.get('fast', False)) is not bool:
        raise ValueError('effort must be low/medium/high; fast must be boolean')
    cap = 1 if request.get('fast') else {'low': 1, 'medium': 2, 'high': 3}[effort]
    provider = request.get('provider', 'kokoro')
    if provider not in ('kokoro', 'chatterbox'):
        raise ValueError('Voice provider must be kokoro or chatterbox; no automatic fallback')
    lines = request.get('lines')
    if not isinstance(lines, list) or not lines:
        raise ValueError('lines must be a nonempty array')
    profiles = request.get('voice_profiles', {})
    if not isinstance(profiles, dict):
        raise ValueError('voice_profiles must map speaker IDs to settings')
    for profile in profiles.values():
        if not isinstance(profile, dict) or set(profile) - CONTROLS:
            raise ValueError('Each voice profile must contain only voice generation settings')
    normalized, ids, cast = [], set(), {}
    for i, line in enumerate(lines):
        if not isinstance(line, dict) or set(line) - CONTROLS - {
                'id', 'speaker', 'text', 'delivery', 'auditions', 'defect_retry', 'selected_take'}:
            raise ValueError('Line contains unknown fields or is not an object')
        speaker = _text(line.get('speaker'), 'speaker')
        text = _text(line.get('text'), 'text')
        line_id = _text(line.get('id', f'line-{i+1}'), 'id')
        if line_id in ids:
            raise ValueError(f'Duplicate line id: {line_id}')
        ids.add(line_id)
        profile = profiles.get(speaker, {})
        for key in ('voice', 'reference', 'model', 'language'):
            if key in profile and key in line and profile[key] != line[key]:
                raise ValueError(f'{speaker}: {key} conflicts with voice profile')
        settings = {k: v for k, v in request.items() if k in CONTROLS}
        settings.update(profile)
        settings.update({k: v for k, v in line.items() if k in CONTROLS})
        if 'voice' not in settings:
            raise ValueError(f'{speaker} needs a voice ID or voice_profiles mapping')
        settings.update(provider=provider, text=text)
        reuse = line.get('selected_take') is not None
        settings = audio.voice_settings(settings, require_reference=not reuse)
        character = tuple(settings.get(k) for k in ('voice', 'reference', 'model', 'language'))
        if speaker in cast and cast[speaker] != character:
            raise ValueError(f'{speaker} changes voice within the batch; use a stable voice profile')
        cast[speaker] = character
        delivery = line.get('delivery', '')
        if not isinstance(delivery, str):
            raise ValueError('delivery must be a listening/direction note')
        auditions = line.get('auditions', [{}])
        if not isinstance(auditions, list) or not auditions:
            raise ValueError('auditions must be a nonempty array of control overrides')
        variants = []
        for variant in auditions:
            if not isinstance(variant, dict) or set(variant) - VARIATIONS:
                raise ValueError('Auditions may vary speed, seed, phrasing, pauses, exaggeration, cfg or delivery')
            note = variant.get('delivery', delivery)
            if not isinstance(note, str):
                raise ValueError('audition delivery must be a string')
            candidate = {**settings, **{k: v for k, v in variant.items() if k != 'delivery'}}
            variants.append((audio.voice_settings(candidate, require_reference=not reuse), note))
        retry = line.get('defect_retry')
        if retry is not None:
            if not isinstance(retry, dict) or set(retry) != {'reason', 'settings'}:
                raise ValueError('defect_retry requires reason and settings')
            _text(retry['reason'], 'defect_retry.reason')
            changes = retry['settings']
            if not isinstance(changes, dict) or not changes or set(changes) - (VARIATIONS - {'delivery'}):
                raise ValueError('defect_retry needs targeted synthesis control changes')
            for variant, _ in variants[:cap]:
                repaired = audio.voice_settings({**variant, **changes})
                if repaired == variant:
                    raise ValueError('defect_retry must change synthesis settings')
        selected = line.get('selected_take')
        if selected is not None:
            if (not isinstance(selected, dict) or set(selected) - {'manifest', 'line_id', 'take_id'} or
                    'manifest' not in selected):
                raise ValueError('selected_take requires manifest, optional line_id and take_id')
            _text(selected['manifest'], 'selected_take.manifest')
            if 'auditions' in line or retry is not None:
                raise ValueError('selected_take cannot also request auditions or a defect retry')
        normalized.append({'id': line_id, 'speaker': speaker, 'text': text, 'voice': settings['voice'],
                           'delivery': delivery, 'settings': settings, 'variants': variants[:cap],
                           'retry': retry, 'selected': selected, 'explicit': line})
    return normalized, cap


def _safe_path(base, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('Take files must use relative paths')
    base = Path(base).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError('Take path escapes its manifest directory')
    return path


def _file_record(path, relative):
    return {'path': relative, 'sha256': audio.sha256(path), **audio.measure_wav(path)}


def _technical_check(measurement):
    if measurement['sample_rate'] != 48000:
        raise audio.AudioDefect('sample_rate')
    if not measurement['frames']:
        raise audio.AudioDefect('empty')
    if measurement['peak'] < 1e-4 or measurement['active_start_sample'] is None:
        raise audio.AudioDefect('silent')
    if measurement['clipped_samples']:
        raise audio.AudioDefect('clipped')


def verify_take(take, base):
    """Verify recipe, both SHA-256s and measurements. Never trust stored durations."""
    try:
        if take['id'] != _digest(take['recipe']) or take['settings'] != take['recipe']['settings']:
            raise ValueError('Take identity/settings do not match its recipe')
        for kind in ('raw', 'polished'):
            record = take[kind]
            path = _safe_path(base, record['path'])
            if audio.sha256(path) != record['sha256']:
                raise ValueError(f'{kind} take hash mismatch')
            measured = audio.measure_wav(path)
            if any(record.get(k) != v for k, v in measured.items()):
                raise ValueError(f'{kind} take measurements mismatch')
            _technical_check(measured)
        return take
    except (OSError, KeyError, TypeError, wave.Error, EOFError) as exc:
        raise ValueError(f'Invalid or missing take artifact: {exc}') from exc


def _portable_settings(settings, identity):
    # Acquisition policy and symbolic refs are not generation controls. Actual bytes
    # and immutable revisions live in identity. Reference paths must not key voices.
    portable = {k: v for k, v in settings.items() if k not in ('reference', 'revision', 'local_files_only')}
    if settings.get('reference'):
        portable['reference_sha256'] = identity['reference_sha256']
    return portable


def _cached_take(settings, cache, session, processing):
    identity = session.identity(settings)
    if (not isinstance(identity, dict) or not identity.get('files') or
            not re.fullmatch(r'[0-9a-f]{40,64}', identity.get('resolved_revision', ''))):
        raise ValueError('Cache requires resolved immutable model identity and file hashes')
    portable = _portable_settings(settings, identity)
    recipe = {'schema': 1, 'settings': portable, 'identity': identity, 'processing': processing}
    key = _digest(recipe)
    destination = cache / key
    if destination.exists():
        try:
            take = json.loads((destination / 'take.json').read_text())
            if take['id'] != key:
                raise ValueError('Wrong cache entry')
            return verify_take(take, destination), destination, True
        except (ValueError, OSError, KeyError, TypeError):
            # Preserve corrupt evidence; never delete or overwrite accepted artifacts.
            try:
                destination.rename(cache / f'{key}.corrupt-{uuid.uuid4().hex}')
            except FileNotFoundError:
                pass  # Another process has already quarantined it.
    with tempfile.TemporaryDirectory(prefix='.voice-', dir=cache) as temporary:
        stage = Path(temporary)
        generated = session.synthesize(settings, stage / 'raw.wav')
        if generated.get('identity', identity) != identity:
            raise ValueError('Model identity changed during synthesis; take was not cached')
        _technical_check(audio.measure_wav(stage / 'raw.wav'))
        if settings['polish']:
            audio.polish(stage / 'raw.wav', stage / 'polished.wav')
        else:
            shutil.copyfile(stage / 'raw.wav', stage / 'polished.wav')
        take = {'id': key, 'recipe': recipe, 'settings': portable,
                'raw': _file_record(stage / 'raw.wav', 'raw.wav'),
                'polished': _file_record(stage / 'polished.wav', 'polished.wav'),
                'generation_wall_seconds': generated.get('wall_seconds')}
        verify_take(take, stage)
        (stage / 'take.json').write_text(json.dumps(take, indent=2, allow_nan=False))
        try:
            stage.rename(destination)  # Atomic directory publication, safe for concurrent readers.
        except OSError:
            if not destination.is_dir():
                raise
            winner = json.loads((destination / 'take.json').read_text())
            if winner['id'] != key:
                raise ValueError('Concurrent cache entry has wrong identity')
            return verify_take(winner, destination), destination, True
    return take, destination, False


def _copy_take(take, base, output, reused, delivery):
    verify_take(take, base)
    copied = deepcopy(take)
    for kind in ('raw', 'polished'):
        # Include content hash: stochastic generations of the same recipe cannot
        # overwrite a take already selected into this output directory.
        relative = f'takes/{take["id"]}/{kind}-{take[kind]["sha256"]}.wav'
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if audio.sha256(target) != take[kind]['sha256']:
                raise ValueError(f'Existing output artifact is corrupt: {target}')
        else:
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.wav', delete=False) as stream:
                temporary = Path(stream.name)
            try:
                shutil.copyfile(_safe_path(base, take[kind]['path']), temporary)
                if audio.sha256(temporary) != take[kind]['sha256']:
                    raise ValueError('Take changed while being copied')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        copied[kind]['path'] = relative
    copied.update(reused=reused, delivery=delivery)
    return verify_take(copied, output)


def _selected(line):
    selection = line['selected']
    path = Path(selection['manifest'])
    manifest = json.loads(path.read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported selected manifest schema')
    candidates = [entry for entry in manifest['lines'] if entry['id'] == selection.get('line_id', line['id'])]
    if len(candidates) != 1:
        raise ValueError('Selected manifest must identify exactly one line')
    source = candidates[0]
    if any(source.get(k) != line[k] for k in ('speaker', 'text', 'voice')):
        raise ValueError('Selected take speaker/text/voice differs from requested line')
    take_id = selection.get('take_id', source['selected_take_id'])
    takes = [take for take in source['takes'] if take['id'] == take_id]
    if len(takes) != 1:
        raise ValueError('Selected take ID is missing or ambiguous')
    take = verify_take(takes[0], path.parent)
    if any(take['settings'].get(k) != line['settings'][k] for k in ('provider', 'text', 'voice')):
        raise ValueError('Selected take synthesis settings differ from the requested line')
    for control in VARIATIONS - {'delivery'}:
        if control in line['explicit'] and take['settings'].get(control) != line['settings'][control]:
            raise ValueError(f'Selected take conflicts with explicit {control}')
    if line['settings'].get('reference'):
        if audio.sha256(line['settings']['reference']) != take['settings'].get('reference_sha256'):
            raise ValueError('Selected take conflicts with the supplied reference audio')
    return take, path.parent


def run_batch(request, output_dir, *, session=None):
    """Return/write manifest.json with measured sequential timing and portable WAVs.

    session may supply identity(settings) and synthesize(settings, raw_wav); the
    default is one reusable AudioSession. No ASR or emotional scoring is performed.
    """
    lines, cap = _normalize(request)  # Validate the entire batch before synthesis.
    output = Path(output_dir).resolve()
    if (output / 'manifest.json').exists():
        raise ValueError('Output already has a manifest; choose a new output directory to preserve accepted takes')
    output.mkdir(parents=True, exist_ok=True)
    cache = Path(request.get('cache_dir', output / '.voice-cache')).resolve()
    session = session or audio.AudioSession()
    processing = None
    result = {'schema': 1, 'sample_rate': 48000, 'audition_cap': cap, 'defect_retry_cap': 1,
              'quality': {'emotional_quality': 'not_assessed', 'asr': 'not_run',
                          'selection': 'First technically usable take is provisional; listen and select explicitly.'},
              'lines': []}
    cursor = 0
    for line in lines:
        takes, attempts = [], []
        if line['selected'] is not None:
            take, base = _selected(line)
            takes.append(_copy_take(take, base, output, True, line['delivery'] or take.get('delivery', '')))
            acceptance = 'caller_selected'
        else:
            if processing is None:
                processing = {'adapter_sha256': audio.sha256(Path(audio.__file__)),
                              'voice_sha256': audio.sha256(Path(__file__)),
                              'voice_schema': 1, 'chain': audio.VOICE_CHAIN,
                              'ffmpeg': subprocess.run(['ffmpeg', '-version'], capture_output=True,
                                                       text=True, check=True).stdout}
                cache.mkdir(parents=True, exist_ok=True)
            retry_used = False
            for settings, delivery in line['variants']:
                kind = 'audition'
                while True:
                    started = time.monotonic()
                    attempt = {'kind': kind, 'speed': settings['speed'], 'seed': settings['seed']}
                    if kind == 'defect_retry':
                        attempt['reason'] = line['retry']['reason']
                    attempts.append(attempt)
                    try:
                        take, base, reused = _cached_take(settings, cache, session, processing)
                    except audio.AudioDefect as exc:
                        attempt.update(defect=str(exc), wall_seconds=round(time.monotonic() - started, 3))
                        if line['retry'] and not retry_used:
                            retry_used = True
                            settings = audio.voice_settings({**settings, **line['retry']['settings']})
                            kind = 'defect_retry'
                            continue
                        break
                    attempt.update(take_id=take['id'], reused=reused,
                                   wall_seconds=round(time.monotonic() - started, 3))
                    if not any(existing['id'] == take['id'] for existing in takes):
                        takes.append(_copy_take(take, base, output, reused, delivery))
                    break
            if not takes:
                raise ValueError(f'{line["id"]}: no usable take after bounded auditions/retry: {attempts}')
            acceptance = 'provisional_requires_listening'
        selected = takes[0]
        measured = selected['polished']
        entry = {k: line[k] for k in ('id', 'speaker', 'text', 'voice', 'delivery')}
        entry.update(takes=takes, attempts=attempts, selected_take_id=selected['id'], acceptance=acceptance,
                     duration=measured['duration'], start_sample=cursor, end_sample=cursor + measured['frames'],
                     active_start_sample=cursor + measured['active_start_sample'],
                     active_end_sample=cursor + measured['active_end_sample'])
        cursor = entry['end_sample']
        result['lines'].append(entry)
    result.update(frames=cursor, duration=cursor / 48000)
    # An exclusive final write also prevents concurrent jobs from replacing a manifest.
    with (output / 'manifest.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


def summarize(result, output_dir):
    """Small stdout receipt; active bounds are local to each selected WAV."""
    root = Path(output_dir).resolve()
    lines = []
    for line in result['lines']:
        take = next(t for t in line['takes'] if t['id'] == line['selected_take_id'])
        entry = {key: line[key] for key in ('id', 'speaker', 'text', 'voice', 'selected_take_id', 'duration')}
        entry.update({key: take['polished'][key]
                      for key in ('frames', 'active_start_sample', 'active_end_sample')})
        entry.update({kind: str(root / take[kind]['path']) for kind in ('raw', 'polished')})
        lines.append(entry)
    return {'manifest': str(root / 'manifest.json'), 'duration': result['duration'],
            'sample_rate': result['sample_rate'], 'frames': result['frames'], 'lines': lines}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', help='JSON request path or - for stdin')
    parser.add_argument('output_dir')
    parser.add_argument('--summary', action='store_true',
                        help='Print compact selected-take receipt; full manifest stays on disk')
    args = parser.parse_args()
    try:
        request = json.loads(sys.stdin.read() if args.request == '-' else Path(args.request).read_text())
        # Provider libraries sometimes print initialization messages; stdout stays JSON.
        from contextlib import redirect_stdout
        with redirect_stdout(sys.stderr):
            result = run_batch(request, args.output_dir)
        print(json.dumps(summarize(result, args.output_dir) if args.summary else result,
                         indent=None if args.summary else 2, allow_nan=False))
    except Exception as exc:
        parser.exit(1, f'Voice batch failed ({type(exc).__name__}): {exc}\nNo voice fallback was substituted.\n')


if __name__ == '__main__':
    main()
