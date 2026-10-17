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
    mouths = json.load(open(mouths_path))
    scene = bpy.context.scene
    if round(scene.render.fps / scene.render.fps_base) != mouths['fps']:
        raise ValueError(f'scene fps differs from the mouth curves ({mouths["fps"]})')
    missing = set(mouths['speakers']) - set(rigs)
    if missing:
        raise ValueError(f'no rig given for speakers {sorted(missing)}')
    for speaker, curve in mouths['speakers'].items():
        arm = bpy.data.objects[rigs[speaker]]
        meshes = mouth_meshes(arm)
        for i, openness in enumerate(curve):
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
                pb = arm.pose.bones[bone]
                pb.rotation_mode = 'XYZ'
                pb.rotation_euler = (math.radians(-openness * max_deg), 0.0, 0.0)
                pb.keyframe_insert('rotation_euler', frame=frame)
        datablocks = [m.data.shape_keys for m in meshes] if meshes else [arm]
        for block in datablocks:
            for fc in block.animation_data.action.fcurves:
                for k in fc.keyframe_points:
                    if fc.data_path.startswith(('key_blocks', f'pose.bones["{bone}"]')):
                        k.interpolation = 'CONSTANT'
