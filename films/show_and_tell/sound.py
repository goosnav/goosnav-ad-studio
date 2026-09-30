"""SHOW AND TELL: desert wind, spins, a fuse, a very large explosion, silence on the card."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *
FILM = 'show_and_tell'
WORK = config.path('work', FILM, 'lpv'); VO = config.path('work', FILM, 'vo')
ev = json.load(open(WORK / 'events.json'))
M = Mix(ev['dur']); N = M.N; END = ev['end']; B = ev['BOOM']
air = M.curve([(0, 0), (0.4, 1), (B - 0.05, 1), (B, 0.3), (END - 0.05, 0.6), (END, 0), (ev['dur'], 0)])
M.add(lp(wind(N, 120, 1400, seed=2), 1400) * air * 0.14, 0, 1.0, -0.3)
M.add(lp(wind(N, 120, 1400, seed=6), 1400) * air * 0.14, 0, 1.0, 0.3)
a, b = ev['SPIN1']
M.add(whoosh(b - a, 300, 2500) * 0.35, a, 1.0, -0.4)
a, b = ev['SPIN2']
ts = a
while ts < b:
    M.add(whoosh(0.35, 400, 4000) * 0.3, ts, 1.0, np.random.default_rng(int(ts * 100)).uniform(-0.8, 0.8)); ts += 0.28
for k in ('P1', 'P2', 'P3'):
    M.add(flutter(0.3, 200, 800, 4000) * 0.12, ev['LIFT'][k][0], 1.0, 0)            # arms up: jacket rustle
# the fuse: fizzing hiss with crackle, from the lift to the bang
a = ev['LIFT']['P3'][0] - 0.2; n = int((B - a) * SR)
hiss = bp(np.random.default_rng(3).standard_normal(n), 3000, 9000) * (0.6 + 0.4 * (np.random.default_rng(4).random(n) > 0.97))
M.add(hiss * np.linspace(0.3, 1, n) * 0.08, a, 1.0, 0.4)
# the explosion: a huge boom, a long rumble, secondary blasts, debris
M.add(boom(6.0, 120, 24, 1.0), B, 1.0, 0)
M.add(verb(pad_tail(boom(3.5, 180, 40, 1.0), 3), 1.0) * 0.5, B + 0.02, 1.0, 0)
n = int((END - B) * SR); tt_ = np.arange(n) / SR
rumble = lp(np.random.default_rng(5).standard_normal(n), 90) * np.exp(-tt_ * 0.5) * seg_env(n, 0.01, 0.4)
M.add(np.tanh(rumble * 4) * 0.5, B, 1.0, 0)
rng = np.random.default_rng(8)
for d in np.sort(rng.uniform(0.3, 3.3, 10)):
    M.add(boom(1.5, 150, 45, 0.8) * 0.35, B + d, 1.0, rng.uniform(-0.7, 0.7))
for d in np.sort(rng.uniform(0.8, 4.5, 30)):
    M.add(die_hit(0.1) * 0.12, B + d, 1.0, rng.uniform(-0.9, 0.9))
for k, at in ev['VO_AT'].items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=1.0, key=k)
M.duck(0.5)
print('voice/fx dB', M.report_voice())
M.master(WORK / 'mix.wav', rms_target=0.08)
