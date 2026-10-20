import pytest
from harness.audio import validate_request


def test_audio_request_rejects_missing_text_or_unknown_provider():
    with pytest.raises(ValueError):validate_request({'provider':'kokoro','text':''})
    with pytest.raises(ValueError):validate_request({'provider':'whatever','text':'hi'})
    assert validate_request({'provider':'kokoro','text':'hello','voice':'af_heart'})['provider']=='kokoro'


def test_no_automatic_piper_downgrade():
    with pytest.raises(ValueError):validate_request({'provider':'piper','text':'hi'})


@pytest.mark.parametrize('settings', [
    {'speed': 0}, {'speed': float('nan')}, {'speed': True}, {'seed': -1},
    {'threads': 0}, {'pauses': {'after': -1}}, {'pauses': {'between': 1}},
    {'phrasing': ['Different words.']}, {'phrasing': []},
    {'provider': 'chatterbox', 'speed': 1.2},
    {'provider': 'chatterbox', 'voice': 'am_onyx'},
])
def test_invalid_voice_controls_fail_before_model_loading(settings):
    with pytest.raises(ValueError):
        validate_request({'provider': 'kokoro', 'text': 'One. Two.', **settings})


def test_explicit_phrasing_and_pauses_preserve_spoken_words():
    request = {'provider': 'kokoro', 'text': 'One. Two.', 'phrasing': ['One.', 'Two.'],
               'pauses': {'before': .1, 'between': .2, 'after': .3}, 'speed': .9}
    assert validate_request(request) == request


def test_measure_pcm_counts_real_frames_and_detects_truncation(tmp_path):
    import struct
    import wave
    from harness import audio
    path = tmp_path / 'sample.wav'
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        stream.writeframes(struct.pack('<h', 4096) * 12000)
    assert hasattr(audio, 'measure_wav'), 'PCM measurement API is missing'
    measured = audio.measure_wav(path)
    assert measured['duration'] == .25
    assert measured['frames'] == 12000
    assert measured['peak'] == .125
    path.write_bytes(path.read_bytes()[:-2])
    with pytest.raises(ValueError, match='truncated'):
        audio.measure_wav(path)


def test_phrase_pauses_are_real_samples_and_each_segment_is_checked():
    import numpy as np
    from harness import audio
    assert hasattr(audio, 'assemble_phrases'), 'Measured phrase assembly is missing'
    segments = {'One.': np.ones(2400) * .1, 'Two.': np.ones(4800) * .2}
    signal = audio.assemble_phrases(['One.', 'Two.'], segments.__getitem__, 24000,
                                   {'before': .1, 'between': .2, 'after': .3})
    assert len(signal) == 21600  # .1 + .1 + .2 + .2 + .3 seconds
    assert np.count_nonzero(signal[:2400]) == 0
    assert np.allclose(signal[2400:4800], .1)
    assert np.count_nonzero(signal[4800:9600]) == 0
    assert np.allclose(signal[9600:14400], .2)
    assert np.count_nonzero(signal[14400:]) == 0
    for segment, reason in [(np.zeros(100), 'silent'), (np.array([]), 'empty'),
                            (np.array([float('nan')]), 'non-finite')]:
        with pytest.raises(audio.AudioDefect, match=reason):
            audio.assemble_phrases(['bad'], lambda text: segment, 24000, {})


def test_identity_hashes_actual_local_files_and_resolves_moving_ref_per_session(tmp_path, monkeypatch):
    import hashlib
    import sys
    from types import SimpleNamespace
    from harness.audio import AudioSession
    snapshots = {}
    for revision in ('a' * 40, 'b' * 40):
        folder = tmp_path / revision
        (folder / 'voices').mkdir(parents=True)
        (folder / 'config.json').write_text('{}')
        (folder / 'kokoro-v1_0.pth').write_bytes(revision.encode())
        (folder / 'voices/af_heart.pt').write_bytes(b'voice')
        snapshots[revision] = str(folder)
    current = ['a' * 40]
    def download(repo, *, revision, allow_patterns, local_files_only):
        assert local_files_only is True
        return snapshots[current[0] if revision == 'main' else revision]
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=download))
    monkeypatch.setattr('importlib.metadata.version', lambda package: 'fixture-version')
    request = {'provider': 'kokoro', 'text': 'Hi.'}
    session = AudioSession()
    first = session.identity(request)
    assert first['files']['voices/af_heart.pt'] == hashlib.sha256(b'voice').hexdigest()
    current[0] = 'b' * 40
    assert session.identity(request)['resolved_revision'] == 'a' * 40  # frozen batch
    assert AudioSession().identity(request)['resolved_revision'] == 'b' * 40
    (tmp_path / ('a' * 40) / 'voices/af_heart.pt').write_bytes(b'changed-voice')
    changed = session.identity(request)
    assert changed['files']['voices/af_heart.pt'] == hashlib.sha256(b'changed-voice').hexdigest()
