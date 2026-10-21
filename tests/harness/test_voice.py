"""Real WAV/cache/polish tests; only the optional model boundary is replaced."""
import importlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

import pytest


def wav(path, frames=12000, silent=False):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b''.join(struct.pack('<h', 0 if silent else
                           int(5000 * math.sin(2 * math.pi * 300 * i / 48000)))
                           for i in range(frames)))


class FakeSession:
    """Represents slow synthesis, including output from failed generations."""
    def __init__(self, revision='a' * 40, silent=0):
        self.revision, self.silent, self.calls = revision, silent, []

    def identity(self, request):
        import hashlib
        identity = {'provider': request['provider'], 'model': 'fixture-model',
                    'resolved_revision': self.revision, 'files': {'weights': self.revision},
                    'runtime': {'fixture': '1'}}
        if request.get('reference'):
            identity['reference_sha256'] = hashlib.sha256(Path(request['reference']).read_bytes()).hexdigest()
        return identity

    def synthesize(self, request, output):
        self.calls.append(dict(request))
        wav(output, round(12000 / request['speed']), len(self.calls) <= self.silent)
        return {'wall_seconds': 0.01}


@pytest.fixture
def voice():
    assert importlib.util.find_spec('harness.voice') is not None, 'batch voice module is missing'
    return importlib.import_module('harness.voice')


@pytest.fixture
def request_data(tmp_path):
    return {'cache_dir': str(tmp_path / 'cache'), 'provider': 'kokoro', 'effort': 'medium',
            'voice_profiles': {'GUY': {'voice': 'am_onyx', 'speed': 1.0}},
            'lines': [{'id': 'hello', 'speaker': 'GUY', 'text': 'Hello there.'},
                      {'id': 'bye', 'speaker': 'GUY', 'text': 'Goodbye.'}]}


def test_batch_measures_and_reuses_portable_takes(voice, request_data, tmp_path):
    session = FakeSession()
    first = voice.run_batch(request_data, tmp_path / 'first', session=session)
    assert first['duration'] == .5
    assert [(l['start_sample'], l['end_sample']) for l in first['lines']] == [(0, 12000), (12000, 24000)]
    assert len(session.calls) == 2
    second = voice.run_batch(request_data, tmp_path / 'second', session=session)
    assert len(session.calls) == 2
    assert all(line['takes'][0]['reused'] for line in second['lines'])
    assert second['lines'][0]['acceptance'] == 'provisional_requires_listening'
    take = second['lines'][0]['takes'][0]
    for kind in ('raw', 'polished'):
        assert not Path(take[kind]['path']).is_absolute()
        assert (tmp_path / 'second' / take[kind]['path']).is_file()
        assert len(take[kind]['sha256']) == 64
    assert json.loads((tmp_path / 'second/manifest.json').read_text()) == second


@pytest.mark.parametrize('effort,fast,limit', [('low', False, 1), ('medium', False, 2),
                                             ('high', False, 3), ('high', True, 1)])
def test_audition_budget_is_a_cap_not_a_generation_target(voice, request_data, tmp_path, effort, fast, limit):
    request_data.update(effort=effort, fast=fast)
    request_data['lines'] = request_data['lines'][:1]
    request_data['lines'][0]['auditions'] = [{'speed': x} for x in (1.0, .9, 1.1, 1.2)]
    session = FakeSession()
    result = voice.run_batch(request_data, tmp_path / 'out', session=session)
    assert len(result['lines'][0]['takes']) == limit
    assert len(session.calls) == limit
    assert len({t['id'] for t in result['lines'][0]['takes']}) == limit


@pytest.mark.parametrize('kind', ['raw', 'polished'])
def test_corrupt_cache_is_regenerated(voice, request_data, tmp_path, kind):
    session = FakeSession()
    first = voice.run_batch(request_data, tmp_path / 'first', session=session)
    take = first['lines'][0]['takes'][0]
    (Path(request_data['cache_dir']) / take['id'] / f'{kind}.wav').write_bytes(b'broken')
    result = voice.run_batch(request_data, tmp_path / 'second', session=session)
    assert len(session.calls) == 3
    assert not result['lines'][0]['takes'][0]['reused']


def test_moving_model_and_generation_settings_invalidate_cache(voice, request_data, tmp_path):
    a = FakeSession()
    one = voice.run_batch(request_data, tmp_path / 'one', session=a)
    b = FakeSession(revision='b' * 40)
    two = voice.run_batch(request_data, tmp_path / 'two', session=b)
    assert len(b.calls) == 2
    assert one['lines'][0]['selected_take_id'] != two['lines'][0]['selected_take_id']
    request_data['lines'][0]['speed'] = .8
    three = voice.run_batch(request_data, tmp_path / 'three', session=b)
    assert len(b.calls) == 3
    assert three['lines'][0]['duration'] == .3125


def test_delivery_note_is_not_a_fake_emotion_control(voice, request_data, tmp_path):
    session = FakeSession()
    one = voice.run_batch(request_data, tmp_path / 'one', session=session)
    request_data['lines'][0]['delivery'] = 'With tragic bewilderment.'
    two = voice.run_batch(request_data, tmp_path / 'two', session=session)
    assert len(session.calls) == 2  # Notes alone cannot change Kokoro audio.
    assert one['lines'][0]['selected_take_id'] == two['lines'][0]['selected_take_id']
    assert two['lines'][0]['delivery'] == 'With tragic bewilderment.'
    assert two['quality']['emotional_quality'] == 'not_assessed'
    assert two['quality']['asr'] == 'not_run'


@pytest.mark.parametrize('summary', [False, True])
def test_selected_take_reuses_exact_bytes_without_model_or_cache(voice, request_data, tmp_path, summary):
    one = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    shutil.rmtree(request_data['cache_dir'])
    for line in request_data['lines']:
        line['selected_take'] = {'manifest': str(tmp_path / 'one/manifest.json'), 'line_id': line['id']}
    # Default session may not load dependencies or resolve current model for explicit reuse.
    two = voice.run_batch(request_data, tmp_path / 'two')
    assert two['duration'] == one['duration']
    for before, after in zip(one['lines'], two['lines']):
        assert after['acceptance'] == 'caller_selected'
        assert after['selected_take_id'] == before['selected_take_id']
        assert after['takes'][0]['polished']['sha256'] == before['takes'][0]['polished']['sha256']
    completed = subprocess.run([sys.executable, '-m', 'harness.voice', '-', str(tmp_path / 'cli')]
                               + (['--summary'] if summary else []),
                               input=json.dumps(request_data), capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    stdout = json.loads(completed.stdout)
    disk = json.loads((tmp_path / 'cli/manifest.json').read_text())
    assert stdout['duration'] == .5
    if summary:
        assert stdout['manifest'] == str(tmp_path / 'cli/manifest.json')
        assert len(completed.stdout) < len(json.dumps(disk)) / 2
        for entry, full in zip(stdout['lines'], disk['lines']):
            for key in ('id', 'speaker', 'text', 'voice', 'selected_take_id', 'duration'):
                assert entry[key] == full[key]
            selected = next(t for t in full['takes'] if t['id'] == full['selected_take_id'])
            for key in ('frames', 'active_start_sample', 'active_end_sample'):
                assert entry[key] == selected['polished'][key]
            for kind in ('raw', 'polished'):
                assert entry[kind] == str(tmp_path / 'cli' / selected[kind]['path'])
                assert Path(entry[kind]).is_file()
            assert 'takes' not in entry
        assert 'recipe' in disk['lines'][0]['takes'][0]
    else:
        assert stdout == disk


@pytest.mark.parametrize('change', ['text', 'voice', 'raw', 'polished', 'duration'])
def test_selected_take_fails_closed_on_mismatch_or_corruption(voice, request_data, tmp_path, change):
    first = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    line = request_data['lines'][0]
    line['selected_take'] = {'manifest': str(tmp_path / 'one/manifest.json'), 'line_id': 'hello'}
    if change in ('text', 'voice'):
        line[change] = 'Other words.' if change == 'text' else 'am_puck'
    elif change == 'duration':
        first['lines'][0]['takes'][0]['polished']['duration'] = 999
        (tmp_path / 'one/manifest.json').write_text(json.dumps(first))
    else:
        (tmp_path / 'one' / first['lines'][0]['takes'][0][change]['path']).write_bytes(b'bad')
    with pytest.raises(ValueError):
        voice.run_batch(request_data, tmp_path / 'two')


def test_one_targeted_defect_retry_is_separate_from_audition_budget(voice, request_data, tmp_path):
    request_data.update(effort='low')
    request_data['lines'] = request_data['lines'][:1]
    request_data['lines'][0]['defect_retry'] = {'reason': 'Silence on the first phrasing.',
                                               'settings': {'speed': .9}}
    session = FakeSession(silent=1)
    result = voice.run_batch(request_data, tmp_path / 'out', session=session)
    assert len(session.calls) == 2
    assert result['lines'][0]['takes'][0]['settings']['speed'] == .9
    assert result['lines'][0]['attempts'][0]['defect'] == 'silent'
    assert result['lines'][0]['attempts'][1]['kind'] == 'defect_retry'
    assert result['lines'][0]['duration'] == pytest.approx(13333 / 48000)


def test_persistent_defect_stops_after_one_retry(voice, request_data, tmp_path):
    request_data['lines'] = request_data['lines'][:1]
    request_data['lines'][0]['defect_retry'] = {'reason': 'Silence.', 'settings': {'speed': .9}}
    session = FakeSession(silent=100)
    with pytest.raises(ValueError, match='usable take'):
        voice.run_batch(request_data, tmp_path / 'out', session=session)
    assert len(session.calls) == 2
    assert not (tmp_path / 'out/manifest.json').exists()


def test_profile_conflicts_and_bad_later_lines_fail_before_synthesis(voice, request_data, tmp_path):
    session = FakeSession()
    request_data['lines'][1]['voice'] = 'am_puck'
    with pytest.raises(ValueError, match='profile'):
        voice.run_batch(request_data, tmp_path / 'out', session=session)
    assert session.calls == []


def test_unavailable_provider_never_falls_back(voice, request_data, tmp_path):
    class Missing(FakeSession):
        def identity(self, request):
            raise ImportError('Chatterbox is not installed')
    request_data.update(provider='chatterbox', voice_profiles={'GUY': {'voice': 'default'}})
    with pytest.raises(ImportError, match='Chatterbox'):
        voice.run_batch(request_data, tmp_path / 'out', session=Missing())


def test_select_nondefault_audition_and_copy_manifest_tree(voice, request_data, tmp_path):
    request_data['lines'] = request_data['lines'][:1]
    request_data['lines'][0]['auditions'] = [{'speed': 1}, {'speed': .8}]
    original = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    shutil.copytree(tmp_path / 'one', tmp_path / 'relocated')
    shutil.rmtree(tmp_path / 'one')
    take = original['lines'][0]['takes'][1]
    request_data['lines'][0].pop('auditions')
    request_data['lines'][0]['selected_take'] = {
        'manifest': str(tmp_path / 'relocated/manifest.json'), 'take_id': take['id']}
    selected = voice.run_batch(request_data, tmp_path / 'selected')
    assert selected['duration'] == .3125
    assert selected['lines'][0]['takes'][0]['polished']['sha256'] == take['polished']['sha256']


def test_selected_manifest_cannot_traverse_outside_artifact_directory(voice, request_data, tmp_path):
    original = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    take = original['lines'][0]['takes'][0]
    shutil.copyfile(tmp_path / 'one' / take['raw']['path'], tmp_path / 'outside.wav')
    take['raw']['path'] = '../outside.wav'
    (tmp_path / 'one/manifest.json').write_text(json.dumps(original))
    request_data['lines'][0]['selected_take'] = {'manifest': str(tmp_path / 'one/manifest.json')}
    with pytest.raises(ValueError, match='escapes'):
        voice.run_batch(request_data, tmp_path / 'two')


def test_same_revision_different_weights_and_polish_invalidate_cache(voice, request_data, tmp_path):
    class Weights(FakeSession):
        def identity(self, request):
            return {**super().identity(request), 'files': {'weights': 'modified-weights'}}
    one = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    changed = Weights()
    two = voice.run_batch(request_data, tmp_path / 'two', session=changed)
    assert len(changed.calls) == 2
    assert one['lines'][0]['selected_take_id'] != two['lines'][0]['selected_take_id']
    request_data['polish'] = False
    dry = voice.run_batch(request_data, tmp_path / 'dry', session=changed)
    assert len(changed.calls) == 4
    take = dry['lines'][0]['takes'][0]
    assert take['raw']['sha256'] == take['polished']['sha256']


def test_defects_without_targeted_changes_are_not_blindly_retried(voice, request_data, tmp_path):
    session = FakeSession(silent=100)
    with pytest.raises(ValueError, match='usable take'):
        voice.run_batch(request_data, tmp_path / 'one', session=session)
    assert len(session.calls) == 1


def test_concurrent_batches_publish_whole_cache_entries(voice, request_data, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    barrier = threading.Barrier(2)
    class Concurrent(FakeSession):
        def synthesize(self, request, output):
            barrier.wait(timeout=10)
            return super().synthesize(request, output)
    request_data['lines'] = request_data['lines'][:1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(voice.run_batch, request_data, tmp_path / name, session=Concurrent())
                   for name in ('one', 'two')]
        results = [future.result() for future in futures]
    assert results[0]['duration'] == results[1]['duration'] == .25
    assert results[0]['lines'][0]['selected_take_id'] == results[1]['lines'][0]['selected_take_id']
    again = FakeSession()
    voice.run_batch(request_data, tmp_path / 'three', session=again)
    assert again.calls == []


def test_direct_call_keeps_single_take_sidecars_without_model_dependencies(tmp_path):
    from harness.audio import generate
    class Synthesis(FakeSession):
        def synthesize(self, request, output):
            settings = {'speed': 1.0, **request}
            super().synthesize(settings, output)
            shutil.copyfile(output, output.with_suffix('.native.wav'))
            return {'identity': self.identity(settings)}
    result = generate({'provider': 'kokoro', 'text': 'Hi.', 'polish': False},
                      tmp_path / 'take.wav', session=Synthesis())
    assert result['duration'] == .25
    assert (tmp_path / 'take.dry.wav').read_bytes() == (tmp_path / 'take.wav').read_bytes()
    assert (tmp_path / 'take.native.wav').is_file()
    assert json.loads((tmp_path / 'take.json').read_text())['resolved_revision'] == 'a' * 40


def test_selected_chatterbox_take_needs_no_original_reference(voice, request_data, tmp_path):
    reference = tmp_path / 'reference.wav'
    wav(reference)
    request_data.update(provider='chatterbox', voice_profiles={
        'GUY': {'voice': 'guy-established', 'reference': str(reference)}})
    original = voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    reference.unlink()
    del request_data['voice_profiles']['GUY']['reference']
    for line in request_data['lines']:
        line['selected_take'] = {'manifest': str(tmp_path / 'one/manifest.json')}
    selected = voice.run_batch(request_data, tmp_path / 'two')
    assert selected['lines'][0]['selected_take_id'] == original['lines'][0]['selected_take_id']


def test_selected_take_rejects_explicit_reference_change(voice, request_data, tmp_path):
    reference = tmp_path / 'reference.wav'
    wav(reference)
    request_data.update(provider='chatterbox', voice_profiles={
        'GUY': {'voice': 'guy-established', 'reference': str(reference)}})
    voice.run_batch(request_data, tmp_path / 'one', session=FakeSession())
    wav(reference, frames=6000)
    for line in request_data['lines']:
        line['selected_take'] = {'manifest': str(tmp_path / 'one/manifest.json')}
    with pytest.raises(ValueError, match='reference'):
        voice.run_batch(request_data, tmp_path / 'two')
