"""Mouth movement measured from the voices, not guessed by a worker.

The audio stage delivers a dialogue-only stem. The controller turns it into one jaw curve
per speaker (0 closed .. 1 wide, one value per film frame) and hands it to the animator,
who keys it with blender/lipsync.py. scene_check.py later verifies the result in the .blend.
"""
import array
import math
import wave

from .contracts import ContractError

LEVELS = (0.0, 0.45, 0.75, 1.0)   # cartoon mouth chart: shut, small, open, wide


def _frames_rms(path, fps):
    with wave.open(str(path)) as w:
        rate, channels, n = w.getframerate(), w.getnchannels(), w.getnframes()
        if w.getsampwidth() != 2:
            raise ContractError('dialogue stem must be PCM16')
        raw = array.array('h', w.readframes(n))
    if channels > 1:
        raw = array.array('h', (int(sum(raw[i:i + channels]) / channels) for i in range(0, len(raw), channels)))
    hop = rate / fps
    return rate, n, [math.sqrt(sum(v * v for v in raw[int(i * hop):int((i + 1) * hop)]) / max(1, int(hop)))
                     for i in range(int(n / hop))]


def mouth_curves(stem, timeline, fps):
    rate, n, rms = _frames_rms(stem, fps)
    if rate != timeline['sample_rate'] or abs(n / rate - timeline['duration']) > .05:
        raise ContractError('The dialogue stem must have the mix\'s sample rate and duration')
    speakers = {}
    for line in timeline['dialogue']:
        a = int(line['start_sample'] / rate * fps); b = min(len(rms), math.ceil(line['end_sample'] / rate * fps))
        window = rms[a:b]
        loud = sorted(window)[int(len(window) * .9)] if window else 0
        if loud < 100:
            raise ContractError(f'The dialogue stem is silent during "{line["text"]}"')
        curve = speakers.setdefault(line['speaker'], [0.0] * len(rms))
        for i, v in enumerate(window):
            r = v / loud
            curve[a + i] = LEVELS[0 if r < .15 else 1 if r < .45 else 2 if r < .8 else 3]
    for curve in speakers.values():
        # Drop one-frame flickers (open between two closed frames) so the jaw does not chatter.
        flicker = [i for i in range(1, len(curve) - 1) if curve[i] and not curve[i - 1] and not curve[i + 1]]
        for i in flicker:
            curve[i] = 0.0
    return {'fps': fps, 'frames': len(rms), 'speakers': speakers,
            'note': 'jaw openness 0..1 per frame, frame 0 = film start; apply with blender/lipsync.py'}
