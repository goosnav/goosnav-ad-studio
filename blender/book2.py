"""Perform the openable Book Two (props/hq/book2_goosnav_dilemma_openable[_v2].blend) on a cut.

Run inside Blender after appending the "Book Two — openable" collection.

    import book2
    book2.retime(open_through=4, turns={5: 7.95, 6: 14.3}, slam=18.22)   # seconds
    book2.turn_page_by_hand(rig, 'R', 5, 7.95)
    book2.slam_by_hand(rig, 'R', 18.22, hold_until=21.5)

The library file holds one demonstration action per hinge (cover 13-49, leaf n turning
on frames 73+44(n-1) .. +28) and a Curl shape-key action per leaf. retime() bakes new
actions that sample that demo on your timeline, so the artwork, hinge travel and paper
curl stay exactly the asset's. Leaf n shows printed pages 2n-1 (front) and 2n (back);
with leaves 1..k turned the spread is pages 2k | 2k+1.

Hand helpers drive the v10 rig's existing hand IK (forearm IK constraint, influence 0 at
rest): the wrist rides the turning leaf's free edge, offset so the fingertips touch it.
"""
import math
import re

import bpy
from mathutils import Vector

def _hinges():
    """Cover plus every leaf hinge in the scene: 6 leaves in v1, 72 in v2 (actual interior)."""
    leaves = sorted((o for o in bpy.data.objects if re.fullmatch(r'Page_\d+_Hinge', o.name)),
                    key=lambda o: int(o.name.split('_')[1]))
    return ['Cover_Hinge'] + [o.name for o in leaves]
HAND_OFFSET = Vector((0, 0.015, 0.068))   # v10 three-fingered hand hangs ~7 cm below the wrist
_state = {}


def _demo_turn(leaf):
    start = 73 + 44 * (leaf - 1)
    return start, start + 28


def leaf_object(leaf):
    return next(o for o in bpy.data.objects if o.name.startswith(f'Leaf_{leaf:02d}_'))


def _fps():
    scene = bpy.context.scene
    return scene.render.fps / scene.render.fps_base


def retime(*, open_through=0, turns=None, slam=None, turn_seconds=0.5, close_seconds=0.25,
           frames=None):
    """Bake the book's hinges and curls onto the scene timeline.

    open_through: leaves already turned at frame 0 (0 = cover open on page 1). turns:
    {leaf: start seconds}, consecutive leaves after open_through. slam: seconds at which
    every turned leaf and the cover hit shut.
    """
    scene = bpy.context.scene
    fps = _fps()
    frames = frames or scene.frame_end + 1
    turns = dict(sorted((turns or {}).items(), key=lambda kv: kv[1]))
    expected = list(range(open_through + 1, open_through + 1 + len(turns)))
    if list(turns) != expected:
        raise ValueError(f'turns must be the next consecutive leaves {expected}, in time order')
    if turns and slam is not None and slam - close_seconds < max(turns.values()) + turn_seconds:
        raise ValueError('the slam must start after the last page turn finishes')
    hold = _demo_turn(open_through)[1] + 7 if open_through else 56

    def demo(t):
        frame = hold
        for leaf, at in turns.items():
            a, b = _demo_turn(leaf)
            if t < at:
                return frame
            if t < at + turn_seconds:
                return a + (t - at) / turn_seconds * (b - a)
            frame = b
        return frame

    owners = []
    for name in _hinges():
        hinge = bpy.data.objects[name]
        owners.append((hinge, hinge.animation_data.action))
        if name != 'Cover_Hinge':
            keys = leaf_object(int(name.split('_')[1])).data.shape_keys
            owners.append((keys, keys.animation_data.action))
    shut = slam - close_seconds if slam is not None else None
    for owner, source in owners:
        source = bpy.data.actions.get(source.get('book2_demo', source.name)) or source
        action = bpy.data.actions.new(f'Book2 retimed: {owner.name}')
        action['book2_demo'] = source.name
        for fc in source.fcurves:
            closed = fc.evaluate(1)
            points = []
            for frame in range(frames):
                t = frame / fps
                value = fc.evaluate(demo(min(t, shut) if shut is not None else t))
                if shut is not None and t > shut:
                    u = min(1.0, (t - shut) / close_seconds)
                    if fc.data_path.endswith('value'):     # the paper flexes mid-slam
                        value = 0.55 * math.sin(math.pi * u) if u < 1 else 0.0
                    else:                                  # accelerating into the hit
                        value += (closed - value) * u * u
                points += [frame, value]
            new = action.fcurves.new(fc.data_path, index=fc.array_index)
            new.keyframe_points.add(frames)
            new.keyframe_points.foreach_set('co', points)
            for k in new.keyframe_points:
                k.interpolation = 'LINEAR'
        owner.animation_data.action = action
    if slam is not None:
        jolt(slam)
    _state.update(turn_seconds=turn_seconds, close_seconds=close_seconds)


def jolt(at, root='Book2_Root'):
    """A small hop and pitch of the whole book on impact."""
    book = bpy.data.objects[root]
    rot, loc = book.rotation_euler.copy(), book.location.copy()
    hit = at * _fps()
    for dt, pitch, lift in ((-2, 0, 0), (0, 0, 0), (1, math.radians(-1.6), 0.004),
                            (3, math.radians(0.5), 0.0), (5, 0, 0)):
        book.rotation_euler = rot
        book.rotation_euler.x = rot.x + pitch
        book.location = loc + Vector((0, 0, lift))
        book.keyframe_insert('rotation_euler', frame=hit + dt)
        book.keyframe_insert('location', frame=hit + dt)
    book.rotation_euler, book.location = rot, loc


def edge_point(obj, frame, along=0.0):
    """World position of a leaf/cover's free edge (max local x) at a frame, curl included."""
    scene = bpy.context.scene
    scene.frame_set(int(frame), subframe=frame % 1)
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    verts = evaluated.data.vertices
    xmax = max(v.co.x for v in verts)
    edge = [v.co for v in verts if v.co.x > xmax - 0.004]
    return evaluated.matrix_world @ Vector(min(edge, key=lambda co: abs(co.y - along)))


def _local(arm, bone, world):
    """IK targets parent to the unposed root: a world point as the bone's location channel."""
    rest = arm.matrix_world @ arm.pose.bones[bone].bone.matrix_local
    return rest.inverted() @ world


def _key_target(arm, side, frame, world=None):
    pb = arm.pose.bones[f'hand_ik.{side}']
    pb.location = _local(arm, pb.name, world) if world is not None else Vector()
    pb.keyframe_insert('location', frame=frame)


def ik(arm, side, frame, influence):
    con = next(c for c in arm.pose.bones[f'forearm.{side}'].constraints if c.type == 'IK')
    con.influence = influence
    con.keyframe_insert('influence', frame=frame)


def turn_page_by_hand(arm, side, leaf, start, *, reach=0.42, release=0.55, step=2):
    """Reach to the leaf's outer edge, ride it over the spine as it turns, then withdraw."""
    fps = _fps()
    seconds = _state.get('turn_seconds', 0.5)
    obj = leaf_object(leaf)
    begin = edge_point(obj, start * fps) + HAND_OFFSET
    ik(arm, side, (start - reach - 0.05) * fps, 0.0)
    pb = arm.pose.bones[f'hand_ik.{side}']
    pb.location = _local(arm, pb.name, begin) * 0.35
    pb.keyframe_insert('location', frame=(start - reach) * fps)
    _key_target(arm, side, (start - 0.06) * fps, begin)
    ik(arm, side, (start - 0.12) * fps, 1.0)
    for i in range(0, int(seconds * fps) + 1, step):
        frame = start * fps + i
        _key_target(arm, side, frame, edge_point(obj, frame) + HAND_OFFSET)
    end = start + seconds
    ik(arm, side, (end + 0.10) * fps, 1.0)
    ik(arm, side, (end + release) * fps, 0.0)
    _key_target(arm, side, (end + release + 0.05) * fps)


def slam_by_hand(arm, side, slam, *, hold_until, cover='Front cover', root='Book2_Root'):
    """Grab the turned stack's edge, slam it shut, then press the closed book down."""
    fps = _fps()
    grab = slam - _state.get('close_seconds', 0.25)
    obj = bpy.data.objects[cover]
    ik(arm, side, (grab - 0.40) * fps, 0.0)
    ik(arm, side, (grab - 0.08) * fps, 1.0)
    _key_target(arm, side, (grab - 0.40) * fps)
    _key_target(arm, side, (grab - 0.03) * fps, edge_point(obj, grab * fps) + HAND_OFFSET)
    for frame in range(int(grab * fps), int(slam * fps) + 1):
        _key_target(arm, side, frame, edge_point(obj, frame) + HAND_OFFSET)
    press = bpy.data.objects[root].matrix_world @ Vector((0.117, 0.0, 0.018)) + HAND_OFFSET
    _key_target(arm, side, slam * fps + 2, press)
    _key_target(arm, side, hold_until * fps, press)
    ik(arm, side, hold_until * fps, 1.0)
