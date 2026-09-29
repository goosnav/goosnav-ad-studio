"""Sound for LIGHTS OUT. Everything is synthesized with numpy/scipy (rights-clean). 48 kHz stereo.
The factory runs at 96 BPM: every slam, crimp and shuffle sits on the beat grid, and the score is built around it."""
import json, sys, os, numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from timing import T, VO_AT, BEAT, DUR

SR = 48000
N = int(SR * DUR)
rng = np.random.default_rng(21)
L = np.zeros(N); R = np.zeros(N)       # effects
ML = np.zeros(N); MR = np.zeros(N)     # music
VL = np.zeros(N); VR = np.zeros(N)     # voice

def tt(n): return np.arange(n) / SR
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def add(sig, at, gain=1.0, pan=0.0, bus='fx'):
    i = int(round(at * SR))
    if i >= N: return
    if i < 0: sig = sig[-i:]; i = 0
    sig = sig[:N - i]
    a = (pan + 1) * np.pi / 4
    l, r = {'fx': (L, R), 'mu': (ML, MR), 'vo': (VL, VR)}[bus]
    if sig.ndim == 2:
        l[i:i + len(sig)] += sig[:, 0] * gain; r[i:i + len(sig)] += sig[:, 1] * gain
    else:
        l[i:i + len(sig)] += sig * gain * np.cos(a); r[i:i + len(sig)] += sig * gain * np.sin(a)
def env(n, att, rel):
    e = np.ones(n); a = int(att * SR); r = int(rel * SR)
    if a: e[:a] = np.linspace(0, 1, a) ** 2
    if r: e[-r:] *= np.linspace(1, 0, r) ** 2
    return e
def curve(points, n=N):
    x = np.array([p[0] for p in points]) * SR; y = np.array([p[1] for p in points])
    return np.interp(np.arange(n), x, y)
def ir(seconds, decay, lpf, seed, pre=0.02):
    r = np.random.default_rng(seed); n = int(SR * seconds); t = tt(n)
    a = lp(r.standard_normal(n), lpf) * np.exp(-t * decay); b = lp(r.standard_normal(n), lpf) * np.exp(-t * decay)
    k = int(pre * SR); a[:k] = 0; b[:k] = 0
    s = np.sqrt(np.sum(a ** 2)); return a / s, b / s
HALL = ir(5.5, 1.1, 4000, 1, 0.04)      # the enormous hall
ROOM = ir(1.2, 4.5, 6000, 2, 0.01)      # close machinery
def verb(x, wet=0.4, space=HALL):
    x = np.concatenate([x, np.zeros(len(space[0]))])
    return np.stack([x + wet * fftconvolve(x, space[0])[:len(x)], x + wet * fftconvolve(x, space[1])[:len(x)]], -1)
def region(sig, t0, t1, gain=1.0, pan=0.0, bus='fx', fade=0.3):
    n = int((t1 - t0) * SR); s = sig[:n] * env(min(n, len(sig)), fade, fade)
    add(s, t0, gain, pan, bus)

# ------------------------------------------------------------------ instruments
def mx(*xs):
    n = max(len(x) for x in xs); out = np.zeros(n)
    for x in xs: out[:len(x)] += x
    return out
def noise(n, seed=None):
    return (np.random.default_rng(seed) if seed is not None else rng).standard_normal(n)
def thump(f0=60, f1=38, dur=1.2, decay=5.0):
    n = int(dur * SR); t = tt(n)
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * decay)
def clank(base=220, dur=1.5, bright=1.0, seed=0):
    """struck steel: inharmonic partials + a noisy transient"""
    r = np.random.default_rng(seed); n = int(dur * SR); t = tt(n)
    out = np.zeros(n)
    for k, (m, g, d) in enumerate([(1, 1, 3), (2.31, 0.6, 4), (3.93, 0.5, 6), (5.41, 0.35, 8), (7.2, 0.25, 11), (9.8, 0.15, 14)]):
        out += g * np.sin(2 * np.pi * base * m * (1 + r.uniform(-0.01, 0.01)) * t + r.uniform(0, 6)) * np.exp(-t * d)
    tr = hp(r.standard_normal(n), 1200) * np.exp(-t * 60) * bright
    return (out * 0.5 + tr) * (1 - np.exp(-t * 900))
def slam_big(weight=1.0, seed=0):
    n = int(2.5 * SR); t = tt(n)
    body = thump(95, 32, 2.5, 2.2) * 1.2 * weight
    crunch = lp(noise(n, seed), 900) * np.exp(-t * 9) * 0.8
    metal = np.concatenate([clank(140, 2.5, 1.2, seed), np.zeros(0)])[:n] * 0.35
    return np.tanh((body + crunch + metal) * 1.5)
def hiss(dur, lo=2500, hi=9000, att=0.01, rel=0.6, seed=None):
    n = int(dur * SR)
    return bp(noise(n, seed), lo, hi) * env(n, att, rel)
def whoosh(dur=1.0, lo=200, hi=3000, seed=None):
    n = int(dur * SR); x = noise(n, seed); out = np.zeros(n); B = 32
    for b in range(B):
        a, e = b * n // B, (b + 1) * n // B
        c = lo + (hi - lo) * np.sin(np.pi * (b + 0.5) / B)
        out[a:e] = bp(x[max(a - 3000, 0):e], c * 0.6, c * 1.5)[-(e - a):]
    return out * np.sin(np.pi * tt(n) / dur) ** 2
def grains(dur, density, lo, hi, glen=0.01, seed=None):
    r = np.random.default_rng(seed); n = int(dur * SR); out = np.zeros(n); g = int(glen * SR)
    for _ in range(int(dur * density)):
        i = r.integers(0, max(n - g, 1)); out[i:i + g] += r.standard_normal(g)[:len(out[i:i + g])] * np.hanning(g)[:len(out[i:i + g])] * r.uniform(0.2, 1)
    return bp(out, lo, hi)
def drip(f=900, seed=0):
    n = int(0.08 * SR); t = tt(n)
    fr = f * (1 + 1.5 * np.exp(-t * 60))
    return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 55)
def servo(dur, f0, f1, seed=0):
    n = int(dur * SR); t = tt(n)
    f = np.linspace(f0, f1, n) * (1 + 0.004 * np.sin(2 * np.pi * 31 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3.01 * ph)
    return bp(x, 150, 5000) * env(n, 0.08, 0.15)
def arc(dur, seed=0):
    """welding: buzzing 100 Hz arc + crackle"""
    r = np.random.default_rng(seed); n = int(dur * SR); t = tt(n)
    buzz = np.sign(np.sin(2 * np.pi * 100 * t)) * 0.2
    buzz = bp(buzz, 200, 4000)
    cr = grains(dur, 900, 1500, 9000, 0.004, seed) * 1.5
    gate = (lp(r.standard_normal(n), 6) > -0.2).astype(float)
    gate = lp(gate, 40)
    return (buzz + cr) * gate
def bird(seed):
    r = np.random.default_rng(seed); out = []
    for k in range(r.integers(2, 5)):
        d = r.uniform(0.06, 0.16); n = int(d * SR); t = tt(n)
        f0 = r.uniform(2800, 4200); f1 = f0 * r.uniform(0.7, 1.35)
        f = np.linspace(f0, f1, n) + 300 * np.sin(2 * np.pi * r.uniform(20, 40) * t)
        out.append(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2)
        out.append(np.zeros(int(r.uniform(0.04, 0.12) * SR)))
    return np.concatenate(out)

# music voices (Radiophonic-ish): sine/triangle leads with tape echo, organ pad, pulse bass
def tri(f, n, ph=0.0):
    x = (np.arange(n) / SR * f + ph) % 1.0
    return 4 * np.abs(x - 0.5) - 1
def note(f, dur, kind='sine', att=0.01, rel=0.25, vib=0.0):
    n = int(dur * SR); t = tt(n)
    fm = f * (1 + vib * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(fm) / SR
    if kind == 'sine': x = np.sin(ph) + 0.12 * np.sin(2 * ph)
    elif kind == 'tri': x = tri(f, n)
    else: x = sum(np.sin(ph * k) / k ** 1.3 for k in (1, 2, 3, 4, 6, 8))
    return x * env(n, att, rel)
def tape_echo(x, delay=0.75 * BEAT, fb=0.45, taps=5, tone=3500):
    out = np.concatenate([x, np.zeros(int(delay * SR * taps))]).copy()
    d = int(delay * SR); y = x.copy()
    for k in range(1, taps + 1):
        y = lp(y, tone) * fb
        out[k * d:k * d + len(y)] += y
    return out
def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

# ------------------------------------------------------------------ bed: mains hum, tape hiss, air
print('bed')
t_all = tt(N)
hum = (np.sin(2 * np.pi * 50 * t_all) + 0.5 * np.sin(2 * np.pi * 100 * t_all) + 0.25 * np.sin(2 * np.pi * 150 * t_all))
hum_env = curve([(0, 0.0), (0.6, 0.0), (0.62, 1.0), (T['LAMPS_OFF'], 1.0), (T['LAMPS_OFF'] + 0.05, 0.0), (DUR, 0.0)])
add(hum * hum_env * 0.012, 0, 1.0, 0.0)
air = lp(noise(N, 3), 700) * curve([(0, 0.25), (1, 0.4), (10, 0.6), (63.75, 0.6), (64, 0.8), (80, 0.8), (80.05, 0.3), (DUR, 0.25)])
add(air * 0.05, 0, 1.0, -0.2); add(lp(noise(N, 4), 700) * 0.05 * curve([(0, 0.25), (1, 0.4), (10, 0.6), (80, 0.8), (80.05, 0.3), (DUR, 0.25)]), 0, 1.0, 0.2)
tapehiss = hp(noise(N, 5), 3000) * 0.004
add(tapehiss, 0, 1.0, -0.3); add(hp(noise(N, 6), 3000) * 0.004, 0, 1.0, 0.3)
# distant factory: a slow machine rhythm on the beat, through the hall reverb, all film long until the dawn
dist = np.zeros(N)
b = 0.0
while b < T['DOCK']:
    k = int(round(b / BEAT))
    g = 0.5 if k % 4 == 0 else 0.25
    s = lp(thump(70, 45, 0.6, 9), 300) * g
    i = int(b * SR); dist[i:i + len(s)] += s[:N - i]
    b += BEAT
dist *= curve([(0, 0), (4, 0), (8, 1), (T['ARMS'], 1), (T['ARMS'] + 1, 0.5), (T['DOCK'], 0.3), (T['DOCK'] + 0.5, 0)])
dv = verb(dist, 1.2)[:N]
add(dv * 0.09, 0)

# ------------------------------------------------------------------ 1. LIGHTS
print('lights')
add(verb(mx(clank(90, 3.0, 2.0, 7) * 0.9, thump(80, 40, 1.5, 4) * 0.8), 0.8), T['BREAKER'], 0.55)
# each lamp strike: a tick and a rising ballast buzz, near ones loud, far ones faint, cascading away
import math
for k in range(34):
    for j, x in enumerate((-27, -9, 9, 27)):
        y = -24 + 6 + k * 12
        ts = T['LAMPS'] + (y + 24) / 12 * 0.09 * 4 + 0.03 * (hash((x, int(y))) % 7)
        if ts > 9: continue
        dist_m = math.hypot(x, y + 20) + 5
        g = min(1.0, 14 / dist_m)
        tick = clank(1800 + 300 * j, 0.25, 1.0, k * 4 + j) * 0.25
        n = int(1.4 * SR); tb = tt(n)
        buzz = np.sin(2 * np.pi * 100 * tb) * 0.3 + np.sin(2 * np.pi * 200 * tb) * 0.2
        buzz = bp(buzz + 0.3 * np.sign(np.sin(2 * np.pi * 100 * tb)), 150, 3000) * np.exp(-tb * 2.2) * np.clip(tb / 0.1, 0, 1) * 0.15
        s = np.concatenate([tick, np.zeros(max(0, n - len(tick)))])[:n] + buzz
        add(s * g * 0.35, ts, 1.0, x / 40)

# ------------------------------------------------------------------ 2. REEL: slow rumble, paper web flutter
print('reel')
n = int((T['PRESS'] - T['REEL']) * SR)
rumble = lp(noise(n, 11), 90) * 1.5 + 0.3 * np.sin(2 * np.pi * 28 * tt(n))
region(rumble, T['REEL'], T['PRESS'], 0.12, 0.0)
region(grains((T['PRESS'] - T['REEL']), 500, 800, 5000, 0.02, 12), T['REEL'], T['PRESS'], 0.08, 0.3)
creak = np.sin(2 * np.pi * np.cumsum(180 + 40 * np.sin(2 * np.pi * 0.4 * tt(int(3 * SR)))) / SR) * 0.05
add(bp(creak, 120, 900) * env(len(creak), 0.8, 1.2), T['REEL'] + 1.5, 1.0, -0.4)

# ------------------------------------------------------------------ 3/4. PRESS and SHEETS: the platen on every other beat
print('press')
cyc = 2 * BEAT
t = 0.0
slam_ts = []
n0 = int(np.floor((T['REEL']) / cyc))
for n_ in range(n0, int(T['BIND'] / cyc) + 1):
    ts = n_ * cyc + 0.5 * cyc
    if T['REEL'] <= ts < T['BIND']:
        slam_ts.append(ts)
for ts in slam_ts:
    near = T['PRESS'] <= ts < T['SHEETS']
    g = 0.3 if near else (0.22 if ts >= T['SHEETS'] else 0.14)
    s = slam_big(1.0, int(ts * 10))
    add(verb(s, 0.5 if near else 0.9) * g, ts)
    add(hiss(1.3, 1800, 8000, 0.02, 1.0, int(ts * 7)) * 0.12 * g * 1.6, ts + 0.05, 1.0, -0.3)
    add(hiss(0.5, 3000, 9000, 0.3, 0.2, int(ts * 9)) * 0.06 * g, ts - 0.45, 1.0, 0.4)   # the platen coming down
    if near:  # sparks
        add(grains(0.7, 300, 3000, 11000, 0.003, int(ts)) * np.exp(-tt(int(0.7 * SR)) * 5) * 0.5, ts + 0.02, 1.0, 0.3)
    # web advance: a rush of paper over rollers, then the cutter
    add(whoosh(0.5, 600, 5000, int(ts * 3)) * 0.1 * (1.0 if ts >= T['SHEETS'] else 0.5), ts - cyc * 0.5, 1.0, 0.2)
    add(clank(900, 0.3, 1.5, int(ts)) * 0.06 * (1.0 if ts >= T['SHEETS'] else 0.4), ts + 0.1, 1.0, 0.5)
# ink rain: a patter of drops
for i in range(int((T['SHEETS'] - T['PRESS']) * 60)):
    tp = T['PRESS'] + rng.uniform(0, T['SHEETS'] - T['PRESS'])
    add(drip(rng.uniform(600, 1600), i) * rng.uniform(0.02, 0.06), tp, 1.0, rng.uniform(-0.6, 0.6))
region(bp(noise(int(6.5 * SR), 31), 1500, 7000) * 0.05, T['PRESS'], T['SHEETS'], 1.0, 0.0, fade=0.5)

# ------------------------------------------------------------------ 5. BINDERY
print('bind')
for i in range(4):
    ts = T['BIND_T0'] + 0.1 + i * 0.42
    add(grains(0.5, 1400, 1200, 8000, 0.006, 40 + i) * env(int(0.5 * SR), 0.05, 0.3) * 0.22, ts, 1.0, 0.1 * i)
    add(thump(300, 200, 0.15, 30) * 0.08, ts + 0.52, 1.0, 0.0)
add(servo(1.1, 300, 520, 3) * 0.05, T['BIND_T0'] + 1.9)
add(mx(clank(400, 0.6, 0.5, 5) * 0.12, thump(160, 90, 0.4, 14) * 0.2), T['BIND_SLAM'] - 0.45, 1.0, 0.0)   # the board closes
add(hiss(0.35, 2000, 9000, 0.25, 0.05, 50) * 0.12, T['BIND_SLAM'] - 0.35)
big = slam_big(1.5, 99)
add(verb(big, 0.6) * 0.95, T['BIND_SLAM'])
add(verb(clank(55, 2.5, 2.0, 98), 0.8) * 0.25, T['BIND_SLAM'])
add(grains(1.5, 400, 300, 3000, 0.02, 97) * np.exp(-tt(int(1.5 * SR)) * 2) * 0.2, T['BIND_SLAM'] + 0.05)
add(hiss(1.6, 600, 5000, 0.2, 0.8, 51) * 0.12, T['BIND_SLAM'] + 0.9, 1.0, 0.2)   # hydraulic lift
add(servo(1.4, 90, 140, 7) * 0.08, T['BIND_SLAM'] + 0.9)
# the line: rollers and a gentle rattle
n = int((T['KILN'] - T['LINE']) * SR)
rat = grains(T['KILN'] - T['LINE'], 60, 400, 3000, 0.015, 61) + lp(noise(n, 62), 200) * 0.4
region(rat, T['LINE'], T['KILN'], 0.25, 0.2)
for k in range(int((T['KILN'] - T['LINE']) / 0.5 * 1.5)):
    add(thump(420, 300, 0.12, 40) * 0.05, T['LINE'] + k * 0.5 / 1.5 + 0.1, 1.0, 0.3)

# ------------------------------------------------------------------ 6. GOOSKLERF
print('goosklerf')
n = int((T['QUENCH'] - T['KILN']) * SR)
roar = lp(noise(n, 70), 350) * 1.2 + grains(T['QUENCH'] - T['KILN'], 80, 1500, 7000, 0.004, 71) * 0.6
region(roar, T['KILN'], T['QUENCH'], 0.25, -0.2)
for i in range(18):
    ts = T['DICE_T0'] + i * 0.5
    for k in range(4):   # dice rattling up the chute
        add(clank(2400 + 200 * (i % 3), 0.12, 1.0, i * 10 + k) * 0.035, ts + 0.2 + k * 0.2, 1.0, 0.2)
    tpl = ts + 1.45
    if tpl < T['SHUF'] + 0.8:
        g = 1.0 if tpl >= T['QUENCH'] else 0.4
        add(thump(500, 250, 0.15, 25) * 0.1 * g, tpl, 1.0, 0.0)       # plop
        add(hiss(1.4, 2500, 10000, 0.005, 1.2, 80 + i) * 0.14 * g, tpl + 0.01, 1.0, rng.uniform(-0.3, 0.3))   # tsss
        add(grains(0.4, 900, 1500, 6000, 0.004, 90 + i) * 0.15 * g, tpl, 1.0, 0.0)
# shuffler: a riffle when the fan opens, a snap when it closes
for k in range(5):
    ts = T['SHUF'] + 0.1 + k * 2 * BEAT
    if ts > T['CRIMP']: break
    add(grains(0.32, 2500, 1500, 9000, 0.003, 100 + k) * env(int(0.32 * SR), 0.01, 0.1) * 0.35, ts, 1.0, -0.1)
    add(mx(clank(1600, 0.1, 2.0, 110 + k) * 0.08, thump(700, 400, 0.06, 60) * 0.1), ts + 0.72 * 2 * BEAT + 0.15, 1.0, 0.1)
# crimper: advance, then the jaws on the beat, with a sizzle
for k in range(5):
    t0 = T['CRIMP'] - 0.3 + k * 2 * BEAT
    if t0 > T['TUBE']: break
    add(grains(0.4, 200, 600, 3000, 0.01, 120 + k) * 0.1, t0, 1.0, 0.2)
    tj = t0 + 0.5 * 2 * BEAT
    add(mx(clank(700, 0.5, 1.2, 130 + k) * 0.18, thump(200, 100, 0.3, 16) * 0.3), tj, 1.0, 0.0)
    add(hiss(0.7, 3000, 11000, 0.01, 0.5, 140 + k) * 0.12, tj + 0.02, 1.0, 0.1)
    add(hiss(0.4, 800, 3000, 0.05, 0.2, 150 + k) * 0.08, tj + 0.4, 1.0, -0.2)   # pneumatic release

# ------------------------------------------------------------------ 7. TUBE
print('tube')
region(np.sin(2 * np.pi * 60 * tt(int(7 * SR))) * 0.2 + lp(noise(int(7 * SR), 160), 300) * 0.3, T['TUBE'], T['TUBEUP'], 0.3, 0.0)
add(clank(1100, 0.5, 1.5, 161) * 0.25, T['FIRE'] - 0.45, 1.0, 0.3)      # lever
add(hiss(0.5, 1500, 7000, 0.3, 0.05, 162) * 0.15, T['FIRE'] - 0.5)
whoomp = thump(120, 45, 1.2, 4) + lp(noise(int(1.2 * SR), 163), 500) * np.exp(-tt(int(1.2 * SR)) * 6) * 0.8
add(verb(whoomp, 0.5) * 0.7, T['FIRE'])
# the carrier rushing up the brass: a rising, receding whistle
n = int(2.2 * SR); tb = tt(n)
f = 180 * (1 + 6 * (tb / 2.2) ** 1.5)
wh = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + bp(noise(n, 164), 400, 4000) * 0.6
wh *= np.exp(-tb * 1.2) * np.clip(tb / 0.05, 0, 1)
add(verb(wh, 0.8) * 0.35, T['FIRE'] + 0.02)
add(verb(mx(thump(200, 120, 0.4, 10) * 0.3, clank(600, 0.8, 0.6, 165) * 0.15), 1.5) * 0.25, T['FIRE'] + 1.9)   # far above: out
# ------------------------------------------------------------------ 8. ARMS
print('arms')
region(lp(noise(int(17 * SR), 170), 120) * 0.8, T['ARMS'], T['DOCK'], 0.2, 0.0, fade=1.0)
A0 = T['ARMS_T0']
add(verb(arc(5.2, 171), 0.6) * 0.18, A0 + 1.0, 1.0, -0.2)                       # arm 0 welding
for k in range(3):
    add(servo(0.9, 180 + 40 * k, 260 + 30 * k, 172 + k) * 0.05, A0 + 0.2 + k * 2.1, 1.0, -0.3)
# the hoist chain lowering the forearm, then the seat
region(grains(3.2, 120, 800, 5000, 0.01, 180) + bp(noise(int(3.2 * SR), 181), 300, 900) * 0.1, A0 + 1.6, A0 + 4.8, 0.3, 0.3)
add(verb(mx(clank(260, 1.8, 1.0, 182) * 0.5, thump(150, 70, 0.6, 8) * 0.6), 0.7) * 0.35, A0 + 4.8, 1.0, 0.2)
# arm 1 wakes: wrist turns once, then it reaches
W = A0 + 6.6
add(servo(1.6, 420, 640, 190) * 0.09, W, 1.0, 0.1)
add(servo(2.6, 160, 300, 191) * 0.08, W + 1.8, 1.0, 0.1)
add(clank(1900, 0.2, 1.0, 192) * 0.05, W + 1.62, 1.0, 0.1)
add(verb(arc(3.0, 193), 0.6) * 0.14, W + 4.6, 1.0, 0.2)
# the row: many arcs, far off, in the dark
for k in range(7):
    add(verb(arc(12, 200 + k), 1.5) * 0.03 / (1 + k * 0.4), T['ARMS'] + 0.4 * k, 1.0, rng.uniform(-0.6, 0.6))

# ------------------------------------------------------------------ 9. DOCK
print('dock')
region(bp(noise(int(10 * SR), 210), 150, 1500) * 0.5, T['DOCK'], DUR, 0.06, 0.4, fade=1.5)   # outside air
for k in range(14):
    add(verb(bird(220 + k), 0.6, ROOM) * rng.uniform(0.03, 0.07), T['DOCK'] + 0.4 + k * rng.uniform(0.35, 0.6), 1.0, rng.uniform(0.2, 0.9))
for k in range(6):   # sodium lamps ticking as they cool
    add(clank(3000 + 400 * k, 0.1, 1.0, 230 + k) * 0.03, T['DOCK'] + 1.0 + k * 0.7, 1.0, rng.uniform(-0.8, 0.0))
add(verb(slam_big(1.0, 240), 1.6)[: int(4 * SR)] * 0.12, T['DOCK'] + 5 * BEAT, 1.0, -0.5)   # far inside, once more, on the beat
# lights out: the relay, the hum dies
add(verb(mx(clank(120, 2.0, 2.0, 250) * 0.7, thump(90, 45, 0.8, 6) * 0.6), 1.0) * 0.45, T['LAMPS_OFF'])

# ------------------------------------------------------------------ MUSIC
print('music')
# D dorian. Organ pad changes every 2 bars; pulse bass on the beats; a sine lead with tape echo.
CH = {'Dm': [50, 57, 62, 65, 69], 'Bb': [46, 58, 62, 65, 70], 'F': [53, 57, 60, 65, 72], 'C': [48, 55, 60, 64, 67],
      'Gm': [43, 55, 58, 62, 67], 'A': [45, 57, 61, 64, 69], 'D': [50, 57, 62, 66, 69]}
PROG = ['Dm', 'Bb', 'F', 'C', 'Dm', 'Bb', 'Gm', 'A']
BAR = 4 * BEAT
def pad(chord, t0, dur, gain):
    x = sum(note(mtof(m), dur, 'organ', 0.6, 1.0) for m in CH[chord]) / 5
    add(verb(lp(x, 2500), 0.35) * gain, t0, 1.0, 0.0, 'mu')
music_start, music_mid, music_thin, music_stop = 1.0, T['REEL'], T['TUBE'], T['ARMS']
bar = 0
tb = music_start
while tb < music_stop - 0.1:
    ch = PROG[(bar // 2) % len(PROG)]
    if bar % 2 == 0:
        g = 0.11 if tb < music_mid else (0.09 if tb < music_thin else 0.07)
        if tb < 4: g *= (tb - 1) / 3 + 0.2
        pad(ch, tb, 2 * BAR + 1.0, g)
    # bass pulse on each beat once the factory is running
    if music_mid <= tb < music_stop:
        root = CH[ch][0] - 12
        for k in range(4):
            gk = 0.13 if k == 0 else 0.08
            if tb >= music_thin: gk *= 0.5
            add(lp(note(mtof(root), BEAT * 0.9, 'tri', 0.005, 0.2), 700) * gk, tb + k * BEAT, 1.0, 0.0, 'mu')
    bar += 1; tb += BAR
# the lead: a proud little tune, played while he is proud (10 s .. 51 s), with tape echo
MEL = [(0, 69, 1), (1, 72, 1), (2, 74, 2), (4, 77, 1), (5, 76, 1), (6, 74, 2),      # beats, midi, length(beats)
       (8, 72, 1), (9, 70, 1), (10, 69, 2), (12, 67, 1), (13, 69, 1), (14, 65, 2),
       (16, 69, 1), (17, 72, 1), (18, 74, 2), (20, 79, 1), (21, 77, 1), (22, 76, 2),
       (24, 74, 1), (25, 72, 1), (26, 70, 1), (27, 69, 1), (28, 73, 4)]
lead = np.zeros(N)
for rep, start in enumerate([T['REEL'] + BAR * 0, T['REEL'] + BAR * 8]):   # twice
    for b_, m, ln in MEL:
        ts = start + b_ * BEAT
        x = note(mtof(m), ln * BEAT * 0.95, 'sine', 0.02, 0.12, vib=0.006)
        i = int(ts * SR); lead[i:i + len(x)] += x[:N - i]
# second half answers an octave down, fainter, and stops mid-phrase at the tube (the doubt starts)
start = T['REEL'] + BAR * 16
for b_, m, ln in MEL[:14]:
    ts = start + b_ * BEAT
    if ts > T['TUBE'] + 1.5: break
    x = note(mtof(m - 12), ln * BEAT * 0.95, 'sine', 0.02, 0.12, vib=0.006) * 0.7
    i = int(ts * SR); lead[i:i + len(x)] += x[:N - i]
lead = tape_echo(lead)[:N]
add(verb(lead, 0.3) [:N] * 0.06, 0, 1.0, 0.0, 'mu')
# the reveal: no tune. A low sine and a high, faint, unresolved tone
n = int((T['DOCK'] - T['ARMS']) * SR); tb_ = tt(n)
drone = np.sin(2 * np.pi * 36.7 * tb_) * 0.5 + np.sin(2 * np.pi * 55 * tb_) * 0.3
drone *= env(n, 3.0, 2.0)
add(drone * 0.05, T['ARMS'], 1.0, 0.0, 'mu')
high = np.sin(2 * np.pi * 1245 * tb_ + 0.8 * np.sin(2 * np.pi * 0.2 * tb_)) * env(n, 5.0, 3.0)
add(verb(high, 0.8)[:n] * 0.006, T['ARMS'] + 2.0, 1.0, 0.3, 'mu')
# dawn: one open chord, the first major chord in the film, very quiet; then the end card
pad('D', T['DOCK'] + 0.5, 6.0, 0.05)
end = sum(note(mtof(m), 4.5, 'organ', 0.3, 3.0) for m in [50, 57, 62, 66, 69, 74]) / 6
add(verb(lp(end, 2200), 0.5) * 0.07, T['END'] + 0.05, 1.0, 0.0, 'mu')
bell = sum(np.sin(2 * np.pi * mtof(74) * p * tt(int(4 * SR))) * g * np.exp(-tt(int(4 * SR)) * d) for p, g, d in [(1, 1, 1.2), (2.76, 0.4, 2), (5.4, 0.2, 3)])
add(verb(bell, 0.6)[: int(4 * SR)] * 0.03, T['END'] + 0.1, 1.0, 0.0, 'mu')

# music: 1970s tape: band-limit, gentle saturation, a little wow
mu = np.stack([ML, MR], 0)
mu = hp(lp(mu, 11000), 45)
mu = np.tanh(mu * 2.0) / 2.0

# ------------------------------------------------------------------ narration + ducking
print('voice')
late = {'14': 0.9, '15': 0.9, '16': 0.85, '17': 0.8, '18': 0.72, '19': 0.72, '20': 0.8}
for k, at in VO_AT.items():
    sr, x = wavfile.read(f'{HERE}/vo/vo_{k}.wav')
    x = x.astype(np.float64) / 32768
    add(x * late.get(k, 1.0), at, 1.0, 0.0, 'vo')
vo = np.abs(VL) + np.abs(VR)
e = lp(vo, 4.0, 1); e = e / (e.max() + 1e-9)
duck = 1 - 0.9 * np.clip(e * 5, 0, 1)
fx = np.stack([L, R], 0) * duck * 0.5
mu = mu * duck * 0.7
# after the lights go out: only the dawn remains (fx fades), end card keeps music tail
mix = fx + mu + np.stack([VL, VR], 0)
mix = hp(mix, 28)
for k, at in VO_AT.items():
    a_, b_ = int(at * SR), int((at + 1.8) * SR)
    f_ = np.sqrt(np.mean((fx[:, a_:b_] + mu[:, a_:b_]) ** 2)); v_ = np.sqrt(np.mean(np.stack([VL, VR])[:, a_:b_] ** 2))
    print('VO', k, 'voice-over-bed dB', round(20 * np.log10(v_ / (f_ + 1e-9)), 1))
# master: normalise loudness roughly, soft limit
rms = np.sqrt(np.mean(mix ** 2)); mix = mix / rms * 0.11
mix = np.tanh(mix * 1.2) / 1.2
mix = mix / np.max(np.abs(mix)) * 0.89
# fade the last half second
fo = int(0.5 * SR); mix[:, -fo:] *= np.linspace(1, 0, fo)
wavfile.write(HERE + '/mix.wav', SR, (mix.T * 32767).astype(np.int16))
print('mix written')
if os.environ.get('DIAG'):
    for k in os.environ['DIAG'].split(','):
        at = VO_AT[k]; a_, b_ = int(at * SR), int((at + 1.8) * SR)
        r = lambda x: 20 * np.log10(np.sqrt(np.mean(x[:, a_:b_] ** 2)) + 1e-12)
        print('DIAG', k, 'fx', round(r(fx), 1), 'mu', round(r(mu), 1), 'vo', round(r(np.stack([VL, VR])), 1), 'duck', round(float(duck[a_:b_].mean()), 2),
              'fx_undcuk', round(r(np.stack([L, R])), 1))
