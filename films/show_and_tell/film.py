"""GNV-LPV-MIX-001 SHOW AND TELL -- Goosnav Book 2 + Goosklerf. Monumental low-poly vignette, 9:16.

An infinite desert with black pyramids. Three men stand far apart from everything.
"I have a Goosklerf trading card deck." (lifts it, spins once)
"Well, I have a Goosnav book." (lifts it, spins chaotically)
"Well... I have a bomb." (lifts it. It explodes.) Overhead: an extremely chaotic mushroom cloud.
End card: Two of these are for sale.
"""
import sys, os, json, math
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa
from lowpoly import *   # noqa
from studio import config

FILM = 'show_and_tell'
FPS = 24
DUR = 23.5
WORK = str(config.path('work', FILM, FORMAT))
VO = str(config.path('work', FILM, 'vo'))
TEX = str(config.textures()); SRC = str(config.sources())
rng = np.random.default_rng(21); set_rng(rng)

T2, T3, T_BOOM, T_END = 3.2, 5.4, 15.8, 21.0
T4 = T_BOOM + 0.1
VO_AT = {'01': 5.8, '02': 9.5, '03': 13.2}
SPEAKER = {'01': 'P1', '02': 'P2', '03': 'P3'}
LIFT = {'P1': (6.3, 9.0), 'P2': (10.0, 13.1), 'P3': (14.0, 99)}
SPIN1 = (7.3, 8.6)
SPIN2 = (10.8, 12.9)
CUT_FRAMES = [round(x * FPS) for x in (T2, T3, T4)]

scene = setup_scene(fps=FPS, samples=16, bloom=(0.95, 0.06, 6.0), look='AgX - Base Contrast')
fog_world(sky_top='#7F9AB0', sky_horizon='#E4DDCB', strength=1.15, density=0.00035, anisotropy=0.3)
scene.view_settings.exposure = 0.1
sun(4.2, '#FFF4E2', elev=58, azim=-35, angle=1.5)      # hard desert noon

# ---------------------------------------------------------------- desert and pyramids
sand = mat('sand', '#CDB88F', 0.9, noise=0.12, noise_scale=0.02)
box('desert', (8000, 8000, 0.2), sand, (0, 0, -0.1))
black = mat('pyramid', '#15171A', 0.25, 0.2)
def pyramid(name, loc, base, height, yaw=0.0):
    me = bpy.data.meshes.new(name)
    b = base / 2
    me.from_pydata([(-b, -b, 0), (b, -b, 0), (b, b, 0), (-b, b, 0), (0, 0, height)], [],
                   [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)])
    me.materials.append(black)
    ob = link(bpy.data.objects.new(name, me)); ob.location = loc; ob.rotation_euler = (0, 0, yaw)
    return ob
for i, (x, y, base, h, yaw) in enumerate(((-380, 1300, 700, 460, 0.2), (420, 1800, 950, 620, -0.1), (1300, 1400, 520, 330, 0.35),
                                            (-1500, 2500, 1200, 760, 0.0), (80, 3200, 800, 520, 0.5))):
    pyramid(f'pyr{i}', (x, y, 0), base, h, yaw)

# ---------------------------------------------------------------- three men and their things
XS = {'P1': -1.35, 'P2': 0.0, 'P3': 1.35}
P1 = Human('P1', skin=SKIN[0], top='#00B2A9', legs='#2E3338', hair='#6B4B2E', jacket='#0E7F79')
P2 = Human('P2', skin=SKIN[2], top='#D5D2C8', legs='#343A2A', hair='#141414', jacket='#0033A0', build=1.08)
P3 = Human('P3', skin=SKIN[1], top='#586044', legs='#414746', hair='#9A9590', hat='#343A2A', height=1.84)
MEN = {'P1': P1, 'P2': P2, 'P3': P3}
pack_mat = tex_mat('pack', os.path.join(TEX, 'gen_pack.png'), 0.3, 512)
pack = make_box('pack', (0.12, 0.02, 0.19), {(0, -1, 0): pack_mat, (0, 1, 0): pack_mat}, mat('foil', '#C8CCD4', 0.25, 0.9))
book = product_book('book2', 1.0, TEX)
bomb = empty('bomb')
ball('bomb_body', 0.16, mat('bombblack', '#111214', 0.2, 0.3), 12, 8, (0, 0, 0), (1, 1, 1), bomb)
cyl('bomb_cap', 0.05, 0.05, mat('bombcap', '#3A3D40', 0.35, 0.8), 8, (0, 0, 0.16), bomb)
fuse = cyl('bomb_fuse', 0.012, 0.12, mat('fuse', '#C9B48A', 0.8), 6, (0.02, 0, 0.24), bomb)
fuse.rotation_euler = (0, 0.4, 0)
spark = ball('spark', 0.025, mat('spark', '#FFD27A', 0.3, emit=40.0), 6, 4, (0.045, 0, 0.3), (1, 1, 1), bomb)
ball('bomb_glint', 0.03, mat('glint', '#FFFFFF', 0.1, emit=3.0), 6, 4, (-0.07, -0.12, 0.08), (1, 0.5, 1), bomb)

lines = Lines([(SPEAKER[k], t, os.path.join(VO, f'vo_{k}.wav')) for k, t in VO_AT.items()], FPS)
ARMS_UP = {'uarm_L': (-2.95, 0, 0.28), 'uarm_R': (-2.95, 0, -0.28), 'farm_L': (-0.35, 0, -0.3), 'farm_R': (-0.35, 0, 0.3)}

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

def lift_amount(p, t):
    a, b = LIFT[p]
    return ease((t - a) / 0.5) * (1 - ease((t - b) / 0.45))

def set_men(t):
    tc = on_twos(t)
    for p, H in MEN.items():
        yaw = 0.0
        H.place((XS[p], 0.0, 0.0), yaw)
        H.pose({})
        w = lift_amount(p, tc)
        H.pose(ARMS_UP, w=w)
        if p == 'P1' and SPIN1[0] <= tc <= SPIN1[1]:
            u = ease((tc - SPIN1[0]) / (SPIN1[1] - SPIN1[0]))
            H.place((XS[p], 0.0, 0.0), 2 * math.pi * u)
        if p == 'P2' and SPIN2[0] <= tc <= SPIN2[1]:
            u = (tc - SPIN2[0]) / (SPIN2[1] - SPIN2[0])
            yaw = 2 * math.pi * 3.5 * ease(u) + 0.6 * math.sin(tc * 23)
            hop = 0.14 * abs(math.sin(tc * 11))
            H.place((XS[p] + 0.08 * math.sin(tc * 13), 0.05 * math.cos(tc * 9), hop), yaw)
            H.add({'spine': (0.35 * math.sin(tc * 17), 0.3 * math.sin(tc * 13), 0),
                   'thigh_L': (-0.6 * max(0, math.sin(tc * 11)), 0, 0.3), 'thigh_R': (-0.6 * max(0, -math.sin(tc * 11)), 0, -0.3),
                   'uarm_L': (0.3 * math.sin(tc * 19), 0, 0.2 * math.sin(tc * 7)), 'head': (0.3 * math.sin(tc * 15), 0, 0.4 * math.sin(tc * 9))})
        # everyone else watches the speaker
        speaking = [k for k, s in SPEAKER.items() if s == p and VO_AT[k] <= tc < VO_AT[k] + 2.4]
        if not speaking and w < 0.1:
            spk = [s for k, s in SPEAKER.items() if VO_AT[k] <= tc < VO_AT[k] + 3.4]
            if spk:
                H.look(yaw=0.5 * (1 if XS[spk[0]] > XS[p] else -1), pitch=0.05)
        H.idle(tc); H.blink(t, hash(p) % 7)
        H.talk(lines.amount(p, t))
        H.root.scale = (1, 1, 1) if t < T_BOOM else (0.0001, 0.0001, 0.0001)   # gone
    bpy.context.view_layer.update()   # grips must be evaluated this frame before props follow them
    # the things, between the raised hands (or low in the right hand)
    for p, ob, off, rot in (('P1', pack, (0, 0, 0.06), (0, 0, 0)), ('P2', book, (0, 0, 0.12), (math.pi / 2, 0, 0)),
                            ('P3', bomb, (0, 0, 0.15), (0, 0, 0))):
        H = MEN[p]
        if t >= T_BOOM:
            ob.location = tuple(HIDE); continue
        gl = H.grip('L').matrix_world.translation; gr = H.grip('R').matrix_world.translation
        mid = (gl + gr) / 2
        w = lift_amount(p, on_twos(t))
        if w > 0.05:
            ob.location = mid + Vector(off)
            ob.rotation_euler = (rot[0], rot[1], H.root.rotation_euler[2])
        else:
            ob.location = gr + Vector((0, -0.04, -0.02))
            ob.rotation_euler = (rot[0] * 0.3, 0, 0)
    spark.scale = (1, 1, 1) if (t >= LIFT['P3'][0] - 0.2 and int(t * 48) % 3) else (0.4, 0.4, 0.4)

# ---------------------------------------------------------------- the explosion (procedural, low-poly)
BX = v3(XS['P3'], 0.0, 1.9)
fire_mat = mat('fire', '#FF9A2E', 0.5, emit=18.0)
hot_mat = mat('hot', '#FFE6A0', 0.3, emit=40.0)
smoke_mats = [mat(f'smoke{i}', c, 0.95) for i, c in enumerate(('#3B3530', '#5E544A', '#7A6E60', '#2A2622'))]
dust_mat = mat('dust', '#B8A07A', 0.95)
def puff(name, m, seg=10):
    return ball(name, 1.0, m, seg, 7, tuple(HIDE))
FIRE = [puff(f'fire{i}', hot_mat if i < 5 else fire_mat) for i in range(14)]
STEM = [puff(f'stem{i}', smoke_mats[i % 4]) for i in range(16)]
CAP = [puff(f'cap{i}', smoke_mats[(i * 3) % 4]) for i in range(36)]
CAPFIRE = [puff(f'capfire{i}', fire_mat) for i in range(12)]
SKIRT = [puff(f'skirt{i}', dust_mat) for i in range(30)]
POPS = [puff(f'pop{i}', hot_mat) for i in range(10)]
DEBRIS = [box(f'deb{i}', (0.6, 0.4, 0.3), smoke_mats[i % 4], tuple(HIDE)) for i in range(40)]
for d in DEBRIS:
    d.rotation_mode = 'XYZ'
ringm, nt, out = new_mat('shock')
e = nt.nodes.new('ShaderNodeEmission'); e.inputs[0].default_value = (1.0, 0.95, 0.85, 1); e.inputs[1].default_value = 6
tr = nt.nodes.new('ShaderNodeBsdfTransparent'); ms = nt.nodes.new('ShaderNodeMixShader')
nt.links.new(tr.outputs[0], ms.inputs[1]); nt.links.new(e.outputs[0], ms.inputs[2]); nt.links.new(ms.outputs[0], out.inputs[0])
ringm.blend_method = 'BLEND'; ringm.shadow_method = 'NONE'
RING_MIX = ms.inputs[0]
ring = cyl('shockring', 1.0, 0.3, ringm, 48, tuple(HIDE), cap=False)
flash_l = point('boomlight', tuple(BX), 0, '#FFE2B0', 3.0)
R = np.random.default_rng(77)
F_OFF = R.normal(0, 1, (14, 3)); STEM_PH = R.uniform(0, 6.3, 16); CAP_PH = R.uniform(0, 6.3, 36)
DEB_V = R.normal(0, 1, (40, 3)) * [22, 22, 0] + [0, 0, 1] * R.uniform(18, 40, (40, 1)); DEB_W = R.normal(0, 6, (40, 3))
POP_T = np.sort(R.uniform(0.2, 3.2, 10)); POP_P = R.normal(0, 1, (10, 3)) * [22, 22, 8] + [0, 0, 14]

def set_explosion(t):
    s = t - T_BOOM
    if s < 0:
        for ob in FIRE + STEM + CAP + CAPFIRE + SKIRT + POPS + DEBRIS:
            ob.location = tuple(HIDE)
        ring.location = tuple(HIDE); flash_l.data.energy = 0
        return
    grow = 1 - math.exp(-s * 1.4)
    H = 6 + 36 * (1 - math.exp(-s * 0.9))                 # cap height
    base = v3(BX[0], BX[1], 0)
    # fireball: fast bloom, then rises and cools into the cap
    for i, ob in enumerate(FIRE):
        r = (2 + 7 * min(1, s / 0.5)) * (1 - 0.8 * min(1, max(0, s - 1.5) / 2.0)) * (0.7 + 0.3 * abs(F_OFF[i, 0]))
        p = base + v3(*(F_OFF[i] * r * 0.5)) + v3(0, 0, r * 0.6 + H * min(1, s / 2.5) * 0.8)
        ob.location = tuple(p); ob.scale = (r, r, r)
    # stem: a twisting column
    for i, ob in enumerate(STEM):
        f = i / (len(STEM) - 1)
        z = H * f * grow
        a = STEM_PH[i] + s * 1.3
        r = (5.0 + 2.0 * math.sin(f * 7 + s)) * grow
        ob.location = tuple(base + v3(1.8 * math.cos(a) * f, 1.8 * math.sin(a) * f, z)); ob.scale = (r, r, r * 1.2)
    # cap: a rolling torus, fire on its underside early on
    R_cap = 6 + 18 * (1 - math.exp(-s * 1.1))
    for i, ob in enumerate(CAP):
        th = CAP_PH[i] + (i / len(CAP)) * 2 * math.pi
        roll = s * 2.2 + i * 0.7
        rr = 5 + 5 * (1 - math.exp(-s))
        cx = R_cap * math.cos(th); cy = R_cap * math.sin(th)
        p = base + v3(cx + rr * 0.5 * math.cos(roll) * math.cos(th), cy + rr * 0.5 * math.cos(roll) * math.sin(th), H + rr * 0.5 * math.sin(roll))
        sc = (4 + 3 * abs(math.sin(i * 1.7))) * grow
        ob.location = tuple(p); ob.scale = (sc, sc, sc * 0.85)
    for i, ob in enumerate(CAPFIRE):
        th = i / len(CAPFIRE) * 2 * math.pi + s
        k = max(0.0, 1 - s / 2.8)
        ob.location = tuple(base + v3(R_cap * 0.7 * math.cos(th), R_cap * 0.7 * math.sin(th), H - 3)); sc = 5 * k * grow
        ob.scale = (sc, sc, sc * 0.6)
    # base surge along the ground
    R_sk = 4 + 34 * (1 - math.exp(-s * 1.2))
    for i, ob in enumerate(SKIRT):
        th = i / len(SKIRT) * 2 * math.pi + 0.2 * math.sin(i)
        sc = (3 + 2.5 * abs(math.sin(i * 2.3))) * grow
        ob.location = tuple(base + v3(R_sk * math.cos(th), R_sk * math.sin(th), sc * 0.4)); ob.scale = (sc, sc, sc * 0.6)
    # secondary blasts: chaos
    for i, ob in enumerate(POPS):
        d = s - POP_T[i]
        if 0 <= d < 0.6:
            sc = 7 * math.sin(math.pi * d / 0.6)
            ob.location = tuple(base + v3(*POP_P[i])); ob.scale = (sc, sc, sc)
        else:
            ob.location = tuple(HIDE)
    for i, ob in enumerate(DEBRIS):
        p = base + v3(0, 0, 1) + v3(*(DEB_V[i] * s)) + v3(0, 0, -4.9 * s * s)
        if p[2] < 0.2:
            p[2] = 0.2
        ob.location = tuple(p); ob.rotation_euler = tuple(DEB_W[i] * s)
    K = 2.4                                    # scale the whole cloud up about its base
    for ob in FIRE + STEM + CAP + CAPFIRE + SKIRT + POPS + DEBRIS:
        if ob.location.z > -100:
            ob.location = tuple(base + (v3(*ob.location) - base) * K)
            if ob not in DEBRIS:
                ob.scale = tuple(c * K for c in ob.scale)
    rr = 5 + 260 * (s / 1.4) ** 0.6
    ring.location = (base[0], base[1], 0.3) if s < 1.6 else tuple(HIDE)
    ring.scale = (rr, rr, 1)
    RING_MIX.default_value = max(0.0, 1 - s / 1.6) ** 1.5 * 0.9
    flash_l.data.energy = 4.0e7 * math.exp(-s * 2.2)

cam, cam_d = make_camera(clip_end=12000)
OVERHEAD_EYE = v3(14.0, -150.0, 92.0)
def camera_at(t):
    if t < T2:     # the infinite desert, the black pyramids
        u = t / T2
        return lerp(v3(70.0, -12.0, 1.6), v3(70.5, -6.0, 1.6), u), v3(40.0, 1500.0, 190.0), 20.0, 0.0
    if t < T3 or t >= T4:   # overhead, far: three dots
        amp = 0.0
        if t >= T_BOOM:
            s = t - T_BOOM
            amp = 3.0 * math.exp(-s * 1.2) + 0.4
        u = (t - (T2 if t < T3 else T4)) / 5.0
        if t >= T_BOOM:   # pull back and up as the cloud climbs, keeping the whole mushroom in frame
            k = ease((t - T_BOOM) / 3.2)
            eye = lerp(OVERHEAD_EYE, v3(18.0, -245.0, 132.0), k) + shake(t, amp * (1 + 2 * k), 0.9)
            return eye, v3(1.0, 0.0, lerp(16.0, 50.0, k)), 22.0, 0.0
        eye = OVERHEAD_EYE + shake(t, amp, 0.9) + v3(0, 0, 4 * u)
        return eye, v3(1.0, 0.0, 1.0), 30.0, 0.0
    u = (t - T3) / (T_BOOM - T3)   # closer: the three of them
    tx = 0.0
    for p, (a, b) in LIFT.items():
        if a - 0.6 <= t:
            tx = XS[p] * 0.35
    eye = lerp(v3(0.0, -7.6, 1.55), v3(0.0, -6.2, 1.5), u)
    return eye, v3(tx, 0.0, 1.35), 24.0, 0.0

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_men(t); set_explosion(t)
    return t >= T_END

def events():
    os.makedirs(WORK, exist_ok=True)
    json.dump({'VO_AT': VO_AT, 'SPEAKER': SPEAKER, 'LIFT': LIFT, 'SPIN1': SPIN1, 'SPIN2': SPIN2, 'BOOM': T_BOOM,
               'cuts': [T2, T3, T4], 'end': T_END, 'dur': DUR}, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
