"""GNV-LPV-B2-001 THE ARCHIVE -- Goosnav Book 2. Monumental low-poly vignette (GLPV-001), 9:16.

An archivist at a single desk at the bottom of an endless archive logs obsolete media.
He puts down Goosnav Book 2. A voice from far down the aisle: "What does that one need?" "Eyes."
Adapted from AD 13 "THE ARCHIVE" (Goosnav 54 Video Ad Scripts) into the Giant Archive template.

  blender -b --factory-startup -P films/the_archive/film.py -- --format lpv [--preview] [--times ...]
"""
import sys, os, json, math
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa
from lowpoly import *   # noqa
from studio import config

FILM = 'the_archive'
FPS = 24
DUR = 23.0
WORK = str(config.path('work', FILM, FORMAT))
VO = str(config.path('work', FILM, 'vo'))
TEX = str(config.textures()); SRC = str(config.sources())
rng = np.random.default_rng(3); set_rng(rng)

# ---------------------------------------------------------------- timeline
T1, T2, T3, T4, T5, T_END = 0.0, 5.0, 13.9, 15.8, 17.7, 21.0
VO_AT = {'01': 5.3, '02': 8.3, '03': 11.3, '04': 16.0, '05': 18.0}
SPEAKER = {'01': 'ARCHIVIST', '02': 'ARCHIVIST', '03': 'ARCHIVIST', '04': 'ASSISTANT', '05': 'ARCHIVIST'}
ITEM_T = [(5.2, 7.6), (8.2, 10.6), (11.2, 13.4)]      # pick up -> into the tray
BOOK_T = (14.1, 15.3)                                  # book comes up from the drawer onto the desk
OPEN_T = 18.7
CUT_FRAMES = [round(x * FPS) for x in (T2, T3, T4, T5)]

scene = setup_scene(fps=FPS, samples=16, bloom=(0.9, 0.04, 5.0), look='AgX - Base Contrast')
fog_world(sky_top='#56616A', sky_horizon='#8A9496', strength=0.9, density=0.010, anisotropy=0.1)
scene.view_settings.exposure = 0.6

# ---------------------------------------------------------------- the archive
conc = mat('floor', PAL['concrete_dark'], 0.35, noise=0.2, noise_scale=0.08)
steel = mat('steel', '#5C6468', 0.5, 0.6)
box('floor', (60, 700, 0.2), conc, (0, 150, -0.1))
# shelf walls: posts, decks, and a backing of "boxes" (brick texture = rows of archive boxes)
def box_backing(name):
    m, nt, out = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); br = nt.nodes.new('ShaderNodeTexBrick')
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Color1'].default_value = (*hexrgb('#9C8265'), 1); br.inputs['Color2'].default_value = (*hexrgb('#B4AC99'), 1)
    br.inputs['Mortar'].default_value = (*hexrgb('#2A2622'), 1)
    br.inputs['Mortar Size'].default_value = 0.04; br.offset = 0.0; br.squash = 1.0
    br.inputs['Brick Width'].default_value = 0.42; br.inputs['Row Height'].default_value = 0.5
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    nt.links.new(tc.outputs['Object'], mp.inputs[0]); nt.links.new(mp.outputs[0], br.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.inputs['Roughness'].default_value = 0.9
    nt.links.new(br.outputs['Color'], b.inputs['Base Color']); nt.links.new(b.outputs[0], out.inputs[0])
    return m
backing = box_backing('boxes')
AISLE = 3.2
SHELF_H = 62.0
for sx in (-1, 1):
    x = sx * (AISLE + 0.7)
    wall = box(f'backing{sx}', (1.2, 620, SHELF_H), backing, (x + sx * 0.1, 160, SHELF_H / 2))
    wall.data.materials[0] = backing
    for lvl in np.arange(0.0, SHELF_H, 2.0):
        box(f'deck{sx}_{lvl}', (1.6, 620, 0.05), steel, (x - sx * 0.1, 160, lvl + 0.02))
    for y in np.arange(-150, 470, 4.0):
        box(f'post{sx}_{y}', (0.08, 0.08, SHELF_H), steel, (x - sx * 0.85, y, SHELF_H / 2))
# ceiling light rows
lightm = mat('tube', '#E8F0F2', 0.3, emit=6.0)
for y in np.arange(-40, 470, 12.0):
    box(f'tube_{y}', (0.25, 5.0, 0.12), lightm, (0, y, SHELF_H + 2.5))
for y in (-20, 30, 90, 160):
    area(f'aisle_light_{y}', (0, y, SHELF_H), 30, 40000, '#DDE8EE')
for y in (-60, -8, 12, 40, 80):
    area(f'low_fill_{y}', (0, y, 14), 6, 2500, '#D8E2E8', (0, 0, 0))
# a rolling ladder with the assistant, far down the aisle (behind the camera side = -Y)
ladder_m = mat('ladder', PAL['utility_yellow'], 0.6)
LAD_Y = -48.0
for sx in (-1, 1):
    box(f'rail{sx}', (0.06, 0.06, 14), ladder_m, (-AISLE + 0.9 + sx * 0.3, LAD_Y, 7), None)
for z in np.arange(0.5, 14, 0.5):
    box(f'rung{z}', (0.62, 0.05, 0.04), ladder_m, (-AISLE + 0.9, LAD_Y, z))
assistant = Human('assistant', skin=SKIN[0], top='#6E7F87', legs='#3A3F44', hair='#6B4B2E', hair_style='long')
assistant.place((-AISLE + 0.9, LAD_Y + 0.3, 9.0), yaw=math.pi)
point('ladder_pool', (-AISLE + 1.6, LAD_Y + 1.5, 11.5), 3500, '#FFE2B0', 0.3)

# ---------------------------------------------------------------- the desk
wood = mat('desk', '#6B5A48', 0.55)
desk_top_z = 0.76
box('desk_top', (1.6, 0.8, 0.05), wood, (0, 0, desk_top_z - 0.025))
box('desk_ped', (0.45, 0.72, desk_top_z - 0.05), wood, (-0.55, 0, (desk_top_z - 0.05) / 2))
box('desk_ped2', (0.45, 0.72, desk_top_z - 0.05), wood, (0.55, 0, (desk_top_z - 0.05) / 2))
green = mat('lampshade', '#2F5A3C', 0.4)
cyl('lamp_base', 0.07, 0.02, mat('brass', '#8A7440', 0.35, 0.8), 10, (0.58, 0.18, desk_top_z + 0.01))
cyl('lamp_stem', 0.012, 0.36, mat('brass2', '#8A7440', 0.35, 0.8), 6, (0.58, 0.18, desk_top_z + 0.19))
box('lamp_shade', (0.3, 0.14, 0.08), green, (0.5, 0.12, desk_top_z + 0.38))
point('lamp', (0.46, 0.08, desk_top_z + 0.3), 55, '#FFD9A0', 0.05)
chair_m = mat('chair', '#2E3338', 0.6)
box('chair_seat', (0.46, 0.44, 0.06), chair_m, (0, 0.62, 0.46))
box('chair_back', (0.46, 0.06, 0.5), chair_m, (0, 0.86, 0.74))
tray_m = mat('tray', '#C8C2B0', 0.6)
TRAY = v3(-0.55, 0.05, desk_top_z)
box('tray_base', (0.34, 0.26, 0.012), tray_m, tuple(TRAY + v3(0, 0, 0.006)))
for dx, dy, sz in ((0.17, 0, (0.012, 0.26, 0.07)), (-0.17, 0, (0.012, 0.26, 0.07)), (0, 0.13, (0.34, 0.012, 0.07)), (0, -0.13, (0.34, 0.012, 0.07))):
    box(f'tray_w{dx}{dy}', sz, tray_m, tuple(TRAY + v3(dx, dy, 0.035)))

# media: floppy, CD, phone (no brands)
floppy = box('floppy', (0.09, 0.093, 0.004), mat('floppy', '#3C4A5A', 0.4))
box('floppy_label', (0.07, 0.035, 0.001), mat('flabel', '#E6E2D6', 0.8), (0, 0.022, 0.0025), floppy)
cd = cyl('cd', 0.06, 0.0015, mat('cd', '#C9CDD2', 0.15, 0.9), 16)
phone = box('phone', (0.05, 0.11, 0.022), mat('phone', '#2B2D30', 0.4))
box('phone_screen', (0.04, 0.045, 0.001), mat('pscreen', '#6E8C7A', 0.2), (0, 0.022, 0.0115), phone)
ITEMS = [floppy, cd, phone]
ITEM_HOME = [v3(-0.05, -0.12, desk_top_z + 0.004), v3(0.13, -0.14, desk_top_z + 0.002), v3(0.3, -0.1, desk_top_z + 0.011)]
ITEM_TRAY = [TRAY + v3(0.02, 0.02, 0.02), TRAY + v3(-0.03, -0.02, 0.03), TRAY + v3(0.0, 0.0, 0.05)]

# Book 2 (generic, closed) and an open copy for the reading shot (real drawing sheets on the pages)
book = product_book('book2', 1.0, TEX)
BOOK_HOME = v3(0.02, -0.14, desk_top_z)
openbook = empty('openbook')
board = mat('ob_board', PAL['book2'], 0.55)
paper = mat('ob_paper', '#EEE9DC', 0.9)
for side, sx in (('L', -1), ('R', 1)):
    hinge = empty(f'ob_hinge{side}', (0, 0, 0), openbook)
    box(f'ob_board{side}', (0.28, 0.215, 0.004), board, (sx * 0.14, 0, 0.002), hinge)
    pg = tex_mat(f'ob_page{side}', os.path.join(TEX, 'page_00.png' if side == 'L' else 'page_04.png'), 0.9, 512, 0.1)
    make_box(f'ob_pages{side}', (0.27, 0.205, 0.012), {(0, 0, 1): pg}, paper).parent = hinge
    bpy.data.objects[f'ob_pages{side}'].location = (sx * 0.138, 0, 0.01)
    hinge.rotation_euler = (0, sx * -0.06, 0)

# ---------------------------------------------------------------- the archivist
arch = Human('archivist', skin=SKIN[1], top='#5E646A', legs='#33373B', hair='#9A9590', glasses=False,
             jacket='#4E5A62', hair_style='short')
arch.place((0, 0.6, 0), yaw=0.0)

lines = Lines([(SPEAKER[k], t, os.path.join(VO, f'vo_{k}.wav')) for k, t in VO_AT.items()], FPS)

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def set_items(t):
    for i, ob in enumerate(ITEMS):
        a, b = ITEM_T[i]
        u = ease((t - (a + 0.6)) / (b - a - 0.8))
        p = lerp(ITEM_HOME[i], ITEM_TRAY[i], u) + v3(0, 0, 0.18 * math.sin(math.pi * u))
        ob.location = tuple(p)
        ob.rotation_euler = (0, 0, 0.3 * i + 0.4 * u)
    # book
    if t < BOOK_T[0]:
        book.location = tuple(HIDE)
    elif t < OPEN_T:
        u = ease((t - BOOK_T[0]) / (BOOK_T[1] - BOOK_T[0]))
        p = lerp(v3(0.35, 0.1, desk_top_z - 0.3), BOOK_HOME, u) + v3(0, 0, 0.12 * math.sin(math.pi * u))
        book.location = tuple(p); book.rotation_euler = (0, 0, 0.25 * (1 - u))
    else:
        book.location = tuple(HIDE)
    if t >= OPEN_T:
        u = ease((t - OPEN_T) / 0.5)
        openbook.location = (0.02, -0.1, desk_top_z + 0.004)
        openbook.rotation_euler = (0, 0, math.pi)     # page tops away from the reader at +Y
        for side, sx in (('L', -1), ('R', 1)):
            bpy.data.objects[f'ob_hinge{side}'].rotation_euler = (0, sx * lerp(-2.9, -0.06, u) if side == 'L' else sx * -0.06, 0)
    else:
        openbook.location = tuple(HIDE)

def set_archivist(t):
    tc = on_twos(t)
    arch.pose(POSES['desk'])
    arch.sit_height(0.49)
    # reaching for items / book
    reach = 0.0
    for a, b in ITEM_T + [BOOK_T]:
        if a <= tc <= b:
            reach = math.sin(math.pi * (tc - a) / (b - a))
    arch.add({'uarm_R': (-0.55 * reach, 0, -0.1 * reach), 'farm_R': (0.35 * reach, 0, 0), 'spine': (0.08 * reach, 0, -0.05 * reach)})
    if tc >= OPEN_T:
        arch.pose(POSES['lean_in'], w=min(1, (tc - OPEN_T) / 0.5), base=POSES['desk']); arch.sit_height(0.49)
        arch.add({'thigh_L': (-1.5, 0, 0.05), 'thigh_R': (-1.5, 0, -0.05), 'shin_L': (1.5, 0, 0), 'shin_R': (1.5, 0, 0), 'head': (0.35, 0, 0)})
    # glance at each item while he names it; look up the aisle at the voice
    if T4 <= tc < T5 + 0.4:
        arch.look(yaw=0.15, pitch=-0.25)
    elif tc < OPEN_T:
        arch.look(yaw=0.0, pitch=0.28)
    arch.idle(tc, 0.6)
    arch.blink(t, 1)
    arch.talk(lines.amount('ARCHIVIST', t))
    # the assistant, tiny, far away on the ladder
    assistant.pose({'uarm_L': (-2.6, 0, 0.2), 'uarm_R': (-1.2, 0, -0.2), 'thigh_L': (-0.6, 0, 0), 'shin_L': (0.9, 0, 0)})
    assistant.talk(lines.amount('ASSISTANT', t))

cam, cam_d = make_camera(clip_end=1500)

def camera_at(t):
    if t < T2:   # the monumental wide: tiny desk at the foot of the aisle
        u = t / T2
        return lerp(v3(0.4, -24.0, 1.5), v3(0.3, -20.5, 1.5), u), v3(0, 25, 10.0), 17.0, 0.0
    if t < T3:   # medium over the desk
        u = (t - T2) / (T3 - T2)
        return lerp(v3(0.25, -2.35, 1.38), v3(0.15, -2.1, 1.36), u), v3(0.0, 0.3, 0.98), 30.0, 0.0
    if t < T4:   # insert: the book arrives
        return v3(0.42, -1.05, 1.22), v3(0.04, -0.12, 0.8), 42.0, 0.0
    if t < T5:   # reverse: past his shoulder, down the aisle, to the voice on the ladder
        u = (t - T4) / (T5 - T4)
        return lerp(v3(0.75, 2.1, 1.6), v3(0.7, 1.9, 1.6), u), v3(-AISLE + 0.9, LAD_Y, 8.0), 30.0, 0.0
    u = (t - T5) / (T_END - T5)   # "Eyes." then over his shoulder onto the open book
    if t < OPEN_T:
        return v3(0.1, -1.9, 1.22), v3(0.0, 0.5, 1.2), 36.0, 0.0
    return lerp(v3(-1.05, 0.75, 2.1), v3(-0.92, 0.65, 2.0), u), v3(0.02, -0.12, 0.78), 30.0, 0.0

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_items(t); set_archivist(t)
    return t >= T_END

def events():
    os.makedirs(WORK, exist_ok=True)
    json.dump({'VO_AT': VO_AT, 'SPEAKER': SPEAKER, 'ITEM_T': ITEM_T, 'BOOK_T': BOOK_T, 'OPEN_T': OPEN_T,
               'cuts': [T2, T3, T4, T5], 'end': T_END, 'dur': DUR}, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
