"""THE LONGEST TURN -- Goosklerf / Goosnav Book 2 / Patreon. 87 s, Blender Eevee, 4:5 portrait.
One game of Goosklerf filmed as the most important battle in history, on a wet walnut table the size
of a continent, then revealed to be an ordinary dining table in an ordinary room.
Units are centimetres (cards 6.3 x 8.8, dice 1.6, table 200 x 110). Everything is driven by update(t).

  flock $LOCK blender -b --factory-startup -P films/the_longest_turn/film.py -- --format 4x5 \
        [--start S --end E] [--step N] [--preview] [--times t1,t2] [--mblur --cuts ...] [--resume]
"""
import sys, os
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa: F401,F403
import bstudio as bs
from studio import config

FILM = 'the_longest_turn'
TEX = str(config.textures())
WORK = str(config.path('work', FILM, FORMAT))
MYTEX = str(config.path('work', FILM, 'tex'))
FPS = 24
DUR = 87.0
rng = np.random.default_rng(31)
set_rng(rng)
FAR = v3(0, 0, -20000)            # parking spot for things that don't exist yet (beyond clip)

# ---------------------------------------------------------------- timeline
T_S1 = 0.0          # night plain, lightning reveals
T_S2 = 6.8          # the fortresses go up (trench run)
T_S3 = 15.0         # reinforcements (booster)
T_TEAR = 17.35
T_S4 = 20.2         # the dice come down
T_IMP = [25.0, 26.35, 27.95, 2.4]     # the fourth die opens the film
T_S5 = 32.8         # the rulebook
T_OPEN = 34.55
T_S6 = 44.2         # the five
T_THROW = 45.0
T_LAND = 50.0
T_FALL = 55.0       # the fortress falls
T_S7 = 57.0         # the storm passes, pull up
T_REVEAL = 58.0
T_S8 = 70.0         # dispatch under the door
T_SLIDE = 70.8
T_S9 = 75.0         # hero products
T_WHITE = 83.3      # white end card (overlay) fully up by ~83.7

# ---------------------------------------------------------------- slow motion clock
_TT = np.arange(0, DUR + 1, 0.001)
_RATE = 1 - 0.92 * ss(44.6, 45.3, _TT) * (1 - ss(50.02, 50.9, _TT))
_TS = np.concatenate([[0], np.cumsum(_RATE[:-1]) * 0.001])
def ts(t):
    """film time with the slow-motion stretch: rain, droplets, lightning and the hero die run on this"""
    return float(np.interp(t, _TT, _TS))

# ---------------------------------------------------------------- scene
scene = setup_scene(fps=FPS, samples=20, bloom=(0.8, 0.06, 6.5))
ee = scene.eevee
ee.use_ssr = flag('--ssr') or not PREVIEW
ee.use_ssr_halfres = True
ee.ssr_thickness = 0.4
ee.ssr_max_roughness = 0.35
ee.use_volumetric_lights = True
ee.volumetric_start = 0.2
ee.volumetric_end = 450.0
ee.volumetric_tile_size = '8'
ee.volumetric_samples = 48
ee.volumetric_light_clamp = 0.0
ee.shadow_cascade_size = '2048'
ee.gtao_distance = 2.0

# ---------------------------------------------------------------- world: storm sky
world = bpy.data.worlds.new('storm'); scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
wo = wn.nodes.new('ShaderNodeOutputWorld')
tc = wn.nodes.new('ShaderNodeTexCoord')
mp = wn.nodes.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1.0, 1.0, 2.6)
wn.links.new(tc.outputs['Generated'], mp.inputs[0])
nz = wn.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2
nz.inputs['Detail'].default_value = 12.0; nz.inputs['Roughness'].default_value = 0.62
wn.links.new(mp.outputs[0], nz.inputs['Vector'])
cr = wn.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].position = 0.35; cr.color_ramp.elements[0].color = (0.004, 0.005, 0.009, 1)
cr.color_ramp.elements[1].position = 0.72; cr.color_ramp.elements[1].color = (0.05, 0.058, 0.08, 1)
wn.links.new(nz.outputs['Fac'], cr.inputs[0])
sep = wn.nodes.new('ShaderNodeSeparateXYZ'); wn.links.new(tc.outputs['Generated'], sep.inputs[0])
hz = wn.nodes.new('ShaderNodeMapRange'); hz.clamp = True
hz.inputs['From Min'].default_value = -0.02; hz.inputs['From Max'].default_value = 0.6
hz.inputs['To Min'].default_value = 1.6; hz.inputs['To Max'].default_value = 0.55
wn.links.new(sep.outputs['Z'], hz.inputs['Value'])
m1 = wn.nodes.new('ShaderNodeMix'); m1.data_type = 'RGBA'; m1.blend_type = 'MULTIPLY'; m1.inputs['Factor'].default_value = 1
wn.links.new(cr.outputs[0], m1.inputs[6])
comb = wn.nodes.new('ShaderNodeCombineXYZ'); wn.links.new(hz.outputs[0], comb.inputs[0]); wn.links.new(hz.outputs[0], comb.inputs[1]); wn.links.new(hz.outputs[0], comb.inputs[2])
wn.links.new(comb.outputs[0], m1.inputs[7])
SKY_LIGHT = wn.nodes.new('ShaderNodeRGB')          # base * clouds + lightning colour, set per frame
m2 = wn.nodes.new('ShaderNodeMix'); m2.data_type = 'RGBA'; m2.blend_type = 'MULTIPLY'; m2.inputs['Factor'].default_value = 1
wn.links.new(m1.outputs[2], m2.inputs[6]); wn.links.new(SKY_LIGHT.outputs[0], m2.inputs[7])
bg = wn.nodes.new('ShaderNodeBackground'); bg.inputs[1].default_value = 1.0
wn.links.new(m2.outputs[2], bg.inputs[0])
wn.links.new(bg.outputs[0], wo.inputs['Surface'])
vs = wn.nodes.new('ShaderNodeVolumeScatter'); vs.inputs['Anisotropy'].default_value = 0.35
vs.inputs['Color'].default_value = (0.5, 0.62, 0.9, 1)
wn.links.new(vs.outputs[0], wo.inputs['Volume'])
FOG = vs.inputs['Density']

# ---------------------------------------------------------------- lights
fill_d = bpy.data.lights.new('fill', 'SUN'); fill_d.color = (0.55, 0.65, 0.9); fill_d.use_shadow = False
fill = link(bpy.data.objects.new('fill', fill_d)); fill.rotation_euler = (math.radians(50), 0, math.radians(140))
moon_d = bpy.data.lights.new('moon', 'SUN'); moon_d.color = (0.62, 0.74, 1.0); moon_d.angle = 0.02
moon_d.shadow_cascade_max_distance = 220.0; moon_d.shadow_cascade_count = 4
moon = link(bpy.data.objects.new('moon', moon_d)); moon.rotation_euler = (math.radians(68), 0, math.radians(-125))
bolt_d = bpy.data.lights.new('strike', 'SUN'); bolt_d.angle = 0.03
bolt_d.shadow_cascade_max_distance = 220.0; bolt_d.shadow_cascade_count = 4
strike = link(bpy.data.objects.new('strike', bolt_d))
flash_d = bpy.data.lights.new('impact', 'POINT'); flash_d.color = (1.0, 0.55, 0.2); flash_d.shadow_soft_size = 1.0
flash = link(bpy.data.objects.new('impact', flash_d)); flash_d.volume_factor = 0.0
fire_d = bpy.data.lights.new('fire', 'POINT'); fire_d.color = (1.0, 0.3, 0.05); fire_d.shadow_soft_size = 0.6
fire = link(bpy.data.objects.new('fire', fire_d)); fire_d.volume_factor = 0.0
gold_d = bpy.data.lights.new('gold', 'POINT'); gold_d.color = (1.0, 0.72, 0.35); gold_d.shadow_soft_size = 3.0
gold = link(bpy.data.objects.new('gold', gold_d)); gold_d.volume_factor = 0.5
tear_d = bpy.data.lights.new('tear', 'POINT'); tear_d.color = (1.0, 0.9, 0.75); tear_d.shadow_soft_size = 1.5
tearl = link(bpy.data.objects.new('tearlight', tear_d))

TEAL, ORANGE, PURPLE = (0.0, 0.70, 0.66), (1.0, 0.31, 0.0), (0.42, 0.05, 1.0)
COLS = [TEAL, ORANGE, PURPLE]
# lightning strikes: (time, colour, azimuth, elevation, strength)
STRIKES = [(1.0, 0, 0.3, 0.7, 1.0), (2.7, 1, -0.6, 0.5, 0.6), (4.9, 2, 1.2, 0.6, 0.9),
           (9.4, 0, -1.0, 0.6, 0.8), (12.7, 1, 0.8, 0.5, 0.9),
           (15.8, 2, 2.6, 0.6, 0.8), (17.35, 1, 3.0, 0.55, 1.1), (19.0, 0, 2.2, 0.7, 0.6),
           (21.2, 2, 0.2, 0.8, 0.9), (22.6, 0, -0.4, 0.7, 0.8), (30.1, 1, 0.5, 0.6, 0.8), (31.9, 2, -0.8, 0.5, 0.7),
           (33.4, 0, 1.2, 0.6, 0.6), (41.2, 2, 0.9, 0.6, 0.5),
           (46.4, 0, 0.9, 0.6, 1.0), (47.7, 1, -0.3, 0.6, 1.0), (49.0, 2, 1.7, 0.6, 1.0), (50.05, 1, 0.4, 0.8, 1.2),
           (52.8, 0, 1.1, 0.6, 0.7), (55.1, 2, 0.6, 0.6, 1.0)]
STRIKE_TS = [ts(s[0]) for s in STRIKES]
def strike_env(t):
    """sum of lightning pulses at time t: (amount, rgb, dir, index of the dominant strike)"""
    tsn = ts(t); best, amt, rgb = -1, 0.0, v3(0, 0, 0)
    bmax = 0.0
    for k, (t0, c, az, el, s) in enumerate(STRIKES):
        d = tsn - STRIKE_TS[k]
        if d < 0 or d > 1.2:
            continue
        a = 0.0
        for off, g in ((0.0, 1.0), (0.085, 0.55), (0.21, 0.8), (0.34, 0.3)):
            if d >= off:
                a += g * math.exp(-(d - off) * 16.0)
        a *= s
        amt += a; rgb = rgb + a * v3(*COLS[c])
        if a > bmax:
            bmax, best = a, k
    return amt, rgb, best

# ---------------------------------------------------------------- helpers
def mesh_obj(name, me, mat=None):
    if mat is not None and not me.materials:
        me.materials.append(mat)
    return link(bpy.data.objects.new(name, me))

def ico_mesh(name, sub=2, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0); bm.to_mesh(me); bm.free()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    if mat: me.materials.append(mat)
    return me

def cube_mesh(name, mat=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    if mat: me.materials.append(mat)
    return me

def quad_mesh(name, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-0.5, 0, -0.5), (0.5, 0, -0.5), (0.5, 0, 0.5), (-0.5, 0, 0.5)], [], [(0, 1, 2, 3)])
    me.update()
    if mat: me.materials.append(mat)
    return me

class Pool:
    """n objects sharing one mesh, moved by matrix_world only"""
    def __init__(self, name, n, me):
        self.n = n
        self.obs = [link(bpy.data.objects.new(f'{name}{i:03d}', me)) for i in range(n)]
    def set(self, pos, R=None, scale=None):
        M = np.zeros((self.n, 4, 4)); M[:, 3, 3] = 1
        R = np.repeat(np.eye(3)[None], self.n, 0) if R is None else R
        if scale is not None:
            sc = np.asarray(scale, float)
            sc = np.repeat(sc[:, None], 3, 1) if sc.ndim == 1 else sc
            R = R * sc[:, None, :]
        M[:, :3, :3] = R; M[:, :3, 3] = pos
        for ob, m in zip(self.obs, M):
            ob.matrix_world = Matrix(m.tolist())
    def hide(self):
        self.set(np.repeat(FAR[None], self.n, 0), scale=np.full(self.n, 0.001))

def place(ob, pos, R=None):
    M = np.eye(4); M[:3, 3] = pos
    if R is not None:
        M[:3, :3] = R
    ob.matrix_world = Matrix(M.tolist())

def Rz(a):
    return np.array(Matrix.Rotation(a, 3, 'Z'))
def Rx(a):
    return np.array(Matrix.Rotation(a, 3, 'X'))
def Ry(a):
    return np.array(Matrix.Rotation(a, 3, 'Y'))

def transparent_mat(name, rgb, strength, alpha):
    m, nt, out = new_mat(name)
    e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = strength
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    ms = nt.nodes.new('ShaderNodeMixShader'); ms.inputs[0].default_value = alpha
    nt.links.new(tp.outputs[0], ms.inputs[1]); nt.links.new(e.outputs[0], ms.inputs[2])
    nt.links.new(ms.outputs[0], out.inputs[0])
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; m.use_backface_culling = False
    return m, e.inputs[1], ms.inputs[0]

# ---------------------------------------------------------------- the table (always there)
TX, TY = 200.0, 110.0
tm, nt, out = new_mat('walnut')
L = nt.links
tco = nt.nodes.new('ShaderNodeTexCoord')
# planks along x, seams every 18.33 cm in y
sepw = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(tco.outputs['Object'], sepw.inputs[0])
dv = nt.nodes.new('ShaderNodeMath'); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = TY / 6
L.new(sepw.outputs['Y'], dv.inputs[0])
fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'FRACT'; L.new(dv.outputs[0], fr.inputs[0])
sub = nt.nodes.new('ShaderNodeMath'); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = 0.5; L.new(fr.outputs[0], sub.inputs[0])
ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L.new(sub.outputs[0], ab.inputs[0])
seam = nt.nodes.new('ShaderNodeMapRange'); seam.inputs['From Min'].default_value = 0.488; seam.inputs['From Max'].default_value = 0.4985
L.new(ab.outputs[0], seam.inputs['Value'])
# per-plank offset so the grain doesn't line up
fl_ = nt.nodes.new('ShaderNodeMath'); fl_.operation = 'FLOOR'; L.new(dv.outputs[0], fl_.inputs[0])
off = nt.nodes.new('ShaderNodeMath'); off.operation = 'MULTIPLY'; off.inputs[1].default_value = 37.7; L.new(fl_.outputs[0], off.inputs[0])
cmb = nt.nodes.new('ShaderNodeCombineXYZ')
addx = nt.nodes.new('ShaderNodeMath'); addx.operation = 'ADD'; L.new(sepw.outputs['X'], addx.inputs[0]); L.new(off.outputs[0], addx.inputs[1])
L.new(addx.outputs[0], cmb.inputs[0]); L.new(sepw.outputs['Y'], cmb.inputs[1]); L.new(off.outputs[0], cmb.inputs[2])
gm = nt.nodes.new('ShaderNodeMapping'); gm.inputs['Scale'].default_value = (0.035, 1.1, 1.0)
L.new(cmb.outputs[0], gm.inputs[0])
grain = nt.nodes.new('ShaderNodeTexWave'); grain.wave_type = 'BANDS'; grain.bands_direction = 'Y'
grain.inputs['Scale'].default_value = 0.11; grain.inputs['Distortion'].default_value = 12.0
grain.inputs['Detail'].default_value = 3.0; grain.inputs['Detail Scale'].default_value = 1.2
L.new(gm.outputs[0], grain.inputs['Vector'])
gr = nt.nodes.new('ShaderNodeValToRGB')
gr.color_ramp.elements[0].color = (0.05, 0.022, 0.009, 1); gr.color_ramp.elements[1].color = (0.19, 0.095, 0.042, 1)
L.new(grain.outputs['Fac'], gr.inputs[0])
seamc = nt.nodes.new('ShaderNodeMix'); seamc.data_type = 'RGBA'
L.new(seam.outputs[0], seamc.inputs['Factor']); L.new(gr.outputs[0], seamc.inputs[6]); seamc.inputs[7].default_value = (0.004, 0.002, 0.001, 1)
# wetness: darker, glossier, puddles
WET_V = nt.nodes.new('ShaderNodeValue'); WET = WET_V.outputs[0]; WET.default_value = 1.0
pud = nt.nodes.new('ShaderNodeTexNoise'); pud.inputs['Scale'].default_value = 0.045; pud.inputs['Detail'].default_value = 4
L.new(tco.outputs['Object'], pud.inputs['Vector'])
pudm = nt.nodes.new('ShaderNodeMapRange'); pudm.inputs['From Min'].default_value = 0.5; pudm.inputs['From Max'].default_value = 0.56
L.new(pud.outputs['Fac'], pudm.inputs['Value'])
wetpud = nt.nodes.new('ShaderNodeMath'); wetpud.operation = 'MULTIPLY'; L.new(pudm.outputs[0], wetpud.inputs[0]); L.new(WET, wetpud.inputs[1])
dark = nt.nodes.new('ShaderNodeMix'); dark.data_type = 'RGBA'; dark.blend_type = 'MULTIPLY'
dmul = nt.nodes.new('ShaderNodeMath'); dmul.operation = 'MULTIPLY'; dmul.inputs[1].default_value = 0.2; L.new(WET, dmul.inputs[0])
L.new(dmul.outputs[0], dark.inputs['Factor']); L.new(seamc.outputs[2], dark.inputs[6]); dark.inputs[7].default_value = (0.5, 0.5, 0.55, 1)
rough = nt.nodes.new('ShaderNodeMapRange')   # WET 0 -> 0.42, 1 -> 0.14
rough.inputs['To Min'].default_value = 0.42; rough.inputs['To Max'].default_value = 0.22
L.new(WET, rough.inputs['Value'])
rp = nt.nodes.new('ShaderNodeMix'); rp.data_type = 'FLOAT'
L.new(wetpud.outputs[0], rp.inputs['Factor']); L.new(rough.outputs[0], rp.inputs[2]); rp.inputs[3].default_value = 0.02
b = nt.nodes.new('ShaderNodeBsdfPrincipled')
b.inputs['Specular IOR Level'].default_value = 0.6
L.new(dark.outputs[2], b.inputs['Base Color']); L.new(rp.outputs[0], b.inputs['Roughness'])
# bump: grain + seams + rain ripples (4D noise, W = time)
TIME_V = nt.nodes.new('ShaderNodeValue'); TIME = TIME_V.outputs[0]
rip = nt.nodes.new('ShaderNodeTexNoise'); rip.noise_dimensions = '4D'; rip.inputs['Scale'].default_value = 1.6
rip.inputs['Detail'].default_value = 2
L.new(tco.outputs['Object'], rip.inputs['Vector']); L.new(TIME, rip.inputs['W'])
ripw = nt.nodes.new('ShaderNodeMath'); ripw.operation = 'MULTIPLY'; L.new(rip.outputs['Fac'], ripw.inputs[0]); L.new(WET, ripw.inputs[1])
hsum = nt.nodes.new('ShaderNodeMath'); hsum.operation = 'MULTIPLY_ADD'; hsum.inputs[1].default_value = 0.35
L.new(grain.outputs['Fac'], hsum.inputs[0]); L.new(ripw.outputs[0], hsum.inputs[2])
hs2 = nt.nodes.new('ShaderNodeMath'); hs2.operation = 'SUBTRACT'; L.new(hsum.outputs[0], hs2.inputs[0]); L.new(seam.outputs[0], hs2.inputs[1])
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.15; bump.inputs['Distance'].default_value = 0.05
L.new(hs2.outputs[0], bump.inputs['Height']); L.new(bump.outputs[0], b.inputs['Normal'])
L.new(b.outputs[0], out.inputs[0])
table_top = make_box('table_top', (TX, TY, 4.0), {}, tm, bevel=0.6)
table_top.location = (0, 0, -2.0)

# ---------------------------------------------------------------- Goosklerf cards
CW, CH = 6.3, 8.8
card_mat = mat_two_sided('card', TEX + '/gen_card.png', TEX + '/gen_card.png', rough=0.3, translucent=0.02, gloss=0.6, glow=0.05, alpha=True)

def card_R(normal, up):
    return frames_from(np.asarray(normal, float)[None], np.asarray(up, float)[None])[0]

def hinge_pose(base, n_up, axis, ang):
    """card standing on its bottom edge at `base` (centre of that edge), facing n_up when upright;
    rotated by `ang` about the edge axis (0 = upright)."""
    R0 = card_R(n_up, v3(0, 0, 1))
    Rr = rot_axis(np.asarray(axis, float)[None], np.array([ang]))[0]
    R = Rr @ R0
    return base + R @ v3(0, 0, CH / 2), R

CARDS = []   # dicts: kind, params

# the trench: two parallel walls along x, cards slam up in sequence as the camera runs
TR_X = [-9.0 + 6.55 * k for k in range(8)]
TR_Y = 2.7
def cam_x_run(t):
    return lerp(-26.0, 17.0, float(sm(T_S2, T_S3 - 0.6, t)))
_run_t = np.linspace(T_S2, T_S3, 400)
_run_x = np.array([cam_x_run(x) for x in _run_t])
for k, x in enumerate(TR_X):
    tu = T_S2 + 0.5 + 0.66 * k
    for s in (-1, 1):
        CARDS.append(dict(kind='slam', base=v3(x, s * TR_Y, 0.0), n=v3(0, -s, 0), ax=v3(s, 0, 0) * 0 + v3(1, 0, 0),
                          fall_sign=-s, t_up=tu + (0.16 if s > 0 else 0.0)))
# fortress squares (always standing) and the fortress that falls (F)
QS = [v3(60, 36, 0), v3(-22, 40, 0), v3(-84, -2, 0), v3(35, -38, 0), v3(84, 20, 0), v3(-40, -40, 0)]
F = v3(18.5, 29.0, 0)
def square(c, kind, t_fall=None):
    for j, (dx, dy) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
        nrm = v3(dx, dy, 0)
        base = c + nrm * (CW / 2 + 0.05)
        ax = np.cross(v3(0, 0, 1), nrm)
        d = dict(kind=kind, base=base, n=nrm, ax=ax)
        if t_fall is not None:
            d['t_fall'] = t_fall[j]; d['zoff'] = 0.03 * (j + 1)
        CARDS.append(d)
for q in QS:
    square(q, 'stand')
square(F, 'fall', t_fall=[T_FALL + 0.15, T_FALL + 0.7, T_FALL + 1.2, T_FALL + 0.45])
# dead cards lying about
for i in range(12):
    while True:
        x, y = rng.uniform(-90, 90), rng.uniform(-50, 50)
        if abs(y) > 8 and np.hypot(x - F[0], y - F[1]) > 9 and np.hypot(x - 16, y - 20) > 6 and np.hypot(x - 60, y + 36) > 25:
            break
    CARDS.append(dict(kind='flat', pos=v3(x, y, 0.02 + 0.001 * i), yaw=rng.uniform(0, 6.3)))
# the booster: 12 cards burst out of the pack towards the camera
PACK_C = v3(-60.0, -20.0, 0.0)          # standing upright, front towards +x: a dam
PACK_MOUTH = PACK_C + v3(0, 0, 11.2 - 0.3)
for i in range(12):
    a = rng.uniform(-0.45, 0.45)
    CARDS.append(dict(kind='boost', i=i, t0=T_TEAR + 0.07 * i + rng.uniform(0, 0.05), dir=v3(math.cos(a), math.sin(a), 0),
                      v=rng.uniform(9, 16), k=rng.uniform(1.6, 2.4), vz=rng.uniform(14, 24), yaw0=rng.uniform(-0.4, 0.4),
                      spin=rng.uniform(-4, 4), flips=int(rng.integers(1, 3)), tax=norm(rng.normal(size=3) * v3(1, 1, 0))))
CARDS[-1].update(kind='lens', t0=T_TEAR + 0.8)   # the last one comes straight into the lens
NC = len(CARDS)
cards = Sheets('cards', NC, CW, CH, [card_mat], np.zeros(NC, int), nx=2, nz=2, curl_ids=np.ones(NC, int))
G = 60.0   # giant gravity, cm/s^2 on screen: heavy, slow, huge

def boost_pose(c, t):
    tau = t - c['t0']
    if tau < 0:
        return PACK_C + v3(0, 0, 0.0), card_R(v3(0, 0, 1), v3(1, 0, 0))
    k, z0, zr = c['k'], PACK_MOUTH[2], 0.03 + 0.004 * c['i']
    t_air = (c['vz'] + math.sqrt(c['vz'] ** 2 + 2 * G * (z0 - zr))) / G
    if tau < t_air:
        d = c['v'] * tau
        z = z0 + c['vz'] * tau - 0.5 * G * tau * tau
    else:
        d = c['v'] * t_air + c['v'] / k * (1 - math.exp(-k * (tau - t_air)))
        z = zr
    p = PACK_MOUTH + c['dir'] * d
    tumble = c['flips'] * math.pi * min(tau / t_air, 1.0)
    yaw = c['yaw0'] + c['spin'] * min(tau, t_air + 1 / k)
    R0 = Rz(yaw) @ card_R(v3(0, 0, 1), v3(1, 0, 0))
    R = rot_axis(c['tax'][None], np.array([tumble]))[0] @ R0
    return v3(p[0], p[1], z), R

def lens_pose(c, t):
    tau = t - c['t0']
    if tau < 0:
        return PACK_C, card_R(v3(0, 0, 1), v3(1, 0, 0))
    D = 20.05 - c['t0']            # arrives at the lens on 20.05, the hidden cut into scene 4
    u = min(tau / D, 1.0)
    e_ = cam3_eye(T_S4 - 0.1)
    target = e_ + norm(PACK_MOUTH + v3(0, 0, 1.5) - e_) * 0.45
    p = lerp(PACK_MOUTH, target, u ** 1.2) + v3(0, 0, 9.0 * math.sin(math.pi * u) * (1 - u * 0.5))
    fwd = norm(target - PACK_MOUTH)
    spin = 9.0 * (1 - u)
    R = rot_axis(fwd[None], np.array([spin]))[0] @ card_R(-fwd, v3(0, 0, 1))
    if t >= T_S4:   # it lands behind the camera, out of the way
        return v3(-28, -18, 0.05), card_R(v3(0, 0, 1), v3(1, 0.3, 0))
    return p, R

def set_cards(t):
    P = np.zeros((NC, 3)); R = np.zeros((NC, 3, 3))
    for i, c in enumerate(CARDS):
        k = c['kind']
        if k == 'slam':
            u = t - c['t_up']
            if u < 0:
                ang = math.pi / 2
            else:
                a = min(u / 0.42, 1.0)
                ang = (math.pi / 2) * (1 - a * a)
                if u >= 0.42:
                    ang = -0.05 * math.exp(-(u - 0.42) * 7) * math.sin((u - 0.42) * 30)
            ang *= c['fall_sign']
            p, r = hinge_pose(c['base'], c['n'], c['ax'], ang)
            p[2] = max(p[2], 0.03)
        elif k == 'stand':
            p, r = hinge_pose(c['base'], c['n'], c['ax'], 0.0)
        elif k == 'fall':
            u = t - c['t_fall']
            a = min(max(u, 0) / 0.9, 1.0)
            ang = -(math.pi / 2) * a ** 2.2        # falls inward
            p, r = hinge_pose(c['base'], c['n'], c['ax'], ang)
            p = p + v3(0, 0, c['zoff'] * a)
            if a >= 1:
                bounce = 0.25 * math.exp(-(u - 0.9) * 9) * abs(math.sin((u - 0.9) * 18))
                p, r = hinge_pose(c['base'], c['n'], c['ax'], -(math.pi / 2) + bounce)
                p = p + v3(0, 0, c['zoff'])
        elif k == 'flat':
            p = c['pos']; r = Rz(c['yaw']) @ card_R(v3(0, 0, 1), v3(0, 1, 0))
        elif k == 'boost':
            p, r = boost_pose(c, t)
        else:
            p, r = lens_pose(c, t)
        P[i] = p; R[i] = r
    cards.set(P, R)

# ---------------------------------------------------------------- the booster pack
PW, PT, PH = 7.2, 0.9, 11.2
pack_front = mat_image('pack_front', TEX + '/gen_pack.png', rough=0.25, spec=0.8, coat=0.5)
pack_silver = mat_color('pack_silver', (0.78, 0.8, 0.84), rough=0.2, metal=1.0)
pack = make_box('pack', (PW, PT, PH - 1.1), {(0, -1, 0): pack_front, (0, 1, 0): pack_front}, pack_silver, bevel=0.12)
crimp = make_box('crimp', (PW + 0.2, 0.35, 1.1), {}, pack_silver, bevel=0.05)
mouth_mat = mat_emit('mouth', (1.0, 0.92, 0.8), 0.0)
MOUTH = mouth_mat.node_tree.nodes['Emission'].inputs[1]
mouth = mesh_obj('mouth', quad_mesh('mouthq'), mouth_mat)
PACK_R = Rz(math.pi / 2)   # upright, front towards +x
pack_hero = make_box('pack_hero', (PW, PT, PH), {(0, -1, 0): pack_front}, pack_silver, bevel=0.12)

def set_pack(t):
    strain = float(ss(15.6, T_TEAR, t)) if t < T_TEAR else 0.0
    jit = shake(t * 2.0, 0.08 * strain ** 2, 3.0)
    s = 1 + 0.10 * strain ** 2
    R = PACK_R.copy()
    M = np.eye(4); M[:3, :3] = R @ np.diag([1.0, s * 1.2, 1.0]); M[:3, 3] = PACK_C + v3(0, 0, (PH - 1.1) / 2) + jit * v3(1, 1, 0.3)
    pack.matrix_world = Matrix(M.tolist())
    top = PACK_C + v3(0, 0, PH - 0.55)
    if t < T_TEAR:
        place(crimp, top + jit, R)
    else:
        u = t - T_TEAR
        p = top + v3(6 * u, 4 * u, 26 * u - 0.5 * G * u * u)
        p[2] = max(p[2], 0.2)
        place(crimp, p, rot_axis(v3(0.3, 1, 0.2)[None], np.array([9 * u * math.exp(-u * 0.4)]))[0] @ R)
    # light from inside the pack at the tear
    k = math.exp(-max(t - T_TEAR, 0) * 1.6) if t >= T_TEAR else strain ** 3 * 0.05
    MOUTH.default_value = 60.0 * k if T_S3 <= t < T_S4 else 0.0
    M = np.eye(4); M[:3, :3] = Rz(math.pi / 2) @ Rx(math.pi / 2) @ np.diag([PW * 0.9, 1, 0.7]); M[:3, 3] = PACK_MOUTH + v3(0, 0, -0.2)
    mouth.matrix_world = Matrix(M.tolist()) if T_S3 <= t < T_S4 else Matrix.Translation(Vector(FAR))
    tearl.location = PACK_MOUTH + v3(1.0, 0, 2.0)
    tear_d.energy = 2.5e4 * k if T_S3 <= t < T_S4 else 0.0

# ---------------------------------------------------------------- dice
DIE = 1.6
PIP_OF = {(0, 0, 1): 1, (0, 0, -1): 6, (1, 0, 0): 2, (-1, 0, 0): 5, (0, 1, 0): 3, (0, -1, 0): 4}
die_mats = {nm: {n: mat_image(f'die_{nm}_{p}', f'{TEX}/die_{nm}_{p}.png', rough=0.18, spec=0.7, coat=0.7)
                 for n, p in PIP_OF.items()} for nm in ('teal', 'orange', 'purple')}
def new_die(name, col):
    fm = die_mats[col]
    return make_box(name, (DIE, DIE, DIE), fm, fm[(0, 0, 1)], bevel=0.18)
meteors = [new_die('meteor_teal', 'teal'), new_die('meteor_orange', 'orange'), new_die('meteor_purple', 'purple'), new_die('meteor_purple2', 'purple')]
hero_die = new_die('hero_die', 'orange')
prop_dice = [new_die('prop_teal', 'teal'), new_die('prop_purple', 'purple')]
UP_FACE = {1: np.eye(3), 6: Rx(math.pi), 2: Ry(-math.pi / 2), 5: Ry(math.pi / 2), 3: Rx(math.pi / 2), 4: Rx(-math.pi / 2)}

# meteor dice
CAM4 = v3(37.2, 0.0, 0.55)
IMP = [v3(61.0, -5.0, 0), v3(72.0, 9.0, 0), v3(55.5, 12.5, 0), v3(36.0, 46.0, 0)]
MSTART = [v3(150, -60, 330), v3(175, 60, 360), v3(120, 110, 340), v3(170, 140, 300)]
T_APPEAR = [21.1, 21.7, 22.3, 0.2]
MREST = [Rz(0.4) @ UP_FACE[3], Rz(-0.7) @ UP_FACE[6], Rz(1.1) @ UP_FACE[2], Rz(0.2) @ UP_FACE[4]]
MSPIN = [norm(v3(1, 0.3, 0.2)), norm(v3(-0.2, 1, 0.4)), norm(v3(0.5, -0.4, 1)), norm(v3(0.3, 1, -0.5))]
def meteor_pos(i, t):
    D = T_IMP[i] - T_APPEAR[i]
    u = max(T_IMP[i] - t, 0.0) / D
    return IMP[i] + v3(0, 0, DIE / 2 - 0.35) + (MSTART[i] - IMP[i]) * u ** 1.25

# trails: three tiers of emissive balls
trail_mats = [mat_emit('fire_core', (1.0, 0.85, 0.55), 60.0), mat_emit('fire_mid', (1.0, 0.38, 0.06), 30.0),
              mat_emit('fire_tail', (0.6, 0.08, 0.02), 10.0)]
NTR = 22
TIERS = [range(0, 4), range(4, 12), range(12, NTR)]
trails = [[Pool(f'trail{i}_{k}', len(TIERS[k]), ico_mesh(f'fireball{i}{k}', 1, trail_mats[k])) for k in range(3)] for i in range(4)]
# craters: scorched disc with glowing rim
cm_, nt, out = new_mat('crater')
tco2 = nt.nodes.new('ShaderNodeTexCoord')
vl = nt.nodes.new('ShaderNodeVectorMath'); vl.operation = 'LENGTH'; nt.links.new(tco2.outputs['Object'], vl.inputs[0])
cn = nt.nodes.new('ShaderNodeTexNoise'); cn.inputs['Scale'].default_value = 3.0; nt.links.new(tco2.outputs['Object'], cn.inputs['Vector'])
cadd = nt.nodes.new('ShaderNodeMath'); cadd.operation = 'MULTIPLY_ADD'; cadd.inputs[1].default_value = 0.35
nt.links.new(cn.outputs['Fac'], cadd.inputs[0]); nt.links.new(vl.outputs['Value'], cadd.inputs[2])
crr = nt.nodes.new('ShaderNodeValToRGB')
e0 = crr.color_ramp.elements[0]; e0.position = 0.3; e0.color = (0.004, 0.003, 0.002, 1)
e1 = crr.color_ramp.elements[1]; e1.position = 1.15; e1.color = (0.0, 0.0, 0.0, 0)
em_ = crr.color_ramp.elements.new(0.62); em_.color = (0.01, 0.006, 0.004, 1)
nt.links.new(cadd.outputs[0], crr.inputs[0])
glow = nt.nodes.new('ShaderNodeValToRGB')
g0 = glow.color_ramp.elements[0]; g0.position = 0.5; g0.color = (0, 0, 0, 1)
g1 = glow.color_ramp.elements[1]; g1.position = 0.95; g1.color = (0, 0, 0, 1)
gm_ = glow.color_ramp.elements.new(0.72); gm_.color = (1.0, 0.3, 0.05, 1)
nt.links.new(cadd.outputs[0], glow.inputs[0])
cb = nt.nodes.new('ShaderNodeBsdfPrincipled'); cb.inputs['Roughness'].default_value = 0.8
nt.links.new(crr.outputs[0], cb.inputs['Base Color'])
nt.links.new(glow.outputs[0], cb.inputs['Emission Color'])
EMBER = cb.inputs['Emission Strength']
tp = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(crr.outputs['Alpha'], mx.inputs[0]); nt.links.new(tp.outputs[0], mx.inputs[1]); nt.links.new(cb.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs[0])
cm_.blend_method = 'CLIP'; cm_.shadow_method = 'NONE'
disc = bpy.data.meshes.new('disc')
bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=1.0); bm.to_mesh(disc); bm.free()
disc.materials.append(cm_)
craters = [mesh_obj(f'crater{i}', disc) for i in range(4)]
CR_R = [4.2, 3.8, 3.5, 4.4]
# shockwave rings
ring_me = bpy.data.meshes.new('ring')
bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=False, segments=72, radius=1.0)
ret = bmesh.ops.extrude_edge_only(bm, edges=bm.edges[:])
for vv in [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]:
    vv.co *= 0.82
bm.to_mesh(ring_me); bm.free()
ring_mat, RING_STR, RING_MIX = transparent_mat('ring', (1.0, 0.7, 0.45), 8.0, 0.6)
ring_me.materials.append(ring_mat)
rings = [mesh_obj(f'ring{i}', ring_me) for i in range(4)]

# ---------------------------------------------------------------- particles: splinters and water
wood_mat = mat_color('splinter', (0.28, 0.14, 0.06), rough=0.6)
NSPL = 26
splinters = Pool('splinter', NSPL * 4, cube_mesh('splinter_m', wood_mat))
SP_V = rng.normal(size=(NSPL * 4, 3)) * v3(9, 9, 0) ; SP_V[:, 2] = rng.uniform(10, 30, NSPL * 4)
SP_S = np.stack([rng.uniform(0.08, 0.2, NSPL * 4), rng.uniform(0.08, 0.2, NSPL * 4), rng.uniform(0.3, 1.1, NSPL * 4)], -1)
SP_AX = norm(rng.normal(size=(NSPL * 4, 3))); SP_W = rng.uniform(4, 14, NSPL * 4)

drop_mat, nt, out = new_mat('water')
bw = nt.nodes.new('ShaderNodeBsdfPrincipled'); bw.inputs['Base Color'].default_value = (0.6, 0.7, 0.8, 1)
bw.inputs['Roughness'].default_value = 0.05; bw.inputs['Specular IOR Level'].default_value = 1.0
bw.inputs['Emission Color'].default_value = (0.6, 0.7, 0.85, 1)
DROP_GLOW = bw.inputs['Emission Strength']
nt.links.new(bw.outputs[0], out.inputs[0])
# bursts: (t0, origin, n, speed, up, size, clock)   clock 'ts' = runs on the slow-motion clock
BURSTS = []
for c in CARDS:
    if c['kind'] == 'slam':
        BURSTS.append((c['t_up'] + 0.42, c['base'] + c['n'] * 0.6, 6, 7.0, 9.0, 0.10, 't'))
BURSTS.append((T_TEAR, PACK_MOUTH, 30, 9.0, 16.0, 0.13, 't'))
for c in CARDS:
    if c['kind'] == 'boost':
        z0, zr = PACK_MOUTH[2], 0.03 + 0.004 * c['i']
        c['t_air'] = (c['vz'] + math.sqrt(c['vz'] ** 2 + 2 * G * (z0 - zr))) / G
        BURSTS.append((c['t0'] + c['t_air'], boost_pose(c, c['t0'] + c['t_air'])[0] * v3(1, 1, 0), 6, 7.0, 6.0, 0.10, 't'))
for i in range(4):
    BURSTS.append((T_IMP[i], IMP[i], 18, 14.0, 22.0, 0.16, 't'))
T_LAND_TS = ts(T_LAND)
BURSTS.append((T_LAND, v3(16.0, 20.0, 0.0), 40, 8.0, 12.0, 0.09, 'ts'))
BURSTS.append((T_LAND + 0.5, v3(16.5, 20.3, 0.0), 14, 4.0, 5.0, 0.07, 'ts'))
NDROP = sum(bb[2] for bb in BURSTS)
drops = Pool('drop', NDROP, ico_mesh('drop_m', 1, drop_mat))
D_DIR = rng.normal(size=(NDROP, 3)); D_DIR[:, 2] = 0; D_DIR = norm(D_DIR)
D_SP = rng.uniform(0.3, 1.0, NDROP); D_UP = rng.uniform(0.4, 1.0, NDROP); D_SZ = rng.uniform(0.5, 1.2, NDROP)
BURST_T = [(ts(bb[0]) if bb[6] == 'ts' else bb[0]) for bb in BURSTS]

def set_drops(t):
    P = np.repeat(FAR[None], NDROP, 0); S = np.full(NDROP, 0.001); j = 0
    tsn = ts(t)
    for (t0, o, n, sp, up, sz, clk), tb in zip(BURSTS, BURST_T):
        tau = (tsn if clk == 'ts' else t) - tb
        if 0 <= tau < 3.0:
            sl = slice(j, j + n)
            v = D_DIR[sl] * (sp * D_SP[sl])[:, None]
            z = up * D_UP[sl] * tau - 0.5 * G * tau * tau
            p = o[None] + v * tau + np.stack([np.zeros(n), np.zeros(n), z], -1)
            alive = z > -0.05
            P[sl] = np.where(alive[:, None], p, FAR[None])
            S[sl] = np.where(alive, sz * D_SZ[sl], 0.001)
        j += n
    drops.set(P, scale=S)

def set_splinters(t):
    P = np.repeat(FAR[None], NSPL * 4, 0); R = np.repeat(np.eye(3)[None], NSPL * 4, 0); S = np.full((NSPL * 4, 3), 0.001)
    for i in range(4):
        tau = t - T_IMP[i]
        if tau < 0 or t >= T_S5:
            continue
        sl = slice(i * NSPL, (i + 1) * NSPL)
        t_hit = 2 * SP_V[sl, 2] / G
        tc_ = np.minimum(tau, t_hit)
        p = IMP[i][None] + SP_V[sl] * tc_[:, None] * v3(1, 1, 0) + np.stack([0 * tc_, 0 * tc_, SP_V[sl, 2] * tc_ - 0.5 * G * tc_ ** 2 + 0.1], -1)
        P[sl] = p
        R[sl] = rot_axis(SP_AX[sl], SP_W[sl] * tc_)
        S[sl] = SP_S[sl]
    splinters.set(P, R, S)

# ---------------------------------------------------------------- rain
rain_mat, RAIN_GLOW, _ = transparent_mat('rain', (0.75, 0.82, 1.0), 1.0, 0.45)
NR = 520
rain = Pool('rain', NR, quad_mesh('rainq', rain_mat))
R_BASE = rng.uniform(0, 1, (NR, 3)); R_V = rng.uniform(0.85, 1.15, NR)
RAIN_BOX = v3(26, 26, 16)
WIND = v3(0.18, 0.08, -1.0)

def set_rain(t, eye, amount):
    if amount <= 0.001:
        rain.hide(); return
    tsn = ts(t)
    vel = 42.0
    p = R_BASE * RAIN_BOX + (norm(WIND)[None] * vel * R_V[:, None]) * tsn
    p = (p % RAIN_BOX) - RAIN_BOX / 2
    p = p + v3(eye[0], eye[1], eye[2] + 4.0)
    rate = float(np.interp(t, _TT, _RATE))
    ln = 1.1 * rate + 0.05
    hor = np.hypot(p[:, 0] - eye[0], p[:, 1] - eye[1])
    keep = (p[:, 2] > 0.02) & (hor > 0.5) & (np.arange(NR) < NR * amount)
    Z = np.repeat(norm(WIND)[None], NR, 0) * -1
    tocam = norm(eye[None] - p)
    X = norm(np.cross(Z, tocam)); Y = np.cross(Z, X)
    R = np.stack([X, Y, Z], -1)
    S = np.stack([np.full(NR, 0.012), np.ones(NR), np.full(NR, ln)], -1)
    P = np.where(keep[:, None], p, FAR[None])
    rain.set(P, R, S)

# ---------------------------------------------------------------- lightning bolts in the sky
def bolt_curve(name, seed, mat):
    r = np.random.default_rng(seed)
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 1.6; cu.bevel_resolution = 0
    def branch(p0, d, n, step):
        sp = cu.splines.new('POLY'); pts = [p0]
        p = p0.copy()
        for i in range(n):
            p = p + d * step + r.normal(size=3) * v3(1, 1, 0.3) * step * 0.45
            pts.append(p.copy())
        sp.points.add(len(pts) - 1)
        for pt, q in zip(sp.points, pts):
            pt.co = (*q, 1)
        return pts
    main = branch(v3(0, 0, 0), v3(0, 0, -1), 26, 40.0)
    for k in (6, 11, 17):
        branch(main[k], norm(v3(r.uniform(-1, 1), r.uniform(-1, 1), -1.2)), 8, 30.0)
    cu.materials.append(mat)
    return link(bpy.data.objects.new(name, cu))
bolt_mats = [mat_emit(f'bolt{c}', tuple(0.5 + 0.5 * x for x in COLS[c]), 40.0) for c in range(3)]
bolts = [bolt_curve(f'bolt{k}', 100 + k, bolt_mats[k % 3]) for k in range(6)]
for bo in bolts:
    bo.visible_shadow = False

# ---------------------------------------------------------------- the rulebook (generic)
RB = v3(-55.0, 32.0, 0.0)
RBW, RBH, RBT = 15.0, 21.0, 0.9
rb_front = mat_image('rb_front', MYTEX + '/rulebook_front.png', rough=0.45, spec=0.4, coat=0.3)
rb_back = mat_image('rb_back', MYTEX + '/rulebook_back.png', rough=0.45)
rb_spine = mat_image('rb_spine', MYTEX + '/rulebook_spine.png', rough=0.45)
rb_inside = mat_color('rb_inside', (0.55, 0.52, 0.47), rough=0.8)
rb_purple = mat_color('rb_purple', (0.033, 0.0, 0.168), rough=0.45)
pm, nt, out = new_mat('rb_page')
pt_ = nt.nodes.new('ShaderNodeTexImage'); pt_.image = img(MYTEX + '/rulebook_page.png')
pb = nt.nodes.new('ShaderNodeBsdfPrincipled'); pb.inputs['Roughness'].default_value = 0.85
nt.links.new(pt_.outputs[0], pb.inputs['Base Color']); nt.links.new(pt_.outputs[0], pb.inputs['Emission Color'])
PAGE_EMIT = pb.inputs['Emission Strength']
nt.links.new(pb.outputs[0], out.inputs[0])
cover = make_box('rb_cover', (RBW, 0.18, RBH), {(0, -1, 0): rb_front, (0, 1, 0): rb_inside}, rb_purple, bevel=0.04)
rb_block = make_box('rb_block', (RBW - 0.3, RBT - 0.4, RBH - 0.3), {(0, -1, 0): pm}, rb_inside)
rb_backb = make_box('rb_backb', (RBW, 0.18, RBH), {(0, 1, 0): rb_back}, rb_purple, bevel=0.04)
rb_spineb = make_box('rb_spineb', (0.18, RBT, RBH), {(-1, 0, 0): rb_spine}, rb_purple, bevel=0.04)
HINGE = RB + v3(-RBW / 2, -RBT / 2 + 0.09, 0)
def rb_angle(t):
    if t < T_OPEN:
        return 0.0
    u = (t - T_OPEN) / 3.2
    return math.radians(118) * float(sm(0, 1, u)) + (math.radians(-3) * math.exp(-(t - T_OPEN - 3.2) * 3) * math.sin((t - T_OPEN - 3.2) * 9) if u > 1 else 0)
mote_mat = mat_emit('mote', (1.0, 0.75, 0.4), 18.0)
NMOTE = 70
motes = Pool('mote', NMOTE, ico_mesh('mote_m', 1, mote_mat))
MO_B = rng.uniform(0, 1, (NMOTE, 3)); MO_W = rng.uniform(0.3, 0.9, NMOTE); MO_S = rng.uniform(0.02, 0.06, NMOTE)
def set_motes(t):
    k = float(ss(T_OPEN + 0.8, T_OPEN + 2.5, t))
    if not (T_OPEN < t < T_S6) or k <= 0:
        motes.hide(); return
    box = v3(16.0, 14.0, 20.0)
    p = MO_B * box + v3(0.3, 0.2, 1.0)[None] * (MO_W * (t - T_OPEN))[:, None]
    p = (p % box) - box / 2
    p = RB + v3(-2.0, -8.0, 10.0) + p + 0.4 * np.stack([np.sin(t * MO_W * 2 + MO_B[:, 0] * 9), np.cos(t * MO_W * 1.7 + MO_B[:, 1] * 9), 0 * MO_W], -1)
    motes.set(p, scale=MO_S * k)

def set_rulebook(t):
    place(rb_backb, RB + v3(0, RBT / 2 - 0.09, RBH / 2))
    place(rb_block, RB + v3(0.1, 0, RBH / 2))
    place(rb_spineb, RB + v3(-RBW / 2 + 0.09, 0, RBH / 2))
    a = rb_angle(t)
    R = Rz(-a)
    place(cover, HINGE + R @ v3(RBW / 2, 0, RBH / 2), R)
    k = float(ss(T_OPEN + 0.2, T_OPEN + 2.8, t))
    flick = 1 + 0.06 * math.sin(t * 23) * math.sin(t * 7.1)
    on = k * flick * (1 - float(ss(T_S7, T_REVEAL, t)))
    PAGE_EMIT.default_value = 0.14 * on + (0.6 if t >= T_REVEAL else 0)
    gold.location = RB + v3(-2.0, -3.5, 11.0)
    gold_d.energy = 3.5e3 * on

# ---------------------------------------------------------------- the room (parked until the reveal)
FLOOR_Z = -76.0
ROOM = link(bpy.data.objects.new('ROOM', None))
def room_part(ob, loc, rot=None):
    ob.parent = ROOM
    ob.location = loc
    if rot is not None:
        ob.rotation_euler = rot
    return ob
floor_mat, nt, out = new_mat('floor')
ftc = nt.nodes.new('ShaderNodeTexCoord')
fw = nt.nodes.new('ShaderNodeTexWave'); fw.wave_type = 'BANDS'; fw.bands_direction = 'X'
fw.inputs['Scale'].default_value = 0.02; fw.inputs['Distortion'].default_value = 2.0
nt.links.new(ftc.outputs['Object'], fw.inputs['Vector'])
fr_ = nt.nodes.new('ShaderNodeValToRGB')
fr_.color_ramp.elements[0].color = (0.10, 0.055, 0.03, 1); fr_.color_ramp.elements[1].color = (0.22, 0.13, 0.07, 1)
nt.links.new(fw.outputs['Fac'], fr_.inputs[0])
fb_ = nt.nodes.new('ShaderNodeBsdfPrincipled'); fb_.inputs['Roughness'].default_value = 0.45
nt.links.new(fr_.outputs[0], fb_.inputs['Base Color']); nt.links.new(fb_.outputs[0], out.inputs[0])
wall_mat = mat_color('wall', (0.12, 0.16, 0.14), rough=0.85)
ceil_mat = mat_color('ceiling', (0.5, 0.5, 0.48), rough=0.9)
trim_mat = mat_color('trim', (0.75, 0.73, 0.68), rough=0.5)
door_mat = mat_color('door', (0.55, 0.53, 0.48), rough=0.55)
oak_mat = mat_color('oak', (0.09, 0.045, 0.02), rough=0.4)
RX0, RX1, RY0, RY1, RZ1 = -300.0, 300.0, -260.0, 240.0, 184.0
room_part(make_box('floor', (RX1 - RX0, RY1 - RY0, 2), {}, floor_mat), (0, (RY0 + RY1) / 2, FLOOR_Z - 1))
room_part(make_box('ceiling', (RX1 - RX0, RY1 - RY0, 2), {}, ceil_mat), (0, (RY0 + RY1) / 2, RZ1 + 1))
WH = RZ1 - FLOOR_Z
room_part(make_box('wall_back', (RX1 - RX0, 2, WH), {}, wall_mat), (0, RY1 + 1, FLOOR_Z + WH / 2))
room_part(make_box('wall_front', (RX1 - RX0, 2, WH), {}, wall_mat), (0, RY0 - 1, FLOOR_Z + WH / 2))
room_part(make_box('wall_right', (2, RY1 - RY0, WH), {}, wall_mat), (RX1 + 1, (RY0 + RY1) / 2, FLOOR_Z + WH / 2))
# left wall with a door opening: three pieces around the door (door at y -100..-15, up to 205 cm)
DY0, DY1, DH = -100.0, -15.0, 205.0
room_part(make_box('wall_l1', (2, DY0 - RY0, WH), {}, wall_mat), (RX0 - 1, (RY0 + DY0) / 2, FLOOR_Z + WH / 2))
room_part(make_box('wall_l2', (2, RY1 - DY1, WH), {}, wall_mat), (RX0 - 1, (DY1 + RY1) / 2, FLOOR_Z + WH / 2))
room_part(make_box('wall_l3', (2, DY1 - DY0, WH - DH), {}, wall_mat), (RX0 - 1, (DY0 + DY1) / 2, FLOOR_Z + DH + (WH - DH) / 2))
room_part(make_box('door', (3, DY1 - DY0 - 1, DH - 1.6), {}, door_mat, bevel=0.3), (RX0 - 2.5, (DY0 + DY1) / 2, FLOOR_Z + 1.6 + (DH - 1.6) / 2))
room_part(make_box('knob', (3, 3, 3), {}, mat_color('brass', (0.8, 0.6, 0.3), rough=0.25, metal=1.0), bevel=1.0), (RX0 + 0.5, DY1 - 9, FLOOR_Z + 100))
hall_mat = mat_emit('hall', (1.0, 0.78, 0.5), 4.0)
room_part(make_box('hall_gap', (1, DY1 - DY0 - 2, 1.4), {}, hall_mat), (RX0 - 4.5, (DY0 + DY1) / 2, FLOOR_Z + 0.7))
room_part(make_box('hall_floor', (60, DY1 - DY0, 1), {}, mat_emit('hallf', (1.0, 0.78, 0.5), 0.8)), (RX0 - 34, (DY0 + DY1) / 2, FLOOR_Z - 0.4))
for nm, (ly, lz, sy, sz) in {'jamb1': (DY0 - 3, DH / 2, 6, DH), 'jamb2': (DY1 + 3, DH / 2, 6, DH), 'lintel': ((DY0 + DY1) / 2, DH + 3, DY1 - DY0 + 12, 6)}.items():
    room_part(make_box(nm, (3, sy, sz), {}, trim_mat), (RX0 + 0.5, ly, FLOOR_Z + lz))
room_part(make_box('skirting', (2, RY1 - RY0, 12), {}, trim_mat), (RX1 - 0.5, (RY0 + RY1) / 2, FLOOR_Z + 6))
room_part(make_box('skirting_b', (RX1 - RX0, 2, 12), {}, trim_mat), (0, RY1 - 0.5, FLOOR_Z + 6))
# window in the back wall: night outside, rain on the glass
gm2, nt, out = new_mat('glass')
gtc = nt.nodes.new('ShaderNodeTexCoord')
gmap = nt.nodes.new('ShaderNodeMapping'); gmap.inputs['Scale'].default_value = (1.0, 1.0, 0.08)
nt.links.new(gtc.outputs['Object'], gmap.inputs[0])
gn = nt.nodes.new('ShaderNodeTexNoise'); gn.inputs['Scale'].default_value = 0.22; gn.inputs['Detail'].default_value = 2
nt.links.new(gmap.outputs[0], gn.inputs['Vector'])
gr2 = nt.nodes.new('ShaderNodeValToRGB')
gr2.color_ramp.elements[0].position = 0.55; gr2.color_ramp.elements[0].color = (0.006, 0.012, 0.03, 1)
gr2.color_ramp.elements[1].position = 0.7; gr2.color_ramp.elements[1].color = (0.05, 0.08, 0.14, 1)
nt.links.new(gn.outputs['Fac'], gr2.inputs[0])
ge = nt.nodes.new('ShaderNodeEmission'); ge.inputs[1].default_value = 1.0
nt.links.new(gr2.outputs[0], ge.inputs[0])
gg = nt.nodes.new('ShaderNodeBsdfGlossy'); gg.inputs['Roughness'].default_value = 0.05
ga = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(ge.outputs[0], ga.inputs[0]); nt.links.new(gg.outputs[0], ga.inputs[1])
nt.links.new(ga.outputs[0], out.inputs[0])
WX, WZ0, WW, WHh = 60.0, 20.0, 120.0, 120.0
room_part(make_box('glass', (WW, 1, WHh), {}, gm2), (WX, RY1 - 0.2, FLOOR_Z + 90 + WHh / 2))
for nm, (lx, lz, sx, sz) in {'wf_l': (WX - WW / 2 - 3, WHh / 2, 6, WHh + 12), 'wf_r': (WX + WW / 2 + 3, WHh / 2, 6, WHh + 12),
                             'wf_t': (WX, WHh + 3, WW + 12, 6), 'wf_b': (WX, -3, WW + 20, 7), 'wf_m': (WX, WHh / 2, 4, WHh), 'wf_h': (WX, WHh / 2, WW, 4)}.items():
    room_part(make_box(nm, (sx, 6, sz), {}, trim_mat), (lx, RY1 - 2, FLOOR_Z + 90 + lz))
# table legs and apron
for sx in (-1, 1):
    for sy in (-1, 1):
        room_part(make_box(f'leg{sx}{sy}', (7, 7, 72), {}, oak_mat), (sx * (TX / 2 - 9), sy * (TY / 2 - 9), -4 - 36))
room_part(make_box('apron1', (TX - 20, 3, 10), {}, oak_mat), (0, -(TY / 2 - 9), -9))
room_part(make_box('apron2', (TX - 20, 3, 10), {}, oak_mat), (0, (TY / 2 - 9), -9))
# chairs
def chair(name, x, y, face):
    parts = [('seat', (44, 42, 4), (0, 0, 46 - 2)), ('back', (44, 4, 50), (0, 21 * face, 46 + 25)),
             ('l1', (4, 4, 44), (-19, -18, 22)), ('l2', (4, 4, 44), (19, -18, 22)), ('l3', (4, 4, 44), (-19, 18, 22)), ('l4', (4, 4, 44), (19, 18, 22))]
    for pn, size, off in parts:
        room_part(make_box(f'{name}_{pn}', size, {}, oak_mat, bevel=0.4), (x + off[0], y + off[1], FLOOR_Z + off[2]))
chair('chairA', -30, -88, -1); chair('chairB', 40, 90, 1)
# pendant lamp
LAMP = v3(0, 0, 70.0)
shade_mat = mat_color('shade', (0.02, 0.09, 0.07), rough=0.35, metal=0.6)
sh = bpy.data.meshes.new('shade')
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, cap_tris=False, segments=48, radius1=24.0, radius2=6.0, depth=20.0); bm.to_mesh(sh); bm.free()
sh.materials.append(shade_mat); sh.polygons.foreach_set('use_smooth', np.ones(len(sh.polygons), bool))
shade_ob = room_part(link(bpy.data.objects.new('shade', sh)), tuple(LAMP + v3(0, 0, 8)))
shade_ob.modifiers.new('solid', 'SOLIDIFY').thickness = 0.5
room_part(make_box('cord', (0.6, 0.6, RZ1 - LAMP[2] - 18), {}, mat_color('cord', (0.02, 0.02, 0.02))), (0, 0, (RZ1 + LAMP[2] + 18) / 2))
bulb = room_part(mesh_obj('bulb', ico_mesh('bulbm', 2, mat_emit('bulb', (1.0, 0.8, 0.55), 60.0))), tuple(LAMP + v3(0, 0, 2)))
bulb.scale = (4, 4, 4); bulb.visible_shadow = False
lamp_d = bpy.data.lights.new('pendant', 'SPOT'); lamp_d.color = (1.0, 0.72, 0.45); lamp_d.spot_size = math.radians(150)
lamp_d.spot_blend = 0.6; lamp_d.shadow_soft_size = 3.0; lamp_d.energy = 0
lamp = link(bpy.data.objects.new('pendant', lamp_d)); lamp.location = tuple(LAMP + v3(0, 0, -2))
room_d = bpy.data.lights.new('roomfill', 'POINT'); room_d.color = (1.0, 0.75, 0.5); room_d.shadow_soft_size = 30; room_d.energy = 0
room_d.use_shadow = False
roomfill = link(bpy.data.objects.new('roomfill', room_d)); roomfill.location = (0, 0, 150)
door_d = bpy.data.lights.new('doorlight', 'AREA'); door_d.shape = 'RECTANGLE'; door_d.size = 2; door_d.size_y = 80
door_d.color = (1.0, 0.75, 0.45); door_d.energy = 0
doorl = link(bpy.data.objects.new('doorlight', door_d)); doorl.location = (RX0 + 1, (DY0 + DY1) / 2, FLOOR_Z + 1.5)
doorl.rotation_euler = (0, math.radians(-90), 0)
win_d = bpy.data.lights.new('window', 'AREA'); win_d.shape = 'RECTANGLE'; win_d.size = WW; win_d.size_y = WHh
win_d.color = (0.45, 0.6, 1.0); win_d.energy = 0
winl = link(bpy.data.objects.new('windowlight', win_d)); winl.location = (WX, RY1 - 3, FLOOR_Z + 90 + WHh / 2)
winl.rotation_euler = (math.radians(-90), 0, 0)

# things that are on the table in the room: Book 2, a mug, the hero products
BW, BT, BH = 26.0, 2.4, 19.5
book_front = mat_image('b2_front', TEX + '/gen_book_front.png', rough=0.55, spec=0.3, coat=0.04)
book_back = mat_image('b2_back', TEX + '/gen_book_back.png', rough=0.45, spec=0.35, coat=0.15)
book_spine = mat_image('b2_spine', TEX + '/gen_book_spine.png', rough=0.45, spec=0.35, coat=0.15)
pages_mat = mat_color('b2_pages', (0.88, 0.85, 0.78), rough=0.9)
book2 = make_box('book2', (BW, BT, BH), {(0, -1, 0): book_front, (0, 1, 0): book_back, (-1, 0, 0): book_spine}, pages_mat, bevel=0.12)
H_C = v3(60.0, -34.0, 0.0)
BOOK_R = Rz(math.radians(9)) @ Rx(-math.pi / 2)
mug_me = bpy.data.meshes.new('mug')
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=4.2, radius2=4.2, depth=9.5); bm.to_mesh(mug_me); bm.free()
mug_me.materials.append(mat_color('ceramic', (0.85, 0.84, 0.8), rough=0.15))
mug_me.polygons.foreach_set('use_smooth', np.ones(len(mug_me.polygons), bool))
mug = mesh_obj('mug', mug_me)
comic_mat = mat_two_sided('comic', TEX + '/comic_01.png', TEX + '/comic_01.png', translucent=0.05, glow=0.08)
comic = Sheets('comic', 1, 28.0, 21.6, [comic_mat], [0], curl_ids=[1])

def set_room(t):
    on = t >= T_REVEAL
    ROOM.location = (0, 0, 0) if on else tuple(FAR)
    lamp_up = float(ss(T_S7 + 0.3, T_REVEAL + 2.0, t))
    lamp_d.energy = 1.1e6 * lamp_up
    room_d.energy = 2.0e6 * lamp_up
    door_d.energy = 8.0e4 * lamp_up
    win_d.energy = 3.0e5 * lamp_up
    if on:
        place(book2, H_C + v3(0, 0, BT / 2 + 0.01), BOOK_R)
        place(mug, v3(-76.0, -30.0, 4.76))
        place(pack_hero, H_C + v3(17.5, -8.0, PT / 2 + 0.02), Rz(math.radians(-28)) @ Rx(-math.pi / 2))
        place(prop_dice[0], H_C + v3(-6.0, -14.2, DIE / 2), Rz(0.5) @ UP_FACE[5])
        place(prop_dice[1], H_C + v3(-2.2, -15.6, DIE / 2), Rz(-0.3) @ UP_FACE[3])
    else:
        for ob in (book2, mug, pack_hero, prop_dice[0], prop_dice[1]):
            place(ob, FAR)
    # the dispatch slides in under the door
    if t >= T_S8 - 0.1:
        u = float(sm(T_SLIDE, T_SLIDE + 2.2, t))
        x = lerp(RX0 - 16.0, RX0 + 40.0, u)
        yaw = lerp(0.25, -0.08, u)
        p = v3(x, lerp(-52.0, -60.0, u), FLOOR_Z + 0.25)
        R = Rz(yaw) @ card_R(v3(0, 0, 1), v3(-1, 0, 0))
        comic.set(p[None], R[None])
    else:
        comic.set(FAR[None], np.eye(3)[None])

# ---------------------------------------------------------------- camera
cam, cam_d = make_camera(clip_end=12000)
cam_d.clip_start = 0.02
cam_d.dof.use_dof = True
cam_d.dof.aperture_fstop = 128.0

def cam3_eye(t):
    u = float(sm(T_S3, T_S4, t))
    return lerp(v3(-38.0, -17.2, 1.0), v3(-39.5, -17.6, 0.8), u)

def die_state(t):
    """the hero die on the slow-motion clock: flight, two hops, settle. returns pos, R"""
    t0, t1 = ts(T_THROW), T_LAND_TS
    tsn = max(ts(t), t0)
    Tf = t1 - t0
    P0 = v3(3.0, 15.5, 7.5); P1 = v3(15.2, 19.6, DIE / 2)
    Rf = Rz(0.35) @ UP_FACE[5]
    ax = norm(v3(0.4, -1.0, 0.3))
    t_rest = t1 + 0.62
    spin = 26.0 * max(t_rest - tsn, 0.0) ** 1.35 + 0.0
    R = rot_axis(ax[None], np.array([spin]))[0] @ Rf
    if tsn < t1:
        u = tsn - t0
        vz = (P1[2] - P0[2] + 0.5 * G * 3.0 * Tf * Tf) / Tf
        p = P0 + (P1 - P0) * v3(1, 1, 0) * (u / Tf) + v3(0, 0, vz * u - 0.5 * G * 3.0 * u * u)
        return p, R
    s = tsn - t1
    hops = [(0.0, 0.26, 0.55, v3(0.45, 0.25, 0)), (0.26, 0.40, 0.14, v3(0.2, 0.1, 0)), (0.40, 0.62, 0.0, v3(0.15, 0.05, 0))]
    acc = v3(0, 0, 0)
    for a, bnd, hh, dxy in hops:
        if s < bnd:
            u = (s - a) / (bnd - a)
            uu = u if hh > 0 else 1 - (1 - u) ** 2
            return P1 + acc + dxy * uu + v3(0, 0, 4 * hh * u * (1 - u)), R
        acc = acc + dxy
    return P1 + acc, Rf
DIE_REST = die_state(80.0)[0]

def meteor_track(t):
    """point the camera follows while the meteors fall"""
    return meteor_pos(0, t)

def camera_at(t):
    """eye, target, lens (16:9-authored), roll, focus distance (None = no depth of field)"""
    if t < T_S2:   # 1. the night plain
        u = float(sm(-0.6, T_S2 - 0.2, t))
        P0, P1, P2 = v3(-96.0, -30.0, 30.0), v3(-72.0, 6.0, 7.0), v3(-35.0, 13.0, 0.45)
        eye = (1 - u) ** 2 * P0 + 2 * u * (1 - u) * P1 + u * u * P2
        tgt = lerp(v3(18.0, 30.0, 0.0), v3(-21.0, 40.0, 5.0), float(sm(1.5, T_S2 - 0.3, t)))
        k = math.exp(-max(t - T_IMP[3], 0) * 3.0) if t >= T_IMP[3] else 0.0
        eye = eye + shake(t, 0.03 + 0.5 * k * (0.3 + eye[2] / 40), 1.6)
        return eye, tgt, lerp(20.0, 30.0, u), lerp(-0.08, 0.02, u) + 0.02 * math.sin(t * 0.4), None
    if t < T_S3:   # 2. the run down the trench
        x = cam_x_run(t)
        step = math.sin((t - T_S2) * 2 * math.pi * 1.9)
        eye = v3(x, 0.25 * math.sin(t * 1.3), 0.62 + 0.06 * abs(step)) + shake(t, 0.03, 1.2)
        up = float(sm(13.3, T_S3, t))
        tgt = eye + v3(10.0, 0.6 * math.sin(t * 0.9), lerp(0.7, 9.0, up))
        amp = 0.0
        for c in CARDS:
            if c['kind'] == 'slam':
                d = t - c['t_up'] - 0.42
                if 0 <= d < 0.35:
                    amp += 0.05 * (1 - d / 0.35)
        return eye + shake(t, amp, 2.0), tgt, lerp(20.0, 17.0, up), lerp(0.0, 0.12, up) + 0.03 * step, None
    if t < T_S4:   # 3. reinforcements
        eye = cam3_eye(t)
        tgt = PACK_C + v3(0, 0, lerp(6.0, 8.5, float(sm(16.9, 17.3, t))) - 1.5 * float(sm(18.0, 19.5, t)))
        zoom = float(sm(16.9, 17.25, t)) * (1 - float(sm(17.6, 18.3, t)))
        lens = lerp(30.0, 48.0, zoom) - 6.0 * float(sm(17.6, 19.0, t))
        k = math.exp(-max(t - T_TEAR, 0) * 2.5) if t >= T_TEAR else 0.0
        strain = float(ss(15.6, T_TEAR, t)) * 0.02
        return eye + shake(t, 0.05 * k + strain, 1.7), tgt + shake(t + 4, 0.2 * k, 1.3), lens, 0.0, None
    if t < T_S5:   # 4. the dice come down
        eye = CAM4.copy()
        look_sky = eye + v3(18.0, 1.0, 34.0)
        follow = meteor_track(min(t, T_IMP[0] - 0.05))
        w = float(sm(21.8, 24.2, t))
        tgt = lerp(look_sky, lerp(look_sky, follow, 0.85), w)
        after = float(sm(T_IMP[0] + 0.3, T_IMP[2] + 0.4, t))
        tgt = lerp(tgt, v3(63.0, 3.0, 1.5), after)
        crash = float(sm(23.55, 23.8, t)) * (1 - float(sm(T_IMP[0] - 0.1, T_IMP[0] + 0.35, t)))
        lens = lerp(20.0, 44.0, crash)
        creep = float(sm(28.8, T_S5, t))
        eye = lerp(eye, v3(42.0, -1.2, 0.75), creep)
        tgt = lerp(tgt, IMP[0] + v3(0, 0, 1.2), creep)
        lens = lerp(lens, 28.0, creep)
        amp = 0.0
        for ti in T_IMP:
            if t >= ti:
                amp += 0.35 * math.exp(-(t - ti) * 3.0)
        eye = eye + shake(t, amp * 0.5 + 0.015, 2.2); eye[1] = np.clip(eye[1], -2.2, 2.2) if t < 28.8 else eye[1]
        return eye, tgt + shake(t + 2, amp, 1.6), lens, 0.03 * math.sin(t * 0.7), None
    if t < T_S6:   # 5. the rulebook
        u = float(sm(T_S5, T_S6, t))
        push = float(sm(T_OPEN + 1.0, T_S6, t))
        eye = lerp(v3(-51.0, 3.0, 0.9), v3(-52.0, 9.0, 1.6), u)
        eye = lerp(eye, v3(-52.8, 8.0, 2.0), push * 0.9) + shake(t, 0.02, 0.6)
        orb = float(sm(T_OPEN + 2.0, T_S6, t))
        a = lerp(0.0, 0.85, orb); rel = eye - RB
        eye = RB + v3(rel[0] * math.cos(a) - rel[1] * math.sin(a), rel[0] * math.sin(a) + rel[1] * math.cos(a), rel[2] + 7.0 * orb)
        tgt = lerp(RB + v3(0, 0, 11.5), RB + v3(-1.5, 0, 10.0), push)
        return eye, tgt, lerp(24.0, 26.0, push), 0.0, None
    if t < T_S7:   # 6. the five
        dp, _ = die_state(t)
        base_eye = v3(11.0, 11.8, 1.1)
        tgt = lerp(v3(16.5, 23.0, 2.2), dp, 0.3)
        lens = 32.0
        eye = base_eye + shake(t, 0.012, 0.3)
        land = float(sm(T_LAND + 0.25, T_LAND + 1.2, t))
        eye = lerp(eye, v3(13.2, 15.4, 4.2), land)
        tgt = lerp(tgt, DIE_REST + v3(0, 0, 0.3), land)
        lens = lerp(lens, 58.0, land)
        if t > T_LAND + 1.2:
            a = 0.5 * float(sm(T_LAND + 1.2, T_FALL, t)); rel = eye - DIE_REST
            eye = DIE_REST + v3(rel[0] * math.cos(a) - rel[1] * math.sin(a), rel[0] * math.sin(a) + rel[1] * math.cos(a), rel[2] - 1.0 * a)
        wide = float(sm(T_FALL - 0.9, T_FALL + 0.4, t))
        eye = lerp(eye, v3(11.5, 10.2, 2.4), wide)
        tgt = lerp(tgt, F + v3(-1.0, -3.0, 3.2), wide)
        lens = lerp(lens, 30.0, wide)
        k = math.exp(-max(t - T_LAND, 0) * 5) if t >= T_LAND else 0.0
        return eye + shake(t, 0.05 * k, 1.5), tgt, lens, 0.0, None
    if t < T_S8:   # 7. the storm passes: straight up, then back into the room
        a = float(sm(T_S7, T_REVEAL, t))
        e0 = lerp(v3(11.5, 10.2, 2.4), DIE_REST + v3(0.0, -0.8, 7.0), a)
        t0 = lerp(F + v3(-1.0, -3.0, 3.2), DIE_REST, a)
        u = float(sm(T_REVEAL, 67.5, t))
        P0, P1, P2 = DIE_REST + v3(0, -0.8, 7.0), DIE_REST + v3(0, -10, 95), v3(96.0, -112.0, 72.0)
        bez = (1 - u) ** 2 * P0 + 2 * u * (1 - u) * P1 + u * u * P2
        eye = e0 if t < T_REVEAL else bez
        tg = t0 if t < T_REVEAL else lerp(DIE_REST, v3(38.0, -8.0, -6.0), float(sm(T_REVEAL + 2.0, 67.5, t)))
        lens = lerp(30.0, 22.0, u)
        fd = float(np.linalg.norm(tg - eye)) if t >= T_REVEAL else None
        drift = float(sm(65.5, T_S8 + 1.0, t))
        eye = lerp(eye, v3(74.0, -76.0, 34.0), drift)
        tg = lerp(tg, H_C + v3(-6.0, 6.0, 0.0), drift)
        lens = lerp(lens, 26.0, drift)
        return eye, tg, lens, 0.0, fd
    if t < T_S9:   # 8. the dispatch
        u = float(sm(T_S8, T_S9, t))
        eye = lerp(v3(-222.0, -44.0, -38.0), v3(-232.0, -50.0, -44.0), u)
        tgt = v3(RX0 + 28.0, -60.0, FLOOR_Z)
        return eye, tgt, 26.0, 0.0, float(np.linalg.norm(tgt - eye))
    u = float(sm(T_S9, DUR, t))     # 9. the products
    eye = lerp(v3(52.0, -83.0, 27.0), v3(60.0, -75.0, 22.0), u)
    tgt = H_C + v3(-0.5, -5.0, 1.0)
    return eye, tgt, 35.0, 0.0, float(np.linalg.norm(tgt - eye))

# ---------------------------------------------------------------- per-frame state
def set_dice(t):
    for i, ob in enumerate(meteors):
        if t < T_APPEAR[i] or t >= T_S6 + 0.0 and False:
            place(ob, FAR); continue
        p = meteor_pos(i, t)
        if t < T_IMP[i]:
            R = rot_axis(MSPIN[i][None], np.array([(T_IMP[i] - t) * 11.0]))[0] @ MREST[i]
        else:
            R = MREST[i]
        place(ob, p, R)
    if t < T_THROW - 0.1:
        place(hero_die, FAR)
    else:
        p, R = die_state(t)
        place(hero_die, p, R)

def set_trails(t):
    for i in range(4):
        on = T_APPEAR[i] <= t < T_IMP[i]
        for k in range(3):
            pool = trails[i][k]
            if not on:
                pool.hide(); continue
            idx = np.array(list(TIERS[k]))
            tt_ = t - idx * 0.028
            P = np.array([meteor_pos(i, max(x, T_APPEAR[i])) for x in tt_])
            grow = float(ss(T_APPEAR[i], T_APPEAR[i] + 0.6, t))
            S = (1.35 * (1 - idx / NTR) ** 0.8 + 0.12) * grow
            flick = 1 + 0.15 * np.sin(t * 40 + idx * 1.7)
            pool.set(P, scale=S * flick)
    # fire light at the leading meteor / embers after the impacts
    near = None
    for i in range(4):
        if T_APPEAR[i] <= t < T_IMP[i]:
            near = i; break
    if near is not None:
        fire.location = meteor_pos(near, t); fire_d.energy = 6.0e4 * float(ss(T_APPEAR[near], T_IMP[near] - 1.5, t))
    elif T_IMP[0] <= t < T_S7:
        fire.location = IMP[0] + v3(-2.0, -2.0, 1.6)
        fire_d.energy = 900.0 * (1 + 0.25 * math.sin(t * 17) * math.sin(t * 5.3))
    else:
        fire_d.energy = 0.0
    # impact flash, rings, craters
    fl, fp = 0.0, IMP[0]
    for i, ti in enumerate(T_IMP):
        if t >= ti and math.exp(-(t - ti) * 8.0) > fl:
            fl, fp = math.exp(-(t - ti) * 8.0), IMP[i]
        if t >= ti and t < T_REVEAL:
            s = CR_R[i]
            place(craters[i], IMP[i] + v3(0, 0, 0.015 + 0.003 * i), np.diag([s, s, 1.0]))
        else:
            place(craters[i], FAR)
        tau = t - ti
        if 0 <= tau < 1.1:
            r = 1.0 + 13 * (tau / 1.1) ** 0.6
            place(rings[i], IMP[i] + v3(0, 0, 0.12), np.diag([r, r, 1.0]))
        else:
            place(rings[i], FAR)
    RING_MIX.default_value = max([0.0] + [0.7 * (1 - (t - ti) / 1.1) ** 1.5 for ti in T_IMP if 0 <= t - ti < 1.1])
    RING_STR.default_value = 8.0
    flash.location = fp + v3(0, 0, 3.0)
    flash_d.energy = 7.0e4 * fl
    EMBER.default_value = 0.8 * (1 - float(ss(T_S7, T_REVEAL, t))) * (0.8 + 0.2 * math.sin(t * 9))

def set_bolts(t, eye, fwd):
    amt, rgb, best = strike_env(t)
    for bo in bolts:
        bo.location = FAR
    if best >= 0 and amt > 0.25 and t < T_S7:
        t0, c, az, el, s = STRIKES[best]
        bo = bolts[c + 3 * (best % 2)]
        f2 = norm(v3(fwd[0], fwd[1], 0.0))
        side = norm(np.cross(f2, v3(0, 0, 1)))
        off = ((best * 0.37) % 1.0 - 0.5) * 1.1
        pos = eye + (f2 + side * off) * 1400.0
        pos[2] = 820.0 + 120 * (best % 3)
        bo.location = tuple(pos)
        bo.rotation_euler = (0, 0, best * 1.3)
    return amt, rgb, best

def set_storm(t, eye, tgt):
    storm = 1 - float(ss(T_S7 - 0.5, T_REVEAL, t))
    amt, rgb, best = set_bolts(t, eye, norm(tgt - eye))
    base = 1.0
    if best >= 0:
        t0, c, az, el, s = STRIKES[best]
        d = v3(math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))
        strike.rotation_euler = Vector((-d).tolist()).to_track_quat('-Z', 'Y').to_euler()
    col = rgb / max(amt, 1e-6) if amt > 0 else v3(1, 1, 1)
    bolt_d.color = tuple(np.clip(0.35 + 0.65 * col, 0, 1))
    bolt_d.energy = 2.6 * amt * storm
    sky = (v3(0.62, 0.78, 1.15) * 1.05 * base + rgb * 1.7) * storm + v3(0.02, 0.018, 0.015) * (1 - storm)
    SKY_LIGHT.outputs[0].default_value = (*sky, 1)
    fill_d.energy = 0.45 * base * storm
    moon_d.energy = 1.6 * base * storm
    scene.view_settings.exposure = 1.25 * (1 - float(ss(T_S7 - 0.3, T_REVEAL + 0.3, t)))
    FOG.default_value = 0.0018 * storm + 0.00025 * (1 - storm)
    RAIN_GLOW.default_value = (0.8 + 7.0 * amt) * storm
    DROP_GLOW.default_value = 0.3 + 3.0 * amt
    for m in bolt_mats:
        m.node_tree.nodes['Emission'].inputs[1].default_value = 30.0 * min(amt, 1.5)
    WET.default_value = 1 - float(ss(T_S7, T_REVEAL + 0.6, t))
    TIME.default_value = ts(t) * 1.3
    set_rain(t, eye, storm * float(ss(0.0, 0.5, t)))
    return amt

def update(t):
    eye, tgt, lens, roll, fd = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    if fd is None:
        cam_d.dof.aperture_fstop = 128.0
    else:
        cam_d.dof.focus_distance = fd
        cam_d.dof.aperture_fstop = 2.2 if t < T_S9 else 3.2
    set_cards(t); set_pack(t); set_dice(t); set_trails(t); set_drops(t); set_splinters(t)
    set_rulebook(t); set_motes(t); set_room(t); set_storm(t, eye, tgt)
    return t >= T_WHITE + 0.6

def events():
    ev = {'strikes': [[s[0], s[1], s[4]] for s in STRIKES],
          'slams': sorted(float(c['t_up'] + 0.42) for c in CARDS if c['kind'] == 'slam'),
          'boost_land': sorted(float(c['t0'] + c['t_air']) for c in CARDS if c['kind'] == 'boost'),
          'falls': sorted(float(c['t_fall'] + 0.9) for c in CARDS if c['kind'] == 'fall'),
          'appear': T_APPEAR, 'impacts': T_IMP,
          'T': {k: v for k, v in globals().items() if k.startswith('T_') and isinstance(v, float)}}
    os.makedirs(WORK, exist_ok=True)
    json.dump(ev, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

CUT_TIMES = [T_S2, T_S3, T_S4, T_S5, T_S6, T_S8, T_S9]
CUT_FRAMES = [round(x * FPS) for x in CUT_TIMES] + [round(T_REVEAL * FPS)]

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
