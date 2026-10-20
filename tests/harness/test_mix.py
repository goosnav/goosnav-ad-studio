"""Real PCM, accepted-artifact, FFmpeg and replay checks; synthesis alone is fake."""
import array
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import wave

import pytest

from harness.contracts import promote, validate
from harness.voice import run_batch


def write_wav(path, samples, rate=48000, channels=1):
    pcm = array.array('h', samples)
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((channels, 2, rate, 0, 'NONE', 'not compressed'))
        stream.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(str(path), 'rb') as stream:
        meta = (stream.getframerate(), stream.getnchannels(), stream.getnframes())
        pcm = array.array('h', stream.readframes(stream.getnframes()))
    if sys.byteorder != 'little':
        pcm.byteswap()
    return meta, pcm


class FixtureSynthesis:
    def identity(self, settings):
        return {'provider': 'kokoro', 'model': 'fixture', 'resolved_revision': 'a' * 40,
                'files': {'weights': 'a' * 64}, 'runtime': {'fixture': '1'}}

    def synthesize(self, settings, output):
        # .2 s silence, .4 s nonzero signal, .2 s silence. No estimated timings.
        write_wav(output, [0] * 9600 + [4000, -4000] * 9600 + [0] * 9600)
        return {'identity': self.identity(settings), 'wall_seconds': 0}


@pytest.fixture
def mix():
    assert importlib.util.find_spec('harness.mix'), 'Deterministic mix helper is missing'
    return importlib.import_module('harness.mix')


@pytest.fixture
def direct(tmp_path):
    work = tmp_path / 'work'; work.mkdir()
    run_batch({'provider': 'kokoro', 'polish': False,
               'lines': [{'id': 'second', 'speaker': 'B', 'voice': 'af_heart', 'text': 'Yes.'},
                         {'id': 'first', 'speaker': 'A', 'voice': 'am_onyx', 'text': 'Hi.'}]},
              work / 'scratch', session=FixtureSynthesis())
    data = {'summary': 'Measured direct result', 'scratch_takes': 'scratch/manifest.json',
            'direction': {'duration': 3, 'cast': [{'speaker': 'A', 'voice': 'am_onyx'},
                                                  {'speaker': 'B', 'voice': 'af_heart'}],
                          'lines': [{'id': 'first', 'speaker': 'A', 'text': 'Hi.', 'start': .5, 'end': 1.1,
                                     'delivery': 'Plainly.', 'offscreen': 'Listener is on screen.'},
                                    {'id': 'second', 'speaker': 'B', 'text': 'Yes.', 'start': 1.3, 'end': 2.1,
                                     'delivery': 'Warmly.'}]},
            'files': [{'path': 'scratch/manifest.json', 'kind': 'voice_manifest'}]}
    manifest = json.loads((work / 'scratch/manifest.json').read_text())
    for entry in manifest['lines']:
        for kind in ('raw', 'polished'):
            data['files'].append({'path': 'scratch/' + entry['takes'][0][kind]['path'], 'kind': 'audio'})
    promote(data, work, tmp_path / 'accepted')
    return tmp_path / 'accepted/accepted.json'


def test_complete_audio_contract_preserves_planned_starts_and_nonzero_samples(mix, direct, tmp_path):
    output = tmp_path / 'mix'
    result = mix.assemble(direct, output, no_bed=True, fps=24)
    assert validate('audio', result, output, {}) == result
    assert result['dialogue_stem'] == 'dialogue.wav'
    assert result['source'] == 'request.json'
    assert json.loads((output / 'result.json').read_text()) == result
    meta, pcm = read_wav(output / 'dialogue.wav')
    assert meta == (48000, 2, 144000)
    assert (output / 'mix.wav').read_bytes() == (output / 'dialogue.wav').read_bytes()
    assert pcm[:33600 * 2] == array.array('h', [0]) * (33600 * 2)
    assert pcm[33600 * 2:52800 * 2] == array.array('h', [4000, 4000, -4000, -4000]) * 9600
    timeline = json.loads((output / 'timeline.json').read_text())
    assert timeline['frames'] == 144000 and timeline['duration'] == 3
    assert [(l['start_sample'], l['end_sample']) for l in timeline['dialogue']] == [(24000, 52800), (62400, 100800)]
    assert timeline['dialogue'][0]['offscreen'] == 'Listener is on screen.'
    assert timeline['events'] == [] and 'No bed' in timeline['sound_rationale']
    audit = json.loads((output / 'audit.json').read_text())
    assert audit['lines'][0]['trim_end_samples'] == 9600
    assert audit['lines'][0]['trim_start_samples'] == 0
    assert audit['lines'][0]['source_line_id'] == 'first'
    assert len(audit['lines'][0]['take_id']) == 64
    assert audit['asr'] == 'not_run'
    assert all((output / f['path']).is_file() for f in result['files'])


def test_output_is_deterministic_and_portable_request_replays_without_originals(mix, direct, tmp_path):
    first = mix.assemble(direct, tmp_path / 'one', no_bed=True)
    second = mix.assemble(direct, tmp_path / 'two', no_bed=True)
    assert first == second
    shutil.rmtree(direct.parent)
    shutil.move(tmp_path / 'one', tmp_path / 'relocated')
    completed = subprocess.run([sys.executable, '-m', 'harness.mix', '--request',
                                str(tmp_path / 'relocated/request.json'), str(tmp_path / 'replay')],
                               text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['mix'] == 'mix.wav'
    for name in ('mix.wav', 'dialogue.wav', 'timeline.json'):
        assert (tmp_path / 'replay' / name).read_bytes() == (tmp_path / 'relocated' / name).read_bytes()


def test_direct_cli_accepts_promoted_absolute_declarations(mix, direct, tmp_path):
    completed = subprocess.run([sys.executable, '-m', 'harness.mix', str(direct),
                                str(tmp_path / 'cli'), '--no-bed', '--fps', '30'],
                               text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result['timeline'] == 'timeline.json'
    assert json.loads((tmp_path / 'cli/timeline.json').read_text())['fps'] == 30


def test_refuses_to_fit_active_speech_by_cutting_or_stretching(mix, direct, tmp_path):
    data = json.loads(direct.read_text())
    data['direction']['lines'][0]['end'] = .89  # .39 s slot, .4 s nonzero audio
    direct.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='fit'):
        mix.assemble(direct, tmp_path / 'out', no_bed=True)
    assert not (tmp_path / 'out/result.json').exists()


def test_trims_leading_silence_only_if_trailing_silence_is_insufficient(mix, direct, tmp_path):
    data = json.loads(direct.read_text())
    data['direction']['lines'][0]['end'] = .9  # .4 s slot; remove both .2 s edges
    direct.write_text(json.dumps(data))
    mix.assemble(direct, tmp_path / 'out', no_bed=True)
    _, pcm = read_wav(tmp_path / 'out/dialogue.wav')
    assert pcm[24000 * 2:43200 * 2] == array.array('h', [4000, 4000, -4000, -4000]) * 9600
    audit = json.loads((tmp_path / 'out/audit.json').read_text())
    assert audit['lines'][0]['trim_start_samples'] == audit['lines'][0]['trim_end_samples'] == 9600


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='FFmpeg is required for a supplied bed')
def test_real_ffmpeg_bed_resampling_at_quiet_gain_never_loops(mix, direct, tmp_path):
    bed = tmp_path / 'bed.wav'
    write_wav(bed, [10000] * 12000, rate=24000)
    mix.assemble(direct, tmp_path / 'out', bed=bed, bed_gain_db=-30)
    meta, pcm = read_wav(tmp_path / 'out/mix.wav')
    assert meta == (48000, 2, 144000)
    assert 310 <= pcm[1000] <= 320
    assert pcm[30000 * 2] == 0  # source bed ended; it was not looped
    _, stem = read_wav(tmp_path / 'out/dialogue.wav')
    assert stem[1000] == 0
    assert pcm[35000 * 2] == stem[35000 * 2]
    audit = json.loads((tmp_path / 'out/audit.json').read_text())
    assert audit['bed']['gain_db'] == -30 and audit['bed']['looped'] is False


@pytest.mark.parametrize('change', ['text', 'voice', 'duplicate_line', 'undeclared_manifest',
                                   'undeclared_raw', 'manifest_escape', 'absolute_escape', 'symlink', 'hash'])
def test_rejects_mismatched_or_unsafe_declared_scratch_inputs(mix, direct, tmp_path, change):
    data = json.loads(direct.read_text())
    if change == 'text':
        data['direction']['lines'][0]['text'] = 'Different words.'
    elif change == 'voice':
        data['direction']['cast'][0]['voice'] = 'am_puck'
    elif change == 'duplicate_line':
        data['direction']['lines'].append(dict(data['direction']['lines'][0], id='extra', start=2.2, end=3))
    elif change == 'undeclared_manifest':
        data['files'] = data['files'][1:]
    elif change == 'undeclared_raw':
        data['files'] = [f for f in data['files'] if '/raw-' not in f['path']]
    elif change in ('manifest_escape', 'absolute_escape'):
        outsider = tmp_path / 'outside.json'; shutil.copyfile(data['scratch_takes'], outsider)
        data['scratch_takes'] = '../outside.json' if change == 'manifest_escape' else str(outsider)
        data['files'][0]['path'] = data['scratch_takes']
    elif change == 'symlink':
        manifest = Path(data['scratch_takes'])
        outsider = tmp_path / 'outside.json'; shutil.copyfile(manifest, outsider)
        manifest.unlink(); manifest.symlink_to(outsider)
    elif change == 'hash':
        data['files'][0]['sha256'] = 'f' * 64
    direct.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        mix.assemble(direct, tmp_path / 'out', no_bed=True)
    assert not (tmp_path / 'out/result.json').exists()


def test_reuse_is_explicit_and_existing_outputs_are_preserved(mix, direct, tmp_path):
    with pytest.raises(ValueError, match='bed'):
        mix.assemble(direct, tmp_path / 'missing-choice')
    with pytest.raises(ValueError, match='gain'):
        mix.assemble(direct, tmp_path / 'loud', bed=direct, bed_gain_db=6)
    output = tmp_path / 'out'; output.mkdir()
    (output / 'mix.wav').write_bytes(b'keep accepted work')
    with pytest.raises(ValueError, match='empty'):
        mix.assemble(direct, output, no_bed=True)
    assert (output / 'mix.wav').read_bytes() == b'keep accepted work'


def test_explicit_silent_film_needs_no_scratch_and_keeps_complete_alignment(mix, tmp_path):
    direct = tmp_path / 'direct.json'
    direct.write_text(json.dumps({'direction': {'duration': 1.25, 'cast': [], 'lines': [],
                                               'mix': 'Intentional silent visual scene.'}, 'files': []}))
    result = mix.assemble(direct, tmp_path / 'out', no_bed=True)
    assert result['dialogue_stem'] == 'dialogue.wav'
    meta, pcm = read_wav(tmp_path / 'out/mix.wav')
    assert meta == (48000, 2, 60000) and not any(pcm)
    timeline = json.loads((tmp_path / 'out/timeline.json').read_text())
    assert timeline['dialogue'] == [] and timeline['duration'] == 1.25
    assert 'silent' in timeline['sound_rationale'].lower()


@pytest.mark.parametrize('part', ['direct', 'raw', 'polished', 'escape', 'symlink'])
def test_replay_reverifies_portable_input_hashes_and_paths(mix, direct, tmp_path, part):
    output = tmp_path / 'one'
    mix.assemble(direct, output, no_bed=True)
    request = json.loads((output / 'request.json').read_text())
    if part == 'direct':
        (output / request['direct_result']).write_text('{}')
    elif part in ('raw', 'polished'):
        next((output / 'inputs/voice').glob(part + '-*.wav')).write_bytes(b'corrupt')
    else:
        outside = tmp_path / 'external.json'
        shutil.copyfile(output / request['direct_result'], outside)
        if part == 'escape':
            request['direct_result'] = str(outside)
        else:
            (output / 'alias.json').symlink_to(outside)
            request['direct_result'] = 'alias.json'
        (output / 'request.json').write_text(json.dumps(request))
    with pytest.raises(ValueError):
        mix.replay(output / 'request.json', tmp_path / 'replay')
    assert not (tmp_path / 'replay/result.json').exists()


def test_overlapping_lines_are_summed_without_reordering_or_sample_clipping(mix, direct, tmp_path):
    data = json.loads(direct.read_text())
    data['direction']['lines'][1].update(start=.5, end=1.3)
    direct.write_text(json.dumps(data))
    mix.assemble(direct, tmp_path / 'out', no_bed=True)
    _, pcm = read_wav(tmp_path / 'out/dialogue.wav')
    assert pcm[33600 * 2:52800 * 2] == array.array('h', [8000, 8000, -8000, -8000]) * 9600
    timeline = json.loads((tmp_path / 'out/timeline.json').read_text())
    assert [l['speaker'] for l in timeline['dialogue']] == ['A', 'B']


def test_matching_without_ids_is_a_multiset_not_manifest_order(mix, direct, tmp_path):
    data = json.loads(direct.read_text())
    for line in data['direction']['lines']:
        del line['id']
    direct.write_text(json.dumps(data))
    mix.assemble(direct, tmp_path / 'out', no_bed=True)
    audit = json.loads((tmp_path / 'out/audit.json').read_text())
    assert [l['source_line_id'] for l in audit['lines']] == ['first', 'second']


def test_selected_take_recipe_cannot_be_relabeled_as_different_words(mix, direct, tmp_path):
    data = json.loads(direct.read_text())
    manifest_path = Path(data['scratch_takes'])
    manifest = json.loads(manifest_path.read_text())
    data['direction']['lines'][0]['text'] = 'Altered words'
    next(l for l in manifest['lines'] if l['id'] == 'first')['text'] = 'Altered words'
    manifest_path.chmod(0o600)  # Deliberately tamper with this test's promoted copy.
    manifest_path.write_text(json.dumps(manifest))
    # Remove outer receipts so this specifically tests recipe vs line matching.
    data['files'] = [{k: v for k, v in f.items() if k not in ('sha256', 'bytes')} for f in data['files']]
    direct.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='settings'):
        mix.assemble(direct, tmp_path / 'out', no_bed=True)


def test_low_level_edge_signal_is_never_removed_using_activity_threshold(mix, direct, tmp_path):
    # Real fixture generation with signal below the active-envelope threshold at
    # BOTH edges; the body is ordinary audible PCM. No fake measurement layer.
    class Breathy(FixtureSynthesis):
        def synthesize(self, settings, output):
            write_wav(output, [1] * 9600 + [4000, -4000] * 9600 + [1] * 9600)
            return {'identity': self.identity(settings), 'wall_seconds': 0}
    work = tmp_path / 'breathy'; work.mkdir()
    run_batch({'polish': False, 'lines': [{'id': 'a', 'speaker': 'A', 'voice': 'am_onyx', 'text': 'Hi.'}]},
              work / 'scratch', session=Breathy())
    manifest = json.loads((work / 'scratch/manifest.json').read_text())
    take = manifest['lines'][0]['takes'][0]
    data = {'scratch_takes': 'scratch/manifest.json',
            'direction': {'duration': 1, 'cast': [{'speaker': 'A', 'voice': 'am_onyx'}],
                          'lines': [{'speaker': 'A', 'text': 'Hi.', 'start': 0, 'end': .4}]},
            'files': [{'path': 'scratch/manifest.json', 'kind': 'notes'}] +
                     [{'path': 'scratch/' + take[k]['path'], 'kind': 'audio'} for k in ('raw', 'polished')]}
    (work / 'direct.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='fit'):
        mix.assemble(work / 'direct.json', tmp_path / 'out', no_bed=True)


def test_stage_result_cli_integrates_nonempty_worker_workspace_without_manual_rewrites(mix, direct, tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    (workspace / 'TASK.md').write_text('Keep my worker instructions')
    completed = subprocess.run([sys.executable, '-m', 'harness.mix', str(direct),
                                'generated-audio', '--no-bed', '--fps', '24',
                                '--stage-result', 'result.json'], text=True, capture_output=True, cwd=workspace,
                               env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[2])})
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert json.loads((workspace / 'result.json').read_text()) == result
    assert validate('audio', result, workspace, {}) == result
    inner = json.loads((workspace / 'generated-audio/result.json').read_text())
    for key in ('mix', 'dialogue_stem', 'timeline', 'source', 'audit'):
        assert result[key] == 'generated-audio/' + inner[key]
    assert result['summary'] == inner['summary'] and result['quality'] == inner['quality']
    assert result['files'] == [dict(f, path='generated-audio/' + f['path']) for f in inner['files']]
    assert (workspace / 'TASK.md').read_text() == 'Keep my worker instructions'
    # The portable request itself is NOT rewritten to workspace-relative paths.
    assert json.loads((workspace / result['source']).read_text())['direct_result'] == 'inputs/direct.json'


@pytest.mark.parametrize('unsafe', ['existing', 'wrong_parent', 'symlink'])
def test_stage_result_cli_fails_before_generating_if_destination_is_unsafe(mix, direct, tmp_path, unsafe):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    target = workspace / 'result.json'
    if unsafe == 'existing':
        target.write_text('Keep original result')
    elif unsafe == 'wrong_parent':
        target = tmp_path / 'result.json'
    else:
        original = tmp_path / 'original.json'; original.write_text('Keep original result')
        target.symlink_to(original)
    completed = subprocess.run([sys.executable, '-m', 'harness.mix', str(direct),
                                str(workspace / 'generated-audio'), '--no-bed',
                                '--stage-result', str(target)], text=True, capture_output=True)
    assert completed.returncode != 0
    assert 'Stage result' in completed.stderr
    assert not (workspace / 'generated-audio').exists()
    if unsafe in ('existing', 'symlink'):
        assert target.read_text() == 'Keep original result'


def test_stage_result_revalidates_and_copies_only_declared_artifact_references(mix, direct, tmp_path):
    output = tmp_path / 'generated-audio'
    mix.assemble(direct, output, no_bed=True)
    # Unknown strings, even those that look exactly like a path, must stay intact.
    inner = json.loads((output / 'result.json').read_text())
    inner.update(summary='mix.wav', extra_note={'quoted_filename': 'dialogue.wav'})
    (output / 'result.json').write_text(json.dumps(inner))
    staged = mix.stage_result(output, tmp_path / 'result.json')
    assert staged['summary'] == 'mix.wav'
    assert staged['extra_note'] == {'quoted_filename': 'dialogue.wav'}
    assert staged['mix'] == 'generated-audio/mix.wav'
    with pytest.raises(ValueError, match='exist'):
        mix.stage_result(output, tmp_path / 'result.json')
    (output / 'mix.wav').write_bytes(b'broken')
    with pytest.raises(ValueError, match='hash'):
        mix.stage_result(output, tmp_path / 'another-result.json')
    assert not (tmp_path / 'another-result.json').exists()


def calibration_direct(tmp_path, signals, *, overlap=False):
    """Real PCM/manifest fixture; replace only the optional speech model."""
    class Samples(FixtureSynthesis):
        def synthesize(self, settings, output):
            write_wav(output, signals[int(settings['text'])])
            return {'identity': self.identity(settings), 'wall_seconds': 0}
    work = tmp_path / 'calibration-source'; work.mkdir()
    manifest = run_batch({'polish': False, 'lines': [
        {'id': str(i), 'speaker': str(i), 'text': str(i), 'voice': 'am_onyx'}
        for i in range(len(signals))]}, work / 'scratch', session=Samples())
    lines = [{'id': str(i), 'speaker': str(i), 'text': str(i),
              'start': 0 if overlap else i * 1.2,
              'end': (0 if overlap else i * 1.2) + len(signal) / 48000}
             for i, signal in enumerate(signals)]
    data = {'scratch_takes': 'scratch/manifest.json',
            'direction': {'duration': len(signals) * 1.2, 'lines': lines,
                          'cast': [{'speaker': str(i), 'voice': 'am_onyx'} for i in range(len(signals))]},
            'files': [{'path': 'scratch/manifest.json', 'kind': 'notes'}] +
                     [{'path': 'scratch/' + line['takes'][0][kind]['path'], 'kind': 'audio'}
                      for line in manifest['lines'] for kind in ('raw', 'polished')]}
    (work / 'direct.json').write_text(json.dumps(data))
    return work / 'direct.json'


@pytest.mark.parametrize('with_bed', [False, True])
def test_quiet_dialogue_is_uniformly_calibrated_to_controller_metric(mix, tmp_path, with_bed):
    from harness.direction import check_mix
    signals = [[0] * 9600 + [level, -level] * 9600 + [0] * 9600 for level in (2000, 1900)]
    direct = calibration_direct(tmp_path, signals)
    output = tmp_path / 'out'
    if with_bed:
        if not shutil.which('ffmpeg'):
            pytest.skip('FFmpeg is required for a supplied bed')
        bed = tmp_path / 'bed.wav'
        write_wav(bed, [1000] * 115200)
        mix.assemble(direct, output, bed=bed)
    else:
        mix.assemble(direct, output, no_bed=True)
    timeline = json.loads((output / 'timeline.json').read_text())
    measured = check_mix(output / 'mix.wav', timeline)
    assert min(l['db'] for l in measured['speech']) == pytest.approx(-21, abs=.01)
    audit = json.loads((output / 'audit.json').read_text())['dialogue_calibration']
    assert audit['before'][1]['db'] == pytest.approx(-24.7346, abs=.01)
    assert 3.7 < audit['gain_db'] < 3.8
    assert audit['after_mix'] == measured['speech']
    assert audit['blockers'] == []
    meta, pcm = read_wav(output / 'dialogue.wav')
    assert meta == (48000, 2, 115200)
    assert [(l['start_sample'], l['end_sample']) for l in timeline['dialogue']] == [(0, 38400), (57600, 96000)]
    for start, original in zip((0, 57600), signals):
        expected = array.array('h', [round(x * audit['gain']) for x in original for _ in range(2)])
        assert pcm[start * 2:(start + len(original)) * 2] == expected
    if not with_bed:
        assert (output / 'dialogue.wav').read_bytes() == (output / 'mix.wav').read_bytes()


def test_overlap_calibration_keeps_safe_peaks_and_controller_floor(mix, tmp_path):
    from harness.direction import check_mix
    direct = calibration_direct(tmp_path, [[24000, -24000] * 19200] * 2, overlap=True)
    output = tmp_path / 'out'
    mix.assemble(direct, output, no_bed=True)
    meta, pcm = read_wav(output / 'mix.wav')
    assert meta == (48000, 2, 115200)
    assert max(pcm) == 32700 and min(pcm) == -32700
    timeline = json.loads((output / 'timeline.json').read_text())
    check_mix(output / 'mix.wav', timeline)
    audit = json.loads((output / 'audit.json').read_text())
    assert audit['uniform_headroom_gain'] == pytest.approx(32700 / 48000)
    assert audit['dialogue_calibration']['blockers'] == []
    assert audit['dialogue_calibration']['gain'] == 1


@pytest.mark.parametrize('limit', ['peak', 'gain_cap', 'cancellation'])
def test_unachievable_dialogue_floor_records_blocker_without_clipping(mix, tmp_path, limit):
    if limit == 'peak':
        signal = [300, -300] * 19200
        signal[12000] = 30000
        signals = [signal]
    elif limit == 'gain_cap':
        signals = [[150, -150] * 19200]
    else:
        signals = [[4000, -4000] * 19200, [-4000, 4000] * 19200]
    direct = calibration_direct(tmp_path, signals, overlap=limit == 'cancellation')
    output = tmp_path / 'out'
    with pytest.raises(ValueError, match='floor'):
        mix.assemble(direct, output, no_bed=True)
    assert not (output / 'result.json').exists()
    assert not (output / 'mix.wav').exists()
    audit = json.loads((output / 'audit.json').read_text())['dialogue_calibration']
    assert 0 <= audit['gain_db'] <= 18
    assert audit['blockers']
    assert any(l['db'] < -24 for l in audit['after_dialogue'])
