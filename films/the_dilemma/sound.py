"""THE DILEMMA: sound design and narration mix. Reads events.json written by film.py.

  python3 films/the_dilemma/sound.py --format 4x5      (the mix is format-independent; format picks the work dir)
"""
import sys, os, json, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *
from studio import audio as A

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='16x9'); a = ap.parse_args()
FILM = 'the_dilemma'
WORK = config.path('work', FILM, a.format)
VO = config.path('work', FILM, 'vo')
DUR = 90.0
ev = json.load(open(WORK / 'events.json'))
T = ev['T']
M = Mix(DUR)
N = M.N
add = M.add
curve = M.curve
L, R = M.L, M.R

# ------------------------------------------------------------------ build
print('drone')
# D drone through the whole film, with section chords
D2 = 73.42
drone = saw_stack(D2, N, 0.003, 10) * 0.5 + saw_stack(D2 * 1.5, N, 0.004, 8) * 0.3 + saw_stack(D2 / 2, N, 0.002, 6) * 0.4
drone = lp(drone, 900)
dr_env = curve([(0, 0), (1.0, 0), (3.0, 0.35), (13.8, 0.45), (21.2, 0.8), (21.5, 0.0), (23.5, 0.0), (27, 0.55),
                (42, 0.6), (46.5, 0.5), (53, 0.75), (61, 0.55), (73, 0.4), (75.9, 0.9), (76.0, 0.0), (77.0, 0.0),
                (79, 0.5), (86.6, 0.45), (88.5, 0.15), (90, 0)])
add(drone * dr_env * 0.22, 0, 1.0, -0.15)
add(drone * dr_env * 0.22, 0, 1.0, 0.15)

print('wind')
w = wind(N, seed=2)
w_env = curve([(0, 0), (0.9, 0), (1.0, 0.5), (13.8, 0.45), (21.5, 0.6), (22, 0.2), (24, 0.7), (27, 1.0), (41, 1.0),
               (42, 0.35), (61, 0.3), (73, 0.4), (76, 0.5), (86.6, 0.3), (87, 0.05), (90, 0)])
add(lp(w, 1000) * w_env * 0.08, 0, 1.0, -0.3)
add(lp(wind(N, seed=5), 1000) * w_env * 0.08, 0, 1.0, 0.3)
# funnel roar: lower, heavier
roar = lp(wind(N, 60, 500, seed=9), 500) * curve([(0, 0), (23.5, 0), (27.5, 1.0), (41.5, 1.1), (42, 0), (90, 0)])
add(roar * 0.16, 0, 1.0, 0.0)

print('drip')
n = int(0.12 * SR); t = tt(n)
drip = np.sin(2 * np.pi * np.cumsum(1400 * np.exp(-t * 25) + 350) / SR) * np.exp(-t * 30)
add(pad_tail(drip, 3) , 0.35, 0.0)
add(verb(pad_tail(drip, 3.4), 0.9), 0.35, 0.5)

print('monolith choir')
ch = choir([D2 * 2, D2 * 3, D2 * 4 * 1.25], int(15 * SR))
add(verb(ch * seg_env(len(ch), 4.0, 5.0), 0.5) * 0.05, T['T_S1B'] - 1.0)

print('tension')
n = int((T['T_EXP'] - T['T_LEAK']) * SR); t = tt(n)
riser_f = 200 * (4 ** (t / t[-1]))
riser = np.sin(2 * np.pi * np.cumsum(riser_f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(riser_f * 1.5) / SR)
riser *= (t / t[-1]) ** 2.5
add(verb(riser * 0.12, 0.4), T['T_LEAK'])
rumble = lp(rng.standard_normal(n), 120) * (t / t[-1]) ** 1.5
add(np.tanh(rumble * 3) * 0.35, T['T_LEAK'])
# heartbeat thumps accelerating
tb = T['T_LEAK'] + 1.5
gap = 1.1
while tb < T['T_EXP'] - 0.2:
    add(slam(1.2) * 0.35, tb, 1.0); add(slam(0.8) * 0.2, tb + 0.22, 1.0)
    tb += gap; gap *= 0.84
# silence gap, then detonation
print('detonation')
add(boom(6.0, 110, 26), T['T_EXP'], 0.95)
add(verb(pad_tail(boom(3.0, 160, 40, 1.0), 3), 0.8) * 0.4, T['T_EXP'])
ring = (np.sin(2 * np.pi * 880 * tt(int(7 * SR))) + 0.6 * np.sin(2 * np.pi * 1318.5 * tt(int(7 * SR)))) * np.exp(-tt(int(7 * SR)) * 0.55)
add(ring * 0.045, T['T_EXP'] + 0.15, 1.0, 0.0)
burst = flutter(4.0, 1800) * np.exp(-tt(int(4 * SR)) * 0.8)
add(burst * 0.35, T['T_EXP'] + 0.05, 1.0, -0.2)
add(flutter(4.0, 1800) * np.exp(-tt(int(4 * SR)) * 0.8) * 0.35, T['T_EXP'] + 0.08, 1.0, 0.2)
add(whoosh(1.4, 200, 2500) * 0.5, T['T_EXP'] + 0.3, 1.0, -0.6)   # front board past the lens

print('vortex')
dur = T['T_S5'] - T['T_V0']
fl = lp(flutter(dur, 700), 4500) * seg_env(int(dur * SR), 2.5, 1.0)
add(fl * 0.10, T['T_V0'], 1.0, -0.4)
add(lp(flutter(dur, 700), 4500) * seg_env(int(dur * SR), 2.5, 1.0) * 0.10, T['T_V0'], 1.0, 0.4)
# shimmering chord (D major 9) during the weather
ch2 = choir([D2 * 4, D2 * 5, D2 * 6, D2 * 9], int(18 * SR), vowel=(500, 900, 2400))
add(verb(ch2 * seg_env(len(ch2), 3.0, 4.0), 0.6) * 0.05, 25.5)
PENTA = [293.66, 329.63, 369.99, 440.0, 493.88, 587.33, 659.25, 739.99, 880.0]
tb = 27.0
while tb < 41.5:
    f = PENTA[rng.integers(0, len(PENTA))]
    add(verb(pad_tail(bell(f, 2.5), 2), 0.7) * 0.05, tb, 1.0)
    tb += rng.uniform(0.18, 0.45)
for th in ev['hero_pages']:
    add(whoosh(1.6, 400, 5000) * 0.55, th - 0.8, 1.0, 0.0)
    add(flutter(0.9, 900) * 0.4, th - 0.4, 1.0, 0.0)
# gentle whooshes as pages sweep past
tb = 27.8
while tb < 41.0:
    add(whoosh(rng.uniform(0.6, 1.1), 300, 2500) * 0.10, tb, 1.0, rng.uniform(-0.9, 0.9))
    tb += rng.uniform(0.5, 1.2)

print('cards')
add(lp(flutter(T['T_S5B'] - T['T_S5'], 400, 1200, 6000), 4000) * 0.12, T['T_S5'], 1.0, 0.0)
for k, x in enumerate(PENTA[::-1] + PENTA):
    add(verb(pad_tail(bell(x * 0.5, 2.0), 1.5), 0.7) * 0.04, T['T_S5'] + 0.25 * k, 1.0, rng.uniform(-0.5, 0.5))
for i, tl in enumerate(ev['card_land']):
    if tl < T['T_S5B'] - 0.3:
        continue
    add(slam(0.8) * 0.24, tl, 1.0, rng.uniform(-0.4, 0.4))
for i, tl in enumerate(ev['dice_land']):
    for dt_, g in ((0.0, 1.0), (0.75, 0.55), (1.15, 0.28), (1.40, 0.12)):
        add(die_hit(1.0 if dt_ == 0 else 0.5) * 0.6 * g, tl + dt_, 1.0, (-0.4, 0.4, 0.0)[i])
    add(whoosh(0.8, 200, 1500) * 0.3, tl - 0.8, 1.0, (-0.4, 0.4, 0.0)[i])
# pack lands
tp = ev['pack']
add(whoosh(1.0, 300, 3000) * 0.35, tp - 0.9)
add(boom(1.5, 90, 40, 0.3) * 0.4, tp)
cr = hp(rng.standard_normal(int(0.7 * SR)), 2500) * (rng.random(int(0.7 * SR)) > 0.97) * np.exp(-tt(int(0.7 * SR)) * 5)
add(cr * 0.5, tp + 0.02)
# triumphant swell
ch3 = choir([D2 * 2, D2 * 3, D2 * 4, D2 * 5], int(9 * SR))
add(verb(ch3 * seg_env(len(ch3), 1.5, 3.0), 0.5) * 0.04, 52.5)

print('standing order')
ch4 = choir([D2 * 4, D2 * 5, D2 * 6, D2 * 7.5], int(13 * SR), vowel=(400, 800, 2600))
add(verb(ch4 * seg_env(len(ch4), 3.0, 3.0), 0.8) * 0.07, T['T_S6'] - 0.5)
hum = saw_stack(D2 * 8, int(12 * SR), 0.002, 4) * seg_env(int(12 * SR), 2.0, 2.0)
add(lp(hum, 3000) * 0.02, T['T_S6'])
add(flutter(12, 120, 1500, 6000) * 0.25, T['T_S6'])
tb = T['T_S6'] + 1.0
for f in [587.33, 739.99, 880.0, 1108.73, 880.0, 739.99, 587.33, 739.99, 880.0, 1174.66]:
    add(verb(pad_tail(bell(f, 3.0), 2), 0.8) * 0.035, tb, 1.0, rng.uniform(-0.6, 0.6))
    tb += 1.05
add(whoosh(2.8, 200, 2500) * 0.3, T['T_S7'] - 3.2)

print('rewind')
n = int((T['T_SLAM'] - T['T_S7']) * SR); t = tt(n)
rev = boom(3.0, 110, 26)[::-1][:n]
rev = np.concatenate([np.zeros(n - len(rev)), rev]) if len(rev) < n else rev
swell = hp(rng.standard_normal(n), 800) * (t / t[-1]) ** 3
END = np.ones(n); END[-int(0.015 * SR):] = np.linspace(1, 0, int(0.015 * SR))   # no hard stop into the slam
swell *= END
rev = rev * END
add(swell * 0.35, T['T_S7'], 1.0, -0.2)
add(hp(rng.standard_normal(n), 800) * (t / t[-1]) ** 3 * END * 0.35, T['T_S7'], 1.0, 0.2)
add(rev * 0.45, T['T_S7'])
fl2 = flutter(n / SR, 1400)[::-1] * (t / t[-1]) ** 2 * END
add(fl2 * 0.4, T['T_S7'])
add(boom(5.0, 120, 30), T['T_SLAM'], 0.55)
add(slam(1.5) * 0.45, T['T_SLAM'])

print('resolve')
ch5 = choir([D2 * 2, D2 * 3, D2 * 4, D2 * 5, D2 * 9 / 2], int(12 * SR))
add(verb(ch5 * seg_env(len(ch5), 3.0, 4.5), 0.6) * 0.07, T['T_SLAM'] + 0.8)
for k, f in enumerate([293.66, 369.99, 440.0, 587.33]):
    add(verb(pad_tail(bell(f, 4.0), 2), 0.8) * 0.05, 80.0 + 0.35 * k)
add(whoosh(0.9, 400, 4000) * 0.5, T['T_LENS'] + 0.1)
add(flutter(0.5, 900) * 0.5, T['T_END_WHITE'] - 0.35)
# final: a single low D after the whisper
fin = saw_stack(D2, int(3.5 * SR), 0.002, 6)
add(lp(fin, 500) * seg_env(len(fin), 0.8, 2.5) * 0.09, 86.9)


# ------------------------------------------------------------------ narration
VO_AT = {'01': 2.0, '02': 5.2, '03': 14.2, '04': 26.5, '05': 38.0, '06': 43.0, '07': 54.15, '08': 61.5,
         '09': 77.5, '10': 81.6, '11': 87.5}
for k, at in VO_AT.items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=1.0, whisper=(k == '11'), key=k)
M.duck(0.68)
print('voice/fx dB', M.report_voice())
M.master(WORK / 'mix.wav')
print('mix written', WORK / 'mix.wav')
