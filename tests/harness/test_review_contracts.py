import pytest

from harness.contracts import ContractError, validate


@pytest.mark.parametrize('stage', ['board_review', 'creative_qa'])
@pytest.mark.parametrize('severity', ['important', 'major', 'moderate'])
def test_modern_review_cannot_pass_important_defect(tmp_path, stage, severity):
    data = {'summary': 'Speaker hidden', 'files': [], 'verdict': 'pass',
            'findings': [{'target': 'speaker A', 'severity': severity,
                          'problem': 'Speaking face is hidden', 'fix': 'Reframe the shot'}]}
    with pytest.raises(ContractError, match='important'):
        validate(stage, data, tmp_path, {'strict_review': True})


@pytest.mark.parametrize('stage', ['board_review', 'creative_qa'])
def test_modern_minor_note_and_legacy_important_note_keep_contract(tmp_path, stage):
    data = {'summary': 'A note', 'files': [], 'verdict': 'pass',
            'findings': [{'target': 'lighting', 'severity': 'minor',
                          'problem': 'Slightly flat', 'fix': 'Optional fill'}]}
    assert validate(stage, data, tmp_path, {'strict_review': True})['verdict'] == 'pass'
    data['findings'][0]['severity'] = 'important'
    assert validate(stage, data, tmp_path, {})['verdict'] == 'pass'


def test_review_error_explains_how_to_cite_accepted_inputs(tmp_path):
    data = {'summary': 'Reviewed existing board', 'files': [{'path': '../accepted/board.png', 'kind': 'image'}],
            'verdict': 'pass', 'findings': []}
    with pytest.raises(ContractError, match=r'files: \[\]'):
        validate('board_review', data, tmp_path, {})
