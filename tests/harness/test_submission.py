"""Submission is mechanical declaration, never a fabricated creative approval."""
import json
from pathlib import Path

import pytest

from harness.contracts import ContractError, validate


@pytest.fixture
def authored(tmp_path):
    for name in ('scene.blend', 'build.py', 'manifest.json', 'beat.png', 'hero.png', 'notes.md'):
        (tmp_path / name).write_text('fixture artifact')
    plan = {'summary': 'Authored scene', 'assets': [
        {'name': 'Set', 'source': 'configured catalog', 'rights': 'owned', 'proxy': False}],
        'scene': 'scene.blend', 'source': 'build.py', 'manifest': 'manifest.json',
        'boards': [{'beat': 0, 'image': 'beat.png'}, {'beat': 'end_card', 'image': 'hero.png'}],
        'used_asset_ids': ['stable-set'], 'files': [{'path': 'notes.md', 'kind': 'notes'}]}
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    return plan


def test_submit_assets_preserves_authored_fields_and_declares_explicit_files(tmp_path, authored):
    from harness.submission import submit_assets
    result = submit_assets('plan.json', 'result.json', tmp_path)
    for key in ('summary', 'assets', 'scene', 'source', 'manifest', 'boards', 'used_asset_ids'):
        assert result[key] == authored[key]
    assert {f['path'] for f in result['files']} == {
        'plan.json', 'scene.blend', 'build.py', 'manifest.json', 'beat.png', 'hero.png', 'notes.md'}
    assert result == json.loads((tmp_path / 'result.json').read_text())
    assert json.loads((tmp_path / 'plan.json').read_text()) == authored
    validate('assets', result, tmp_path, {})


@pytest.mark.parametrize('field,value', [
    ('scene', '../scene.blend'), ('source', '/tmp/not-local.py'),
    ('manifest', 'absent.json'), ('boards', [{'beat': 0, 'image': '../outside.png'}]),
    ('boards', [{'beat': 0, 'image': 'beat.png'}, {'beat': 0, 'image': 'hero.png'}]),
    ('boards', [{'beat': True, 'image': 'beat.png'}]), ('boards', []),
    ('assets', [{'name': 'Unfinished', 'source': 'local', 'rights': 'owned', 'proxy': True}]),
    ('used_asset_ids', [123]), ('files', [{'path': 'absent.png', 'kind': 'image'}]),
])
def test_invalid_submission_writes_no_result(tmp_path, authored, field, value):
    from harness.submission import submit_assets
    authored[field] = value
    (tmp_path / 'plan.json').write_text(json.dumps(authored))
    with pytest.raises(ValueError):
        submit_assets('plan.json', 'result.json', tmp_path)
    assert not (tmp_path / 'result.json').exists()


def test_submit_never_follows_symlink_or_overwrites(tmp_path, authored):
    from harness.submission import submit_assets
    (tmp_path / 'scene.blend').unlink()
    (tmp_path / 'scene.blend').symlink_to(tmp_path / 'hero.png')
    with pytest.raises(ValueError):
        submit_assets('plan.json', 'result.json', tmp_path)
    (tmp_path / 'result.json').write_text('keep')
    with pytest.raises(FileExistsError):
        submit_assets('plan.json', 'result.json', tmp_path)
    assert (tmp_path / 'result.json').read_text() == 'keep'


@pytest.mark.parametrize('value', [{'text': 'A real premise'}, ['A real premise'], ''])
def test_research_error_explains_plain_string_not_nested_text(tmp_path, value):
    data = {'summary': 'Research', 'files': [], 'brand_brief': 'Brand',
            'creative_directions': value, 'references': []}
    with pytest.raises(ContractError, match='creative_directions.*nonempty plain-text string'):
        validate('research', data, tmp_path, {})


def test_research_prompt_exposes_complete_schema():
    from harness.briefs import JOBS
    assert 'brand_brief and creative_directions must each be a plain-text string' in JOBS['research']


def test_assets_brief_has_submission_quickstart():
    from harness.creative import job
    text = job('assets', '')
    assert '-m harness.submission' in text
    assert 'Do not read the entire worker guide' in text
    assert 'before optional polish' in text


def test_modern_assets_context_retains_plan_and_audio_paths_not_dependency_inventory(tmp_path):
    from harness.briefs import brief
    from harness.config import load_config
    inputs = {'ad-01-direct': {'summary': 'Plan', 'direction': {'beats': []},
                              'scratch_takes': '/accepted/manifest.json',
                              'files': [{'path': '/accepted/raw.wav', 'sha256': 'a'*64}]},
              'ad-01-audio': {'summary': 'Mix', 'mix': '/accepted/mix.wav',
                             'timeline': '/accepted/timeline.json', 'mouths': '/accepted/mouths.json',
                             'files': [{'path': '/accepted/source.py'}]},
              'selected_script': {'script': 'Original script'}}
    before = json.dumps(inputs)
    def payload(modern):
        text = brief({'stage': 'assets', 'ad': 0}, load_config(), inputs, [],
                     modern=modern, workspace=tmp_path)
        return json.loads(text.split('\nPROJECT\n')[1].split('\nREPAIR\n')[0])['accepted_inputs']
    compact = payload(True)
    assert 'files' not in compact['ad-01-direct']
    assert compact['ad-01-direct']['direction'] == inputs['ad-01-direct']['direction']
    assert compact['ad-01-direct']['scratch_takes'] == '/accepted/manifest.json'
    assert compact['ad-01-audio']['mouths'] == '/accepted/mouths.json'
    assert compact['selected_script'] == inputs['selected_script']
    assert payload(False) == inputs
    assert json.dumps(inputs) == before


def test_submission_cli_from_unrelated_cwd(tmp_path, authored):
    import os
    import subprocess
    import sys
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-m', 'harness.submission', 'plan.json',
                             '--workspace', str(tmp_path), '--output', 'handoff/result.json'],
                            cwd=tmp_path.parent, env={**os.environ, 'PYTHONPATH': str(repo)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert (tmp_path/'handoff/result.json').is_file()
    assert 'controller media and creative review still required' in result.stdout


def test_canonical_paths_stay_in_sync_with_references_and_promote(tmp_path, authored):
    from harness.submission import submit_assets
    from harness.contracts import promote
    for key in ('scene', 'source', 'manifest'):
        authored[key] = './' + authored[key]
    for board in authored['boards']:
        board['image'] = './' + board['image']
    authored['files'][0]['path'] = './notes.md'
    (tmp_path/'candidate.json').write_text('{}')
    authored['candidate_manifest'] = './candidate.json'
    (tmp_path/'plan.json').write_text(json.dumps(authored))
    result = submit_assets('./plan.json', './result.json', tmp_path)
    paths = {f['path'] for f in result['files']}
    for key in ('scene', 'source', 'manifest', 'candidate_manifest'):
        assert result[key] in paths
    assert all(b['image'] in paths for b in result['boards'])
    promoted = promote(result, tmp_path, tmp_path/'accepted')
    for key in ('scene', 'source', 'manifest', 'candidate_manifest'):
        assert Path(promoted[key]).is_absolute()
        assert Path(promoted[key]).is_file()
    assert all(Path(b['image']).is_file() for b in promoted['boards'])


def test_board_review_prompt_and_error_list_severity_options(tmp_path):
    from harness.creative import job
    assert 'severity:blocking|important|minor' in job('board_review', '')
    result = {'summary': 'Review', 'files': [], 'verdict': 'pass', 'findings': [
        {'target': 'acting', 'severity': 'unverified', 'problem': 'Not listened', 'fix': 'Listen'}]}
    with pytest.raises(ContractError, match='severity.*blocking.*important.*minor'):
        validate('board_review', result, tmp_path, {'strict_review': True})
