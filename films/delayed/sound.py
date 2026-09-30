"""DELAYED: terminal air, PA chimes, zip, box, card slaps, dice, a jet taxiing beyond the glass (bible §25)."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *
FILM = 'delayed'
WORK = config.path('work', FILM, 'lpv'); VO = config.path('work', FILM, 'vo')
ev = json.load(open(WORK / 'events.json'))
M = Mix(ev['dur']); N = M.N; END = ev['end']
tone = M.curve([(0, 0), (0.3, 1), (END - 0.05, 1), (END, 0), (ev['dur'], 0)])
t = np.arange(N) / SR
M.add((lp(np.random.default_rng(1).standard_normal(N), 350) * 0.6 + 0.05 * np.sin(2 * np.pi * 120 * t)) * tone * 0.16, 0, 1.0, 0)
def chime():
    out = []
    for f in (784.0, 622.3):
        n = int(0.7 * SR); tt_ = np.arange(n) / SR
        out.append((np.sin(2 * np.pi * f * tt_) + 0.3 * np.sin(2 * np.pi * 2 * f * tt_)) * np.exp(-tt_ * 3))
    return np.concatenate([out[0][: int(0.45 * SR)], out[1]])
for k in ('01', '04'):
    M.add(verb(pad_tail(chime(), 3), 1.4) * 0.12, ev['VO_AT'][k] - 1.0, 1.0, 0)
a, b = ev['BOX_T']
M.add(bp(np.random.default_rng(3).standard_normal(int(0.6 * SR)), 1500, 6000) * np.linspace(0.2, 1, int(0.6 * SR)) * 0.08, a - 0.5, 1.0, 0.4)  # zip
M.add(slam(0.35) * 0.5, b, 1.0, 0)
def card_slap(k):
    n = int(0.12 * SR); tt_ = np.arange(n) / SR
    return bp(np.random.default_rng(k).standard_normal(n), 1200, 7000) * np.exp(-tt_ * 90) * 0.6
for i, tc in enumerate(ev['CARD_T']):
    M.add(card_slap(i) * 0.55, tc, 1.0, 0.2 * (-1) ** i)
for j in range(5):
    M.add(die_hit(0.1) * (0.35 - 0.05 * j), ev['DICE_T'] + 0.12 * j + 0.03 * j * j, 1.0, 0.2)
# the jet, muffled through the glass: whine + roar rising as it taxis
a, b = ev['PLANE_T']
n = int((b - a) * SR); tt_ = np.arange(n) / SR
env = np.clip(tt_ / 2.0, 0, 1) * seg_env(n, 0.5, 1.0)
jet = lp(np.random.default_rng(5).standard_normal(n), 600) * 0.6 + 0.15 * np.sin(2 * np.pi * (1200 + 300 * tt_ / tt_[-1]) * tt_)
M.add(lp(jet, 1500) * env * 0.035 * M.curve([(0, 1), (END - 0.05, 1), (END, 0), (ev['dur'], 0)])[int(a * SR): int(a * SR) + n], a, 1.0, -0.4)
for k, at in ev['VO_AT'].items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=0.3 if ev['SPEAKER'][k] == 'PA' else 1.0, key=k)   # PA is dense (band-limited, saturated)
M.duck(0.5)
print('voice/fx dB', M.report_voice())
M.master(WORK / 'mix.wav', rms_target=0.08)
