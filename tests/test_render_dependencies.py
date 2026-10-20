"""Render dependency safety, including complete cache hits and real Blender files."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from harness import render as renderer
from harness.contracts import digest


def cached_render(tmp_path, scene):
    audio = tmp_path / 'mix.wav'
    audio.write_bytes(b'audio is not decoded by these dependency tests')
    output = tmp_path / 'output.mp4'
    settings = {'width': 540, 'height': 676, 'fps': 1, 'samples': 8}
    cache = tmp_path / '.render-cache' / renderer.render_key(scene, settings)
    cache.mkdir(parents=True, exist_ok=True)
    frame = cache / '000001.png'
    frame.write_bytes(b'previously hashed frame' * 10)
    (cache / 'frames.json').write_text(json.dumps({frame.name: digest(frame)}))
    return audio, output, cache


def test_complete_cache_is_validated_before_reading_or_encoding(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'
    scene.write_bytes(b'fixture scene')
    audio, output, cache = cached_render(tmp_path, scene)
    # Invalid JSON proves the journal is not even read before dependency validation.
    (cache / 'frames.json').write_text('do not read an unvalidated cache')
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert '--disable-autoexec' in argv and '--python-expr' in argv
        assert argv[-1] == str(scene)
        raise subprocess.CalledProcessError(1, argv, output='external font: actor.ttf')

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    with pytest.raises(ValueError, match='external font'):
        renderer.render(scene, audio, output, fps=1, seconds=1)
    assert len(calls) == 1
    assert not output.exists()
    assert (cache / 'frames.json').read_text() == 'do not read an unvalidated cache'


def test_dependency_validation_failure_creates_no_cache(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    output = tmp_path / 'new-output' / 'preview.mp4'
    monkeypatch.setattr(renderer.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 0, ''))
    with pytest.raises(ValueError, match='did not confirm'):
        renderer.render(scene, audio, output)
    assert not output.parent.exists()


def test_validation_consumes_the_render_allowance(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio, output, cache = cached_render(tmp_path, scene)
    clock = [0]
    calls = []
    monkeypatch.setattr(renderer.time, 'monotonic', lambda: clock[0])

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs['timeout'] == 5
        clock[0] = 6
        return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    with pytest.raises(TimeoutError, match='allowance exhausted'):
        renderer.render(scene, audio, output, fps=1, seconds=1, timeout=5)
    assert len(calls) == 1
    assert not output.exists()


def test_scene_change_during_validation_cannot_authorize_cache(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'safe scene')
    audio, output, cache = cached_render(tmp_path, scene)

    def run(argv, **kwargs):
        scene.write_bytes(b'changed dependencies')
        return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    with pytest.raises(ValueError, match='Scene changed'):
        renderer.render(scene, audio, output, fps=1, seconds=1)
    assert not output.exists()


def test_uncached_render_keeps_autoexec_disabled_after_validation(tmp_path, monkeypatch):
    scene = tmp_path / 'scene.blend'; scene.write_bytes(b'scene')
    audio = tmp_path / 'mix.wav'; audio.write_bytes(b'audio')
    calls = []

    def run(argv, **kwargs):
        if '--python-expr' in argv:
            calls.append('validate')
            return subprocess.CompletedProcess(argv, 0, 'AD_RENDER_DEPENDENCIES_OK\n')
        if '--python' in argv:
            calls.append('render')
            assert '--factory-startup' in argv and '--disable-autoexec' in argv
            assert argv.index('--disable-autoexec') < argv.index(str(scene))
            request = json.loads(Path(argv[-1]).read_text())
            hashes = {}
            for frame in range(request['start'], request['end'] + 1):
                path = Path(request['folder']) / f'{frame:06}.png'
                path.write_bytes(b'frame' * 30)
                hashes[path.name] = digest(path)
            (Path(request['folder']) / 'frames.json').write_text(json.dumps(hashes))
        else:
            assert argv[0] == 'ffmpeg'
            calls.append('encode')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(renderer.subprocess, 'run', run)
    renderer.render(scene, audio, tmp_path / 'output.mp4', fps=1, seconds=1)
    assert calls == ['validate', 'render', 'encode']


@pytest.fixture(scope='module')
def blender_scenes(tmp_path_factory):
    blender = shutil.which('blender')
    if not blender:
        pytest.skip('requires real Blender')
    root = tmp_path_factory.mktemp('render-dependencies')
    fonts = sorted(Path('/usr/share/fonts').rglob('*.ttf'))
    script = f'ROOT = {str(root)!r}\nFONT_PATH = {str(fonts[0]) if fonts else None!r}\n' + '''
import bpy
from pathlib import Path
root = Path(ROOT)
def save(name):
    bpy.ops.wm.save_as_mainfile(filepath=str(root / (name + '.blend')))
bpy.ops.wm.read_factory_settings(use_empty=False)
image = bpy.data.images.new('dependency', width=4, height=4)
image.generated_color = (.1, .4, .8, 1)
image.filepath_raw = str(root / 'texture.png')
image.file_format = 'PNG'
image.save()
image.source = 'FILE'
image.use_fake_user = True
save('external-image')
image.pack()
image.filepath = '//removed-source.png'
save('packed')
bpy.ops.wm.read_factory_settings(use_empty=False)
bpy.context.scene.sequence_editor_create().sequences.new_image(
    'external-strip', str(root / 'texture.png'), channel=1, frame_start=1)
save('sequencer')
bpy.ops.wm.read_factory_settings(use_empty=False)
volume = bpy.data.volumes.new('external-volume')
volume.filepath = str(root / 'missing.vdb')
bpy.context.scene.collection.objects.link(bpy.data.objects.new('volume', volume))
save('volume')
bpy.ops.wm.read_factory_settings(use_empty=False)
cache = bpy.data.objects['Cube'].modifiers.new('cloth', 'CLOTH').point_cache
save('disk-cache')
cache.use_disk_cache = True
bpy.ops.wm.save_mainfile()
bpy.ops.wm.read_factory_settings(use_empty=False)
with bpy.data.libraries.load(str(root / 'packed.blend'), link=True) as (source, target):
    target.objects = ['Cube']
for obj in target.objects:
    bpy.context.scene.collection.objects.link(obj)
save('linked')
if FONT_PATH:
    bpy.ops.wm.read_factory_settings(use_empty=False)
    text = bpy.data.curves.new('text', 'FONT')
    text.body = 'External font'
    text.font = bpy.data.fonts.load(FONT_PATH)
    bpy.context.scene.collection.objects.link(bpy.data.objects.new('text', text))
    save('font')
'''
    result = subprocess.run([blender, '--background', '--factory-startup', '--disable-autoexec',
                             '--python-exit-code', '1', '--python-expr', script],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return blender, root


@pytest.mark.parametrize('name', ['external-image', 'font', 'sequencer', 'volume', 'disk-cache', 'linked'])
def test_real_dependencies_rejected_even_with_complete_cached_frames(blender_scenes, tmp_path, monkeypatch, name):
    blender, root = blender_scenes
    scene = root / (name + '.blend')
    if not scene.exists():
        pytest.skip('system font unavailable')
    audio, output, cache = cached_render(tmp_path, scene)
    run = subprocess.run
    calls = []

    def checked_run(argv, **kwargs):
        calls.append(argv)
        assert '--python-expr' in argv, 'Rejected dependencies must never render or encode'
        return run(argv, **kwargs)

    monkeypatch.setattr(renderer.subprocess, 'run', checked_run)
    with pytest.raises(ValueError, match='external/unsupported dependencies'):
        renderer.render(scene, audio, output, blender=blender, fps=1, seconds=1, timeout=30)
    assert len(calls) == 1
    assert not output.exists()


def test_real_packed_scene_revalidates_on_every_cache_hit(blender_scenes, tmp_path, monkeypatch):
    blender, root = blender_scenes
    scene = root / 'packed.blend'
    audio, output, cache = cached_render(tmp_path, scene)
    run = subprocess.run
    calls = []

    def checked_run(argv, **kwargs):
        if '--python-expr' in argv:
            calls.append('validate')
            return run(argv, **kwargs)
        assert argv[0] == 'ffmpeg', 'Complete verified cache should not render again'
        calls.append('encode')
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(renderer.subprocess, 'run', checked_run)
    for _ in range(2):
        renderer.render(scene, audio, output, blender=blender, fps=1, seconds=1, timeout=30)
    assert calls == ['validate', 'encode', 'validate', 'encode']
