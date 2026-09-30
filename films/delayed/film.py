"""GNV-LPV-GK-001 DELAYED -- Goosklerf. Monumental low-poly vignette, 9:16.

A vast, empty departure hall. "Flight two seventy one is delayed. Another two hours."
"You brought it?" "Yeah." Goosklerf on a suitcase. "Now boarding." "Finish the turn."
Through the glass, the plane leaves without them.
Adapted from AD 39 "AIRPORT" into the bible's BUS TERMINAL / GAME CONSEQUENCE patterns (§23, §37.10).
"""
import sys, os, json, math
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa
from lowpoly import *   # noqa
from studio import config

FILM = 'delayed'
FPS = 24
DUR = 23.0
WORK = str(config.path('work', FILM, FORMAT))
VO = str(config.path('work', FILM, 'vo'))
TEX = str(config.textures()); SRC = str(config.sources())
rng = np.random.default_rng(9); set_rng(rng)

T2, T3, T4, T5, T_END = 5.6, 9.0, 13.4, 18.5, 21.0
VO_AT = {'01': 0.8, '02': 6.2, '03': 6.95, '04': 13.8, '05': 17.35}
SPEAKER = {'01': 'PA', '02': 'A', '03': 'B', '04': 'PA', '05': 'A'}
BOX_T = (7.3, 8.5)                       # box out of the bag onto the suitcase
DEAL = [9.4, 9.9, 10.4, 10.9]            # cards slap down
DICE_T = 11.6                            # two dice rolled
PLAY_T = [14.4, 15.7]                    # cards played during boarding
PLANE_T = (16.3, 23.0)                   # plane taxis away
CUT_FRAMES = [round(x * FPS) for x in (T2, T3, T4, T5)]

scene = setup_scene(fps=FPS, samples=16, bloom=(0.9, 0.05, 6.0), look='AgX - Base Contrast')
fog_world(sky_top='#44525F', sky_horizon='#9A8C7A', strength=1.0, density=0.0007, anisotropy=0.1)
scene.view_settings.exposure = 0.2
sun(2.6, '#FFE3C4', elev=14, azim=160, angle=4)      # low dusk sun through the glass
for fx in (-30, 0, 30):   # apron floodlights on the parked aircraft
    area(f'flood{fx}', (fx, 41.0, 16), 18, 30000, '#F3EBDD', (math.radians(60), 0, 0))

# ---------------------------------------------------------------- the hall
floor_m = mat('terrazzo', '#B4AC99', 0.3, noise=0.12, noise_scale=0.6)
box('hall_floor', (140, 90, 0.2), floor_m, (0, -10, -0.1))
ceil_m = mat('ceiling', PAL['concrete'], 0.9, noise=0.1, noise_scale=0.05)
box('hall_ceiling', (140, 90, 1.0), ceil_m, (0, -10, 32.5))
box('hall_back', (140, 1.0, 33), ceil_m, (0, -55, 16.5))
for sx in (-1, 1):
    box(f'hall_side{sx}', (1.0, 90, 33), ceil_m, (sx * 70, -10, 16.5))
skym = mat('skylight', '#EDEFEF', 0.3, emit=3.5)
for x in np.arange(-60, 61, 15.0):
    box(f'skylight{x}', (1.2, 80, 0.2), skym, (x, -10, 31.9))
# the glass wall at y = +35 with a mullion grid
mull = mat('mullion', '#41464A', 0.4, 0.6)
GY = 35.0
for x in np.arange(-70, 71, 7.0):
    box(f'mull_v{x}', (0.18, 0.3, 32), mull, (x, GY, 16))
for z in np.arange(0, 33, 8.0):
    box(f'mull_h{z}', (140, 0.3, 0.18), mull, (0, GY, z))
glass_m, nt, out = new_mat('glass')
gb = nt.nodes.new('ShaderNodeBsdfPrincipled'); gb.inputs['Roughness'].default_value = 0.05
gb.inputs['Alpha'].default_value = 0.08
nt.links.new(gb.outputs[0], out.inputs[0]); glass_m.blend_method = 'BLEND'; glass_m.shadow_method = 'NONE'
box('glass_wall', (140, 0.05, 32), glass_m, (0, GY + 0.1, 16))
# outside: apron, lines, a far terminal, and a generic airliner (no livery)
box('apron', (600, 400, 0.2), mat('asphalt', '#4A4C4B', 0.8, noise=0.1, noise_scale=0.02), (0, GY + 200, -0.15))
yl = mat('apron_line', PAL['utility_yellow'], 0.6)
box('lead_in', (0.4, 160, 0.02), yl, (-5, GY + 80, 0.0))
box('taxi_line', (400, 0.4, 0.02), yl, (0, GY + 95, 0.0))
white = mat('plane_white', '#E4E4DF', 0.45)
grey = mat('plane_grey', '#8E9396', 0.5)
plane = empty('plane')
fus = cyl('fuselage', 2.6, 44, white, 14, (0, 0, 4.6), plane, axis='Y')
ball('nose', 2.6, white, 14, 8, (0, -22, 4.6), (1, 1.5, 1), plane)
box('tailcone', (3.2, 6, 3.6), white, (0, 24, 5.4), plane)
box('fin', (0.5, 7, 9), white, (0, 24.5, 11), plane)
for sx in (-1, 1):
    wing = box(f'wing{sx}', (17, 5.5, 0.5), white, (sx * 9.5, 1.5, 3.2), plane)
    wing.rotation_euler = (0, 0, sx * 0.35)
    cyl(f'engine{sx}', 1.3, 4.2, grey, 12, (sx * 7.0, -1.5, 2.1), plane, axis='Y')
    box(f'stab{sx}', (6, 3, 0.35), white, (sx * 3.6, 24, 6.2), plane)
box('cheatline', (0.06, 44, 0.7), mat('cheat', '#2E3338', 0.4), (-2.6, 0, 5.3), plane)
box('cheatline2', (0.06, 44, 0.7), mat('cheat', '#2E3338', 0.4), (2.6, 0, 5.3), plane)
for i in range(18):
    box(f'win{i}', (0.05, 0.5, 0.35), mat('pwin', '#2A3036', 0.3), (-2.62, -16 + i * 2.0, 5.3), plane)
box('far_terminal', (180, 30, 16), mat('farterm', '#6F7577', 0.9), (40, GY + 260, 8))
PLANE_HOME = v3(6.0, GY + 22.0, 0.0)
plane.scale = (1.6, 1.6, 1.6)

# gate sign and seats
sign_png = paper_sign('gate_sign', ['*GATE 27', 'FLIGHT 271  -  DELAYED'], (768, 256), '#1D211F', '#E6C14A', WORK, 64)
sign = make_box('gate_sign', (3.0, 0.12, 1.0), {(0, -1, 0): tex_mat('gatesign', sign_png, 0.5, 768, 1.2)}, mat('signb', '#1D211F', 0.5))
sign.location = (-5.0, 18.0, 4.5)
cyl('sign_post', 0.08, 4.0, mat('post', '#41464A', 0.4, 0.6), 8, (-5.0, 18.0, 2.0))
seat_m = mat('seat', '#3F5964', 0.5); beam_m = mat('beam', '#5C6468', 0.4, 0.7)
def seat_row(name, x0, y, n, facing):
    box(f'{name}_beam', (n * 0.62, 0.08, 0.08), beam_m, (x0 + n * 0.31 - 0.31, y, 0.3))
    for i in range(n):
        x = x0 + i * 0.62
        box(f'{name}_s{i}', (0.54, 0.48, 0.07), seat_m, (x, y, 0.45))
        box(f'{name}_b{i}', (0.54, 0.07, 0.5), seat_m, (x, y + facing * 0.24, 0.72))
    for x in (x0, x0 + (n - 1) * 0.62):
        box(f'{name}_leg{x}', (0.06, 0.3, 0.3), beam_m, (x, y, 0.15))
for r in range(6):                      # empty rows around them
    for c in range(3):
        seat_row(f'row{r}_{c}', -24 + c * 18, -14 + r * 5.5, 12, 1 if r % 2 else -1)
seat_row('rowA', -1.24, -1.15, 5, 1)   # A's row (faces +Y, backrest at -Y)
seat_row('rowB', -1.24, 1.15, 5, -1)   # B's row (faces -Y)

# ---------------------------------------------------------------- travellers, suitcase, the game
A = Human('A', skin=SKIN[1], top='#6E7F87', legs='#2E3338', hair='#2A2420', jacket='#586044')
B = Human('B', skin=SKIN[3], top='#D5D2C8', legs='#343A2A', hair='#141414', jacket='#7A4933', hair_style='long', height=1.7)
A.place((0.0, -1.2, 0), yaw=math.pi)   # faces +Y
B.place((0.0, 1.2, 0), yaw=0.0)        # faces -Y
suit = box('suitcase', (0.75, 0.5, 0.48), mat('suit', '#2B3A4A', 0.45), (0, 0, 0.24))
box('suit_band', (0.77, 0.52, 0.04), mat('suitb', '#1D211F', 0.5), (0, 0, 0.24))
bag = box('bag', (0.4, 0.22, 0.3), mat('bag', '#343A2A', 0.8), (0.55, 1.35, 0.15))
TOP = 0.481
gkbox = product_cardbox('gk', 1.0, TEX, SRC)
BOX_HOME = v3(-0.26, 0.12, TOP)
cards = [card(f'c{i}', TEX) for i in range(8)]
CARD_POS = [v3(-0.05, -0.12, TOP + 0.001 + 0.0005 * i) for i in range(2)] + [v3(0.1, -0.12, TOP + 0.001), v3(0.02, 0.1, TOP + 0.001),
            v3(0.14, 0.1, TOP + 0.001), v3(0.24, -0.05, TOP + 0.001), v3(-0.12, 0.04, TOP + 0.002), v3(0.2, 0.08, TOP + 0.002)]
CARD_T = DEAL + PLAY_T + [16.6, 17.0]
dice = []
for nm in ('teal', 'orange'):
    fm = {n: mat_image(f'd_{nm}_{p}', os.path.join(TEX, f'die_{nm}_{p}.png'), 0.3, 0.5) for n, p in
          {(0, 0, 1): 1, (0, 0, -1): 6, (1, 0, 0): 2, (-1, 0, 0): 5, (0, 1, 0): 3, (0, -1, 0): 4}.items()}
    d = make_box(f'die_{nm}', (0.03, 0.03, 0.03), fm, fm[(0, 0, 1)])
    d.rotation_mode = 'XYZ'; dice.append(d)
DICE_REST = [v3(0.27, 0.15, TOP + 0.015), v3(0.31, 0.1, TOP + 0.015)]

lines = Lines([(SPEAKER[k], t, os.path.join(VO, f'vo_{k}.wav')) for k, t in VO_AT.items()], FPS)

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def set_game(t):
    # the box: from B's bag to the suitcase
    if t < BOX_T[0]:
        gkbox.location = (0.55, 1.35, 0.3); gkbox.rotation_euler = (0, 0, 0.3)
    else:
        u = ease((t - BOX_T[0]) / (BOX_T[1] - BOX_T[0]))
        p = lerp(v3(0.55, 1.35, 0.3), BOX_HOME, u) + v3(0, 0, 0.35 * math.sin(math.pi * u))
        gkbox.location = tuple(p); gkbox.rotation_euler = (0, 0, lerp(0.3, -0.15, u))
    for i, c in enumerate(cards):
        tc = CARD_T[i]
        if t < tc - 0.35:
            c.location = tuple(HIDE); continue
        u = ease((t - (tc - 0.35)) / 0.35)
        src = v3(0.0, -0.45 if i % 2 == 0 else 0.45, 0.85)
        p = lerp(src, CARD_POS[i], u)
        c.location = tuple(p)
        c.rotation_euler = (0, 0, (0.3 * i - 0.6) + (1 - u) * 1.5)
    for k, d in enumerate(dice):
        if t < DICE_T - 0.2:
            d.location = tuple(HIDE); continue
        s = t - DICE_T
        if s < 0.9:
            u = ease((s + 0.2) / 1.1)
            p = lerp(v3(0.0, 0.35, 0.72), DICE_REST[k], u) + v3(0, 0, 0.12 * abs(math.sin(s * 9)) * (1 - u))
            d.location = tuple(p); d.rotation_euler = (s * 11 + k, s * 7, s * 5 + k)
        else:
            d.location = tuple(DICE_REST[k]); d.rotation_euler = ((0, math.pi / 2)[k], 0, 0.4 + k)

def set_people(t):
    tc = on_twos(t)
    for H, who, seed in ((A, 'A', 4), (B, 'B', 5)):
        H.pose(POSES['sit']); H.sit_height(0.49)
        if tc < T2 - 0.4:
            H.add({'spine': (-0.12, 0, 0), 'uarm_L': (0.1, 0, 0.1), 'uarm_R': (0.1, 0, -0.1)})   # slumped, waiting
            H.look(0, -0.1)
        else:
            H.add({'spine': (0.25, 0, 0), 'uarm_L': (-0.7, 0, 0.15), 'uarm_R': (-0.7, 0, -0.15),
                   'farm_L': (-0.9, 0, -0.2), 'farm_R': (-0.9, 0, 0.2), 'head': (0.35, 0, 0)})
        H.idle(tc, 0.7); H.blink(t, seed)
        H.talk(lines.amount(who, t))
    # B reaches into the bag for the box
    if BOX_T[0] - 0.4 <= tc < BOX_T[1]:
        r = math.sin(math.pi * (tc - BOX_T[0] + 0.4) / (BOX_T[1] - BOX_T[0] + 0.4))
        B.add({'uarm_R': (0.4 * r, 0, -0.5 * r), 'spine': (0.1 * r, 0, -0.2 * r)})
    # A: "You brought it?" looks up at B; both glance at the gate during boarding, then back to the cards
    if VO_AT['02'] - 0.3 <= tc < VO_AT['03'] + 0.6:
        A.add({'head': (-0.35, 0, 0)})
    if 15.6 <= tc < 16.8:
        B.add({'head': (-0.4, 0, 0.6)})
    if 16.0 <= tc < 17.0:
        A.add({'head': (-0.3, 0, -0.5)})

def set_plane(t):
    """parked side-on beyond the glass; taxis off to the left, nose first"""
    u = ease((t - PLANE_T[0]) / (PLANE_T[1] - PLANE_T[0]))
    plane.location = tuple(PLANE_HOME + v3(-95 * u ** 2.0, 6 * u, 0))
    plane.rotation_euler = (0, 0, math.pi / 2)

cam, cam_d = make_camera(clip_end=3000)
def camera_at(t):
    if t < T2:   # monumental: the hall, the glass wall, the plane, two tiny people
        u = t / T2
        return lerp(v3(-9.0, -24.0, 1.5), v3(-8.4, -22.5, 1.5), u), v3(-2.0, 35.0, 7.0), 13.0, 0.0
    if t < T3:
        return v3(2.5, 0.35, 1.3), v3(0.0, 0.0, 0.78), 26.0, 0.0
    if t < T4:   # overhead on the suitcase
        return v3(0.08, 0.02, 1.32), v3(0.04, 0.0, TOP), 34.0, 0.0
    if t < T5:   # boarding: over A's shoulder to B, the glass and the plane behind her
        u = (t - T4) / (T5 - T4)
        return lerp(v3(-1.3, -1.9, 1.85), v3(-1.15, -1.75, 1.8), u), v3(0.1, 1.3, 0.85), 22.0, 0.0
    u = (t - T5) / (T_END - T5)   # the plane leaves; they stay
    return lerp(v3(-2.6, -10.5, 1.5), v3(-2.4, -9.8, 1.5), u), v3(2.0, 35.0, 5.5), 14.0, 0.0

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_game(t); set_people(t); set_plane(t)
    return t >= T_END

def events():
    os.makedirs(WORK, exist_ok=True)
    json.dump({'VO_AT': VO_AT, 'SPEAKER': SPEAKER, 'BOX_T': BOX_T, 'CARD_T': CARD_T, 'DICE_T': DICE_T,
               'PLANE_T': PLANE_T, 'cuts': [T2, T3, T4, T5], 'end': T_END, 'dur': DUR},
              open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
