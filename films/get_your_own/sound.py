"""GET YOUR OWN: place measured voice takes on the cut and build the sound design.

python3 films/get_your_own/sound.py films/get_your_own/cut.json WORKDIR

Takes are referenced as "<manifest dir>:<line id>:<speed>" relative to WORKDIR (the
harness.voice batch outputs). Writes WORKDIR/audio/{mix.wav, dialogue_stem.wav,
timeline.json, mouths.json}. Effects are synthesized here: no library samples.
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from harness.lipsync import mouth_curves  # noqa: E402

RATE = 48000
rng = np.random.default_rng(2002)


def band(x, lo=None, hi=None, order=4):
    if lo and hi:
        sos = butter(order, [lo, hi], 'bandpass', fs=RATE, output='sos')
    elif lo:
        sos = butter(order, lo, 'highpass', fs=RATE, output='sos')
    else:
        sos = butter(order, hi, 'lowpass', fs=RATE, output='sos')
    return sosfilt(sos, x)


def db(value):
    return 10 ** (value / 20)


def read_wav(path):
    with wave.open(str(path)) as w:
        raw = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            raw = raw.reshape(-1, w.getnchannels()).mean(1)
        if w.getframerate() != RATE:
            raise SystemExit(f'{path}: expected {RATE} Hz')
    return raw


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(str(path), 'w') as w:
        w.setnchannels(1 if pcm.ndim == 1 else pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def take(work, ref):
    folder, line_id, speed = ref.split(':')
    manifest = json.loads((work / folder / 'manifest.json').read_text())
    line = next(l for l in manifest['lines'] if l['id'] == line_id)
    chosen = next(t for t in line['takes'] if abs(t['settings']['speed'] - float(speed)) < 1e-6)
    p = chosen['polished']
    x = read_wav(work / folder / p['path'])
    a = max(0, p['active_start_sample'] - int(.03 * RATE))
    b = min(len(x), p['active_end_sample'] + int(.06 * RATE))
    return x[a:b], {'manifest': f'{folder}/manifest.json', 'take_id': chosen['id'],
                    'voice': chosen['settings']['voice'], 'speed': chosen['settings']['speed'],
                    'seed': chosen['settings']['seed'], 'model': chosen['settings']['model']}


def hall_ir(seconds, decay, lo=180, hi=5200, seed=1):
    """Diffuse stone-hall tail; a few early reflections give the vault its size."""
    n = int(seconds * RATE)
    r = np.random.default_rng(seed)
    t = np.arange(n) / RATE
    tail = band(r.standard_normal(n), lo, hi) * np.exp(-t * 6.9 / decay)
    for delay, gain in ((0.043, .5), (0.071, .38), (0.118, .3), (0.167, .22), (0.231, .16)):
        tail[int(delay * RATE)] += gain * 40
    tail[0] = 0
    return tail / np.sqrt((tail ** 2).sum())


def page_turn(seconds=0.5):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    rustle = band(rng.standard_normal(n), 900, 7000) * np.exp(-((t - .18) / .13) ** 2)
    crinkle = np.zeros(n)
    for at in rng.uniform(.04, .34, 14):
        i = int(at * RATE)
        burst = band(rng.standard_normal(400), 2500, 9000) * np.hanning(400)
        crinkle[i:i + 400] += burst[:max(0, n - i)] * rng.uniform(.3, 1)
    flap = np.zeros(n)
    i = int(.36 * RATE); m = int(.08 * RATE)
    flap[i:i + m] = band(rng.standard_normal(m), 120, 900) * np.exp(-np.arange(m) / RATE / .018)
    out = .6 * rustle + .35 * crinkle + .9 * flap
    return out / np.abs(out).max()


def slam():
    n = int(.6 * RATE)
    t = np.arange(n) / RATE
    thump = np.sin(2 * np.pi * (85 * t - 30 * t ** 2)) * np.exp(-t / .09)
    slap = band(rng.standard_normal(n), 300, 4200) * np.exp(-t / .022)
    crack = band(rng.standard_normal(n), 2000, 9000) * np.exp(-t / .006)
    out = .9 * thump + .8 * slap + .35 * crack
    return out / np.abs(out).max()


def shush(seconds=0.95):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    env = np.minimum(1, t / .05) * np.clip((seconds - t) / .45, 0, 1) ** 1.5
    hiss = band(rng.standard_normal(n), 1800, 7500) + .4 * band(rng.standard_normal(n), 3500, 5200)
    return hiss * env / np.abs(hiss * env).max()


def tick(seconds=0.12, f=2300):
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    return (np.sin(2 * np.pi * f * t) * .5 + band(rng.standard_normal(n), 1500, 6000)) * np.exp(-t / .008)


def place(buffer, x, at, gain=1.0):
    i = int(round(at * RATE))
    j = min(len(buffer), i + len(x))
    buffer[i:j] += gain * x[:j - i]


def main():
    cut_path, work = Path(sys.argv[1]), Path(sys.argv[2]).expanduser()
    cut = json.loads(cut_path.read_text())
    n = int(cut['duration'] * RATE)
    out = work / 'audio'; out.mkdir(parents=True, exist_ok=True)

    dialogue = np.zeros(n)
    timeline = {'fps': cut['fps'], 'sample_rate': RATE, 'duration': cut['duration'],
                'dialogue': [], 'events': [], 'sound_rationale': (
                    'Dry, close dialogue in a vast stone reading room: room tone and a distant '
                    'clock establish the silence, page turns are the only action sounds, and the '
                    'slam is the one loud event, its echo filling the hall before a distant shush.')}
    for line in cut['lines']:
        x, meta = take(work, line['take'])
        x = band(x, 85)
        x *= db(-19) / max(1e-6, np.sqrt(np.mean(x[np.abs(x) > .02] ** 2)))   # loud-part RMS
        start = int(round(line['start'] * RATE))
        if start + len(x) > n:
            raise SystemExit(f'{line["id"]} runs past the end')
        if np.any(dialogue[start:start + len(x)] != 0):
            raise SystemExit(f'{line["id"]} overlaps another line')
        dialogue[start:start + len(x)] = x
        timeline['dialogue'].append({'id': line['id'], 'speaker': line['speaker'], 'text': line['text'],
                                     'start_sample': start, 'end_sample': start + len(x), **meta})

    small_room = hall_ir(1.1, .9, seed=3)
    big_hall = hall_ir(5.0, 4.2, lo=90, hi=4200, seed=5)
    voices = dialogue + .14 * fftconvolve(dialogue, small_room)[:n]

    left = np.zeros(n); right = np.zeros(n)
    # Room tone: low air, plus a far clock ticking once a second in the vault.
    air = band(rng.standard_normal(n), 40, 420) * db(-46)
    ticks = np.zeros(n)
    for k, at in enumerate(np.arange(.35, cut['duration'], 1.0)):
        place(ticks, tick(f=2300 if k % 2 else 1900), at, db(-36))
    far = fftconvolve(ticks, big_hall)[:n] * .9 + ticks * .15
    effects_l = air + far * .8
    effects_r = air * .9 + far
    for event in cut['events']:
        if event['name'] == 'page_turn':
            sound = page_turn()
            place(effects_l, sound, event['at'], db(-20)); place(effects_r, sound, event['at'], db(-21))
            timeline['events'].append({'name': f'page turn (leaf {event["leaf"]})', 'sample': int(event['at'] * RATE)})
        elif event['name'] == 'slam':
            dry = np.zeros(n); place(dry, slam(), event['at'])
            boom = dry * db(-7) + fftconvolve(dry, big_hall)[:n] * db(-1)
            effects_l += boom; effects_r += boom * .96
            timeline['events'].append({'name': 'book slammed shut, hall echo', 'sample': int(event['at'] * RATE)})
        elif event['name'] == 'shush':
            dry = np.zeros(n); place(dry, shush(), event['at'])
            wet = fftconvolve(dry, big_hall)[:n]
            effects_l += dry * db(-34) + wet * db(-26)
            effects_r += dry * db(-27) + wet * db(-22)
            timeline['events'].append({'name': 'distant librarian: shh', 'sample': int(event['at'] * RATE)})
    # Fade the bed out under the end card's last moments.
    fade = np.ones(n); k = int(.8 * RATE); fade[-k:] = np.linspace(1, 0, k)
    mix = np.stack([(voices + effects_l) * fade, (voices + effects_r) * fade], 1)
    peak = np.abs(mix).max()
    if peak > .95:
        mix *= .95 / peak
        dialogue *= .95 / peak
    write_wav(out / 'mix.wav', mix)
    write_wav(out / 'dialogue_stem.wav', dialogue)
    (out / 'timeline.json').write_text(json.dumps(timeline, indent=2))
    mouths = mouth_curves(out / 'dialogue_stem.wav', timeline, cut['fps'])
    (out / 'mouths.json').write_text(json.dumps(mouths))
    print(json.dumps({'mix': str(out / 'mix.wav'), 'peak': round(float(np.abs(mix).max()), 3),
                      'lines': [(l['id'], round(l['start_sample'] / RATE, 2), round(l['end_sample'] / RATE, 2))
                                for l in timeline['dialogue']]}, indent=1))


if __name__ == '__main__':
    main()
