import json
import shutil
import subprocess

import pytest

from harness.config import load_config
from harness.contracts import ContractError
from harness.speech import heard, check_speech, loudness, normalize_loudness


def test_word_recall_tolerates_endings_but_not_missing_words():
    assert heard("We're leaving.", " We're leavings.") == 1.0
    assert heard("There's a hold on it.", " There's a hold on.") == 0.8
    assert heard('For who?', ' Four.') == 0.0


def timeline(*lines):
    return {'sample_rate': 48000, 'dialogue': [
        {'speaker': 'A', 'text': t, 'start_sample': int(a * 48000), 'end_sample': int(b * 48000)} for t, a, b in lines]}


def test_speech_gate_needs_every_line_heard(tmp_path, monkeypatch):
    c = load_config(None, {'audio': {'python': '/usr/bin/python3'}})
    t = timeline(("There's a hold on it.", 1, 2), ('For who?', 3, 4))
    monkeypatch.setattr('harness.speech.transcribe', lambda media, windows, config: [" There's a hold on it.", ' For who?'])
    assert check_speech('mix.wav', t, c)['recall'] == 1.0
    monkeypatch.setattr('harness.speech.transcribe', lambda media, windows, config: [" There's a hold on it.", ' Four.'])
    with pytest.raises(ContractError, match='For who'):
        check_speech('mix.wav', t, c)
    assert check_speech('mix.wav', timeline(), c)['lines'] == []


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires FFmpeg')
def test_loudness_is_normalised_for_social_video(tmp_path):
    quiet = tmp_path / 'quiet.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=64x64:rate=24', '-f', 'lavfi',
                    '-i', 'sine=frequency=500:sample_rate=48000', '-af', 'volume=-30dB', '-t', '3',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', str(quiet)], check=True)
    assert loudness(quiet)['integrated'] < -30
    normalize_loudness(quiet, load_config())
    m = loudness(quiet)
    assert abs(m['integrated'] + 14) < 1.0 and m['true_peak'] <= -1.0


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires FFmpeg')
def test_presence_gate_rejects_muffled_voices(tmp_path):
    from harness.speech import check_presence
    def make(name, source):
        path = tmp_path / f'{name}.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', source, '-t', '2', '-ar', '48000',
                        '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True)
        return path
    t = timeline(('Okay.', 0.5, 1.5))
    with pytest.raises(ContractError, match='muffled'):
        check_presence(make('dull', 'sine=frequency=180:sample_rate=48000'), t)
    assert check_presence(make('clear', 'anoisesrc=color=pink:sample_rate=48000'), t)[0]['presence_db'] > -13


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='requires FFmpeg')
def test_voice_polish_lifts_presence(tmp_path):
    from harness.audio import polish
    from harness.speech import presence_db
    dull = tmp_path / 'dull.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'anoisesrc=color=brown:sample_rate=48000', '-t', '2',
                    '-ac', '1', '-c:a', 'pcm_s16le', str(dull)], check=True)
    before = presence_db(dull, 0, 2)
    polish(dull, tmp_path / 'bright.wav')
    assert presence_db(tmp_path / 'bright.wav', 0, 2) > before + 3
