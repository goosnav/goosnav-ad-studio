"""Shot helpers that frame what an actor is doing at a given moment, for Blender Python.

face_camera(name, rig, seconds) builds a camera aimed at the actor's face from the side
the face is actually pointing at that time, using the v10 jaw's rest direction as
"forward" (the same convention harness/scene_check.py uses to judge face visibility).
Keep the gaze pitch to shoot up at a downcast face (a book's-eye view); swing moves the
camera off the nose axis so a long nose reads in three-quarter instead of end-on.
"""
import bpy
from mathutils import Vector


def face_forward(rig):
    """The face's world direction for the current frame."""
    head = rig.pose.bones['head']
    rest_head, rest_jaw = rig.data.bones['head'], rig.data.bones['jaw']
    up = (rest_head.tail_local - rest_head.head_local).normalized()
    forward = rest_jaw.tail_local - rest_jaw.head_local
    forward = (forward - up * forward.dot(up)).normalized()
    pose = (rig.matrix_world @ head.matrix @ rest_head.matrix_local.inverted()).to_3x3()
    return (pose @ forward).normalized()


def face_camera(name, rig, seconds, *, distance=0.78, lens=45, swing=0.35, lift=0.04,
                keep_pitch=True):
    scene = bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    current = scene.frame_current
    scene.frame_set(round(seconds * fps))
    look = face_forward(rig)
    flat = Vector((look.x, look.y, 0)).normalized()
    if not keep_pitch:
        look = flat
    side = Vector((-flat.y, flat.x, 0)) * swing
    head = rig.pose.bones['head']
    face = rig.matrix_world @ ((head.head + head.tail) / 2)
    data = bpy.data.cameras.new(name)
    data.lens, data.sensor_fit, data.sensor_width, data.clip_start = lens, 'VERTICAL', 24, 0.02
    cam = bpy.data.objects.new(name, data)
    scene.collection.objects.link(cam)
    cam.location = face + (look + side).normalized() * distance + Vector((0, 0, lift))
    cam.rotation_euler = (face + Vector((0, 0, -0.03)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.frame_set(current)
    return cam
