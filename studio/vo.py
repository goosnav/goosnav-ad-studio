"""studio.vo: narration with Piper TTS.

lines file: one line per clip, `ID|text`. "..." inside a line becomes a real pause.

  python3 -m studio.vo LINES.txt OUTDIR [--voice en_US-ryan-high] [--slow 0.93] [--length 1.1]
                                        [--pause 0.55] [--reverb 0.32] [--warmth 0.35]

Writes vo_<ID>.wav (48 kHz, dry+room), dry_<ID>.wav, durations.json (spoken length per clip) and
gaps.json (silences > 0.22 s inside each clip: use them to time picture to sentences).
Needs the `piper` binary (see tools/setup.sh) and a voice .onnx in <cache>/voices.
"""
import argparse, json, os, subprocess, tempfile
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, resample_poly, butter, sosfilt

from studio import config

SR = 48000

# Piper voice licences (dataset licence from each voice's MODEL_CARD, checked 2026-09-29).
# Ads are commercial use: only SAFE voices may ship. build()/build_cast() refuse anything else
# unless allow_unsafe=True (for private tests only).
SAFE_VOICES = {
    'en_US-joe-medium': 'CC0',
    'en_US-norman-medium': 'public domain',
    'en_US-john-medium': 'public domain (fine-tuned from kristin)',
    'en_US-bryce-medium': 'public domain',
    'en_US-kristin-medium': 'public domain (LibriVox)',
    'en_US-ljspeech-high': 'public domain',
    'en_GB-cori-medium': 'public domain',
    'en_GB-jenny_dioco-medium': 'Jenny (Dioco) licence: commercial use permitted; attribution not required for distributed clips',
}
UNSAFE_VOICES = {
    'en_US-ryan-high': 'CC BY-NC-SA 4.0 (non-commercial)',
    'en_US-lessac-medium': 'Blizzard 2013 research licence (non-commercial)',
    'en_US-amy-medium': 'Mycroft mimic3, fine-tuned from lessac (unclear / research)',
    'en_GB-alan-medium': 'Mycroft mimic3: "All Rights Reserved"',
    'en_US-hfc_male-medium': 'CC BY-NC-SA 4.0', 'en_US-hfc_female-medium': 'CC BY-NC-SA 4.0',
}

def check_voice(voice, allow_unsafe=False):
    if voice in SAFE_VOICES or allow_unsafe:
        return
    why = UNSAFE_VOICES.get(voice, 'licence not vetted: check its MODEL_CARD and add it to SAFE_VOICES')
    raise SystemExit(f'voice {voice} is not cleared for commercial ads: {why}')

def synth(text, voice, length=1.1, sentence_silence=0.45):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        out = f.name
    subprocess.run([config.piper(), '-m', config.voice(voice), '--length_scale', str(length),
                    '--sentence_silence', str(sentence_silence), '-f', out],
                   input=text.encode(), check=True, capture_output=True)
    sr, x = wavfile.read(out)
    os.unlink(out)
    x = x.astype(np.float32) / 32768.0
    nz = np.where(np.abs(x) > 0.01)[0]
    return sr, x[max(nz[0] - 200, 0): nz[-1] + 800]

def process(text, voice, slow=0.93, length=1.1, pause=0.55, warmth=0.35):
    parts = [p.strip() for p in text.split('...') if p.strip()]
    chunks, sr = [], 22050
    for i, p in enumerate(parts):
        sr, x = synth(p, voice, length)
        chunks.append(x)
        if i < len(parts) - 1:
            chunks.append(np.zeros(int(sr * pause), np.float32))
    x = np.concatenate(chunks)
    # resample to 48 kHz while "tape slowing": lower pitch and slower delivery together
    fr = Fraction(SR / slow / sr).limit_denominator(4000)
    x = resample_poly(x, fr.numerator, fr.denominator)
    lo = sosfilt(butter(2, 220, 'lp', fs=SR, output='sos'), x)
    x = x + warmth * lo
    x = sosfilt(butter(2, 9000, 'lp', fs=SR, output='sos'), x)
    x = sosfilt(butter(2, 70, 'hp', fs=SR, output='sos'), x)
    return np.tanh(x * 1.8) / np.tanh(1.8)

def room_ir(seconds=3.2, decay=2.3, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * seconds); t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * decay)
    ir = sosfilt(butter(1, 3500, 'lp', fs=SR, output='sos'), ir)
    ir[: int(SR * 0.03)] *= np.linspace(0, 1, int(SR * 0.03))
    return ir / np.sqrt(np.sum(ir ** 2))

def gaps(x, thresh=0.012, min_gap=0.22):
    w = int(SR * 0.03)
    env = np.convolve(np.abs(x), np.ones(w) / w, 'same')
    quiet = env < thresh
    out, start = [], None
    for i in range(0, len(quiet), int(SR * 0.01)):
        if quiet[i] and start is None:
            start = i
        if not quiet[i] and start is not None:
            if (i - start) / SR > min_gap:
                out.append((round(start / SR, 2), round(i / SR, 2)))
            start = None
    return out

def build(lines, outdir, voice='en_US-norman-medium', slow=0.93, length=1.1, pause=0.55, reverb=0.32,
          warmth=0.35, room_seconds=3.2, room_decay=2.3):
    check_voice(voice)
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    ir = room_ir(room_seconds, room_decay)
    durs, gp = {}, {}
    for line in Path(lines).read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        n, text = line.split('|', 1)
        dry = process(text, voice, slow, length, pause, warmth)
        wet = fftconvolve(dry, ir)[: len(dry) + int(SR * 2.5)]
        dry = np.pad(dry, (0, len(wet) - len(dry)))
        dryn = dry / np.max(np.abs(dry)) * 0.9
        wavfile.write(outdir / f'dry_{n}.wav', SR, (dryn * 32767).astype(np.int16))
        y = 0.85 * dry + reverb * wet
        y = y / np.max(np.abs(y)) * 0.89
        wavfile.write(outdir / f'vo_{n}.wav', SR, (y * 32767).astype(np.int16))
        durs[n] = round(np.where(np.abs(dry) > 0.01)[0][-1] / SR, 3)
        gp[n] = gaps(dryn)
        print(n, durs[n], text)
    (outdir / 'durations.json').write_text(json.dumps(durs, indent=1))
    (outdir / 'gaps.json').write_text(json.dumps(gp, indent=1))
    return durs

def radio(x, lo=300, hi=3400, hiss=0.004, seed=5):
    """PA / radio voice: band-limited, a little saturation and hiss (bible §26)"""
    y = sosfilt(butter(4, [lo, hi], 'band', fs=SR, output='sos'), x)
    y = np.tanh(y * 2.2) / np.tanh(2.2)
    return y + hiss * np.random.default_rng(seed).standard_normal(len(y))

def build_cast(lines, outdir, cast):
    """lines: `ID|SPEAKER|text`. cast: {SPEAKER: {voice, slow, length, reverb, room_seconds, room_decay,
    warmth, radio}}. Plain, close voices by default (slow 1.0, small room): not announcer voices."""
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    durs, gp, who = {}, {}, {}
    for line in Path(lines).read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        n, spk, text = line.split('|', 2)
        c = dict(voice='en_US-joe-medium', slow=1.0, length=1.05, reverb=0.12, room_seconds=0.8, room_decay=6.0,
                 warmth=0.1, radio=False, pause=0.45)
        c.update(cast.get(spk, {}))
        check_voice(c['voice'])
        dry = process(text, c['voice'], c['slow'], c['length'], c['pause'], c['warmth'])
        ir = room_ir(c['room_seconds'], c['room_decay'])
        wet = fftconvolve(dry, ir)[: len(dry) + int(SR * c['room_seconds'])]
        dry = np.pad(dry, (0, len(wet) - len(dry)))
        y = 0.9 * dry + c['reverb'] * wet
        if c['radio']:
            y = radio(y)
        y = y / np.max(np.abs(y)) * 0.89
        wavfile.write(outdir / f'vo_{n}.wav', SR, (y * 32767).astype(np.int16))
        durs[n] = round(np.where(np.abs(dry) > 0.01)[0][-1] / SR, 3)
        gp[n] = gaps(dry / np.max(np.abs(dry)) * 0.9)
        who[n] = spk
        print(n, spk, durs[n], text)
    (outdir / 'durations.json').write_text(json.dumps(durs, indent=1))
    (outdir / 'gaps.json').write_text(json.dumps(gp, indent=1))
    (outdir / 'speakers.json').write_text(json.dumps(who, indent=1))
    return durs

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('lines'); ap.add_argument('outdir')
    ap.add_argument('--voice', default='en_US-norman-medium')
    ap.add_argument('--slow', type=float, default=0.93)
    ap.add_argument('--length', type=float, default=1.1)
    ap.add_argument('--pause', type=float, default=0.55)
    ap.add_argument('--reverb', type=float, default=0.32)
    ap.add_argument('--warmth', type=float, default=0.35)
    a = ap.parse_args()
    build(a.lines, a.outdir, a.voice, a.slow, a.length, a.pause, a.reverb, a.warmth)
