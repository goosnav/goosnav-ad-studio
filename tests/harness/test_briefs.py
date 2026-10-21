"""Director commands execute from an unrelated cwd; measurements use real WAVs."""
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
import wave

import pytest

from harness.briefs import brief
from harness.config import load_config
from harness.creative import main, reuse_takes, summarize_takes
from harness.voice import run_batch


class ToneSession:
    """Only the optional speech-model boundary is replaced, not file validation."""
    def identity(self, request):
        return {'provider': request['provider'], 'model': 'test-tone',
                'resolved_revision': 'a' * 40, 'files': {'weights': 'b' * 64}}

    def synthesize(self, request, output):
        frames = round(12000 / request['speed'])
        with wave.open(str(output), 'wb') as stream:
            stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            stream.writeframes(b''.join(struct.pack('<h', int(5000 * math.sin(i / 25)))
                                       for i in range(frames)))
        return {'wall_seconds': 0.01}


@pytest.fixture
def measured(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    work = tmp_path / "director's workspace"
    work.mkdir()
    (work / 'TASK.md').write_text('Stage workspace')
    request = {'provider': 'kokoro', 'effort': 'medium', 'cache_dir': str(tmp_path / 'cache'),
               'lines': [{'id': 'hello', 'speaker': 'A', 'voice': 'am_michael',
                          'text': 'Hello.', 'delivery': 'Plain',
                          'auditions': [{'speed': 1}, {'speed': .5}]}]}
    data = run_batch(request, work / 'scratch', session=ToneSession())
    # Explicitly choose the longer measured audition; stale convenience fields must not win.
    data['lines'][0]['selected_take_id'] = data['lines'][0]['takes'][1]['id']
    manifest = work / 'scratch/manifest.json'
    manifest.write_text(json.dumps(data))
    return work, manifest, data


def project(config, workspace=None, modern=True, stage='direct'):
    prompt = brief({'stage': stage, 'ad': 0}, config, {}, [], modern=modern,
                   workspace=workspace)
    return json.loads(prompt.split('\nPROJECT\n', 1)[1].split('\nREPAIR\n', 1)[0])


def test_director_commands_run_configured_python_from_workspace(measured, tmp_path):
    work, manifest, data = measured
    cfg = load_config()
    interpreter = tmp_path / "audio interpreter's python"
    interpreter.symlink_to(sys.executable)
    cfg['audio']['python'] = str(interpreter)
    p = project(cfg, work)
    completed = subprocess.run(['bash', '-c', p['director_tools']['takes']], cwd=tmp_path,
                               capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    summary = json.loads((work / 'scratch-measurements.json').read_text())
    assert summary['scratch_takes'] == 'scratch/manifest.json'
    assert summary['lines'][0]['duration'] == .5
    assert p['config']['tools'] == cfg['tools']
    assert not (tmp_path / 'scratch-measurements.json').exists()


def test_unspecified_workspace_requires_explicit_binding(tmp_path):
    cfg = load_config()
    cfg['audio']['python'] = sys.executable
    command = project(cfg)['director_tools']['takes']
    env = {k: v for k, v in os.environ.items() if k != 'STAGE_WORKSPACE'}
    run = subprocess.run(['bash', '-c', command], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=10)
    assert run.returncode != 0
    assert not list(tmp_path.iterdir())


def test_audio_command_uses_supplied_manifest_and_workspace(tmp_path):
    work = tmp_path / "audio's workspace"
    work.mkdir()
    (work / 'TASK.md').write_text('Audio stage')
    accepted = tmp_path / 'accepted-direct.json'
    accepted.write_text(json.dumps({'summary': 'Deliberate silence', 'files': [],
                                   'direction': {'duration': 1, 'lines': [], 'cast': []}}))
    cfg = load_config(); cfg['audio']['python'] = sys.executable
    command = project(cfg, work, stage='audio')['audio_tools']['assemble']
    run = subprocess.run(['bash', '-c', command], cwd=tmp_path,
                         env={**os.environ, 'DIRECT_RESULT': str(accepted)},
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    result = json.loads((work / 'result.json').read_text())
    assert result['mix'].startswith('generated-audio/')
    assert (work / result['mix']).is_file()
    assert not (tmp_path / 'generated-audio').exists()
    assert (work / 'TASK.md').read_text() == 'Audio stage'


def test_writer_has_explicit_workspace_python_and_approved_cast(tmp_path):
    cfg = load_config()
    cfg['sources']['characters'] = [str(tmp_path / 'renamed-actor.blend')]
    p = project(cfg, tmp_path, stage='write')
    assert p['workspace'] == str(tmp_path.resolve())
    assert p['controller_python'] == sys.executable
    assert p['cast_models'] == cfg['sources']['characters']
    assert 'sources' not in p['config']


def test_voice_command_reuses_portable_predecessor_without_synthesis(measured, tmp_path):
    work, manifest, data = measured
    predecessor = tmp_path / 'predecessor'
    shutil.move(str(manifest.parent), predecessor)
    shutil.rmtree(tmp_path / 'cache')
    cfg = load_config()
    cfg['audio']['python'] = sys.executable
    commands = project(cfg, work)['director_tools']
    request = commands['request_template']
    request['lines'] = [{'id': 'hello', 'speaker': 'A', 'voice': 'am_michael', 'text': 'Hello.',
                         'selected_take': {'manifest': str(predecessor / 'manifest.json')}}]
    (work / 'scratch-request.json').write_text(json.dumps(request))
    run = subprocess.run(['bash', '-c', commands['voice']], cwd=tmp_path,
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    assert not run.stdout  # full manifest goes to the workspace log, not agent context
    out = json.loads((work / 'scratch/manifest.json').read_text())
    assert out['duration'] == .5
    assert out['lines'][0]['selected_take_id'] == data['lines'][0]['takes'][1]['id']
    assert (work / 'scratch-voice.log').is_file()
    assert not (work / 'scratch/.voice-cache').exists()


def test_missing_audio_python_does_not_guess_an_interpreter():
    cfg = load_config()
    cfg['audio']['python'] = ''
    tools = project(cfg)['director_tools']
    assert tools['voice'] is None
    assert tools['takes'] is None
    assert tools['blocker']


@pytest.mark.parametrize('provider', ['kokoro', 'chatterbox', 'piper'])
def test_director_request_uses_configured_voice_provider(provider):
    cfg = load_config()
    cfg['audio']['voice_provider'] = provider
    request = project(cfg)['director_tools']['request_template']
    assert request['provider'] == provider


def test_legacy_and_audio_briefs_do_not_gain_director_helpers(tmp_path):
    cfg = load_config()
    assert 'director_tools' not in project(cfg, tmp_path, modern=False)
    assert 'director_tools' not in project(cfg, tmp_path, stage='audio')


def test_summary_uses_selected_duration_and_declares_all_auditions(measured):
    work, manifest, data = measured
    result = summarize_takes(manifest, work)
    assert result['scratch_takes'] == 'scratch/manifest.json'
    assert result['total_wav_seconds'] == .5
    assert result['lines'][0]['duration'] == .5
    assert result['lines'][0]['acceptance'] == 'provisional_requires_listening'
    assert len(result['files']) == 5  # manifest and both raw/polished auditions
    assert all((work / f['path']).is_file() for f in result['files'])
    assert all(not Path(f['path']).is_absolute() for f in result['files'])


@pytest.mark.parametrize('damage', ['raw', 'polished', 'text', 'duration', 'selection'])
def test_summary_fails_closed_on_corrupt_manifest_or_wav(measured, damage):
    work, manifest, data = measured
    line = data['lines'][0]
    take = line['takes'][0]  # unselected dependencies must also be checked
    if damage in ('raw', 'polished'):
        (manifest.parent / take[damage]['path']).write_bytes(b'broken')
    elif damage == 'text':
        line['text'] = 'Different words.'
    elif damage == 'duration':
        take['polished']['duration'] = .01
    else:
        line['selected_take_id'] = 'missing'
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        summarize_takes(manifest, work)


def test_predecessor_reuse_without_models_cache_or_modified_source(measured, tmp_path, monkeypatch):
    work, manifest, data = measured
    shutil.rmtree(tmp_path / 'cache')
    original = manifest.read_bytes()
    from harness.audio import AudioSession
    def forbidden(*args, **kwargs):
        raise AssertionError('Reuse must not load or synthesize speech')
    monkeypatch.setattr(AudioSession, 'identity', forbidden)
    monkeypatch.setattr(AudioSession, 'synthesize', forbidden)
    successor = tmp_path / 'successor'
    successor.mkdir()
    result = reuse_takes(manifest, successor / 'scratch', successor)
    assert result['scratch_takes'] == 'scratch/manifest.json'
    assert result['lines'][0]['duration'] == .5
    assert result['lines'][0]['acceptance'] == 'provisional_requires_listening'
    assert len(result['files']) == 3  # only the selected pair copied
    copied = json.loads((successor / result['scratch_takes']).read_text())
    assert copied['lines'][0]['takes'][0]['polished']['sha256'] == data['lines'][0]['takes'][1]['polished']['sha256']
    assert manifest.read_bytes() == original
    assert all((successor / f['path']).is_file() for f in result['files'])


def test_helper_rejects_output_escape_and_overwrite(measured):
    work, manifest, data = measured
    with pytest.raises(ValueError):
        main(['takes', str(manifest), '--workspace', str(work), '--output', '../escape.json'])
    existing = work / 'summary.json'
    existing.write_text('previous checkpoint')
    with pytest.raises(FileExistsError):
        main(['takes', str(manifest), '--workspace', str(work), '--output', 'summary.json'])
    assert existing.read_text() == 'previous checkpoint'


@pytest.mark.parametrize('autoexec', [False, True])
def test_motion_command_opens_real_model_in_blender(tmp_path, autoexec):
    blender = shutil.which('blender')
    if not blender:
        pytest.skip('Blender unavailable')
    work = tmp_path / 'stage'
    work.mkdir()
    (work / 'TASK.md').write_text('Stage workspace')
    model = tmp_path / "actor's rig.blend"
    marker = tmp_path / 'embedded-script-ran'
    embedded = f'from pathlib import Path; Path({str(marker)!r}).write_text("executed")'
    create = ('import bpy; bpy.ops.object.armature_add(); '
              'rig=bpy.context.object; rig.name="ActualRig"; rig.animation_data_create(); '
              'rig.animation_data.action=bpy.data.actions.new("idle"); '
              'rig.pose.bones[0].keyframe_insert(data_path="location",frame=1); '
              'text=bpy.data.texts.new("embedded.py"); text.use_module=True; '
              f'text.write({embedded!r}); '
              f'bpy.ops.wm.save_as_mainfile(filepath={str(model)!r})')
    made = subprocess.run([blender, '-b', '--factory-startup', '--python-exit-code', '1',
                           '--python-expr', create], capture_output=True, text=True, timeout=30)
    assert made.returncode == 0, made.stdout + made.stderr
    original = model.read_bytes()
    cfg = load_config()
    cfg['tools']['blender'] = blender
    command = project(cfg, work)['director_tools']['motion']
    if autoexec:
        # The helper must also protect callers that did not use the safe CLI flags.
        command = command.replace('--disable-autoexec', '--enable-autoexec')
    run = subprocess.run(['bash', '-c', f'CHARACTER_MODEL={shlex.quote(str(model))}; ' + command],
                         cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    inventory = json.loads((work / 'motion.json').read_text())
    rigs = inventory['models'][0]['armatures']
    assert rigs[0]['name'] == 'ActualRig'
    assert 'idle' in rigs[0]['clips']
    assert not marker.exists(), 'Embedded Python executed while inventorying a model'
    assert model.read_bytes() == original, 'Inventory must not save its in-memory clip tags'
