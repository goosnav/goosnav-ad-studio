"""lowpoly: the house kit for Monumental Low-Poly Vignettes (GLPV-001).

Actors are built from primitives (a few hundred triangles), parented at the joints, posed by
setting joint rotations every frame (transform-only animation, which Eevee batch-renders
reliably). Faces: eyes, brows, nose, jaw-flap mouth. Products are symbolic: shape, colour, title.

    from lowpoly import *
    a = Human('archivist', skin=SKIN[1], top=MAT['CLOTH_GRAY'], legs=..., hair=...)
    a.place((0, 0, 0), yaw=0)
    a.pose(POSES['sit'])            # dict joint -> (rx, ry, rz) radians
    a.walk(t)                       # walk cycle, sets legs/arms
    a.talk(open01); a.blink(t)
"""
import bpy, bmesh, math, wave, os
import numpy as np
from mathutils import Vector, Matrix, Euler
from bstudio import link, new_mat, img, v3

def hexrgb(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)  # sRGB -> linear

PAL = {  # bible §11 base world palette + product accents
    'concrete': '#777A78', 'concrete_dark': '#414746', 'concrete_pale': '#B4AC99', 'dust': '#9C8265',
    'earth': '#735E46', 'olive': '#586044', 'olive_dark': '#343A2A', 'sky_slate': '#758695',
    'sky_pale': '#AEBBC3', 'water': '#3F5964', 'rust': '#7A4933', 'utility_yellow': '#C3A53B',
    'offwhite': '#D5D2C8', 'nearblack': '#1D211F', 'book2': '#0033A0',
    'gk_teal': '#00B2A9', 'gk_orange': '#FE5000', 'gk_purple': '#330072',
}

_MATS = {}
def mat(name, color, rough=0.75, metal=0.0, noise=0.0, noise_scale=0.4, emit=0.0):
    """flat house material; optional broad low-frequency mottling (concrete, dust)"""
    key = (name, color, rough, metal, noise, noise_scale, emit)
    if key in _MATS:
        return _MATS[key]
    m, nt, out = new_mat(name)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    rgb = hexrgb(color) if isinstance(color, str) else color
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Specular IOR Level'].default_value = 0.3
    if noise > 0:
        tc = nt.nodes.new('ShaderNodeTexCoord')
        n = nt.nodes.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = noise_scale
        n.inputs['Detail'].default_value = 1.5
        nt.links.new(tc.outputs['Object'], n.inputs['Vector'])
        mr = nt.nodes.new('ShaderNodeMapRange')
        mr.inputs['To Min'].default_value = 1 - noise; mr.inputs['To Max'].default_value = 1 + noise * 0.5
        nt.links.new(n.outputs['Fac'], mr.inputs['Value'])
        mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        mix.inputs['Factor'].default_value = 1.0
        mix.inputs[6].default_value = (*rgb, 1)
        cm = nt.nodes.new('ShaderNodeCombineColor')
        for i in range(3):
            nt.links.new(mr.outputs[0], cm.inputs[i])
        nt.links.new(cm.outputs[0], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    else:
        b.inputs['Base Color'].default_value = (*rgb, 1)
    if emit:
        b.inputs['Emission Color'].default_value = (*rgb, 1)
        b.inputs['Emission Strength'].default_value = emit
    nt.links.new(b.outputs[0], out.inputs[0])
    _MATS[key] = m
    return m

def tex_mat(name, path, rough=0.6, size=512, emit=0.0):
    """image material downsampled to a game-era texture size (bible §5.2)"""
    return _tex(name, path, rough, size, emit)

def _tex(name, path, rough, size, emit):
    m, nt, out = new_mat(name)
    t = nt.nodes.new('ShaderNodeTexImage')
    im = img(path)
    w, h = im.size
    if max(w, h) > size:
        s = size / max(w, h)
        im.scale(max(1, int(w * s)), max(1, int(h * s)))
    t.image = im; t.interpolation = 'Linear'; t.extension = 'EXTEND'
    b = nt.nodes.new('ShaderNodeBsdfPrincipled'); b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = 0.3
    nt.links.new(t.outputs[0], b.inputs['Base Color'])
    if emit:
        nt.links.new(t.outputs[0], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = emit
    if im.channels == 4 or path.endswith('.png'):
        tp = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(t.outputs['Alpha'], mx.inputs[0]); nt.links.new(tp.outputs[0], mx.inputs[1])
        nt.links.new(b.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
        m.blend_method = 'CLIP'; m.shadow_method = 'CLIP'
    else:
        nt.links.new(b.outputs[0], out.inputs[0])
    return m

# ---------------------------------------------------------------- primitives
def box(name, size, m, loc=(0, 0, 0), parent=None, pivot=(0, 0, 0)):
    """box of `size` whose origin is `pivot` (in box-local offset terms: the box centre sits at -pivot)"""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = v.co.x * size[0] - pivot[0]; v.co.y = v.co.y * size[1] - pivot[1]; v.co.z = v.co.z * size[2] - pivot[2]
    bm.to_mesh(me); bm.free()
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    if parent:
        ob.parent = parent
    ob.location = loc
    return ob

def cyl(name, r, h, m, seg=8, loc=(0, 0, 0), parent=None, axis='Z', cap=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=seg, radius1=r, radius2=r, depth=h)
    if axis == 'X':
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, 'Y'))
    elif axis == 'Y':
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
    bm.to_mesh(me); bm.free()
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    if parent:
        ob.parent = parent
    ob.location = loc
    return ob

def ball(name, r, m, seg=8, rings=6, loc=(0, 0, 0), scale=(1, 1, 1), parent=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    bm.to_mesh(me); bm.free()
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    if parent:
        ob.parent = parent
    ob.location = loc; ob.scale = scale
    return ob

def empty(name, loc=(0, 0, 0), parent=None):
    ob = link(bpy.data.objects.new(name, None))
    if parent:
        ob.parent = parent
    ob.location = loc
    ob.rotation_mode = 'XYZ'
    return ob

# ---------------------------------------------------------------- actors
SKIN = ['#E6BFA0', '#C99A76', '#8D5E3E', '#5E3B26']
POSES = {
    'stand': {},
    'sit': {'thigh_L': (-1.5, 0, 0.05), 'thigh_R': (-1.5, 0, -0.05), 'shin_L': (1.5, 0, 0), 'shin_R': (1.5, 0, 0)},
    'desk': {'thigh_L': (-1.5, 0, 0.05), 'thigh_R': (-1.5, 0, -0.05), 'shin_L': (1.5, 0, 0), 'shin_R': (1.5, 0, 0),
             'uarm_L': (-0.75, 0, 0.12), 'uarm_R': (-0.75, 0, -0.12), 'farm_L': (-0.85, 0, 0), 'farm_R': (-0.85, 0, 0),
             'spine': (0.08, 0, 0)},
    'reach_R': {'uarm_R': (-1.1, 0, -0.15), 'farm_R': (-0.45, 0, 0)},
    'hold_front': {'uarm_L': (-0.5, 0, 0.25), 'uarm_R': (-0.5, 0, -0.25), 'farm_L': (-1.1, 0, -0.3), 'farm_R': (-1.1, 0, 0.3)},
    'read': {'uarm_L': (-0.55, 0, 0.3), 'uarm_R': (-0.55, 0, -0.3), 'farm_L': (-1.25, 0, -0.35), 'farm_R': (-1.25, 0, 0.35),
             'head': (0.35, 0, 0)},
    'arms_crossed': {'uarm_L': (-0.35, 0, 0.35), 'uarm_R': (-0.35, 0, -0.35), 'farm_L': (-1.6, 0, -0.9), 'farm_R': (-1.6, 0, 0.9)},
    'slump': {'spine': (0.25, 0, 0), 'head': (0.2, 0, 0), 'uarm_L': (0, 0, 0.15), 'uarm_R': (0, 0, -0.15)},
    'lean_in': {'spine': (0.35, 0, 0), 'head': (0.15, 0, 0), 'uarm_L': (-0.9, 0, 0.2), 'uarm_R': (-0.9, 0, -0.2),
                'farm_L': (-0.6, 0, 0), 'farm_R': (-0.6, 0, 0)},
}

class Human:
    """a ~600-triangle actor; faces -Y at yaw 0; root at the floor between the feet"""
    def __init__(self, name, skin=SKIN[1], top='#5A6470', legs='#2E3338', shoes='#1D211F', hair='#2A2420',
                 height=1.78, build=1.0, hair_style='short', glasses=False, hat=None, jacket=None):
        s = height / 1.78
        self.name = name
        self.s = s
        M = lambda c, r=0.8: mat(f'{name}_{c}', c, r)
        mskin, mtop, mlegs, mshoe, mhair = M(skin, 0.7), M(top), M(legs), M(shoes, 0.6), M(hair, 0.9)
        mdark = mat('ink', '#141414', 0.5)
        mjack = M(jacket) if jacket else mtop
        self.root = empty(f'{name}_root')
        J = {}
        def joint(n, loc, parent):
            J[n] = empty(f'{name}_{n}', loc, parent)
            return J[n]
        hip = joint('hips', (0, 0, 0.95 * s), self.root)
        box(f'{name}_pelvis', (0.34 * s * build, 0.2 * s, 0.16 * s), mlegs, parent=hip)
        sp = joint('spine', (0, 0, 0.06 * s), hip)
        box(f'{name}_torso', (0.40 * s * build, 0.23 * s * build, 0.56 * s), mjack, loc=(0, 0, 0.30 * s), parent=sp)
        nk = joint('neck', (0, 0, 0.60 * s), sp)
        cyl(f'{name}_neckm', 0.055 * s, 0.1 * s, mskin, 6, (0, 0, 0.03 * s), nk)
        hd = joint('head', (0, 0, 0.08 * s), nk)
        ball(f'{name}_skull', 0.12 * s, mskin, 8, 6, (0, 0, 0.12 * s), (0.9, 1.0, 1.12), hd)
        if hair_style != 'bald':
            hz = 0.2 * s if hair_style == 'short' else 0.17 * s
            hr = ball(f'{name}_hair', 0.126 * s, mhair, 8, 6, (0, 0.018 * s, hz), (0.94, 1.0, 0.72 if hair_style == 'short' else 1.0), hd)
            # back of the head: without this a figure seen from behind reads as a blank face
            ball(f'{name}_hairback', 0.12 * s, mhair, 8, 6, (0, 0.035 * s, 0.12 * s if hair_style == 'short' else 0.08 * s), (0.92, 0.85, 0.95 if hair_style == 'short' else 1.25), hd)
        if hat:
            cyl(f'{name}_hat', 0.13 * s, 0.07 * s, M(hat, 0.6), 10, (0, 0, 0.25 * s), hd)
        # face (on -Y side)
        fy = -0.105 * s
        self.eyes = [box(f'{name}_eye{i}', (0.028 * s, 0.01 * s, 0.018 * s), mdark, (x * s, fy, 0.14 * s), hd) for i, x in enumerate((-0.042, 0.042))]
        self.brows = [box(f'{name}_brow{i}', (0.05 * s, 0.012 * s, 0.011 * s), mhair, (x * s, fy - 0.002, 0.175 * s), hd) for i, x in enumerate((-0.045, 0.045))]
        box(f'{name}_nose', (0.03 * s, 0.03 * s, 0.05 * s), mskin, (0, fy - 0.01 * s, 0.11 * s), hd)
        self.mouth = box(f'{name}_mouth', (0.06 * s, 0.01 * s, 0.012 * s), mdark, (0, fy + 0.004, 0.06 * s), hd)
        if glasses:
            for x in (-0.042, 0.042):
                box(f'{name}_lens{x}', (0.045 * s, 0.006 * s, 0.032 * s), mat('glasses', '#222222', 0.3), (x * s, fy - 0.012 * s, 0.14 * s), hd)
        # arms
        for side, sx in (('L', 1), ('R', -1)):
            sh = joint(f'uarm_{side}', (sx * 0.245 * s * build, 0, 0.52 * s), sp)
            box(f'{name}_uarm{side}', (0.095 * s, 0.1 * s, 0.31 * s), mjack, (0, 0, -0.14 * s), sh)
            el = joint(f'farm_{side}', (0, 0, -0.30 * s), sh)
            box(f'{name}_farm{side}', (0.08 * s, 0.085 * s, 0.27 * s), mjack, (0, 0, -0.13 * s), el)
            wr = joint(f'hand_{side}', (0, 0, -0.27 * s), el)
            box(f'{name}_hand{side}', (0.075 * s, 0.035 * s, 0.1 * s), mskin, (0, 0, -0.05 * s), wr)
            J[f'grip_{side}'] = empty(f'{name}_grip{side}', (0, -0.03 * s, -0.08 * s), wr)
        # legs
        for side, sx in (('L', 1), ('R', -1)):
            th = joint(f'thigh_{side}', (sx * 0.095 * s, 0, -0.02 * s), hip)
            box(f'{name}_thigh{side}', (0.14 * s, 0.15 * s, 0.45 * s), mlegs, (0, 0, -0.22 * s), th)
            kn = joint(f'shin_{side}', (0, 0, -0.44 * s), th)
            box(f'{name}_shin{side}', (0.115 * s, 0.12 * s, 0.44 * s), mlegs, (0, 0, -0.22 * s), kn)
            an = joint(f'foot_{side}', (0, 0, -0.44 * s), kn)
            box(f'{name}_foot{side}', (0.11 * s, 0.26 * s, 0.075 * s), mshoe, (0, -0.06 * s, -0.035 * s), an)
        self.J = J
        self._rest_hip = 0.95 * s

    # ------------------------------------------------ placement and posing
    def place(self, loc, yaw=0.0):
        self.root.location = Vector(loc)
        self.root.rotation_euler = (0, 0, yaw)

    def pose(self, p, w=1.0, base=None):
        """apply pose dict (optionally blended from `base` by w); unspecified joints return to rest"""
        base = base or {}
        for n, j in self.J.items():
            if n.startswith('grip'):
                continue
            a = np.array(base.get(n, (0, 0, 0)), float); b = np.array(p.get(n, (0, 0, 0)), float)
            j.rotation_euler = tuple(a + (b - a) * w)
        self.J['hips'].location = (0, 0, self._rest_hip)

    def add(self, joints):
        """add rotations on top of the current pose"""
        for n, r in joints.items():
            e = self.J[n].rotation_euler
            self.J[n].rotation_euler = (e[0] + r[0], e[1] + r[1], e[2] + r[2])

    def sit_height(self, seat_z):
        """lower the hips so the thighs rest on a seat of height seat_z"""
        self.J['hips'].location = (0, 0.02 * self.s, seat_z + 0.08 * self.s)

    def walk(self, phase, amp=1.0, carry=False):
        s = math.sin(phase); c = math.cos(phase)
        self.J['thigh_L'].rotation_euler = (-0.42 * s * amp, 0, 0)
        self.J['thigh_R'].rotation_euler = (0.42 * s * amp, 0, 0)
        self.J['shin_L'].rotation_euler = (0.55 * max(0, c) * amp, 0, 0)
        self.J['shin_R'].rotation_euler = (0.55 * max(0, -c) * amp, 0, 0)
        if not carry:
            self.J['uarm_L'].rotation_euler = (0.3 * s * amp, 0, 0.05)
            self.J['uarm_R'].rotation_euler = (-0.3 * s * amp, 0, -0.05)
            self.J['farm_L'].rotation_euler = (-0.25, 0, 0); self.J['farm_R'].rotation_euler = (-0.25, 0, 0)
        self.J['hips'].location = (0, 0, self._rest_hip + 0.025 * abs(c) * amp)

    def idle(self, t, amount=1.0):
        """breathing + tiny weight shift, layered on current pose"""
        self.add({'spine': (0.015 * math.sin(t * 1.7) * amount, 0, 0.01 * math.sin(t * 0.6) * amount)})

    def look(self, yaw=0.0, pitch=0.0):
        self.add({'head': (pitch, 0, yaw)})

    def talk(self, amount):
        self.mouth.scale = (1, 1, 1 + 3.2 * max(0.0, min(1.0, amount)))

    def blink(self, t, seed=0):
        """blink every ~3-7 s"""
        r = (math.sin(seed * 12.9898) * 43758.5453) % 1
        period = 3.0 + 4.0 * r
        ph = (t + r * period) % period
        closed = ph < 0.12
        for e in self.eyes:
            e.scale = (1, 1, 0.15 if closed else 1)

    def grip(self, side='R'):
        return self.J[f'grip_{side}']

def attach(ob, target, offset=(0, 0, 0), rot=(0, 0, 0)):
    """snap an object to a target's world transform plus a local offset (called per frame)"""
    target_m = target.matrix_world
    ob.matrix_world = target_m @ Matrix.Translation(offset) @ Euler(rot).to_matrix().to_4x4()

# ---------------------------------------------------------------- symbolic products
def product_book(name='book2', scale=1.0, tex_dir=None, open_amount=0.0):
    """Goosnav Book 2: generic Book Two blue hardcover (real trim ~ 11 x 8.5 in landscape)"""
    from bstudio import make_box
    W, H, T = 0.28 * scale, 0.215 * scale, 0.022 * scale
    fm = _tex(f'{name}_front', os.path.join(tex_dir, 'gen_book_front.png'), 0.55, 512, 0)
    bm = _tex(f'{name}_back', os.path.join(tex_dir, 'gen_book_back.png'), 0.55, 512, 0)
    spm = _tex(f'{name}_spine', os.path.join(tex_dir, 'gen_book_spine.png'), 0.55, 256, 0)
    blue = mat('book2_board', PAL['book2'], 0.55)
    pages = mat('pages', '#EEE9DC', 0.9)
    root = empty(f'{name}_root')
    # lying flat: cover faces +Z. Build as a box with -Y face = cover, then rotate so the cover faces up.
    ob = make_box(f'{name}_body', (W, T, H), {(0, -1, 0): fm, (0, 1, 0): bm, (-1, 0, 0): spm}, blue)
    ob.parent = root
    ob.rotation_euler = (-math.pi / 2, 0, 0)  # cover (-Y face) turned to face up
    ob.location = (0, 0, T / 2)
    return root

def product_cardbox(name='gk_box', scale=1.0, tex_dir=None, src_dir=None):
    """Goosklerf box: the flat logo on the lid, purple body"""
    from bstudio import make_box
    logo = _tex(f'{name}_lid', os.path.join(src_dir, 'GOOSKLERF.jpg'), 0.5, 512, 0)
    body = mat('gk_body', PAL['gk_purple'], 0.5)
    ob = make_box(f'{name}', (0.1 * scale, 0.1 * scale, 0.045 * scale), {(0, 0, 1): logo}, body)
    ob.location = (0, 0, 0.0225 * scale)
    root = empty(f'{name}_root'); ob.parent = root
    return root

def card(name, tex_dir, face_up=True):
    """one Goosklerf card (generic card texture on both sides), 63 x 88 mm, lying flat"""
    m = _tex(f'card_{name}', os.path.join(tex_dir, 'gen_card.png'), 0.4, 256, 0)
    me = bpy.data.meshes.new(name)
    w, h = 0.063, 0.088
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap'); uv.data.foreach_set('uv', [0, 0, 1, 0, 1, 1, 0, 1])
    me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    ob.rotation_mode = 'XYZ'
    m.use_backface_culling = False
    return ob

def paper_sign(name, lines, size_px=(512, 256), bg='#D5D2C8', fg='#1D211F', out_dir='/tmp', font_px=64, align='left'):
    """a plain Helvetica sign/form texture (world set dressing)"""
    import subprocess, json as _j
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{name}.png')
    spec = _j.dumps({'lines': lines, 'size': size_px, 'bg': bg, 'fg': fg, 'font_px': font_px, 'align': align, 'out': path})
    # render with system python + PIL via studio.typeset helpers (Blender's python may lack PIL)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(['python3', '-c', f'''
import json, sys; sys.path.insert(0, {repo!r})
from PIL import Image, ImageDraw
from studio import config
s = json.loads({spec!r})
W, H = s["size"]; im = Image.new("RGB", (W, H), s["bg"]); d = ImageDraw.Draw(im)
y = int(H * 0.12)
for ln in s["lines"]:
    bold = ln.startswith("*"); t = ln.lstrip("*")
    f = config.font("font_sans_bold" if bold else "font_sans", s["font_px"])
    x = int(W * 0.08) if s["align"] == "left" else int((W - d.textlength(t, font=f)) / 2)
    d.text((x, y), t, font=f, fill=s["fg"]); y += int(s["font_px"] * 1.35)
im.save(s["out"])
'''], check=True)
    return path

# ---------------------------------------------------------------- world helpers
def fog_world(sky_top='#9FB0BD', sky_horizon='#C9D1D3', strength=1.0, density=0.004, anisotropy=0.2):
    world = bpy.data.worlds.new('world'); bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord'); sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*hexrgb(sky_horizon), 1); ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].color = (*hexrgb(sky_top), 1); ramp.color_ramp.elements[1].position = 0.6
    nt.links.new(sep.outputs['Z'], ramp.inputs[0])
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs[1].default_value = strength
    nt.links.new(ramp.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs['Surface'])
    if density > 0:
        vs = nt.nodes.new('ShaderNodeVolumePrincipled')
        vs.inputs['Color'].default_value = (*hexrgb(sky_horizon), 1)
        vs.inputs['Density'].default_value = density
        vs.inputs['Anisotropy'].default_value = anisotropy
        nt.links.new(vs.outputs[0], out.inputs['Volume'])
        ee = bpy.context.scene.eevee
        ee.volumetric_start = 0.5; ee.volumetric_end = 600.0
        ee.volumetric_tile_size = '8'; ee.volumetric_samples = 48
    return bg

def sun(energy=3.0, color='#FFF1DC', elev=35, azim=-30, angle=2.0):
    d = bpy.data.lights.new('sun', 'SUN'); d.energy = energy; d.color = hexrgb(color); d.angle = math.radians(angle)
    d.shadow_cascade_max_distance = 120
    ob = link(bpy.data.objects.new('sun', d))
    ob.rotation_euler = (math.radians(90 - elev), 0, math.radians(azim))
    return ob

def area(name, loc, size, energy, color='#FFFFFF', rot=(0, 0, 0)):
    d = bpy.data.lights.new(name, 'AREA'); d.energy = energy; d.size = size; d.color = hexrgb(color)
    ob = link(bpy.data.objects.new(name, d)); ob.location = loc; ob.rotation_euler = rot
    return ob

def point(name, loc, energy, color='#FFFFFF', radius=0.1):
    d = bpy.data.lights.new(name, 'POINT'); d.energy = energy; d.color = hexrgb(color); d.shadow_soft_size = radius
    ob = link(bpy.data.objects.new(name, d)); ob.location = loc
    return ob

# ---------------------------------------------------------------- dialogue -> mouth
def wav_envelope(path, fps=24):
    """per-frame speech envelope 0..1 from a wav (jaw-flap lip sync, bible §32 mode 1)"""
    w = wave.open(path, 'rb'); n = w.getnframes(); sr = w.getframerate(); ch = w.getnchannels()
    a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    hop = sr // fps
    frames = len(a) // hop
    env = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2)) for i in range(frames)])
    if env.max() > 0:
        env = env / np.percentile(env, 95)
    return np.clip(env, 0, 1)

class Lines:
    """dialogue schedule: [(speaker, t_start, wav_path)] -> mouth amount per speaker at time t"""
    def __init__(self, items, fps=24):
        self.items = [(sp, t0, wav_envelope(p, fps)) for sp, t0, p in items if os.path.exists(p)]
        self.fps = fps
    def amount(self, speaker, t):
        v = 0.0
        for sp, t0, env in self.items:
            if sp != speaker:
                continue
            i = int((t - t0) * self.fps)
            if 0 <= i < len(env):
                v = max(v, float(env[i]))
        # jaw flaps rather than tracks: quantise to 3 openings
        return 0.0 if v < 0.18 else (0.45 if v < 0.55 else 1.0)

def on_twos(t, fps=24):
    """character poses update on 2s (bible §7): quantise time to 12 poses per second"""
    return math.floor(t * fps / 2) * 2 / fps
