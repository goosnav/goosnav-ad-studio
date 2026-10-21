"""Real Blender staging regressions. No production assets or benchmark writes."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

BLENDER = shutil.which('blender')
MODULES = Path(__file__).resolve().parents[1] / 'blender'
pytestmark = pytest.mark.skipif(not BLENDER, reason='requires real Blender')


def run(tmp_path, code):
    script = tmp_path / 'check.py'
    script.write_text('import sys\nsys.dont_write_bytecode=True\n'
                      f'sys.path.insert(0, {str(MODULES)!r})\n'
                      'import bpy, math, hashlib, json\nfrom mathutils import Vector\n'
                      'from pathlib import Path\nimport staging\n'
                      f'root=Path({str(tmp_path)!r})\n' + code)
    result = subprocess.run([BLENDER, '-b', '--factory-startup', '--disable-autoexec',
                             '--python-exit-code', '1', '--python', str(script)],
                            capture_output=True, text=True, timeout=45,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    assert result.returncode == 0, result.stdout[-8000:] + result.stderr[-4000:]


SOURCE = '''
bpy.ops.wm.read_factory_settings(use_empty=True)
def cube(name, parent=None, location=(0,0,0), scale=(1,1,1)):
    bpy.ops.mesh.primitive_cube_add()
    obj=bpy.context.object; obj.name=name; obj.parent=parent
    obj.location=location; obj.scale=scale
    return obj
assembly=bpy.data.objects.new('Assembly',None)
bpy.context.scene.collection.objects.link(assembly)
assembly.location=(20,-4,7); assembly.scale=(2,3,.5); assembly.rotation_euler.z=.3
bpy.ops.object.armature_add()
rig=bpy.context.object; rig.name='SourceRig'; rig.parent=assembly
rig.location=(3,2,4); rig.scale=(.7,1.2,2)
body=cube('Body',rig,(0,0,1),(.4,.3,1))
mod=body.modifiers.new('Skin','ARMATURE'); mod.object=rig
group=body.vertex_groups.new(name=rig.data.bones[0].name)
group.add(list(range(len(body.data.vertices))),1,'REPLACE')
joint=bpy.data.objects.new('FaceParent',None); bpy.context.scene.collection.objects.link(joint)
joint.parent=rig; joint.location=(0,0,2)
head=cube('Head',joint,(0,0,.2),(.45,.35,.4))
head.shape_key_add(name='Basis'); key=head.shape_key_add(name='Smile')
for v in key.data: v.co.z += .15
key.value=.6
rig.pose.bones[0].location.z=.1
rig.pose.bones[0].keyframe_insert(data_path='location',frame=1)
rig.pose.bones[0].location.z=.3
rig.pose.bones[0].keyframe_insert(data_path='location',frame=12)
action=rig.animation_data.action; action.name='idle'
track=rig.animation_data.nla_tracks.new(); track.name='idle'
track.strips.new('idle',1,action); rig.animation_data.action=None
# Bound via modifier without being parented to the rig.
detached=cube('BoundDetached',None,(24,0,9),(.15,.15,.15))
detached.modifiers.new('Bind','ARMATURE').object=rig
scenery=cube('Scenery',assembly,(40,40,-10),(20,20,1))
bpy.ops.object.camera_add(); bpy.ops.object.light_add(type='POINT')
text=bpy.data.texts.new('do_not_run.py'); text.use_module=True
text.write('raise RuntimeError("Imported text must never execute")')
bpy.context.scene.frame_set(1)
source=root/'actor.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(source))
original=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.read_factory_settings(use_empty=True)
'''


def test_import_actual_bounds_hierarchy_animation_and_independent_instances(tmp_path):
    run(tmp_path, SOURCE + '''
a=staging.import_actor(source,'A',(-2,1,.3),1.8)
b=staging.world_bounds([a])
assert abs(b['size'][2]-1.8)<1e-5, b
assert abs(b['min'][2]-.3)<1e-5, b
assert abs(b['center'][0]+2)<1e-5 and abs(b['center'][1]-1)<1e-5, b
objects=list(a.children_recursive)
assert sorted(o.type for o in objects).count('ARMATURE')==1
assert len([o for o in objects if o.type=='MESH'])==3
assert not any(o.type in {'CAMERA','LIGHT'} or 'Scenery' in o.name for o in bpy.context.scene.objects)
ar=bpy.data.objects[a['staging_rig']]
head=next(o for o in objects if o.get('staging_source_name')=='Head')
assert head.parent.get('staging_source_name')=='FaceParent'
assert head.parent.parent==ar
assert abs(head.data.shape_keys.key_blocks['Smile'].value-.6)<1e-5
body=next(o for o in objects if o.get('staging_source_name')=='Body')
assert body.modifiers['Skin'].object==ar
assert len(ar.animation_data.nla_tracks)==1
keys=[tuple(k.co) for f in ar.animation_data.nla_tracks[0].strips[0].action.fcurves for k in f.keyframe_points]
assert (1.,.1) in [(x,round(y,1)) for x,y in keys]
other=staging.import_actor(source,'B',(2,1,0),1.2)
br=bpy.data.objects[other['staging_rig']]
assert ar!=br and ar.data!=br.data
assert abs(staging.world_bounds(other)['size'][2]-1.2)<1e-5
before=staging.world_bounds(a)
body_before=staging.world_bounds(body)
other.location.x+=4; bpy.context.view_layer.update()
assert staging.world_bounds(a)==before
bpy.context.scene.frame_set(12)
assert staging.world_bounds(body) != body_before  # pose-bone local Z need not be world Z
assert hashlib.sha256(source.read_bytes()).hexdigest()==original
assert all(o.library is None and (o.data is None or o.data.library is None) for o in a.children_recursive)
''')


@pytest.mark.parametrize('projection', ['PERSP', 'ORTHO'])
def test_portrait_custom_angles_head_regions_and_projected_vertices(tmp_path, projection):
    run(tmp_path, SOURCE + f'''
from bpy_extras.object_utils import world_to_camera_view
a=staging.import_actor(source,'A',(-2,1,0),1.8)
b=staging.import_actor(source,'B',(2,-.5,.25),1.4)
scene=bpy.context.scene; scene.render.resolution_x=540; scene.render.resolution_y=675
scene.render.pixel_aspect_x=1.2; scene.render.pixel_aspect_y=1
bpy.ops.object.camera_add(); cam=bpy.context.object; cam.data.type={projection!r}
cam.data.lens=65; cam.data.shift_x=.13; cam.data.shift_y=-.09
cam.data.clip_end=2
for direction in ((.2,1,-.15),(-1,.4,-.4),(0,0,-1)):
    report=staging.frame_subjects(cam,[a,b],.08,view_direction=direction)
    assert report['all_inside_margin'], report
    assert cam.data.lens==65 and abs(cam.data.shift_x-.13)<1e-6 and abs(cam.data.shift_y+.09)<1e-6
    expected=Vector(direction).normalized()
    assert ((cam.matrix_world.to_quaternion() @ Vector((0,0,-1)))-expected).length<1e-5
    # Independently inspect every evaluated vertex, not the helper's own report.
    deps=scene.view_layers[0].depsgraph
    for actor in (a,b):
        for obj in actor.children_recursive:
            if obj.type!='MESH': continue
            evaluated=obj.evaluated_get(deps)
            for vertex in evaluated.data.vertices:
                p=world_to_camera_view(scene,cam,evaluated.matrix_world @ vertex.co)
                assert .07999 <= p.x <= .92001 and .07999 <= p.y <= .92001, tuple(p)
                assert cam.data.clip_start < p.z < cam.data.clip_end
    rotation=cam.matrix_world.to_quaternion().copy()
    staging.frame_subjects(cam,[a,b],.1)
    assert abs(rotation.dot(cam.matrix_world.to_quaternion()))> .999999
# A close-up region is chosen explicitly by the worker, not inferred as a face.
bounds=staging.world_bounds(a)
region={{'name':'chosen upper body','min':bounds['min'][:],'max':bounds['max'][:]}}
region['min'][2]+=.65*bounds['size'][2]
report=staging.frame_subjects(cam,[region],.1,view_direction=(0,1,-.1))
assert report['all_inside_margin']
assert len(report['subjects'])==1
json.dumps(report,allow_nan=False)
''')


def test_ambiguous_rigs_invalid_parameters_and_no_scenery_import(tmp_path):
    run(tmp_path, SOURCE + '''
bpy.ops.wm.open_mainfile(filepath=str(source),use_scripts=False)
bpy.ops.object.armature_add(); bpy.context.object.name='OtherRig'
bpy.ops.wm.save_as_mainfile(filepath=str(root/'multiple.blend'))
bpy.ops.wm.read_factory_settings(use_empty=True)
def rejects(call):
    try: call()
    except ValueError: pass
    else: raise AssertionError('Expected explicit failure')
rejects(lambda: staging.import_actor(root/'multiple.blend','A',(0,0,0),1.8))
assert len(bpy.context.scene.objects)==0
actor=staging.import_actor(root/'multiple.blend','A',(0,0,0),1.8,rig_name='SourceRig')
assert len([o for o in bpy.context.scene.objects if o.type=='ARMATURE'])==1
rejects(lambda: staging.import_actor(source,'Bad',(0,0,0),0))
rejects(lambda: staging.import_actor(source,'Bad',(float('nan'),0,0),1))
bpy.ops.object.camera_add(); cam=bpy.context.object
for margin in (-.1,.5,float('nan')):
    rejects(lambda: staging.frame_subjects(cam,[actor],margin))
rejects(lambda: staging.frame_subjects(cam,[],.1))
rejects(lambda: staging.frame_subjects(cam,[actor],.1,view_direction=(0,0,0)))
cam.data.type='PANO'; rejects(lambda: staging.frame_subjects(cam,[actor],.1))
''')


def test_render_and_reopen_fitted_portrait_scene(tmp_path):
    run(tmp_path, SOURCE + '''
import time
started=time.monotonic()
a=staging.import_actor(source,'A',(-1.2,0,0),1.8)
b=staging.import_actor(source,'B',(1.2,.5,0),1.55)
for actor,color in ((a,(.7,.2,.06,1)),(b,(.04,.3,.65,1))):
    mat=bpy.data.materials.new(actor.name+'.material'); mat.diffuse_color=color
    for obj in actor.children_recursive:
        if obj.type=='MESH': obj.data.materials.clear(); obj.data.materials.append(mat)
scene=bpy.context.scene
scene.render.resolution_x=248; scene.render.resolution_y=310; scene.render.resolution_percentage=100
bpy.ops.object.camera_add(); camera=bpy.context.object; scene.camera=camera
camera.data.lens=50
report=staging.frame_subjects(camera,[a,b],.09,view_direction=(.15,1,-.12))
assert report['all_inside_margin']
scene.world=bpy.data.worlds.new('World'); scene.world.color=(.15,.15,.15)
bpy.ops.object.light_add(type='AREA',location=(-2,-4,6))
light=bpy.context.object; light.data.energy=800; light.data.size=5
light.rotation_euler=(Vector((0,0,1))-light.location).to_track_quat('-Z','Y').to_euler()
scene.render.engine='BLENDER_EEVEE'; scene.eevee.taa_render_samples=8
scene.render.threads_mode='FIXED'; scene.render.threads=2
scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(root/'portrait.png')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'staged.blend'))
bpy.ops.render.render(write_still=True)
assert (root/'portrait.png').stat().st_size>2000
report['build_render_seconds']=time.monotonic()-started
(root/'projection.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.open_mainfile(filepath=str(root/'staged.blend'),use_scripts=False)
assert abs(staging.world_bounds(bpy.data.objects['A'])['size'][2]-1.8)<1e-5
assert bpy.data.objects[bpy.data.objects['A']['staging_rig']].animation_data.nla_tracks
''')
