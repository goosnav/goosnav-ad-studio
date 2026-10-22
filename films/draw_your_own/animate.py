"""DRAW YOUR OWN: perform the scene on the measured audio.

blender -b BLOCKING.blend --python-exit-code 1 --python films/draw_your_own/animate.py -- \
    films/draw_your_own/cut.json WORKDIR OUT.blend

Order matters: the book is retimed first, then the hand-authored acting (leans, IK
page turns, the slam) is keyed on the rigs, then blender/performance.py composes the
library idle, gaze, talk motion, blinks and measured mouths around those authored
channels without overwriting them.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / 'assets/goosnav-3D-assets'
sys.path.insert(0, str(REPO / 'blender'))
import book2  # noqa: E402
import performance  # noqa: E402
import shots  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
CUT = json.loads(Path(args[0]).read_text())
WORK = Path(args[1]).expanduser()
OUT = Path(args[2])
FPS = CUT['fps']
FRAMES = math.ceil(CUT['duration'] * FPS)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 0, FRAMES - 1
book = bpy.data.objects['Book2_Root']
READER, PAL = bpy.data.objects['READER'], bpy.data.objects['PAL']
TURN = 0.5           # seconds for a hand-flicked leaf
CLOSE = 0.25         # seconds for the slam


def f(seconds):
    return seconds * FPS


def event(name, leaf=None):
    return next(e['at'] for e in CUT['events'] if e['name'] == name and (leaf is None or e.get('leaf') == leaf))


def line(line_id):
    l = next(l for l in CUT['lines'] if l['id'] == line_id)
    return l['start']


LEAF = CUT['book']['turn_leaf']
TURN_AT, SLAM = event('page_turn', LEAF), event('slam')


# --------------------------------------------------------------- body acting
def body_curve(arm, keys):
    """keys: {bone: [(seconds, (x, y, z) radians), ...]} with smooth interpolation, plus breath."""
    for bone, points in keys.items():
        pb = arm.pose.bones[bone]
        base = Vector(pb.rotation_euler)
        for t, rot in points:
            pb.rotation_euler = base + Vector(rot)
            pb.keyframe_insert('rotation_euler', frame=f(t))
    action = arm.animation_data.action
    for fc in action.fcurves:
        if fc.data_path.endswith('rotation_euler') and 'chest' in fc.data_path and fc.array_index == 0:
            # Slow breathing so authored channels never freeze.
            mod = fc.modifiers.new('NOISE')
            mod.scale, mod.strength, mod.phase = 40, 0.03, hash(arm.name) % 7


def reader_acting():
    READER.animation_data_create()
    # Gentle: gaze pitch adds ~14 degrees, and the face must still read on camera.
    read = (0.03, 0.0, 0.0)
    keys = {
        'spine': [(0, read), (SLAM - 0.6, read), (SLAM - 0.2, (0.10, 0, 0)), (SLAM + 0.45, (0.0, 0, 0))],
        'chest': [(0, (0.04, 0, 0)), (SLAM - 0.6, (0.04, 0, 0)), (SLAM - 0.2, (0.12, 0.05, 0)),
                  (line('r3') - 0.1, (0.0, 0.10, 0)), (CUT['end_card']['start'], (0.0, 0.12, 0))],
        'neck': [(0, (0.06, 0, 0)), (line('r3') - 0.3, (0.06, 0, 0)), (line('r3'), (-0.02, 0.12, 0)),
                 (CUT['end_card']['start'], (-0.02, 0.12, 0))],
    }
    body_curve(READER, keys)
    book2.turn_page_by_hand(READER, 'R', LEAF, TURN_AT)
    book2.slam_by_hand(READER, 'R', SLAM, hold_until=CUT['end_card']['start'] + 30 / FPS)


def pal_acting():
    PAL.animation_data_create()
    lean_in, lean_far = line('p1') - 0.35, line('p2') - 0.55
    keys = {
        'spine': [(0, (0.02, 0, 0)), (lean_in, (0.02, 0, 0)), (lean_in + 0.35, (0.09, 0, 0)),
                  (line('r2'), (0.06, 0, 0)), (lean_far, (0.06, 0, 0)), (lean_far + 0.5, (0.20, 0, -0.06)),
                  (SLAM, (0.20, 0, -0.06)), (SLAM + 0.12, (-0.05, 0, 0.02)), (SLAM + 0.6, (0.01, 0, 0))],
        'chest': [(0, (0.02, 0, 0)), (lean_in, (0.02, 0, 0)), (lean_in + 0.35, (0.10, -0.05, 0)),
                  (line('r2'), (0.06, -0.03, 0)), (lean_far, (0.06, -0.03, 0)),
                  (lean_far + 0.5, (0.18, -0.12, -0.05)), (SLAM, (0.18, -0.12, -0.05)),
                  (SLAM + 0.12, (-0.06, 0, 0.02)), (SLAM + 0.6, (0.0, -0.02, 0))],
    }
    body_curve(PAL, keys)
    # The desk hides his feet, so the whole body can slide in toward the book.
    home, turn = PAL.location.copy(), PAL.rotation_euler.z
    toward = (book.matrix_world.translation - home)
    toward.z = 0
    toward = toward.normalized()
    for t, push, spin in ((0, 0, 0), (lean_in, 0, 0), (lean_in + 0.3, 0.05, -0.08), (line('r2'), 0.03, -0.05),
                          (lean_far, 0.03, -0.05), (lean_far + 0.45, 0.19, -0.30), (SLAM, 0.19, -0.30),
                          (SLAM + 0.10, 0.07, -0.18), (SLAM + 0.5, 0.09, -0.20)):
        PAL.location = home + toward * push
        PAL.rotation_euler.z = turn + spin
        PAL.keyframe_insert('location', frame=f(t))
        PAL.keyframe_insert('rotation_euler', frame=f(t))
    PAL.location, PAL.rotation_euler.z = home, turn


def page_point():
    return list(book.matrix_world @ Vector((0.0, 0.0, 0.02)))


def cues():
    end = CUT['duration']
    stop = CUT['end_card']['start']
    r6 = line('r3')
    p3 = line('p2')
    return [
        {'speaker': 'READER', 'kind': 'talk', 'start': 0, 'end': end, 'intensity': 0.45},
        {'speaker': 'PAL', 'kind': 'talk', 'start': 0, 'end': end, 'intensity': 0.7},
        {'speaker': 'READER', 'kind': 'look_at', 'start': 0, 'end': r6 - 0.25, 'target': page_point()},
        {'speaker': 'READER', 'kind': 'look_at', 'start': r6 - 0.25, 'end': end, 'target': 'PAL'},
        {'speaker': 'PAL', 'kind': 'look_at', 'start': 0, 'end': p3 - 0.6, 'target': 'READER'},
        {'speaker': 'PAL', 'kind': 'look_at', 'start': p3 - 0.6, 'end': SLAM + 0.1, 'target': page_point()},
        {'speaker': 'PAL', 'kind': 'look_at', 'start': SLAM + 0.1, 'end': stop, 'target': 'READER'},
    ]


# --------------------------------------------------------------- cameras/cuts
BODY_PARTS = ('head', 'nose', 'eye', 'pupil', 'torso', 'pelvis', 'leg', 'foot')


def cut_cameras():
    scene.timeline_markers.clear()
    hidden = [o for o in bpy.data.objects if o.parent == READER and o.type == 'MESH'
              and any(p in o.name.split('_', 1)[-1] for p in BODY_PARTS)]
    for o in hidden:
        o.hide_render = False
        o.keyframe_insert('hide_render', frame=0)
    for shot in CUT['shots']:
        a = round(f(shot['start']))
        marker = scene.timeline_markers.new(shot['camera'], frame=a)
        marker.camera = bpy.data.objects[shot['camera']]
        for o in hidden:
            o.hide_render = bool(shot.get('hide_reader_body'))
            o.keyframe_insert('hide_render', frame=a)
    for o in hidden:
        for fc in o.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'
    # Slow push on the wide so both visits to it breathe.
    wide = bpy.data.objects['CAM_wide']
    start = wide.location.copy()
    wide.keyframe_insert('location', frame=0)
    wide.location = start + (Vector((-5.4, 11.5, -6.0)).normalized() * 1.6)
    wide.keyframe_insert('location', frame=FRAMES - 1)
    for fc in wide.animation_data.action.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = 'LINEAR'
    # The two-shot camera takes the slam.
    two = bpy.data.objects['CAM_two']
    base = two.location.copy()
    hit = f(SLAM)
    for dt, off in ((-1, (0, 0, 0)), (1, (0.012, 0, -0.016)), (2, (-0.008, 0, 0.01)), (3, (0.004, 0, -0.004)),
                    (5, (0, 0, 0))):
        two.location = base + Vector(off)
        two.keyframe_insert('location', frame=hit + dt)
    two.location = base


def page_light():
    data = bpy.data.lights.new('Page light', 'AREA')
    data.energy, data.size, data.color = 4.0, 0.35, (1.0, 0.93, 0.82)
    light = bpy.data.objects.new('Page light', data)
    scene.collection.objects.link(light)
    m = book.matrix_world
    centre = m @ Vector((0, 0, 0.02))
    normal = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
    light.location = centre + normal * 0.45 + Vector((0.1, 0, 0.1))
    light.rotation_euler = (centre - light.location).to_track_quat('-Z', 'Y').to_euler()


def main():
    book2.retime(open_through=CUT['book']['open_through'], turns={LEAF: TURN_AT}, slam=SLAM,
                 turn_seconds=TURN, close_seconds=CLOSE, frames=FRAMES)
    reader_acting()
    pal_acting()
    scene.frame_set(0)
    rigs = {'READER': 'READER', 'PAL': 'PAL'}
    models = {'READER': str(LIB / 'characters/ps1guy_v10.blend'),
              'PAL': str(LIB / 'characters/ps1guy_v10_beady.blend')}
    audio = WORK / 'audio'
    report = performance.apply(str(audio / 'timeline.json'), str(audio / 'mouths.json'), rigs,
                               models=models, cues=cues(), library_root=str(LIB))
    # The book's point of view: the Pal looms in, nose first.
    shots.face_camera('CAM_pal_lean', PAL, line('p2') + 0.3, distance=0.74, lens=34, swing=0.6, lift=0.0)
    cut_cameras()
    page_light()
    scene.frame_set(0)
    (WORK / 'performance_report.json').write_text(json.dumps(report, indent=2))
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
    print('ANIMATED', OUT, json.dumps(report)[:400])


main()
