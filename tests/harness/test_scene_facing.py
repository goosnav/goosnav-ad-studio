"""Face direction uses rig anatomy, not a catalog filename or world axis."""
from pathlib import Path
import shutil
import subprocess

import pytest

from harness.contracts import ContractError
from harness.media import check_scene

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('turn', ['front', 'back', 'head_back', 'quarter'])
def test_speaking_face_direction_before_render(tmp_path, turn):
    if not shutil.which('blender'):
        pytest.skip('requires Blender')
    script = tmp_path / 'build.py'
    scene = tmp_path / 'scene.blend'
    script.write_text('''
import bpy, math, sys
from mathutils import Vector
sys.path.insert(0, sys.argv[-3])
import lipsync
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.object.armature_add()
a=bpy.context.object; a.name='speaker'
bpy.ops.object.mode_set(mode='EDIT')
a.data.edit_bones.remove(a.data.edit_bones[0])
h=a.data.edit_bones.new('head'); h.head=(0,0,1.3); h.tail=(0,0,1.7)
j=a.data.edit_bones.new('jaw'); j.head=(0,0,1.4); j.tail=(0,-.3,1.4); j.parent=h
bpy.ops.object.mode_set(mode='OBJECT')
for bone in a.pose.bones: bone.rotation_mode='XYZ'
bpy.ops.mesh.primitive_cube_add(size=.4, location=(0,0,1.5))
face=bpy.context.object; face.parent=a
face.modifiers.new('skin','ARMATURE').object=a
vg=face.vertex_groups.new(name='head'); vg.add(list(range(8)),1,'REPLACE')
s=bpy.context.scene; s.render.fps=24; s.frame_start=1; s.frame_end=48
s.render.resolution_x=540; s.render.resolution_y=676
bpy.ops.object.camera_add(location=(0,-3,1.5)); s.camera=bpy.context.object
s.camera.rotation_euler=(Vector((0,0,1.5))-s.camera.location).to_track_quat('-Z','Y').to_euler()
turn=sys.argv[-2]
if turn=='back': a.rotation_euler.z=math.pi
if turn=='head_back': a.pose.bones['head'].rotation_euler.y=math.pi
if turn=='quarter': a.rotation_euler.z=math.pi/4
lipsync.apply({'fps':24,'speakers':{'A':[.7]*24+[0]*24}}, {'A':a.name})
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=sys.argv[-1])
''')
    result = subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                             '--python', str(script), '--', str(ROOT / 'blender'), turn, str(scene)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    lines = [{'speaker': 'A', 'text': 'Hello.', 'start': 0, 'end': 1}]
    if turn in {'back', 'head_back'}:
        with pytest.raises(ContractError, match='face is visible'):
            check_scene(scene, {'A': 'speaker'}, lines, 24)
    else:
        assert check_scene(scene, {'A': 'speaker'}, lines, 24)['lines'][0]['face_visible'] == 1
