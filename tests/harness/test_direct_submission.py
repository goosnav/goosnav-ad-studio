"""Real measured WAVs and subprocess submission; only synthesis is a fixture."""
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave

import pytest

from harness.voice import run_batch

REPO = Path(__file__).resolve().parents[2]


class Tone:
    def identity(self, settings):
        return {'provider': 'kokoro', 'model': 'fixture', 'resolved_revision': 'a' * 40,
                'files': {'weights': 'b' * 64}}

    def synthesize(self, settings, output):
        with wave.open(str(output), 'wb') as wav:
            wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b''.join(struct.pack('<h', int(4000 * math.sin(i / 20)))
                                    for i in range(round(24000 / settings['speed']))))
        return {'wall_seconds': 0}


@pytest.fixture
def work(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('requires ffmpeg')
    root = tmp_path / "director's workspace"
    root.mkdir()
    run_batch({'provider': 'kokoro', 'polish': False, 'effort': 'medium',
               'lines': [{'id': 'hello', 'speaker': 'A', 'text': 'Hello.', 'voice': 'am_michael',
                          'auditions': [{'speed': 1}, {'speed': .8}]}]},
              root / 'scratch', session=Tone())
    plan = {'summary': 'Authored plan, not an automated approval.',
            'direction': {'duration': 3, 'cast': [{'speaker': 'A', 'voice': 'am_michael'}],
                          'lines': [{'id': 'hello', 'speaker': 'A', 'text': 'Hello.',
                                     'start': .25, 'end': 1, 'delivery': 'Plain'}],
                          'beats': [{'start': 0, 'end': 2, 'shot': 'Two-shot',
                                     'picture': 'A faces camera.', 'sound': 'Dialogue', 'faces': ['A']}],
                          'end_card': {'seconds': 1, 'title': 'Look', 'picture': 'Product'},
                          'mix': 'No bed.'}}
    (root / 'plan.json').write_text(json.dumps(plan))
    (root / 'direction.md').write_text('Authored staging rationale; acting not assessed.')
    return root


def cli(work, *extra):
    return subprocess.run([sys.executable, '-m', 'harness.creative', 'submit-direction',
                           'plan.json', 'scratch/manifest.json', '--output', 'result.json', *extra],
                          cwd=work, env=dict(os.environ, PYTHONPATH=str(REPO),
                                             PYTHONDONTWRITEBYTECODE='1'),
                          capture_output=True, text=True, timeout=15)


def test_cli_declares_verified_dependencies_and_preserves_authored_plan(work):
    plan_bytes = (work / 'plan.json').read_bytes()
    manifest_bytes = (work / 'scratch/manifest.json').read_bytes()
    shutil.rmtree(work / 'scratch/.voice-cache')
    done = cli(work, '--direction-md', 'direction.md')
    assert done.returncode == 0, done.stderr
    result = json.loads((work / 'result.json').read_text())
    original = json.loads(plan_bytes)
    assert result['summary'] == original['summary']
    assert result['direction'] == original['direction']
    assert result['scratch_takes'] == 'scratch/manifest.json'
    paths = [f['path'] for f in result['files']]
    assert len(paths) == len(set(paths)) == 7  # plan + notes + manifest + both audition pairs
    assert all((work / p).is_file() and not Path(p).is_absolute() for p in paths)
    assert 'result.json' not in paths
    from harness.direction import check_scratch_takes
    assert len(check_scratch_takes(result, work)) == 1
    assert (work / 'plan.json').read_bytes() == plan_bytes
    assert (work / 'scratch/manifest.json').read_bytes() == manifest_bytes
    assert len(done.stdout) < 700 and 'recipe' not in done.stdout


def test_invalid_timing_is_not_repaired_or_approved(work):
    plan = json.loads((work / 'plan.json').read_text())
    plan['direction']['lines'][0]['end'] = .26
    (work / 'plan.json').write_text(json.dumps(plan))
    done = cli(work)
    assert done.returncode == 0, done.stderr
    result = json.loads((work / 'result.json').read_text())
    assert result['direction'] == plan['direction']
    from harness.direction import check_scratch_takes
    from harness.contracts import ContractError
    with pytest.raises(ContractError, match='does not fit'):
        check_scratch_takes(result, work)


@pytest.mark.parametrize('damage', ['raw', 'polished', 'measurement', 'text', 'voice', 'selection'])
def test_rejects_corrupt_or_mismatched_takes_without_writing_result(work, damage):
    path = work / 'scratch/manifest.json'
    manifest = json.loads(path.read_text())
    line = manifest['lines'][0]
    take = line['takes'][0]
    if damage in ('raw', 'polished'):
        (path.parent / take[damage]['path']).write_bytes(b'corrupt')
    elif damage == 'measurement':
        take['polished']['duration'] = .01
    elif damage == 'selection':
        line['selected_take_id'] = 'missing'
    else:
        plan = json.loads((work / 'plan.json').read_text())
        if damage == 'text':
            plan['direction']['lines'][0]['text'] = 'Different.'
        else:
            plan['direction']['cast'][0]['voice'] = 'af_heart'
        (work / 'plan.json').write_text(json.dumps(plan))
    path.write_text(json.dumps(manifest))
    done = cli(work)
    assert done.returncode != 0
    assert not (work / 'result.json').exists()


@pytest.mark.parametrize('target', ['plan', 'manifest', 'notes', 'wave', 'extra', 'output'])
def test_rejects_symlinks_and_outside_paths(work, target):
    outside = work.parent / 'outside'
    outside.write_text('must remain unchanged')
    args = []
    if target == 'output':
        (work / 'result.json').symlink_to(outside)
    elif target == 'extra':
        plan = json.loads((work / 'plan.json').read_text())
        plan['files'] = [{'path': '../outside', 'kind': 'notes'}]
        (work / 'plan.json').write_text(json.dumps(plan))
    else:
        paths = {'plan': work / 'plan.json', 'manifest': work / 'scratch/manifest.json',
                 'notes': work / 'direction.md'}
        if target == 'wave':
            manifest = json.loads(paths['manifest'].read_text())
            selected = manifest['lines'][0]['takes'][0]
            path = work / 'scratch' / selected['raw']['path']
        else:
            path = paths[target]
        actual = work / 'local-original'
        path.rename(actual)
        path.symlink_to(actual)  # reject even an internal alias, matching artifact contracts
        if target == 'notes':
            args = ['--direction-md', 'direction.md']
    done = cli(work, *args)
    assert done.returncode != 0
    assert outside.read_text() == 'must remain unchanged'
    if target != 'output':
        assert not (work / 'result.json').exists()


def test_existing_result_is_never_overwritten_and_extra_files_are_declared(work):
    (work / 'motion.json').write_text('{"models":[]}')
    plan = json.loads((work / 'plan.json').read_text())
    plan['files'] = [{'path': 'motion.json', 'kind': 'motion_inventory'}]
    (work / 'plan.json').write_text(json.dumps(plan))
    done = cli(work)
    assert done.returncode == 0, done.stderr
    original = (work / 'result.json').read_bytes()
    assert {'path': 'motion.json', 'kind': 'motion_inventory'} in json.loads(original)['files']
    again = cli(work)
    assert again.returncode != 0
    assert (work / 'result.json').read_bytes() == original
