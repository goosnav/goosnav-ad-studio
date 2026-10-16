import copy
import json
import math
from pathlib import Path
import random
import struct
import wave

import pytest

from harness.config import load_config
from harness.contracts import ContractError
from harness.direction import check_cast, check_direction, check_mix

RETURN_SLOT = Path.home()/'.local/share/goosnav-ad-studio/runs/20261015-130307-23007d15/workspaces/ad-01-audio'

PLAN = {
    'duration': 10,
    'beats': [{'start': 0, 'end': 3, 'shot': 'medium', 'picture': 'man at slot', 'sound': 'wind'},
              {'start': 3, 'end': 5.5, 'shot': 'close', 'picture': 'hands stop', 'sound': 'line'},
              {'start': 5.5, 'end': 7.5, 'shot': 'reverse wide', 'picture': 'queue, large', 'sound': 'quiet'}],
    'cast': [{'speaker': 'A', 'character': 'borrower, a man', 'gender': 'male', 'voice': 'am_onyx',
              'performance': 'polite'},
             {'speaker': 'B', 'character': 'unseen clerk', 'gender': 'neutral', 'voice': 'af_bella',
              'performance': 'flat'}],
    'lines': [{'speaker': 'B', 'text': "There's a hold on it.", 'start': 1.0, 'end': 3.0},
              {'speaker': 'A', 'text': 'For who?', 'start': 3.3, 'end': 4.3}],
    'end_card': {'seconds': 2.5, 'title': 'Goosnav Book Two. Keep yours.', 'picture': 'book hero'},
    'mix': 'dialogue lead, wind under',
}


def plan(**changes):
    p = copy.deepcopy(PLAN)
    for path, value in changes.items():
        target = p; keys = path.split('.')
        for k in keys[:-1]:
            target = target[int(k)] if k.isdigit() else target[k]
        target[int(keys[-1]) if keys[-1].isdigit() else keys[-1]] = value
    return p


def test_valid_plan_passes():
    assert check_direction(plan(), load_config())


@pytest.mark.parametrize('changes,message', [
    ({'cast.0.voice': 'af_heart'}, 'female voice'),
    ({'lines.0.end': 1.6}, 'words/s'),
    ({'beats.1.start': 3.5}, 'contiguous'),
    ({'beats.2.end': 7.0}, 'end where the end card'),
    ({'beats.0.end': .5, 'beats.1.start': .5}, 'at least'),
    ({'end_card.title': 'Buy it at www.goosnav.shop'}, 'without the web address'),
    ({'end_card.seconds': 1}, 'end_card.seconds'),
    ({'lines.1.speaker': 'C'}, 'not in the cast'),
])
def test_plan_faults_are_rejected(changes, message):
    with pytest.raises(ContractError, match=message):
        check_direction(plan(**changes), load_config())


def write_mix(path, seconds, parts):
    """parts: [(start, end, kind, amplitude)] with kind tone (speech stand-in) or noise."""
    rate = 48000; x = [0.0] * int(seconds * rate); rng = random.Random(1)
    for start, end, kind, amp in parts:
        for i in range(int(start * rate), int(end * rate)):
            x[i] += amp * (math.sin(2 * math.pi * 220 * i / rate) if kind == 'tone' else rng.uniform(-1, 1))
    with wave.open(str(path), 'wb') as w:
        w.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        w.writeframes(b''.join(struct.pack('<h', max(-32767, min(32767, int(v * 32767)))) for v in x))


def timeline(*lines):
    return {'sample_rate': 48000, 'fps': 24, 'duration': 4, 'events': [],
            'dialogue': [{'speaker': 'A', 'voice': 'am_onyx', 'text': t, 'start_sample': int(a * 48000),
                          'end_sample': int(b * 48000)} for t, a, b in lines]}


def test_clear_dialogue_passes_and_buried_dialogue_fails(tmp_path):
    good, bad, loud = tmp_path/'good.wav', tmp_path/'bad.wav', tmp_path/'loud.wav'
    t = timeline(('line', 1, 2))
    write_mix(good, 4, [(0, 4, 'noise', .02), (1, 2, 'tone', .3)])
    assert check_mix(good, t)['speech'][0]['db'] > -24
    write_mix(bad, 4, [(0, 4, 'noise', .1), (1, 2, 'tone', .05)])
    with pytest.raises(ContractError, match='over the bed'):
        check_mix(bad, t)
    write_mix(loud, 4, [(0, 4, 'noise', .01), (1, 2, 'tone', .3), (3, 4, 'noise', .9)])
    with pytest.raises(ContractError, match='over the loudest line'):
        check_mix(loud, t)


@pytest.mark.skipif(not (RETURN_SLOT/'mix.wav').is_file(), reason='RETURN SLOT run not on this machine')
def test_the_return_slot_mix_that_shipped_buried_is_rejected():
    with pytest.raises(ContractError, match='not the lead'):
        check_mix(RETURN_SLOT/'mix.wav', json.loads((RETURN_SLOT/'timeline.json').read_text()))


def test_timeline_must_use_the_cast_voice_in_order():
    t = timeline(("There's a hold on it.", 1, 3), ('For who?', 3.3, 4.3))
    t['dialogue'][0]['speaker'] = 'B'; t['dialogue'][0]['voice'] = 'af_bella'
    check_cast(t, PLAN)
    t['dialogue'][1]['voice'] = 'af_heart'
    with pytest.raises(ContractError, match='cast as am_onyx'):
        check_cast(t, PLAN)
