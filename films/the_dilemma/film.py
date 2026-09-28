"""THE DILEMMA -- Goosnav Book 2 / Goosklerf / Patreon. 90 s, Blender Eevee.
Everything is driven by update(t). Run through the studio CLI or directly:

  flock $LOCK blender -b --factory-startup -P films/the_dilemma/film.py -- --format 4x5 --out DIR \
        [--start S --end E] [--step N] [--preview] [--times t1,t2] [--mblur --cuts 504,1008] [--resume]
"""
import sys, os
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa: F401,F403
import bstudio as bs
from studio import config

FILM = 'the_dilemma'
TEX = str(config.textures())
WORK = str(config.path('work', FILM, FORMAT))
FPS = 24
DUR = 90.0
rng = np.random.default_rng(7)
set_rng(rng)
# ---------------------------------------------------------------- timeline
T_DESERT = 1.0     # hard cut from black
T_S1B = 6.4       # low-angle monolith
T_S2 = 13.8        # close on the cover
T_LEAK = 15.0      # light starts leaking
T_S3 = 21.0        # wide for detonation
T_EXP = 21.5       # detonation
T_V0 = 23.0        # pages begin to be pulled into the vortex
T_FLY = 23.6       # camera starts flying into the funnel
T_S4 = 27.6        # inside the funnel
T_S5 = 42.0        # card rain
T_S5B = 46.5       # fortress builds
T_S5C = 53.0       # push in, pack lands
T_PACK = 53.85
T_S6 = 61.0        # standing order
T_HERO_PAGE = 66.0
T_S7 = 73.0        # rewind
T_SLAM = 76.0
T_LENS = 85.9      # page onto lens
T_END_WHITE = 86.7
HERO_TIMES = [29.4, 32.0, 34.6]  # foot oiling / emotion nullifier / coffee mug

# ---------------------------------------------------------------- terrain
F = v3(16.0, 26.0, 0.0)          # fortress site
def plateau(x, y):
    d0 = np.sqrt(x ** 2 + y ** 2)
    d1 = np.sqrt((x - F[0]) ** 2 + (y - F[1]) ** 2)
    return np.minimum(ss(24, 48, d0), ss(40, 62, d1))
def dunes(x, y):
    d = np.sqrt(x ** 2 + y ** 2)
    def crest(s):
        return ((np.sin(s) + 1) * 0.5) ** 2.2
    a = 0.52; b = -0.9
    u1 = x * math.cos(a) + y * math.sin(a); u2 = x * math.cos(b) + y * math.sin(b)
    h = (5.0 * crest(0.042 * u1 + 0.9 * np.sin(0.017 * y + 0.4))
         + 2.6 * crest(0.071 * u2 + 1.2 * np.sin(0.026 * x + 1.3))
         + 0.55 * np.sin(0.13 * x + 0.21 * y) * np.sin(0.11 * y - 0.07 * x))
    return h * (1 + d / 70.0)
def terrain_h(x, y):
    return dunes(x, y) * plateau(x, y)

# ---------------------------------------------------------------- scene setup
scene = setup_scene(fps=FPS, samples=20)
# ---------------------------------------------------------------- world / sky
world = bpy.data.worlds.new('sky'); scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
wo = wn.nodes.new('ShaderNodeOutputWorld')
tc = wn.nodes.new('ShaderNodeTexCoord')
sep = wn.nodes.new('ShaderNodeSeparateXYZ')
wn.links.new(tc.outputs['Generated'], sep.inputs[0])
ramp = wn.nodes.new('ShaderNodeValToRGB')
cr = ramp.color_ramp
cr.interpolation = 'B_SPLINE'
stops = [(0.0, (1.0, 0.62, 0.45)), (0.05, (1.0, 0.36, 0.52)), (0.16, (0.86, 0.18, 0.62)),
         (0.38, (0.40, 0.10, 0.62)), (0.75, (0.10, 0.04, 0.30)), (1.0, (0.05, 0.02, 0.16))]
cr.elements[0].position = stops[0][0]; cr.elements[0].color = (*stops[0][1], 1)
cr.elements[1].position = stops[-1][0]; cr.elements[1].color = (*stops[-1][1], 1)
for p, c in stops[1:-1]:
    e = cr.elements.new(p); e.color = (*c, 1)
mr = wn.nodes.new('ShaderNodeMapRange')
mr.inputs['From Min'].default_value = 0.0; mr.inputs['From Max'].default_value = 1.0
wn.links.new(sep.outputs['Z'], mr.inputs['Value'])
wn.links.new(mr.outputs[0], ramp.inputs[0])
bg = wn.nodes.new('ShaderNodeBackground')
hue = wn.nodes.new('ShaderNodeHueSaturation')
wn.links.new(ramp.outputs[0], hue.inputs['Color'])
wn.links.new(hue.outputs[0], bg.inputs[0])
SKY_HUE = hue.inputs['Hue']
bg.inputs[1].default_value = 0.8
wn.links.new(bg.outputs[0], wo.inputs[0])
SKY_BG = bg

# three suns in the sky + three coloured sun lamps
SUN_COLS = [(0.0, 0.70, 0.66), (1.0, 0.31, 0.0), (0.42, 0.05, 1.0)]
SUN_A = [(-0.55, 0.16), (0.30, 0.10), (0.72, 0.24)]   # (azimuth from +Y, elevation) scattered
SUN_B = [(-0.13, 0.11), (0.0, 0.11), (0.13, 0.11)]  # aligned behind the book
suns, sun_lamps, sun_mats = [], [], []
for i, c in enumerate(SUN_COLS):
    m = mat_emit(f'sun{i}', c, 9.0)
    me = bpy.data.meshes.new(f'sunball{i}')
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0); bm.to_mesh(me); bm.free()
    me.materials.append(m)
    ob = link(bpy.data.objects.new(f'sun{i}', me))
    ob.visible_shadow = False
    suns.append(ob); sun_mats.append(m)
    ld = bpy.data.lights.new(f'sunlamp{i}', 'SUN'); ld.color = c; ld.energy = 0.9; ld.angle = 0.05; ld.use_shadow = False
    lo = link(bpy.data.objects.new(f'sunlamp{i}', ld)); sun_lamps.append(lo)
key_d = bpy.data.lights.new('key', 'SUN'); key_d.color = (1.0, 0.86, 0.74); key_d.energy = 4.6; key_d.angle = 0.03
key_d.shadow_cascade_max_distance = 90.0
key_d.shadow_cascade_count = 4
key = link(bpy.data.objects.new('key', key_d))
key.rotation_euler = (math.radians(62), 0, math.radians(-28))
flash_d = bpy.data.lights.new('flash', 'POINT'); flash_d.energy = 0; flash_d.shadow_soft_size = 2.0
flash_d.color = (1.0, 0.95, 0.85)
flash = link(bpy.data.objects.new('flash', flash_d))
leak_d = bpy.data.lights.new('leak', 'POINT'); leak_d.energy = 0; leak_d.color = (1.0, 0.8, 0.55); leak_d.shadow_soft_size = 1.5
leak = link(bpy.data.objects.new('leak', leak_d)); leak.location = (5.6, 0.3, 3.4)

def sun_dir(az, el):
    return v3(math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))

# ---------------------------------------------------------------- terrain mesh
def build_terrain():
    N = 360; S = 700.0
    xs = np.linspace(-S / 2, S / 2, N)
    # denser sampling near origin via warp
    w = np.sign(xs) * (np.abs(xs) / (S / 2)) ** 1.8 * (S / 2)
    gx, gy = np.meshgrid(w, w + 40)
    gz = terrain_h(gx, gy)
    verts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
    faces = []
    for j in range(N - 1):
        for i in range(N - 1):
            a = j * N + i
            faces.append((a, a + 1, a + N + 1, a + N))
    me = bpy.data.meshes.new('terrain')
    me.from_pydata(verts.tolist(), [], faces)
    me.update()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    m, nt, out = new_mat('paper_ground')
    L = nt.links
    tc = nt.nodes.new('ShaderNodeTexCoord')
    wave = nt.nodes.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'Z'
    wave.inputs['Scale'].default_value = 2.2; wave.inputs['Distortion'].default_value = 0.6
    wave.inputs['Detail'].default_value = 0.0
    L.new(tc.outputs['Object'], wave.inputs['Vector'])
    lines = nt.nodes.new('ShaderNodeMapRange')  # thin dark lines
    lines.inputs['From Min'].default_value = 0.0; lines.inputs['From Max'].default_value = 0.14
    lines.inputs['To Min'].default_value = 1.0; lines.inputs['To Max'].default_value = 0.0
    L.new(wave.outputs['Fac'], lines.inputs['Value'])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    sepn = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(geo.outputs['Normal'], sepn.inputs[0])
    slope = nt.nodes.new('ShaderNodeMapRange')
    slope.inputs['From Min'].default_value = 0.985; slope.inputs['From Max'].default_value = 0.90
    L.new(sepn.outputs['Z'], slope.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    L.new(lines.outputs[0], mul.inputs[0]); L.new(slope.outputs[0], mul.inputs[1])
    mixl = nt.nodes.new('ShaderNodeMix'); mixl.data_type = 'RGBA'
    mixl.inputs[6].default_value = (0.95, 0.93, 0.89, 1); mixl.inputs[7].default_value = (0.55, 0.50, 0.52, 1)
    L.new(mul.outputs[0], mixl.inputs['Factor'])
    noise = nt.nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 0.08
    L.new(tc.outputs['Object'], noise.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.12
    L.new(mixl.outputs[2], mix.inputs[6]); L.new(noise.outputs['Color'], mix.inputs[7])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.92
    b.inputs['Specular IOR Level'].default_value = 0.15
    L.new(mix.outputs[2], b.inputs['Base Color'])
    rip = nt.nodes.new('ShaderNodeTexNoise'); rip.inputs['Scale'].default_value = 1.4
    rip.inputs['Detail'].default_value = 3.0
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.05
    L.new(tc.outputs['Object'], rip.inputs['Vector'])
    L.new(rip.outputs['Fac'], bump.inputs['Height'])
    L.new(bump.outputs[0], b.inputs['Normal'])
    # aerial haze towards the horizon colour
    cd = nt.nodes.new('ShaderNodeCameraData')
    hz = nt.nodes.new('ShaderNodeMapRange'); hz.clamp = True
    hz.inputs['From Min'].default_value = 40.0; hz.inputs['From Max'].default_value = 420.0
    hz.inputs['To Max'].default_value = 0.85
    L.new(cd.outputs['View Distance'], hz.inputs['Value'])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (1.0, 0.62, 0.62, 1)
    em.inputs[1].default_value = 0.9
    ms = nt.nodes.new('ShaderNodeMixShader')
    L.new(hz.outputs[0], ms.inputs[0]); L.new(b.outputs[0], ms.inputs[1]); L.new(em.outputs[0], ms.inputs[2])
    L.new(ms.outputs[0], out.inputs[0])
    me.materials.append(m)
    return link(bpy.data.objects.new('terrain', me))
terrain = build_terrain()

# ---------------------------------------------------------------- the book
BW, BH, BT = 9.0, 6.75, 1.35    # giant Book Two
BOARD = 0.13
board_mat = mat_color('board_blue', (0.0, 0.0331, 0.3515), rough=0.5)   # PMS 286 #0033A0
front_mat = mat_image('cover_front', TEX + '/gen_book_front.png', rough=0.5, spec=0.35, coat=0.12)
back_mat = mat_image('cover_back', TEX + '/gen_book_back.png', rough=0.5, spec=0.35, coat=0.12)
spine_mat = mat_image('cover_spine', TEX + '/gen_book_spine.png', rough=0.5, spec=0.35, coat=0.12)
# page block: cream with page-edge lines and an emissive seam driven per frame
blk_mat, nt, out = new_mat('page_block')
tc = nt.nodes.new('ShaderNodeTexCoord')
wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Y'
wv.inputs['Scale'].default_value = 60.0
nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
rp = nt.nodes.new('ShaderNodeValToRGB')
rp.color_ramp.elements[0].color = (0.70, 0.66, 0.60, 1); rp.color_ramp.elements[1].position = 0.25
rp.color_ramp.elements[1].color = (0.95, 0.93, 0.87, 1)
nt.links.new(wv.outputs['Fac'], rp.inputs[0])
bb = nt.nodes.new('ShaderNodeBsdfPrincipled'); bb.inputs['Roughness'].default_value = 0.9
nt.links.new(rp.outputs[0], bb.inputs['Base Color'])
bb.inputs['Emission Color'].default_value = (1.0, 0.93, 0.8, 1)
bb.inputs['Emission Strength'].default_value = 0.0
nt.links.new(bb.outputs[0], out.inputs[0])
BLOCK_EMIT = bb.inputs['Emission Strength']

book_front = make_box('book_front', (BW, BOARD, BH), {(0, -1, 0): front_mat}, board_mat, bevel=0.025)
book_back = make_box('book_back', (BW, BOARD, BH), {(0, 1, 0): back_mat}, board_mat, bevel=0.025)
book_spine = make_box('book_spine', (BOARD, BT, BH), {(-1, 0, 0): spine_mat}, board_mat, bevel=0.025)
book_block = make_box('book_block', (BW - 0.16, BT - 2 * BOARD - 0.01, BH - 0.18), {}, blk_mat)
BOOK_PARTS = {  # rest offsets relative to book centre
    'front': (book_front, v3(0.0, -(BT - BOARD) / 2, 0)),
    'back': (book_back, v3(0.0, (BT - BOARD) / 2, 0)),
    'spine': (book_spine, v3(-(BW - BOARD) / 2, 0, 0)),
    'block': (book_block, v3(0.04, 0, 0)),
}
BOOK_C = v3(0, 0, BH / 2)
# explosion destinations for boards
BOARD_FLY = {
    'front': (v3(-0.05, -1.0, 0.28), 70.0, v3(2.3, 0.4, 5.1)),
    'back': (v3(0.2, 1.0, 0.35), 45.0, v3(-1.7, 0.2, 3.3)),
    'spine': (v3(-1.0, -0.15, 0.45), 40.0, v3(0.6, 4.1, 1.2)),
    'block': (v3(0.0, 0.0, 0.3), 0.0, v3(0, 0, 0)),
}

# ---------------------------------------------------------------- pages (Book Two drawings)
PAGE_W, PAGE_H = 3.1, 2.4
page_tex = [f'{TEX}/page_{i:02d}.png' for i in range(6)]
page_mats = [mat_two_sided(f'page{i}', page_tex[i], page_tex[(i + 3) % 6]) for i in range(6)]
NP = 260
page_ids = rng.integers(0, 6, NP)
pages = Sheets('pages', NP, PAGE_W, PAGE_H, page_mats, page_ids)
P_stack_y = np.linspace(-BT / 2 + 0.2, BT / 2 - 0.2, NP)
P_stack = np.stack([rng.uniform(-0.5, 0.5, NP), P_stack_y, BH / 2 + rng.uniform(-0.3, 0.3, NP)], -1)
d = rng.normal(size=(NP, 3)); d[:, 1] -= 0.7; d[:, 2] = np.abs(d[:, 2]) + 0.35
P_dir = norm(d)
P_dist = rng.uniform(9, 42, NP) * (0.6 + 0.4 * rng.random(NP))
P_k = rng.uniform(1.6, 3.2, NP)
P_spin_ax = norm(rng.normal(size=(NP, 3)))
P_spin = rng.uniform(4, 13, NP) * rng.choice([-1, 1], NP)
P_slow = rng.uniform(0.3, 1.2, NP)
P_curl = rng.uniform(-0.35, 0.35, NP)
# vortex params
V_phi = rng.uniform(0, 2 * np.pi, NP)
V_r = rng.uniform(6.5, 12.0, NP)
V_w = rng.uniform(0.85, 1.35, NP)
V_h = rng.uniform(-28, 62, NP)
V_delay = rng.uniform(0, 2.2, NP)
V_flut = rng.uniform(0, 2 * np.pi, NP)
# rewind: pages start scattered in the sky
R_start = np.stack([rng.uniform(-60, 60, NP), rng.uniform(-40, 70, NP), rng.uniform(4, 60, NP)], -1)

# hero pages for the three named machines
HERO_TEX = [f'{TEX}/hero_foot.png', f'{TEX}/hero_emotion.png', f'{TEX}/hero_mug.png']
hero_mats = [mat_two_sided(f'hero{i}', HERO_TEX[i], page_tex[i + 1]) for i in range(3)]
heroes = Sheets('heroes', 3, PAGE_W, PAGE_H, hero_mats, [0, 1, 2])

# ---------------------------------------------------------------- Goosklerf cards
CW, CH = 2.0, 2.8
card_mat = mat_two_sided('card', TEX + '/gen_card.png', TEX + '/gen_card.png', rough=0.35, translucent=0.02, gloss=0.5, glow=0.08, alpha=True)

def fortress_layout():
    out = []  # (pos, R) ; local card front (-Y) shows the Goosklerf back design
    th = math.radians(17)
    b = CH * math.sin(th) / 2
    z = 0.0
    for k in range(4):
        n = 4 - k
        for j in range(n):
            cx = (j - (n - 1) / 2) * (CW + 0.18)
            for s in (-1, 1):
                pos = v3(cx, s * b, z + CH * math.cos(th) / 2)
                R = np.array(Matrix.Rotation(s * th, 3, 'X'))
                if s > 0:
                    R = R @ np.array(Matrix.Rotation(math.pi, 3, 'Z'))
                out.append((pos, R))
        z += CH * math.cos(th) + 0.03
        if k < 3:
            for j in range(n):
                cx = (j - (n - 1) / 2) * (CW + 0.18)
                R = np.array(Matrix.Rotation(-math.pi / 2, 3, 'X'))
                out.append((v3(cx, 0, z), R))
            z += 0.03
    # palisade: ring of upright cards facing outward, alternating face / back
    for i in range(16):
        a = i / 16 * 2 * math.pi - math.pi / 2
        p = v3(9.5 * math.cos(a), 9.5 * math.sin(a), CH / 2)
        outward = v3(math.cos(a), math.sin(a), 0)
        R = frames_from(outward[None], v3(0, 0, 1)[None])[0]
        if i % 2:
            R = R @ np.array(Matrix.Rotation(math.pi, 3, 'Z'))
        out.append((p, R))
    return out
FORT = fortress_layout()
N_FORT = len(FORT)
N_SCAT = 24
NC = N_FORT + N_SCAT
cards = Sheets('cards', NC, CW, CH, [card_mat], np.zeros(NC, int), nx=2, nz=2)
C_target = np.zeros((NC, 3)); C_R = np.zeros((NC, 3, 3))
for i, (p, R) in enumerate(FORT):
    C_target[i] = F + p; C_R[i] = R
for i in range(N_SCAT):
    a = rng.uniform(0, 2 * np.pi); r = rng.uniform(11, 26)
    x, y = F[0] + r * math.cos(a), F[1] + r * math.sin(a)
    C_target[N_FORT + i] = v3(x, y, terrain_h(x, y) + 0.04)
    C_R[N_FORT + i] = euler_mats(v3(math.pi / 2 * rng.choice([-1, 1]) + rng.normal(0, .06), rng.normal(0, .06), rng.uniform(0, 6.3))[None])[0]
# landing times: structure builds bottom-up, palisade after, scatter throughout
C_land = np.zeros(NC)
C_land[:N_FORT - 16] = np.linspace(47.2, 51.6, N_FORT - 16)
C_land[N_FORT - 16:N_FORT] = np.linspace(51.9, 53.3, 16)
C_land[N_FORT:] = np.sort(rng.uniform(46.0, 58.0, N_SCAT))
C_fall = rng.uniform(9, 14, NC)
C_tumble_ax = norm(rng.normal(size=(NC, 3)))
C_tumble = rng.uniform(3, 8, NC)
C_sway = rng.uniform(2, 7, NC)
C_phase = rng.uniform(0, 6.3, NC)

NRC = 40
rain = Sheets('rain', NRC, CW, CH, [card_mat], np.zeros(NRC, int), nx=2, nz=2)
RC_xy = rng.uniform(-14, 14, (NRC, 2)); RC_z0 = rng.uniform(8, 70, NRC); RC_v = rng.uniform(5, 9, NRC)
RC_ax = norm(rng.normal(size=(NRC, 3))); RC_w = rng.uniform(1.5, 5, NRC)

# ---------------------------------------------------------------- dice
DIE = 2.0
PIP_OF = {(0, 0, 1): 1, (0, 0, -1): 6, (1, 0, 0): 2, (-1, 0, 0): 5, (0, 1, 0): 3, (0, -1, 0): 4}
dice = []
DIE_NAMES = ['teal', 'orange', 'purple']
for nm in DIE_NAMES:
    fm = {n: mat_image(f'die_{nm}_{p}', f'{TEX}/die_{nm}_{p}.png', rough=0.22, spec=0.6, coat=0.6) for n, p in PIP_OF.items()}
    base = fm[(0, 0, 1)]
    ob = make_box(f'die_{nm}', (DIE, DIE, DIE), fm, base, bevel=0.22)
    ob.rotation_mode = 'XYZ'
    dice.append(ob)
DICE_REST = [F + v3(-7.5, -10.5, DIE / 2), F + v3(9.5, -8.5, DIE / 2), F + v3(-2.5, -15.5, DIE / 2)]
DICE_REST_E = [v3(0, 0, 0.35), v3(math.pi / 2, 0, -0.5), v3(0, -math.pi / 2, 0.9)]
DICE_LAND = [50.2, 50.85, 51.45]
DICE_HERO = [v3(-6.5, -8.5, DIE / 2), v3(-10.5, -4.8, DIE / 2), v3(7.2, -10.5, DIE / 2)]  # beside the book at the end
DICE_HERO_E = [v3(0, 0, 0.3), v3(math.pi / 2, 0, 0.9), v3(0, -math.pi / 2, -0.4)]

# ---------------------------------------------------------------- Goosklerf pack
pack_front_mat = mat_image('pack_front', TEX + '/gen_pack.png', rough=0.28, spec=0.7, coat=0.4)
pack_silver = mat_color('pack_silver', (0.78, 0.8, 0.84), rough=0.22, metal=1.0)
pack = make_box('pack', (2.9, 0.2, 4.6), {(0, -1, 0): pack_front_mat}, pack_silver, bevel=0.04)
pack.rotation_mode = 'XYZ'

# ---------------------------------------------------------------- the slot in the sky & comics
slot = make_box('slot', (34, 3.2, 0.5), {}, mat_emit('slot_light', (1.0, 0.95, 0.88), 14.0))
slot.visible_shadow = False
SLOT_POS = F + v3(0, 10, 72)
comic_tex = [f'{TEX}/comic_{i:02d}.png' for i in range(7)]
comic_mats = [mat_two_sided(f'comic{i}', comic_tex[i], comic_tex[(i + 2) % 7], translucent=0.12) for i in range(7)]
NS = 90
snow_ids = rng.integers(0, 7, NS)
snow = Sheets('snow', NS, PAGE_W, PAGE_H, comic_mats, snow_ids)
S_birth = np.sort(rng.uniform(52.0, 90.0, NS)) - 18.0   # already falling by the time we look
S_x = rng.uniform(-15, 15, NS)
S_fall = rng.uniform(2.4, 3.6, NS)
S_sw = rng.uniform(0.9, 1.5, NS); S_amp = rng.uniform(1.5, 3.5, NS); S_ph = rng.uniform(0, 6.3, NS)
S_drift = rng.uniform(-9, 9, NS)
hero_comic = Sheets('hero_comic', 1, PAGE_W, PAGE_H, [comic_mats[1]], [0])
lens_page = Sheets('lens_page', 1, PAGE_W, PAGE_H, [page_mats[0]], [0])

# ---------------------------------------------------------------- shockwave ring & grit
def build_ring():
    me = bpy.data.meshes.new('ring')
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, segments=96, radius=1.0)
    inner = [v for v in bm.verts]
    ret = bmesh.ops.extrude_edge_only(bm, edges=bm.edges[:])
    for v in [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]:
        v.co *= 0.8
    bm.to_mesh(me); bm.free()
    m, nt, out = new_mat('ring')
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = (1.0, 0.9, 0.8, 1)
    e.inputs[1].default_value = 6.0
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    ms = nt.nodes.new('ShaderNodeMixShader'); ms.inputs[0].default_value = 0.5
    nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(e.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs[0])
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'
    me.materials.append(m)
    ob = link(bpy.data.objects.new('ring', me))
    return ob, ms.inputs[0], e.inputs[1]
ring, RING_MIX, RING_STR = build_ring()

NG = 220
grit_mat = mat_color('grit', (0.95, 0.92, 0.86), rough=0.9)
grit = Sheets('grit', NG, 0.22, 0.012, [grit_mat], np.zeros(NG, int), nx=1, nz=1)
G_base = rng.uniform(0, 1, (NG, 3))
G_speed = rng.uniform(5, 11, NG)

# ---------------------------------------------------------------- camera
cam, cam_d = make_camera()
def cam_h_funnel(t):
    return lerp(3.6, 78.0, float(sm(T_S4 - 0.8, T_S5 + 1.0, t)) ** 1.15)

def camera_at(t):
    """returns eye, target, lens, roll"""
    if t < T_S1B:
        u = float(sm(T_DESERT, T_S1B + 1.5, t))
        eye = lerp(v3(-5.0, -72.0, 1.0), v3(-3.2, -50.0, 1.3), u) + sway(t, 0.12)
        tgt = lerp(v3(0, 0, 6.2), v3(0, 0, 5.4), u)
        return eye, tgt, 46.0 * (1.3 if PORTRAIT else 1.0), 0.0   # portrait: keep the monolith large
    if t < T_S2:
        u = float(sm(T_S1B - 1.0, T_S2 + 0.5, t))
        a = lerp(-2.40, -1.95, u); r = lerp(18.0, 14.5, u)
        eye = v3(r * math.cos(a), r * math.sin(a), lerp(0.5, 0.8, u)) + sway(t, 0.05)
        return eye, v3(0.5, 0, lerp(6.4, 5.2, u)), 19.0, lerp(0.06, -0.03, u)
    if t < T_S3:
        u = float(sm(T_S2, T_S3, t))
        amp = 0.02 + 0.10 * float(ss(17.0, 21.0, t))
        eye = lerp(v3(6.5, -16.5, 2.6), v3(3.2, -11.8, 3.2), u) + shake(t, amp) + sway(t, 0.05)
        return eye, v3(0, 0, 3.37) + shake(t + 3, amp * 0.5), 38.0, 0.0
    if t < T_S4:
        # wide, then fly into the funnel
        k = float(math.exp(-max(t - T_EXP, 0) * 2.5)) if t > T_EXP else 0.0
        amp = 0.05 + 0.7 * k
        u = float(sm(T_FLY, T_S4, t))
        eye = lerp(v3(0.0, -56.0, 3.0), v3(0.0, 0.0, cam_h_funnel(t)), u) + shake(t, amp, 1.4)
        yaw = lerp(0.0, 0.25, u)
        look = v3(math.sin(yaw), math.cos(yaw), lerp(0.05, 0.12, u))
        tgt = lerp(v3(0, 0, 7.5), eye + look * 10, u)
        lens = lerp(28.0, 19.0, u)
        return eye, tgt, lens, lerp(0.0, -0.12, u)
    if t < T_S5:
        tt = t - T_S4
        eye = v3(0.0, 0.0, cam_h_funnel(t)) + shake(t, 0.05, 0.6)
        yaw = 0.25 + 0.42 * tt + 0.012 * tt * tt
        pitch = lerp(0.12, 0.62, float(ss(34.5, 41.5, t)))
        look = v3(math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch))
        return eye, eye + look * 10, 19.0, -0.12 + 0.18 * math.sin(tt * 0.5)
    if t < T_S5B:
        u = float(sm(T_S5, T_S5B, t))
        eye = F + v3(-3.0, -17.0, 1.4) + v3(0, lerp(0, 2.0, u), 0)
        tgt = F + v3(lerp(-1.0, 1.0, u), -2.0, 40.0)
        return eye, tgt, 22.0, lerp(0.0, 0.35, u)
    if t < T_S5C:
        u = float(sm(T_S5B, T_S5C, t))
        a = lerp(-1.95, -1.25, u)
        r = lerp(33.0, 29.0, u)
        eye = F + v3(r * math.cos(a), r * math.sin(a), lerp(7.0, 3.6, u))
        amp = 0.0
        for tl in C_land[:N_FORT]:
            if 0 <= t - tl < 0.4:
                amp += 0.035 * (1 - (t - tl) / 0.4)
        for tl in DICE_LAND:
            if 0 <= t - tl < 0.6:
                amp += 0.18 * (1 - (t - tl) / 0.6)
        return eye + shake(t, amp, 1.5), F + v3(0, 0, 4.2), 28.0, 0.0
    if t < T_S6:
        u = float(sm(T_S5C, T_S6, t))
        eye = lerp(F + v3(9.0, -26.0, 3.0), F + v3(3.5, -15.0, 1.5), u)
        k = max(0.0, 1 - abs(t - T_PACK) / 0.5) if t > T_PACK else 0.0
        eye = eye + shake(t, 0.12 * k, 1.5)
        return eye, lerp(F + v3(0, 0, 3.5), F + v3(0, -6.5, 2.2), u), lerp(30.0, 36.0, u), 0.0
    if t < T_S7:
        u = float(sm(T_S6, T_S6 + 5.0, t))
        eye = lerp(F + v3(3.5, -15.0, 1.5), F + v3(1.0, -21.0, 2.0), u)
        tgt = lerp(F + v3(0, -6.5, 2.2), SLOT_POS + v3(0, 0, -12), u)
        return eye, tgt, lerp(36.0, 22.0, u), lerp(0.0, 0.2, float(ss(T_S6 + 3, T_S7, t)))
    if t < T_SLAM + 0.3:
        k = math.exp(-max(t - T_SLAM, 0) * 4.0) if t >= T_SLAM else 0.0
        eye = v3(-7.0, -60.0, 4.5) + shake(t, 0.03 + 0.6 * k, 1.4)
        return eye, v3(0, 0, 5.5), 30.0, 0.0
    u = float(sm(T_SLAM + 0.3, T_LENS + 0.6, t))
    k = math.exp(-max(t - T_SLAM, 0) * 4.0)
    a = lerp(-1.95, -1.66, u)
    r = lerp(31.0, 25.0, u)
    eye = v3(r * math.cos(a), r * math.sin(a), lerp(2.6, 1.9, u)) + shake(t, 0.6 * k, 1.4)
    return eye, v3(1.5, 0, lerp(4.4, 4.0, u)), 32.0, 0.0

# ---------------------------------------------------------------- update
def set_book(t):
    if t < T_EXP:
        jit = float(ss(16.5, T_EXP, t)) ** 2
        off = shake(t * 3.1, 0.06 * jit, 2.2)
        rot = shake(t * 2.3 + 5, 0.012 * jit, 2.6)
        for nm, (ob, rest) in BOOK_PARTS.items():
            ob.location = BOOK_C + rest + off + v3(0, 0, abs(off[2]) * 2)
            ob.rotation_euler = tuple(rot)
            ob.scale = (1, 1, 1)
        lk = float(ss(T_LEAK, T_EXP, t)) ** 1.6 * (1 + 0.3 * math.sin(t * 31) * math.sin(t * 7.3))
        BLOCK_EMIT.default_value = 160.0 * lk
        leak_d.energy = 9.0e3 * lk
        return
    # exploded (or rewinding)
    if t < T_S7:
        tau = t - T_EXP
    elif t < T_SLAM:
        tau = 7.0 * ((T_SLAM - t) / (T_SLAM - T_S7)) ** 2.2
    else:
        tau = 0.0
    BLOCK_EMIT.default_value = 400.0 * math.exp(-tau * 6) if t < T_S7 else 0.0
    leak_d.energy = 0.0
    for nm, (ob, rest) in BOOK_PARTS.items():
        dvec, dist, spin = BOARD_FLY[nm]
        k = 1 - math.exp(-1.8 * tau)
        if nm == 'block':
            s = max(0.0, 1 - tau * 5)
            ob.location = BOOK_C + rest
            ob.scale = (s, s, s)
            ob.rotation_euler = (0, 0, 0)
            continue
        ob.scale = (1, 1, 1)
        ob.location = BOOK_C + rest + norm(dvec) * dist * k + v3(0, 0, -0.4 * tau * tau * (nm != 'front'))
        ob.rotation_euler = tuple(spin * k * 1.6)
    if t >= T_SLAM:
        for nm, (ob, rest) in BOOK_PARTS.items():
            ob.location = BOOK_C + rest; ob.rotation_euler = (0, 0, 0); ob.scale = (1, 1, 1)


def page_explosion(tau):
    k = 1 - np.exp(-P_k * tau)
    pos = P_stack + BOOK_C * 0 + P_dir * (P_dist * k)[:, None] + np.stack(
        [0.35 * tau * np.ones(NP), 0.1 * tau * np.ones(NP), -0.12 * tau * tau * np.ones(NP) * 0.2], -1)
    ang = P_spin * k * 0.35 + P_slow * tau
    R = rot_axis(P_spin_ax, ang)
    return pos, R

def set_pages(t, eye):
    if t < T_EXP or t >= T_SLAM:
        pages.set(np.repeat(HIDE[None], NP, 0), np.repeat(np.eye(3)[None], NP, 0))
        return
    if t >= T_S5 and t < T_S7:
        pages.set(np.repeat(HIDE[None], NP, 0), np.repeat(np.eye(3)[None], NP, 0))
        return
    if t >= T_S7:  # rewind: collapse from the sky into the book
        u = ((T_SLAM - t) / (T_SLAM - T_S7))
        tau = 7.0 * u ** 2.2
        pe, Re = page_explosion(tau)
        w = float(ss(0.55, 1.0, u))
        pos = lerp(pe, R_start, w)
        pages.set(pos, Re, curl=P_curl)
        return
    tau = t - T_EXP
    pe, Re = page_explosion(tau)
    w = ss(T_V0 + V_delay, T_V0 + V_delay + 3.0, t)
    if np.max(w) <= 0:
        pages.set(pe, Re, curl=P_curl)
        return
    ch = cam_h_funnel(t)
    tv = t - T_V0
    ang = V_phi + V_w * tv
    rel = (V_h + 2.8 * tv + 28) % 90 - 28
    hgt = np.maximum(ch + rel, 0.8 + rng_fixed_z)
    r = V_r + 0.10 * np.maximum(rel, 0)
    pv = np.stack([r * np.cos(ang), r * np.sin(ang), hgt], -1)
    inward = -np.stack([np.cos(ang), np.sin(ang), np.zeros(NP)], -1)
    flut = 0.35 * np.sin(1.7 * t + V_flut)
    up = np.stack([0.25 * np.sin(ang + flut), 0.25 * np.cos(ang - flut), np.ones(NP)], -1)
    Rv = frames_from(inward + 0.25 * np.stack([np.sin(V_flut + t), np.cos(V_flut * 1.3 + t), 0.3 * np.sin(t * 2 + V_flut)], -1), up)
    pos = lerp(pe, pv, w[:, None])
    # blend orientations by blending the frame axes and re-orthonormalising
    Nn = norm(lerp(-Re[..., 1], -Rv[..., 1], w[:, None]))
    Un = norm(lerp(Re[..., 2], Rv[..., 2], w[:, None]))
    R = frames_from(Nn, Un)
    pages.set(pos, R, curl=P_curl, wave=np.sin(t * 3 + V_flut) * w)
rng_fixed_z = rng.uniform(0, 1.5, NP)

def set_heroes(t, eye, tgt, lens):
    fwd = norm(tgt - eye)
    right = norm(np.cross(fwd, v3(0, 0, 1)))
    upv = np.cross(right, fwd)
    P = np.repeat(HIDE[None], 3, 0); R = np.repeat(np.eye(3)[None], 3, 0)
    curl = np.zeros(3)
    for i, th in enumerate(HERO_TIMES):
        u = (t - th) / 2.1 + 0.5  # 0..1 across the pass
        if 0 <= u <= 1 and T_S4 <= t < T_S5:
            x = lerp(9.0, -9.0, u) ** 1  # right -> left
            x = 9.0 * (1 - 2 * u)
            x = np.sign(x) * abs(x) ** 1.6 / 9.0 ** 0.6  # linger near centre
            dist = 4.1
            P[i] = eye + fwd * dist + right * x + upv * (0.25 * math.sin(u * 3))
            R[i] = frames_from(-fwd[None], (upv + right * 0.12 * math.sin(u * 4 + i))[None])[0]
            curl[i] = 0.18 * math.sin(u * 5)
    heroes.set(P, R, curl=curl)

def set_cards(t):
    if t < T_S5 - 0.5 or t >= T_S7 and t < T_SLAM:
        cards.set(np.repeat(HIDE[None], NC, 0), np.repeat(np.eye(3)[None], NC, 0))
        return
    dt = np.maximum(C_land - t, 0.0)
    fallen = dt <= 0
    hgt = C_fall * dt + 0.9 * dt * dt
    spiral = np.stack([np.cos(C_phase + dt * 1.3), np.sin(C_phase + dt * 1.3), np.zeros(NC)], -1) * (C_sway * np.minimum(dt, 3))[:, None]
    pos = C_target + spiral + np.stack([np.zeros(NC), np.zeros(NC), hgt], -1)
    tumble = rot_axis(C_tumble_ax, C_tumble * dt)
    R = np.einsum('nij,njk->nik', tumble, C_R)
    # landing slam: tiny overshoot
    since = t - C_land
    bump = np.where((since >= 0) & (since < 0.18), 0.12 * np.sin(np.clip(since, 0, 0.18) / 0.18 * np.pi), 0)
    pos[:, 2] += bump
    cards.set(pos, R)

def set_rain(t):
    if not (T_S5 <= t < T_S5B):
        rain.set(np.repeat(HIDE[None], NRC, 0), np.repeat(np.eye(3)[None], NRC, 0)); return
    base = F + v3(-3.0, -17.0, 1.4)
    tt = t - T_S5
    z = RC_z0 - RC_v * tt
    pos = np.stack([base[0] + RC_xy[:, 0] + 2 * np.sin(tt + RC_w), base[1] + 8 + RC_xy[:, 1], base[2] + z], -1)
    rain.set(pos, rot_axis(RC_ax, RC_w * tt + RC_z0))

def die_state(i, t):
    """falling + two bounces + settle, towards DICE_REST[i]"""
    tl = DICE_LAND[i]
    rest = DICE_REST[i]; e_rest = DICE_REST_E[i]
    spin = v3(7.0, -5.0, 3.0) * (1 + 0.2 * i)
    if t < tl:
        dt = tl - t
        p = rest + v3(-4 + 2 * i, -6, 0) * 0 + v3(2.0 * dt, 3.0 * dt, 16.0 * dt + 1.6 * dt * dt + 1.2)
        e = e_rest + spin * (dt + 1.1)
        return p, e
    s = t - tl
    hops = [(0.0, 0.75, 2.8, v3(-1.5, -2.0, 0)), (0.75, 1.15, 0.9, v3(-0.8, -1.0, 0)), (1.15, 1.40, 0.25, v3(-0.3, -0.4, 0))]
    total = v3(-2.6, -3.4, 0)
    start = rest - total
    acc = v3(0, 0, 0)
    for a, b, hh, dxy in hops:
        if s < b:
            u = (s - a) / (b - a)
            p = start + acc + dxy * u + v3(0, 0, 1.2 + 4 * hh * u * (1 - u))
            e = e_rest + spin * max(0.0, 1.1 - s) ** 1.6 * 0.9
            return p, e
        acc = acc + dxy
    u = min(1.0, (s - 1.4) / 0.6)
    p = rest + v3(0, 0, 0)
    e = e_rest + spin * max(0.0, 1.1 - s) ** 1.6 * 0.9
    return p, e

def set_dice(t, eye, tgt):
    for i, ob in enumerate(dice):
        if t < T_S5:
            ob.location = HIDE; continue
        if t < T_S5B:  # tumbling past the up-looking camera
            u = (t - T_S5) / (T_S5B - T_S5)
            base = F + v3(-3.0, -17.0, 1.4)
            offs = [v3(-5, 6, 26), v3(4, 10, 34), v3(-1, 14, 44)][i]
            ob.location = base + offs + v3(0, 0, -34.0 * u) + v3(1.2 * math.sin(t + i), 0, 0)
            ob.rotation_euler = tuple(v3(2.1, 1.3, 0.7) * (t * (1.0 + 0.3 * i)) + i)
            continue
        if t < T_S7:
            p, e = die_state(i, t)
            ob.location = p; ob.rotation_euler = tuple(e)
            continue
        if t < T_SLAM:
            ob.location = HIDE; continue
        ob.location = DICE_HERO[i] + v3(0, 0, terrain_h(*DICE_HERO[i][:2]))
        ob.rotation_euler = tuple(DICE_HERO_E[i])

def set_pack(t):
    if T_S5C - 1.0 <= t < T_S7:
        rest = F + v3(0.6, -7.2, 2.28)
        e_rest = v3(math.radians(-10), 0, math.radians(8))
        if t < T_PACK:
            dt = T_PACK - t
            pack.location = rest + v3(0.5 * dt, -1.0 * dt, 18 * dt + 3 * dt * dt)
            pack.rotation_euler = tuple(e_rest + v3(3.0, 1.2, 4.0) * dt)
        else:
            s = t - T_PACK
            wob = math.exp(-s * 6) * math.sin(s * 30) * 0.08
            pack.location = rest
            pack.rotation_euler = tuple(e_rest + v3(wob, 0, 0))
        return
    if t >= T_SLAM:
        pack.location = v3(5.4, -BT / 2 - 1.1, 2.28)
        pack.rotation_euler = (math.radians(-9), 0, math.radians(-14))
        return
    pack.location = HIDE

def set_snow(t, eye):
    if not (T_S5C + 2 <= t < T_S7):
        snow.set(np.repeat(HIDE[None], NS, 0), np.repeat(np.eye(3)[None], NS, 0))
        hero_comic.set(HIDE[None], np.eye(3)[None])
        return
    age = t - S_birth
    alive = age > 0
    z = SLOT_POS[2] - S_fall * np.maximum(age, 0)
    sw = np.sin(S_sw * age + S_ph)
    x = SLOT_POS[0] + S_x + S_amp * sw + S_drift * np.maximum(age, 0) * 0.08
    y = SLOT_POS[1] + np.cos(S_ph) * 4 + 0.6 * np.cos(S_sw * age * 2 + S_ph) - np.maximum(age, 0) * 0.35
    pos = np.stack([x, y, z], -1)
    pos[~alive] = HIDE
    pos[z < -2] = HIDE
    tilt = 0.8 * np.cos(S_sw * age + S_ph)
    R = rot_axis(np.stack([np.cos(S_ph), np.sin(S_ph), np.zeros(NS)], -1), tilt) @ np.array(Matrix.Rotation(math.pi / 2, 3, 'X'))[None]
    snow.set(pos, R, curl=0.25 * sw, wave=0.5 * np.cos(age * 2 + S_ph))
    # hero comic page falls into the lens
    if t >= T_HERO_PAGE:
        u = float(sm(T_HERO_PAGE, T_S7 - 1.3, t))
        fwd = norm(camera_at(t)[1] - eye)
        right = norm(np.cross(fwd, v3(0, 0, 1))); upv = np.cross(right, fwd)
        d = lerp(34.0, 1.62, u)
        rock = (1 - u) * 0.5 * math.sin(t * 1.6)
        p = eye + fwd * d + right * (1 - u) * 6 * math.sin(t * 0.9) + upv * (1 - u) * 3
        Rh = frames_from(-fwd[None], (upv + right * rock)[None])[0]
        hero_comic.set(p[None], Rh[None], curl=np.array([0.12 * (1 - u)]))
    else:
        hero_comic.set(HIDE[None], np.eye(3)[None])

def set_lens_page(t, eye, tgt):
    if t < T_LENS:
        lens_page.set(HIDE[None], np.eye(3)[None]); return
    u = float(sm(T_LENS, T_END_WHITE, t))
    fwd = norm(tgt - eye); right = norm(np.cross(fwd, v3(0, 0, 1))); upv = np.cross(right, fwd)
    d = lerp(14.0, 0.25, u)
    p = eye + fwd * d + upv * lerp(5.0, 0.0, u) + right * lerp(-2.0, 0.0, u)
    Rl = frames_from(-fwd[None], (upv + right * 0.3 * (1 - u))[None])[0]  # back of the page faces us
    lens_page.set(p[None], Rl[None], curl=np.array([0.25 * (1 - u)]))

def set_ring(t):
    if T_EXP <= t < T_EXP + 3.0:
        tau = t - T_EXP
        r = 2.0 + 70 * (tau / 3.0) ** 0.55
        ring.location = (0, 0, 0.25); ring.scale = (r, r, 1)
        RING_MIX.default_value = max(0.0, 1 - tau / 3.0) ** 1.5 * 0.9
    elif T_SLAM <= t < T_SLAM + 1.6:
        tau = t - T_SLAM
        r = 4.0 + 26 * (tau / 1.6) ** 0.55
        ring.location = (0, 0, 0.2); ring.scale = (r, r, 1)
        RING_MIX.default_value = max(0.0, 1 - tau / 1.6) ** 1.5 * 0.6
    else:
        ring.location = HIDE
        RING_MIX.default_value = 0.0

def set_grit(t, eye, tgt):
    on = (T_DESERT <= t < T_S4) or (t >= T_S7)
    if not on:
        grit.set(np.repeat(HIDE[None], NG, 0), np.repeat(np.eye(3)[None], NG, 0)); return
    fwd = norm(tgt - eye); fwd[2] = 0; fwd = norm(fwd)
    centre = eye + fwd * 14
    box = v3(34, 34, 5)
    wind = v3(1.0, -0.25, 0.04)
    boost = 1 + 4 * float(ss(17, 21.5, t)) * (t < T_EXP + 1)
    p = G_base * box + wind[None] * (G_speed * t * boost)[:, None]
    p = (p % box) - box / 2
    p = centre + p
    p[:, 2] = terrain_h(p[:, 0], p[:, 1]) + (G_base[:, 2] ** 3) * 3.0 + 0.05
    if T_LEAK < t < T_EXP:  # grains hop around the shuddering book
        p[:, 2] += np.abs(np.sin(t * 17 + G_base[:, 0] * 40)) * 0.3 * float(ss(17, 21, t))
    R = frames_from(np.repeat(v3(0, 0, 1)[None], NG, 0) * 0 + norm(np.cross(wind, v3(0, 0, 1)))[None].repeat(NG, 0),
                    np.repeat(v3(0, 0, 1)[None], NG, 0))
    grit.set(p, R)

def set_sky(t):
    u = float(sm(T_SLAM, T_SLAM + 7.0, t))
    for i in range(3):
        a = lerp(SUN_A[i][0], SUN_B[i][0], u); e = lerp(SUN_A[i][1], SUN_B[i][1], u)
        d = sun_dir(a, e)
        suns[i].location = d * 900
        suns[i].scale = (34, 34, 34)
        rot = (-d).tolist()
        sun_lamps[i].rotation_euler = Vector(rot).to_track_quat('-Z', 'Y').to_euler()
        pulse = 1.0
        if T_LEAK < t < T_EXP:
            pulse = 1 + 0.6 * float(ss(T_LEAK, T_EXP, t)) * (0.5 + 0.5 * math.sin(t * (4 + i * 1.7)))
        sun_mats[i].node_tree.nodes['Emission'].inputs[1].default_value = 9.0 * pulse
    # detonation flash
    fl = 0.0
    if T_EXP <= t < T_EXP + 1.5:
        fl = math.exp(-(t - T_EXP) * 3.5)
    if T_SLAM <= t < T_SLAM + 0.8:
        fl = 0.5 * math.exp(-(t - T_SLAM) * 6)
    flash.location = BOOK_C + v3(0, -3, 2)
    flash_d.energy = 6.0e5 * fl
    SKY_BG.inputs[1].default_value = 0.8 + 0.6 * fl
    slot.location = SLOT_POS if T_S5C < t < T_S7 else HIDE
    trip = float(ss(T_S4 - 1, T_S4 + 2, t) * (1 - ss(T_S5 - 2, T_S5, t)))
    SKY_HUE.default_value = 0.5 + trip * 0.09 * math.sin((t - T_S4) * 0.9)

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_book(t); set_pages(t, eye); set_heroes(t, eye, tgt, lens); set_cards(t); set_rain(t)
    set_dice(t, eye, tgt); set_pack(t); set_snow(t, eye); set_lens_page(t, eye, tgt)
    set_ring(t); set_grit(t, eye, tgt); set_sky(t)
    black = (t < T_DESERT) or (t >= T_END_WHITE + 0.2)
    return black

def events():
    ev = {'card_land': [float(x) for x in C_land], 'dice_land': DICE_LAND, 'pack': T_PACK,
          'hero_pages': HERO_TIMES,
          'T': {k: v for k, v in globals().items() if k.startswith('T_') and isinstance(v, float)}}
    os.makedirs(WORK, exist_ok=True)
    json.dump(ev, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

CUT_FRAMES = [504, 1008, 1116, 1272, 1752]   # hard cuts: rendered without motion blur

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
