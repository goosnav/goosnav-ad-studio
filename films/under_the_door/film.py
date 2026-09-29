"""UNDER THE DOOR -- the Goosnav Patreon / Goosnav Book 2 / Goosklerf. ~58 s, 4:5, Blender Eevee.
A bedroom at 3:14 a.m. Comics come under the door, then the tide. Underwater, Book 2 is a lighthouse.
Everything is driven by update(t). Run through the studio CLI:

  python3 -m studio preview under_the_door --format 4x5 --every 12
  python3 -m studio render  under_the_door --format 4x5
"""
import sys, os
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa: F401,F403
import bstudio as bs
from studio import config
from PIL import Image, ImageDraw

FILM = 'under_the_door'
TEX = str(config.textures())
WORK = str(config.path('work', FILM, FORMAT))
FPS = 24
DUR = 58.5
rng = np.random.default_rng(314)
set_rng(rng)

# ---------------------------------------------------------------- timeline (cuts on whole frames)
T_SLIDE0 = 0.5       # first comic out of the gap
T_S2 = 5.5           # the room
T_S3 = 13.0          # the tide
T_FLOOD = 14.4       # the level starts to rise
T_UNDER = 19.75      # cut to underwater
T_S5 = 26.625        # the lighthouse
T_S6 = 35.25         # looking up at the bed
T_DAWN = 42.375      # dry room at dawn
T_S8 = 48.75         # desk hero
T_END = 55.0         # white card (overlay); frames after are black
SLIDE_TIMES = [T_SLIDE0, 6.9, 9.0, 10.5, 11.5, 12.2, 12.7, 13.1, 13.4, 13.65]
CUT_FRAMES = [round(x * FPS) for x in (T_S2, T_S3, T_UNDER, T_S5, T_S6, T_DAWN, T_S8)]

U = v3(200.0, 0.0, 0.0)     # the underwater set lives far from the room

scene = setup_scene(fps=FPS, samples=20, bloom=(0.9, 0.08, 6.5))
ee = scene.eevee
ee.use_volumetric_lights = True
ee.volumetric_start = 0.1
ee.volumetric_end = 70.0
ee.volumetric_tile_size = '8'
ee.volumetric_samples = 48
ee.volumetric_light_clamp = 0.0
ee.shadow_cascade_size = '2048'

# ---------------------------------------------------------------- helpers
def mat_driven_image(name, path, rough=0.5, spec=0.3, coat=0.0):
    """image material whose emission (same image) is driven per frame -> returns (mat, strength socket)"""
    m, nt, out = new_mat(name)
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(path); t.interpolation = 'Cubic'; t.extension = 'EXTEND'
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    nt.links.new(t.outputs[0], b.inputs['Base Color'])
    nt.links.new(t.outputs[0], b.inputs['Emission Color'])
    b.inputs['Emission Strength'].default_value = 0.0
    nt.links.new(b.outputs[0], out.inputs[0])
    return m, b.inputs['Emission Strength']

INK_SOCKETS, PAPER_GLOW = [], []
def mat_comic(name, path, ink_rgb=(0.35, 0.85, 1.0)):
    """a comic board: front = scan, back = the same scan mirrored and faint (show-through).
    Ink emission is driven per frame (bioluminescent underwater, zero in the room)."""
    m, nt, out = new_mat(name)
    L = nt.links.new
    uv = nt.nodes.new('ShaderNodeUVMap')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Location'].default_value = (1, 0, 0); mp.inputs['Scale'].default_value = (-1, 1, 1)
    L(uv.outputs[0], mp.inputs[0])
    tf = nt.nodes.new('ShaderNodeTexImage'); tf.image = img(path); tf.extension = 'EXTEND'
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = img(path); tb.extension = 'EXTEND'
    L(uv.outputs[0], tf.inputs[0]); L(mp.outputs[0], tb.inputs[0])
    paper = (0.93, 0.91, 0.86, 1)
    back = nt.nodes.new('ShaderNodeMix'); back.data_type = 'RGBA'; back.inputs['Factor'].default_value = 0.22
    back.inputs[6].default_value = paper; L(tb.outputs[0], back.inputs[7])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    L(geo.outputs['Backfacing'], mix.inputs['Factor'])
    L(tf.outputs[0], mix.inputs[6]); L(back.outputs[2], mix.inputs[7])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = 0.8
    b.inputs['Specular IOR Level'].default_value = 0.2
    L(mix.outputs[2], b.inputs['Base Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); L(mix.outputs[2], tr.inputs['Color'])
    ms = nt.nodes.new('ShaderNodeMixShader'); ms.inputs[0].default_value = 0.2
    L(b.outputs[0], ms.inputs[1]); L(tr.outputs[0], ms.inputs[2])
    # paper glow (keeps white white under coloured light)
    eg = nt.nodes.new('ShaderNodeEmission'); L(mix.outputs[2], eg.inputs[0]); eg.inputs[1].default_value = 0.15
    PAPER_GLOW.append(eg.inputs[1])
    # ink glow: (1 - luminance) of the scan, front side only
    bw = nt.nodes.new('ShaderNodeRGBToBW'); L(tf.outputs[0], bw.inputs[0])
    inv = nt.nodes.new('ShaderNodeMapRange')
    inv.inputs['From Min'].default_value = 0.25; inv.inputs['From Max'].default_value = 0.75
    inv.inputs['To Min'].default_value = 1.0; inv.inputs['To Max'].default_value = 0.0
    L(bw.outputs[0], inv.inputs['Value'])
    ei = nt.nodes.new('ShaderNodeEmission'); ei.inputs[0].default_value = (*ink_rgb, 1)
    L(inv.outputs[0], ei.inputs[1])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    L(inv.outputs[0], mul.inputs[0]); mul.inputs[1].default_value = 0.0
    INK_SOCKETS.append(mul.inputs[1])
    L(mul.outputs[0], ei.inputs[1])
    a1 = nt.nodes.new('ShaderNodeAddShader'); L(ms.outputs[0], a1.inputs[0]); L(eg.outputs[0], a1.inputs[1])
    a2 = nt.nodes.new('ShaderNodeAddShader'); L(a1.outputs[0], a2.inputs[0]); L(ei.outputs[0], a2.inputs[1])
    L(a2.outputs[0], out.inputs[0])
    m.use_backface_culling = False
    return m

def empty(name):
    e = bpy.data.objects.new(name, None); link(e); return e
def parent(ch, par, loc, rot=(0, 0, 0)):
    ch.parent = par; ch.location = loc; ch.rotation_euler = rot
    return ch
def mat_from(R, p, s=1.0):
    M = np.eye(4); M[:3, :3] = np.asarray(R) * s; M[:3, 3] = p
    return Matrix(M.tolist())
def rz(a):
    return np.array(Matrix.Rotation(a, 3, 'Z'))
def rx(a):
    return np.array(Matrix.Rotation(a, 3, 'X'))
def ry(a):
    return np.array(Matrix.Rotation(a, 3, 'Y'))
def place(ob, p, R=np.eye(3), s=1.0):
    ob.matrix_world = mat_from(R, p, s)
def cyl(name, r, h, mat, verts=32, r2=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=h)
    bm.to_mesh(me); bm.free(); me.materials.append(mat)
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    return link(bpy.data.objects.new(name, me))
def flat_R(yaw):
    """sheet lying flat, art facing up, art-top pointing along +y rotated by yaw"""
    return frames_from(v3(0, 0, 1)[None], v3(-math.sin(yaw), math.cos(yaw), 0)[None])[0]
def hide_all(sh):
    sh.set(np.repeat(HIDE[None], sh.n, 0), np.repeat(np.eye(3)[None], sh.n, 0))

# ---------------------------------------------------------------- world: night blue, underwater volume
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
wn = world.node_tree
for n in list(wn.nodes):
    wn.nodes.remove(n)
wo = wn.nodes.new('ShaderNodeOutputWorld')
wbg = wn.nodes.new('ShaderNodeBackground'); wbg.inputs[0].default_value = (0.004, 0.010, 0.045, 1)
wbg.inputs[1].default_value = 1.0
wn.links.new(wbg.outputs[0], wo.inputs['Surface'])
wvol = wn.nodes.new('ShaderNodeVolumePrincipled')
wvol.inputs['Color'].default_value = (0.0, 0.10, 0.9, 1)
wvol.inputs['Absorption Color'].default_value = (0.12, 0.26, 0.9, 1)
wvol.inputs['Density'].default_value = 0.0
wvol.inputs['Anisotropy'].default_value = 0.35
wn.links.new(wvol.outputs[0], wo.inputs['Volume'])
W_COL = wbg.inputs[0]; W_STR = wbg.inputs[1]; W_DENS = wvol.inputs['Density']

# ---------------------------------------------------------------- the room (x -1.8..1.8, y -2.2..2.1, h 2.6)
RX0, RX1, RY0, RY1, RH = -1.8, 1.8, -2.2, 2.1, 2.6
DOOR_X, DOOR_W, DOOR_H = -0.25, 0.86, 2.05
WIN_Y0, WIN_Y1, WIN_Z0, WIN_Z1 = -1.05, 0.05, 1.0, 2.05
WT = 0.12
plaster = mat_color('plaster', (0.34, 0.37, 0.46), rough=0.9)
def wall(name, x0, x1, y0, y1, z0, z1, m=plaster):
    ob = make_box(name, (x1 - x0, y1 - y0, z1 - z0), {}, m)
    ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    return ob
# floor: walnut boards
fm, nt, out = new_mat('floor')
tc = nt.nodes.new('ShaderNodeTexCoord')
wvb = nt.nodes.new('ShaderNodeTexWave'); wvb.wave_type = 'BANDS'; wvb.bands_direction = 'X'
wvb.inputs['Scale'].default_value = 1.6; wvb.inputs['Distortion'].default_value = 0.0
nt.links.new(tc.outputs['Object'], wvb.inputs['Vector'])
seam = nt.nodes.new('ShaderNodeMapRange'); seam.inputs['From Min'].default_value = 0.0
seam.inputs['From Max'].default_value = 0.05
nt.links.new(wvb.outputs['Fac'], seam.inputs['Value'])
grain = nt.nodes.new('ShaderNodeTexNoise'); grain.inputs['Scale'].default_value = 3.0; grain.inputs['Detail'].default_value = 6
mpg = nt.nodes.new('ShaderNodeMapping'); mpg.inputs['Scale'].default_value = (14, 0.6, 1)
nt.links.new(tc.outputs['Object'], mpg.inputs[0]); nt.links.new(mpg.outputs[0], grain.inputs['Vector'])
cr = nt.nodes.new('ShaderNodeValToRGB')
cr.color_ramp.elements[0].color = (0.16, 0.09, 0.05, 1); cr.color_ramp.elements[1].color = (0.34, 0.20, 0.11, 1)
nt.links.new(grain.outputs['Fac'], cr.inputs[0])
mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
nt.links.new(seam.outputs[0], mx.inputs['Factor']); mx.inputs[6].default_value = (0.02, 0.01, 0.01, 1)
nt.links.new(cr.outputs[0], mx.inputs[7])
# seam=0 on the line -> dark; seam=1 elsewhere -> wood. Mix factor 1 = B (wood)
fb = nt.nodes.new('ShaderNodeBsdfPrincipled'); fb.inputs['Roughness'].default_value = 0.42
fb.inputs['Specular IOR Level'].default_value = 0.5
nt.links.new(mx.outputs[2], fb.inputs['Base Color']); nt.links.new(fb.outputs[0], out.inputs[0])
floor = wall('floor', RX0 - 0.2, RX1 + 0.2, RY0 - 0.2, RY1 + 1.2, -0.05, 0.0, fm)
wall('ceiling', RX0 - 0.2, RX1 + 0.2, RY0 - 0.2, RY1 + 0.2, RH, RH + 0.1)
wall('wall_front', RX0 - 0.2, RX1 + 0.2, RY0 - WT, RY0, 0, RH)
wall('wall_right', RX1, RX1 + WT, RY0, RY1, 0, RH)
# back wall with door hole
wall('back_l', RX0 - 0.2, DOOR_X - DOOR_W / 2, RY1, RY1 + WT, 0, RH)
wall('back_r', DOOR_X + DOOR_W / 2, RX1 + 0.2, RY1, RY1 + WT, 0, RH)
wall('back_top', DOOR_X - DOOR_W / 2, DOOR_X + DOOR_W / 2, RY1, RY1 + WT, DOOR_H, RH)
# left wall with window hole
wall('left_lo', RX0 - WT, RX0, RY0, RY1, 0, WIN_Z0)
wall('left_hi', RX0 - WT, RX0, RY0, RY1, WIN_Z1, RH)
wall('left_f', RX0 - WT, RX0, RY0, WIN_Y0, WIN_Z0, WIN_Z1)
wall('left_b', RX0 - WT, RX0, WIN_Y1, RY1, WIN_Z0, WIN_Z1)
# skirting boards
skirt = mat_color('skirt', (0.62, 0.61, 0.60), rough=0.6)
wall('sk_r', RX1 - 0.015, RX1, RY0, RY1, 0, 0.09, skirt)
wall('sk_bl', RX0, DOOR_X - DOOR_W / 2 - 0.05, RY1 - 0.015, RY1, 0, 0.09, skirt)
wall('sk_br', DOOR_X + DOOR_W / 2 + 0.05, RX1, RY1 - 0.015, RY1, 0, 0.09, skirt)
# window frame + sill + sky plane outside
frame_m = mat_color('frame', (0.75, 0.75, 0.74), rough=0.5)
wall('sill', RX0 - 0.02, RX0 + 0.14, WIN_Y0 - 0.06, WIN_Y1 + 0.06, WIN_Z0 - 0.035, WIN_Z0, frame_m)
wall('mull_v', RX0 - 0.07, RX0 - 0.04, (WIN_Y0 + WIN_Y1) / 2 - 0.02, (WIN_Y0 + WIN_Y1) / 2 + 0.02, WIN_Z0, WIN_Z1, frame_m)
wall('mull_h', RX0 - 0.07, RX0 - 0.04, WIN_Y0, WIN_Y1, 1.62, 1.66, frame_m)
sky_m, nt, out = new_mat('window_sky')
tcs = nt.nodes.new('ShaderNodeTexCoord'); sxz = nt.nodes.new('ShaderNodeSeparateXYZ')
nt.links.new(tcs.outputs['Generated'], sxz.inputs[0])
rs = nt.nodes.new('ShaderNodeValToRGB')
rs.color_ramp.elements[0].color = (0.0, 0.02, 0.10, 1); rs.color_ramp.elements[1].color = (0.0, 0.07, 0.42, 1)
rs.color_ramp.elements[1].position = 0.9
nt.links.new(sxz.outputs['Z'], rs.inputs[0])
rd = nt.nodes.new('ShaderNodeValToRGB')
rd.color_ramp.elements[0].color = (1.0, 0.62, 0.42, 1); rd.color_ramp.elements[1].color = (0.45, 0.62, 0.95, 1)
rd.color_ramp.elements[1].position = 0.75
nt.links.new(sxz.outputs['Z'], rd.inputs[0])
smx = nt.nodes.new('ShaderNodeMix'); smx.data_type = 'RGBA'
nt.links.new(rs.outputs[0], smx.inputs[6]); nt.links.new(rd.outputs[0], smx.inputs[7])
sem = nt.nodes.new('ShaderNodeEmission'); nt.links.new(smx.outputs[2], sem.inputs[0]); sem.inputs[1].default_value = 2.0
nt.links.new(sem.outputs[0], out.inputs[0])
SKY_DAWN = smx.inputs['Factor']; SKY_STR = sem.inputs[1]
sky = make_box('window_sky', (0.02, 5.0, 3.2), {}, sky_m)
sky.location = (RX0 - 1.2, (WIN_Y0 + WIN_Y1) / 2, 1.5); sky.visible_shadow = False
# stars: a few small emissive dots behind the window
star_m = mat_emit('star', (0.8, 0.85, 1.0), 6.0)
for i in range(9):
    s = make_box(f'star{i}', (0.01, 0.012, 0.012), {}, star_m)
    s.location = (RX0 - 1.18, rng.uniform(WIN_Y0 - 0.3, WIN_Y1 + 0.3), rng.uniform(1.5, 2.3)); s.visible_shadow = False
STARS = [o for o in bpy.data.objects if o.name.startswith('star')]

# door
door_m = mat_color('door', (0.62, 0.62, 0.60), rough=0.45)
door = make_box('door', (DOOR_W - 0.01, 0.04, DOOR_H - 0.025), {}, door_m, bevel=0.004)
door.location = (DOOR_X, RY1 + 0.03, 0.025 + (DOOR_H - 0.025) / 2)
knob = cyl('knob', 0.028, 0.06, mat_color('brass', (0.8, 0.6, 0.3), rough=0.25, metal=1.0))
knob.rotation_euler = (math.pi / 2, 0, 0); knob.location = (DOOR_X + DOOR_W / 2 - 0.09, RY1 - 0.01, 1.0)
wall('jamb_l', DOOR_X - DOOR_W / 2 - 0.05, DOOR_X - DOOR_W / 2, RY1 - 0.015, RY1 + WT, 0, DOOR_H + 0.05, frame_m)
wall('jamb_r', DOOR_X + DOOR_W / 2, DOOR_X + DOOR_W / 2 + 0.05, RY1 - 0.015, RY1 + WT, 0, DOOR_H + 0.05, frame_m)
wall('jamb_t', DOOR_X - DOOR_W / 2 - 0.05, DOOR_X + DOOR_W / 2 + 0.05, RY1 - 0.015, RY1 + WT, DOOR_H, DOOR_H + 0.05, frame_m)
# hallway light behind the door: glows only through the gap
hall_m = mat_emit('hall', (0.75, 0.85, 1.0), 6.0)
hall = make_box('hall_glow', (DOOR_W + 0.4, 0.8, 0.01), {}, hall_m)
hall.location = (DOOR_X, RY1 + 0.55, 0.002); hall.visible_shadow = False
hall_wall = make_box('hall_wall', (2.0, 0.02, 2.0), {}, mat_emit('hallw', (0.5, 0.6, 0.8), 1.2))
hall_wall.location = (DOOR_X, RY1 + 1.0, 1.0)
# light fan on the floor inside the gap (fake, cold)
fan_m, nt, out = new_mat('gap_fan')
tcf = nt.nodes.new('ShaderNodeTexCoord'); sfx = nt.nodes.new('ShaderNodeSeparateXYZ')
nt.links.new(tcf.outputs['Generated'], sfx.inputs[0])
gr = nt.nodes.new('ShaderNodeMath'); gr.operation = 'POWER'; gr.inputs[1].default_value = 3.0
nt.links.new(sfx.outputs['Y'], gr.inputs[0])
fe = nt.nodes.new('ShaderNodeEmission'); fe.inputs[0].default_value = (0.6, 0.75, 1.0, 1)
fmul = nt.nodes.new('ShaderNodeMath'); fmul.operation = 'MULTIPLY'; fmul.inputs[1].default_value = 0.7
nt.links.new(gr.outputs[0], fmul.inputs[0]); nt.links.new(fmul.outputs[0], fe.inputs[1])
ftr = nt.nodes.new('ShaderNodeBsdfTransparent')
fad = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(ftr.outputs[0], fad.inputs[0]); nt.links.new(fe.outputs[0], fad.inputs[1])
nt.links.new(fad.outputs[0], out.inputs[0])
fan_m.blend_method = 'BLEND'; fan_m.shadow_method = 'NONE'
FAN_STR = fmul.inputs[1]
fan = make_box('gap_fan', (DOOR_W + 0.3, 0.9, 0.001), {}, fan_m)
fan.location = (DOOR_X, RY1 - 0.45, 0.0015); fan.visible_shadow = False
gap_d = bpy.data.lights.new('gap', 'AREA'); gap_d.shape = 'RECTANGLE'; gap_d.size = DOOR_W; gap_d.size_y = 0.03
gap_d.color = (0.6, 0.75, 1.0); gap_d.energy = 6.0; gap_d.use_shadow = False
gap_l = link(bpy.data.objects.new('gap', gap_d)); gap_l.location = (DOOR_X, RY1 - 0.02, 0.03)
gap_l.rotation_euler = (math.radians(-80), 0, 0)   # points into the room, low

# bed (a group under one empty so it can float)
bed = empty('bed')
BED_C = v3(-1.32, -0.55, 0.0)
sheet_m = mat_color('bedsheet', (0.78, 0.78, 0.80), rough=0.8)
duvet_m = mat_color('duvet', (0.20, 0.26, 0.42), rough=0.85)
wood_m = mat_color('bedwood', (0.16, 0.09, 0.05), rough=0.5)
parent(make_box('bed_frame', (0.98, 2.04, 0.2), {}, wood_m, bevel=0.01), bed, (0, 0, 0.27))
for sx in (-1, 1):
    for sy in (-1, 1):
        parent(make_box(f'bed_leg{sx}{sy}', (0.06, 0.06, 0.2), {}, wood_m), bed, (sx * 0.44, sy * 0.97, 0.1))
parent(make_box('headboard', (0.98, 0.05, 0.75), {}, wood_m, bevel=0.01), bed, (0, 1.02, 0.55))
parent(make_box('mattress', (0.92, 1.98, 0.2), {}, sheet_m, bevel=0.04), bed, (0, 0, 0.47))
parent(make_box('duvet', (0.96, 1.3, 0.1), {}, duvet_m, bevel=0.045), bed, (0, -0.35, 0.6))
parent(make_box('pillow', (0.62, 0.36, 0.12), {}, sheet_m, bevel=0.05), bed, (0, 0.72, 0.62), (0.25, 0, 0))

# desk, lamp, clock
desk_m = mat_color('desk', (0.30, 0.18, 0.10), rough=0.45)
DESK = (0.45, 1.55, 1.52, 2.08)  # x0 x1 y0 y1
wall('desk_top', DESK[0], DESK[1], DESK[2], DESK[3], 0.72, 0.755, desk_m)
for x in (DESK[0] + 0.04, DESK[1] - 0.04):
    for y in (DESK[2] + 0.04, DESK[3] - 0.04):
        wall(f'desk_leg{x}{y}', x - 0.02, x + 0.02, y - 0.02, y + 0.02, 0, 0.72, desk_m)
LAMP = v3(1.40, 1.9, 0.755)
metal_m = mat_color('lampmetal', (0.05, 0.12, 0.08), rough=0.35, metal=0.6)
lb = cyl('lamp_base', 0.075, 0.025, metal_m); lb.location = LAMP + v3(0, 0, 0.0125)
la = cyl('lamp_arm', 0.009, 0.42, metal_m); la.location = LAMP + v3(-0.05, -0.02, 0.2); la.rotation_euler = (0.25, -0.22, 0)
shade_m, nt, out = new_mat('shade')
g = nt.nodes.new('ShaderNodeNewGeometry')
bo = nt.nodes.new('ShaderNodeBsdfPrincipled'); bo.inputs['Base Color'].default_value = (0.04, 0.12, 0.07, 1)
bo.inputs['Metallic'].default_value = 0.6; bo.inputs['Roughness'].default_value = 0.3
bi = nt.nodes.new('ShaderNodeEmission'); bi.inputs[0].default_value = (1.0, 0.72, 0.4, 1); bi.inputs[1].default_value = 8.0
SHADE_IN = bi.inputs[1]
ms = nt.nodes.new('ShaderNodeMixShader'); nt.links.new(g.outputs['Backfacing'], ms.inputs[0])
nt.links.new(bo.outputs[0], ms.inputs[2]); nt.links.new(bi.outputs[0], ms.inputs[1])   # cone normals face inward; nt.links.new(ms.outputs[0], out.inputs[0])
shade_m.use_backface_culling = False
me = bpy.data.meshes.new('shade'); bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=False, segments=40, radius1=0.12, radius2=0.04, depth=0.15)
bm.to_mesh(me); bm.free(); me.materials.append(shade_m)
me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
shade = link(bpy.data.objects.new('shade', me))
SHADE_P = LAMP + v3(-0.16, -0.12, 0.40)
shade.location = SHADE_P; shade.rotation_euler = (-0.35, 0.45, 0)
bulb = cyl('bulb', 0.03, 0.05, mat_emit('bulb', (1.0, 0.8, 0.55), 40.0)); bulb.location = SHADE_P + v3(0, 0, -0.03)
bulb.visible_shadow = False
lamp_d = bpy.data.lights.new('lamp', 'SPOT'); lamp_d.color = (1.0, 0.60, 0.28); lamp_d.energy = 60.0
lamp_d.shadow_soft_size = 0.04; lamp_d.spot_size = math.radians(120); lamp_d.spot_blend = 0.5
lamp_l = link(bpy.data.objects.new('lamp', lamp_d)); lamp_l.location = SHADE_P + v3(0, 0, -0.06)
lamp_l.rotation_euler = (0.35, -0.45, 0)
lamp_up_d = bpy.data.lights.new('lamp_up', 'POINT'); lamp_up_d.color = (1.0, 0.62, 0.30); lamp_up_d.energy = 10.0
lamp_up_d.use_shadow = False; lamp_up_d.shadow_soft_size = 0.1
lamp_up = link(bpy.data.objects.new('lamp_up', lamp_up_d)); lamp_up.location = SHADE_P + v3(0, 0, 0.05)
# a soft warm bounce so the room reads (no shadow)
bounce_d = bpy.data.lights.new('bounce', 'AREA'); bounce_d.size = 2.5; bounce_d.color = (1.0, 0.62, 0.36)
bounce_d.energy = 14.0; bounce_d.use_shadow = False
cool_d = bpy.data.lights.new('cool', 'AREA'); cool_d.size = 2.0; cool_d.color = (0.35, 0.5, 1.0)
cool_d.energy = 30.0; cool_d.use_shadow = False
cool = link(bpy.data.objects.new('cool', cool_d)); cool.location = (-0.6, -0.8, 2.4)
bounce = link(bpy.data.objects.new('bounce', bounce_d)); bounce.location = (0.4, 0.6, 2.5)
# moonlight through the window
moon_d = bpy.data.lights.new('moon', 'SUN'); moon_d.color = (0.40, 0.55, 1.0); moon_d.energy = 2.2; moon_d.angle = 0.02
moon_d.shadow_cascade_max_distance = 12.0; moon_d.shadow_cascade_count = 2
moon = link(bpy.data.objects.new('moon', moon_d))
moon.rotation_euler = Vector((1.0, -0.15, -0.75)).to_track_quat('-Z', 'Y').to_euler()   # light travels +x, down
# clock texture (a prop: amber digits) -> WORK
os.makedirs(WORK, exist_ok=True)
def clock_png(text, path):
    im = Image.new('RGB', (720, 300), (6, 5, 5)); d = ImageDraw.Draw(im)
    f = config.font('font_sans_bold', 210)
    tw = d.textlength(text, font=f)
    d.text(((720 - tw) / 2, 30), text, font=f, fill=(255, 150, 40))
    im.save(path)
    return path
clock_face, CLOCK_EMIT = mat_driven_image('clock_face', clock_png('3:14', os.path.join(WORK, 'clock_314.png')), rough=0.2, spec=0.6)
clock = make_box('clock', (0.2, 0.08, 0.09), {(0, -1, 0): clock_face}, mat_color('clockbody', (0.03, 0.03, 0.035), rough=0.4), bevel=0.006)
clock.location = (0.62, 1.93, 0.755 + 0.045); clock.rotation_euler = (0, 0, -0.25)
clock_glow = bpy.data.lights.new('clockglow', 'POINT'); clock_glow.color = (1.0, 0.5, 0.15); clock_glow.energy = 0.6
clock_glow.use_shadow = False; clock_glow.shadow_soft_size = 0.05
cgl = link(bpy.data.objects.new('clockglow', clock_glow)); cgl.location = (0.66, 1.82, 0.81)
mug = cyl('mug', 0.04, 0.095, mat_color('mug', (0.8, 0.78, 0.72), rough=0.3)); mug.location = (1.50, 1.64, 0.755 + 0.0475)

# ---------------------------------------------------------------- Goosnav Book 2 (generic) under one empty
BW, BH, BT, BOARD = 0.30, 0.225, 0.042, 0.004
book_blue = mat_color('book_blue', (0.0, 0.0331, 0.3515), rough=0.5)
cov_front, COV_EMIT = mat_driven_image('cover_front', TEX + '/gen_book_front.png', rough=0.5, spec=0.35, coat=0.12)
cov_back = mat_image('cover_back', TEX + '/gen_book_back.png', rough=0.5, spec=0.35, coat=0.12)
cov_spine = mat_image('cover_spine', TEX + '/gen_book_spine.png', rough=0.5, spec=0.35, coat=0.12)
pages_m = mat_color('bookpages', (0.92, 0.90, 0.84), rough=0.9)
book = empty('book')
parent(make_box('book_front', (BW, BOARD, BH), {(0, -1, 0): cov_front}, book_blue, bevel=0.001), book, (0, -(BT - BOARD) / 2, 0))
parent(make_box('book_back', (BW, BOARD, BH), {(0, 1, 0): cov_back}, book_blue, bevel=0.001), book, (0, (BT - BOARD) / 2, 0))
parent(make_box('book_spine', (BOARD, BT, BH), {(-1, 0, 0): cov_spine}, book_blue, bevel=0.001), book, (-(BW - BOARD) / 2, 0, 0))
parent(make_box('book_block', (BW - 0.008, BT - 2 * BOARD - 0.001, BH - 0.008), {}, pages_m), book, (0.002, 0, 0))
BOOK_DESK = (v3(0.98, 1.97, 0.755 + BH / 2), rz(0.05))

# Goosklerf pack + dice
pack_front_mat = mat_image('pack_front', TEX + '/gen_pack.png', rough=0.28, spec=0.7, coat=0.4)
pack = make_box('pack', (0.09, 0.006, 0.143), {(0, -1, 0): pack_front_mat}, mat_color('pack_silver', (0.78, 0.8, 0.84), rough=0.22, metal=1.0), bevel=0.001)
PIP_OF = {(0, 0, 1): 1, (0, 0, -1): 6, (1, 0, 0): 2, (-1, 0, 0): 5, (0, 1, 0): 3, (0, -1, 0): 4}
dice = []
for nm in ('teal', 'orange', 'purple'):
    fmats = {n: mat_image(f'die_{nm}_{p}', f'{TEX}/die_{nm}_{p}.png', rough=0.22, spec=0.6, coat=0.6) for n, p in PIP_OF.items()}
    dice.append(make_box(f'die_{nm}', (1.0, 1.0, 1.0), fmats, fmats[(0, 0, 1)], bevel=0.11))
DIE_S = 0.034
DICE_DESK = [(v3(0.86, 1.70, 0.755 + DIE_S / 2), rz(0.3)), (v3(0.95, 1.64, 0.755 + DIE_S / 2), rx(math.pi / 2) @ rz(0.1)),
             (v3(1.10, 1.68, 0.755 + DIE_S / 2), ry(-math.pi / 2) @ rz(-0.5))]
PACK_DESK = (v3(1.20, 1.93, 0.755 + 0.0715 + 0.003), rz(-0.3) @ rx(-0.16))

# ---------------------------------------------------------------- paper
CMW, CMH = 0.36, 0.278          # comic board sheet (scan aspect 1400:1080)
comic_mats = [mat_comic(f'comic{i}', f'{TEX}/comic_{i:02d}.png') for i in range(7)]
card_mat = mat_two_sided('card', TEX + '/gen_card.png', TEX + '/gen_card.png', rough=0.35, translucent=0.02, gloss=0.5, glow=0.1, alpha=True)
CARD_EM = card_mat.node_tree.nodes['Emission'].inputs[1]

# the comics that slide under the door
NSL = len(SLIDE_TIMES)
sl_ids = [1] + list(rng.integers(0, 7, NSL - 1))
slides = Sheets('slide', NSL, CMW, CMH, comic_mats, sl_ids, curl_ids=[1] * NSL)
SL_REST = [v3(DOOR_X + 0.02, 1.42, 0.0)]
SL_YAW = [0.06]
for i in range(1, NSL):
    SL_REST.append(v3(DOOR_X + rng.uniform(-0.75, 0.75), RY1 - rng.uniform(0.35, 1.5), 0))
    SL_YAW.append(rng.uniform(-0.9, 0.9))

# the flood: many comics come in, then ride the rising surface; reused as the underwater surface
NF = 300
fl_ids = rng.integers(0, 7, NF)
flood = Sheets('flood', NF, CMW, CMH, comic_mats, fl_ids)
def ok_xy(x, y):
    in_bed = (BED_C[0] - 0.55 < x < BED_C[0] + 0.55) and (BED_C[1] - 1.1 < y < BED_C[1] + 1.1)
    in_desk = DESK[0] - 0.1 < x < DESK[1] + 0.1 and y > DESK[2] - 0.1
    return not in_bed and not in_desk
FL_T = np.sort(T_S3 + 0.5 + 6.2 * rng.random(NF) ** 0.55)
FL_XY = []
while len(FL_XY) < NF:
    x, y = rng.uniform(RX0 + 0.15, RX1 - 0.15), rng.uniform(RY0 + 0.15, RY1 - 0.2)
    if ok_xy(x, y):
        FL_XY.append((x, y))
FL_XY = np.array(FL_XY)
FL_SX = DOOR_X + rng.uniform(-0.38, 0.38, NF)
FL_YAW = rng.uniform(-np.pi, np.pi, NF)
FL_DUR = rng.uniform(0.45, 0.9, NF)
FL_JZ = rng.uniform(0.0, 0.05, NF)
FL_PH = rng.uniform(0, 2 * np.pi, NF)
# underwater surface layout (local to a shot centre)
SU_XY = np.stack([rng.uniform(-9, 9, NF), rng.uniform(-6, 14, NF)], -1)

# drifting pages underwater
ND = 150
dr_ids = rng.integers(0, 7, ND)
drift = Sheets('drift', ND, CMW * 2.2, CMH * 2.2, comic_mats, dr_ids)
DR_P = np.stack([rng.uniform(-9, 9, ND), rng.uniform(-4, 34, ND), rng.uniform(-13, -0.6, ND)], -1)
DR_V = np.stack([rng.normal(0, 0.12, ND), rng.normal(0.05, 0.12, ND), rng.normal(0.0, 0.05, ND)], -1)
DR_AX = norm(rng.normal(size=(ND, 3))); DR_W = rng.uniform(0.08, 0.35, ND) * rng.choice([-1, 1], ND)
DR_PH = rng.uniform(0, 2 * np.pi, ND)
DR_R0 = euler_mats(rng.uniform(-np.pi, np.pi, (ND, 3)))

# Goosklerf cards: a school of fish
NC = 30
cards = Sheets('cards', NC, 0.063 * 5, 0.088 * 5, [card_mat], np.zeros(NC, int), nx=2, nz=2)
CA_OFF = np.stack([rng.normal(0, 1.1, NC), rng.normal(0, 0.8, NC), rng.normal(0, 0.6, NC)], -1)
CA_PH = rng.uniform(0, 2 * np.pi, NC); CA_SP = rng.uniform(0.9, 1.1, NC)
desk_card = Sheets('desk_card', 1, 0.063, 0.088, [card_mat], [0], nx=2, nz=2)

# hero comic by the door at dawn / lens covers
hero = Sheets('hero', 1, CMW, CMH, [comic_mats[3]], [0], curl_ids=[1])
lens_sheet = Sheets('lens_sheet', 1, CMW, CMH, [comic_mats[5]], [0])

# underwater: dark plane under the flood surface (room) / seabed (sea)
deep_m = mat_color('deep', (0.0, 0.015, 0.07), rough=0.25)
deep = make_box('deep', (RX1 - RX0 + 0.4, RY1 - RY0 + 0.4, 0.01), {}, deep_m)
seabed_m = mat_color('seabed', (0.05, 0.10, 0.22), rough=0.9)
seabed = make_box('seabed', (400, 400, 0.1), {}, seabed_m)
seabed.location = HIDE
surf_glow = make_box('surf_glow', (400, 400, 0.02), {}, mat_emit('surf_glow', (0.12, 0.30, 1.0), 0.12))
surf_glow.location = HIDE; surf_glow.visible_shadow = False

# paper tower (the lighthouse) and its lantern
TOWER_BASE = U + v3(0.0, 44.0, -16.0)
tower_blocks = []
blk_m, nt, out = new_mat('tower_paper')
tcb = nt.nodes.new('ShaderNodeTexCoord')
wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Z'; wv.inputs['Scale'].default_value = 30.0
wv.inputs['Distortion'].default_value = 2.0
nt.links.new(tcb.outputs['Object'], wv.inputs['Vector'])
rp = nt.nodes.new('ShaderNodeValToRGB')
rp.color_ramp.elements[0].color = (0.45, 0.46, 0.50, 1); rp.color_ramp.elements[1].color = (0.90, 0.89, 0.86, 1)
rp.color_ramp.elements[1].position = 0.3
nt.links.new(wv.outputs['Fac'], rp.inputs[0])
bb = nt.nodes.new('ShaderNodeBsdfPrincipled'); bb.inputs['Roughness'].default_value = 0.9
nt.links.new(rp.outputs[0], bb.inputs['Base Color'])
nt.links.new(rp.outputs[0], bb.inputs['Emission Color']); bb.inputs['Emission Strength'].default_value = 0.08
nt.links.new(bb.outputs[0], out.inputs[0])
z = 0.0
for k in range(11):
    w = lerp(3.6, 2.4, k / 10) + rng.uniform(-0.2, 0.2)
    hgt = rng.uniform(0.9, 1.3)
    ob = make_box(f'tower{k}', (w, w * 0.8, hgt), {}, blk_m)
    ob.location = TOWER_BASE + v3(rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.1), z + hgt / 2)
    ob.rotation_euler = (rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03), rng.uniform(-0.25, 0.25))
    tower_blocks.append(ob)
    z += hgt
TOWER_TOP = TOWER_BASE + v3(0, 0, z)
LH_SCALE = 12.0
LH_BOOK = TOWER_TOP + v3(0, 0, BH * LH_SCALE / 2)
LANTERN = LH_BOOK + v3(0, 0.0, BH * LH_SCALE / 2 + 0.35)
lantern = cyl('lantern', 0.28, 0.5, mat_emit('lantern', (1.0, 0.72, 0.40), 60.0))
lantern.location = LANTERN; lantern.visible_shadow = False
lant_d = bpy.data.lights.new('lant', 'POINT'); lant_d.color = (1.0, 0.65, 0.35); lant_d.energy = 0.0; lant_d.shadow_soft_size = 0.3
lant = link(bpy.data.objects.new('lant', lant_d)); lant.location = LANTERN
cov_d = bpy.data.lights.new('covlight', 'SPOT'); cov_d.color = (1.0, 0.85, 0.7); cov_d.energy = 0.0; cov_d.spot_size = 0.9
cov_d.use_shadow = False
cov_l = link(bpy.data.objects.new('covlight', cov_d))
cov_l.location = LH_BOOK + v3(0, -6.0, 3.0)
cov_l.rotation_euler = Vector(tuple(LH_BOOK - cov_l.location)).to_track_quat('-Z', 'Y').to_euler()
# two beams: spot light (volumetric) + a soft emissive cone
def beam_mesh():
    me = bpy.data.meshes.new('beam'); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.25, radius2=4.5, depth=40.0)
    for v in bm.verts:
        v.co.z += 20.0   # apex at origin, opens along +z
    uvl = bm.loops.layers.uv.new('UVMap')
    for f in bm.faces:
        for lp_ in f.loops:
            lp_[uvl].uv = (0.0, lp_.vert.co.z / 40.0)
    bm.to_mesh(me); bm.free()
    m, nt, out = new_mat('beam')
    uv = nt.nodes.new('ShaderNodeUVMap'); sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(uv.outputs[0], sep.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange'); fall.inputs['To Min'].default_value = 1.0; fall.inputs['To Max'].default_value = 0.0
    nt.links.new(sep.outputs['Y'], fall.inputs['Value'])
    pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.2
    nt.links.new(fall.outputs[0], pw.inputs[0])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.35
    fac = nt.nodes.new('ShaderNodeMath'); fac.operation = 'SUBTRACT'; fac.inputs[0].default_value = 1.0
    nt.links.new(lw.outputs['Facing'], fac.inputs[1])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    nt.links.new(pw.outputs[0], m1.inputs[0]); nt.links.new(fac.outputs[0], m1.inputs[1])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; m2.inputs[1].default_value = 1.2
    nt.links.new(m1.outputs[0], m2.inputs[0])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (1.0, 0.70, 0.38, 1)
    nt.links.new(m2.outputs[0], em.inputs[1])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    ad = nt.nodes.new('ShaderNodeAddShader'); nt.links.new(tr.outputs[0], ad.inputs[0]); nt.links.new(em.outputs[0], ad.inputs[1])
    nt.links.new(ad.outputs[0], out.inputs[0])
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; m.use_backface_culling = False
    m.show_transparent_back = True
    me.materials.append(m)
    return me, m2.inputs[1]
beam_me, BEAM_STR = beam_mesh()
beams, beam_spots = [], []
for i in range(2):
    ob = link(bpy.data.objects.new(f'beam{i}', beam_me)); ob.visible_shadow = False; beams.append(ob)
    sd = bpy.data.lights.new(f'beamspot{i}', 'SPOT'); sd.color = (1.0, 0.7, 0.4); sd.energy = 0.0
    sd.spot_size = math.radians(14); sd.spot_blend = 0.6; sd.use_shadow = False; sd.shadow_soft_size = 0.2
    beam_spots.append(link(bpy.data.objects.new(f'beamspot{i}', sd)))
BEAM_PERIOD = 9.0
BEAM_TILT = math.radians(-9)
BEAM_FACE_T = 31.4                                    # a beam sweeps across the lens here

# sea light: amber from above (the lamp is up there somewhere), blue from everywhere
sea_d = bpy.data.lights.new('seasun', 'SUN'); sea_d.color = (1.0, 0.68, 0.40); sea_d.energy = 0.0; sea_d.use_shadow = False
sea_sun = link(bpy.data.objects.new('seasun', sea_d)); sea_sun.rotation_euler = (0.12, 0.08, 0)
sea_d.volume_factor = 0.05
fill_d = bpy.data.lights.new('seafill', 'SUN'); fill_d.color = (0.3, 0.5, 1.0); fill_d.energy = 0.0; fill_d.use_shadow = False
sea_fill = link(bpy.data.objects.new('seafill', fill_d)); sea_fill.rotation_euler = (math.radians(150), 0, 0.5)
fill_d.volume_factor = 0.0

# ---------------------------------------------------------------- camera
cam, cam_d = make_camera(clip_end=400)
cam_d.clip_start = 0.02
def P(lens):   # lenses below are authored as portrait lenses; aim_camera multiplies by LENS_SCALE
    return lens / LENS_SCALE if PORTRAIT else lens

def level(t):
    """height of the paper sea in the room"""
    if t < T_FLOOD or t >= T_DAWN:
        return 0.0
    return 0.97 * float(ss(T_FLOOD, T_UNDER, t)) ** 1.25

def camera_at(t):
    if t < T_S2:     # floor by the door; the first comic comes to the lens
        u = float(sm(0.0, T_S2, t))
        eye = lerp(v3(DOOR_X + 0.05, 0.62, 0.82), v3(DOOR_X + 0.02, 0.86, 0.66), u) + sway(t, 0.008)
        tgt = lerp(v3(DOOR_X, 1.75, 0.22), v3(DOOR_X + 0.01, 1.62, 0.12), u)
        return eye, tgt, P(27.0), 0.0
    if t < T_S3:     # the room, high corner
        u = float(sm(T_S2, T_S3 + 1.0, t))
        eye = lerp(v3(1.52, -2.05, 2.25), v3(1.22, -1.55, 2.05), u) + sway(t, 0.01)
        tgt = lerp(v3(-0.55, 0.95, 0.55), v3(-0.45, 1.1, 0.5), u)
        return eye, tgt, P(15.5), 0.0
    if t < T_UNDER:  # the tide; camera sinks toward the surface
        u = float(sm(T_S3, T_UNDER, t))
        eye = lerp(v3(1.25, -1.72, 1.15), v3(1.05, -1.45, 0.98), u) + sway(t, 0.012)
        tgt = lerp(v3(-0.55, 1.2, 0.45), v3(-0.6, 1.0, 0.75), u)
        return eye, tgt, P(19.0), lerp(0.0, -0.05, u)
    if t < T_S5:     # under: look up at the paper ceiling, then down and forward while sinking
        u = float(sm(T_UNDER, T_S5 + 0.5, t))
        eye = U + v3(0, lerp(0.0, 3.0, u), lerp(-1.2, -5.5, u)) + sway(t, 0.05)
        pitch = lerp(1.05, -0.25, float(sm(T_UNDER + 0.5, T_S5, t)))
        look = v3(0.18 * math.sin(t * 0.3), math.cos(pitch), math.sin(pitch))
        return eye, eye + look * 5, P(17.0), 0.06 * math.sin(t * 0.4)
    if t < T_S6:     # the lighthouse: glide toward it
        u = float(sm(T_S5, T_S6 + 1.0, t))
        eye = U + v3(lerp(-3.0, 1.0, u), lerp(20.0, 30.0, u), lerp(-8.5, -6.5, u)) + sway(t, 0.06)
        tgt = LH_BOOK + v3(0, 0, lerp(-3.0, -1.8, u))
        return eye, tgt, P(lerp(26.0, 33.0, u)), 0.03 * math.sin(t * 0.35)
    if t < T_DAWN:   # looking up at the bed, rising
        u = float(sm(T_S6, T_DAWN, t))
        c = U + v3(30.0, 0.0, 0.0)
        eye = c + v3(lerp(1.6, 0.9, u), lerp(-4.2, -2.4, u), lerp(-6.0, -1.1, u ** 1.3)) + sway(t, 0.05)
        tgt = c + v3(0, lerp(0.2, 0.6, u), 0.2)
        return eye, tgt, P(lerp(16.0, 15.0, u)), 0.0
    if t < T_S8:     # dawn: push to the comic left by the door
        u = float(sm(T_DAWN, T_S8 + 0.5, t))
        eye = lerp(v3(0.30, -0.25, 1.30), v3(-0.18, 0.98, 0.72), u) + sway(t, 0.006)
        tgt = lerp(v3(-0.30, 1.55, 0.25), v3(-0.23, 1.52, 0.0), u)
        return eye, tgt, P(24.0), 0.0
    u = float(sm(T_S8, T_END, t))   # the desk at dawn
    eye = lerp(v3(0.90, 0.80, 1.10), v3(0.96, 1.02, 1.03), u) + sway(t, 0.004)
    tgt = lerp(v3(0.98, 1.9, 0.86), v3(0.98, 1.9, 0.86), u)
    return eye, tgt, P(30.0), 0.0

# ---------------------------------------------------------------- per-object update
def underwater(t):
    return T_UNDER <= t < T_DAWN

def set_lights(t):
    uw = underwater(t)
    dawn = t >= T_DAWN
    room_on = 0.0 if uw else 1.0
    lamp_k = 1.0 if not dawn else 0.75
    lamp_d.energy = 60.0 * room_on * lamp_k
    lamp_up_d.energy = 2.5 * room_on * lamp_k
    cool_d.energy = (55.0 if not dawn else 60.0) * room_on
    cool_d.color = (0.35, 0.5, 1.0) if not dawn else (0.75, 0.82, 1.0)
    bounce_d.color = (1.0, 0.62, 0.36) if not dawn else (1.0, 0.85, 0.72)
    surf_glow.location = (U + v3(0, 0, 0.12)) if uw else HIDE
    SHADE_IN.default_value = 8.0 * room_on * lamp_k
    bounce_d.energy = (14.0 if not dawn else 40.0) * room_on
    moon_d.energy = (2.4 if not dawn else 3.6) * room_on
    moon_d.color = (0.40, 0.55, 1.0) if not dawn else (1.0, 0.80, 0.66)
    SKY_DAWN.default_value = 1.0 if dawn else 0.0
    SKY_STR.default_value = 2.0 if not dawn else 3.0
    for s in STARS:
        s.hide_render = dawn
    gap_on = 0.0 if (uw or dawn) else 1.0
    gap_d.energy = 6.0 * gap_on
    FAN_STR.default_value = 0.7 * gap_on
    hall.hide_render = dawn
    CLOCK_EMIT.default_value = 3.0
    clock_glow.energy = 0.6 * room_on
    # the room's world
    if uw:
        W_COL.default_value = (0.0, 0.02, 0.2, 1)
        W_STR.default_value = 1.0
        W_DENS.default_value = 0.045
        sea_d.energy = 1.4
        fill_d.energy = 0.6
        for s in INK_SOCKETS:
            s.default_value = 1.6
        for s in PAPER_GLOW:
            s.default_value = 0.05
        CARD_EM.default_value = 0.25
        COV_EMIT.default_value = 0.9
    else:
        W_COL.default_value = (0.004, 0.010, 0.045, 1) if not dawn else (0.05, 0.06, 0.09, 1)
        W_STR.default_value = 1.0
        W_DENS.default_value = 0.0
        sea_d.energy = 0.0
        fill_d.energy = 0.0
        for s in INK_SOCKETS:
            s.default_value = 0.0
        for s in PAPER_GLOW:
            s.default_value = 0.12
        CARD_EM.default_value = 0.1
        COV_EMIT.default_value = 0.0
    # the lighthouse
    lh = uw
    lant_d.energy = 2500.0 if lh else 0.0
    cov_d.energy = 1800.0 if lh else 0.0
    lantern.location = LANTERN if lh else HIDE
    for i, (b, s) in enumerate(zip(beams, beam_spots)):
        if not lh:
            b.location = HIDE; s.data.energy = 0.0; continue
        # beam i points at the camera path when (t - BEAM_FACE_T) is a multiple of the half period
        a = 2 * math.pi * (t - BEAM_FACE_T) / BEAM_PERIOD + math.pi * i
        toward = norm(v3(-1.0, -26.0, 0.0))            # roughly from the tower back toward the glide
        base_yaw = math.atan2(toward[1], toward[0])
        yaw = base_yaw + a
        d = v3(math.cos(yaw) * math.cos(BEAM_TILT), math.sin(yaw) * math.cos(BEAM_TILT), math.sin(BEAM_TILT))
        R = np.array(Vector(tuple(d)).to_track_quat('Z', 'Y').to_matrix())   # cone axis (+Z) along d
        place(b, LANTERN, R)
        s.location = LANTERN
        s.rotation_euler = Vector(tuple(d)).to_track_quat('-Z', 'Y').to_euler()
        s.data.energy = 5.0e4
    BEAM_STR.default_value = 0.8

def set_book(t):
    if underwater(t):
        p, R, s = LH_BOOK, rz(0.0), LH_SCALE
        if t < T_S5 or t >= T_S6:
            p = HIDE
    else:
        p, R = BOOK_DESK; s = 1.0
    place(book, p, R, s)

def set_products(t):
    uw = underwater(t)
    if uw and T_S6 <= t:    # dice as buoys around the floating bed
        c = U + v3(30.0, 0.0, 0.0)
        spots = [v3(-1.7, 0.9, 0), v3(1.5, -0.5, 0), v3(0.4, 2.6, 0)]
        for i, ob in enumerate(dice):
            bob = 0.08 * math.sin(t * 1.3 + i * 2.0)
            R = euler_mats(v3(0.25 * math.sin(t * 0.9 + i), 0.2 * math.sin(t * 0.7 + 2 * i), 0.4 * i + 0.1 * t)[None])[0]
            place(ob, c + spots[i] + v3(0, 0, bob + 0.05), R, 0.55)
    elif uw:
        for ob in dice:
            ob.location = HIDE
    else:
        for ob, (p, R) in zip(dice, DICE_DESK):
            place(ob, p, R, DIE_S)
    if uw:
        pack.location = HIDE
        desk_card.set(HIDE[None], np.eye(3)[None])
    else:
        place(pack, *PACK_DESK)
        R = frames_from(v3(0.12, -1.0, 0.25)[None], v3(0, 0.25, 1)[None])[0]
        desk_card.set((v3(0.74, 1.76, 0.755 + 0.044))[None], R[None])

def set_bed(t):
    if underwater(t):
        if t >= T_S6:
            c = U + v3(30.0, 0.0, 0.0)
            R = euler_mats(v3(0.04 * math.sin(t * 0.8), 0.05 * math.sin(t * 0.6 + 1), 0.3 + 0.03 * t)[None])[0]
            place(bed, c + v3(0, 0, -0.42 + 0.05 * math.sin(t * 1.1)), R)
        else:
            bed.location = HIDE
        return
    h = level(t)
    lift = max(0.0, h - 0.28)
    k = float(ss(0.28, 0.6, h))
    R = euler_mats(v3(0.05 * k * math.sin(t * 1.5), 0.07 * k * math.sin(t * 1.1 + 1), 0.25 * k * float(ss(T_FLOOD + 2, T_UNDER, t)))[None])[0]
    place(bed, BED_C + v3(0.15 * k, 0.1 * k, lift + 0.03 * k * math.sin(t * 2.0)), R)

def set_slides(t):
    pos = np.repeat(HIDE[None], NSL, 0); Rs = np.repeat(np.eye(3)[None], NSL, 0)
    dawn = t >= T_DAWN
    uw = underwater(t)
    for i, ts in enumerate(SLIDE_TIMES):
        if uw or dawn or t < ts:
            continue
        u = min(1.0, (t - ts) / (0.95 if i == 0 else 0.8))
        s = 1 - (1 - u) ** 3
        start = v3(DOOR_X + (SL_REST[i][0] - DOOR_X) * 0.2, RY1 + 0.35, 0)
        p = lerp(start, SL_REST[i], s)
        p[2] = 0.0025 + 0.0012 * i + level(t)
        yaw = SL_YAW[i] * s
        if level(t) > 0.01:
            p[2] += 0.02 * math.sin(t * 2.1 + i) + 0.03
        pos[i] = p; Rs[i] = flat_R(yaw)
    slides.set(pos, Rs)

def set_flood(t):
    if t < T_S3:
        hide_all(flood); return
    if t < T_UNDER:    # the room fills
        h = level(t)
        tau = t - FL_T
        u = np.clip(tau / FL_DUR, 0, 1)
        s = 1 - (1 - u) ** 3
        sx = np.stack([FL_SX, np.full(NF, RY1 + 0.3)], -1)
        xy = sx + (FL_XY - sx) * s[:, None]
        wave = 0.03 * np.sin(2.3 * xy[:, 0] + 1.7 * xy[:, 1] - 2.2 * t + FL_PH) * float(ss(0.02, 0.2, h))
        z = 0.004 + h + FL_JZ * float(ss(0.0, 0.1, h)) + wave + 0.0006 * np.arange(NF)
        pos = np.stack([xy[:, 0], xy[:, 1], z], -1)
        pos[tau < 0] = HIDE
        tilt_ax = np.stack([np.cos(FL_PH), np.sin(FL_PH), np.zeros(NF)], -1)
        tilt = 0.18 * np.sin(1.3 * t + FL_PH) * float(ss(0.05, 0.3, h))
        R = np.einsum('nij,njk->nik', rot_axis(tilt_ax, tilt), np.stack([flat_R(y) for y in FL_YAW * s + 0.2]))
        flood.set(pos, R, )
        return
    if t < T_DAWN:     # underwater: the same sheets are the surface overhead
        c = U + v3(30.0, 0.0, 0.0) if t >= T_S6 else U
        if T_S5 <= t < T_S6:
            c = U + v3(0, 20, 0)
        xy = SU_XY * (1.8 if T_S5 <= t < T_S6 else 0.55)
        wave = 0.08 * np.sin(0.9 * xy[:, 0] + 0.6 * xy[:, 1] - 0.8 * t + FL_PH)
        pos = np.stack([c[0] + xy[:, 0], c[1] + xy[:, 1], wave - 0.03 * (np.arange(NF) % 5)], -1)
        if t >= T_S6:   # leave room for the bed and the dice
            d = np.hypot(xy[:, 0] - 0.0, xy[:, 1] - 0.0)
            pos[d < 1.4] = HIDE
        tilt_ax = np.stack([np.cos(FL_PH), np.sin(FL_PH), np.zeros(NF)], -1)
        R = np.einsum('nij,njk->nik', rot_axis(tilt_ax, 0.15 * np.sin(0.7 * t + FL_PH)), np.stack([flat_R(y) for y in FL_YAW]))
        flood.set(pos, R)
        return
    hide_all(flood)

def set_deep(t, eye):
    h = level(t)
    if not underwater(t) and h > 0.012:
        deep.location = (0, 0, h - 0.035)
    else:
        deep.location = HIDE
    seabed.location = (U + v3(0, 0, -16.05)) if underwater(t) else HIDE

def set_drift(t, eye):
    if not (T_UNDER <= t < T_DAWN):
        hide_all(drift); return
    tt_ = t - T_UNDER
    p = DR_P + DR_V * tt_ + np.stack([0.3 * np.sin(0.4 * t + DR_PH), 0.2 * np.sin(0.33 * t + DR_PH * 1.3), 0.25 * np.sin(0.5 * t + DR_PH)], -1)
    if T_S6 <= t:
        p = p + v3(30.0, -18.0, 0.0)
    pos = U + p
    # keep a little clear space around the lens
    off = pos - eye
    d = np.linalg.norm(off, axis=1)
    near = d < 1.0
    pos[near] = eye + off[near] / np.maximum(d[near], 1e-3)[:, None] * 1.0
    R = np.einsum('nij,njk->nik', rot_axis(DR_AX, DR_W * t + DR_PH), DR_R0)
    drift.set(pos, R)

def set_cards(t):
    # a school crosses in the lighthouse shot and again under the bed
    if T_S5 <= t < T_S6:
        u = (t - 30.8) / 5.5
        c = U + v3(lerp(-9.0, 7.0, u), 22.0, -6.2 + 0.6 * math.sin(u * 3))
        vel = v3(1.0, 0.15, 0.1 * math.cos(u * 3))
    elif T_S6 <= t < T_DAWN:
        u = (t - 37.2) / 5.0
        c = U + v3(30.0, 0.0, 0.0) + v3(lerp(-6.5, 5.5, u), lerp(-0.5, 0.8, u), -2.2 - 0.3 * math.sin(u * 3))
        vel = v3(1.0, 0.1, 0.0)
    else:
        hide_all(cards); return
    lag = CA_OFF[:, 0] * 0.35
    pos = c + CA_OFF * np.array([1.0, 1.0, 1.0]) + np.stack([np.zeros(NC), 0.25 * np.sin(2.5 * t + CA_PH), 0.15 * np.sin(1.7 * t + CA_PH)], -1)
    pos[:, 0] += 0.4 * np.sin(1.1 * t * CA_SP + CA_PH) - lag
    fwd = norm(vel)
    wig = 0.35 * np.sin(4.0 * t * CA_SP + CA_PH)
    side = norm(np.cross(v3(0, 0, 1), fwd))
    normals = norm(side[None] * np.cos(wig)[:, None] + fwd[None] * np.sin(wig)[:, None])
    ups = np.repeat(v3(0, 0, 1)[None], NC, 0) + fwd[None] * 0.5   # long axis leans into the swim
    cards.set(pos, frames_from(normals, ups))

def set_hero(t):
    if t >= T_DAWN:
        hero.set(v3(DOOR_X + 0.02, 1.5, 0.003)[None], flat_R(0.1)[None])
    else:
        hero.set(HIDE[None], np.eye(3)[None])

def set_lens_sheet(t, eye, tgt):
    # a page floats up over the lens at the end of the tide; another at the surfacing
    for t0, t1 in ((T_UNDER - 0.55, T_UNDER), (T_DAWN - 0.5, T_DAWN)):
        if t0 <= t < t1:
            u = float(sm(t0, t1, t))
            fwd = norm(tgt - eye); right = norm(np.cross(fwd, v3(0, 0, 1))); upv = np.cross(right, fwd)
            d = lerp(1.2, 0.035, u)
            p = eye + fwd * d - upv * lerp(0.9, 0.0, u) + right * lerp(0.3, 0.0, u)
            R = frames_from((-fwd)[None], (upv + right * 0.3 * (1 - u))[None])[0]
            lens_sheet.set(p[None], R[None])
            return
    lens_sheet.set(HIDE[None], np.eye(3)[None])

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_lights(t); set_book(t); set_products(t); set_bed(t)
    set_slides(t); set_flood(t); set_deep(t, eye); set_drift(t, eye); set_cards(t)
    set_hero(t); set_lens_sheet(t, eye, tgt)
    return t >= T_END + 0.3

def events():
    ev = {'slides': SLIDE_TIMES, 'flood_in': [float(x) for x in FL_T[::6]],
          'beam_pass': [BEAM_FACE_T + k * BEAM_PERIOD / 2 for k in range(-2, 3)],
          'T': {k: v for k, v in globals().items() if k.startswith('T_') and isinstance(v, float)}}
    os.makedirs(WORK, exist_ok=True)
    json.dump(ev, open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
