"""studio.audio: rights-clean sound design with numpy/scipy.

Instruments (boom, slam, whoosh, paper flutter, wind, choir, bells, dice hits...), a two-bus Mix
(effects/music + voice) with equal-power pan, automation curves, voice ducking and a simple master
that lands near -14 LUFS. You cannot listen from an agent session: verify with studio.qa loudness,
a spectrogram, and Mix.report_voice() (aim for >= 8 dB voice over effects under narration).

    from studio.audio import *
    m = Mix(90.0)
    m.add(boom(4.0), at=21.5, gain=0.9)
    m.add_voice('vo_01.wav', at=2.0)
    m.duck(0.68); m.master('mix.wav')
"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
rng = np.random.default_rng(11)

def seed(s):
    global rng
    rng = np.random.default_rng(s)

def tt(n):
    return np.arange(n) / SR
def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)
def lp(x, f, order=2):
    return sosfilt(butter(order, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, order=2):
    return sosfilt(butter(order, f, 'high', fs=SR, output='sos'), x)
def seg_env(n, att, rel):
    e = np.ones(n)
    a = int(att * SR); r = int(rel * SR)
    if a: e[:a] = np.linspace(0, 1, a) ** 2
    if r: e[-r:] *= np.linspace(1, 0, r) ** 2
    return e
def reverb_ir(seconds=3.5, decay=2.0, lpf=5000, seed=1):
    r = np.random.default_rng(seed)
    n = int(SR * seconds); t = tt(n)
    irl = lp(r.standard_normal(n), lpf) * np.exp(-t * decay)
    irr = lp(r.standard_normal(n), lpf) * np.exp(-t * decay)
    irl[:240] = 0; irr[:240] = 0
    s = np.sqrt(np.sum(irl ** 2))
    return irl / s, irr / s
IRL, IRR = reverb_ir()

def verb(x, wet=0.35):
    return np.stack([x + wet * fftconvolve(x, IRL)[: len(x)], x + wet * fftconvolve(x, IRR)[: len(x)]], -1)
def pad_tail(x, sec):
    return np.concatenate([x, np.zeros(int(sec * SR))])


# ------------------------------------------------------------------ instruments
def saw_stack(freq, n, detune=0.004, harm=14):
    t = tt(n); out = np.zeros(n)
    for d in (-detune, 0, detune):
        f = freq * (1 + d)
        ph = rng.uniform(0, 6.28)
        for k in range(1, harm + 1):
            if f * k > 9000:
                break
            out += np.sin(2 * np.pi * f * k * t + ph * k) / k
    return out / 3

def choir(freqs, n, vowel=(700, 1150, 2600)):
    x = sum(saw_stack(f, n, 0.006, 24) for f in freqs)
    y = sum(bp(x, f * 0.85, f * 1.15) * g for f, g in zip(vowel, (1.0, 0.6, 0.25)))
    vib = 1 + 0.15 * np.sin(2 * np.pi * 5.1 * tt(n))
    return y * vib

def bell(freq, dur=3.0):
    n = int(dur * SR); t = tt(n)
    parts = [(1, 1.0, 1.2), (2.76, 0.5, 2.0), (5.4, 0.25, 3.2), (8.93, 0.12, 4.5)]
    return sum(g * np.sin(2 * np.pi * freq * p * t) * np.exp(-t * dcy) for p, g, dcy in parts) * (1 - np.exp(-t * 400))

def _attack(x, ms=2.0):
    """soften instantaneous onsets: AAC overshoots badly on infinite-slope transients"""
    n = min(len(x), int(SR * ms / 1000))
    x = x.copy(); x[:n] *= np.linspace(0, 1, n)
    return x

def boom(dur=4.0, f0=95, f1=28, noise=0.6):
    n = int(dur * SR); t = tt(n)
    f = f1 + (f0 - f1) * np.exp(-t * 3.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 1.1)
    nz = lp(rng.standard_normal(n), 400) * np.exp(-t * 2.5) * noise
    crack = hp(rng.standard_normal(n), 1500) * np.exp(-t * 18) * 0.6
    return _attack(np.tanh((body + nz + crack) * 1.6))

def slam(weight=1.0):
    n = int(0.45 * SR); t = tt(n)
    thump = np.sin(2 * np.pi * (70 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 16) * weight
    slap = bp(rng.standard_normal(n), 900, 5200) * np.exp(-t * 45) * 0.8
    return _attack(thump + slap)

def die_hit(big=1.0):
    n = int(0.6 * SR); t = tt(n)
    knock = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, d in ((180, 18), (410, 30), (960, 45)))
    thud = np.sin(2 * np.pi * (55 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 7)
    return _attack((0.5 * knock + thud * big) * 0.9)

def whoosh(dur=1.2, f_lo=300, f_hi=3500):
    n = int(dur * SR); t = tt(n) / dur
    x = rng.standard_normal(n)
    out = np.zeros(n)
    blocks = 40
    for b in range(blocks):
        a, e = b * n // blocks, (b + 1) * n // blocks
        c = f_lo + (f_hi - f_lo) * np.sin(np.pi * (b + 0.5) / blocks)
        out[a:e] = bp(x[max(a - 2000, 0):e], c * 0.6, c * 1.4)[-(e - a):]
    return out * np.sin(np.pi * t) ** 2

def flutter(dur, density, lo=1500, hi=7000):
    """paper: many tiny grains"""
    n = int(dur * SR); out = np.zeros(n)
    cnt = int(dur * density)
    g = int(0.012 * SR)
    for _ in range(cnt):
        i = rng.integers(0, n - g)
        w = rng.uniform(0.2, 1.0)
        out[i:i + g] += rng.standard_normal(g) * np.hanning(g) * w
    return bp(out, lo, hi)

def wind(n, lo=150, hi=1400, seed=0):
    r = np.random.default_rng(seed)
    x = r.standard_normal(n)
    y = bp(x, lo, hi)
    gust = lp(r.standard_normal(n), 0.4)
    gust = 0.6 + 0.4 * gust / (np.max(np.abs(gust)) + 1e-9)
    return y * gust


class Mix:
    """two stereo buses (fx/music and voice) on a fixed timeline"""
    def __init__(self, dur):
        self.dur = dur
        self.N = int(SR * dur)
        self.L = np.zeros(self.N); self.R = np.zeros(self.N)
        self.VL = np.zeros(self.N); self.VR = np.zeros(self.N)
        self.voice_at = {}

    def add(self, sig, at, gain=1.0, pan=0.0, bus='fx'):
        """pan -1..1 (equal power); stereo input (n,2) is added as is"""
        N = self.N
        i = int(at * SR)
        if i >= N:
            return
        if i < 0:
            sig = sig[-i:]; i = 0
        sig = sig[: N - i]
        a = (pan + 1) * np.pi / 4
        l, r = (self.L, self.R) if bus == 'fx' else (self.VL, self.VR)
        if sig.ndim == 2:
            l[i:i + len(sig)] += sig[:, 0] * gain; r[i:i + len(sig)] += sig[:, 1] * gain
        else:
            l[i:i + len(sig)] += sig * gain * np.cos(a); r[i:i + len(sig)] += sig * gain * np.sin(a)

    def curve(self, points):
        """piecewise-linear automation over the whole timeline: [(t, v), ...]"""
        x = np.array([p[0] for p in points]) * SR; y = np.array([p[1] for p in points])
        return np.interp(np.arange(self.N), x, y)

    def add_voice(self, path, at, gain=1.0, whisper=False, key=None):
        sr, x = wavfile.read(str(path))
        x = x.astype(np.float64) / 32768
        if x.ndim == 2:
            x = x.mean(1)
        if whisper:
            x = hp(x, 400) * 0.55
            x = x + 0.5 * fftconvolve(x, IRL)[: len(x)]
        self.add(x * gain, at, 1.0, 0.0, bus='voice')
        self.voice_at[key or str(path)] = at

    def duck(self, depth=0.68):
        vo = np.abs(self.VL) + np.abs(self.VR)
        envv = lp(vo, 3.0, 1)
        envv = envv / (np.max(envv) + 1e-9)
        d = 1 - depth * np.clip(envv * 3, 0, 1)
        self.L *= d; self.R *= d

    def report_voice(self, window=2.5):
        out = {}
        for k, at in self.voice_at.items():
            a, b = int(at * SR), int((at + window) * SR)
            fx = np.sqrt(np.mean(self.L[a:b] ** 2 + self.R[a:b] ** 2))
            vv = np.sqrt(np.mean(self.VL[a:b] ** 2 + self.VR[a:b] ** 2))
            out[k] = round(20 * np.log10(vv / (fx + 1e-9)), 1)
        return out

    def master(self, path, rms_target=0.12, drive=1.3, ceiling=0.93):
        mix = np.stack([self.L + self.VL, self.R + self.VR], -1)
        mix = hp(mix.T, 25).T
        rms = np.sqrt(np.mean(mix ** 2))
        mix = mix / rms * rms_target
        mix = np.tanh(mix * drive) / drive
        mix = mix / np.max(np.abs(mix)) * ceiling
        wavfile.write(str(path), SR, (mix * 32767).astype(np.int16))
        return mix
