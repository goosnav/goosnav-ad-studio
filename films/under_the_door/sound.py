"""UNDER THE DOOR: sound design and narration mix. Reads events.json written by film.py.
All synthesized: music box, underwater pad, paper hush, clock, foghorn, knocks.

  python3 -m studio sound under_the_door --format 4x5
"""
import sys, os, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='4x5'); a = ap.parse_args()
FILM = 'under_the_door'
WORK = config.path('work', FILM, a.format)
VO = config.path('work', FILM, 'vo')
DUR = 58.5
ev = json.load(open(WORK / 'events.json'))
T = ev['T']
M = Mix(DUR)
N = M.N
add, curve = M.add, M.curve
r = np.random.default_rng(314)
T_UNDER, T_DAWN, T_END = T['T_UNDER'], T['T_DAWN'], T['T_END']

def mbox(f, dur=2.6):
    """music-box tine: bright attack, inharmonic partial, long ring, slightly detuned"""
    n = int(dur * SR); t = tt(n)
    f = f * (1 + r.normal(0, 0.0025))
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t * 1.6)
         + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 5.0)
         + 0.12 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 11.0))
    x[:96] *= np.linspace(0, 1, 96)
    x[-2400:] *= np.linspace(1, 0, 2400)
    return x

def lowpass_seg(x, f):
    return lp(x, f, 4)

# muffling curve: everything underwater loses its top
UW = curve([(0, 0), (T_UNDER - 0.05, 0), (T_UNDER, 1), (T_DAWN - 0.1, 1), (T_DAWN, 0), (DUR, 0)])

# ------------------------------------------------------------------ room tone, clock
print('room')
room = lp(r.standard_normal(N), 400) * 0.02 * curve([(0, 0), (0.3, 1), (T_UNDER, 1), (T_UNDER + 0.01, 0), (T_DAWN, 0), (T_DAWN + 0.05, 1), (T_END - 0.5, 1), (T_END + 0.3, 0), (DUR, 0)])
add(room, 0, 1.0, -0.2); add(lp(r.standard_normal(N), 400) * 0.02 * (room != 0), 0, 1.0, 0.2)
tick = hp(r.standard_normal(int(0.012 * SR)), 2500) * np.exp(-tt(int(0.012 * SR)) * 500)
tb = 0.25
while tb < T_END:
    if not (T['T_S3'] + 2 < tb < T_DAWN):
        add(tick * (0.10 if tb % 2 < 1 else 0.07), tb, 1.0, 0.35)
    tb += 1.0

# ------------------------------------------------------------------ paper under the door
print('slides')
def shff(dur=0.7, g=1.0):
    n = int(dur * SR); t = tt(n)
    x = bp(r.standard_normal(n), 1200, 7000) * (1 - np.exp(-t * 60)) * np.exp(-t * (4.5 / dur))
    return x * g
for i, ts in enumerate(ev['slides']):
    add(shff(0.9 if i == 0 else 0.7, 0.28 if i == 0 else 0.18), ts - 0.05, 1.0, r.uniform(-0.3, 0.3))
    add(lp(r.standard_normal(int(0.15 * SR)), 300) * np.exp(-tt(int(0.15 * SR)) * 30) * 0.08, ts + 0.02)
# the tide: hush of paper, building into a roar, then cut by the water
print('tide')
n = int((T_UNDER - T['T_S3']) * SR); t = tt(n)
env = (t / t[-1]) ** 1.8
hush = lp(bp(r.standard_normal(n), 300, 3200), 2500) * env * 0.13
hush2 = lp(bp(r.standard_normal(n), 300, 3200), 2500) * env * 0.13
add(hush, T['T_S3'], 1.0, -0.5); add(hush2, T['T_S3'], 1.0, 0.5)
for tf in ev['flood_in']:
    add(lp(shff(0.5, 0.06), 4000), tf, 1.0, r.uniform(-0.7, 0.7))
add(lp(r.standard_normal(n), 150) * env * 0.35, T['T_S3'])   # low swell

# ------------------------------------------------------------------ underwater
print('underwater')
n = int((T_DAWN - T_UNDER) * SR); t = tt(n)
uw_env = seg_env(n, 0.05, 0.4)
rumble = lp(r.standard_normal(n), 160, 4) * 0.5 * uw_env
add(rumble, T_UNDER, 1.0, -0.2); add(lp(r.standard_normal(n), 160, 4) * 0.5 * uw_env, T_UNDER, 1.0, 0.2)
add(lp(boom(3.0, 70, 30, 0.3), 400) * 0.5, T_UNDER)          # the plunge
# paper "bubbles": soft low-passed flutters
tb = T_UNDER + 0.5
while tb < T_DAWN - 0.5:
    add(lp(flutter(0.6, 300, 300, 1500), 1200) * 0.10, tb, 1.0, r.uniform(-0.8, 0.8))
    tb += r.uniform(0.6, 1.6)
# the pad: D minor 9, opening to D major at dawn
D2 = 73.42
def pad(freqs, dur, cut=700):
    n = int(dur * SR)
    x = sum(saw_stack(f, n, 0.004, 8) for f in freqs) / len(freqs)
    return lp(x, cut, 2)
p1 = pad([D2 * 2, D2 * 3, D2 * 2 * 1.2, D2 * 4 * 1.125 * 2 / 2], T_DAWN - T_UNDER + 2.0, 600)
add(verb(p1 * seg_env(len(p1), 2.5, 2.5), 0.6) * 0.07, T_UNDER - 0.3)
p0 = pad([D2 * 2, D2 * 3], T_UNDER - 1.0, 400)
add(p0 * seg_env(len(p0), 4.0, 0.3) * 0.05, 1.0)
p2 = pad([D2 * 2, D2 * 2.5, D2 * 3, D2 * 4.5], T_END + 0.6 - T_DAWN, 900)
add(verb(p2 * seg_env(len(p2), 1.5, 3.5), 0.6) * 0.06, T_DAWN)
# foghorn on each pass of the beam
for tbp in ev['beam_pass']:
    if T['T_S5'] - 0.5 < tbp < T['T_S6']:
        n2 = int(3.2 * SR)
        horn = lp(saw_stack(D2 * 0.75, n2, 0.003, 10), 260, 2) * seg_env(n2, 0.8, 1.6)
        add(verb(horn, 0.7) * 0.10, tbp - 1.2)
# dice knocking at the surface
for tk in (36.4, 37.9, 40.6):
    k = lp(die_hit(0.6), 900) * 0.35
    add(verb(pad_tail(k, 1.0), 0.8) * 0.5, tk, 1.0, r.uniform(-0.5, 0.5))
    add(verb(pad_tail(lp(die_hit(0.4), 900) * 0.2, 1.0), 0.8) * 0.5, tk + 0.22, 1.0, r.uniform(-0.5, 0.5))
# card school swish
for tc in (32.4, 38.6):
    add(lp(whoosh(2.0, 200, 1500), 1500) * 0.18, tc)
# surfacing: rising swell into air
n = int(1.4 * SR); sw = lp(r.standard_normal(n), 900) * (tt(n) / tt(n)[-1]) ** 3
add(sw * 0.3, T_DAWN - 1.4)
add(bp(r.standard_normal(int(0.8 * SR)), 300, 4000) * np.exp(-tt(int(0.8 * SR)) * 5) * 0.12, T_DAWN)

# ------------------------------------------------------------------ the music box
print('music box')
D5, E5, F5, G5, A5, C6, A4, Bb4 = 587.33, 659.25, 698.46, 783.99, 880.0, 1046.5, 440.0, 466.16
TUNE = [D5, F5, A5, G5, F5, E5, D5, A4, Bb4, D5, F5, E5, D5, A4, None, None]
def play(t0, t1, gain, wet, spacing=0.78, muff=False):
    tb, k = t0, 0
    while tb < t1:
        f = TUNE[k % len(TUNE)]
        if f:
            x = mbox(f)
            if muff:
                x = lp(x, 1400, 2)
            add(verb(pad_tail(x, 2.0), wet) * gain, tb, 1.0, r.uniform(-0.3, 0.3))
        tb += spacing * r.uniform(0.9, 1.18)      # a little out of time
        k += 1
play(0.35, T['T_S3'] + 1.5, 0.05, 0.45)
play(T_UNDER + 1.0, T_DAWN - 1.0, 0.045, 0.9, spacing=1.15, muff=True)
for k, f in enumerate([A5, F5, E5, D5]):                   # its last four notes, at dawn
    add(verb(pad_tail(mbox(f, 3.2), 2.5), 0.6) * 0.055, 44.8 + 0.95 * k + (0.2 if k == 3 else 0), 1.0, 0.1)
add(verb(pad_tail(mbox(D5 / 2 * 2, 3.5), 3.0), 0.7) * 0.06, T_END + 2.2)   # one note on the white card, after the whisper

# ------------------------------------------------------------------ muffle underwater, narration
M.L = M.L * (1 - UW) + lp(M.L, 700, 2) * UW
M.R = M.R * (1 - UW) + lp(M.R, 700, 2) * UW
VO_AT = {'01': 1.2, '02': 6.0, '03': 12.8, '04': 20.6, '05': 27.2, '06': 35.6, '07': 43.0, '08': 49.4, '09': 55.7}
for k, at in VO_AT.items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=1.0 if k != '09' else 0.9, whisper=(k == '09'), key=k)
M.duck(0.6)
print('voice/fx dB', M.report_voice())
# the whisper is 1 s long; the 2.5 s window above includes the note after it, so measure it on its own span
a_, b_ = int(55.7 * SR), int(56.7 * SR)
fx_ = np.sqrt(np.mean(M.L[a_:b_] ** 2 + M.R[a_:b_] ** 2)); vv_ = np.sqrt(np.mean(M.VL[a_:b_] ** 2 + M.VR[a_:b_] ** 2))
print('whisper 09 voice/fx dB over its own span', round(20 * np.log10(vv_ / (fx_ + 1e-9)), 1))
M.master(WORK / 'mix.wav')
print('mix written', WORK / 'mix.wav')
