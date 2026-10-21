"""Key measured mouth movement onto Goosnav character rigs.

The controller measures each speaker's jaw curve from the dialogue stem (mouths.json in the
accepted audio artifacts). Call this AFTER keying the body, so the jaw keys win:

    import sys; sys.path.insert(0, '<repo>/blender')
    import lipsync
    lipsync.apply('/path/to/mouths.json', {'GUY': 'guy', 'FRIEND': 'gal'})

Rigs open the mouth by rotating the `jaw` pose bone by -X (goosnav-3D-assets README).
Frame 0 of the curve is the scene's frame_start. Save the .blend afterwards: the controller
checks the saved scene, not your render.
"""
import json
import math

import bpy
from mathutils import Euler

MAX_DEG = 28.0   # jaw rigs: 17 (the library default) barely reads past the snout on screen
MOUTH_KEYS = ('open', 'round', 'wide')


def mouth_meshes(arm):
    """Meshes skinned to this armature that carry mouth morphs (ps1guy v10: guy_head)."""
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys
            and any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)
            and 'open' in o.data.shape_keys.key_blocks]


def apply(mouths_path, rigs, max_deg=MAX_DEG, bone='jaw'):
    """Morph rigs get 'round' for small openings and 'open' for larger ones (weights sum <= 1);
    jaw rigs get the jaw bone rotated by -X. Constant interpolation: a mouth chart snaps."""
    if isinstance(mouths_path, dict):
        mouths = mouths_path
    else:
        with open(mouths_path) as f:
            mouths = json.load(f)
    scene = bpy.context.scene
    if round(scene.render.fps / scene.render.fps_base) != mouths['fps']:
        raise ValueError(f'scene fps differs from the mouth curves ({mouths["fps"]})')
    missing = set(mouths['speakers']) - set(rigs)
    if missing:
        raise ValueError(f'no rig given for speakers {sorted(missing)}')
    for speaker, curve in mouths['speakers'].items():
        arm = bpy.data.objects[rigs[speaker]]
        meshes = mouth_meshes(arm)
        if meshes:
            for mesh in meshes:
                if mesh.data.users > 1:
                    mesh.data = mesh.data.copy()
            paths = {f'key_blocks["{name}"].value' for name in MOUTH_KEYS}
        else:
            pb = arm.pose.bones[bone]
            rotation = ('rotation_quaternion' if pb.rotation_mode == 'QUATERNION' else
                        'rotation_axis_angle' if pb.rotation_mode == 'AXIS_ANGLE' else 'rotation_euler')
            paths = {pb.path_from_id(rotation)}
        datablocks = [m.data.shape_keys for m in meshes] if meshes else [arm]
        for block in datablocks:
            data = block.animation_data_create()
            if data.action and data.action.users > 1:
                data.action = data.action.copy()
            if data.action:
                for fc in list(data.action.fcurves):
                    if fc.data_path in paths:
                        data.action.fcurves.remove(fc)
        # Explicit closure also removes stale speech when a replacement is shorter.
        for i, openness in enumerate(list(curve) + [0.0]):
            frame = scene.frame_start + i
            if meshes:
                weights = {'open': openness if openness > 0.5 else 0.0,
                           'round': 0.8 if 0 < openness <= 0.5 else 0.0, 'wide': 0.0}
                for mesh in meshes:
                    for name, value in weights.items():
                        key = mesh.data.shape_keys.key_blocks.get(name)
                        if key:
                            key.value = value
                            key.keyframe_insert('value', frame=frame)
            else:
                value = Euler((math.radians(-openness * max_deg), 0.0, 0.0))
                if rotation == 'rotation_quaternion':
                    value = value.to_quaternion()
                elif rotation == 'rotation_axis_angle':
                    axis, angle = value.to_quaternion().to_axis_angle()
                    value = (angle, *axis)
                setattr(pb, rotation, value)
                pb.keyframe_insert(rotation, frame=frame)
        for block in datablocks:
            for fc in block.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    if fc.data_path in paths:
                        k.interpolation = 'CONSTANT'
