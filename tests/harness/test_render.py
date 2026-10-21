from pathlib import Path
import json
import runpy
import struct
import subprocess
import sys
from types import SimpleNamespace
import zlib
import pytest

from harness import render as renderer
from harness.contracts import digest


def test_cli_uses_measured_receipt_without_guessing_mix_folder(tmp_path, monkeypatch, capsys):
    folder = tmp_path / 'audio'; folder.mkdir()
    mix = folder / 'mix-0002.wav'; mix.write_bytes(b'verified mixed audio')
    receipt = folder / 'production.json'
    receipt.write_text(json.dumps({'mix': mix.name, 'direction': {'duration': 9},
        'files': [{'path': mix.name, 'sha256': digest(mix)}]}))
    calls = []
    monkeypatch.setattr(renderer, 'render', lambda **kwargs: calls.append(kwargs) or {})
    renderer.main(['--scene', 'scene.blend', '--production', str(receipt), '--output', 'preview.mp4'])
    assert calls[0]['audio'] == str(mix)
    assert calls[0]['seconds'] == 9
    mix.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Changed'):
        renderer.main(['--scene', 'scene.blend', '--production', str(receipt), '--output', 'preview.mp4'])
    assert len(calls) == 1


def test_production_render_checks_saved_speakers_before_expensive_frames(tmp_path, monkeypatch):
    from harness import media
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    direction = {'duration': 9, 'cast': [{'speaker': 'A', 'model': 'active.blend'}],
                 'lines': [{'speaker': 'A', 'text': 'Hi', 'start': .2, 'end': 1.2}]}
    receipt = tmp_path / 'production.json'
    receipt.write_text(json.dumps({'mix': audio.name, 'direction': direction,
        'files': [{'path': audio.name, 'sha256': digest(audio)}]}))
    rigs = tmp_path / 'rigs.json'; rigs.write_text('{"A":"actor.rig"}')
    calls = []
    def check(scene, names, lines, fps, models, **kwargs):
        calls.append('check')
        assert names == {'A': 'actor.rig'} and models == {'A': 'active.blend'}
        assert lines[0]['end'] == 1.2
        raise ValueError('Speaker face is obscured')
    monkeypatch.setattr(media, 'check_scene', check)
    monkeypatch.setattr(renderer, 'render', lambda **kwargs: calls.append('render'))
    with pytest.raises(ValueError, match='face is obscured'):
        renderer.main(['--scene', 'scene.blend', '--production', str(receipt),
                       '--rigs', str(rigs), '--output', 'preview.mp4'])
    assert calls == ['check']


def png(width, height):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0' * ((width * 3 + 1) * height))) + chunk(b'IEND', b''))


def install_blender_double(monkeypatch, draw):
    # Run the actual helper; only Blender's slow rendering API is replaced.
    scene = SimpleNamespace(render=SimpleNamespace(image_settings=SimpleNamespace()), eevee=SimpleNamespace())
    scene.frame_set = lambda frame: setattr(scene, 'frame', frame)
    bpy = SimpleNamespace(context=SimpleNamespace(scene=scene), data=SimpleNamespace(images=[], libraries=[]),
                          ops=SimpleNamespace(render=SimpleNamespace(render=lambda **kw: draw(scene))))
    monkeypatch.setitem(sys.modules, 'bpy', bpy)
    calls = []

    def run(argv, **kwargs):
        if '--python-expr' in argv:
            calls.append('validate')
            return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')
        if '--python' in argv:
            request = json.loads(Path(argv[-1]).read_text())
            calls.append((request['start'], request['end']))
            with monkeypatch.context() as patch:
                patch.setattr(sys, 'argv', argv)
                runpy.run_path(argv[argv.index('--python') + 1], run_name='__main__')
        else:
            calls.append('encode')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    return calls


def test_interrupted_range_checkpoints_each_frame_and_resumes_only_missing(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    output = tmp_path / 'output.mp4'
    interrupt = [True]

    def draw(scene):
        path = Path(scene.render.filepath)
        if scene.frame == 3 and interrupt[0]:
            path.write_bytes(b'partial frame')
            raise subprocess.TimeoutExpired('blender', 1)
        path.write_bytes(png(scene.render.resolution_x, scene.render.resolution_y))

    calls = install_blender_double(monkeypatch, draw)
    with pytest.raises(subprocess.TimeoutExpired):
        renderer.render(scene, audio, output, seconds=1)
    cache = next((tmp_path / '.render-cache').iterdir())
    hashes = json.loads((cache / 'frames.json').read_text())
    assert hashes == {f'{n:06}.png': digest(cache / f'{n:06}.png') for n in (1, 2)}
    first_mtime = (cache / '000001.png').stat().st_mtime_ns
    interrupt[0] = False
    result = renderer.render(scene, audio, output, seconds=1)
    assert calls == ['validate', (1, 24), 'validate', (3, 24), 'encode']
    assert (cache / '000001.png').stat().st_mtime_ns == first_mtime
    assert result['settings']['height'] == 676
    assert len(json.loads((cache / 'frames.json').read_text())) == 24
    renderer.render(scene, audio, output, seconds=1)
    assert calls[-2:] == ['validate', 'encode']


@pytest.mark.parametrize('corruption', ['missing-journal', 'changed-frame', 'wrong-hash'])
def test_parent_rechecks_helper_journal_before_encode(tmp_path, monkeypatch, corruption):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')

    def run(argv, **kwargs):
        if '--python-expr' in argv:
            return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')
        assert '--python' in argv, 'Unverified frames must not reach encoding'
        request = json.loads(Path(argv[-1]).read_text())
        folder = Path(request['folder'])
        frame = folder / '000001.png'; frame.write_bytes(png(540, 676))
        if corruption != 'missing-journal':
            hashes = {frame.name: digest(frame) if corruption == 'changed-frame' else 'wrong'}
            (folder / 'frames.json').write_text(json.dumps(hashes))
        if corruption == 'changed-frame':
            frame.write_bytes(b'mutated after journal')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    with pytest.raises(ValueError, match='[Uu]nverified'):
        renderer.render(scene, audio, tmp_path / 'output.mp4', fps=1, seconds=1)


def test_helper_does_not_checkpoint_truncated_png(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    install_blender_double(monkeypatch, lambda scene: Path(scene.render.filepath).write_bytes(b'broken' * 100))
    with pytest.raises(ValueError, match='[Ii]nvalid.*frame'):
        renderer.render(scene, audio, tmp_path / 'output.mp4', fps=1, seconds=1)
    assert not list((tmp_path / '.render-cache').glob('*/frames.json'))


def test_checkpoint_replace_failure_preserves_previous_journal(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    install_blender_double(monkeypatch, lambda scene: Path(scene.render.filepath).write_bytes(
        png(scene.render.resolution_x, scene.render.resolution_y)))
    replace = Path.replace
    def interrupted_replace(path, target):
        if Path(target).name == 'frames.json' and Path(target).exists():
            raise OSError('interrupted atomic checkpoint')
        return replace(path, target)
    monkeypatch.setattr(Path, 'replace', interrupted_replace)
    with pytest.raises(OSError, match='interrupted atomic checkpoint'):
        renderer.render(scene, audio, tmp_path / 'output.mp4', fps=2, seconds=1)
    cache = next((tmp_path / '.render-cache').iterdir())
    assert json.loads((cache / 'frames.json').read_text()) == {'000001.png': digest(cache / '000001.png')}


def test_disjoint_missing_ranges_preserve_other_checkpoints(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    output = tmp_path / 'output.mp4'
    calls = install_blender_double(monkeypatch, lambda scene: Path(scene.render.filepath).write_bytes(
        png(scene.render.resolution_x, scene.render.resolution_y)))
    renderer.render(scene, audio, output, fps=5, seconds=1)
    cache = next((tmp_path / '.render-cache').iterdir())
    for frame in (2, 4):
        (cache / f'{frame:06}.png').write_bytes(b'partial')
    calls.clear()
    renderer.render(scene, audio, output, fps=5, seconds=1)
    assert calls == ['validate', (2, 2), (4, 4), 'encode']
    hashes = json.loads((cache / 'frames.json').read_text())
    assert renderer.missing_ranges(cache, 1, 5, hashes) == []
    assert len(hashes) == 5


def test_render_resume_rejects_changed_source_and_uses_exact_missing_frames(tmp_path):
    from harness.render import render_key, missing_ranges
    scene = tmp_path / 'scene.blend'
    scene.write_bytes(b'first scene')
    first = render_key(scene, {'width': 540, 'height': 676, 'fps': 24})
    scene.write_bytes(b'changed scene')
    assert render_key(scene, {'width': 540, 'height': 676, 'fps': 24}) != first
    # Only verified frame hashes count as complete; a truncated write is rendered again.
    from harness.contracts import digest
    frames = tmp_path / 'frames'; frames.mkdir()
    p = frames / '000001.png'; p.write_bytes(b'valid accepted frame')
    q = frames / '000002.png'; q.write_bytes(b'partial')
    assert missing_ranges(frames, 1, 4, {'000001.png': digest(p), '000002.png': 'wrong'}) == [(2, 4)]
