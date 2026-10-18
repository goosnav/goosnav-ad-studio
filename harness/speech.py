"""Can a viewer understand the ad? Measured, not reported.

check_speech: a local Whisper model (harness/asr.py in the audio environment) transcribes
each dialogue window; the planned words have to be there.
normalize_loudness: the finished film is set to social-video loudness so quiet dialogue is
not a playback-volume problem.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile

from .contracts import ContractError

LINE_RECALL = 0.5      # each line: at least half its words recognised
TOTAL_RECALL = 0.8     # the whole ad: four words in five
TRUE_PEAK = -1.5       # dBTP ceiling after normalisation


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace('\u2019', "'"))


def heard(planned, transcript):
    """Share of planned words found in the transcript (endings may differ on longer words)."""
    want, got = words(planned), words(transcript)
    found = 0
    for w in want:
        match = next((i for i, g in enumerate(got) if g == w or
                      (min(len(g), len(w)) >= 4 and (g.startswith(w) or w.startswith(g)))), None)
        if match is not None:
            found += 1; got.pop(match)
    return round(found / len(want), 2) if want else 1.0


def transcribe(media, windows, config):
    """Texts heard in each (start, end) window of any audio/video file."""
    python = config['audio']['python']
    if not python or not Path(python).is_file():
        raise ContractError('Speech check needs audio.python (the local model environment); see dev/OPERATIONS.md')
    with tempfile.TemporaryDirectory() as tmp:
        wav, request, result = Path(tmp) / 'speech.wav', Path(tmp) / 'request.json', Path(tmp) / 'result.json'
        subprocess.run([config['tools']['ffmpeg'], '-v', 'error', '-y', '-i', str(media), '-ac', '1', '-ar', '16000',
                        str(wav)], check=True, timeout=300)
        request.write_text(json.dumps({'wav': str(wav), 'windows': windows, 'model': config['audio']['asr_model']}))
        r = subprocess.run([python, str(Path(__file__).with_name('asr.py')), str(request), str(result)],
                           capture_output=True, text=True, timeout=1800)
        if r.returncode or not result.is_file():
            raise ContractError(f'Speech recogniser failed: {r.stderr[-800:]}')
        return json.loads(result.read_text())['texts']


def check_speech(media, timeline, config):
    rate = timeline['sample_rate']
    dialogue = timeline.get('dialogue') or []
    if not dialogue:
        return {'lines': [], 'recall': 1.0}
    # A little air either side: measured line edges can clip a first or last consonant.
    windows = [[l['start_sample'] / rate - 0.3, l['end_sample'] / rate + 0.3] for l in dialogue]
    texts = transcribe(media, windows, config)
    lines = [{'speaker': l['speaker'], 'planned': l['text'], 'heard': t.strip(), 'recall': heard(l['text'], t)}
             for l, t in zip(dialogue, texts)]
    planned = sum(len(words(l['text'])) for l in dialogue) or 1
    total = round(sum(x['recall'] * len(words(x['planned'])) for x in lines) / planned, 2)
    bad = [f'"{x["planned"]}" was heard as "{x["heard"]}"' for x in lines if x['recall'] < LINE_RECALL]
    if bad or total < TOTAL_RECALL:
        raise ContractError('Dialogue is not intelligible to a speech recogniser '
                            f'({total:.0%} of words heard): ' + '; '.join(bad or [x['planned'] + ' -> ' + x['heard'] for x in lines]) +
                            '. Clarify the takes (EQ, pace, level over the bed, no voice filtering).')
    return {'lines': lines, 'recall': total, 'model': config['audio']['asr_model']}


PRESENCE_DB = -13.0    # share of a line's energy in 2-5 kHz (consonants), about 5 %


def _mean_db(media, start, end, band):
    r = subprocess.run(['ffmpeg', '-nostats', '-ss', str(max(0, start)), '-t', str(end - start), '-i', str(media),
                        '-af', f'{band},volumedetect', '-f', 'null', '-'], capture_output=True, text=True, timeout=120)
    m = re.search(r'mean_volume: (-?[\d.]+|-inf) dB', r.stderr)
    return float(m[1]) if m and m[1] != '-inf' else -120.0


def presence_db(media, start, end):
    """Consonant band (2-5 kHz) level relative to the whole voice band (80 Hz-8 kHz), in dB."""
    return round(_mean_db(media, start, end, 'highpass=f=2000:poles=2,lowpass=f=5000:poles=2')
                 - _mean_db(media, start, end, 'highpass=f=80,lowpass=f=8000'), 1)


def check_presence(stem, timeline):
    rate = timeline['sample_rate']
    lines = [{'speaker': l['speaker'], 'text': l['text'],
              'presence_db': presence_db(stem, l['start_sample'] / rate, l['end_sample'] / rate)}
             for l in timeline.get('dialogue') or []]
    dull = [f'"{x["text"]}" ({x["speaker"]}) {x["presence_db"]} dB' for x in lines if x['presence_db'] < PRESENCE_DB]
    if dull:
        raise ContractError(f'Voices are muffled (2-5 kHz presence under {PRESENCE_DB} dB): ' + '; '.join(dull) +
                            '. Use the polished takes (audio.py polishes by default), add presence EQ, or recast '
                            'with a clearer voice (am_michael, bm_lewis, am_adam, bf_emma, af_heart).')
    return lines


def loudness(media):
    r = subprocess.run(['ffmpeg', '-nostats', '-i', str(media), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True, timeout=600)
    summary = r.stderr[r.stderr.rfind('Summary:'):]
    i = re.search(r'I:\s+(-?[\d.]+) LUFS', summary); p = re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summary)
    if not i or not p:
        raise ContractError('Could not measure loudness')
    return {'integrated': float(i[1]), 'true_peak': float(p[1]) if p[1] != '-inf' else -120.0}


def normalize_loudness(media, config, passes=3):
    """Set integrated loudness in place: measured gain, then a peak limiter under the true-peak
    ceiling, re-measured until within 0.75 LU. (Two-pass loudnorm undershoots badly on 10 s ads
    with sharp effects: -19.9 LUFS for a -14 target.) The picture is copied untouched."""
    target = config['output']['loudness']
    media = Path(media)
    ceiling = 10 ** ((TRUE_PEAK - 1.0) / 20)   # sample-peak limit 1 dB under the true-peak ceiling
    level = loudness(media)
    for _ in range(passes):
        if abs(level['integrated'] - target) <= 0.75 and level['true_peak'] <= TRUE_PEAK + 0.3:
            break
        gain = target - level['integrated']
        out = media.with_suffix('.loudnorm' + media.suffix)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(media), '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy',
                        '-af', f'volume={gain:.2f}dB,alimiter=limit={ceiling:.4f}:attack=1:release=50:level=0,'
                        'aresample=48000', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart',
                        str(out)], check=True, timeout=600)
        out.replace(media)
        level = loudness(media)
    return level
