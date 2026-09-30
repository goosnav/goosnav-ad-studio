"""CONTINUATION DEPARTMENT: exterior air, footsteps, paper, pen, stamp, a building powering up (bible §25)."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *
FILM = 'continuation_department'
WORK = config.path('work', FILM, 'lpv'); VO = config.path('work', FILM, 'vo')
ev = json.load(open(WORK / 'events.json'))
M = Mix(ev['dur']); N = M.N; END = ev['end']
tone = M.curve([(0, 0), (0.3, 1), (END - 0.05, 1), (END, 0), (ev['dur'], 0)])
M.add(lp(wind(N, 100, 900, seed=3), 900) * tone * 0.10, 0, 1.0, -0.3)
M.add(lp(np.random.default_rng(4).standard_normal(N), 140) * tone * 0.25, 0, 1.0, 0.3)   # far city
def step(k):
    n = int(0.12 * SR); tt_ = np.arange(n) / SR
    return (bp(np.random.default_rng(k).standard_normal(n), 300, 2500) * np.exp(-tt_ * 70) + 0.4 * np.sin(2 * np.pi * 90 * tt_) * np.exp(-tt_ * 50)) * 0.5
for i, ts in enumerate(np.arange(0.1, ev['WALK_END'], 0.48)):
    M.add(verb(pad_tail(step(i), 1.0), 0.5) * 0.35, ts, 1.0, 0.1 * (-1) ** i)
M.add(lp(flutter(0.8, 500, 1200, 5000), 5000) * 0.3, ev['FORM_T'][0], 1.0, 0)          # paper slides out
M.add(bp(np.random.default_rng(9).standard_normal(int(0.35 * SR)), 2000, 7000) * np.hanning(int(0.35 * SR)) * 0.15, ev['CHECK_T'] - 0.15, 1.0, 0)  # pen tick
M.add(slam(0.9) * 0.6, ev['STAMP_T'], 1.0, 0)                                          # stamp
# the building answers: a deep swell and relays clicking in, floor by floor
a, b = ev['LIGHTS_T']
n = int((b - a + 2.5) * SR); tt_ = np.arange(n) / SR
hum = (np.sin(2 * np.pi * 50 * tt_) + 0.5 * np.sin(2 * np.pi * 100 * tt_) + 0.25 * np.sin(2 * np.pi * 150 * tt_)) * np.clip(tt_ / (b - a), 0, 1) ** 1.5
hum *= seg_env(n, 0.2, 1.5)
M.add(hum * 0.10, a, 1.0, 0); M.add(lp(boom(3.0, 70, 35, 0.2), 200) * 0.3, a, 1.0, 0)
rng = np.random.default_rng(7)
for ts in np.sort(rng.uniform(a, b, 26)):
    M.add(verb(pad_tail(die_hit(0.2) * 0.25, 1.5), 1.2) * 0.3, ts, 1.0, rng.uniform(-0.8, 0.8))
M.add(lp(flutter(1.2, 250, 1000, 5000), 4000) * 0.25, ev['PAGE_T'][1] - 1.2, 1.0, 0)    # the page arrives
for k, at in ev['VO_AT'].items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=1.0, key=k)
M.duck(0.5)
print('voice/fx dB', M.report_voice())
M.master(WORK / 'mix.wav', rms_target=0.08)
