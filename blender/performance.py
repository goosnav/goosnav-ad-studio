"""Reusable planted conversation, built from the character's existing motion assets.

Run inside Blender. apply(timeline, mouths, rigs, models=...) owns animation on
the named characters only. It preserves actor placement, copies an idle clip,
adds small line-timed nods/blinks, then keys the measured mouths. No hand IK,
prop manipulation, rig rebuilding or model generation is involved.
"""
import json
import math
from pathlib import Path

import bpy
import lipsync


def _read(value):
    if isinstance(value, dict):
        return value
    with open(value) as f:
        return json.load(f)


def _arm(value):
    arm = bpy.data.objects[value] if isinstance(value, str) else value
    if arm.type != 'ARMATURE':
        raise ValueError(f'{arm.name} is not an armature')
    return arm


def _clips(arm, model=None):
    """Use this actor's NLA clips, or load bone actions from its original model."""
    model = model or arm.get('studio_motion_model')
    source_path = str(Path(model).resolve()) if model else None
    local = {track.name: strip.action for track in
             (arm.animation_data.nla_tracks if arm.animation_data else [])
             if not track.name.startswith('Studio clip:')
             for strip in track.strips if strip.action}
    cached = {a['studio_motion_clip']: a for a in bpy.data.actions
              if source_path and a.get('studio_motion_source') == source_path}
    if local:
        clips = local
    elif cached:
        clips = cached
    elif model and bpy.data.filepath and source_path == str(Path(bpy.data.filepath).resolve()):
        # Blender 4.0 can crash when it appends data from its own open file.
        clips = {action.name: action for action in bpy.data.actions}
    elif model:
        with bpy.data.libraries.load(str(model), link=False) as (source, target):
            names = [n for n in source.actions if '__Key' not in n]
            target.actions = list(names)
        clips = dict(zip(names, target.actions))
    else:
        clips = {}
    clips = {name: action for name, action in clips.items() if action and any(
        fc.data_path.startswith('pose.bones[') for fc in action.fcurves)}
    for name, action in clips.items():
        action.use_fake_user = True
        if source_path:
            action['studio_motion_source'] = source_path
            action['studio_motion_clip'] = name
    return clips


def available_clips(rig, model=None):
    """Actual embedded names; never promise an unsupported motion."""
    return sorted(_clips(_arm(rig), model))


def _strip(arm, action, start, end, loop, blend=0):
    # Copy before stripping the demo jaw/object tracks. Source motion stays intact.
    body = action.copy(); body.name = f'Studio body: {arm.name} / {action.name}'
    body.use_fake_user = False
    for key in ('studio_motion_source', 'studio_motion_clip'):
        if key in body:
            del body[key]
    for fc in list(body.fcurves):
        if not fc.data_path.startswith('pose.bones[') or 'pose.bones["jaw"]' in fc.data_path:
            body.fcurves.remove(fc)
    a, b = action.frame_range
    period = max(1, b - a)
    track = arm.animation_data_create().nla_tracks.new()
    track.name = f'Studio clip: {action.name}'
    strip = track.strips.new(body.name, int(start), body)
    strip.action_frame_start, strip.action_frame_end = a, a + period
    if loop:
        strip.repeat = max(1, math.ceil((end - start) / period))
    else:
        strip.scale = (end - start) / period
    strip.frame_end = end
    strip.extrapolation = 'NOTHING'
    strip.blend_type = 'REPLACE'
    strip.blend_in = strip.blend_out = min(blend, (end - start) / 4)
    return strip


def play_clip(rig, name, start, end, *, model=None, loop=False):
    """Schedule a named library clip in scene frames [start, end), not seconds.

    Use 'walk' for an in-place cycle or 'gesture' for an optional single gesture.
    This adds body motion only; measured speech remains authoritative. World
    travel/contact is not inferred. Missing clips raise instead of being invented.
    """
    if end <= start:
        raise ValueError('clip end must be after start')
    arm = _arm(rig); clips = _clips(arm, model)
    if name not in clips:
        raise ValueError(f'{name!r} unavailable on {arm.name}; available clips: {sorted(clips)}')
    return _strip(arm, clips[name], start, end, loop, blend=3)


def _meshes(arm):
    return [o for o in bpy.data.objects if o.type == 'MESH' and
            (o.parent == arm or any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers))]


def _blinks(meshes, start, end, fps, offset):
    targets = []
    for obj in meshes:
        keys = obj.data.shape_keys
        if keys and 'blink' in keys.key_blocks:
            targets.append((keys.key_blocks['blink'], 'value', 0.0, 1.0))
        elif 'eye' in obj.name.lower() or 'pupil' in obj.name.lower():
            targets.append((obj, 'scale', obj.scale.z, obj.scale.z * .06))
    frames = list(range(start + round((1.8 + offset * .37) * fps), end, round(3.3 * fps)))
    for target, path, opened, closed in targets:
        points = [(start, opened), (end, opened)]
        for f in frames:
            points.extend([(max(start, f - 2), opened), (f, closed), (min(end, f + 2), opened)])
        for frame, value in sorted(points):
            if path == 'value':
                target.value = value; target.keyframe_insert(path, frame=frame)
            else:
                target.scale.z = value; target.keyframe_insert(path, index=2, frame=frame)
    return frames if targets else []


def apply(timeline, mouths, rigs, *, models=None, nod_degrees=3):
    """One call for one/two standing speakers; use accepted audio paths or dicts.

    models maps speakers to their original .blend files, including older rigs
    with saved pose_idle actions rather than NLA clips. Rigs may include listeners.
    Optional gestures are added afterwards with play_clip, using actual clip names.
    """
    timeline, mouths = _read(timeline), _read(mouths)
    scene = bpy.context.scene; fps = scene.render.fps / scene.render.fps_base
    if fps != mouths['fps'] or fps != timeline['fps']:
        raise ValueError('scene, timeline and mouth fps must match')
    if not 0 <= nod_degrees <= 6:
        raise ValueError('nod_degrees must be between 0 and 6')
    if set(mouths['speakers']) - set(rigs):
        raise ValueError('every speaking character needs a rig')
    rate = timeline['sample_rate']; start = scene.frame_start
    end = start + mouths['frames']
    if rate <= 0 or mouths['frames'] != math.ceil(timeline['duration'] * fps):
        raise ValueError('invalid timeline duration or sample rate')
    prepared = []
    for speaker, value in rigs.items():
        arm = _arm(value); model = (models or {}).get(speaker)
        clips = _clips(arm, model)
        name = next((n for n in ('idle', 'pose_idle') if n in clips), None)
        if not name or 'head' not in arm.pose.bones:
            raise ValueError(f'{arm.name} needs a library idle/pose_idle and head bone; available: {sorted(clips)}')
        prepared.append((speaker, arm, model, name, clips[name]))
    report = {}; scene.frame_set(start)
    for index, (speaker, arm, model, name, idle) in enumerate(prepared):
        arm.animation_data_clear()
        if model:
            arm['studio_motion_model'] = str(model)
        meshes = _meshes(arm)
        for obj in meshes:
            # Duplicated actors may share shape-key data; speech must not leak
            # from one actor into the other actor's face.
            if obj.data.shape_keys and obj.data.users > 1:
                obj.data = obj.data.copy()
            obj.animation_data_clear()
            if obj.data.shape_keys:
                obj.data.shape_keys.animation_data_clear()
                for key in obj.data.shape_keys.key_blocks:
                    if key.name in ('open', 'round', 'wide', 'blink'):
                        key.value = 0
        # Imported previews/old hand-contact attempts must not override idle.
        for bone in arm.pose.bones:
            for constraint in bone.constraints:
                if constraint.name in ('arm_ik', 'arm_ik_rot'):
                    constraint.influence = 0
        if 'jaw' in arm.pose.bones:
            arm.pose.bones['jaw'].rotation_mode = 'XYZ'
            arm.pose.bones['jaw'].rotation_euler = (0, 0, 0)
        _strip(arm, idle, start, end, True)
        head = arm.pose.bones['head']; head.rotation_mode = 'XYZ'
        base = {fc.array_index: fc for fc in idle.fcurves
                if fc.data_path == 'pose.bones["head"].rotation_euler'}
        a, b = idle.frame_range
        lines = [(line['start_sample'] / rate, line['end_sample'] / rate)
                 for line in timeline['dialogue'] if line['speaker'] == speaker]
        for frame in sorted(set(range(start, end, 2)) | {end}):
            t = (frame - start) / fps
            pulse = max((math.sin(math.pi * (t - lo) / (hi - lo)) ** 2
                         for lo, hi in lines if lo <= t < hi), default=0)
            local = a + (frame - start) % max(1, b - a)
            head.rotation_euler = tuple(base[i].evaluate(local) if i in base else 0 for i in range(3))
            head.rotation_euler.x += math.radians(nod_degrees) * pulse
            head.keyframe_insert('rotation_euler', frame=frame)
        report[speaker] = {'idle': name, 'blinks': _blinks(meshes, start, end, fps, index)}
    lipsync.apply(mouths, rigs)
    scene.frame_set(start)
    return report
