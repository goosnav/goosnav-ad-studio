"""WHAT WE SENT (the_probe) -- Goosnav Book 2 / Goosklerf / Patreon. 60 s, 4:5, Blender Eevee.
A Voyager-class probe, still going. Bolted to it: Goosnav Book 2, a sealed Goosklerf pack and a
pneumatic canister that receives a new comic every month. Everything is driven by update(t).

  python3 -m studio preview the_probe --format 4x5 --every 12
  python3 -m studio render  the_probe --format 4x5
"""
import sys, os
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa: F401,F403
import bstudio as bs
from mathutils import Quaternion
from studio import config

FILM = 'the_probe'
TEX = str(config.textures())
WORK = str(config.path('work', FILM, FORMAT))
FPS = 24
DUR = 60.0
rng = np.random.default_rng(11)
set_rng(rng)

def P(lens):
    """portrait lenses are authored directly: aim_camera multiplies by LENS_SCALE"""
    return lens / LENS_SCALE

# ---------------------------------------------------------------- timeline (from the VO, see SCRIPT.md)
T_S2 = 6.4          # macro glide
T_S3 = 14.9         # the book
T_S4 = 20.3         # gas giant
T_S5 = 28.0         # canister
T_ARRIVE1 = 31.2    # the tube receives a comic
T_S6 = 39.9         # ringed world + the die
T_SIX = 43.6        # it came up six
T_S7 = 46.8         # recede
T_S8 = 49.8         # hero, one more comic
T_ARRIVE2 = 50.15
T_END = 55.5        # white card over (frames after T_END+0.45 are black)
T_SUNRISE = 1.3
SHOT_T = [0.0, T_S2, T_S3, T_S4, T_S5, T_S6, T_S7, T_S8, 99.0]

scene = setup_scene(fps=FPS, samples=20, bloom=(0.9, 0.09, 7.0))
scene.eevee.gtao_distance = 0.6
scene.eevee.shadow_cascade_size = '4096'
scene.eevee.use_soft_shadows = True

# ---------------------------------------------------------------- world: black space, stars, planetshine
world = bpy.data.worlds.new('space'); scene.world = world
world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
wout = wn.nodes.new('ShaderNodeOutputWorld')
tc = wn.nodes.new('ShaderNodeTexCoord')
vor = wn.nodes.new('ShaderNodeTexVoronoi'); vor.voronoi_dimensions = '3D'
vor.inputs['Scale'].default_value = 190.0
wn.links.new(tc.outputs['Generated'], vor.inputs['Vector'])
st_mr = wn.nodes.new('ShaderNodeMapRange'); st_mr.interpolation_type = 'SMOOTHSTEP'
st_mr.inputs[1].default_value = 0.075; st_mr.inputs[2].default_value = 0.0
wn.links.new(vor.outputs['Distance'], st_mr.inputs[0])
sep = wn.nodes.new('ShaderNodeSeparateColor')
wn.links.new(vor.outputs['Color'], sep.inputs[0])
thin = wn.nodes.new('ShaderNodeMath'); thin.operation = 'POWER'; thin.inputs[1].default_value = 5.0
wn.links.new(sep.outputs[0], thin.inputs[0])
star = wn.nodes.new('ShaderNodeMath'); star.operation = 'MULTIPLY'
wn.links.new(st_mr.outputs[0], star.inputs[0]); wn.links.new(thin.outputs[0], star.inputs[1])
star_bg = wn.nodes.new('ShaderNodeBackground')
wn.links.new(star.outputs[0], star_bg.inputs['Color'])
STAR_STR = star_bg.inputs['Strength']; STAR_STR.default_value = 1.6
# lighting for everything but camera rays: dim ambient + coloured planetshine from one direction
PS_DIR = wn.nodes.new('ShaderNodeCombineXYZ')
dotp = wn.nodes.new('ShaderNodeVectorMath'); dotp.operation = 'DOT_PRODUCT'
wn.links.new(tc.outputs['Generated'], dotp.inputs[0]); wn.links.new(PS_DIR.outputs[0], dotp.inputs[1])
ps_mr = wn.nodes.new('ShaderNodeMapRange'); ps_mr.inputs[1].default_value = -0.2; ps_mr.inputs[2].default_value = 1.0
wn.links.new(dotp.outputs['Value'], ps_mr.inputs[0])
ps_col = wn.nodes.new('ShaderNodeMix'); ps_col.data_type = 'RGBA'
ps_col.inputs[6].default_value = (0.010, 0.011, 0.014, 1)
PS_COLOR = ps_col.inputs[7]
wn.links.new(ps_mr.outputs[0], ps_col.inputs['Factor'])
env_bg = wn.nodes.new('ShaderNodeBackground')
wn.links.new(ps_col.outputs[2], env_bg.inputs['Color'])
PS_STR = env_bg.inputs['Strength']
lp_ = wn.nodes.new('ShaderNodeLightPath')
wmix = wn.nodes.new('ShaderNodeMixShader')
wn.links.new(lp_.outputs['Is Camera Ray'], wmix.inputs[0])
wn.links.new(env_bg.outputs[0], wmix.inputs[1]); wn.links.new(star_bg.outputs[0], wmix.inputs[2])
wn.links.new(wmix.outputs[0], wout.inputs[0])

# ---------------------------------------------------------------- sun
sun_d = bpy.data.lights.new('sun', 'SUN')
sun_d.energy = 5.0; sun_d.angle = math.radians(0.4); sun_d.color = (1.0, 0.985, 0.96)
sun_d.use_contact_shadow = True; sun_d.contact_shadow_distance = 0.05
sun_d.shadow_cascade_count = 4; sun_d.shadow_cascade_max_distance = 6.0
sun_ob = link(bpy.data.objects.new('sun', sun_d)); sun_ob.rotation_mode = 'QUATERNION'
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0)
sun_disk = bpy.context.object
sun_disk.data.materials.append(mat_emit('sun_disk', (1.0, 0.98, 0.94), 90.0))
sun_disk.visible_shadow = False
SUN_DIST, SUN_R = 5200.0, 22.0

# ---------------------------------------------------------------- materials
def foil_mat(name, col, metal=0.72, rough=0.3, crinkle=0.55, scale=9.0):
    m, nt, out = new_mat(name)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*col, 1)
    b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = rough
    t = nt.nodes.new('ShaderNodeTexCoord')
    v = nt.nodes.new('ShaderNodeTexVoronoi'); v.voronoi_dimensions = '3D'; v.inputs['Scale'].default_value = scale
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale * 2.3
    nz.inputs['Detail'].default_value = 6
    nt.links.new(t.outputs['Object'], v.inputs['Vector']); nt.links.new(t.outputs['Object'], nz.inputs['Vector'])
    ad = nt.nodes.new('ShaderNodeMath'); ad.operation = 'ADD'
    nt.links.new(v.outputs['Distance'], ad.inputs[0]); nt.links.new(nz.outputs['Fac'], ad.inputs[1])
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = crinkle
    bump.inputs['Distance'].default_value = 0.02
    nt.links.new(ad.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs[0], b.inputs['Normal'])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m

GOLD = foil_mat('gold_foil', (1.0, 0.60, 0.20))
GOLD_FINE = foil_mat('gold_fine', (1.0, 0.64, 0.24), crinkle=0.25, scale=40.0, rough=0.25)
BLACKFOIL = foil_mat('black_foil', (0.035, 0.03, 0.03), metal=0.4, rough=0.35, crinkle=0.4, scale=12.0)
ALU = mat_color('alu', (0.72, 0.73, 0.75), rough=0.42, metal=0.35)
WHITE = mat_color('dish_white', (0.80, 0.80, 0.78), rough=0.55)
DARK = mat_color('rtg_dark', (0.06, 0.06, 0.065), rough=0.5, metal=0.5)
BRASS = mat_color('bracket_gold', (0.95, 0.66, 0.28), rough=0.22, metal=1.0)

# ---------------------------------------------------------------- geometry helpers
root = link(bpy.data.objects.new('probe', None))
root.rotation_mode = 'QUATERNION'

def own(ob):
    ob.parent = root
    return ob

def cyl(p0, p1, r, mat, verts=12, fill='NGON'):
    p0, p1 = v3(*p0), v3(*p1)
    d = p1 - p0; L = float(np.linalg.norm(d))
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=L, end_fill_type=fill)
    ob = bpy.context.object
    ob.location = Vector((p0 + p1) / 2)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector(d / L).to_track_quat('Z', 'Y')
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    return own(ob)

def box(size, center, mat, face_mats=None, bevel=0.0):
    ob = make_box('box', size, face_mats or {}, mat, bevel=bevel)
    ob.location = Vector(center)
    return own(ob)

# ---------------------------------------------------------------- the probe
BUS_R, BUS_H = 0.9, 0.45
bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=BUS_R, depth=BUS_H)
bus = own(bpy.context.object); bus.data.materials.append(GOLD)
cyl((0, 0, -0.26), (0, 0, -0.22), BUS_R * 0.93, BLACKFOIL, verts=10)
cyl((0, 0, 0.22), (0, 0, 0.27), BUS_R * 1.02, ALU, verts=10)
for k in range(10):   # equipment bays: alternating foil panels
    a = (k + 0.5) * 2 * math.pi / 10
    c = v3(math.cos(a), math.sin(a), 0) * (BUS_R * 0.93)
    b = box((0.34, 0.03, 0.36), c, BLACKFOIL if k % 3 == 0 else GOLD_FINE)
    b.rotation_euler = (0, 0, a + math.pi / 2)

# dish: paraboloid opening +Z
F_DISH, R_DISH, Z_DISH = 1.3, 1.85, 0.3
def build_dish():
    nr, ns = 18, 72
    verts, faces = [], []
    for i in range(nr + 1):
        r = R_DISH * i / nr
        for j in range(ns):
            a = 2 * math.pi * j / ns
            verts.append((r * math.cos(a), r * math.sin(a), Z_DISH + r * r / (4 * F_DISH)))
    for i in range(nr):
        for j in range(ns):
            a = i * ns + j; b = i * ns + (j + 1) % ns
            faces.append((a, b, b + ns, a + ns))
    me = bpy.data.meshes.new('dish'); me.from_pydata(verts, [], faces); me.update()
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
    me.materials.append(WHITE)
    ob = link(bpy.data.objects.new('dish', me))
    sol = ob.modifiers.new('sol', 'SOLIDIFY'); sol.thickness = 0.025
    return own(ob)
dish = build_dish()
Z_RIM = Z_DISH + R_DISH ** 2 / (4 * F_DISH)
Z_FOC = Z_DISH + F_DISH
for k in range(4):
    a = k * math.pi / 2 + 0.3
    cyl((R_DISH * 0.97 * math.cos(a), R_DISH * 0.97 * math.sin(a), Z_RIM - 0.02), (0, 0, Z_FOC - 0.05), 0.012, ALU, 8)
cyl((0, 0, Z_FOC - 0.08), (0, 0, Z_FOC + 0.02), 0.2, WHITE, 24)
cyl((0, 0, Z_DISH - 0.05), (0, 0, Z_FOC - 0.3), 0.06, GOLD_FINE, 12)
# RTG boom (+X): three generators with fins
cyl((BUS_R * 0.9, 0, -0.05), (3.0, 0, -0.35), 0.03, ALU, 8)
cyl((BUS_R * 0.9, 0.12, 0.0), (3.0, 0.0, -0.35), 0.015, ALU, 6)
for k in range(3):
    c = v3(1.75 + k * 0.52, 0, -0.14 - k * 0.075)
    d = norm(v3(3.0 - 0.81, 0, -0.30))
    cyl(c - d * 0.21, c + d * 0.21, 0.17, DARK, 16)
    for f in range(6):
        a = f * math.pi / 3
        off = v3(0, math.cos(a), math.sin(a)) * 0.2
        cyl(c - d * 0.2 + off, c + d * 0.2 + off, 0.035, DARK, 4)
# science boom (+Y) and scan platform
cyl((0.1, BUS_R * 0.9, 0.0), (0.1, 2.5, 0.15), 0.035, ALU, 8)
cyl((-0.1, BUS_R * 0.9, 0.05), (0.1, 2.5, 0.15), 0.015, ALU, 6)
box((0.42, 0.42, 0.34), (0.1, 2.7, 0.2), GOLD_FINE, bevel=0.01)
cyl((0.0, 2.55, 0.42), (0.0, 2.95, 0.42), 0.07, ALU, 16)
cyl((0.2, 2.55, 0.44), (0.2, 2.85, 0.44), 0.045, DARK, 16)
# magnetometer boom and the two long whip antennas
cyl((0.5, 0.55, 0.2), (3.4, 6.2, 2.4), 0.02, ALU, 6)
cyl((0.5, 0.55, 0.2), (3.4, 6.2, 2.4), 0.008, ALU, 4).location += Vector((0.05, -0.05, 0.05))
cyl((0.3, 0.3, -0.25), (-3.5, 4.0, -8.5), 0.006, ALU, 4)
cyl((0.3, 0.3, -0.25), (2.8, 4.8, -8.4), 0.006, ALU, 4)

# ---------------------------------------------------------------- the message boom (-X) and payload plate
PX, PY, PZ = -2.6, -0.1, 0.0           # plate centre; plate faces -Y
PLATE_W, PLATE_H, PLATE_T = 0.74, 0.54, 0.014
YF = PY - PLATE_T / 2                   # front face of the plate
for (y, z) in ((0.06, 0.08), (0.06, -0.08), (-0.06, 0.0)):
    cyl((-BUS_R * 0.92, y, z), (PX + 0.2, PY + PLATE_T / 2 + 0.05 + y * 0.3, z * 0.8), 0.014, ALU, 8)
for k in range(5):
    x = -1.0 - k * 0.33
    cyl((x, 0.06, 0.08), (x - 0.33, -0.06, 0.0), 0.007, ALU, 6)
    cyl((x, 0.06, -0.08), (x - 0.33, 0.06, 0.08), 0.007, ALU, 6)
cyl((PX + 0.2, PY + 0.05, 0.0), (PX + 0.2, PY + PLATE_T / 2, 0.0), 0.05, ALU, 16)
plate = box((PLATE_W, PLATE_T, PLATE_H), (PX, PY, PZ), ALU, bevel=0.004)
box((PLATE_W - 0.03, 0.002, PLATE_H - 0.03), (PX, YF - 0.001, PZ), GOLD_FINE)
for sx in (-1, 1):
    for sz in (-1, 1):
        cyl((PX + sx * (PLATE_W / 2 - 0.025), YF, PZ + sz * (PLATE_H / 2 - 0.025)),
            (PX + sx * (PLATE_W / 2 - 0.025), YF - 0.012, PZ + sz * (PLATE_H / 2 - 0.025)), 0.011, ALU, 6)

# Goosnav Book 2 (generic): 0.30 x 0.225, landscape cover (as gen_book_front.png)
BK_W, BK_H, BK_T = 0.30, 0.225, 0.045
BOOK_C = v3(PX - 0.15, YF - BK_T / 2 - 0.004, PZ + 0.085)
board = mat_color('board_blue', (0.0, 0.0331, 0.3515), rough=0.5)
pages = mat_color('page_edge', (0.86, 0.83, 0.76), rough=0.9)
bk_front = mat_image('cover_front', TEX + '/gen_book_front.png', rough=0.45, spec=0.35, coat=0.15)
bk_back = mat_image('cover_back', TEX + '/gen_book_back.png', rough=0.45, spec=0.35, coat=0.15)
bk_spine = mat_image('cover_spine', TEX + '/gen_book_spine.png', rough=0.45, spec=0.35, coat=0.15)
book = box((BK_W, BK_T, BK_H), BOOK_C, board,
           {(0, -1, 0): bk_front, (0, 1, 0): bk_back, (-1, 0, 0): bk_spine, (1, 0, 0): pages,
            (0, 0, 1): pages, (0, 0, -1): pages}, bevel=0.003)
# gold clips: mid-edges only, never over the title
for (dx, dz, sx, sz) in ((-BK_W / 2, -0.05, 0.02, 0.05), (BK_W / 2, 0.0, 0.02, 0.05), (0.05, -BK_H / 2, 0.06, 0.02)):
    box((sx, BK_T + 0.012, sz), BOOK_C + v3(dx, -0.003, dz), BRASS, bevel=0.002)

# sealed Goosklerf pack (generic, gen_pack.png)
PK_W, PK_H = 0.105, 0.105 * 1840 / 1160
PACK_C = v3(PX + 0.2, YF - 0.009, PZ + 0.09)
pk_front = mat_image('pack_front', TEX + '/gen_pack.png', rough=0.25, spec=0.7, coat=0.4)
pk_silver = mat_color('pack_silver', (0.78, 0.8, 0.84), rough=0.22, metal=1.0)
pack = box((PK_W, 0.012, PK_H), PACK_C, pk_silver, {(0, -1, 0): pk_front}, bevel=0.002)
for dz in (-1, 1):
    box((0.035, 0.022, 0.014), PACK_C + v3(0, -0.002, dz * PK_H / 2), BRASS, bevel=0.002)

# the pneumatic canister: an open tube along X, a hinged cap at +X, a pipe that ends in space
CAN_R = 0.06
CAN_X0, CAN_X1 = PX - 0.30, PX + 0.10
CAN_Y, CAN_Z = YF - CAN_R - 0.018, PZ - 0.165
CE = v3(CAN_X1, CAN_Y, CAN_Z)           # the open end
tube = cyl((CAN_X0, CAN_Y, CAN_Z), (CAN_X1, CAN_Y, CAN_Z), CAN_R, ALU, 32, fill='NOTHING')
tsol = tube.modifiers.new('sol', 'SOLIDIFY'); tsol.thickness = 0.004
cyl((CAN_X0 - 0.004, CAN_Y, CAN_Z), (CAN_X0 + 0.004, CAN_Y, CAN_Z), CAN_R, ALU, 32)
cyl((CAN_X0 + 0.02, CAN_Y, CAN_Z), (CAN_X0 + 0.045, CAN_Y, CAN_Z), CAN_R + 0.006, BRASS, 32)
cyl((CAN_X1 - 0.03, CAN_Y, CAN_Z), (CAN_X1 - 0.008, CAN_Y, CAN_Z), CAN_R + 0.006, BRASS, 32)
for x in (CAN_X0 + 0.08, CAN_X1 - 0.08):
    box((0.025, 0.02, 0.09), (x, YF - 0.01, CAN_Z), BRASS, bevel=0.002)
tube_inner = cyl((CAN_X0 + 0.01, CAN_Y, CAN_Z), (CAN_X1 - 0.004, CAN_Y, CAN_Z), CAN_R - 0.006, DARK, 32, fill='NOTHING')
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=CAN_R + 0.004, depth=0.012)
cap = own(bpy.context.object); cap.data.materials.append(BRASS); cap.rotation_mode = 'QUATERNION'
HINGE = CE + v3(0.006, 0, CAN_R + 0.004)
CAP_REST = CE + v3(0.006, 0, 0)
cyl(HINGE + v3(0, -0.02, 0), HINGE + v3(0, 0.02, 0), 0.006, BRASS, 8)
# pipe from the back of the canister, curling away and ending open in space
cu = bpy.data.curves.new('pipe', 'CURVE'); cu.dimensions = '3D'
cu.bevel_depth = 0.034; cu.bevel_resolution = 6; cu.use_fill_caps = False
spl = cu.splines.new('BEZIER'); spl.bezier_points.add(2)
pts = [(CAN_X0 - 0.004, CAN_Y, CAN_Z), (CAN_X0 - 0.35, CAN_Y - 0.12, CAN_Z + 0.02), (CAN_X0 - 0.55, CAN_Y - 0.62, CAN_Z + 0.32)]
hl = [(0.1, 0, 0), (0.12, 0.05, 0), (0.05, 0.12, -0.06)]
for bp_, p, h in zip(spl.bezier_points, pts, hl):
    bp_.co = p; bp_.handle_left = tuple(np.array(p) + h); bp_.handle_right = tuple(np.array(p) - h)
pipe = own(link(bpy.data.objects.new('pipe', cu))); cu.materials.append(ALU)
PIPE_END = v3(*pts[-1])
cyl(PIPE_END + v3(0.005, 0.03, -0.015) * 0.3, PIPE_END - v3(0.02, 0.08, -0.04) * 0.25, 0.041, BRASS, 24, fill='NOTHING')

# ---------------------------------------------------------------- comics (real scans only)
CM_W, CM_H = 0.20, 0.20 * 1080 / 1400
paper_back = TEX + '/page_00.png'
def blank_back():
    p = os.path.join(WORK, 'paper_back.png')
    if not os.path.exists(p):
        os.makedirs(WORK, exist_ok=True)
        im = bpy.data.images.new('pb', 64, 64)
        im.pixels.foreach_set(np.tile(np.array([0.93, 0.91, 0.86, 1], np.float32), 64 * 64))
        im.filepath_raw = p; im.file_format = 'PNG'; im.save()
    return p
BACK = blank_back()
comic_mats = {i: mat_two_sided(f'comic{i}', f'{TEX}/comic_{i:02d}.png', BACK, rough=0.8, translucent=0.1, glow=0.12)
              for i in range(7)}

def roll_mesh(w, h, k, mat, nx=28, nz=4):
    th = max(k * 1.75 * math.pi, 1e-4)
    r = w / th
    ph = np.linspace(-th / 2, th / 2, nx + 1)
    zs = np.linspace(-h / 2, h / 2, nz + 1)
    xs = r * np.sin(ph); ys = r * (1 - np.cos(ph)); ys -= ys.mean() * (k > 0.01)
    verts = [(xs[i], ys[i], z) for z in zs for i in range(nx + 1)]
    faces = []
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    me = bpy.data.meshes.new('roll'); me.from_pydata(verts, [], faces); me.update()
    uvl = me.uv_layers.new(name='UVMap')
    uv = [((i / nx), (j / nz)) for j in range(nz + 1) for i in range(nx + 1)]
    uvl.data.foreach_set('uv', np.array([uv[v] for f in faces for v in f]).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
    me.materials.append(mat)
    return me

ROLL_K = [1.0, 0.72, 0.48, 0.3, 0.16, 0.06, 0.0]
def roll_set(ci):
    obs = []
    for k in ROLL_K:
        ob = link(bpy.data.objects.new(f'roll{ci}', roll_mesh(CM_W, CM_H, k, comic_mats[ci])))
        ob.location = HIDE
        obs.append(ob)
    return obs
ROLL_A = roll_set(1)       # "Cheer up buddy..."
ROLL_B = roll_set(3)       # "Sleeping wastes so much time" -- the one that arrives at the end
TRAIL = []
for ci in (0, 2, 4, 5, 6):
    ob = link(bpy.data.objects.new(f'trail{ci}', roll_mesh(CM_W, CM_H, 0.07, comic_mats[ci], nx=10)))
    ob.location = HIDE
    TRAIL.append(ob)

# ---------------------------------------------------------------- planets (procedural, Goosklerf colours)
def planet_mat(name, ramp, wave_scale, distort, rim, rim_str, storm=None, pole=None, detail_scale=1.2):
    m, nt, out = new_mat(name)
    tc_ = nt.nodes.new('ShaderNodeTexCoord')
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'
    wv.inputs['Scale'].default_value = wave_scale; wv.inputs['Distortion'].default_value = distort
    wv.inputs['Detail'].default_value = 5; wv.inputs['Detail Scale'].default_value = detail_scale
    wv.inputs['Detail Roughness'].default_value = 0.6
    nt.links.new(tc_.outputs['Object'], wv.inputs['Vector'])
    cr = nt.nodes.new('ShaderNodeValToRGB')
    els = cr.color_ramp.elements
    for i, (pos, col) in enumerate(ramp):
        e = els[i] if i < 2 else els.new(pos)
        e.position = pos; e.color = (*col, 1)
    nt.links.new(wv.outputs['Fac'], cr.inputs[0])
    col = cr.outputs[0]
    if storm:   # an oval storm with its own swirl
        c, size, scol = storm
        sub = nt.nodes.new('ShaderNodeVectorMath'); sub.operation = 'SUBTRACT'
        sub.inputs[1].default_value = c
        nt.links.new(tc_.outputs['Object'], sub.inputs[0])
        sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'MULTIPLY'; sc.inputs[1].default_value = (1.0, 1.0, 1.9)
        nt.links.new(sub.outputs[0], sc.inputs[0])
        ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
        nt.links.new(sc.outputs[0], ln.inputs[0])
        sn = nt.nodes.new('ShaderNodeTexNoise'); sn.inputs['Scale'].default_value = 14; sn.inputs['Detail'].default_value = 4
        nt.links.new(tc_.outputs['Object'], sn.inputs['Vector'])
        dd = nt.nodes.new('ShaderNodeMath'); dd.operation = 'MULTIPLY_ADD'
        dd.inputs[1].default_value = size * 0.35
        nt.links.new(sn.outputs['Fac'], dd.inputs[0]); nt.links.new(ln.outputs['Value'], dd.inputs[2])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs[1].default_value = size * 1.15; mr.inputs[2].default_value = size * 0.8
        nt.links.new(dd.outputs[0], mr.inputs[0])
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'
        mx.inputs[7].default_value = (*scol, 1)
        nt.links.new(mr.outputs[0], mx.inputs['Factor']); nt.links.new(col, mx.inputs[6])
        col = mx.outputs[2]
    if pole:
        sp = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc_.outputs['Object'], sp.inputs[0])
        ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; nt.links.new(sp.outputs['Z'], ab.inputs[0])
        mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
        mr.inputs[1].default_value = 0.72; mr.inputs[2].default_value = 0.98
        nt.links.new(ab.outputs[0], mr.inputs[0])
        mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs[7].default_value = (*pole, 1)
        nt.links.new(mr.outputs[0], mx.inputs['Factor']); nt.links.new(col, mx.inputs[6])
        col = mx.outputs[2]
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.85; b.inputs['Specular IOR Level'].default_value = 0.15
    nt.links.new(col, b.inputs['Base Color'])
    # atmosphere: a limb glow on the sunward side
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.6
    nt.links.new(lw.outputs['Facing'], pw.inputs[0])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    L = nt.nodes.new('ShaderNodeCombineXYZ')
    dp = nt.nodes.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'
    nt.links.new(geo.outputs['Normal'], dp.inputs[0]); nt.links.new(L.outputs[0], dp.inputs[1])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs[1].default_value = -0.3; mr.inputs[2].default_value = 0.5
    nt.links.new(dp.outputs['Value'], mr.inputs[0])
    mu = nt.nodes.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'
    nt.links.new(pw.outputs[0], mu.inputs[0]); nt.links.new(mr.outputs[0], mu.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (*rim, 1)
    ms = nt.nodes.new('ShaderNodeMath'); ms.operation = 'MULTIPLY'; ms.inputs[1].default_value = rim_str
    nt.links.new(mu.outputs[0], ms.inputs[0]); nt.links.new(ms.outputs[0], em.inputs[1])
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(b.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    return m, L

def sphere(name, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=160, ring_count=80, radius=1.0)
    ob = bpy.context.object; ob.name = name
    ob.data.materials.append(mat)
    ob.data.polygons.foreach_set('use_smooth', np.ones(len(ob.data.polygons), bool))
    ob.rotation_mode = 'QUATERNION'; ob.location = HIDE
    ob.visible_shadow = False
    return ob

TEAL_M, TEAL_L = planet_mat('teal_giant', [(0.0, (0.010, 0.20, 0.25)), (0.35, (0.04, 0.42, 0.47)), (0.6, (0.16, 0.62, 0.66)),
                                           (1.0, (0.05, 0.36, 0.42))], 1.4, 1.5, (0.30, 0.85, 0.95), 5.0,
                             pole=(0.45, 0.80, 0.85))
ORANGE_M, ORANGE_L = planet_mat('orange_giant', [(0.0, (0.28, 0.06, 0.012)), (0.22, (0.75, 0.25, 0.04)),
                                                 (0.45, (0.95, 0.62, 0.30)), (0.62, (0.62, 0.17, 0.03)),
                                                 (0.8, (0.98, 0.75, 0.45)), (1.0, (0.45, 0.11, 0.02))], 3.2, 5.5,
                                (1.0, 0.55, 0.25), 2.0, storm=((0.62, -0.62, -0.32), 0.17, (0.62, 0.08, 0.02)))
PURPLE_M, PURPLE_L = planet_mat('purple_world', [(0.0, (0.10, 0.02, 0.22)), (0.3, (0.30, 0.10, 0.55)),
                                                 (0.55, (0.55, 0.36, 0.78)), (0.8, (0.22, 0.06, 0.42)),
                                                 (1.0, (0.42, 0.22, 0.66))], 2.2, 2.5, (0.70, 0.50, 1.0), 3.0,
                                pole=(0.20, 0.05, 0.36))
teal = sphere('teal', TEAL_M); orange = sphere('orange', ORANGE_M); purple = sphere('purple', PURPLE_M)
PLANET_L = [TEAL_L, ORANGE_L, PURPLE_L]

# rings: annulus with a planet-shadow term computed in the shader
def build_rings():
    ns, nr = 256, 2
    r0, r1 = 1.45, 2.45
    verts, faces = [], []
    for i in range(nr + 1):
        r = r0 + (r1 - r0) * i / nr
        for j in range(ns):
            a = 2 * math.pi * j / ns
            verts.append((r * math.cos(a), r * math.sin(a), 0))
    for i in range(nr):
        for j in range(ns):
            a = i * ns + j; b = i * ns + (j + 1) % ns
            faces.append((a, b, b + ns, a + ns))
    me = bpy.data.meshes.new('rings'); me.from_pydata(verts, [], faces); me.update()
    m, nt, out = new_mat('rings')
    tc_ = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    nt.links.new(tc_.outputs['Object'], ln.inputs[0])
    cx = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(ln.outputs['Value'], cx.inputs['X'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.noise_dimensions = '1D'
    nz.inputs['Scale'].default_value = 9.0; nz.inputs['Detail'].default_value = 8; nz.inputs['Roughness'].default_value = 0.62
    nt.links.new(ln.outputs['Value'], nz.inputs['W'])
    a_r = nt.nodes.new('ShaderNodeValToRGB')
    e = a_r.color_ramp.elements
    e[0].position = 0.38; e[0].color = (0, 0, 0, 1); e[1].position = 0.62; e[1].color = (1, 1, 1, 1)
    nt.links.new(nz.outputs['Fac'], a_r.inputs[0])
    edge = nt.nodes.new('ShaderNodeMapRange')   # soft inner/outer edges and a Cassini-like gap
    edge.inputs[1].default_value = 1.45; edge.inputs[2].default_value = 1.6
    nt.links.new(ln.outputs['Value'], edge.inputs[0])
    edge2 = nt.nodes.new('ShaderNodeMapRange')
    edge2.inputs[1].default_value = 2.45; edge2.inputs[2].default_value = 2.2
    nt.links.new(ln.outputs['Value'], edge2.inputs[0])
    gap = nt.nodes.new('ShaderNodeMapRange'); gap.interpolation_type = 'SMOOTHSTEP'
    gap.inputs[1].default_value = 0.0; gap.inputs[2].default_value = 0.03
    dist = nt.nodes.new('ShaderNodeMath'); dist.operation = 'SUBTRACT'; dist.inputs[1].default_value = 2.02
    nt.links.new(ln.outputs['Value'], dist.inputs[0])
    absd = nt.nodes.new('ShaderNodeMath'); absd.operation = 'ABSOLUTE'; nt.links.new(dist.outputs[0], absd.inputs[0])
    nt.links.new(absd.outputs[0], gap.inputs[0])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    nt.links.new(edge.outputs[0], m1.inputs[0]); nt.links.new(edge2.outputs[0], m1.inputs[1])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(gap.outputs[0], m2.inputs[1])
    sepc = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(a_r.outputs[0], sepc.inputs[0])
    alpha = nt.nodes.new('ShaderNodeMath'); alpha.operation = 'MULTIPLY'
    nt.links.new(sepc.outputs[0], alpha.inputs[0]); nt.links.new(m2.outputs[0], alpha.inputs[1])
    alpha2 = nt.nodes.new('ShaderNodeMath'); alpha2.operation = 'MULTIPLY_ADD'
    alpha2.inputs[1].default_value = 0.75; alpha2.inputs[2].default_value = 0.0
    nt.links.new(alpha.outputs[0], alpha2.inputs[0])
    col_r = nt.nodes.new('ShaderNodeValToRGB')
    ce = col_r.color_ramp.elements
    ce[0].position = 0.0; ce[0].color = (0.30, 0.20, 0.40, 1); ce[1].position = 1.0; ce[1].color = (0.85, 0.78, 0.92, 1)
    nt.links.new(nz.outputs['Fac'], col_r.inputs[0])
    # planet shadow: P is shadowed when the planet sphere lies between P and the sun
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    C = nt.nodes.new('ShaderNodeCombineXYZ'); L = nt.nodes.new('ShaderNodeCombineXYZ'); Rv = nt.nodes.new('ShaderNodeValue')
    vs = nt.nodes.new('ShaderNodeVectorMath'); vs.operation = 'SUBTRACT'
    nt.links.new(C.outputs[0], vs.inputs[0]); nt.links.new(geo.outputs['Position'], vs.inputs[1])
    td = nt.nodes.new('ShaderNodeVectorMath'); td.operation = 'DOT_PRODUCT'
    nt.links.new(vs.outputs[0], td.inputs[0]); nt.links.new(L.outputs[0], td.inputs[1])
    tl = nt.nodes.new('ShaderNodeVectorMath'); tl.operation = 'SCALE'
    nt.links.new(L.outputs[0], tl.inputs[0]); nt.links.new(td.outputs['Value'], tl.inputs['Scale'])
    pp = nt.nodes.new('ShaderNodeVectorMath'); pp.operation = 'SUBTRACT'
    nt.links.new(vs.outputs[0], pp.inputs[0]); nt.links.new(tl.outputs[0], pp.inputs[1])
    pl = nt.nodes.new('ShaderNodeVectorMath'); pl.operation = 'LENGTH'; nt.links.new(pp.outputs[0], pl.inputs[0])
    rr = nt.nodes.new('ShaderNodeMath'); rr.operation = 'DIVIDE'
    nt.links.new(pl.outputs['Value'], rr.inputs[0]); nt.links.new(Rv.outputs[0], rr.inputs[1])
    inside = nt.nodes.new('ShaderNodeMapRange'); inside.interpolation_type = 'SMOOTHSTEP'
    inside.inputs[1].default_value = 1.0; inside.inputs[2].default_value = 0.96
    nt.links.new(rr.outputs[0], inside.inputs[0])
    front = nt.nodes.new('ShaderNodeMath'); front.operation = 'GREATER_THAN'; front.inputs[1].default_value = 0.0
    nt.links.new(td.outputs['Value'], front.inputs[0])
    sh = nt.nodes.new('ShaderNodeMath'); sh.operation = 'MULTIPLY'
    nt.links.new(inside.outputs[0], sh.inputs[0]); nt.links.new(front.outputs[0], sh.inputs[1])
    lit = nt.nodes.new('ShaderNodeMapRange'); lit.inputs[3].default_value = 1.0; lit.inputs[4].default_value = 0.06
    nt.links.new(sh.outputs[0], lit.inputs[0])
    shade = nt.nodes.new('ShaderNodeMix'); shade.data_type = 'RGBA'; shade.blend_type = 'MULTIPLY'
    shade.inputs['Factor'].default_value = 1.0
    nt.links.new(col_r.outputs[0], shade.inputs[6]); nt.links.new(lit.outputs[0], shade.inputs[7])
    b = nt.nodes.new('ShaderNodeBsdfDiffuse'); nt.links.new(shade.outputs[2], b.inputs['Color'])
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    mx = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(alpha2.outputs[0], mx.inputs[0]); nt.links.new(tp.outputs[0], mx.inputs[1]); nt.links.new(b.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; m.use_backface_culling = False
    m.show_transparent_back = False
    me.materials.append(m)
    ob = link(bpy.data.objects.new('rings', me)); ob.rotation_mode = 'QUATERNION'; ob.location = HIDE
    ob.visible_shadow = False
    return ob, C, L, Rv
rings, RING_C, RING_L, RING_R = build_rings()

# ---------------------------------------------------------------- the die the size of a moon
PIP_OF = {(0, 0, 1): 1, (0, 0, -1): 6, (1, 0, 0): 2, (-1, 0, 0): 5, (0, 1, 0): 3, (0, -1, 0): 4}
die_fm = {n: mat_image(f'die_teal_{p}', f'{TEX}/die_teal_{p}.png', rough=0.3, spec=0.5, coat=0.5) for n, p in PIP_OF.items()}
die = make_box('die', (2.0, 2.0, 2.0), die_fm, die_fm[(0, 0, 1)], bevel=0.22)
die.location = HIDE; die.visible_shadow = False

# ---------------------------------------------------------------- honest lens flare: ghosts in camera space
def ghost_mat(name, rgb):
    m, nt, out = new_mat(name)
    tc_ = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    nt.links.new(tc_.outputs['Object'], ln.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs[1].default_value = 1.0; mr.inputs[2].default_value = 0.55; mr.inputs[3].default_value = 0.0
    mr.inputs[4].default_value = 1.0
    nt.links.new(ln.outputs['Value'], mr.inputs[0])
    rim = nt.nodes.new('ShaderNodeMapRange'); rim.inputs[1].default_value = 0.6; rim.inputs[2].default_value = 0.98
    rim.inputs[3].default_value = 0.35; rim.inputs[4].default_value = 1.0
    nt.links.new(ln.outputs['Value'], rim.inputs[0])
    mu = nt.nodes.new('ShaderNodeMath'); mu.operation = 'MULTIPLY'
    nt.links.new(mr.outputs[0], mu.inputs[0]); nt.links.new(rim.outputs[0], mu.inputs[1])
    strength = nt.nodes.new('ShaderNodeValue'); strength.outputs[0].default_value = 0.0
    mu2 = nt.nodes.new('ShaderNodeMath'); mu2.operation = 'MULTIPLY'
    nt.links.new(mu.outputs[0], mu2.inputs[0]); nt.links.new(strength.outputs[0], mu2.inputs[1])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (*rgb, 1)
    nt.links.new(mu2.outputs[0], em.inputs[1])
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(tp.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs[0])
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; m.use_backface_culling = False
    return m, strength.outputs[0]

GHOSTS = []   # (object, strength socket, position factor along the flare axis, size, base strength)
for k, (f, size, rgb, s0, sides) in enumerate([
        (0.62, 0.030, (0.55, 0.85, 1.0), 0.9, 6), (0.28, 0.018, (1.0, 0.75, 0.4), 1.3, 6),
        (-0.22, 0.045, (0.45, 1.0, 0.8), 0.5, 6), (-0.55, 0.080, (0.75, 0.55, 1.0), 0.32, 6),
        (-0.95, 0.052, (1.0, 0.65, 0.35), 0.45, 6), (-1.45, 0.14, (0.4, 0.8, 1.0), 0.18, 64)]):
    bpy.ops.mesh.primitive_circle_add(vertices=sides, radius=1.0, fill_type='NGON')
    ob = bpy.context.object; ob.rotation_mode = 'QUATERNION'; ob.location = HIDE; ob.visible_shadow = False
    m, sock = ghost_mat(f'ghost{k}', rgb)
    ob.data.materials.append(m)
    GHOSTS.append((ob, sock, f, size, s0))
# a long, faint horizontal streak through the sun (anamorphic-ish, subtle)
bpy.ops.mesh.primitive_circle_add(vertices=48, radius=1.0, fill_type='NGON')
streak = bpy.context.object; streak.rotation_mode = 'QUATERNION'; streak.location = HIDE; streak.visible_shadow = False
sm_, STREAK_S = ghost_mat('streak', (0.85, 0.92, 1.0)); streak.data.materials.append(sm_)

# ---------------------------------------------------------------- camera
cam, cam_d = make_camera(clip_end=9000)

def cam_rot(eye, tgt, roll=0.0):
    return np.array(look_at_quat(eye, tgt, roll).to_matrix())

def cdir(x, y):
    """camera-space direction (tangent units) -> unit vector, -Z forward"""
    return norm(v3(x, y, -1.0))

# ---------------------------------------------------------------- shots
def shot_of(t):
    for i in range(len(SHOT_T) - 1):
        if t < SHOT_T[i + 1]:
            return i
    return len(SHOT_T) - 2

def camera_at(t):
    """-> eye, tgt, lens(mm, portrait), roll, clip_start"""
    s = shot_of(t)
    if s == 0:     # sunrise over the ice giant; the probe tiny in the upper third
        u = sm(0.0, T_S2, t)
        eye = v3(-15, -46, -9) + v3(3.0, 1.0, 2.5) * u
        tgt = v3(-1.0, 0, -13.0) + v3(1.5, 0, 0.5) * u
        return eye, tgt, 36, math.radians(-4 + 2.5 * u), 0.2
    if s == 1:     # macro glide from the bus, along the boom, to the plate
        a = sm(T_S2, 9.4, t)
        eye = lerp(v3(-1.05, -0.92, 0.42), v3(-2.42, -0.86, 0.14), a)
        tgt0 = lerp(v3(-0.82, -0.25, 0.02), BOOK_C, a)
        b = sm(9.9, 11.4, t); c = sm(12.3, 13.9, t)
        tgt = lerp(lerp(tgt0, PACK_C + v3(-0.05, 0, 0), b), v3(CAN_X0 + 0.25, CAN_Y, CAN_Z + 0.02), c)
        eye = eye + v3(0.14, 0.0, 0.0) * b + v3(-0.06, 0.08, -0.1) * c
        return eye, tgt, lerp(30, 36, a), 0.0, 0.01
    if s == 2:     # the book: slow push, raking sun
        u = sm(T_S3, T_S4, t)
        eye = lerp(v3(-2.62, -0.74, -0.02), v3(-2.71, -0.54, 0.06), u)
        return eye, BOOK_C + v3(0.0, 0, 0.004), 40, math.radians(1.5 - 2.0 * u), 0.01
    if s == 3:     # gas giant, the probe crossing it
        u = sm(T_S4, T_S5, t)
        a = math.radians(-118 + 26 * u)
        rad = 25 - 4 * u
        eye = v3(rad * math.cos(a), rad * math.sin(a), 5.0 - 1.5 * u)
        return eye, v3(0.2, 0, -1.2 + 0.4 * u), 40, math.radians(3 - 3 * u), 0.2
    if s == 4:     # canister ECU -> the comic comes to the lens
        eye_c = lerp(v3(CE[0] + 0.24, CE[1] - 0.36, CE[2] + 0.07), v3(CE[0] + 0.21, CE[1] - 0.31, CE[2] + 0.06), sm(T_S5, T_ARRIVE1, t))
        tgt_c = CE + v3(-0.06, 0, 0)
        e_read, p_read = read_pose(t)
        b = sm(T_ARRIVE1 + 0.7, T_ARRIVE1 + 3.3, t)
        return lerp(eye_c, e_read, b), lerp(tgt_c, p_read, b), 36, 0.0, 0.01
    if s == 5:     # the ringed world and the die
        u = sm(T_S6, T_S7, t)
        eye = v3(-9, -27, -2) + v3(4.5, 1.5, 0.8) * u
        return eye, v3(0, 0, 5.2), 30, math.radians(-3 + 3 * u), 0.2
    if s == 6:     # recede
        u = (t - T_S7) / (T_S8 - T_S7)
        eye = v3(-2.2, -6.2, 0.6) + v3(0.0, -0.5, 0.1) * u
        return eye, probe_pos(t) + v3(0, 0, 0.3), 30, 0.0, 0.05
    u = sm(T_S8, T_END, t)   # hero
    eye = lerp(v3(PX + 0.03, -1.36, 0.0), v3(PX + 0.02, -1.20, 0.02), u)
    return eye, v3(PX + 0.0, PY, 0.19), 36, 0.0, 0.01

# reading pose for comic_01
P_READ = CE + v3(0.23, -0.27, 0.10)
N_READ = norm(v3(0.12, -1.0, 0.10))
def read_pose(t):
    d = lerp(0.30, 0.272, sm(T_ARRIVE1 + 3.0, T_S6, t))
    return P_READ + N_READ * d, P_READ

def probe_pos(t):
    if T_S7 <= t < T_S8:
        u = t - T_S7
        return norm(v3(0.35, 1.0, 0.08)) * (1.0 * u + 1.1 * u * u)
    return v3(0, 0, 0)

# per-shot world: sun direction (camera space), planets (camera space dir, distance, radius), planetshine
REF = {}
def ref_rot(s):
    if s not in REF:
        e, g, _, r, _ = camera_at(SHOT_T[s] + 0.001)
        REF[s] = (e, cam_rot(e, g, r))
    return REF[s]

SHOTS = {
    0: dict(sun=(0.105, -0.07), planets=[('teal', (0.0, None), 2400, 1650, (0.3, 0.2, 0.9))],
            shine=((0.1, 0.55, 0.6), 0.5, 'teal'), sunE=5.0, stars=1.4),
    1: dict(sunW=norm(v3(-0.55, -1.0, 0.75)), planets=[], shine=((0.1, 0.5, 0.55), 0.35, None), sunE=4.2, stars=1.0),
    2: dict(sunW=norm(v3(-1.0, -0.42, 0.42)), planets=[], shine=((0.1, 0.5, 0.55), 0.35, None), sunE=4.4, stars=1.0),
    3: dict(sun=(-1.1, 0.45, 0.8), planets=[('orange', (0.02, -0.52), 2600, 1500, (0.2, 1.0, 0.25))],
            shine=((0.85, 0.4, 0.12), 0.45, 'orange'), sunE=4.6, stars=1.2),
    4: dict(sunW=norm(v3(-0.25, -1.0, 0.62)), planets=[], shine=((0.4, 0.2, 0.6), 0.35, None), sunE=4.0, stars=1.0),
    5: dict(sun=(-0.75, 0.35, 0.75), planets=[('purple', (0.34, 0.36), 3600, 820, (0.35, 0.25, 1.0))],
            shine=((0.35, 0.15, 0.6), 0.4, 'purple'), sunE=4.6, stars=1.3),
    6: dict(sun=(0.26, 0.36), planets=[], shine=((0.35, 0.15, 0.6), 0.45, None), sunE=5.0, stars=1.6),
    7: dict(sunW=norm(v3(-0.5, -1.0, 0.55)), planets=[], shine=((0.25, 0.3, 0.55), 0.35, None), sunE=4.2, stars=1.2),
}
PLANET_OB = {'teal': teal, 'orange': orange, 'purple': purple}

def sun_dir(s, t):
    cfg = SHOTS[s]
    if 'sunW' in cfg:
        return cfg['sunW']
    e, R = ref_rot(s)
    sx = cfg['sun']
    if len(sx) == 3:   # (x, y, z) camera-space vector (z>0 = behind the camera)
        return norm(R @ norm(v3(*sx)))
    return norm(R @ cdir(sx[0], sx[1]))

def planet_center(s, name, cfg_p, t):
    e, R = ref_rot(s)
    _, (x, y), dist, rad, _ = cfg_p
    if s == 0:   # the planet sinks: the sun rises over the limb
        el = math.radians(-43.3 - 9.0 * (1 - math.exp(-t / 2.4)))
        d = v3(0.0, math.sin(el), -math.cos(el))
        return e + R @ d * dist
    return e + R @ cdir(x, y) * dist

def set_world(s, t, eye, R_cam, lens):
    cfg = SHOTS[s]
    L = sun_dir(s, t)
    sun_ob.rotation_quaternion = Vector(-L).to_track_quat('-Z', 'Y')
    sun_d.energy = cfg['sunE']
    sun_d.shadow_cascade_max_distance = 3.0 if s in (1, 2, 4, 7) else 60.0
    sun_disk.location = Vector(eye + L * SUN_DIST); sun_disk.scale = (SUN_R,) * 3
    STAR_STR.default_value = cfg['stars']
    col, strength, pname = cfg['shine']
    PS_COLOR.default_value = (*col, 1)
    PS_STR.default_value = strength
    for pl in PLANET_L + [RING_L]:
        pl.inputs[0].default_value, pl.inputs[1].default_value, pl.inputs[2].default_value = L
    for ob in PLANET_OB.values():
        ob.location = HIDE
    rings.location = HIDE
    occluders = []
    shine_dir = -L
    for cfg_p in cfg['planets']:
        name = cfg_p[0]; ob = PLANET_OB[name]
        C = planet_center(s, name, cfg_p, t); rad = cfg_p[3]
        ob.location = Vector(C); ob.scale = (rad, rad, rad * 0.985)
        ax = norm(v3(*cfg_p[4]))
        spin = 0.012 * t if name == 'orange' else 0.004 * t
        q = Vector((0, 0, 1)).rotation_difference(Vector(ax))
        q = q @ Quaternion((0, 0, 1), spin)
        ob.rotation_quaternion = q
        occluders.append((C, rad))
        shine_dir = norm(C - eye)
        if name == 'purple':
            rings.location = Vector(C); rings.scale = (rad, rad, rad)
            rings.rotation_quaternion = q
            RING_C.inputs[0].default_value, RING_C.inputs[1].default_value, RING_C.inputs[2].default_value = C
            RING_R.outputs[0].default_value = rad
    if s == 6:
        shine_dir = norm(v3(-0.3, -1.0, -0.2))
    PS_DIR.inputs[0].default_value, PS_DIR.inputs[1].default_value, PS_DIR.inputs[2].default_value = shine_dir
    set_flare(eye, R_cam, lens, L, occluders, t)

def set_flare(eye, R_cam, lens, L, occluders, t):
    dc = R_cam.T @ L
    vis = 0.0
    if dc[2] < -0.05:
        px, py = dc[0] / -dc[2], dc[1] / -dc[2]
        hy = 18.0 / lens; hx = hy * FULL_W / FULL_H
        m = max(abs(px) / hx, abs(py) / hy)
        vis = float(1 - ss(0.95, 1.5, m))
        for C, rad in occluders:
            d = C - eye; dist = np.linalg.norm(d)
            sep = math.acos(np.clip(np.dot(L, d / dist), -1, 1))
            ang = math.asin(min(rad / dist, 1.0))
            vis *= float(ss(ang - 0.002, ang + 0.012, sep))
    q = look_at_quat(eye, eye + R_cam @ v3(0, 0, -1))
    rot_q = Quaternion(q)
    D = 1.0
    for ob, sock, f, size, s0 in GHOSTS:
        if vis <= 0.001:
            ob.location = HIDE; continue
        pc = v3(px * f, py * f, -D)
        ob.location = Vector(eye + R_cam @ pc)
        ob.rotation_quaternion = rot_q @ Quaternion((0, 0, 1), 0.3)
        ob.scale = (size * D,) * 3
        sock.default_value = s0 * vis
    if vis <= 0.001:
        streak.location = HIDE
    else:
        pc = v3(px, py, -D * 1.02)
        streak.location = Vector(eye + R_cam @ pc)
        streak.rotation_quaternion = rot_q
        streak.scale = (0.9, 0.0035, 1.0)
        STREAK_S.default_value = 1.3 * vis

# ---------------------------------------------------------------- the canister and the comics
def cap_angle(t):
    a = 0.0
    if T_ARRIVE1 <= t < T_S6:
        a = ss(T_ARRIVE1, T_ARRIVE1 + 0.28, t) * 1.0 + 0.9 * ss(T_ARRIVE1 + 0.2, T_ARRIVE1 + 0.9, t)
        a -= 0.12 * math.sin((t - T_ARRIVE1) * 9) * math.exp(-(t - T_ARRIVE1) * 3) * (t > T_ARRIVE1 + 0.3)
    if t >= T_ARRIVE2:
        a = ss(T_ARRIVE2, T_ARRIVE2 + 0.25, t) * 1.0 + 0.85 * ss(T_ARRIVE2 + 0.18, T_ARRIVE2 + 0.8, t)
        a -= 0.12 * math.sin((t - T_ARRIVE2) * 9) * math.exp(-(t - T_ARRIVE2) * 3) * (t > T_ARRIVE2 + 0.3)
    return a

def set_cap(t):
    a = cap_angle(t)
    q = Quaternion((0, 1, 0), -a)
    base = Quaternion((0, 1, 0), math.pi / 2)    # disc axis Z -> X
    cap.rotation_quaternion = q @ base
    cap.location = Vector(HINGE + np.array(q.to_matrix()) @ (CAP_REST - HINGE))

R_ROLL = np.column_stack([v3(0, 1, 0), v3(0, 0, 1), v3(1, 0, 0)])   # sheet Z along the canister axis
Q_ROLL = Matrix(R_ROLL.tolist()).to_quaternion()

def place(ob, pos, q):
    ob.matrix_world = Matrix.LocRotScale(Vector(pos), q, Vector((1, 1, 1)))

def show_roll(obs, k_idx, pos, q):
    for i, ob in enumerate(obs):
        if i == k_idx:
            place(ob, pos, q)
        else:
            ob.location = HIDE

def set_comics(t):
    # comic_01: slides out, uncurls, comes to be read
    if T_ARRIVE1 + 0.15 <= t < T_S6:
        t0 = T_ARRIVE1 + 0.15
        slide = float(sm(t0, t0 + 0.95, t))
        pos_roll = CE + v3(1, 0, 0) * (-CM_H / 2 + slide * (CM_H / 2 + 0.035))
        unroll = float(ss(t0 + 0.85, t0 + 1.9, t))
        k_idx = min(int(unroll * (len(ROLL_K) - 1) + 0.5), len(ROLL_K) - 1)
        R_read = frames_from(N_READ[None], v3(0, 0, 1)[None])[0]
        q_read = Matrix(R_read.tolist()).to_quaternion()
        turn = float(sm(t0 + 0.9, t0 + 2.9, t))
        drift = float(sm(t0 + 0.9, t0 + 3.2, t))
        pos = lerp(pos_roll, P_READ, drift)
        # after it arrives, a slow living drift (small, keeps it readable)
        w = t - (t0 + 3.2)
        if w > 0:
            pos = pos + v3(0.004 * math.sin(w * 0.7), 0.0, 0.003 * math.sin(w * 0.55 + 1))
        q = Q_ROLL.slerp(q_read, turn)
        if w > 0:
            q = q @ Quaternion((0, 1, 0), 0.02 * math.sin(w * 0.6))
        show_roll(ROLL_A, k_idx, pos, q)
    else:
        show_roll(ROLL_A, -1, HIDE, Quaternion())
    # comic_03: the one that arrives at the end, half out, still rolled
    if t >= T_ARRIVE2 + 0.12:
        t0 = T_ARRIVE2 + 0.12
        slide = float(sm(t0, t0 + 1.2, t))
        pos = CE + v3(1, 0, 0) * (-CM_H / 2 + slide * (CM_H * 0.62))
        q = Q_ROLL @ Quaternion((0, 0, 1), 0.15 * slide)
        show_roll(ROLL_B, 1, pos, q)
    else:
        show_roll(ROLL_B, -1, HIDE, Quaternion())

TRAIL_P = [v3(-0.9, 1.6, 0.5), v3(1.1, 2.6, -0.5), v3(-0.3, 4.0, 1.2), v3(1.6, 5.5, 0.9), v3(-1.5, 7.0, -0.6)]
def set_trail(t, eye, R_cam):
    if not (T_S7 <= t < T_S8):
        for ob in TRAIL:
            ob.location = HIDE
        return
    u = t - T_S7
    for i, ob in enumerate(TRAIL):
        p = TRAIL_P[i] + v3(0.25 * (i % 2 * 2 - 1), 0.5, 0.12 * math.sin(i)) * u
        c = R_cam @ v3(p[0], p[2], -p[1])
        q = Quaternion(Vector((0.3, 1, 0.2 * i)).normalized(), 0.4 * i + 0.35 * u * (1 + 0.2 * i)) @ Quaternion((1, 0, 0), 1.2 + 0.3 * i)
        place(ob, eye + c, q)

# ---------------------------------------------------------------- the die
def set_die(t, s):
    if s != 5:
        die.location = HIDE; return
    e, R = ref_rot(5)
    dt = t - T_SIX
    D = 1500.0
    x = -0.30 + 0.085 * dt
    y = 0.00 - 0.012 * dt
    pos = e + R @ cdir(x, y) * D
    to_cam = norm(e - pos)
    half = 175.0
    # face 6 (local -Z) toward the camera at T_SIX; tumbling fast before, slowing through it
    up = R @ v3(0, 1, 0)
    zc = -to_cam
    xc = norm(np.cross(up, zc)); yc = np.cross(zc, xc)
    R6 = np.column_stack([xc, yc, zc])
    ang = 0.22 * dt + 0.05 * dt ** 3
    ax = norm(R @ v3(0.45, 1.0, 0.3))
    Rt = rot_axis(ax[None], np.array([ang]))[0] @ R6
    die.matrix_world = Matrix.LocRotScale(Vector(pos), Matrix(Rt.tolist()).to_quaternion(), Vector((half, half, half)))

# ---------------------------------------------------------------- update
def update(t):
    s = shot_of(t)
    eye, tgt, lens, roll, clip = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, P(lens), roll)
    cam_d.clip_start = clip
    R_cam = cam_rot(eye, tgt, roll)
    pp = probe_pos(t)
    root.location = Vector(pp)
    set_world(s, t, eye, R_cam, lens)
    set_cap(t); set_comics(t); set_trail(t, eye, R_cam); set_die(t, s)
    return t >= T_END + 0.5

def events():
    ev = {'T': {k: v for k, v in globals().items() if k.startswith('T_') and isinstance(v, float)},
          'cuts': SHOT_T[1:-1]}
    os.makedirs(WORK, exist_ok=True)
    json.dump(ev, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

CUT_FRAMES = [math.ceil(x * FPS - 1e-6) for x in SHOT_T[1:-1]]

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
