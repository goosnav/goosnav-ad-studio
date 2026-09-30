"""Dry character voices, tactile prop foley, then an outsized desert explosion."""
import json
import sys

import numpy as np

sys.path.insert(0, '/home/goosnav/Desktop/code/goosnav-ad-studio')
from studio import config
from studio.audio import Mix, SR, boom, flutter, hp, lp, slam, whoosh

WORK = config.path('work', 'three_brags', '4x5')
VO = config.path('work', 'three_brags', 'vo')
events = json.loads((WORK / 'events.json').read_text())
mix = Mix(events['duration'])
samples = mix.N
seconds = np.arange(samples) / SR
noise = np.random.default_rng(31).standard_normal(samples)
wind = lp(noise, 450) * (.11 + .03 * np.sin(2 * np.pi * .15 * seconds))
wind *= np.clip((events['end_scene'] - seconds) / .4, 0, 1)
mix.add(wind, 0, .28)

mix.add(flutter(.65, 520, 500, 5600), 6.45, .16, -.55)
mix.add(whoosh(1.85, 210, 2100), 7.35, .24, -.5)
mix.add(flutter(.8, 650, 600, 6000), 10.85, .19, .15)
for start in (11.78, 12.65, 13.48):
    mix.add(whoosh(.85, 270, 3300), start, .20, .16)
mix.add(slam(.55), 14.67, .12, .14)
mix.add(flutter(.52, 330, 1200, 5500), 16.6, .11, .52)

for tick in (17.18, 17.38, 17.58, 17.78):
    count = int(.09 * SR)
    time_values = np.arange(count) / SR
    click = np.sin(2 * np.pi * 1600 * time_values) * np.exp(-time_values * 62)
    mix.add(click, tick, .035, .48)

mix.add(boom(4.1, 110, 22, .75), events['explode'], .82)
mix.add(slam(1.1), events['explode'] + .07, .25)
mix.add(hp(np.random.default_rng(19).standard_normal(int(2.2 * SR)), 2800) *
        np.exp(-np.arange(int(2.2 * SR)) / SR * 2.1), events['explode'] + .14, .018)
mix.add(whoosh(2.7, 120, 1500), events['explode'] + .35, .32)
for index, time_at in enumerate((18.55, 18.91, 19.32, 19.82, 20.40)):
    mix.add(slam(.4) * .28, time_at, .15, -.7 + .35 * index)

for key, time_at in events['voice_at'].items():
    mix.add_voice(VO / f'vo_{key}.wav', time_at, gain=1.0, key=key)
mix.duck(.82)
print('Voice over effects (dB):', mix.report_voice())
mix.master(WORK / 'mix.wav', rms_target=.10)
print(WORK / 'mix.wav')
