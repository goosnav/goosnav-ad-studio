"""Product content handoff, the scripting prompt's craft rules and procedural foley."""
import json

import numpy as np
import pytest

from harness import foley
from harness.config import load_config
from harness.content import product_content
from harness.production import ANIMATOR_JOB, SCRIPT_JOB, production_brief
from harness.workflow import build_tasks

PRODUCTS = [{'name': 'Goosnav Book 2', 'description': 'Book'}, {'name': 'Goosklerf', 'description': 'Cards'}]


def test_inventory_matches_configured_products_and_keeps_membership_honest():
    content = {c['product']: c for c in product_content({'products': PRODUCTS})}
    assert set(content) == {'Goosnav Book 2', 'Goosklerf'}
    book = content['Goosnav Book 2']
    assert book['confirmed'] and all(i['locator'] and i['evidence'] for i in book['confirmed'])
    # Interior pages in the openable model are not proven to be printed in Book Two.
    assert not any('Page ' in i['item'] for i in book['confirmed'])
    assert any('NOT Book Two' in i['evidence'] for i in book['unconfirmed'])
    assert 'footoil' in content['Goosklerf']['cards']['ids']
    assert product_content({'products': [{'name': 'Unrelated mug'}]}) == []
    assert [c['product'] for c in product_content({'products': ['Goosklerf']})] == ['Goosklerf']


def test_compact_inventory_points_to_the_card_list_instead_of_inlining_it():
    compact = {c['product']: c for c in product_content({'products': PRODUCTS}, compact=True)}
    cards = compact['Goosklerf']['cards']
    assert cards['count'] > 100 and isinstance(cards['ids'], str)


def test_script_job_builds_on_real_content_and_comedy_craft():
    for phrase in ('PRODUCT TASTE FIRST', 'PRODUCT_CONTENT', 'MAKE IT FUNNY', 'withholding',
                   'escalation', 'tight', 'button', 'is a guideline, not a limit'):
        assert phrase in SCRIPT_JOB
    assert 'No essential handoff, card reveal, book opening' not in SCRIPT_JOB
    assert 'No compulsory joke or twist' not in SCRIPT_JOB
    for phrase in ('blender/book2.py', 'face_camera', 'nose axis', 'sounds', 'harness.foley'):
        assert phrase in ANIMATOR_JOB


def test_compact_script_brief_hands_product_content_to_the_writer(tmp_path):
    config = load_config(overrides={'products': PRODUCTS})
    state = {'config': config, 'tasks': build_tasks(1, compact=True)}
    prompt = production_brief(state, state['tasks'][0], tmp_path, 60, tmp_path)
    project = json.loads(prompt.split('\nPROJECT\n')[1])
    assert [c['product'] for c in project['PRODUCT_CONTENT']] == ['Goosnav Book 2', 'Goosklerf']


def test_foley_places_events_against_measured_lines_and_stays_under_speech():
    lines = [{'start': 1.0, 'end': 2.5}, {'start': 4.0, 'end': 5.0}]
    bed, events = foley.render(8, {'ambience': 'hall', 'events': [
        {'name': 'page_turn', 'after_line': 0, 'offset': 0.25},
        {'name': 'slam', 'before_line': 1}, {'name': 'shush', 'at': 6.5}]}, lines)
    assert [(e['name'], e['at']) for e in events] == [('page_turn', 2.75), ('slam', 4.0), ('shush', 6.5)]
    assert bed.shape == (8 * foley.RATE, 2) and np.abs(bed).max() <= 0.98 + 1e-9
    # Mixed at BED_GAIN_DB, the loudest 400 ms stays below a -21 dBFS dialogue line.
    assert foley._window_db(bed[:, 0]) + foley.BED_GAIN_DB < -21


@pytest.mark.parametrize('bad', [
    {'events': [{'name': 'laser'}]},
    {'events': [{'name': 'slam'}]},
    {'events': [{'name': 'slam', 'at': 1, 'after_line': 0}]},
    {'events': [{'name': 'slam', 'after_line': 9}]},
    {'events': [{'name': 'slam', 'at': 1, 'gain_db': 20}]},
    {'ambience': 'space'}])
def test_foley_rejects_unknown_or_ambiguous_events(bad):
    with pytest.raises(ValueError):
        foley.render(4, bad, [{'start': 0.5, 'end': 1.0}])
