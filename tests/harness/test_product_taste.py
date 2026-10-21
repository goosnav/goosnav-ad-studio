"""Product-content guidance uses existing jobs/fields, never another agent pass."""
import pytest

from harness.creative import PRODUCT_TASTE, _production_job, job, scope


# The production director retains the established timing/cast schema from briefs.
DIRECTOR = 'Director preface\nPlan the whole ad second by second against TARGET LENGTH:\ncast, beats, lines, end_card'


@pytest.mark.parametrize('stage', tuple(PRODUCT_TASTE))
def test_taste_note_is_added_once_to_the_existing_job(stage):
    original = DIRECTOR if stage == 'direct' else 'Existing stage contract'
    assignment = job(stage, original)
    assert assignment == _production_job(stage, original) + '\n\nPRODUCT TASTE\n' + PRODUCT_TASTE[stage]
    assert assignment.count('\nPRODUCT TASTE\n') == 1
    # Each worker gets only its own small instruction, not the whole policy.
    assert len(PRODUCT_TASTE[stage].split()) <= 120


@pytest.mark.parametrize('stage', ['audio', 'board_review', 'frame', 'qa', 'package', 'unknown'])
def test_unrelated_jobs_are_not_inflated(stage):
    assert stage not in PRODUCT_TASTE
    assert job(stage, 'Existing contract') == _production_job(stage, 'Existing contract')


def test_research_preserves_small_budget_and_honest_provenance():
    text = job('research', 'At most two sources. creative_directions must be text.')
    assert text.startswith('At most two sources. creative_directions must be text.')
    assert 'existing two-source budget' in text
    assert "'Taste:'" in text and 'creative_directions' in text
    assert 'edition membership' in text
    assert 'If unverified, say so' in text
    assert 'Never invent book contents, card rules' in text


def test_source_note_survives_existing_plain_text_handoffs():
    assert 'visual_direction' in job('write', '')
    assert 'visual_direction' in job('select', '')
    assert 'beat.picture' in job('direct', DIRECTOR)
    assert 'source/edition note' in job('creative_qa', '')
    assert 'all fields plain text' in job('write', '')
    assert 'No new research pass' in job('select', '')


def test_content_lettering_is_not_confused_with_promotional_overlays():
    assert 'IS product content' in job('assets', '')
    assert 'Real lettering\non the product is allowed' in job('animate', '')
    assert 'marketing overlays still belong to Frame' in job('animate', '')


def test_no_reference_scene_or_duration_template_is_imposed():
    assert "reference film's setting, cast count, lines, shot count or length" in job('select', '')
    assert 'within configured delivery bounds' in job('direct', DIRECTOR)
    assert 'No mandatory music, page turn, sample count or runtime' in job('edit', '')
    assert 'not resemblance to GET YOUR OWN' in job('creative_qa', '')


def test_existing_quickstarts_and_editor_reuse_are_retained():
    assert 'ASSETS QUICKSTART' in job('assets', '')
    assert 'AUDIO QUICKSTART' in job('audio', '')
    assert 'performance.apply' in job('animate', '')
    assert 'Plan the whole ad second by second' in job('direct', DIRECTOR)
    assert 'reuse the accepted render' in job('edit', 'then render the original scene at\n full delivery quality.')
    assert 'restart frame' in job('creative_qa', 'a wording fix there means restart direct.')
    assert 'Fast mode: reuse a finished set' in scope({'generation': {'fast': True}})
