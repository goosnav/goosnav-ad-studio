"""Exercise real voice receipts/WAVs/mixing; replace only model synthesis."""
import copy
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

import pytest

from harness import production_tools as production
from harness.contracts import validate
from harness.direction import check_direction, check_scratch_takes


class Tone:
    def __init__(self):
        self.calls = []
        self.fail = None

    def identity(self, settings):
        return {'provider': 'kokoro', 'model': 'fixture', 'resolved_revision': 'a' * 40,
                'files': {'weights': 'b' * 64}}

    def synthesize(self, settings, output):
        if settings['text'] == self.fail:
            raise RuntimeError('interrupted provider')
        self.calls.append(settings['text'])
        with wave.open(str(output), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b''.join(struct.pack('<h', int(4000 * math.sin(i / 20)))
                                    for i in range(24000)))
        return {'wall_seconds': 0}


def write(path, data):
    path.write_text(json.dumps(data))
    return path


def test_receipts_are_exclusive_and_invalid_json_is_never_published(tmp_path):
    path = tmp_path / 'result.json'
    with pytest.raises(ValueError):
        production._write(path, {'duration': float('nan')})
    assert not path.exists()
    production._write(path, {'summary': 'original'})
    with pytest.raises(FileExistsError):
        production._write(path, {'summary': 'replacement'})
    assert json.loads(path.read_text()) == {'summary': 'original'}
    assert list(tmp_path.iterdir()) == [path]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('requires ffmpeg')
    config = {'output': {'fps': 24, 'width': 64, 'height': 80, 'min_seconds': 2,
                         'max_seconds': 8, 'cta': True, 'end_card_seconds': 1,
                         'frame': 'end_card'},
              'audio': {'voice_provider': 'kokoro'}, 'sources': {'characters': []},
              'tools': {'ffmpeg': shutil.which('ffmpeg')}}
    plan = {'summary': 'Caller-authored spoken scene.', 'direction': {
        'duration': 3, 'cast': [{'speaker': 'A', 'character': 'Guy', 'gender': 'male',
                                'voice': 'am_michael', 'performance': 'Plain', 'polish': False}],
        'lines': [{'speaker': 'A', 'text': 'Hello.', 'delivery': 'Plain'},
                  {'speaker': 'A', 'text': 'Yes.', 'delivery': 'Plain'}],
        'end_card': {'seconds': 1, 'title': 'Look', 'picture': 'Real product'},
        'mix': 'Dry dialogue, no bed.'}}
    p, c = write(tmp_path / 'plan.json', plan), write(tmp_path / 'config.json', config)
    session = Tone()
    real_batch = production.voice.run_batch
    requests = []

    def batch(request, output):
        requests.append(copy.deepcopy(request))
        return real_batch(request, output, session=session)

    monkeypatch.setattr(production.voice, 'run_batch', batch)
    return tmp_path, p, c, session, requests


def test_audio_measured_schema_and_reuse(setup):
    work, plan, config, tone, requests = setup
    result = production.audio(plan, config, work / 'audio')
    root = work / 'audio'
    assert json.loads((root / 'production.json').read_text()) == result
    assert len(tone.calls) == 2
    assert requests[0]['fast'] and requests[0]['effort'] == 'low'
    assert all('auditions' not in line for line in requests[0]['lines'])
    assert [(l['start'], l['end']) for l in result['direction']['lines']] == [(0, .5), (.68, 1.18)]
    assert result['direction']['beats'][0]['faces'] == ['A']
    check_direction(result['direction'], json.loads(config.read_text()))
    assert len(check_scratch_takes(result, root)) == 2
    validate('audio', result, root, {})
    declared = {f['path'] for f in result['files']}
    assert len(declared) == len(result['files'])
    assert all(not Path(p).is_absolute() and (root / p).is_file() for p in declared)
    assert all(result[k] in declared for k in ('scratch_takes', 'mix', 'dialogue_stem', 'timeline', 'mouths'))
    mouths = json.loads((root / result['mouths']).read_text())
    assert mouths['frames'] == 72 and max(mouths['speakers']['A']) > 0
    for key in ('mix', 'dialogue_stem'):
        with wave.open(str(root / result[key])) as wav:
            assert wav.getframerate() == 48000 and wav.getnframes() == 144000
    before = {p: (root / p).read_bytes() for p in declared}
    assert production.audio(plan, config, root) == result
    assert len(tone.calls) == 2
    assert before == {p: (root / p).read_bytes() for p in declared}


def test_cast_model_is_character_asset_not_speech_model(setup):
    work, plan, config, _, requests = setup
    value = json.loads(plan.read_text())
    value['direction']['cast'][0]['model'] = str(work / 'active-character.blend')
    write(plan, value)
    result = production.audio(plan, config, work / 'audio')
    assert result['direction']['cast'][0]['model'].endswith('active-character.blend')
    assert all('model' not in line for line in requests[0]['lines'])


def test_preserves_explicit_starts_and_beats(setup):
    work, plan, config, _, _ = setup
    authored = json.loads(plan.read_text())
    authored['direction']['lines'][0].update(start=.2, end=.3)
    authored['direction']['lines'][1]['start'] = 1
    beats = [{'start': 0, 'end': 2, 'shot': 'Close-up', 'picture': 'Face',
              'sound': 'Speech', 'faces': ['A']}]
    authored['direction']['beats'] = beats
    write(plan, authored)
    result = production.audio(plan, config, work / 'audio')
    assert result['direction']['beats'] == beats
    assert [(l['start'], l['end']) for l in result['direction']['lines']] == [(.2, .7), (1, 1.5)]


def test_overflow_keeps_takes_and_changed_plan_needs_fresh_folder(setup):
    work, plan, config, tone, _ = setup
    authored = json.loads(plan.read_text())
    authored['direction']['lines'][1]['start'] = 6.8   # past the 8 s maximum minus the card
    write(plan, authored)
    with pytest.raises(ValueError, match='Shorten dialogue'):
        production.audio(plan, config, work / 'audio')
    assert (work / 'audio/scratch/manifest.json').is_file()
    with pytest.raises(ValueError, match='Shorten dialogue'):
        production.audio(plan, config, work / 'audio')
    assert len(tone.calls) == 2
    authored['direction']['lines'][1].pop('start')
    write(plan, authored)
    with pytest.raises(ValueError, match='fresh output folder'):
        production.audio(plan, config, work / 'audio')


def test_partial_batch_reuses_cached_first_line(setup):
    work, plan, config, tone, _ = setup
    tone.fail = 'Yes.'
    with pytest.raises(RuntimeError, match='interrupted'):
        production.audio(plan, config, work / 'audio')
    assert tone.calls == ['Hello.']
    assert not (work / 'audio/scratch/manifest.json').exists()
    tone.fail = None
    production.audio(plan, config, work / 'audio')
    assert tone.calls == ['Hello.', 'Yes.']


def test_explicit_start_cannot_overlap_measured_previous_take(setup):
    work, plan, config, _, _ = setup
    authored = json.loads(plan.read_text())
    authored['direction']['lines'][1]['start'] = .4
    write(plan, authored)
    with pytest.raises(ValueError, match='precedes measured cursor'):
        production.audio(plan, config, work / 'audio')
    assert not (work / 'audio/production.json').exists()


def test_changed_config_collision_preserves_completed_result(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    before = (work / 'audio/production.json').read_bytes()
    changed = json.loads(config.read_text())
    changed['output']['fps'] = 30
    write(config, changed)
    with pytest.raises(ValueError, match='fresh output folder'):
        production.audio(plan, config, work / 'audio')
    assert (work / 'audio/production.json').read_bytes() == before


def test_selected_takes_and_moved_completed_audio_reuse_without_synthesis(setup):
    work, plan, config, tone, _ = setup
    production.audio(plan, config, work / 'audio')
    authored = json.loads(plan.read_text())
    for i, line in enumerate(authored['direction']['lines']):
        line['selected_take'] = {'manifest': str(work / 'audio/scratch/manifest.json'),
                                 'line_id': f'line-{i + 1}'}
    write(plan, authored)
    production.audio(plan, config, work / 'selected')
    assert len(tone.calls) == 2
    # Completed output has only relative artifact links, including voice/mix inputs.
    shutil.move(str(work / 'selected'), str(work / 'moved'))
    production.audio(plan, config, work / 'moved')
    assert len(tone.calls) == 2


def test_selected_take_cannot_ignore_explicit_speech_controls(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    authored = json.loads(plan.read_text())
    authored['direction']['lines'][0].update(speed=1.2, selected_take={
        'manifest': str(work / 'audio/scratch/manifest.json'), 'line_id': 'line-1'})
    write(plan, authored)
    with pytest.raises(ValueError, match='speed'):
        production.audio(plan, config, work / 'selected')


def test_shared_cache_reuses_across_outputs_without_external_dependencies(setup):
    work, plan, config, tone, requests = setup
    shared = work / 'store/cache/voices'
    production.audio(plan, config, work / 'first', cache_dir=shared)
    result = production.audio(plan, config, work / 'second', cache_dir=shared)
    assert len(tone.calls) == 2
    assert all(r['cache_dir'] == str(shared) for r in requests)
    assert not (work / 'second/voice-cache').exists()
    assert all((work / 'second' / f['path']).is_file() for f in result['files'])
    assert all('cache' not in Path(f['path']).parts for f in result['files'])


def test_intermediate_direction_tampering_is_rejected(setup, monkeypatch):
    work, plan, config, tone, _ = setup
    original = production.mix.assemble
    monkeypatch.setattr(production.mix, 'assemble', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('stop')))
    with pytest.raises(RuntimeError):
        production.audio(plan, config, work / 'audio')
    receipt = work / 'audio/direction-result.json'
    changed = json.loads(receipt.read_text())
    changed['direction']['lines'][0]['start'] = .1
    write(receipt, changed)
    monkeypatch.setattr(production.mix, 'assemble', original)
    with pytest.raises(ValueError, match='differs from measured checkpoint'):
        production.audio(plan, config, work / 'audio')
    assert len(tone.calls) == 2


@pytest.mark.parametrize('key', ['mix', 'scratch_takes', 'mouths'])
def test_completed_corruption_is_not_reused(setup, key):
    work, plan, config, _, _ = setup
    result = production.audio(plan, config, work / 'audio')
    (work / 'audio' / result[key]).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Changed dependency'):
        production.audio(plan, config, work / 'audio')


def test_resume_after_mixing_without_resynthesis(setup, monkeypatch):
    work, plan, config, tone, _ = setup
    original = production.mouth_curves
    monkeypatch.setattr(production, 'mouth_curves', lambda *a: (_ for _ in ()).throw(RuntimeError('interrupted')))
    with pytest.raises(RuntimeError):
        production.audio(plan, config, work / 'audio')
    monkeypatch.setattr(production, 'mouth_curves', original)
    production.audio(plan, config, work / 'audio')
    assert len(tone.calls) == 2
    assert len(list((work / 'audio').glob('mix-*'))) == 1


def submission_inputs(work):
    for name in ('scene.blend', 'build.py', 'preview.mp4'):
        (work / name).write_bytes(b'fixture')
    write(work / 'rigs.json', {'A': 'actual_armature'})
    write(work / 'used-assets.json', {'used_asset_ids': ['active-guy']})
    return dict(scene=work / 'scene.blend', source=work / 'build.py',
                preview=work / 'preview.mp4', rigs=work / 'rigs.json',
                assets=work / 'used-assets.json')


def test_submit_catches_mistyped_asset_ids_before_worker_finishes(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    args = submission_inputs(work)
    catalog = work / 'active-assets.json'
    write(catalog, [{'id': 'active-guy', 'path': 'configured/character.blend'}])
    write(args['assets'], ['invented-id'])
    target = work / 'result.json'
    with pytest.raises(ValueError, match='Unknown active asset IDs.*invented-id'):
        production.submit(work / 'audio/production.json', **args, output=target, catalog=catalog)
    assert not target.exists()
    write(args['assets'], ['active-guy'])
    assert production.submit(work / 'audio/production.json', **args, output=target,
                             catalog=catalog)['used_asset_ids'] == ['active-guy']


def test_submit_maps_nested_audio_and_external_accepted_tree(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    args = submission_inputs(work)
    result = production.submit(work / 'audio/production.json', **args, output=work / 'animate.json')
    assert result['mix'].startswith('audio/')
    assert result['used_asset_ids'] == ['active-guy'] and 'verdict' not in result
    validate('animate', result, work, {})
    check_scratch_takes(result, work)
    second = work / 'another workspace'
    second.mkdir()
    # Model controller promotion of path declarations.
    receipt = json.loads((work / 'audio/production.json').read_text())
    for entry in receipt['files']:
        entry['path'] = str(work / 'audio' / entry['path'])
    for key in ('scratch_takes', 'mix', 'dialogue_stem', 'timeline', 'mouths'):
        receipt[key] = str(work / 'audio' / receipt[key])
    write(work / 'audio/accepted.json', receipt)
    copied = production.submit(work / 'audio/accepted.json', **submission_inputs(second),
                               output=second / 'result.json')
    check_scratch_takes(copied, second)
    assert all((second / f['path']).is_file() for f in copied['files'])
    assert copied['mix'].startswith('result-audio-inputs/')


def test_submit_rejects_bad_ids_missing_files_and_symlinks(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    args = submission_inputs(work)
    write(args['assets'], ['same', 'same'])
    with pytest.raises(ValueError, match='used_asset_ids'):
        production.submit(work / 'audio/production.json', **args, output=work / 'result.json')
    write(args['assets'], [])
    args['scene'].unlink()
    with pytest.raises(ValueError, match='Missing'):
        production.submit(work / 'audio/production.json', **args, output=work / 'result.json')
    args['scene'].symlink_to(args['source'])
    with pytest.raises(ValueError, match='Unsafe'):
        production.submit(work / 'audio/production.json', **args, output=work / 'result.json')


def test_edit_real_conformance_requires_explicit_review(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    args = submission_inputs(work)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=64x80:r=24:d=3', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(args['preview'])], check=True)
    production.submit(work / 'audio/production.json', **args, output=work / 'animate.json')
    cut = {'segments': [{'start': 0, 'end': 2, 'reason': 'Keep story'},
                        {'start': 2, 'end': 3, 'reason': 'Keep hero'}],
           'removed_lines': [], 'sound_plan': 'Keep dry dialogue'}
    cut_path = write(work / 'cut.json', cut)
    with pytest.raises(ValueError, match='no approval inferred'):
        production.edit(work / 'animate.json', cut_path, config, work / 'edit.json')
    cut['review'] = {'verdict': 'pass', 'findings': [
        {'target': '0.1s', 'severity': 'minor', 'problem': 'Small lighting variation',
         'fix': 'Optional lighting polish'}], 'summary': 'Caller inspected this cut.'}
    write(cut_path, cut)
    result = production.edit(work / 'animate.json', cut_path, config, work / 'edit.json')
    assert result['verdict'] == 'pass' and result['review'] == cut['review']
    assert result['findings'] == cut['review']['findings']
    validate('edit', result, work, {'compact': True, 'strict_review': True})
    assert (work / result['master']).stat().st_size > 100
    timeline = json.loads((work / result['timeline']).read_text())
    assert len(timeline['dialogue']) == 2
    assert production.edit(work / 'animate.json', cut_path, config, work / 'edit.json') == result


@pytest.mark.parametrize('severity', ['important', 'blocking', 'major', 'critical'])
def test_edit_rejects_unresolved_findings_before_work(setup, severity):
    work, _, config, _, _ = setup
    cut = {'review': {'verdict': 'pass', 'summary': 'Reviewed', 'findings': [
        {'target': '0s', 'severity': severity, 'problem': 'Unreadable', 'fix': 'Reframe'}]}}
    plan = write(work / 'cut.json', cut)
    with pytest.raises(ValueError, match='cannot pass'):
        production.edit(work / 'nonexistent.json', plan, config, work / 'edit.json')
    assert not (work / 'edit-edit-work').exists()


@pytest.fixture
def edit_inputs(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    args = submission_inputs(work)
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=64x80:r=24:d=3', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(args['preview'])], check=True)
    production.submit(work / 'audio/production.json', **args, output=work / 'animate.json')
    cut = {'segments': [{'start': 0, 'end': 2, 'reason': 'Keep story'},
                        {'start': 2, 'end': 3, 'reason': 'Keep hero'}],
           'removed_lines': [], 'sound_plan': 'Keep dialogue',
           'review': {'verdict': 'pass', 'findings': [], 'summary': 'Caller reviewed'}}
    cut_path = write(work / 'cut.json', cut)
    editor = work / 'editor'
    editor.mkdir()
    return work / 'animate.json', cut_path, config, editor / 'result.json'


@pytest.mark.parametrize('failure', ['copy', 'render', 'receipt'])
def test_edit_same_input_retry_preserves_partial_and_reuses_completed(edit_inputs, monkeypatch, failure):
    accepted, plan, config, target = edit_inputs
    original_copy, original_assemble, original_write = (
        production.shutil.copyfile, production.editing.assemble, production._write)
    calls = {'copy': 0, 'render': 0}
    failed = False

    def copying(source, dest):
        nonlocal failed
        calls['copy'] += 1
        if failure == 'copy' and calls['copy'] == 2 and not failed:
            failed = True
            Path(dest).write_bytes(b'partial copy')
            raise RuntimeError('interrupted copy')
        return original_copy(source, dest)

    def assembling(*args):
        nonlocal failed
        calls['render'] += 1
        if failure == 'render' and not failed:
            failed = True
            Path(args[-2]).write_bytes(b'partial render')
            raise RuntimeError('interrupted render')
        return original_assemble(*args)

    def writing(path, value):
        nonlocal failed
        if failure == 'receipt' and Path(path) == target and not failed:
            failed = True
            raise RuntimeError('interrupted receipt')
        return original_write(path, value)

    monkeypatch.setattr(production.shutil, 'copyfile', copying)
    monkeypatch.setattr(production.editing, 'assemble', assembling)
    monkeypatch.setattr(production, '_write', writing)
    with pytest.raises(RuntimeError, match='interrupted'):
        production.edit(accepted, plan, config, target)
    assert not target.exists()
    copied = {p: p.stat().st_mtime_ns for p in (target.parent / 'result-animate-inputs').rglob('*')
              if p.is_file()}
    result = production.edit(accepted, plan, config, target)
    assert all(p.stat().st_mtime_ns == mtime for p, mtime in copied.items())
    assert calls['render'] == (2 if failure == 'render' else 1)
    if failure == 'render':
        assert (target.parent / 'result-edit-work/attempt-0000/master.mp4').read_bytes() == b'partial render'
        assert 'attempt-0001' in result['master']
    before = dict(calls)
    assert production.edit(accepted, plan, config, target) == result
    assert calls == before


@pytest.mark.parametrize('changed', ['plan', 'config', 'accepted'])
def test_edit_changed_inputs_get_new_version_without_overwrite(edit_inputs, monkeypatch, changed):
    accepted, plan, config, target = edit_inputs
    original = production.editing.assemble

    def interrupted(*args):
        Path(args[-2]).write_bytes(b'keep partial')
        raise RuntimeError('interrupted')

    monkeypatch.setattr(production.editing, 'assemble', interrupted)
    with pytest.raises(RuntimeError):
        production.edit(accepted, plan, config, target)
    path = {'plan': plan, 'config': config, 'accepted': accepted}[changed]
    value = json.loads(path.read_text())
    value['changed'] = True
    write(path, value)
    monkeypatch.setattr(production.editing, 'assemble', original)
    result = production.edit(accepted, plan, config, target)
    assert (target.parent / 'result-edit-work/attempt-0000/master.mp4').read_bytes() == b'keep partial'
    assert result['master'] != 'result-edit-work/attempt-0000/master.mp4'
    assert target.exists()


def test_changed_edit_inputs_cannot_overwrite_existing_receipt(edit_inputs):
    accepted, plan, config, target = edit_inputs
    production.edit(accepted, plan, config, target)
    checksum = production.digest(target)
    value = json.loads(plan.read_text()); value['review']['summary'] = 'Changed'
    write(plan, value)
    with pytest.raises(ValueError, match='input collision'):
        production.edit(accepted, plan, config, target)
    assert production.digest(target) == checksum


def test_edit_completed_corruption_is_rejected(edit_inputs):
    accepted, plan, config, target = edit_inputs
    result = production.edit(accepted, plan, config, target)
    (target.parent / result['master']).write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='Changed dependency'):
        production.edit(accepted, plan, config, target)


def test_new_edit_revision_after_controller_archives_receipt_keeps_old_media(edit_inputs):
    accepted, plan, config, target = edit_inputs
    first = production.edit(accepted, plan, config, target)
    old_master = target.parent / first['master']
    old_hash = production.digest(old_master)
    target.rename(target.with_name('result.previous.json'))
    revised = json.loads(plan.read_text())
    revised['review']['summary'] = 'Rechecked the repaired animation'
    write(plan, revised)
    second = production.edit(accepted, plan, config, target)
    assert second['master'] != first['master']
    assert production.digest(old_master) == old_hash
    assert production.edit(accepted, plan, config, target) == second


def test_cli_reuses_audio_and_submits_schema(setup):
    work, plan, config, _, _ = setup
    production.audio(plan, config, work / 'audio')
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2]),
               PYTHONDONTWRITEBYTECODE='1')
    base = [sys.executable, '-m', 'harness.production_tools']
    done = subprocess.run(base + ['audio', str(plan), '--config', str(config), '--output', 'audio',
                                 '--cache-dir', str(work / 'store/cache/voices')],
                          cwd=work, env=env, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)['scratch_takes'] == 'scratch/manifest.json'
    args = submission_inputs(work)
    command = base + ['submit', 'audio/production.json', '--output', 'result.json']
    write(work / 'active-assets.json', [{'id': 'active-guy'}])
    command += ['--catalog', 'active-assets.json']
    for key, path in args.items():
        command += ['--' + key, str(path)]
    done = subprocess.run(command, cwd=work, env=env, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    validate('animate', json.loads(done.stdout), work, {})


def test_story_led_duration_grows_to_fit_measured_takes(setup):
    work, plan, config, _, _ = setup
    authored = json.loads(plan.read_text())
    authored['direction']['duration'] = 2   # one second of story for two measured takes
    write(plan, authored)
    result = production.audio(plan, config, work / 'audio')
    direction = result['direction']
    last_end = direction['lines'][-1]['end']
    assert direction['duration'] > 2 and 'Grew from the planned 2 s' in direction['duration_note']
    assert direction['duration'] - 1 >= last_end + 0.5
    assert direction['beats'][-1]['end'] == pytest.approx(direction['duration'] - 1)


def test_planned_sounds_become_a_foley_bed_and_timeline_events(setup):
    work, plan, config, _, _ = setup
    authored = json.loads(plan.read_text())
    authored['direction']['sounds'] = {'ambience': 'hall', 'events': [
        {'name': 'page_turn', 'after_line': 0, 'offset': 0.1}, {'name': 'slam', 'at': 1.5}]}
    write(plan, authored)
    production.audio(plan, config, work / 'audio')
    mixed = next((work / 'audio').glob('mix-*'))
    audit = json.loads((mixed / 'audit.json').read_text())
    assert audit['bed']['mode'] == 'supplied' and audit['bed']['gain_db'] == -12
    timeline = json.loads((mixed / 'timeline.json').read_text())
    assert [e['name'] for e in timeline['events']] == ['page_turn', 'slam']
    assert 'harness.foley' in timeline['sound_rationale']
