"""DRAW YOUR OWN: build the set, cast, book and cameras for the Book Two ad.

blender -b --python-exit-code 1 --python films/draw_your_own/scene.py -- OUT.blend [--boards DIR]

The vaulted reading room is built at roughly 2.2x human scale; scaling it to 0.4
turns its 2 m desks into 0.8 m standing desks while the hall stays immense.
Everything here is placement and lighting; animation is added by animate.py.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
LIB = Path(__file__).resolve().parents[2] / 'assets/goosnav-3D-assets'
HALL_SCALE = 0.4
# Reading_table at (-11, -18) in hall units; its long axis runs along X.
TABLE = Vector((-11.0, -18.0, 2.0)) * HALL_SCALE
TABLE_TOP = (2.0 + 0.15) * HALL_SCALE + 0.001   # slab centre 2.0, 0.3 thick
TABLE_HALF_DEPTH = 2.0 * HALL_SCALE
READER_X, PAL_X = TABLE.x - 0.52, TABLE.x + 0.16
ACTOR_Y = TABLE.y + TABLE_HALF_DEPTH + 0.27
NATIVE = (540, 675)

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = Path(args[0]) if args else HERE / 'scene.blend'
BOARDS = Path(args[args.index('--boards') + 1]) if '--boards' in args else None


def append(path, names):
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        missing = set(names) - set(src.collections)
        if missing:
            raise SystemExit(f'{path} lacks collections {sorted(missing)}')
        dst.collections = list(names)
    for coll in dst.collections:
        bpy.context.scene.collection.children.link(coll)
    return dst.collections


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = 'BLENDER_EEVEE'
    s.render.fps = 24
    s.render.resolution_x, s.render.resolution_y = NATIVE
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.view_settings.view_transform = 'Filmic'
    s.view_settings.look = 'Medium High Contrast'
    s.view_settings.exposure = 0.55
    e = s.eevee
    e.taa_render_samples = 32
    e.use_gtao = True
    e.gtao_distance = 1.2
    e.use_soft_shadows = True
    e.shadow_cube_size = '1024'
    e.shadow_cascade_size = '2048'
    e.use_bloom = True
    e.bloom_intensity = 0.03
    e.bloom_threshold = 1.2
    e.use_motion_blur = False   # PLAYBOOK: motion blur smears hard cuts.
    world = bpy.data.worlds.new('Hall air')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.014, 0.018, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    s.world = world
    return s


def build_hall():
    colls = append(LIB / 'environments/reading-room/scene.blend',
                   ['Architecture', 'Book_galleries', 'Reading_furniture', 'Distant_dais',
                    'Animated', 'Lighting'])
    root = bpy.data.objects.new('Hall_root', None)
    bpy.context.scene.collection.objects.link(root)
    root.scale = (HALL_SCALE,) * 3
    for coll in colls:
        for obj in coll.all_objects:
            if obj.parent is None:
                obj.parent = root
            if obj.type == 'LIGHT':
                # Inverse-square: shrinking distances by S brightens by 1/S^2.
                obj.data.energy *= HALL_SCALE ** 2 * (0.55 if obj.data.type == 'AREA' else 0.8)
                if obj.data.type == 'SUN':
                    obj.data.energy = 0.35
    bpy.context.view_layer.update()
    # Clear standing room behind our desk: chairs on its far side near the actors.
    doomed = [o for o in colls[2].all_objects if o.name.startswith('Chair')
              and abs((o.matrix_world.translation.y) - (TABLE.y + 2.7 * HALL_SCALE)) < 0.6
              and TABLE.x - 1.6 < o.matrix_world.translation.x < TABLE.x + 1.6]
    # Our desk keeps one green lamp, screen-left of the pair; its other lamps and
    # generic open volumes would block the two-shot or compete with Book Two.
    for o in colls[2].all_objects:
        loc = o.matrix_world.translation
        on_desk = abs(loc.y - TABLE.y) < TABLE_HALF_DEPTH + 0.1 and abs(loc.x - TABLE.x) < 1.9
        if on_desk and (o.name.startswith('Open_volume') or (
                o.name.startswith(('Green_shade', 'Lamp_stem', 'Desk_light')) and loc.x > TABLE.x - 0.8)):
            doomed.append(o)
    for o in set(doomed):
        bpy.data.objects.remove(o)
    # Crunchy early-3D texture sampling on the hall's 128 px patterns.
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    node.interpolation = 'Closest'
    return root


def place_book():
    """Book Two, open at pages 8|9, on the library's slanted book rest in front of the reader."""
    append(LIB / 'props/hq/book2_goosnav_dilemma_openable_v2.blend', ['Book Two — openable v2'])  # actual interior
    append(LIB / 'props/ps1/library_book_rest.blend', ['Library book rest'])
    rest = bpy.data.objects['Library_book_rest']
    rest_angle = rest['slope_radians']
    rest.location = (READER_X, TABLE.y + TABLE_HALF_DEPTH - 0.16, TABLE_TOP)
    # The rest slopes up toward -Y (away from the reader at +Y).
    rest.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()   # matrix_world is stale until the depsgraph runs
    root = bpy.data.objects['Book2_Root']
    # Book local +X is the right-hand page, +Y the page top. The reader faces -Y,
    # so his right is world -X: turn the book 180 degrees, then lie it on the slope.
    slope = Matrix.Rotation(-rest_angle, 4, 'X')
    turn = Matrix.Rotation(math.pi, 4, 'Z')
    # Book2_Root is the spine's centre on the book's underside. The prop records the
    # lift that clears the opened cover (it hinges ~1 cm below the base).
    seat = Matrix.Translation((0, 0.0, rest['book2_seat_height']))
    root.matrix_world = rest.matrix_world @ seat @ turn @ slope.inverted()
    return root, rest


def actors():
    reader = append(LIB / 'characters/ps1guy_v10.blend', ['Character_v10_plate'])[0]
    pal = append(LIB / 'characters/ps1guy_v10_beady.blend', ['Character_v10_beady'])[0]
    r = next(o for o in reader.all_objects if o.type == 'ARMATURE')
    p = next(o for o in pal.all_objects if o.type == 'ARMATURE')
    r.name, p.name = 'READER', 'PAL'
    r.location = (READER_X, ACTOR_Y, 0)
    p.location = (PAL_X, ACTOR_Y + 0.05, 0)
    p.rotation_euler = (0, 0, math.radians(-28))   # turned toward the reader and his book
    r.rotation_euler = (0, 0, math.radians(4))
    return r, p


def lamp_pool():
    """A warm pool from the desk's green banker's lamp; the hall stays cool and dim."""
    lamps = [o for o in bpy.data.objects if o.name.startswith('Green_shade')]
    near = min(lamps, key=lambda o: (o.matrix_world.translation - Vector((READER_X, TABLE.y, 1))).length)
    pos = near.matrix_world.translation
    key = bpy.data.lights.new('Lamp pool', 'SPOT')
    key.energy, key.color = 55, (1.0, 0.78, 0.48)
    key.spot_size, key.spot_blend, key.shadow_soft_size = math.radians(115), 0.6, 0.05
    obj = bpy.data.objects.new('Lamp pool', key)
    obj.location = pos + Vector((0, 0, -0.05))
    obj.rotation_euler = (0, 0, 0)
    bpy.context.scene.collection.objects.link(obj)
    bounce = bpy.data.lights.new('Face fill', 'AREA')
    bounce.energy, bounce.size, bounce.color = 14, 1.2, (1.0, 0.86, 0.66)
    f = bpy.data.objects.new('Face fill', bounce)
    f.location = (READER_X + 0.2, TABLE.y - 0.2, TABLE_TOP + 0.05)
    f.rotation_euler = Euler((math.radians(-112), 0, 0))
    bpy.context.scene.collection.objects.link(f)
    face = bpy.data.lights.new('Lamp key', 'AREA')
    face.energy, face.size, face.color = 38, 0.6, (1.0, 0.80, 0.56)
    k = bpy.data.objects.new('Lamp key', face)
    k.location = (READER_X - 0.75, TABLE.y - 0.15, 1.95)
    k.rotation_euler = (Vector((READER_X + 0.3, ACTOR_Y, 1.4)) - k.location).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(k)
    rim = bpy.data.lights.new('Hall rim', 'AREA')
    rim.energy, rim.size, rim.color = 60, 3, (0.62, 0.74, 1.0)
    r = bpy.data.objects.new('Hall rim', rim)
    r.location = (READER_X + 0.3, ACTOR_Y + 2.6, 3.2)
    r.rotation_euler = Euler((math.radians(-52), 0, math.radians(180)))
    bpy.context.scene.collection.objects.link(r)
    return obj


def camera(name, loc, target, lens):
    data = bpy.data.cameras.new(name)
    data.lens, data.sensor_fit, data.sensor_width = lens, 'VERTICAL', 24
    data.clip_start, data.clip_end = 0.02, 400
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    direction = Vector(target) - Vector(loc)
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return obj


def page_camera(name, book, side, distance=0.42, lens=44):
    # Outside the 0.23 m arc a turning leaf sweeps, so the flip passes the lens cleanly.
    """Square to one page, looking along its normal: the insert shows real art large."""
    m = book.matrix_world
    centre = m @ Vector((0.117 * side, 0.004, 0.016))
    normal = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
    up = (m.to_3x3() @ Vector((0, 1, 0)))
    up = (up - normal * up.dot(normal)).normalized()
    cam = camera(name, centre + normal * distance, centre, lens)
    cam.matrix_world = Matrix.Translation(cam.location) @ Matrix(
        [up.cross(normal), up, normal]).transposed().to_4x4()
    return cam


def cameras(book):
    rh = Vector((READER_X, ACTOR_Y - 0.06, 1.52))
    ph = Vector((PAL_X - 0.06, ACTOR_Y, 1.52))
    bpy.context.view_layer.update()
    return {
        'CAM_wide': camera('CAM_wide', (TABLE.x + 5.4, TABLE.y - 11.5, 7.4),
                           (TABLE.x + 0.4, TABLE.y + 1.2, 0.9), 30),
        # Front-right three-quarter: both long noses read in profile, never end-on.
        'CAM_two': camera('CAM_two', (TABLE.x + 0.80, TABLE.y - 0.92, 1.55),
                          (TABLE.x - 0.22, ACTOR_Y, 1.24), 30),
        # Tight close-ups: the faces fill the frame (the owner finds these funny).
        'CAM_reader': camera('CAM_reader', (READER_X - 0.40, ACTOR_Y - 1.02, 1.44), rh, 50),
        'CAM_pal': camera('CAM_pal', (PAL_X + 0.48, ACTOR_Y - 0.98, 1.45), ph, 50),
        # From the reader's side, so the Pal's nose comes at the lens as he leans in.
        'CAM_pal_ecu': camera('CAM_pal_ecu', (PAL_X - 0.34, ACTOR_Y - 0.82, 1.57),
                              ph + Vector((0.0, 0.0, 0.05)), 45),
        'CAM_insert_L': page_camera('CAM_insert_L', book, -1),
        'CAM_insert_R': page_camera('CAM_insert_R', book, 1),
    }


def main():
    scene = reset()
    build_hall()
    reader, pal = actors()
    book, rest = place_book()
    lamp_pool()
    cams = cameras(book)
    scene.camera = cams['CAM_two']
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
    if BOARDS:
        BOARDS.mkdir(parents=True, exist_ok=True)
        # Show the opening spread for the boards: pages 8|9.
        scene.frame_set(233)   # demo action: spread 8|9 open
        for name, cam in cams.items():
            scene.camera = cam
            scene.render.filepath = str(BOARDS / f'{name}.png')
            bpy.ops.render.render(write_still=True)


main()
