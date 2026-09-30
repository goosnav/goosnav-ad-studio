"""GNV-LPV-PAT-001 CONTINUATION DEPARTMENT -- the Goosnav Patreon. Monumental low-poly vignette, 9:16.

One small service window at the foot of a colossal concrete building. "Name?" "Sam." "Purpose?"
"I like Goosnav." A form: WOULD YOU LIKE GOOSNAV TO CONTINUE? [x] YES, $3 A MONTH. Stamp. "Very good."
The whole building lights up, floor by floor, and one real comic page drifts down to him.
Adapted from AD 33 "CONTINUATION DEPARTMENT" + the bible's SUPPORT INPUT skeleton (§37.11, §38F).
"""
import sys, os, json, math
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *   # noqa
from lowpoly import *   # noqa
from studio import config

FILM = 'continuation_department'
FPS = 24
DUR = 22.0
WORK = str(config.path('work', FILM, FORMAT))
VO = str(config.path('work', FILM, 'vo'))
TEX = str(config.textures())
rng = np.random.default_rng(5); set_rng(rng)

T2, T3, T4, T5, T_END = 5.0, 9.2, 12.6, 14.6, 20.0
VO_AT = {'01': 5.5, '02': 6.25, '03': 6.95, '04': 7.75, '05': 13.75}
SPEAKER = {'01': 'CLERK', '02': 'VISITOR', '03': 'CLERK', '04': 'VISITOR', '05': 'CLERK'}
FORM_T = (9.35, 10.3)       # form slides out under the glass
CHECK_T = 11.35             # he ticks YES
STAMP_T = 13.1              # stamp lands
LIGHTS_T = (14.9, 18.8)     # floors light up bottom to top
PAGE_T = (15.2, 19.8)       # a page drifts down to him
CUT_FRAMES = [round(x * FPS) for x in (T2, T3, T4, T5)]

scene = setup_scene(fps=FPS, samples=16, bloom=(0.9, 0.05, 6.0), look='AgX - Base Contrast')
fog_world(sky_top='#8C9AA6', sky_horizon='#C4CBCC', strength=1.1, density=0.0035, anisotropy=0.2)
scene.view_settings.exposure = 0.3
sun(2.2, '#F2EEE6', elev=38, azim=-150, angle=6)

# ---------------------------------------------------------------- plaza and the building
def slab_mat(name, color, joint=6.0):
    m, nt, out = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord'); br = nt.nodes.new('ShaderNodeTexBrick')
    br.offset = 0.0; br.squash = 1.0
    br.inputs['Scale'].default_value = 1.0 / joint
    br.inputs['Color1'].default_value = (*hexrgb(color), 1); br.inputs['Color2'].default_value = (*[c * 0.93 for c in hexrgb(color)], 1)
    br.inputs['Mortar'].default_value = (*[c * 0.7 for c in hexrgb(color)], 1); br.inputs['Mortar Size'].default_value = 0.01
    br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    nt.links.new(tc.outputs['Object'], br.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.inputs['Roughness'].default_value = 0.85
    nt.links.new(br.outputs['Color'], b.inputs['Base Color']); nt.links.new(b.outputs[0], out.inputs[0])
    return m
box('plaza', (500, 500, 0.2), slab_mat('plaza', PAL['concrete_pale'], 6.0), (0, -150, -0.1))

def facade_mat():
    """concrete with a grid of dark windows; windows below LIGHT_Z glow warm"""
    m, nt, out = new_mat('facade')
    geo = nt.nodes.new('ShaderNodeNewGeometry')          # world position: one grid across all wall pieces
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(geo.outputs['Position'], sep.inputs[0])
    br = nt.nodes.new('ShaderNodeTexBrick'); br.offset = 0.0; br.squash = 1.0
    br.inputs['Scale'].default_value = 1.0 / 3.2
    br.inputs['Color1'].default_value = (0.05, 0.06, 0.07, 1); br.inputs['Color2'].default_value = (0.06, 0.065, 0.075, 1)
    br.inputs['Mortar'].default_value = (*hexrgb(PAL['concrete']), 1); br.inputs['Mortar Size'].default_value = 0.3
    br.inputs['Brick Width'].default_value = 1.0; br.inputs['Row Height'].default_value = 1.0
    cm = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(sep.outputs['X'], cm.inputs['X']); nt.links.new(sep.outputs['Z'], cm.inputs['Y'])
    nt.links.new(cm.outputs[0], br.inputs['Vector'])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.inputs['Roughness'].default_value = 0.8
    nt.links.new(br.outputs['Color'], b.inputs['Base Color'])
    # glow mask: window (mortar fac == 0) AND z < LIGHT_Z
    lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'
    nt.links.new(sep.outputs['Z'], lt.inputs[0]); lt.inputs[1].default_value = -10.0
    win = nt.nodes.new('ShaderNodeMath'); win.operation = 'LESS_THAN'
    nt.links.new(br.outputs['Fac'], win.inputs[0]); win.inputs[1].default_value = 0.5
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(lt.outputs[0], mul.inputs[0]); nt.links.new(win.outputs[0], mul.inputs[1])
    em = nt.nodes.new('ShaderNodeMath'); em.operation = 'MULTIPLY'; em.inputs[1].default_value = 5.0
    nt.links.new(mul.outputs[0], em.inputs[0])
    b.inputs['Emission Color'].default_value = (1.0, 0.78, 0.45, 1)
    nt.links.new(em.outputs[0], b.inputs['Emission Strength'])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m, lt.inputs[1]
FACADE, LIGHT_Z = facade_mat()
plain = mat('wallplain', PAL['concrete'], 0.85, noise=0.15, noise_scale=0.05)
# the facade (y = 0 plane, facing -Y) with a service opening 1.3 x 1.0 at counter height
BW, BH, WALL = 180.0, 120.0, 0.6
OPEN_W, OPEN_B, OPEN_T_ = 1.3, 1.05, 2.05
def wall_part(name, x0, x1, z0, z1, m):
    ob = box(name, (x1 - x0, WALL, z1 - z0), m, ((x0 + x1) / 2, WALL / 2, (z0 + z1) / 2))
    return ob
for nm, x0, x1, z0, z1 in (('wl', -BW / 2, -OPEN_W / 2, 0, BH), ('wr', OPEN_W / 2, BW / 2, 0, BH),
                           ('wt', -OPEN_W / 2, OPEN_W / 2, OPEN_T_, BH), ('wb', -OPEN_W / 2, OPEN_W / 2, 0, OPEN_B)):
    wall_part(nm, x0, x1, z0, z1, FACADE)
box('building_body', (BW, 70, BH), plain, (0, WALL + 35, BH / 2))
for x, h in ((-70, 18), (-40, 24), (30, 20), (62, 16)):   # rooftop stacks
    cyl(f'stack{x}', 3.0, h, plain, 10, (x, 30, BH + h / 2))
# distant blocks in the fog
for i, (x, y, w, h) in enumerate(((-260, 140, 90, 70), (240, 180, 120, 95), (-120, 320, 160, 110), (150, 380, 100, 60))):
    box(f'far{i}', (w, 40, h), plain, (x, y, h / 2))
# counter, glass, sign
box('counter', (1.5, 0.45, 0.06), mat('counter', PAL['concrete_dark'], 0.5), (0, -0.2, OPEN_B + 0.03))
glass_m, nt, out = new_mat('glass')
gb = nt.nodes.new('ShaderNodeBsdfPrincipled'); gb.inputs['Roughness'].default_value = 0.05
gb.inputs['Alpha'].default_value = 0.12; gb.inputs['Base Color'].default_value = (0.8, 0.88, 0.9, 1)
nt.links.new(gb.outputs[0], out.inputs[0]); glass_m.blend_method = 'BLEND'; glass_m.shadow_method = 'NONE'
box('glass', (OPEN_W, 0.01, OPEN_T_ - OPEN_B - 0.12), glass_m, (0, 0.12, (OPEN_B + OPEN_T_) / 2 + 0.06))
sign_png = paper_sign('cd_sign', ['*CONTINUATION DEPARTMENT'], (1024, 128), '#1D211F', '#D5D2C8', WORK, 70, 'center')
sign = make_box('sign', (1.8, 0.04, 0.225), {(0, -1, 0): tex_mat('sign', sign_png, 0.6, 1024)}, mat('signbody', '#1D211F', 0.6))
sign.location = (0, -0.03, OPEN_T_ + 0.35)
# booth interior behind the window
box('booth_floor', (2.4, 2.4, 0.05), mat('boothfloor', '#6F6A5E', 0.8), (0, WALL + 1.2, 0.0))
box('booth_back', (2.4, 0.1, 2.6), mat('boothwall', '#A8A48F', 0.9), (0, WALL + 2.4, 1.3))
box('booth_desk', (1.3, 0.6, 0.05), mat('bdesk', '#6B5A48', 0.55), (0, WALL + 0.45, 1.0))
point('booth_lamp', (0.4, WALL + 0.8, 1.9), 60, '#FFE0B0', 0.2)

# ---------------------------------------------------------------- people
clerk = Human('clerk', skin=SKIN[0], top='#8C8775', legs='#4A4A44', hair='#6D6A66', glasses=True,
              jacket='#7B6F5A', hair_style='long', height=1.66)
clerk.place((0, WALL + 0.95, 0), yaw=0.0)
visitor = Human('visitor', skin=SKIN[2], top='#3F5964', legs='#2E3338', hair='#1D1A18', jacket='#586044')

# ---------------------------------------------------------------- the form, the tick, the stamp, the page
form_png = paper_sign('cd_form', ['*WOULD YOU LIKE', '*GOOSNAV TO CONTINUE?', '', '[   ]  YES  -  $3 A MONTH', '', '[   ]  NO'],
                      (512, 640), '#EFEBE0', '#1D211F', WORK, 34)
form = make_box('form', (0.21, 0.26, 0.002), {(0, 0, 1): tex_mat('form', form_png, 0.9, 512)}, mat('formpaper', '#EFEBE0', 0.9))
tick = box('tick', (0.03, 0.006, 0.001), mat('ink2', '#10131A', 0.5))
tick2 = box('tick2', (0.05, 0.006, 0.001), mat('ink2', '#10131A', 0.5))
stamp_png = paper_sign('cd_stamp', ['*APPROVED'], (256, 96), '#EFEBE0', '#A1231B', WORK, 44, 'center')
stamp_mark = make_box('stamp_mark', (0.12, 0.045, 0.001), {(0, 0, 1): tex_mat('stampmark', stamp_png, 0.9, 256)}, mat('sm', '#EFEBE0', 0.9))
stamp = empty('stamp')
cyl('stamp_handle', 0.018, 0.08, mat('stamph', '#3A2A20', 0.5), 8, (0, 0, 0.07), stamp)
box('stamp_block', (0.09, 0.05, 0.03), mat('stampb', '#1D211F', 0.5), (0, 0, 0.015), stamp)
pen = cyl('pen', 0.006, 0.14, mat('pen', '#1D211F', 0.4), 6, axis='Y')
page = make_box('page', (0.62, 0.48, 0.002), {(0, 0, 1): tex_mat('page', os.path.join(TEX, 'comic_02.png'), 0.9, 512, 0.2)},
                mat('pageback', '#EFEBE0', 0.9))

lines = Lines([(SPEAKER[k], t, os.path.join(VO, f'vo_{k}.wav')) for k, t in VO_AT.items()], FPS)

def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)

FORM_OUT = v3(0.02, -0.25, OPEN_B + 0.061)
def set_props(t):
    u = ease((t - FORM_T[0]) / (FORM_T[1] - FORM_T[0]))
    form.location = tuple(lerp(v3(0.02, 0.35, OPEN_B + 0.061), FORM_OUT, u)) if t >= FORM_T[0] else tuple(HIDE)
    form.rotation_euler = (0, 0, math.pi if False else 0)
    on = t >= CHECK_T
    for ob, rz, off in ((tick, 0.8, v3(-0.07, 0.035, 0.0015)), (tick2, -0.9, v3(-0.057, 0.04, 0.0016))):
        ob.location = tuple(FORM_OUT + off) if on else tuple(HIDE); ob.rotation_euler = (0, 0, rz)
    # pen: in visitor's hand region, dips at the tick
    if FORM_T[1] <= t < CHECK_T + 0.8:
        d = max(0.0, 1 - abs(t - CHECK_T) / 0.35)
        pen.location = tuple(FORM_OUT + v3(-0.02, -0.02, 0.07 - 0.06 * d)); pen.rotation_euler = (0.5, 0, 0.6)
    else:
        pen.location = tuple(HIDE)
    # stamp: raised by the clerk, lands at STAMP_T on the form (pushed back inside the window)
    if STAMP_T - 1.0 <= t < STAMP_T + 0.7:
        s = t - STAMP_T
        z = 0.0 if 0 <= s < 0.15 else (0.18 * min(1, -s / 0.4) if s < 0 else 0.18 * min(1, (s - 0.15) / 0.3))
        stamp.location = tuple(FORM_OUT + v3(0.02, 0.02, 0.003 + z))
    else:
        stamp.location = tuple(HIDE)
    stamp_mark.location = tuple(FORM_OUT + v3(0.03, 0.03, 0.0017)) if t >= STAMP_T else tuple(HIDE)
    stamp_mark.rotation_euler = (0, 0, -0.12)
    # the building answers
    lu = ease((t - LIGHTS_T[0]) / (LIGHTS_T[1] - LIGHTS_T[0]))
    LIGHT_Z.default_value = -10.0 if t < LIGHTS_T[0] else lerp(0.0, BH + 5, lu)
    # the page
    if t >= PAGE_T[0]:
        pu = min(1.0, (t - PAGE_T[0]) / (PAGE_T[1] - PAGE_T[0]))
        z = lerp(38.0, 1.55, pu ** 0.8)
        x = 0.4 + 2.2 * math.sin(pu * 7.0) * (1 - pu)
        page.location = (x - 0.4, -2.2 + 1.0 * (1 - pu), z)
        page.rotation_euler = (0.9 * math.sin(pu * 7.0 + 1) * (1 - pu) + 0.2, 0.4 * math.cos(pu * 5), pu * 1.3)
    else:
        page.location = tuple(HIDE)

WALK_FROM, WALK_TO = v3(0.6, -8.2, 0), v3(-0.38, -0.72, 0)
def set_people(t):
    tc = on_twos(t)
    # visitor walks to the window (faces +Y = yaw pi)
    wu = min(1.0, tc / 4.8)
    p = lerp(WALK_FROM, WALK_TO, wu)
    visitor.place(tuple(p), yaw=math.pi + 0.15 * (1 - wu))
    if wu < 1.0:
        visitor.walk(tc * 5.2)
    else:
        visitor.pose(POSES['stand'])
        if FORM_T[1] <= tc < CHECK_T + 0.8:
            visitor.add({'uarm_R': (-0.75, 0, 0.1), 'farm_R': (-0.8, 0, 0), 'head': (0.35, 0, 0)})
        if tc >= PAGE_T[0] + 1.2:
            visitor.look(0, -0.45 + 0.4 * min(1, (tc - PAGE_T[0] - 1.2) / 3.0))
        visitor.idle(tc)
    visitor.blink(t, 2)
    visitor.talk(lines.amount('VISITOR', t))
    # clerk at her desk; slides the form, raises and brings down the stamp
    clerk.pose(POSES['desk']); clerk.sit_height(0.52)
    if FORM_T[0] - 0.3 <= tc < FORM_T[1]:
        clerk.add({'uarm_R': (-0.45, 0, -0.1), 'farm_R': (0.3, 0, 0)})
    if STAMP_T - 1.0 <= tc < STAMP_T + 0.7:
        lift = 1.0 - min(1.0, abs(tc - (STAMP_T - 0.4)) / 0.5)
        clerk.add({'uarm_R': (-0.6 - 0.5 * lift, 0, -0.1), 'farm_R': (0.2, 0, 0)})
    clerk.look(0, 0.12)
    clerk.idle(tc, 0.5)
    clerk.blink(t, 3)
    clerk.talk(lines.amount('CLERK', t))

cam, cam_d = make_camera(clip_end=2000)
def camera_at(t):
    if t < T2:
        u = t / T2
        return lerp(v3(4.0, -34.0, 1.5), v3(3.6, -31.5, 1.5), u), v3(0.0, 0.0, 26.0), 13.0, 0.0
    if t < T3:
        return v3(2.3, -3.0, 1.62), v3(-0.15, -0.2, 1.4), 24.0, 0.0
    if t < T4:
        return v3(0.5, -0.72, 1.62), v3(0.0, -0.24, OPEN_B + 0.06), 36.0, 0.0
    if t < T5:
        return v3(0.42, -0.62, 1.52), v3(0.02, -0.22, OPEN_B + 0.08), 34.0, 0.0
    u = (t - T5) / (T_END - T5)
    return lerp(v3(-3.2, -17.0, 1.0), v3(-3.0, -15.5, 1.0), u), v3(-0.3, 0.0, 15.0 + 4 * u), 12.0, 0.0

def update(t):
    eye, tgt, lens, roll = camera_at(t)
    aim_camera(cam, cam_d, eye, tgt, lens, roll)
    set_props(t); set_people(t)
    return t >= T_END

def events():
    os.makedirs(WORK, exist_ok=True)
    json.dump({'VO_AT': VO_AT, 'SPEAKER': SPEAKER, 'FORM_T': FORM_T, 'CHECK_T': CHECK_T, 'STAMP_T': STAMP_T,
               'LIGHTS_T': LIGHTS_T, 'PAGE_T': PAGE_T, 'WALK_END': 4.8, 'cuts': [T2, T3, T4, T5], 'end': T_END, 'dur': DUR},
              open(os.path.join(WORK, 'events.json'), 'w'), indent=1)

if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(map(str, CUT_FRAMES))]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
