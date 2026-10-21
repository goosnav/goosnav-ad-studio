"""Reusable planted conversation, built from the character's existing motion assets.

Run inside Blender. apply(timeline, mouths, rigs, models=...) preserves authored
poses and animation, adds reference-relative idle on free Euler channels and
small line-timed nods/blinks, then keys the measured mouths. No hand IK,
prop manipulation, rig rebuilding or model generation is involved.
"""
import ast
import json
import math
from pathlib import Path

import bpy
import lipsync
from mathutils import Vector


def _active_path(value):
    path = Path(value).expanduser()
    if any(p.lower() in {'archive', 'archives', 'archived'}
           for p in (*path.parts, *path.resolve().parts)):
        raise ValueError('Motion sources must use active, non-archived paths')
    return path.resolve()


def _motion_bank(models, library_root):
    """Read literal asset recipes. Never import/exec code from an asset library."""
    if library_root is not None:
        roots = [_active_path(library_root)]
    else:
        roots = []
        for model in (models or {}).values():
            for parent in _active_path(model).parents:
                if (parent / 'scripts/conversation_motion.py').is_file():
                    roots.append(parent)
                    break
        roots = list(dict.fromkeys(roots))
    if len(roots) != 1:
        raise ValueError('Supply one library_root containing scripts/conversation_motion.py')
    path = roots[0] / 'scripts/conversation_motion.py'
    if path.is_symlink() or not _active_path(path).is_relative_to(roots[0]):
        raise ValueError('Motion recipe must remain inside its supplied library')
    if path.stat().st_size > 65536:
        raise ValueError('Motion recipe exceeds 64 KiB')
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        statements = [n for n in tree.body if not (
            isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str))]
        if (len(statements) != 1 or not isinstance(statements[0], ast.Assign)
                or len(statements[0].targets) != 1
                or not isinstance(statements[0].targets[0], ast.Name)
                or statements[0].targets[0].id != 'BANK'):
            raise ValueError('Motion recipe must contain only a literal BANK assignment')
        bank = ast.literal_eval(statements[0].value)
        recipes = bank['recipes']
        assert bank['schema'] == 'conversation-motion/v1'
        assert 1 <= _finite(bank['source_fps']) <= 240
        assert 0 < _finite(bank['transition_seconds']) <= 1
        assert set(recipes) == {'listen', 'talk', 'gesture', 'look_at', 'walk'}
        for kind in ('listen', 'gesture', 'walk'):
            recipe = recipes[kind]
            assert recipe['clip'] == {'listen': 'idle', 'gesture': 'gesture', 'walk': 'walk'}[kind]
            assert type(recipe['loop']) is bool
            assert isinstance(recipe['bones'], list) and recipe['bones']
            assert all(isinstance(n, str) and n not in ('jaw', 'root') for n in recipe['bones'])
        for name, axes in recipes['talk']['rotations'].items():
            assert name in {'head', 'neck', 'chest', 'upper_arm.L', 'upper_arm.R', 'forearm.L', 'forearm.R'}
            assert len(axes) == 3
            for offset, amplitude, frequency, phase in axes:
                assert abs(_finite(offset)) <= .5 and abs(_finite(amplitude)) <= .25
                assert 0 <= _finite(frequency) <= 4 and abs(_finite(phase)) <= 7
        assert 0 < _finite(recipes['look_at']['max_yaw']) <= .8
        assert 0 < _finite(recipes['look_at']['max_pitch']) <= .4
    except (SyntaxError, AssertionError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise ValueError('Invalid conversation-motion/v1 recipe') from exc
    return bank


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Motion values must be finite numbers')
    return value


def _cues(value, rigs, duration):
    if not isinstance(value, list):
        raise ValueError('cues must be a list')
    result = []
    for raw in value:
        if not isinstance(raw, dict) or set(raw) - {'speaker', 'kind', 'start', 'end', 'intensity', 'target'}:
            raise ValueError('Cue fields: speaker, kind, start, end, intensity, target')
        cue = dict(raw)
        if cue.get('speaker') not in rigs or cue.get('kind') not in {'talk', 'listen', 'gesture', 'look_at', 'walk'}:
            raise ValueError('Cue needs a known speaker and motion kind')
        if not 0 <= _finite(cue.get('start')) < _finite(cue.get('end')) <= duration:
            raise ValueError('Cue times must be inside the timeline, with end after start')
        cue['intensity'] = _finite(cue.get('intensity', 1.0))
        if not 0 <= cue['intensity'] <= 1:
            raise ValueError('Cue intensity must be between 0 and 1')
        if cue['kind'] == 'look_at':
            target = cue.get('target')
            if isinstance(target, str):
                if target not in rigs or target == cue['speaker']:
                    raise ValueError('look_at target must name another speaker')
            elif not isinstance(target, (list, tuple)) or len(target) != 3:
                raise ValueError('look_at target must be a speaker or world XYZ point')
            else:
                for v in target:
                    _finite(v)
        elif 'target' in cue:
            raise ValueError('Only look_at accepts a target; walk is in place')
        result.append(cue)
    # Accidental duplicate submissions cannot amplify a pose. Same-channel cues
    # must be sequential; different kinds compose in a documented fixed order.
    result = list({json.dumps(c, sort_keys=True): c for c in result}.values())
    for i, cue in enumerate(result):
        for other in result[:i]:
            same = cue['kind'] == other['kind'] or {cue['kind'], other['kind']} == {'talk', 'listen'}
            if (cue['speaker'] == other['speaker'] and same
                    and max(cue['start'], other['start']) < min(cue['end'], other['end'])):
                raise ValueError('Overlapping cues for the same speaker/channel')
    return sorted(result, key=lambda c: (c['speaker'], c['start'], c['kind']))


def conversation_cues(timeline, speakers=None):
    """Default body cues from accepted sample timings, without gesture boilerplate.

    `speakers` optionally includes silent listeners (an ID iterable or rig map).
    Merge overlapping/adjacent lines; listener gaze is gentle and only during an
    actual other speaker's line. This function performs no Blender mutation.
    """
    timeline = _read(timeline)
    duration = _finite(timeline['duration']); rate = _finite(timeline['sample_rate'])
    if duration <= 0 or rate <= 0:
        raise ValueError('Timeline duration/sample_rate must be positive')
    lines = []
    for line in timeline['dialogue']:
        lo = _finite(line['start_sample']) / rate
        hi = _finite(line['end_sample']) / rate
        if not isinstance(line.get('speaker'), str) or not line['speaker'] or not 0 <= lo <= hi <= duration:
            raise ValueError('Dialogue needs a speaker and bounded sample interval')
        if hi > lo:
            lines.append((line['speaker'], lo, hi))
    names = sorted(set(speakers if speakers is not None else (s for s, _, _ in lines)))
    if any(not isinstance(s, str) or not s for s in names) or set(s for s, _, _ in lines)-set(names):
        raise ValueError('speakers must include every dialogue speaker')
    edges = sorted({0.0, duration, *(v for _, lo, hi in lines for v in (lo, hi))})
    result = []
    for speaker in names:
        previous = {}
        for lo, hi in zip(edges, edges[1:]):
            talking = sorted({s for s, a, b in lines if a <= lo and hi <= b})
            kind = 'talk' if speaker in talking else 'listen'
            selected = [{'speaker': speaker, 'kind': kind, 'start': lo, 'end': hi}]
            if kind == 'listen' and talking:
                selected.append({'speaker': speaker, 'kind': 'look_at', 'start': lo, 'end': hi,
                                 'target': talking[0], 'intensity': .55})
            for cue in selected:
                key = (cue['kind'], cue.get('target'))
                last = previous.get(key)
                if last is not None and last['end'] == lo:
                    last['end'] = hi
                else:
                    previous[key] = cue
                    result.append(cue)
    return result


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
    source_path = str(_active_path(model)) if model else None
    local = {track.name: strip.action for track in
             (arm.animation_data.nla_tracks if arm.animation_data else [])
             if not track.name.startswith('Studio clip:')
             for strip in track.strips if strip.action}
    cached = {a['studio_motion_clip']: a for a in bpy.data.actions
              if source_path and a.get('studio_motion_source') == source_path}
    if any(name in local for name in ('idle', 'pose_idle')):
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
    clips.update(local)
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


def _active_nla_actions(data):
    # Libraries keep their entire motion pack in muted tracks. Those clips are
    # available to play_clip, but must not suppress procedural motion now.
    tracks = [t for t in data.nla_tracks if not t.mute]
    solo = any(t.is_solo for t in tracks)
    return [strip.action for track in tracks if not solo or track.is_solo
            for strip in track.strips if strip.action and not strip.mute]


def _begin(block):
    """Rebuild our composite action from the untouched authored action and pose.

    Metadata travels with the blend, so a repeat after save/reload is also safe.
    Other NLA tracks, drivers and constraints are never removed or muted.
    """
    data = block.animation_data_create()
    previous = data.action
    if previous and previous.get('studio_performance'):
        baseline = json.loads(previous['studio_baseline'])
        original = bpy.data.actions.get(previous.get('studio_original', ''))
        generated_paths = {fc.data_path for fc in previous.fcurves}
        authored_paths = {fc.data_path for fc in original.fcurves} if original else set()
        data.action = original
        for path, value in baseline.items():
            if path not in generated_paths or path in authored_paths:
                continue
            owner, _, prop = path.rpartition('.')
            setattr(block.path_resolve(owner) if owner else block, prop, value)
        if previous.users == 0:
            bpy.data.actions.remove(previous)
    else:
        original = previous
        baseline = {}
        if isinstance(block, bpy.types.Object):
            baseline['scale'] = list(block.scale)
            if block.type == 'ARMATURE':
                for bone in block.pose.bones:
                    for prop in ('location', 'rotation_euler', 'rotation_quaternion', 'scale'):
                        baseline[bone.path_from_id(prop)] = list(getattr(bone, prop))
        elif isinstance(block, bpy.types.Key):
            baseline = {key.path_from_id('value'): key.value for key in block.key_blocks}
    protected = set()
    actions = ([original] if original else []) + _active_nla_actions(data)
    for action in actions:
        protected.update(fc.data_path for fc in action.fcurves)
    protected.update(fc.data_path for fc in data.drivers)
    if original:
        original.use_fake_user = True
    generated = original.copy() if original else bpy.data.actions.new('Studio performance')
    generated.name = f'Studio performance: {block.name}'
    generated.use_fake_user = False
    generated['studio_performance'] = True
    generated['studio_original'] = original.name if original else ''
    generated['studio_baseline'] = json.dumps(baseline)
    data.action = generated
    return protected


def _blinks(meshes, start, end, fps, offset):
    targets = []
    for obj in meshes:
        keys = obj.data.shape_keys
        if keys and 'blink' in keys.key_blocks:
            if not _protected(keys, 'key_blocks["blink"].value'):
                targets.append((keys.key_blocks['blink'], 'value', keys.key_blocks['blink'].value, 1.0))
        elif ('eye' in obj.name.lower() or 'pupil' in obj.name.lower()) and not _protected(obj, 'scale'):
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


def _protected(block, path):
    data = block.animation_data
    if not data:
        return False
    original = bpy.data.actions.get(data.action.get('studio_original', '')) if data.action else None
    actions = ([original] if original else []) + _active_nla_actions(data)
    return any(fc.data_path == path for a in actions for fc in a.fcurves) or any(
        fc.data_path == path for fc in data.drivers)


def apply(timeline, mouths, rigs, *, models=None, nod_degrees=3,
          cues=None, library_root=None):
    """One call for one/two standing speakers; use accepted audio paths or dicts.

    models maps speakers to their original .blend files, including older rigs
    with saved pose_idle actions rather than NLA clips. Rigs may include listeners.
    Optional cues use seconds from timeline start and the asset-owned literal bank.
    Supply library_root, or resolve it from supplied model ancestors. Cue body
    channels are composed into this owned action, not hidden below it in NLA.
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
    bank = _motion_bank(models, library_root) if cues is not None else None
    cues = _cues(cues, rigs, timeline['duration']) if bank else []
    prepared = []
    if len({_arm(value).as_pointer() for value in rigs.values()}) != len(rigs):
        raise ValueError('each speaker needs a separate rig')
    for speaker, value in rigs.items():
        arm = _arm(value); model = (models or {}).get(speaker)
        clips = _clips(arm, model)
        name = next((n for n in ('idle', 'pose_idle') if n in clips), None)
        if not name or 'head' not in arm.pose.bones:
            raise ValueError(f'{arm.name} needs a library idle/pose_idle and head bone; available: {sorted(clips)}')
        if bank:
            for cue in cues:
                if cue['speaker'] == speaker and cue['kind'] in ('gesture', 'walk'):
                    if bank['recipes'][cue['kind']]['clip'] not in clips:
                        raise ValueError(f'{speaker}: missing {cue["kind"]} clip')
        prepared.append((speaker, arm, model, name, clips[name], clips))
    report = {}; scene.frame_set(start)
    # Freeze attention targets before writing any actor, so rig iteration order
    # cannot change gaze. This version aims at a fixed world point per cue.
    targets = {speaker: list(arm.matrix_world @ arm.pose.bones['head'].head)
               for speaker, arm, *_ in prepared}
    for index, (speaker, arm, model, name, idle, clips) in enumerate(prepared):
        protected = _begin(arm)
        if model:
            arm['studio_motion_model'] = str(model)
        meshes = _meshes(arm)
        for obj in meshes:
            # Duplicated actors may share shape-key data; speech must not leak
            # from one actor into the other actor's face.
            if obj.data.shape_keys and obj.data.users > 1:
                obj.data = obj.data.copy()
            _begin(obj)
            if obj.data.shape_keys:
                _begin(obj.data.shape_keys)
        # Add only reference-relative Euler idle motion on unauthored channels.
        # Quaternion/axis-angle rigs and authored curves retain their own motion.
        # In particular, never substitute the stock head/neck rest orientation.
        a, b = idle.frame_range
        channels = []
        for bone in arm.pose.bones:
            path = bone.path_from_id('rotation_euler')
            if bone.name == 'jaw' or bone.rotation_mode in ('QUATERNION', 'AXIS_ANGLE') or path in protected:
                continue
            curves = {fc.array_index: fc for fc in idle.fcurves if fc.data_path == path}
            if curves or bone.name == 'head':
                channels.append((bone, tuple(bone.rotation_euler), curves))
        lines = [(line['start_sample'] / rate, line['end_sample'] / rate)
                 for line in timeline['dialogue'] if line['speaker'] == speaker]
        if bank:
            detail = _animate_bank(arm, bank, [c for c in cues if c['speaker'] == speaker],
                                   idle, clips, protected, targets, lines, start, end, fps)
            report[speaker] = {'idle': name, 'blinks': _blinks(meshes, start, end, fps, index),
                               **detail}
            continue
        for frame in sorted(set(range(start, end, 2)) | {end}):
            t = (frame - start) / fps
            pulse = max((math.sin(math.pi * (t - lo) / (hi - lo)) ** 2
                         for lo, hi in lines if lo <= t < hi), default=0)
            local = a + (frame - start) % max(1, b - a)
            for bone, base, curves in channels:
                bone.rotation_euler = tuple(base[i] + (curves[i].evaluate(local) - curves[i].evaluate(a)
                                           if i in curves else 0) for i in range(3))
                if bone.name == 'head':
                    bone.rotation_euler.x += math.radians(nod_degrees) * pulse
                bone.keyframe_insert('rotation_euler', frame=frame)
        report[speaker] = {'idle': name, 'blinks': _blinks(meshes, start, end, fps, index)}
    if bank:
        # Silent cast members may have no audio curve at all. Close them explicitly
        # so a previous take cannot leave a listener's jaw/morphs open.
        mouths = dict(mouths, speakers={s: mouths['speakers'].get(s, [0.0]*mouths['frames']) for s in rigs})
    lipsync.apply(mouths, {speaker: _arm(value).name for speaker, value in rigs.items()})
    scene.frame_set(start)
    return report


def _envelope(t, lo, hi, fade):
    if t <= lo or t >= hi:
        return 0.0
    u = min(1.0, (t-lo)/min(fade, (hi-lo)/2), (hi-t)/min(fade, (hi-lo)/2))
    return u*u*(3-2*u)


def _body_curves(action, bones=None):
    result = {}
    for fc in action.fcurves:
        try:
            bone = fc.data_path.split('pose.bones["', 1)[1].split('"]', 1)[0]
        except IndexError:
            continue
        prop = fc.data_path.rsplit('.', 1)[-1]
        if (bone not in ('jaw', 'root') and (bones is None or bone in bones)
                and fc.data_path == f'pose.bones["{bone}"].{prop}'
                and prop in ('rotation_euler', 'location') and 0 <= fc.array_index < 3):
            result[(bone, prop, fc.array_index)] = fc
    return result


def _animate_bank(arm, bank, cues, idle, clips, protected, targets, lines, start, end, fps):
    """Bake a deterministic reference-relative composite, leaving authored paths alone."""
    recipes = bank['recipes']; source_fps = bank['source_fps']; fade = bank['transition_seconds']
    idle_curves = _body_curves(idle, recipes['listen']['bones'])
    idle_start, idle_end = idle.frame_range
    idle_reference = _body_curves(idle)
    clip_curves = {kind: _body_curves(clips[recipes[kind]['clip']], recipes[kind]['bones'])
                   for kind in ('gesture', 'walk') if any(c['kind'] == kind for c in cues)}
    keys = set(idle_curves)
    for curves in clip_curves.values():
        keys.update(curves)
    if any(c['kind'] == 'talk' for c in cues):
        keys.update((n, 'rotation_euler', i) for n in recipes['talk']['rotations'] for i in range(3))
    if any(c['kind'] == 'look_at' for c in cues):
        keys.update(('head', 'rotation_euler', i) for i in range(3))
    baseline = json.loads(arm.animation_data.action['studio_baseline'])
    channels = {}; skipped = set()
    for name, prop, axis in sorted(keys):
        bone = arm.pose.bones.get(name)
        if bone is None:
            raise ValueError(f'{arm.name}: bank requires bone {name}')
        path = bone.path_from_id(prop)
        if path in protected or (prop == 'rotation_euler' and bone.rotation_mode != 'XYZ'):
            skipped.add(path)
            continue
        # Reference values come from _begin, not the pose at the last sampled frame.
        channels[(name, prop, axis)] = (path, baseline[path][axis])
    # v10 head: +Y follows the bone, +Z is face forward (-Y in character space).
    head = arm.pose.bones['head']
    basis = arm.matrix_world.to_3x3() @ head.bone.matrix_local.to_3x3()
    origin = arm.matrix_world @ head.head
    angles = {}
    for i, cue in enumerate(cues):
        if cue['kind'] == 'look_at':
            target = targets[cue['target']] if isinstance(cue['target'], str) else cue['target']
            delta = basis.inverted() @ (Vector(target)-origin)
            yaw = math.atan2(delta.x, delta.z)
            pitch = -math.atan2(delta.y, math.hypot(delta.x, delta.z))
            limits = recipes['look_at']
            angles[i] = (max(-limits['max_pitch'], min(limits['max_pitch'], pitch)),
                         max(-limits['max_yaw'], min(limits['max_yaw'], yaw)), 0)
    samples = {key: [] for key in channels}
    for frame in range(start, end+1):
        t = (frame-start)/fps
        idle_frame = idle_start + (t*source_fps) % max(1, idle_end-idle_start)
        values = {key: base + (idle_curves[key].evaluate(idle_frame)-idle_curves[key].evaluate(idle_start)
                               if key in idle_curves else 0)
                  for key, (_, base) in channels.items()}
        # Whole-body locomotion first; speaking and selected gestures overlay it.
        for i, cue in sorted(enumerate(cues), key=lambda item: {'listen':0,'walk':1,'talk':2,'gesture':3,'look_at':4}[item[1]['kind']]):
            kind=cue['kind']; weight=_envelope(t,cue['start'],cue['end'],fade)*cue['intensity']
            if not weight:
                continue
            if kind == 'listen':
                for key in idle_curves:
                    if key in channels:
                        base = channels[key][1]
                        values[key] = base+(values[key]-base)*cue['intensity']
            elif kind in ('walk', 'gesture'):
                action=clips[recipes[kind]['clip']]; a,b=action.frame_range
                local = (a + ((t-cue['start'])*source_fps) % max(1,b-a) if recipes[kind]['loop']
                         else a + (t-cue['start'])/(cue['end']-cue['start'])*(b-a))
                for key, fc in clip_curves[kind].items():
                    if key not in channels:
                        continue
                    reference=idle_reference[key].evaluate(idle_start) if key in idle_reference else fc.evaluate(a)
                    delta=fc.evaluate(local)-reference
                    if kind == 'walk':
                        values[key] = (1-weight)*values[key]+weight*(channels[key][1]+delta)
                    else:
                        values[key] += weight*delta
            elif kind == 'talk':
                speech=max((_envelope(t,lo,hi,fade) for lo,hi in lines),default=0)
                for name, axes in recipes[kind]['rotations'].items():
                    for axis,(offset,amplitude,frequency,phase) in enumerate(axes):
                        key=(name,'rotation_euler',axis)
                        if key in channels:
                            values[key] += weight*speech*(offset+amplitude*math.sin(2*math.pi*frequency*(t-cue['start'])+phase))
            elif kind == 'look_at':
                for axis,angle in enumerate(angles[i]):
                    key=('head','rotation_euler',axis)
                    if key in channels:
                        values[key] += weight*angle
        for key,value in values.items():
            samples[key].extend((frame,value))
    action=arm.animation_data.action
    for key,points in samples.items():
        path,_=channels[key]; axis=key[2]
        old=action.fcurves.find(path,index=axis)
        if old:
            action.fcurves.remove(old)
        fc=action.fcurves.new(path,index=axis)
        fc.keyframe_points.add(len(points)//2)
        fc.keyframe_points.foreach_set('co',points)
        for k in fc.keyframe_points:
            k.interpolation='LINEAR'
        fc.update()
    return {'bank':bank['schema'], 'source_fps':source_fps,
            'cues':len(cues), 'skipped_authored_paths':sorted(skipped)}
