"""THE ARCHIVE: world tone, foley, dialogue (bible §25). No music; one low two-note motif under the wide."""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *

FILM = 'the_archive'
WORK = config.path('work', FILM, 'lpv'); VO = config.path('work', FILM, 'vo')
ev = json.load(open(WORK / 'events.json'))
M = Mix(ev['dur']); N = M.N; END = ev['end']
t = np.arange(N) / SR
# world tone: HVAC + fluorescent hum, stops at the end card
hvac = lp(np.random.default_rng(1).standard_normal(N), 380) * 0.5 + 0.08 * np.sin(2 * np.pi * 120 * t) + 0.03 * np.sin(2 * np.pi * 240 * t)
tone = M.curve([(0, 0), (0.4, 0.7), (END - 0.1, 0.7), (END, 0), (ev['dur'], 0)])
M.add(hvac * tone * 0.22, 0, 1.0, -0.2); M.add(lp(np.random.default_rng(2).standard_normal(N), 300) * tone * 0.1, 0, 1.0, 0.2)
# one distant metal clank far down the aisle in the wide, with a huge room
M.add(verb(pad_tail(die_hit(0.4) * 0.5, 4), 1.6) * 0.35, 2.3, 1.0, 0.3)
# a two-note motif, very low, under the opening
for k, (f, at) in enumerate(((98.0, 0.3), (73.4, 2.6))):
    n = int(3.5 * SR); x = saw_stack(f, n, 0.002, 5) * seg_env(n, 0.8, 2.0)
    M.add(lp(x, 500) * 0.05, at, 1.0, 0)
# foley: each item put in the tray, the book on the desk, the book opening, a page
def clack(h=1.0):
    n = int(0.25 * SR); tt_ = np.arange(n) / SR
    return (bp(np.random.default_rng(int(h * 100)).standard_normal(n), 800, 4000) * np.exp(-tt_ * 60) + 0.5 * np.sin(2 * np.pi * 320 * h * tt_) * np.exp(-tt_ * 40)) * 0.6
for i, (a, b) in enumerate(ev['ITEM_T']):
    M.add(clack(1.0 + 0.2 * i) * 0.5, b - 0.2, 1.0, -0.3)
    M.add(flutter(0.25, 300, 1000, 4000) * 0.15, a + 0.4, 1.0, 0)          # sleeve rustle as he reaches
M.add(slam(0.6) * 0.45, ev['BOOK_T'][1] - 0.05, 1.0, 0.1)                  # book on the desk
M.add(lp(flutter(0.5, 900, 1500, 6000), 5000) * 0.35, ev['OPEN_T'] + 0.05, 1.0, 0)  # the book opens
M.add(lp(flutter(0.35, 600, 1500, 6000), 5000) * 0.25, ev['OPEN_T'] + 1.4, 1.0, 0)  # a page
# dialogue
for k, at in ev['VO_AT'].items():
    M.add_voice(VO / f'vo_{k}.wav', at, gain=1.0, key=k)
M.duck(0.5)
print('voice/fx dB', M.report_voice())
M.master(WORK / 'mix.wav', rms_target=0.1)
print('mix', WORK / 'mix.wav')
