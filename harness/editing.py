"""Deterministic cut lists: keep picture/audio aligned and rebase speech QA after edits.

The editor decides which frames matter. This module only enforces valid trims,
protects spoken words and produces a truthful edited dialogue timeline.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess

from .contracts import ContractError

EPS = 0.025


def _seconds(obj, name):
    v = obj.get(name)
    if type(v) not in (float, int) or not math.isfinite(v):
        raise ContractError(f'edit segment {name} must be finite seconds')
    return float(v)


def validate_plan(plan, source, config, direction=None):
    """Reject out-of-order cuts, clipped syllables, missing CTA windows and hidden removals."""
    if not isinstance(plan, dict):
        raise ContractError('edit_plan.plan must be an object')
    segments = plan.get('segments')
    if not isinstance(segments, list) or not segments:
        raise ContractError('editor must choose one or more source segments')
    if not isinstance(plan.get('sound_plan'), str) or not plan['sound_plan'].strip():
        raise ContractError('editor must explain the intended mix and sound design')
    source_duration = float(source['duration'])
    spans = []
    previous = 0.0
    for i, s in enumerate(segments):
        if not isinstance(s, dict) or not isinstance(s.get('reason'), str) or not s['reason'].strip():
            raise ContractError(f'edit segment {i} needs a reason to exist')
        a, b = _seconds(s, 'start'), _seconds(s, 'end')
        if a < -EPS or b <= a or b > source_duration + EPS:
            raise ContractError(f'edit segment {i} is outside source duration')
        if i and a < previous - EPS:
            raise ContractError('edit segments must follow source order without overlap')
        spans.append((a, b))
        previous = b
    total = sum(b - a for a, b in spans)
    out = config['output']
    if not out['min_seconds'] - EPS <= total <= out['max_seconds'] + EPS:
        raise ContractError(f'editor cut is {total:.2f}s, outside output duration limits')
    if out.get('cta') and out.get('frame') == 'end_card' and direction and direction.get('end_card'):
        card_at = float(direction['duration']) - float(direction['end_card']['seconds'])
        if abs(spans[-1][0] - card_at) > EPS or abs(spans[-1][1] - source_duration) > EPS:
            raise ContractError('the full end-card hero segment must be the final edit segment')
        if any(end > card_at + EPS for _, end in spans[:-1]):
            raise ContractError('only the final segment may contain the end-card hero')
    removed = plan.get('removed_lines', [])
    if not isinstance(removed, list):
        raise ContractError('removed_lines must be an array, even when empty')
    reasons = {}
    for r in removed:
        if (not isinstance(r, dict) or type(r.get('index')) is not int or
                not isinstance(r.get('reason'), str) or not r['reason'].strip()):
            raise ContractError('removed_lines requires index and editorial reason')
        if r['index'] in reasons:
            raise ContractError('same line listed as removed twice')
        reasons[r['index']] = r['reason']
    dialogue = source.get('dialogue', [])
    if set(reasons) - set(range(len(dialogue))):
        raise ContractError('removed_lines index out of range')
    rate = source['sample_rate']
    for i, line in enumerate(dialogue):
        a, b = line['start_sample'] / rate, line['end_sample'] / rate
        coverage = sum(max(0., min(b, hi) - max(a, lo)) for lo, hi in spans)
        if EPS < coverage < b - a - EPS:
            raise ContractError(f'cut bisects spoken line {i}; keep the full take or remove it')
        absent = coverage <= EPS
        if not absent and not any(a >= lo - 0.001 and b <= hi + 0.001 for lo, hi in spans):
            raise ContractError(f'cut splits spoken line {i} between clips; keep its take intact')
        if absent and i not in reasons:
            raise ContractError(f'edit silently removes line {i}; declare and justify removal')
        if not absent and i in reasons:
            raise ContractError(f'line {i} remains in the video but is marked removed')
    return {'duration': total, 'cuts': len(spans), 'removed_lines': sorted(reasons)}


def retime_timeline(source, plan):
    """Shift measured dialogue and effect sample positions by the cuts, not by estimates."""
    rate = source['sample_rate']
    spans = [(round(s['start'] * rate), round(s['end'] * rate)) for s in plan['segments']]
    removed = {r['index'] for r in plan.get('removed_lines', [])}
    offsets, total = [], 0
    for start, end in spans:
        offsets.append(total)
        total += end - start
    dialogue = []
    for index, line in enumerate(source.get('dialogue', [])):
        if index in removed:
            continue
        a, b = line['start_sample'], line['end_sample']
        for (start, end), offset in zip(spans, offsets):
            if a >= start and b <= end:
                dialogue.append({**line, 'start_sample': offset + a - start,
                                 'end_sample': offset + b - start})
                break
        else:
            raise ContractError(f'retained spoken line {index} is not wholly within one cut')
    events = []
    for event in source.get('events', []):
        for (start, end), offset in zip(spans, offsets):
            if start <= event['sample'] < end:
                events.append({**event, 'sample': offset + event['sample'] - start})
                break
    return {**source, 'duration': total / rate, 'dialogue': dialogue, 'events': events}


def validate_conformance(path, plan, source, config, direction, video_duration):
    """Verify the editor delivered the approved timeline, not a stale pre-trim transcript."""
    validated = validate_plan(plan, source, config, direction)
    expected = retime_timeline(source, plan)
    try:
        actual = json.loads(Path(path).read_text())
        good = (actual.get('fps') == expected['fps'] and
                actual.get('sample_rate') == expected['sample_rate'] and
                actual.get('dialogue') == expected['dialogue'] and
                actual.get('events') == expected['events'] and
                abs(float(actual.get('duration', -1)) - expected['duration']) < EPS)
    except (OSError, ValueError, TypeError):
        good = False
    if not good:
        raise ContractError('edited transcript/timestamps do not match cut list')
    frame_tolerance = max(.12, len(plan['segments']) / config['output']['fps'])
    if abs(video_duration - validated['duration']) > frame_tolerance:
        raise ContractError('encoded edit duration differs from approved cut list')
    return validated


def assemble(video, audio, plan, source, config, direction, output, output_timeline):
    """Cut high-res animation and original mixed audio on the same edit decision list."""
    validated = validate_plan(plan, source, config, direction)
    fps = config['output']['fps']
    chains = []
    for i, part in enumerate(plan['segments']):
        a, b = part['start'], part['end']
        chains.append(f'[0:v]trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS,'
                      f'fps={fps},format=yuv420p[v{i}]')
        chains.append(f'[1:a]atrim=start={a:.6f}:end={b:.6f},asetpts=PTS-STARTPTS,'
                      f'aresample=48000[a{i}]')
    inputs = ''.join(f'[v{i}][a{i}]' for i in range(len(plan['segments'])))
    chains.append(f'{inputs}concat=n={len(plan["segments"])}:v=1:a=1[v][a]')
    command = [config['tools']['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-y',
               '-i', str(video), '-i', str(audio), '-filter_complex', ';'.join(chains),
               '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '17',
               '-preset', 'medium', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
               '-ar', '48000', '-movflags', '+faststart', str(output)]
    subprocess.run(command, check=True)
    Path(output_timeline).write_text(json.dumps(retime_timeline(source, plan), indent=2))
    return validated


def main():
    parser = argparse.ArgumentParser(description='Trim video+audio and rebase QA timestamps')
    for name in ('video', 'audio', 'plan', 'timeline', 'config', 'direction', 'output', 'output-timeline'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    read = lambda path: json.loads(Path(path).read_text())
    print(assemble(args.video, args.audio, read(args.plan), read(args.timeline),
                   read(args.config), read(args.direction), args.output, args.output_timeline))


if __name__ == '__main__':
    main()
