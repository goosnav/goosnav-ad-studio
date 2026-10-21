"""Deterministic accepted-take assembly; no synthesis, ASR, or speech time warping.

python -m harness.mix DIRECT_RESULT OUTPUTDIR --no-bed [--fps 24]
python -m harness.mix DIRECT_RESULT OUTPUTDIR --bed BED.wav --bed-gain-db -30
python -m harness.mix --request PREVIOUS_OUTPUT/request.json OUTPUTDIR
"""
import argparse
import array
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

from .audio import sha256
from .voice import verify_take
from .direction import SPEECH_FLOOR_DB, speech_levels

RATE = 48000
DIALOGUE_TARGET_DB = -21.0
MAX_DIALOGUE_GAIN_DB = 18.0


def _path(root, value):
    """Promoted absolute paths or portable relative paths, never escapes/symlinks."""
    if not isinstance(value, str) or not value or '..' in Path(value).parts:
        raise ValueError('Unsafe artifact path')
    path = Path(value) if Path(value).is_absolute() else root / value
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Symlink artifact paths are not accepted')
    path = path.resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Artifact is missing or escapes the accepted directory')
    return path


def _number(value, name, low, high):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError(f'{name} must be finite and within {low}..{high}')
    return value


def _json(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def _read_pcm(path):
    with wave.open(str(path), 'rb') as stream:
        channels, rate, frames = stream.getnchannels(), stream.getframerate(), stream.getnframes()
        if stream.getsampwidth() != 2 or channels not in (1, 2) or stream.getcomptype() != 'NONE':
            raise ValueError('Inputs must be uncompressed mono/stereo PCM16 WAV')
        pcm = array.array('h', stream.readframes(frames))
    if len(pcm) != frames * channels:
        raise ValueError('Truncated PCM WAV')
    if sys.byteorder != 'little':
        pcm.byteswap()
    return rate, channels, pcm


def _wav(path, samples):
    pcm = array.array('h', samples)
    if sys.byteorder != 'little':
        pcm.byteswap()
    with path.open('xb') as file:
        with wave.open(file, 'wb') as stream:
            stream.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
            stream.writeframes(pcm.tobytes())


def _speech_levels(stereo, dialogue):
    mono = array.array('d', ((stereo[i] + stereo[i + 1]) / 2 for i in range(0, len(stereo), 2)))
    return speech_levels(mono, RATE, dialogue)


def _words(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Spoken text must be nonempty')
    return ' '.join(value.split())


def _load(direct):
    data = json.loads(direct.read_text())
    direction = data.get('direction')
    if not isinstance(direction, dict) or not isinstance(direction.get('lines'), list):
        raise ValueError('Direct result needs direction.lines')
    duration = _number(direction.get('duration'), 'duration', 1 / RATE, 300)
    declared = {}
    for entry in data.get('files', []):
        path = _path(direct.parent, entry['path'])
        if path in declared:
            raise ValueError('Duplicate declared artifact')
        if 'sha256' in entry and sha256(path) != entry['sha256']:
            raise ValueError('Declared artifact hash mismatch')
        if 'bytes' in entry and path.stat().st_size != entry['bytes']:
            raise ValueError('Declared artifact size mismatch')
        declared[path] = entry
    if not direction['lines']:
        return data, None, None, [], round(duration * RATE)
    manifest_path = _path(direct.parent, data.get('scratch_takes'))
    if manifest_path not in declared:
        raise ValueError('scratch_takes manifest must be declared')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema') != 1 or manifest.get('sample_rate') != RATE:
        raise ValueError('Expected harness.voice schema 1 at 48000 Hz')
    entries = manifest.get('lines', [])
    if len({e['id'] for e in entries}) != len(entries):
        raise ValueError('Duplicate scratch line IDs')
    cast = {}
    for character in direction.get('cast', []):
        if character['speaker'] in cast:
            raise ValueError('Duplicate cast speaker')
        cast[character['speaker']] = character['voice']
    used, selected = set(), []
    for plan in direction['lines']:
        speaker, text = plan['speaker'], _words(plan['text'])
        voice = cast.get(speaker)
        if not voice or ('voice' in plan and plan['voice'] != voice):
            raise ValueError('Line voice must match the stable cast mapping')
        candidates = [(i, e) for i, e in enumerate(entries) if i not in used
                      and e['speaker'] == speaker and _words(e['text']) == text and e['voice'] == voice
                      and ('id' not in plan or e['id'] == plan['id'])]
        if not candidates:
            raise ValueError('No unused scratch line matches direction id/speaker/text/voice')
        index, entry = candidates[0]
        used.add(index)
        takes = [t for t in entry['takes'] if t['id'] == entry['selected_take_id']]
        if len(takes) != 1:
            raise ValueError('Each line must select exactly one take')
        take = takes[0]
        if _words(take['settings']['text']) != text or take['settings']['voice'] != voice:
            raise ValueError('Selected take settings differ from directed text/voice')
        for kind in ('raw', 'polished'):
            if Path(take[kind]['path']).is_absolute():
                raise ValueError('Take paths must be portable relative paths')
            path = _path(manifest_path.parent, take[kind]['path'])
            if path not in declared:
                raise ValueError('Both selected raw and polished WAVs must be declared')
        verify_take(take, manifest_path.parent)
        start = round(_number(plan.get('start'), 'line start', 0, duration) * RATE)
        end = round(_number(plan.get('end'), 'line end', 0, duration) * RATE)
        if end <= start:
            raise ValueError('Line needs a positive planned slot')
        selected.append((plan, entry, take, start, end))
    return data, manifest_path, manifest, selected, round(duration * RATE)


def _fit(pcm, channels, slot):
    frames = len(pcm) // channels
    excess = max(0, frames - slot)
    trailing = 0
    while trailing < excess and not any(pcm[(frames - trailing - 1) * channels:(frames - trailing) * channels]):
        trailing += 1
    leading = 0
    while leading < excess - trailing and not any(pcm[leading * channels:(leading + 1) * channels]):
        leading += 1
    if leading + trailing < excess:
        raise ValueError('Active speech cannot fit planned slot; extend direction, never stretch/cut speech')
    return pcm[leading * channels:(frames - trailing) * channels], leading, trailing


def _bed(path, frames):
    with wave.open(str(path), 'rb') as stream:
        channels = stream.getnchannels()
        if stream.getsampwidth() != 2 or channels not in (1, 2) or stream.getcomptype() != 'NONE':
            raise ValueError('Bed must be mono/stereo PCM16 WAV')
    # Ordinary resampling of the BED only; dialogue is never passed through FFmpeg.
    pan = 'pan=stereo|c0=c0|c1=c0,' if channels == 1 else ''
    result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-threads', '1',
                             '-i', str(path), '-map', '0:a:0', '-af',
                             f'{pan}aresample=48000,apad=whole_len={frames},atrim=end_sample={frames}',
                             '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s16le', '-f', 's16le', 'pipe:1'],
                            capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError('Bed conversion failed: ' + result.stderr.decode(errors='replace')[-1000:])
    pcm = array.array('h', result.stdout)
    if sys.byteorder != 'little':
        pcm.byteswap()
    if len(pcm) != frames * 2:
        raise ValueError('Converted bed frame count mismatch')
    return pcm


def assemble(direct_result_path, output_dir, *, fps=None, bed=None, bed_gain_db=-30, no_bed=False):
    """Consume an accepted direct result; write a complete, portable audio artifact set.

    Only digital-zero edge samples can be trimmed, trailing first and only as
    necessary. Any signal that cannot fit fails closed. No emotional/ASR verdict.
    Uniform dialogue boost targets -21 dBFS with the controller's loud-half
    metric, capped at +18 dB. Unsafe/unachievable floors leave audit.json only.
    Output directory must be absent/empty; result.json is written last.
    """
    if type(no_bed) is not bool or (bed is None) != no_bed:
        raise ValueError('Choose exactly one: supplied bed WAV or explicit no_bed=True')
    _number(bed_gain_db, 'bed gain dB', -120, -12)
    direct_input = Path(direct_result_path).absolute()
    direct = _path(direct_input.parent, str(direct_input))
    output = Path(output_dir).absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Output must not use symlinks')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('Output directory must be empty; existing artifacts are never overwritten')
    data, manifest_path, manifest, selected, frames = _load(direct)
    fps = _number(fps if fps is not None else data['direction'].get('fps', 24), 'fps', 1, 120)
    # Wide accumulator preserves overlapping voices without integer clipping.
    dialogue = array.array('i', [0]) * (frames * 2)
    timeline_lines, audit_lines = [], []
    for plan, entry, take, start, end in selected:
        rate, channels, pcm = _read_pcm(_path(manifest_path.parent, take['polished']['path']))
        if rate != RATE:
            raise ValueError('Selected dialogue must already be PCM48k; regeneration/resampling is not allowed')
        fitted, leading, trailing = _fit(pcm, channels, end - start)
        count = len(fitted) // channels
        for i in range(count):
            for channel in range(2):
                dialogue[(start + i) * 2 + channel] += fitted[i * channels + (channel if channels == 2 else 0)]
        line = {key: plan[key] for key in ('speaker', 'text', 'offscreen', 'delivery') if key in plan}
        line.update(voice=entry['voice'], source_line_id=entry['id'], take_id=take['id'],
                    start_sample=start, end_sample=start + count)
        timeline_lines.append(line)
        audit_lines.append({'source_line_id': entry['id'], 'take_id': take['id'],
                            'raw_sha256': take['raw']['sha256'], 'polished_sha256': take['polished']['sha256'],
                            'source_frames': len(pcm) // channels, 'trim_start_samples': leading,
                            'trim_end_samples': trailing, 'start_sample': start, 'end_sample': start + count,
                            'planned_end_sample': end})
    before = _speech_levels(dialogue, timeline_lines)
    requested_gain_db = max(0.0, DIALOGUE_TARGET_DB - min((line['db'] for line in before),
                                                        default=DIALOGUE_TARGET_DB))
    dialogue_gain_db = min(MAX_DIALOGUE_GAIN_DB, requested_gain_db)
    dialogue_gain = 10 ** (dialogue_gain_db / 20)
    dialogue = array.array('d', (sample * dialogue_gain for sample in dialogue))
    bed_path, bed_pcm = None, None
    bed_audit = {'mode': 'none', 'reason': 'Explicit no-bed choice'}
    if bed is not None:
        given = Path(bed).absolute()
        bed_path = _path(given.parent, str(given))
        bed_pcm = _bed(bed_path, frames)
        bed_audit = {'mode': 'supplied', 'sha256': sha256(bed_path), 'gain_db': bed_gain_db, 'looped': False}
    gain = 10 ** (bed_gain_db / 20)
    mixed = array.array('d', (sample + (round(bed_pcm[i] * gain) if bed_pcm is not None else 0)
                             for i, sample in enumerate(dialogue)))
    peak = max(max(map(abs, dialogue), default=0), max(map(abs, mixed), default=0))
    headroom = min(1.0, 32700 / peak) if peak else 1.0
    # Measure the exact final quantized samples, including bed interactions and
    # peak attenuation; a successful pre-gain estimate cannot waive the floor.
    dialogue = array.array('h', (round(x * headroom) for x in dialogue))
    mixed = array.array('h', (round(x * headroom) for x in mixed))
    after_dialogue = _speech_levels(dialogue, timeline_lines)
    after_mix = _speech_levels(mixed, timeline_lines)
    blockers = [{'output': output_name, **line, 'floor_db': SPEECH_FLOOR_DB}
                for output_name, levels in (('dialogue', after_dialogue), ('mix', after_mix))
                for line in levels if line['db'] < SPEECH_FLOOR_DB]
    calibration = {'metric': 'harness.direction.speech_levels', 'target_db': DIALOGUE_TARGET_DB,
                   'floor_db': SPEECH_FLOOR_DB, 'max_gain_db': MAX_DIALOGUE_GAIN_DB,
                   'requested_gain_db': requested_gain_db, 'gain_db': dialogue_gain_db, 'gain': dialogue_gain,
                   'net_gain': dialogue_gain * headroom,
                   'net_gain_db': dialogue_gain_db + 20 * math.log10(headroom),
                   'before': before, 'after_dialogue': after_dialogue, 'after_mix': after_mix,
                   'limited_by': (['gain_cap'] if dialogue_gain_db < requested_gain_db else []) +
                                 (['peak_headroom'] if headroom < 1 else []),
                   'blockers': blockers}
    rationale = ('No bed: explicit caller choice.' if no_bed else 'Caller-supplied WAV bed at quiet gain; never looped.')
    if not selected:
        rationale += ' Intentional silent dialogue stem. ' + str(data['direction'].get('mix', ''))
    timeline = {'sample_rate': RATE, 'channels': 2, 'frames': frames, 'duration': frames / RATE, 'fps': fps,
                'dialogue': timeline_lines, 'events': [], 'sound_rationale': rationale}
    audit = {'schema': 1, 'source_direct_sha256': sha256(direct),
             'source_manifest_sha256': sha256(manifest_path) if manifest_path else None,
             'mixer_sha256': sha256(Path(__file__)), 'lines': audit_lines, 'bed': bed_audit,
             'dialogue_calibration': calibration,
             'uniform_headroom_gain': headroom, 'asr': 'not_run', 'emotional_quality': 'not_assessed',
             'trim_policy': 'Only exact digital-zero edges; trailing first; no internal removal or time warping'}
    output.mkdir(parents=True, exist_ok=True)
    if blockers:
        _json(output / 'audit.json', audit)
        raise ValueError('Dialogue floor cannot be reached safely with bounded uniform gain; '
                         'use a more consistent take. See audit.json for measured blockers')
    inputs = output / 'inputs'; inputs.mkdir()
    snapshot = {'summary': 'Portable selected scratch inputs', 'direction': data['direction'], 'files': []}
    if manifest is not None:
        voice_dir = inputs / 'voice'; voice_dir.mkdir()
        portable_manifest = deepcopy(manifest)
        portable_manifest['lines'] = []
        for _, entry, take, _, _ in selected:
            copied = deepcopy(take)
            for kind in ('raw', 'polished'):
                name = f'{kind}-{take["id"]}.wav'
                destination = voice_dir / name
                if not destination.exists():
                    shutil.copyfile(_path(manifest_path.parent, take[kind]['path']), destination)
                    if sha256(destination) != take[kind]['sha256']:
                        raise ValueError('Input changed during snapshot copy')
                    snapshot['files'].append({'path': 'voice/' + name, 'kind': 'audio', 'sha256': sha256(destination)})
                copied[kind]['path'] = name
            copied_entry = deepcopy(entry)
            copied_entry['takes'] = [copied]
            copied_entry['attempts'] = []
            portable_manifest['lines'].append(copied_entry)
        _json(voice_dir / 'manifest.json', portable_manifest)
        snapshot['scratch_takes'] = 'voice/manifest.json'
        snapshot['files'].append({'path': snapshot['scratch_takes'], 'kind': 'voice_manifest',
                                  'sha256': sha256(voice_dir / 'manifest.json')})
    _json(inputs / 'direct.json', snapshot)
    request = {'schema': 1, 'direct_result': 'inputs/direct.json', 'direct_sha256': sha256(inputs / 'direct.json'),
               'fps': fps, 'no_bed': no_bed, 'bed_gain_db': bed_gain_db}
    if bed_path is not None:
        shutil.copyfile(bed_path, inputs / 'bed.wav')
        if sha256(inputs / 'bed.wav') != bed_audit['sha256']:
            raise ValueError('Bed changed during snapshot copy')
        request.update(bed='inputs/bed.wav', bed_sha256=bed_audit['sha256'])
    _json(output / 'request.json', request)
    _wav(output / 'dialogue.wav', dialogue)
    _wav(output / 'mix.wav', mixed)
    _json(output / 'timeline.json', timeline)
    _json(output / 'audit.json', audit)
    result = {'summary': 'Verified accepted scratch takes assembled without speech stretching or clipping.',
              'mix': 'mix.wav', 'dialogue_stem': 'dialogue.wav', 'timeline': 'timeline.json',
              'source': 'request.json', 'audit': 'audit.json',
              'quality': {'asr': 'not_run', 'emotional_quality': 'not_assessed', 'controller_checks_required': True},
              'files': []}
    for path in sorted(p for p in output.rglob('*') if p.is_file()):
        relative = path.relative_to(output).as_posix()
        kind = 'audio' if path.suffix == '.wav' else ('timeline' if path.name == 'timeline.json' else 'notes')
        result['files'].append({'path': relative, 'kind': kind, 'sha256': sha256(path), 'bytes': path.stat().st_size})
    _json(output / 'result.json', result)
    return result


def replay(request_path, output_dir):
    given = Path(request_path).absolute()
    path = _path(given.parent, str(given))
    request = json.loads(path.read_text())
    if request.get('schema') != 1:
        raise ValueError('Unsupported mix request schema')
    direct = _path(path.parent, request['direct_result'])
    if sha256(direct) != request['direct_sha256']:
        raise ValueError('Replay direct hash mismatch')
    bed = _path(path.parent, request['bed']) if request.get('bed') else None
    if bed is not None and sha256(bed) != request['bed_sha256']:
        raise ValueError('Replay bed hash mismatch')
    return assemble(direct, output_dir, fps=request['fps'], bed=bed,
                    bed_gain_db=request['bed_gain_db'], no_bed=request['no_bed'])


def _stage_target(output_dir, destination):
    output, target = Path(output_dir).absolute(), Path(destination).absolute()
    if any(p.is_symlink() for path in (output, target) for p in (path, *path.parents)):
        raise ValueError('Stage result cannot use symlink paths')
    output, target = output.resolve(), target.resolve()
    if target.parent != output.parent or target == output:
        raise ValueError('Stage result must be a sibling of the output directory')
    if target.exists():
        raise ValueError('Stage result already exists; refusing to overwrite any existing file')
    return output, target


def stage_result(output_dir, destination):
    """Write a new workspace result; remap only declared paths and known references.

    destination must be a sibling of output_dir. Existing workspace files and the
    inner result/request/manifests are never modified. All input hashes rechecked.
    """
    output, target = _stage_target(output_dir, destination)
    result = json.loads(_path(output, 'result.json').read_text())
    from .contracts import validate
    validate('audio', result, output, {})
    mapping = {}
    for entry in result['files']:
        path = _path(output, entry['path'])
        if sha256(path) != entry.get('sha256'):
            raise ValueError('Stage result declared artifact hash mismatch')
        if path.stat().st_size != entry.get('bytes'):
            raise ValueError('Stage result declared artifact size mismatch')
        mapping[entry['path']] = output.name + '/' + entry['path']
    for key in ('mix', 'dialogue_stem', 'timeline', 'source', 'audit'):
        if result.get(key) not in mapping:
            raise ValueError(f'Stage result {key} must reference a declared file')
        result[key] = mapping[result[key]]
    for entry in result['files']:
        entry['path'] = mapping[entry['path']]
    _json(target, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Accepted direct result JSON, or request.json with --request')
    parser.add_argument('output_dir')
    parser.add_argument('--request', action='store_true', help='Replay a portable mix request')
    parser.add_argument('--fps', type=float)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--no-bed', action='store_true')
    choice.add_argument('--bed', help='Caller-supplied PCM16 WAV; never synthesized or looped')
    parser.add_argument('--bed-gain-db', type=float, default=None)
    parser.add_argument('--stage-result', help='Write a new sibling workspace result with prefixed artifact paths')
    args = parser.parse_args()
    try:
        if args.stage_result:
            _stage_target(args.output_dir, args.stage_result)  # Refuse before any generation/output writes.
        if args.request:
            if args.fps is not None or args.no_bed or args.bed or args.bed_gain_db is not None:
                raise ValueError('Replay takes its options from request.json; do not supply overrides')
            result = replay(args.input, args.output_dir)
        else:
            result = assemble(args.input, args.output_dir, fps=args.fps, no_bed=args.no_bed, bed=args.bed,
                              bed_gain_db=args.bed_gain_db if args.bed_gain_db is not None else -30)
        if args.stage_result:
            result = stage_result(args.output_dir, args.stage_result)
        print(json.dumps(result, allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, wave.Error, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Mix failed ({type(exc).__name__}): {exc}\nNo voice was regenerated.\n')


if __name__ == '__main__':
    main()
