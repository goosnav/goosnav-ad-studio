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

MAX_DEG = 28.0   # 17 (the library default) barely reads past the snout on screen


def apply(mouths_path, rigs, max_deg=MAX_DEG, bone='jaw'):
    mouths = json.load(open(mouths_path))
    scene = bpy.context.scene
    if round(scene.render.fps / scene.render.fps_base) != mouths['fps']:
        raise ValueError(f'scene fps differs from the mouth curves ({mouths["fps"]})')
    missing = set(mouths['speakers']) - set(rigs)
    if missing:
        raise ValueError(f'no rig given for speakers {sorted(missing)}')
    for speaker, curve in mouths['speakers'].items():
        pb = bpy.data.objects[rigs[speaker]].pose.bones[bone]
        pb.rotation_mode = 'XYZ'
        for i, openness in enumerate(curve):
            pb.rotation_euler = (math.radians(-openness * max_deg), 0.0, 0.0)
            pb.keyframe_insert('rotation_euler', frame=scene.frame_start + i)
        action = bpy.data.objects[rigs[speaker]].animation_data.action
        for fc in action.fcurves:
            if fc.data_path == f'pose.bones["{bone}"].rotation_euler':
                for k in fc.keyframe_points:
                    k.interpolation = 'CONSTANT'   # mouth chart: snap between shapes
