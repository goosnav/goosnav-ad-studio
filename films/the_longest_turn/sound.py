"""THE LONGEST TURN: sound design, score and the broadcaster's voice. Reads events.json written by film.py.

  python3 films/the_longest_turn/sound.py --format 4x5

The narration is built from the dry Piper takes (studio.vo, en_US-joe-medium, --slow 0.97 --reverb 0) and
run through a broadcast chain here: high-pass, presence lift, fast compression, then a stadium slapback.
"""
import sys, os, json, argparse
import numpy as np
from scipy.io import wavfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config
from studio.audio import *

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='4x5'); a = ap.parse_args()
FILM = 'the_longest_turn'
WORK = config.path('work', FILM, a.format)
VO = config.path('work', FILM, 'vo')
DUR = 87.0
ev = json.load(open(WORK / 'events.json'))
T = ev['T']
seed(23)
rg = np.random.default_rng(5)
M = Mix(DUR)
N = M.N
add = M.add
curve = M.curve

def noise(sec, s=None):
    return (np.random.default_rng(s) if s is not None else rg).standard_normal(int(sec * SR))

# ------------------------------------------------------------------ the broadcaster
def broadcast(x):
    x = hp(x, 140, 2)
    x = x + 0.55 * bp(x, 2200, 4200)                  # presence
    x = lp(x, 7800, 2)
    env = lp(np.abs(x), 25, 1) + 1e-6                 # fast compressor, 4:1 above -22 dB
    thr = 10 ** (-22 / 20) * np.max(env)
    g = np.where(env > thr, (env / thr) ** (1 / 4 - 1), 1.0)
    y = x * g
    y = np.tanh(y / np.max(np.abs(y)) * 1.6)          # a little console drive
    d1, d2 = int(0.105 * SR), int(0.235 * SR)         # stadium slapback
    out = np.zeros(len(y) + d2 + int(1.5 * SR))
    out[:len(y)] += y
    out[d1:d1 + len(y)] += 0.30 * lp(y, 3000)
    out[d2:d2 + len(y)] += 0.14 * lp(y, 2200)
    wet = verb(pad_tail(lp(y, 4000) * 0.5, 1.5), 1.0)[:, 0][:len(out)] - pad_tail(lp(y, 4000) * 0.5, 1.5)[:len(out)]
    out[:len(wet)] += 0.12 * wet
    return out / np.max(np.abs(out)) * 0.9

VO_AT = {'01': 1.4, '02': 7.2, '03': 15.4, '04': 22.6, '05': 33.2, '06': 44.6, '07': 51.2, '08': 58.6,
         '09': 66.0, '10': 70.6, '11': 76.0, '12': 84.0}
for k in VO_AT:
    sr, x = wavfile.read(str(VO / f'dry_{k}.wav'))
    y = broadcast(x.astype(np.float64) / 32768)
    wavfile.write(str(VO / f'bc_{k}.wav'), SR, (y * 32767).astype(np.int16))

# ------------------------------------------------------------------ storm
print('rain')
storm = curve([(0, 0.25), (1.0, 1.0), (44.8, 1.0), (45.4, 0.35), (50.0, 0.35), (50.6, 1.0), (56.3, 1.0), (58.3, 0.0), (DUR, 0.0)])
for s, pan in ((1, -0.5), (2, 0.5)):
    r = lp(bp(noise(DUR, s), 600, 6000), 4500) * (0.75 + 0.25 * lp(noise(DUR, s + 10), 0.6) * 8)
    add(r * storm * 0.045, 0, 1.0, pan)
    add(lp(noise(DUR, s + 20), 400) * storm * 0.06, 0, 1.0, pan)          # the weight of it
# distant rolling thunder bed
roll = lp(noise(DUR, 40), 90) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * tt(N)))
add(np.tanh(roll * 3) * storm * 0.10, 0)

print('thunder')
def thunder(strength, far=0.2, slow=False):
    n = int(6 * SR); t = tt(n)
    crack = hp(noise(0.5), 1200) * np.exp(-tt(int(0.5 * SR)) * 14)
    crack = np.concatenate([crack, np.zeros(n - len(crack))])
    body = lp(noise(6), 160 if not slow else 90) * np.exp(-t * (0.8 if not slow else 0.45))
    grumble = lp(noise(6), 60) * (0.5 + 0.5 * np.sin(2 * np.pi * rg.uniform(1.5, 3) * t)) * np.exp(-t * 0.6)
    d = int(far * SR)
    y = np.zeros(n + d)
    y[:n] += crack * (0.0 if slow else 0.8) * strength
    y[d:] += np.tanh((body * 3 + grumble * 2)) * 0.9 * strength
    return y
for (t0, c, s) in ev['strikes']:
    slow = 45.0 <= t0 <= 50.0
    g = 0.4 if not slow else 0.5
    if any(0 <= t0 - v < 8.6 for v in (22.6,)):   # distant under the dice line
        g = 0.2
    add(thunder(s, 0.05 + 0.35 * (1.2 - s), slow), t0, g, rg.uniform(-0.6, 0.6))
    if slow:
        add(boom(4.0, 60, 22, 0.2) * 0.3, t0 + 0.1)

# ------------------------------------------------------------------ score (D minor, war-film strings)
print('score')
D = 73.42
def pad(freqs, sec, cut=900, det=0.004):
    x = sum(saw_stack(f, int(sec * SR), det, 10) for f in freqs)
    return lp(x, cut) / len(freqs)
Dm = [D, D * 1.5, D * 2, D * 2 * 1.189]             # D A D F
Bb = [D * 0.8909 * 2 / 2, D * 1.189 * 2 / 2 * 1.0, D * 2 * 0.8909, D * 2 * 1.189]
DM = [D, D * 1.5, D * 2, D * 2 * 1.26, D * 3]        # D major
sec_env = lambda sec, a, r: seg_env(int(sec * SR), a, r)
x = pad(Dm, 6.8, 500) * sec_env(6.8, 2.5, 0.8); add(x * 0.10, 0.0, 1.0, -0.1); add(x * 0.10, 0.0, 1.0, 0.1)
x = pad(Dm, 8.4, 900) * sec_env(8.4, 0.3, 0.5) * np.linspace(0.6, 1.2, int(8.4 * SR)); add(x * 0.11, 6.8)
# timpani ostinato under the fortress run
tb = 6.9
while tb < 14.9:
    add(lp(slam(1.4), 300) * 0.5, tb, 1.0, -0.2); tb += 0.5
    if tb < 14.9:
        add(lp(slam(0.9), 300) * 0.3, tb + 0.0, 1.0, 0.2)
    tb += 0.25
# reinforcements: a cluster that tightens to the tear
x = pad([D * 2, D * 2 * 1.06, D * 2 * 1.19, D * 3], T['T_TEAR'] - 15.0, 1400, 0.01) * np.linspace(0.2, 1.0, int((T['T_TEAR'] - 15.0) * SR)) ** 2
add(x * 0.12, 15.0)
x = pad(Bb, 20.2 - T['T_TEAR'], 900) * sec_env(20.2 - T['T_TEAR'], 0.05, 0.6); add(x * 0.12, T['T_TEAR'])
# the dice: low brass drone, then Bb -> Dm under the aftermath
x = pad([D / 2, D, D * 1.5], 12.6, 600) * sec_env(12.6, 1.0, 1.0); add(x * 0.10, 20.2)
# rulebook: the door opens onto D major, choir and bells
x = pad(Dm, 1.8, 700) * sec_env(1.8, 0.4, 0.4); add(x * 0.10, 32.8)
ch = choir([D * 2, D * 3, D * 4 * 1.26 / 1.0, D * 4], int(9.5 * SR))
add(verb(ch * seg_env(len(ch), 2.5, 2.5), 0.6) * 0.06, T['T_OPEN'] + 0.2)
x = pad(DM, 9.6, 1200) * sec_env(9.6, 2.0, 1.5); add(x * 0.09, T['T_OPEN'])
for k, f in enumerate([587.33, 739.99, 880.0, 1174.66, 880.0, 739.99]):
    add(verb(pad_tail(bell(f, 3.0), 2), 0.7) * 0.04, T['T_OPEN'] + 1.0 + 1.1 * k, 1.0, rg.uniform(-0.5, 0.5))
# the five: everything drops. sub, a held high tone, a heartbeat
sub = np.sin(2 * np.pi * 36.7 * tt(int(6.2 * SR))) * sec_env(6.2, 0.8, 0.3)
add(sub * 0.22, 44.2)
tone = (np.sin(2 * np.pi * 1760 * tt(int(6 * SR))) + 0.3 * np.sin(2 * np.pi * 2637 * tt(int(6 * SR)))) * sec_env(6, 1.5, 0.05)
add(tone * 0.02, 44.1)
tb, gap = 44.6, 1.25
while tb < T['T_LAND'] - 0.3:
    add(lp(slam(1.0), 180) * 0.55, tb); add(lp(slam(0.6), 180) * 0.3, tb + 0.25)
    tb += gap; gap *= 0.93
# the landing
add(die_hit(1.6) * 1.2, T['T_LAND']); add(boom(3.5, 90, 30, 0.3) * 0.7, T['T_LAND'])
for dt_, g in ((0.26 * 1.7, 0.45), (0.40 * 1.6, 0.25), (0.62 * 1.4, 0.12)):
    add(die_hit(0.6) * g, T['T_LAND'] + dt_)
# stadium roar and a brass stab in D major
n = int(7.5 * SR); t = tt(n)
roar = bp(noise(7.5), 250, 3200) * (1 + 0.3 * lp(noise(7.5), 4) * 10)
roar_env = np.minimum(t / 0.5, 1) * np.exp(-np.maximum(t - 1.8, 0) * 0.55)
add(verb(roar * roar_env, 0.5) * 0.10, T['T_LAND'] + 0.15)
stab = pad(DM, 4.5, 2400, 0.006) * sec_env(4.5, 0.02, 3.0); add(verb(stab, 0.5) * 0.10, T['T_LAND'] + 0.1)
x = pad(DM, 6.2, 800) * sec_env(6.2, 0.5, 2.0); add(x * 0.08, 51.0)
# the fortress falls: four walls
for tf in ev['falls']:
    add(slam(1.6) * 0.5, tf, 1.0, rg.uniform(-0.4, 0.4)); add(lp(noise(0.4), 2500) * np.exp(-tt(int(0.4 * SR)) * 9) * 0.25, tf + 0.02)
add(boom(3.0, 70, 25, 0.3) * 0.35, ev['falls'][-1])
# the storm passes: one long resolving chord, then the room
x = pad([D, D * 1.5, D * 2, D * 2 * 1.26], 9.0, 700) * sec_env(9.0, 2.0, 4.0); add(x * 0.08, 56.8)

# ------------------------------------------------------------------ hits
print('hits')
for ts_ in ev['slams']:
    add(slam(1.2) * 0.45, ts_, 1.0, rg.uniform(-0.6, 0.6))
    add(bp(noise(0.5), 1500, 7000) * np.exp(-tt(int(0.5 * SR)) * 10) * 0.18, ts_ + 0.01, 1.0, rg.uniform(-0.6, 0.6))
    add(whoosh(0.45, 200, 1600) * 0.12, ts_ - 0.4)
# pack strains, then tears like a dam
n = int((T['T_TEAR'] - 15.6) * SR); t = tt(n)
creak = np.sin(2 * np.pi * np.cumsum(55 + 20 * lp(noise(n / SR), 3) * 30) / SR) * (t / t[-1]) ** 2
add(np.tanh(creak * 2) * 0.15, 15.6)
rip = bp(noise(0.7), 900, 6000) * (rg.random(int(0.7 * SR)) > 0.6) * np.exp(-tt(int(0.7 * SR)) * 4)
add(rip * 0.6, T['T_TEAR'] - 0.05)
add(boom(4.0, 100, 28, 0.6) * 0.8, T['T_TEAR'])
add(lp(flutter(2.2, 900, 600, 5000), 5000) * seg_env(int(2.2 * SR), 0.02, 1.2) * 0.6, T['T_TEAR'] + 0.05)
add(lp(noise(2.5), 1200) * seg_env(int(2.5 * SR), 0.05, 1.8) * 0.35, T['T_TEAR'])     # the flood
for tl in ev['boost_land']:
    add(slam(0.7) * 0.3, tl, 1.0, rg.uniform(-0.5, 0.5))
    add(bp(noise(0.3), 1200, 6000) * np.exp(-tt(int(0.3 * SR)) * 12) * 0.12, tl, 1.0, rg.uniform(-0.5, 0.5))
add(whoosh(0.9, 300, 3500) * 0.6, 19.25)                    # the card into the lens
add(slam(1.5) * 0.4, 20.08)
# meteors: descending whistle and fire, then impact
for i, (ta, ti) in enumerate(zip(ev['appear'], ev['impacts'])):
    n = int((ti - ta) * SR); t = tt(n)
    f = 1800 * (320 / 1800) ** (t / t[-1])
    wh = np.sin(2 * np.pi * np.cumsum(f) / SR) * (t / t[-1]) ** 1.5
    fire = bp(noise(n / SR), 300, 2500) * (t / t[-1]) ** 2
    pan = (-0.3, 0.5, -0.6)[i]
    add(wh * 0.04 + fire * 0.09, ta, 1.0, pan)
    add(boom(3.0, 110, 26, 0.8) * seg_env(int(3.0 * SR), 0.0, 1.2) * 0.85, ti, 1.0, pan * 0.5)
    crack = hp(noise(1.5), 2000) * (rg.random(int(1.5 * SR)) > 0.93) * np.exp(-tt(int(1.5 * SR)) * 2.5)
    add(crack * 0.3, ti + 0.03, 1.0, pan)
    add(lp(noise(2.0), 3000) * np.exp(-tt(int(2 * SR)) * 1.5) * 0.15, ti + 0.1, 1.0, -pan)   # debris
# fire crackle in the craters
n = int((T['T_S5'] - 25.0) * SR)
cr = hp(noise(n / SR), 1500) * (rg.random(n) > 0.985) * 0.3
add(lp(cr, 6000) * seg_env(n, 0.3, 0.5), 25.0, 1.0, 0.2)
# rulebook: a cathedral door
n = int(3.2 * SR); t = tt(n)
door = np.sin(2 * np.pi * np.cumsum(42 + 18 * np.sin(2 * np.pi * 0.7 * t) + 12 * lp(noise(3.2), 6) * 20) / SR)
add(verb(np.tanh(door * 2.5) * sec_env(3.2, 0.2, 0.8) * 0.18, 0.7), T['T_OPEN'])
add(verb(pad_tail(slam(1.4) * 0.4, 2), 0.8), T['T_OPEN'] + 3.2)
add(whoosh(2.5, 200, 1800) * 0.25, T['T_OPEN'] + 0.4)

# ------------------------------------------------------------------ the room
print('room')
room = curve([(0, 0), (57.8, 0), (59.0, 1.0), (DUR - 0.8, 1.0), (DUR, 0)])
win = lp(bp(noise(DUR, 70), 400, 5000), 2500) * 0.02
add(win * room, 0, 1.0, 0.4)
tb = 58.9
while tb < DUR - 1.0:
    tick = bp(noise(0.03), 1800, 5000) * np.exp(-tt(int(0.03 * SR)) * 200)
    add(tick * (0.10 if int(tb) % 2 else 0.08), tb, 1.0, -0.5)
    tb += 1.0
hum = (np.sin(2 * np.pi * 120 * tt(N)) + 0.3 * np.sin(2 * np.pi * 240 * tt(N))) * 0.004
add(hum * room, 0)
# the dispatch slides under the door
add(lp(flutter(2.2, 260, 400, 3500), 3000) * seg_env(int(2.2 * SR), 0.3, 0.8) * 0.35, T['T_SLIDE'], 1.0, -0.3)
add(bp(noise(2.2), 300, 1800) * seg_env(int(2.2 * SR), 0.4, 0.9) * 0.08, T['T_SLIDE'], 1.0, -0.3)
# products: a small warm chord, bells
x = pad([D * 2, D * 3, D * 4 * 1.26 / 1, D * 4], 8.5, 1400) * sec_env(8.5, 1.5, 2.5); add(x * 0.05, 75.0)
for k, f in enumerate([293.66, 369.99, 440.0, 587.33]):
    add(verb(pad_tail(bell(f, 3.0), 2), 0.7) * 0.035, 75.2 + 0.45 * k, 1.0, rg.uniform(-0.4, 0.4))
# end card: "Your roll." then one die, rolled on a table
tr = 84.75
for dt_, g in ((0.0, 0.5), (0.22, 0.32), (0.38, 0.2), (0.5, 0.12), (0.58, 0.06)):
    add(die_hit(0.35) * g, tr + dt_, 1.0, 0.1)

# ------------------------------------------------------------------ narration
for k, at in VO_AT.items():
    M.add_voice(VO / f'bc_{k}.wav', at, gain=1.0, key=k)
M.duck(0.75)
print('voice/fx dB (studio window)', M.report_voice())
# voice over effects measured only where the voice is speaking (the studio window also counts the hits
# that are deliberately placed in the pauses between sentences)
def active_ratio():
    vo = np.abs(M.VL) + np.abs(M.VR)
    env = lp(vo, 8.0, 1)
    out = {}
    for k, at in M.voice_at.items():
        n = len(wavfile.read(str(VO / f'dry_{k}.wav'))[1])
        a, b = int(at * SR), min(int(at * SR) + n, M.N)
        e = env[a:b]; on = e > 0.25 * np.max(e)
        vv = np.sqrt(np.mean((M.VL[a:b] ** 2 + M.VR[a:b] ** 2)[on]))
        fx = np.sqrt(np.mean((M.L[a:b] ** 2 + M.R[a:b] ** 2)[on]))
        out[k] = round(20 * np.log10(vv / (fx + 1e-9)), 1)
    return out
print('voice/fx dB (while speaking)', active_ratio())
M.master(WORK / 'mix.wav')
print('mix written', WORK / 'mix.wav')
