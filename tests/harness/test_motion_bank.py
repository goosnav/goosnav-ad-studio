"""Real v10 evaluation, isolated output; no agent/audio generation or source edits."""
from pathlib import Path
import hashlib
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / 'assets/goosnav-3D-assets'

CHECK = r'''
import bpy, json, math, sys, os
from pathlib import Path
from mathutils import Vector
sys.path.insert(0, sys.argv[-4])
import performance, staging
library, model, fps = Path(sys.argv[-3]), Path(sys.argv[-2]), int(sys.argv[-1])
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
s = bpy.context.scene
s.render.fps = fps; s.frame_start = 11; s.frame_end = 11 + 7 * fps
roots = [staging.import_actor(model, n, (x, 0, 0), 1.7)
         for n, x in [('actor.A', -.65), ('actor.B', .65)]]
arms = [bpy.data.objects[r['staging_rig']] for r in roots]
rigs = dict(zip(('A', 'B'), arms))
models = {n: str(model) for n in rigs}
# An authored static pose and action survive. The generated right-arm cue remains free.
for arm in arms:
    arm.pose.bones['head'].rotation_euler.x = -.36
    arm.pose.bones['neck'].rotation_euler.x = -.3
    b = arm.pose.bones['forearm.L']; b.rotation_euler.x = .4
    b.keyframe_insert('rotation_euler', frame=s.frame_start)
    b.rotation_euler.x = .5; b.keyframe_insert('rotation_euler', frame=s.frame_end)
    arm.pose.bones['hand.L'].constraints['arm_ik_rot'].influence = .17
original = [a.animation_data.action for a in arms]
timeline = {'fps': fps, 'sample_rate': 48000, 'duration': 7, 'dialogue': [
    {'speaker': 'A', 'start_sample': 0, 'end_sample': 96000},
    {'speaker': 'B', 'start_sample': 96000, 'end_sample': 192000}]}
mouths = {'fps': fps, 'frames': 7*fps, 'speakers': {
    'A': [.75 if i < 2*fps else 0 for i in range(7*fps)],
    'B': [.75 if 2*fps <= i < 4*fps else 0 for i in range(7*fps)]}}
cues = [
    {'speaker':'A', 'kind':'talk', 'start':0, 'end':4}, # must gate to measured line
    {'speaker':'B', 'kind':'listen', 'start':0, 'end':2},
    {'speaker':'B', 'kind':'talk', 'start':2, 'end':4},
    {'speaker':'A', 'kind':'gesture', 'start':.5, 'end':1.5},
    {'speaker':'B', 'kind':'look_at', 'start':0, 'end':2, 'target':'A'},
    {'speaker':'A', 'kind':'walk', 'start':4, 'end':6.5},
]
defaults=performance.conversation_cues(timeline,speakers=rigs)
assert [c for c in defaults if c['speaker']=='A' and c['kind']=='talk']==[
    {'speaker':'A','kind':'talk','start':0.0,'end':2.0}]
assert any(c['speaker']=='B' and c['kind']=='look_at' and c['target']=='A' for c in defaults)
assert performance.conversation_cues(dict(timeline,dialogue=timeline['dialogue']*2))==defaults
performance._cues(defaults,rigs,7)
def apply():
    return performance.apply(timeline, mouths, rigs, models=models,
                             library_root=library, cues=cues)
def at(t):
    s.frame_set(s.frame_start+round(t*fps)); bpy.context.view_layer.update()
def sample(t, arm=0, bone='hand.R'):
    at(t)
    a=arms[arm].evaluated_get(bpy.context.evaluated_depsgraph_get())
    return a.matrix_world @ a.pose.bones[bone].matrix
def mouth(arm):
    meshes=performance.lipsync.mouth_meshes(arm)
    return (sum(meshes[0].data.shape_keys.key_blocks[n].value for n in ('open','round','wide'))
            if meshes else abs(arm.pose.bones['jaw'].rotation_euler.x))
report=apply()
assert report['A']['bank']=='conversation-motion/v1'
assert report['A']['source_fps']==24
rest=sample(0); gesture=sample(1)
assert (gesture.translation-rest.translation).length>.06, 'gesture must visibly move hand'
assert sample(.75,1,'head').to_quaternion().rotation_difference(sample(0,1,'head').to_quaternion()).angle>.1, 'listener gaze must visibly move head'
# Gaze must turn toward the partner, not merely move in either direction.
head_rest=arms[1].data.bones['head'].matrix_local.to_3x3()
forward_local=head_rest.inverted() @ Vector((0,-1,0))
forward0=sample(0,1,'head').to_3x3() @ forward_local
forward1=sample(.75,1,'head').to_3x3() @ forward_local
assert forward1.x < forward0.x-.1, ('listener turned away from partner',forward0[:],forward1[:])
assert (sample(4.4,0,'foot.L').translation-sample(4.8,0,'foot.L').translation).length>.04, 'walk must move evaluated foot'
# Source motion advances 24 frames/second even when the scene runs at 30 fps.
at(4.5)
walk=next(t.strips[0].action for t in arms[0].animation_data.nla_tracks if t.name=='walk')
idle=next(t.strips[0].action for t in arms[0].animation_data.nla_tracks if t.name=='idle')
for axis in range(3):
    path='pose.bones["foot_ik.L"].location'
    wc=walk.fcurves.find(path,index=axis); ic=idle.fcurves.find(path,index=axis)
    baseline=json.loads(arms[0].animation_data.action['studio_baseline'])[path][axis]
    assert abs(arms[0].pose.bones['foot_ik.L'].location[axis]-(baseline+wc.evaluate(13)-ic.evaluate(1)))<1e-5
# Talk motion is visible, but a talk cue spanning silence cannot keep speaking arms raised.
assert (sample(2.75,1).translation-sample(0,1).translation).length>.015
assert (sample(3,0).translation-rest.translation).length<.02
for t,who in [(1,'A'),(3,'B'),(6,None)]:
    at(t)
    for name,a in rigs.items():
        assert (mouth(a)>.1)==(name==who), (t,name,mouth(a))
        assert abs(a.pose.bones['hand.L'].constraints['arm_ik_rot'].influence-.17)<1e-6
        expected=original[list(rigs).index(name)].fcurves.find('pose.bones["forearm.L"].rotation_euler',index=0).evaluate(s.frame_current)
        assert abs(a.pose.bones['forearm.L'].rotation_euler.x-expected)<1e-6
at(7)
assert abs(arms[0].pose.bones['head'].rotation_euler.x+.36)<.03
assert abs(arms[0].pose.bones['neck'].rotation_euler.x+.3)<.03
first=[list(sample(t).translation) for t in (0,1,3,4.4,6.8)]
count=len(bpy.data.actions)
apply()
assert len(bpy.data.actions)==count
assert first==[list(sample(t).translation) for t in (0,1,3,4.4,6.8)]
assert all(len(a.animation_data.nla_tracks)==(12 if 'astronaut' in model.stem else 11) for a in arms)
# No explicit root: discover only through the caller's supplied model ancestors.
performance.apply(timeline,mouths,rigs,models=models,cues=cues)
assert first==[list(sample(t).translation) for t in (0,1,3,4.4,6.8)]
out=Path(__file__).with_suffix('.blend'); bpy.ops.wm.save_as_mainfile(filepath=str(out))
names={k:a.name for k,a in rigs.items()}
bpy.ops.wm.open_mainfile(filepath=str(out),use_scripts=False)
s=bpy.context.scene; rigs={k:bpy.data.objects[n] for k,n in names.items()}; arms=list(rigs.values())
apply()
assert first==[list(sample(t).translation) for t in (0,1,3,4.4,6.8)]
if os.environ.get('MOTION_REVIEW') and fps==24 and model.stem=='ps1guy_v10':
    # Optional small visual acceptance artifact, isolated beside the test script.
    cam=bpy.data.objects.new('review.camera',bpy.data.cameras.new('review.camera'))
    s.collection.objects.link(cam);s.camera=cam;cam.location=(0,-5,1.9)
    cam.rotation_euler=(Vector((0,0,.95))-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.type='ORTHO';cam.data.ortho_scale=2.7
    s.render.engine='CYCLES';s.cycles.device='CPU';s.cycles.samples=8;s.cycles.use_denoising=False
    for layer in s.view_layers:layer.cycles.use_denoising=False
    s.render.resolution_x=360;s.render.resolution_y=450;s.render.resolution_percentage=100
    s.world.color=(.2,.2,.2)
    for label,position,energy in [('key',(-3,-4,5),550),('fill',(3,-2,3),300)]:
        d=bpy.data.lights.new(label,'AREA');d.energy=energy;d.shape='DISK';d.size=4
        ob=bpy.data.objects.new(label,d);s.collection.objects.link(ob);ob.location=position
        ob.rotation_euler=(Vector((0,0,1))-ob.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,-.015))
    for label,t in [('idle',0),('gesture-listen',1),('reply',2.75)]:
        at(t);s.render.filepath=str(Path(__file__).with_name('motion-'+label+'.png'))
        bpy.ops.render.render(write_still=True)
    print('MOTION_REVIEW',Path(__file__).parent)
# Empty replacement removes generated body cues and short replacement closes mouths.
performance.apply(timeline,mouths,rigs,models=models,library_root=library,cues=[])
assert (sample(1).translation-rest.translation).length<.04
# Invalid/missing banks fail before mutation, never execute even a syntactically valid module.
count=len(bpy.data.actions)
for bad in [dict(cues=[{'speaker':'A','kind':'fly','start':0,'end':1}]),
            dict(cues=[{'speaker':'A','kind':'look_at','start':0,'end':1,'target':'MISSING'}]),
            dict(cues=[{'speaker':'A','kind':'talk','start':0,'end':float('nan')}]),
            dict(library_root=library/'archive')]:
    args=dict(models=models,library_root=library,cues=cues); args.update(bad)
    try: performance.apply(timeline,mouths,rigs,**args)
    except (ValueError,FileNotFoundError): pass
    else: raise AssertionError(('accepted invalid cue',bad))
    assert len(bpy.data.actions)==count
# Literal parsing rejects code without executing it, even when BANK itself is valid.
recipe=library/'scripts/conversation_motion.py'
clean=recipe.read_text()
recipe.write_text(clean+'\nraise RuntimeError("EXECUTED")\n')
try:
    apply()
except ValueError as exc:
    assert 'literal BANK' in str(exc)
else:
    raise AssertionError('executable bank accepted')
finally:
    recipe.write_text(clean)
assert len(bpy.data.actions)==count
# Auto cues create visible speaking motion and a listener without an audio curve.
silent=dict(mouths,speakers={'A':mouths['speakers']['A']})
one_line=dict(timeline,dialogue=timeline['dialogue'][:1])
automatic=performance.conversation_cues(one_line, speakers=rigs)
performance.apply(one_line,silent,rigs,models=models,library_root=library,cues=automatic)
assert (sample(1).translation-sample(0).translation).length>.015
at(3); assert mouth(rigs['B'])==0
print('MOTION_BANK_OK',fps,model.name)
'''


@pytest.mark.parametrize('fps,model_name', [(24, 'ps1guy_v10.blend'),
                                         (30, 'ps1guy_v10_beady.blend'),
                                         (24, 'ps1guy_skeleton_v1.blend'),
                                         (30, 'ps1guy_astronaut_v1.blend')])
def test_evaluated_conversation_bank(tmp_path, fps, model_name):
    if not shutil.which('blender'):
        pytest.skip('requires Blender')
    # The bank must work after relocation, without the development checkout path.
    lib = tmp_path / 'relocated library'
    (lib / 'scripts').mkdir(parents=True)
    (lib / 'characters').mkdir()
    source = LIBRARY / 'characters' / model_name
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    shutil.copyfile(source, lib / 'characters' / model_name)
    shutil.copyfile(LIBRARY / 'scripts/conversation_motion.py', lib / 'scripts/conversation_motion.py')
    check = tmp_path / 'check.py'; check.write_text(CHECK)
    result = subprocess.run(['blender', '-b', '--factory-startup', '--disable-autoexec',
                             '--threads', '2', '--python-exit-code', '1', '--python', str(check),
                             '--', str(ROOT / 'blender'), str(lib),
                             str(lib / 'characters' / model_name), str(fps)],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'MOTION_BANK_OK' in result.stdout
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
