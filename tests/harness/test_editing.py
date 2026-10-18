"""Editorial regression tests: no ad iteration or Blender rendering."""
import json

import pytest

from harness.config import load_config
from harness.contracts import ContractError, validate
from harness.direction import check_direction
from harness.editing import validate_plan, retime_timeline, validate_conformance
from harness.workflow import build_tasks, ROLES


def source():
    rate = 48000
    return {'fps': 24, 'sample_rate': rate, 'duration': 10.0,
            'dialogue': [
                {'speaker': 'A', 'voice': 'am_michael', 'text': 'First line',
                 'start_sample': rate, 'end_sample': 2 * rate},
                {'speaker': 'A', 'voice': 'am_michael', 'text': 'Second line',
                 'start_sample': 4 * rate, 'end_sample': 5 * rate}],
            'events': [{'sample': int(5.5 * rate), 'kind': 'thud'}]}


def direction():
    return {'duration': 10, 'end_card': {'seconds': 2.5}}


def plan():
    return {'segments': [
        {'start': 0, 'end': 2.5, 'reason': 'first complete line'},
        {'start': 3.2, 'end': 7.5, 'reason': 'cut dead air'},
        {'start': 7.5, 'end': 10, 'reason': 'protect end card'}],
        'removed_lines': [], 'sound_plan': 'Dry dialogue and thud; no music.'}


def test_editor_can_trim_pause_without_bending_speech_time():
    original = source()
    assert validate_plan(plan(), original, load_config(), direction())['duration'] == pytest.approx(9.3)
    edited = retime_timeline(original, plan())
    assert edited['duration'] == pytest.approx(9.3)
    assert edited['dialogue'][0]['start_sample'] == 48000
    assert edited['dialogue'][1]['start_sample'] == round(3.3 * 48000)
    assert edited['events'][0]['sample'] == round(4.8 * 48000)


def test_editor_rejects_half_spoken_line_and_split_take():
    bad = plan()
    bad['segments'][0]['end'] = 1.5
    with pytest.raises(ContractError, match='spoken line'):
        validate_plan(bad, source(), load_config(), direction())
    bad = plan()
    bad['segments'] = [
        {'start': 0, 'end': 1.5, 'reason': 'first half'},
        {'start': 1.5, 'end': 7.5, 'reason': 'other half'},
        {'start': 7.5, 'end': 10, 'reason': 'hero'}]
    with pytest.raises(ContractError, match='splits spoken line'):
        validate_plan(bad, source(), load_config(), direction())


def test_editor_protects_end_card():
    bad = plan()
    bad['segments'][-1]['start'] = 7.7
    with pytest.raises(ContractError, match='end-card'):
        validate_plan(bad, source(), load_config(), direction())


def test_editor_does_not_silently_discard_dialogue():
    bad = {'segments': [
        {'start': 0, 'end': 2.9, 'reason': 'first line'},
        {'start': 6, 'end': 7.5, 'reason': 'visual reaction'},
        {'start': 7.5, 'end': 10, 'reason': 'hero'}],
        'removed_lines': [], 'sound_plan': 'quiet'}
    cfg = load_config(None, {'output': {'min_seconds': 1}})
    with pytest.raises(ContractError, match='silently removes line'):
        validate_plan(bad, source(), cfg, direction())
    bad['removed_lines'] = [{'index': 1, 'reason': 'the image carries the response'}]
    assert validate_plan(bad, source(), cfg, direction())['removed_lines'] == [1]
    assert len(retime_timeline(source(), bad)['dialogue']) == 1


def test_final_qa_rejects_stale_source_timeline(tmp_path):
    p = tmp_path / 'timing.json'
    p.write_text(json.dumps(source()))
    with pytest.raises(ContractError, match='edited transcript'):
        validate_conformance(p, plan(), source(), load_config(), direction(), 9.3)
    p.write_text(json.dumps(retime_timeline(source(), plan())))
    assert validate_conformance(p, plan(), source(), load_config(), direction(), 9.3)


def test_independent_script_gate_requires_all_causal_fields(tmp_path):
    data = {'summary': 'checked', 'files': [], 'verdict': 'pass', 'findings': [],
            'logic': [{'script_id': 'one', 'setup': 'A person presents the object',
                       'cause': 'An unusual property of the object',
                       'reaction': 'Another person reacts directly',
                       'payoff': 'The property has a consequence',
                       'product_connection': 'The book is the original object'}]}
    data.update(selected=['one'], reason='causal and feasible')
    validate('select', data, tmp_path, {'count': 1, 'candidate_ids': ['one']})
    del data['logic'][0]['reaction']
    with pytest.raises(ContractError, match='reaction'):
        validate('select', data, tmp_path, {'count': 1, 'candidate_ids': ['one']})


def test_dedicated_editor_and_story_gate_are_in_actual_graph():
    stages = [t['stage'] for t in build_tasks(1)]
    assert stages.index('write') < stages.index('select') < stages.index('direct')
    assert stages.index('animate') < stages.index('edit') < stages.index('frame')
    assert stages.index('frame') < stages.index('qa') < stages.index('creative_qa')
    assert ROLES['edit'] == 'editor' and ROLES['select'] == 'selector'


def test_long_unmotivated_dialogue_pause_is_rejected():
    p = {'duration': 10, 'beats': [{'start': 0, 'end': 7.5, 'shot': 'medium',
           'picture': 'two characters stand', 'sound': 'dialogue', 'faces': ['A']}],
         'cast': [{'speaker': 'A', 'character': 'Goosnav character', 'gender': 'male',
                   'voice': 'am_michael', 'performance': 'flat'}],
         'lines': [{'speaker': 'A', 'text': 'What happened?', 'start': 1, 'end': 2,
                    'delivery': 'plain'},
                   {'speaker': 'A', 'text': 'That happened.', 'start': 4, 'end': 5,
                    'delivery': 'plain'}],
         'mix': 'clear speech',
         'end_card': {'seconds': 2.5, 'title': 'Book Two', 'picture': 'book hero'}}
    with pytest.raises(ContractError, match='unexplained'):
        check_direction(p, load_config())
    p['intentional_silences'] = [{'start': 2, 'end': 4,
                                  'purpose': 'the other character studies the book',
                                  'visible_event': 'turns head and looks at the page'}]
    assert check_direction(p, load_config())
