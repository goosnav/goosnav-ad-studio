"""Component checks only: no agent sessions, audio generation or video renders."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / 'assets/goosnav-3D-assets/assets/3D'
MODELS = [LIBRARY / 'characters/goosnav_guy_ps1.blend',
          LIBRARY / 'ps1guy/ps1guy.blend',
          LIBRARY / 'ps1guy/astronaut/ps1guy_astronaut_v1.blend']

CHECK = '''
import bpy, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[-2])
import performance
from lipsync import mouth_meshes
model = sys.argv[-1]
scene = bpy.context.scene
scene.render.fps = 24; scene.frame_start = 1; scene.frame_end = 96
actors = []
for _ in range(2):
    with bpy.data.libraries.load(model, link=False) as (source, target):
        target.objects = list(source.objects)
    for obj in target.objects:
        if obj: scene.collection.objects.link(obj)
    actors.append(next(o for o in target.objects if o and o.type == 'ARMATURE'))
first, second = actors
first.location = (-1, 0, 0); second.location = (1, 0, 0)
first.rotation_euler.z = .2; second.rotation_euler.z = -.2
bpy.context.view_layer.update()
# A common duplicate-actor setup shares mesh data. Mouths must still be independent.
if mouth_meshes(first):
    mouth_meshes(second)[0].data = mouth_meshes(first)[0].data
rigs = {'A': first.name, 'B': second.name}
before = {s: a.matrix_world.copy() for s, a in [('A', first), ('B', second)]}
timeline = {'fps': 24, 'sample_rate': 48000, 'duration': 4, 'dialogue': [
    {'speaker': 'A', 'start_sample': 24000, 'end_sample': 72000},
    {'speaker': 'B', 'start_sample': 96000, 'end_sample': 144000}]}
mouths = {'fps': 24, 'frames': 96, 'speakers': {
    'A': [0.7 if 12 <= f < 36 else 0 for f in range(96)],
    'B': [0.7 if 48 <= f < 72 else 0 for f in range(96)]}}
report = performance.apply(timeline, mouths, rigs, models={s: model for s in rigs})
assert report['A']['idle'] in ('idle', 'pose_idle')
assert report['B']['idle'] in ('idle', 'pose_idle')
assert report['A']['blinks'] != report['B']['blinks']
for speaker, arm in [('A', first), ('B', second)]:
    assert report[speaker]['blinks']
    body = arm.animation_data.nla_tracks[0].strips[0].action
    assert all('jaw' not in fc.data_path for fc in body.fcurves)
    assert all(fc.data_path.startswith('pose.bones[') for fc in body.fcurves)
    head = [fc for fc in arm.animation_data.action.fcurves
            if fc.data_path == 'pose.bones["head"].rotation_euler']
    assert head and max(abs(k.co.y) for fc in head for k in fc.keyframe_points) < 0.4
    for frame in (1, 24, 60, 90):
        scene.frame_set(frame)
        assert max(abs(arm.matrix_world[r][c] - before[speaker][r][c])
                   for r in range(4) for c in range(4)) < 1e-6
        meshes = mouth_meshes(arm)
        opened = (max(sum(m.data.shape_keys.key_blocks[n].value for n in ('open','round','wide'))
                      for m in meshes) if meshes else abs(arm.pose.bones['jaw'].rotation_euler.x))
        talking = (speaker == 'A' and frame == 24) or (speaker == 'B' and frame == 60)
        assert (opened > .1) == talking, (speaker, frame, opened)
try:
    performance.play_clip(first, 'open_book', 73, 96, model=model)
except ValueError as e:
    assert 'open_book' in str(e) and 'available' in str(e)
else:
    raise AssertionError('unsupported prop action silently accepted')
if report['A']['idle'] == 'idle':
    count = len(bpy.data.actions)
    strip = performance.play_clip(first, 'walk', 73, 96, model=model, loop=True)
    assert len(bpy.data.actions) == count + 1  # one body copy; no reimported motion pack
    assert strip.action and all('jaw' not in fc.data_path for fc in strip.action.fcurves)
    scene.frame_set(80)
    assert not any(m.data.shape_keys.key_blocks['open'].value for m in mouth_meshes(first))
output = str(Path(__file__).with_suffix('.blend'))
bpy.ops.wm.save_as_mainfile(filepath=output, compress=True)
bpy.ops.wm.open_mainfile(filepath=output)
scene = bpy.context.scene; scene.frame_set(24)
for speaker, name in rigs.items():
    arm = bpy.data.objects[name]; meshes = mouth_meshes(arm)
    opened = (max(m.data.shape_keys.key_blocks['open'].value for m in meshes)
              if meshes else abs(arm.pose.bones['jaw'].rotation_euler.x))
    assert (opened > .1) == (speaker == 'A')
print('PERFORMANCE_OK', json.dumps(report))
'''


@pytest.mark.parametrize('model', MODELS, ids=['jaw rig', 'morph rig', 'astronaut'])
def test_reusable_talking_on_two_real_library_characters(tmp_path, model):
    if not model.is_file():
        model = Path.home() / 'Desktop/code/goosnav-3D-assets/assets/3D' / model.relative_to(LIBRARY)
    if not shutil.which('blender') or not model.is_file():
        pytest.skip('requires Blender and library models')
    check = tmp_path / 'check.py'; check.write_text(CHECK)
    result = subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                             '--python', str(check), '--', str(ROOT / 'blender'), str(model)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PERFORMANCE_OK' in result.stdout


@pytest.mark.parametrize('model', MODELS[:2], ids=['saved poses', 'NLA clips'])
def test_inventory_can_read_the_current_open_model_without_reappending_it(tmp_path, model):
    if not shutil.which('blender') or not model.is_file():
        pytest.skip('requires Blender and library model')
    script = tmp_path / 'inventory.py'
    script.write_text('''
import bpy, sys
sys.path.insert(0, sys.argv[-2])
import performance
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
assert {'idle', 'pose_idle'} & set(performance.available_clips(arm, model=sys.argv[-1]))
print('INVENTORY_OK')
''')
    result = subprocess.run(['blender', '-b', str(model), '--python-exit-code', '1',
                             '--python', str(script), '--', str(ROOT / 'blender'), str(model)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'INVENTORY_OK' in result.stdout
