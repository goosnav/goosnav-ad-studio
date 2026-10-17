"""Run inside Blender against a saved scene: do speakers visibly talk on their lines?

    blender -b scene.blend --python harness/scene_check.py -- request.json report.json

request: {"fps": 24, "rigs": {"GUY": "guy"}, "lines": [{"speaker", "text", "start", "end", "offscreen"}]}
For every frame of every line it evaluates the active camera (markers included):
- mouth: the speaker's mouth (open/round/wide morphs on v10 rigs, else the jaw bone) is open on
  a share of the line's frames, and shut between lines;
- face: the head is inside the frame, big enough to read, and the camera ray to it hits the
  character itself (its skinned meshes or parts parented to its head/jaw/neck), not a prop.
"""
import json
import math
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view

OPEN_DEG = 3.0          # jaw rotation that counts as open
FACE_BONES = ('head', 'jaw', 'neck')


def character_parts(arm):
    parts = {arm.name}
    for obj in bpy.data.objects:
        if any(m.type == 'ARMATURE' and m.object == arm for m in getattr(obj, 'modifiers', [])):
            parts.add(obj.name)
        elif obj.parent == arm and (obj.parent_type != 'BONE' or obj.parent_bone in FACE_BONES):
            parts.add(obj.name)
    return parts


def mouth_meshes(arm):
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys
            and any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)
            and 'open' in o.data.shape_keys.key_blocks]


def mouth_open(arm, meshes):
    """What actually moves the face: mouth morph weight (v10 rigs) or jaw rotation (jaw rigs)."""
    if meshes:
        return max(sum(m.data.shape_keys.key_blocks[k].value for k in ('open', 'round', 'wide')
                       if k in m.data.shape_keys.key_blocks) for m in meshes) > 0.25
    return abs(math.degrees(arm.pose.bones['jaw'].matrix_basis.to_euler().x)) > OPEN_DEG


def face_state(scene, arm, parts, depsgraph):
    cam = scene.camera
    head = arm.pose.bones['head']
    a, b = arm.matrix_world @ head.head, arm.matrix_world @ head.tail
    point = (a + b) / 2
    pa, pb, p = (world_to_camera_view(scene, cam, v) for v in (a, b, point))
    inside = p.z > cam.data.clip_start and 0.02 < p.x < 0.98 and 0.02 < p.y < 0.98
    size = math.hypot(pa.x - pb.x, (pa.y - pb.y) * scene.render.resolution_y / scene.render.resolution_x)
    origin = cam.matrix_world.translation
    ray = point - origin
    hit, _, _, _, obj, _ = scene.ray_cast(depsgraph, origin, ray.normalized(), distance=ray.length + 0.5)
    clear = (not hit) or obj.name in parts or (obj.original and obj.original.name in parts)
    return inside, size, clear


def main():
    args = sys.argv[sys.argv.index('--') + 1:]
    request = json.load(open(args[0]))
    scene = bpy.context.scene
    fps = request['fps']
    rigs = {s: bpy.data.objects.get(name) for s, name in request['rigs'].items()}
    report = {'lines': [], 'idle': {}, 'problems': []}
    missing = [s for s, arm in rigs.items() if arm is None or 'jaw' not in arm.pose.bones or 'head' not in arm.pose.bones]
    if missing:
        report['problems'].append(f'no rig with head/jaw bones for {missing}; check result rigs names')
        json.dump(report, open(args[1], 'w'), indent=2); return
    for speaker, model in (request.get('models') or {}).items():
        # The speaker must BE the library character: same skeleton as the model file's armature.
        with bpy.data.libraries.load(model, link=False) as (source, target):
            target.armatures = list(source.armatures)
        skeletons = [{b.name for b in a.bones} for a in target.armatures if a]
        if not any({b.name for b in rigs[speaker].data.bones} == bones for bones in skeletons):
            report['problems'].append(f'{speaker} is not the library character {model}: its armature does not '
                                      'match; append the character from that file instead of building one')
    parts = {s: character_parts(arm) for s, arm in rigs.items()}
    mouths = {s: mouth_meshes(arm) for s, arm in rigs.items()}
    talking = {s: set() for s in rigs}
    for line in request['lines']:
        frames = range(scene.frame_start + int(line['start'] * fps), scene.frame_start + math.ceil(line['end'] * fps))
        talking.setdefault(line['speaker'], set()).update(frames)
        arm = rigs.get(line['speaker'])
        if arm is None:
            report['problems'].append(f'"{line["text"]}": speaker {line["speaker"]} has no rig'); continue
        opened = seen = 0; sizes = []
        for f in frames:
            scene.frame_set(f)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            if mouth_open(arm, mouths[line['speaker']]):
                opened += 1
            inside, size, clear = face_state(scene, arm, parts[line['speaker']], depsgraph)
            if inside and clear and size > 0.035:
                seen += 1
            sizes.append(size)
        n = max(1, len(frames))
        entry = {'text': line['text'], 'speaker': line['speaker'], 'mouth_open': round(opened / n, 2),
                 'face_visible': round(seen / n, 2), 'face_size': round(max(sizes, default=0), 3)}
        report['lines'].append(entry)
        if entry['mouth_open'] < 0.3:
            report['problems'].append(f'"{line["text"]}": {line["speaker"]}\'s mouth is open on only '
                                      f'{entry["mouth_open"]:.0%} of the line; key mouths.json with blender/lipsync.py')
        if not line.get('offscreen') and entry['face_visible'] < 0.3:
            report['problems'].append(f'"{line["text"]}": {line["speaker"]}\'s face is visible, unblocked and '
                                      f'readable on only {entry["face_visible"]:.0%} of the line (size {entry["face_size"]})')
    for speaker, arm in rigs.items():
        if arm is None:
            continue
        quiet = [f for f in range(scene.frame_start, scene.frame_end + 1)
                 if not any(abs(f - t) <= 3 for t in talking.get(speaker, ()))]
        opened = 0
        for f in quiet[::2]:
            scene.frame_set(f)
            opened += mouth_open(arm, mouths[speaker])
        share = opened / max(1, len(quiet[::2]))
        report['idle'][speaker] = round(share, 2)
        if share > 0.1:
            report['problems'].append(f'{speaker}\'s mouth is open on {share:.0%} of frames where they are silent')
    json.dump(report, open(args[1], 'w'), indent=2)


main()
