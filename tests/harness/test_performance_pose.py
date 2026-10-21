"""Synthetic Blender regression; no catalog layout or production agents required."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECK = r'''
import bpy, math, sys
from pathlib import Path
sys.path.insert(0, sys.argv[-1])
import performance
s = bpy.context.scene
s.render.fps = 24
s.frame_start = 1
arms = []
for name in ('A', 'B'):
    bpy.ops.object.armature_add()
    arm = bpy.context.object
    arm.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    arm.data.edit_bones.remove(arm.data.edit_bones[0])
    for n in ('head', 'neck', 'jaw', 'hand'):
        b = arm.data.edit_bones.new(n); b.head = (0,0,0); b.tail = (0,0,1)
    bpy.ops.object.mode_set(mode='OBJECT')
    for b in arm.pose.bones: b.rotation_mode = 'XYZ'
    arm.pose.bones['head'].rotation_euler.x = math.radians(-26)
    arm.pose.bones['neck'].rotation_euler.x = math.radians(-24)
    c = arm.pose.bones['hand'].constraints.new('LIMIT_ROTATION')
    c.name = 'arm_ik'; c.influence = .7
    arms.append(arm)
idle = bpy.data.actions.new('idle')
idle.use_fake_user = True
for n in ('head', 'neck'):
    fc = idle.fcurves.new('pose.bones["%s"].rotation_euler' % n, index=0)
    for f,v in ((1,0),(13,.02),(25,0)): fc.keyframe_points.insert(f,v)
performance._clips = lambda arm, model=None: {'idle': idle}
# Shared authored action must remain intact, including keyed neck motion.
authored = bpy.data.actions.new('authored')
fc = authored.fcurves.new('pose.bones["neck"].rotation_euler', index=0)
fc.keyframe_points.insert(1, -.4); fc.keyframe_points.insert(49, -.6)
if sys.argv[-2] == 'static':
    fc.data_path = 'location'
for arm in arms: arm.animation_data_create().action = authored
nla=bpy.data.actions.new('authored gesture')
nf=nla.fcurves.new('pose.bones["hand"].rotation_euler',index=1)
nf.keyframe_points.insert(1,.2); nf.keyframe_points.insert(49,.4)
for arm in arms:
    track=arm.animation_data.nla_tracks.new(); track.name='authored gesture'
    track.strips.new('gesture',1,nla)
    driver=arm.driver_add('scale',2).driver; driver.expression='1.25'
# Catalogs retain disabled demo clips as a motion library. They must not
# suppress generated idle/nods: they do not animate the scene at all.
if sys.argv[-2] == 'muted':
    for arm in arms:
        track=arm.animation_data.nla_tracks.new(); track.name='idle library'
        track.strips.new('idle library',1,idle); track.mute=True
faces=[]
if sys.argv[-2] == 'morph':
    for arm in arms:
        mesh=bpy.data.meshes.new('face'); mesh.from_pydata([(0,0,0)],[],[])
        face=bpy.data.objects.new('face',mesh); s.collection.objects.link(face)
        mod=face.modifiers.new('rig','ARMATURE'); mod.object=arm
        for n in ('Basis','open','round','wide','blink','smile'): face.shape_key_add(name=n)
        faces.append(face)
    faces[1].data=faces[0].data
    smile=faces[0].data.shape_keys.key_blocks['smile']
    smile.value=.3; smile.keyframe_insert('value',frame=1)
    smile.value=.6; smile.keyframe_insert('value',frame=49)
    face_authored=faces[0].data.shape_keys.animation_data.action
rigs = {a.name:a.name for a in arms}
timeline = {'fps':24, 'sample_rate':24, 'duration':2, 'dialogue':[
    {'speaker':'A','start_sample':0,'end_sample':24}]}
mouths = {'fps':24,'frames':48,'speakers':{'A':[.7]*24+[0]*24,'B':[0]*48}}
def sample():
    result=[]
    for f in (1,13,25,48):
        s.frame_set(f)
        for arm in arms:
            assert abs(arm.pose.bones['head'].rotation_euler.x-math.radians(-26)) < .08
            if sys.argv[-2]=='static':
                assert abs(arm.pose.bones['neck'].rotation_euler.x-math.radians(-24)) < .025
            else:
                assert abs(arm.pose.bones['neck'].rotation_euler.x-fc.evaluate(f)) < 1e-6
            assert abs(arm.pose.bones['hand'].constraints['arm_ik'].influence-.7)<1e-6
            assert abs(arm.pose.bones['hand'].rotation_euler.y-nf.evaluate(f))<1e-6
            assert abs(arm.scale.z-1.25)<1e-6
            opened=(faces[arms.index(arm)].data.shape_keys.key_blocks['open'].value if faces
                    else abs(arm.pose.bones['jaw'].rotation_euler.x))
            assert (opened>.1)==(arm.name=='A' and f<=24)
            if faces:
                assert abs(faces[arms.index(arm)].data.shape_keys.key_blocks['smile'].value
                           -face_authored.fcurves[0].evaluate(f))<1e-6
            result.append(tuple(arm.pose.bones['head'].rotation_euler))
    return result
performance.apply(timeline,mouths,rigs)
first=sample(); count=len(bpy.data.actions)
if sys.argv[-2] == 'muted':
    s.frame_set(1); head0=arms[0].pose.bones['head'].rotation_euler.x
    s.frame_set(13); head1=arms[0].pose.bones['head'].rotation_euler.x
    assert abs(head1-head0) > .04, (head0,head1)
    assert all(a.animation_data.nla_tracks['idle library'].mute for a in arms)
performance.apply(timeline,mouths,rigs)
assert sample()==first
assert len(bpy.data.actions)==count
assert len(authored.fcurves)==1
if faces:
    assert faces[0].data != faces[1].data
    assert all(k.interpolation=='BEZIER' for k in face_authored.fcurves[0].keyframe_points)
# Generated ownership and baseline survive reopening the saved working scene.
output=str(Path(__file__).with_suffix('.blend'))
bpy.ops.wm.save_as_mainfile(filepath=output)
bpy.ops.wm.open_mainfile(filepath=output)
arms=[bpy.data.objects[n] for n in ('A','B')]
s=bpy.context.scene
idle=bpy.data.actions['idle']
count=len(bpy.data.actions)
performance.apply(timeline,mouths,rigs)
assert len(bpy.data.actions)==count
timeline['duration']=1; mouths['frames']=24
mouths['speakers']={'A':[0]*24,'B':[0]*24}
performance.apply(timeline,mouths,rigs)
s.frame_set(40)
assert abs(arms[0].pose.bones['jaw'].rotation_euler.x)<1e-6
if sys.argv[-2]=='morph':
    assert all(m.data.shape_keys.key_blocks['open'].value==0 for a in arms for m in performance._meshes(a))
# Quaternion-authored head rotation is not converted or replaced by idle/nods.
for arm in arms:
    arm.pose.bones['head'].rotation_mode='QUATERNION'
    arm.pose.bones['head'].rotation_quaternion=(.9238795,.3826834,0,0)
performance.apply(timeline,mouths,rigs)
s.frame_set(13)
assert all(a.pose.bones['head'].rotation_mode=='QUATERNION' for a in arms)
assert all(abs(a.pose.bones['head'].rotation_quaternion.x-.3826834)<1e-6 for a in arms)
print('POSE_OK')
'''

@pytest.mark.parametrize('mode', ['jaw', 'morph', 'static', 'muted'])
def test_authored_pose_and_animation_survive_repeat(tmp_path, mode):
    if not shutil.which('blender'):
        pytest.skip('requires Blender')
    script = tmp_path / 'pose.py'
    script.write_text(CHECK)
    result = subprocess.run(['blender', '-b', '--factory-startup', '--python-exit-code', '1',
                             '--python', str(script), '--', mode, str(ROOT / 'blender')],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'POSE_OK' in result.stdout
