"""Procedural ambience and foley for ad mixes: original synthesis, no sample libraries.

Runs on NumPy alone, so the voice interpreter can use it. A *sounds* plan is part of the
animator's direction and is placed against the measured dialogue:

    {"ambience": "hall",                       # hall | room | outdoor | none
     "events": [{"name": "page_turn", "after_line": 1, "offset": 0.3},
                {"name": "slam", "at": 18.2},
                {"name": "shush", "after_line": 8, "offset": 0.7}]}

Each event uses "at" (seconds) or "after_line"/"before_line" (0-based index into
direction.lines) plus an optional "offset" and "gain_db" (-12..+6). The bed is
levelled for harness.mix at BED_GAIN_DB, so dialogue stays the lead under the
controller's mix gates: the bed sits about 20-30 dB under speech, and the loudest
event, a slam with its echo, matches speech instead of burying it.

    python -m harness.foley sounds.json bed.wav --duration 24.5 [--timeline timeline.json]
"""
import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np

RATE = 48000
BED_GAIN_DB = -12            # harness.mix caps a bed at -12 dB; levels below assume it
AMBIENCES = ('hall', 'room', 'outdoor', 'none')


def _band(x, lo=None, hi=None):
    """Zero-phase FFT band-limit with soft edges (no SciPy in the voice environment)."""
    n = len(x)
    if n == 0:
        return x
    spectrum = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / RATE)
    mask = np.ones_like(f)
    if lo:
        mask *= 1 / (1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi:
        mask *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(spectrum * mask, n)


def _convolve(x, ir):
    n = len(x) + len(ir) - 1
    size = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]


def _ir(seconds, decay, lo, hi, seed):
    """Diffuse tail with a few early reflections: the size of the space."""
    rng = np.random.default_rng(seed)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    tail = _band(rng.standard_normal(n), lo, hi) * np.exp(-t * 6.9 / decay)
    for delay, gain in ((0.043, .5), (0.071, .38), (0.118, .3), (0.167, .22), (0.231, .16)):
        if int(delay * RATE) < n:
            tail[int(delay * RATE)] += gain * 40
    tail[0] = 0
    return tail / np.sqrt((tail ** 2).sum())


SPACES = {'hall': (5.0, 4.2, 90, 4200, .9), 'room': (1.1, 0.8, 150, 6000, .35),
          'outdoor': (0.4, 0.25, 200, 8000, .08), 'none': (0.3, 0.2, 200, 8000, 0.0)}


def _norm(x):
    peak = np.abs(x).max()
    return x / peak if peak > 0 else x


def page_turn(rng):
    n = int(.5 * RATE); t = np.arange(n) / RATE
    rustle = _band(rng.standard_normal(n), 900, 7000) * np.exp(-((t - .18) / .13) ** 2)
    crinkle = np.zeros(n)
    for at in rng.uniform(.04, .34, 14):
        i = int(at * RATE)
        crinkle[i:i + 400] += (_band(rng.standard_normal(400), 2500, 9000) * np.hanning(400))[:n - i] * rng.uniform(.3, 1)
    flap = np.zeros(n); i = int(.36 * RATE); m = int(.08 * RATE)
    flap[i:i + m] = _band(rng.standard_normal(m), 120, 900) * np.exp(-np.arange(m) / RATE / .018)
    return _norm(.6 * rustle + .35 * crinkle + .9 * flap)


def slam(rng):
    n = int(.6 * RATE); t = np.arange(n) / RATE
    thump = np.sin(2 * np.pi * (85 * t - 30 * t ** 2)) * np.exp(-t / .09)
    slap = _band(rng.standard_normal(n), 300, 4200) * np.exp(-t / .022)
    crack = _band(rng.standard_normal(n), 2000, 9000) * np.exp(-t / .006)
    return _norm(.9 * thump + .8 * slap + .35 * crack)


def thud(rng):
    n = int(.35 * RATE); t = np.arange(n) / RATE
    body = np.sin(2 * np.pi * (70 * t - 20 * t ** 2)) * np.exp(-t / .06)
    return _norm(body + .3 * _band(rng.standard_normal(n), 200, 2000) * np.exp(-t / .015))


def shush(rng):
    seconds = .95; n = int(seconds * RATE); t = np.arange(n) / RATE
    env = np.minimum(1, t / .05) * np.clip((seconds - t) / .45, 0, 1) ** 1.5
    hiss = _band(rng.standard_normal(n), 1800, 7500) + .4 * _band(rng.standard_normal(n), 3500, 5200)
    return _norm(hiss * env)


def tick(rng):
    n = int(.12 * RATE); t = np.arange(n) / RATE
    return _norm((np.sin(2 * np.pi * 2100 * t) * .5 + _band(rng.standard_normal(n), 1500, 6000)) * np.exp(-t / .008))


def creak(rng):
    n = int(.9 * RATE); t = np.arange(n) / RATE
    f = 180 + 60 * np.sin(2 * np.pi * 1.3 * t)
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(f) / RATE)) * (rng.uniform(.6, 1, n))
    return _norm(_band(tone, 300, 3000) * np.sin(np.pi * t / t[-1]) ** 2)


# name: (generator, loudest-400ms level in the bed file dBFS, reverb send)
EFFECTS = {'page_turn': (page_turn, -12, .5), 'slam': (slam, -4, 1.0), 'thud': (thud, -6, .7),
           'shush': (shush, -14, 1.4), 'tick': (tick, -22, .9), 'creak': (creak, -12, .8)}


def _window_db(x):
    window = int(.4 * RATE)
    best = max((np.sqrt(np.mean(x[i:i + window] ** 2)) for i in range(0, max(1, len(x) - window + 1), RATE // 20)),
               default=0)
    return 20 * math.log10(max(best, 1e-9))


def resolve(events, lines):
    """Seconds for each event, using measured line starts/ends (dicts with start/end seconds)."""
    out = []
    for i, event in enumerate(events or []):
        if not isinstance(event, dict) or event.get('name') not in EFFECTS:
            raise ValueError(f'sounds.events[{i}].name must be one of {sorted(EFFECTS)}')
        offset = float(event.get('offset', 0))
        anchors = [k for k in ('at', 'after_line', 'before_line') if k in event]
        if len(anchors) != 1:
            raise ValueError(f'sounds.events[{i}] needs exactly one of at, after_line, before_line')
        if 'at' in event:
            at = float(event['at'])
        else:
            index = event[anchors[0]]
            if type(index) is not int or not 0 <= index < len(lines):
                raise ValueError(f'sounds.events[{i}].{anchors[0]} must index direction.lines')
            at = lines[index]['end' if anchors[0] == 'after_line' else 'start']
        gain = float(event.get('gain_db', 0))
        if not -12 <= gain <= 6:
            raise ValueError(f'sounds.events[{i}].gain_db must be -12..6')
        out.append({'name': event['name'], 'at': round(max(0.0, at + offset), 4), 'gain_db': gain})
    return out


def render(duration, sounds, lines=(), seed=2002):
    """Return (stereo float array at RATE, resolved events)."""
    sounds = sounds or {}
    ambience = sounds.get('ambience', 'room')
    if ambience not in AMBIENCES:
        raise ValueError(f'sounds.ambience must be one of {AMBIENCES}')
    rng = np.random.default_rng(seed)
    n = int(round(duration * RATE))
    events = resolve(sounds.get('events', []), list(lines))
    space = SPACES[ambience]
    ir = _ir(*space[:4], seed=seed + 1)
    left = np.zeros(n); right = np.zeros(n)
    if ambience != 'none':
        air_lo, air_hi = {'hall': (40, 420), 'room': (60, 900), 'outdoor': (80, 2400)}[ambience]
        air = _band(rng.standard_normal(n), air_lo, air_hi)
        air *= 10 ** (-35 / 20) / max(1e-9, np.sqrt(np.mean(air ** 2)))
        left += air; right += np.roll(air, 997) * .95
    for event in events:
        make, level, send = EFFECTS[event['name']]
        dry = make(rng)
        dry *= 10 ** ((level + event['gain_db']) / 20) / 10 ** (_window_db(dry) / 20)
        dry = .9 * np.tanh(dry / .9)   # soft-limit the transient instead of scaling the whole bed down
        placed = np.zeros(n); i = int(event['at'] * RATE)
        if i >= n:
            continue
        placed[i:i + len(dry)] = dry[:n - i]
        wet = _convolve(placed, ir) * space[4] * send if space[4] else 0
        left += placed + wet
        right += placed * .96 + (np.roll(wet, 331) if space[4] else 0)
    bed = np.stack([left, right], 1)
    peak = np.abs(bed).max()
    if peak > .98:
        bed *= .98 / peak
    return bed, events


def write(path, bed):
    pcm = (np.clip(bed, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('sounds'); parser.add_argument('output')
    parser.add_argument('--duration', type=float, required=True)
    parser.add_argument('--timeline', help='harness timeline.json for after_line/before_line anchors')
    a = parser.parse_args(argv)
    sounds = json.loads(Path(a.sounds).read_text())
    lines = []
    if a.timeline:
        t = json.loads(Path(a.timeline).read_text())
        lines = [{'start': l['start_sample'] / t['sample_rate'], 'end': l['end_sample'] / t['sample_rate']}
                 for l in t['dialogue']]
    bed, events = render(a.duration, sounds, lines)
    write(a.output, bed)
    print(json.dumps({'output': a.output, 'events': events, 'bed_gain_db': BED_GAIN_DB}))


if __name__ == '__main__':
    main()
