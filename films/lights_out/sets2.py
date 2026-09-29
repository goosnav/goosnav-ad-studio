"""Stations part 2: products, bindery, Goosklerf line, pneumatic tube, the arms, the loading dock."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
from lib import *
from sets import Pool, mat_steam, mat_spark, mat_paper_blank, PAPER, BEAT, BAR, _n

# ------------------------------------------------------------------ textured box with per-face UVs
def tbox_mesh(name, dims, faces, spine_face=None):
    """faces: dict face->material index for 'pz','nz','px','nx','py','ny'. Each face gets 0..1 UVs, upright
    for a viewer outside it (+z up for side faces). spine_face: that face maps u->z, v->y (book spine)."""
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    X, Y, Z = [d / 2 for d in dims]
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new('UVMap')
    def quad(pts, uvs, mi):
        vs = [bm.verts.new(p) for p in pts]
        f = bm.faces.new(vs); f.material_index = mi
        for l, uv in zip(f.loops, uvs): l[uvl].uv = uv
    U = [(0, 0), (1, 0), (1, 1), (0, 1)]
    # +z (u:+x, v:+y)
    quad([(-X, -Y, Z), (X, -Y, Z), (X, Y, Z), (-X, Y, Z)], U, faces['pz'])
    # -z (seen from below, turned over its y axis: u:-x, v:+y)
    quad([(X, -Y, -Z), (-X, -Y, -Z), (-X, Y, -Z), (X, Y, -Z)], U, faces['nz'])
    # +x (u:+y, v:+z)
    quad([(X, -Y, -Z), (X, Y, -Z), (X, Y, Z), (X, -Y, Z)], U, faces['px'])
    # -x
    if spine_face == 'nx':   # u: z(bottom->top), v: y
        quad([(-X, -Y, -Z), (-X, -Y, Z), (-X, Y, Z), (-X, Y, -Z)], [(0, 0), (1, 0), (1, 1), (0, 1)], faces['nx'])
    else:                    # u:-y, v:+z
        quad([(-X, Y, -Z), (-X, -Y, -Z), (-X, -Y, Z), (-X, Y, Z)], U, faces['nx'])
    # +y (u:-x, v:+z)
    quad([(X, Y, -Z), (-X, Y, -Z), (-X, Y, Z), (X, Y, Z)], U, faces['py'])
    # -y (u:+x, v:+z)
    quad([(-X, -Y, -Z), (X, -Y, -Z), (X, -Y, Z), (-X, -Y, Z)], U, faces['ny'])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    return me

def with_mats(ob, mats):
    me = ob.data
    while len(me.materials) < len(mats):
        me.materials.append(None)
    for i, m in enumerate(mats):
        ob.material_slots[i].link = 'OBJECT'; ob.material_slots[i].material = m
    return ob

BOOK_DIMS = (0.229, 0.171, 0.034)
BLUE = (0.0, 0.0331, 0.3515)          # #0033A0 in linear

def mat_page_edge(thick=0.034, board=0.0028):
    """page block edges with the blue board showing top and bottom"""
    m, nt, out = _n('page_edge')
    L = nt.links
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    ab = nt.nodes.new('ShaderNodeMath'); ab.operation = 'ABSOLUTE'; L.new(sep.outputs[2], ab.inputs[0])
    gt = nt.nodes.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = thick / 2 - board
    L.new(ab.outputs[0], gt.inputs[0])
    mz = nt.nodes.new('ShaderNodeMath'); mz.operation = 'MULTIPLY'; mz.inputs[1].default_value = 9000
    L.new(sep.outputs[2], mz.inputs[0])
    sn = nt.nodes.new('ShaderNodeMath'); sn.operation = 'SINE'; L.new(mz.outputs[0], sn.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.inputs['From Min'].default_value = -1
    mr.inputs['To Min'].default_value = 0.72; mr.inputs['To Max'].default_value = 0.9
    L.new(sn.outputs[0], mr.inputs[0])
    cc = nt.nodes.new('ShaderNodeCombineColor')
    for i, f in enumerate((1.0, 0.97, 0.9)):
        mm = nt.nodes.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = f
        L.new(mr.outputs[0], mm.inputs[0]); L.new(mm.outputs[0], cc.inputs[i])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    L.new(gt.outputs[0], mix.inputs[0]); L.new(cc.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (*BLUE, 1)
    L.new(mix.outputs[2], p.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.8; rr.inputs['To Max'].default_value = 0.55
    L.new(gt.outputs[0], rr.inputs[0]); L.new(rr.outputs[0], p.inputs['Roughness'])
    L.new(p.outputs[0], out.inputs[0])
    return m

class Products:
    """shared meshes/materials for the book, pack, kit box, card, comic sleeve, dice"""
    def __init__(self):
        self.m_front = mat_image('book_front', TEX + 'gen_book_front.png', rough=0.55, spec=0.35)
        self.m_back = mat_image('book_back', TEX + 'gen_book_back.png', rough=0.55, spec=0.35)
        self.m_spine = mat_image('book_spine', TEX + 'gen_book_spine.png', rough=0.55, spec=0.35)
        self.m_edge = mat_page_edge()
        self.book_me = tbox_mesh('book', BOOK_DIMS, dict(pz=0, nz=1, nx=2, px=3, py=3, ny=3), spine_face='nx')
        self.book_mats = [self.m_front, self.m_back, self.m_spine, self.m_edge]
        # pack 75 x 118 x 9 mm; front = gen_pack, back and sides plain foil
        self.m_pack = mat_image('pack_front', TEX + 'gen_pack.png', rough=0.28, spec=0.9)
        self.m_foil = mat_basic('foil', (0.62, 0.64, 0.68), rough=0.25, metal=0.9)
        self.pack_me = tbox_mesh('pack', (0.075, 0.118, 0.008), dict(pz=0, nz=1, px=1, nx=1, py=1, ny=1))
        self.pack_mats = [self.m_pack, self.m_foil]
        # kit box 300 x 225 x 70 mm
        self.m_kit_top = mat_image('kit_top', TEX + 'kit_top.png', rough=0.4, spec=0.5)
        self.m_kit_side = mat_image('kit_side', TEX + 'kit_side.png', rough=0.4, spec=0.5)
        self.m_kit_plain = mat_basic('kit_plain', (0.033, 0.0, 0.17), rough=0.4)
        self.kit_me = tbox_mesh('kit', (0.30, 0.225, 0.07), dict(pz=0, nz=2, px=2, nx=2, py=1, ny=1))
        self.kit_mats = [self.m_kit_top, self.m_kit_side, self.m_kit_plain]
        # card: two back-to-back planes with alpha-clipped rounded corners
        self.m_card = mat_image('card', TEX + 'gen_card.png', rough=0.35, alpha=True, spec=0.5)
        self.m_card.use_backface_culling = True
        # dice: 6 face materials per colour, with heat glow from ob.color.r
        self.die_mats = {c: [self.die_mat(c, k) for k in range(1, 7)] for c in ('teal', 'orange', 'purple')}
        self.die_me = self.die_mesh()

    def book(self, name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
        ob = obj(name, self.book_me, loc, (1, 1, 1), rot, parent=parent)
        return with_mats(ob, self.book_mats)
    def pack(self, name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
        return with_mats(obj(name, self.pack_me, loc, (1, 1, 1), rot, parent=parent), self.pack_mats)
    def kit(self, name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
        return with_mats(obj(name, self.kit_me, loc, (1, 1, 1), rot, parent=parent), self.kit_mats)
    def card(self, name, loc=(0, 0, 0), rot=(0, 0, 0), parent=None, size=(0.063, 0.088)):
        e = empty(name, loc, parent); e.rotation_euler = rot
        obj(name + 'a', mesh_plane(), (0, 0, 0.0002), (size[0], size[1], 1), mat=self.m_card, parent=e, shadow=True)
        obj(name + 'b', mesh_plane(), (0, 0, -0.0002), (size[0], size[1], 1), (0, math.pi, 0), mat=self.m_card, parent=e)
        return e

    def die_mat(self, col, k):
        m, nt, out = _n('die_%s_%d' % (col, k))
        L = nt.links
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = bpy.data.images.load(TEX + 'die_%s_%d.png' % (col, k), check_existing=True)
        L.new(tx.outputs['Color'], p.inputs['Base Color'])
        p.inputs['Roughness'].default_value = 0.22; p.inputs['Specular IOR Level'].default_value = 0.6
        p.inputs['Coat Weight'].default_value = 0.4
        oi = nt.nodes.new('ShaderNodeObjectInfo')
        sep = nt.nodes.new('ShaderNodeSeparateColor'); L.new(oi.outputs['Color'], sep.inputs[0])
        # heat: black-body-ish ramp, strength ~ heat^2
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.6, 0.02, 0.0, 1)
        e1 = ramp.color_ramp.elements.new(0.55); e1.color = (1.0, 0.25, 0.02, 1)
        ramp.color_ramp.elements[-1].position = 1.0; ramp.color_ramp.elements[-1].color = (1.0, 0.85, 0.55, 1)
        L.new(sep.outputs[0], ramp.inputs[0])
        L.new(ramp.outputs[0], p.inputs['Emission Color'])
        pw = nt.nodes.new('ShaderNodeMath'); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.2
        L.new(sep.outputs[0], pw.inputs[0])
        ms = nt.nodes.new('ShaderNodeMath'); ms.operation = 'MULTIPLY'; ms.inputs[1].default_value = 14
        L.new(pw.outputs[0], ms.inputs[0]); L.new(ms.outputs[0], p.inputs['Emission Strength'])
        L.new(p.outputs[0], out.inputs[0])
        return m

    def die_mesh(self, s=0.03):
        me = tbox_mesh('die', (s, s, s), dict(pz=0, nz=5, px=1, nx=4, py=2, ny=3))
        return me
    def die(self, name, col, loc=(0, 0, 0)):
        ob = obj(name, self.die_me, loc)
        with_mats(ob, self.die_mats[col])
        ob.color = (0, 0, 0, 1)
        return ob

# ------------------------------------------------------------------ BINDERY: gather, case, press; then the line
class Bindery:
    X, Y = 5.2, 50.0          # beside the book conveyor (x=3)
    TOP = 0.96                # table top
    def __init__(self, H, P):
        self.c = coll('BINDERY'); use(self.c)
        X, Y, TOP = self.X, self.Y, self.TOP
        self.P = P
        w, d, t = BOOK_DIMS
        box('b_table', (X, Y, TOP / 2), (1.8, 1.4, TOP), H.m_cream, bevel=0.03)
        box('b_jig', (X, Y, TOP + 0.01), (0.34, 0.28, 0.02), H.m_steel)
        for sx in (-1, 1):
            box('b_fence', (X + sx * 0.14, Y, TOP + 0.03), (0.01, 0.2, 0.04), H.m_steel)
        self.book_root = empty('bk_root', (X, Y, TOP + 0.02))
        # case: back board, spine, front board on a hinge
        bw, bd, bt = w, d, 0.0028
        self.m_board_in = mat_basic('endpaper', (0.85, 0.83, 0.78), rough=0.8)
        me_back = tbox_mesh('board_back', (bw, bd, bt), dict(pz=1, nz=0, px=2, nx=2, py=2, ny=2))
        with_mats(obj('bk_back', me_back, (0, 0, bt / 2), parent=self.book_root), [P.m_back, self.m_board_in, mat_basic('boardblue', BLUE, rough=0.55)])
        me_sp = tbox_mesh('board_spine', (0.003, bd, t), dict(pz=1, nz=1, px=1, nx=0, py=1, ny=1), spine_face='nx')
        with_mats(obj('bk_spine', me_sp, (-bw / 2 - 0.0015, 0, t / 2), parent=self.book_root), [P.m_spine, bpy.data.materials['boardblue']])
        self.hinge = empty('bk_hinge', (-bw / 2, 0, t), self.book_root)
        me_fr = tbox_mesh('board_front', (bw, bd, bt), dict(pz=0, nz=1, px=2, nx=2, py=2, ny=2))
        with_mats(obj('bk_front', me_fr, (bw / 2, 0, -bt / 2), parent=self.hinge), [P.m_front, self.m_board_in, bpy.data.materials['boardblue']])
        # page block: top shows a drawing page
        self.m_pages = [bpy.data.materials['page%d' % i] for i in range(6)]
        me_blk = tbox_mesh('block', (w - 0.006, d - 0.006, t - 2 * bt - 0.001), dict(pz=0, nz=1, px=1, nx=1, py=1, ny=1))
        self.block = with_mats(obj('bk_block', me_blk, (0.002, 0, t / 2), parent=self.book_root), [self.m_pages[3], P.m_edge])
        # falling sheets (gathered)
        self.falling = []
        for i, pg in enumerate([2, 1, 5, 0]):
            ob = obj('bk_sheet%d' % i, mesh_plane(), (0, 0, -500), (w - 0.006, d - 0.006, 1), mat=self.m_pages[pg])
            self.falling.append(ob)
        # the casing press: huge head for a small book
        self.head = empty('bk_head', (X, Y, TOP + 1.2))
        box('head_block', (0, 0, 1.25), (0.62, 0.52, 2.3), H.m_green, parent=self.head, bevel=0.04)
        box('head_plate', (0, 0, 0.06), (0.36, 0.28, 0.12), H.m_steel, parent=self.head, bevel=0.01)
        box('head_neck', (0, 0, 0.14), (0.5, 0.42, 0.08), H.m_steel, parent=self.head)
        for sx in (-1, 1):
            cyl('head_guide', (X + sx * 0.5, Y + 0.34, 2.2), 0.05, 4.4, H.m_reflector)
        box('head_crown', (X, Y, 4.5), (1.9, 1.3, 0.5), H.m_green, bevel=0.03)
        self.ram = cyl('head_ram', (X, Y, 3.5), 0.18, 1.6, H.m_reflector)
        self.dust = Pool('dust', mesh_sphere('sph16', 16, 8), mat_steam(), 4, shadow=False)
        for o in self.dust.obs: o.color = (0, 0, 0, 1)
        # inspection lamp: a neutral key so Book Two blue reads under sodium
        self.key = light('bk_key', 'AREA', (X + 0.9, Y - 0.9, TOP + 1.1), 14, (1.0, 0.93, 0.85), size=0.6)
        look_at(self.key, (X, Y, TOP))
        # the line of finished books on the x=3 conveyor
        self.line = [P.book('line%03d' % i) for i in range(170)]
        self.finished = P.book('bk_finished')
        self.finished.location = (0, 0, -500)

    def head_z(self, t, t_slam):
        up = self.TOP + 1.3
        down = self.TOP + 0.02 + BOOK_DIMS[2]
        if t < t_slam - 0.32: return up
        if t < t_slam: return lerp(up, down, ease_in((t - (t_slam - 0.32)) / 0.32, 3))
        if t < t_slam + 0.9: return down
        return lerp(down, up + 1.6, smooth((t - t_slam - 0.9) / 1.4))

    def update(self, t, T0, t_slam):
        """T0: start of the gather; sheets fall 0.4s apart, board swings, head slams at t_slam"""
        w, d, th = BOOK_DIMS
        top = self.TOP + 0.02
        for i, ob in enumerate(self.falling):
            ts = T0 + 0.1 + i * 0.42
            u = clamp((t - ts) / 0.55)
            if t < ts - 0.6:
                ob.location = Pool.PARK; continue
            zend = top + th - 0.0028 + 0.0004 * (i + 1)
            z = lerp(zend + 0.45, zend, ease_in(u, 2))
            wob = (1 - u) * 0.35
            ob.location = (self.X + 0.002 + wob * 0.08 * math.sin(i * 2 + t * 5), self.Y + wob * 0.05, z)
            ob.rotation_euler = (wob * 0.4 * math.sin(t * 7 + i), wob * 0.5 * math.cos(t * 6 + i), wob * 0.6 * (i % 2 - 0.5))
            if t > t_slam - 0.4:
                ob.location = Pool.PARK
        self.block.material_slots[0].material = self.m_pages[0] if t > T0 + 1.9 else self.m_pages[3]
        # board swing: from standing open (-100 deg) to closed
        sw = smoother(ramp(t, T0 + 1.9, t_slam - 0.45))
        self.hinge.rotation_euler = (0, math.radians(-100) * (1 - sw), 0)
        hz = self.head_z(t, t_slam)
        self.head.location = (self.X, self.Y, hz)
        self.ram.location = (self.X, self.Y, hz + 2.4 + 0.8)
        # dust puffs at the slam
        for j, ob in enumerate(self.dust.obs):
            age = t - t_slam
            if age < 0 or age > 2.0:
                ob.location = Pool.PARK; ob.color = (0, 0, 0, 1); continue
            a = j * math.pi / 2 + 0.4
            sz = 0.15 + 0.5 * ease_out(age / 2.0)
            ob.location = (self.X + math.cos(a) * (0.2 + 0.25 * ease_out(age / 2)), self.Y + math.sin(a) * (0.16 + 0.2 * ease_out(age / 2)),
                           self.TOP + 0.05 + 0.1 * age)
            ob.scale = (sz, sz, sz * 0.6)
            ob.color = (6.0 * (1 - age / 2.0) ** 2, 0, 0, 1)

    def update_line(self, t, speed=0.75, spacing=0.5, y0=52.0):
        span = spacing * len(self.line)
        for i, ob in enumerate(self.line):
            y = y0 + ((i * spacing + t * speed) % span)
            ob.location = (3.0, y, 0.96 + BOOK_DIMS[2] / 2 + 0.001)
            ob.rotation_euler = (0, 0, 0.04 * math.sin(i * 1.7))

# ------------------------------------------------------------------ GOOSKLERF LINE
class Goosklerf:
    X, Y = 11.0, 100.0
    TOP = 0.96
    def __init__(self, H, P):
        self.c = coll('GOOSKLERF'); use(self.c)
        X, Y, TOP = self.X, self.Y, self.TOP
        self.P = P
        box('g_bench', (X, Y + 2.0, TOP / 2), (1.4, 8.0, TOP), H.m_cream, bevel=0.03)
        # --- kiln with a glowing mouth (mouth faces +y)
        kiln = mat_grimy('kiln', (0.12, 0.10, 0.09), rough=(0.5, 0.9), scale=6, dirt=0.4)
        brick = mat_basic('firebrick', (0.3, 0.12, 0.06), rough=0.9, emit=(1.0, 0.45, 0.12), emit_strength=6.0)
        ky = Y - 1.2; mz = TOP + 0.34
        for part in [((0, 0, 0.6), (1.1, 1.0, 0.44)), ((-0.36, 0.0, 0.25), (0.38, 1.0, 0.3)), ((0.36, 0, 0.25), (0.38, 1.0, 0.3)),
                     ((0, 0, 0.05), (1.1, 1.0, 0.1))]:
            box('kiln', (X + part[0][0], ky + part[0][1], TOP + part[0][2]), part[1], kiln, bevel=0.02)
        box('kiln_hood', (X, ky - 0.1, TOP + 1.0), (0.8, 0.7, 0.4), kiln, bevel=0.02)
        cyl('kiln_flue', (X, ky - 0.2, TOP + 2.2), 0.12, 2.2, H.m_steel)
        box('kiln_inside', (X, ky - 0.2, TOP + 0.25), (0.34, 0.5, 0.3), brick)
        self.kiln_light = light('kiln_L', 'POINT', (X, ky + 0.25, mz - 0.05), 60, (1.0, 0.42, 0.1), size=0.1)
        # chute from the mouth to the quench tank
        self.chute_a = Vector((X, ky + 0.5, TOP + 0.12)); self.chute_b = Vector((X, ky + 1.5, TOP + 0.02 + 0.3))
        self.chute_a = Vector((X, ky + 0.5, TOP + 0.2)); self.chute_b = Vector((X, ky + 1.55, TOP + 0.47))
        a, b = self.chute_a, self.chute_b
        d = b - a
        ang = math.atan2(d.z, d.y)
        mid = (a + b) / 2
        box('chute', mid + Vector((0, 0, -0.01)), (0.08, d.length, 0.006), H.m_steel, rot=(ang, 0, 0))
        for sx in (-1, 1):
            box('chute_side', mid + Vector((sx * 0.042, 0, -0.004)), (0.004, d.length, 0.012), H.m_steel, rot=(ang, 0, 0))
        # the chute actually rises out of the kiln on a little lift and pours downhill into the tank
        # quench tank
        self.tank_y = ky + 1.95
        for dx, dy, sx, sy in ((0.24, 0, 0.02, 0.5), (-0.24, 0, 0.02, 0.5), (0, 0.24, 0.5, 0.02), (0, -0.24, 0.5, 0.02)):
            box('tank_wall', (X + dx, self.tank_y + dy, TOP + 0.2), (sx, sy, 0.4), H.m_steel)
        box('tank_floor', (X, self.tank_y, TOP + 0.01), (0.5, 0.5, 0.02), H.m_steel)
        self.water_z = TOP + 0.37
        wm = mat_glass('water', (0.05, 0.07, 0.08), 0.02, 0.55)
        obj('water', mesh_plane(), (X, self.tank_y, self.water_z), (0.46, 0.46, 1), mat=wm, shadow=False)
        box('tank_inner', (X, self.tank_y, TOP + 0.03), (0.46, 0.46, 0.02), mat_basic('tank_in', (0.08, 0.08, 0.08), rough=0.5))
        # dice
        cols = ['teal', 'orange', 'purple']
        self.dice = [P.die('die%d' % i, cols[i % 3]) for i in range(18)]
        self.steam = Pool('gsteam', mesh_sphere('sph16', 16, 8), bpy.data.materials['steam'], 12, shadow=False)
        for o in self.steam.obs: o.color = (0, 0, 0, 1)
        # --- shuffler: a steel base with a pivot; cards fan in an arc
        self.sh_pos = Vector((X - 0.4, Y + 1.7, TOP))
        box('sh_base', self.sh_pos + Vector((0, 0, 0.04)), (0.24, 0.14, 0.08), H.m_steel, bevel=0.01)
        box('sh_plinth', self.sh_pos + Vector((0, 0, 0.1)), (0.08, 0.05, 0.05), H.m_green)
        self.pivot = empty('sh_pivot', self.sh_pos + Vector((0, 0, 0.13)))
        self.pivot.rotation_euler = (math.radians(90) - math.radians(8), 0, 0)   # cards stand up, face -y
        self.cards = []
        for i in range(12):
            e = empty('card_arm%d' % i, (0, 0, 0), self.pivot)
            P.card('card%d' % i, (0, 0.044 - 0.002, -0.0012 * i), (0, 0, 0), parent=e)
            self.cards.append(e)
        # --- crimper: small belt, packs, heated jaws
        self.cr_y = Y + 3.2
        box('cr_belt', (X, self.cr_y, TOP + 0.08), (0.2, 1.8, 0.02), H.m_rubber)
        box('cr_frame', (X, self.cr_y, TOP + 0.035), (0.24, 1.9, 0.07), H.m_steel)
        self.m_hot = mat_glow_objcolor('jaw_hot', base=(0.2, 0.2, 0.2), rough=0.3, strength=1.0)
        self.jaw_top = empty('jaw_top', (X, self.cr_y, TOP + 0.3))
        box('jaw_bar', (0, 0, 0.03), (0.22, 0.04, 0.05), H.m_steel, parent=self.jaw_top)
        self.jaw_glow = box('jaw_edge', (0, 0, 0.0), (0.2, 0.03, 0.01), self.m_hot, parent=self.jaw_top, shadow=False)
        box('jaw_frame', (X + 0.2, self.cr_y + 0.05, TOP + 0.5), (0.5, 0.08, 0.06), H.m_green)
        box('jaw_post', (X + 0.42, self.cr_y + 0.05, TOP + 0.28), (0.05, 0.06, 0.5), H.m_green)
        cyl('jaw_ram', (X, self.cr_y + 0.05, TOP + 0.42), 0.02, 0.2, H.m_reflector)
        self.jaw_glow.color = (0, 0, 0, 1)
        self.packs = [P.pack('gpack%d' % i) for i in range(8)]
        self.cr_light = light('cr_L', 'POINT', (X, self.cr_y, TOP + 0.14), 0.0, (1.0, 0.4, 0.1), size=0.05, shadow=False)
        # an inspection key (neutral) and a warm top light
        self.key = light('g_key', 'AREA', (X + 1.2, Y + 0.5, TOP + 1.3), 90, (1.0, 0.92, 0.82), size=1.0)
        look_at(self.key, (X, Y + 1.0, TOP))

    def die_state(self, t, i, T0):
        """dice leave the kiln every 0.5s from T0: slide/tumble down the chute, arc, plunge"""
        ts = T0 + i * 0.5
        u = t - ts
        a, b = self.chute_a, self.chute_b
        if u < 0:
            return None, 1.0, (0, 0, 0)
        heat = 1.0
        s = 0.015
        if u < 1.0:   # climbing the chute on the lift belt (it inclines up, out of the kiln)
            k = smooth(u)
            p = a.lerp(b, k) + Vector((0, 0, s + 0.003))
            rot = (0, 0, i * 0.7)
            heat = 1.0 - 0.62 * k
        elif u < 1.45:  # tipped over the lip, tumbling in an arc into the tank
            k = (u - 1.0) / 0.45
            p0 = b + Vector((0, 0, s + 0.003))
            p = p0 + Vector((0, 0.35 * k, 0.12 * k - 0.55 * k * k))
            rot = (-k * math.pi * 1.5, 0.4 * k, i * 0.7)
            heat = 0.38 - 0.08 * k
            if p.z < self.water_z: p.z = self.water_z
        else:           # under water: sink, cool fast
            k = clamp((u - 1.45) / 1.2)
            p = Vector((b.x, b.y + 0.35, self.water_z - 0.02 - 0.12 * ease_out(k)))
            rot = (-math.pi * 1.5, 0.4, i * 0.7)
            heat = 0.3 * (1 - ease_out(clamp((u - 1.45) / 0.3)))
        return p, heat, rot

    def update(self, t, T0, sh_t0, cr_t0):
        for i, ob in enumerate(self.dice):
            p, heat, rot = self.die_state(t, i, T0)
            if p is None or t - (T0 + i * 0.5) > 3.0:
                ob.location = Pool.PARK; continue
            ob.location = p; ob.rotation_euler = rot
            ob.color = (heat, 0, 0, 1)
        # quench steam
        si = 0
        for i in range(len(self.dice)):
            tp = T0 + i * 0.5 + 1.45
            age = t - tp
            if 0 <= age < 2.2 and si < len(self.steam.obs):
                ob = self.steam.obs[si]; si += 1
                sz = 0.15 + 0.6 * ease_out(age / 2.2)
                ob.location = (self.X + 0.03 * math.sin(i), self.tank_y + 0.03, self.water_z + 0.08 + 0.6 * ease_out(age / 2.2))
                ob.scale = (sz, sz, sz * 1.4)
                ob.color = (22.0 * (1 - age / 2.2) ** 2, 0, 0, 1)
        for j in range(si, len(self.steam.obs)):
            self.steam.obs[j].location = Pool.PARK; self.steam.obs[j].color = (0, 0, 0, 1)
        self.kiln_light.data.energy = 60 * (1 + 0.08 * math.sin(t * 13) + 0.05 * math.sin(t * 31))
        # shuffler: fan out on the beat, hold, close; a riffle swaps order each cycle
        u = ((t - sh_t0) % (2 * BEAT)) / (2 * BEAT)
        fan = smooth(u / 0.2) if u < 0.72 else 1 - smoother((u - 0.72) / 0.2)
        cyc = int((t - sh_t0) // (2 * BEAT))
        n = len(self.cards)
        for i, e in enumerate(self.cards):
            j = (i * 5 + cyc * 7) % n if cyc % 2 else i
            ang = (j - (n - 1) / 2) / ((n - 1) / 2) * math.radians(52) * fan
            e.rotation_euler = (0, 0, -ang)
            e.location = (0, 0, 0.0012 * (j - i))
        # crimper: packs advance one pitch per half-bar; the jaws close on the beat and glow
        pitch = 0.26
        u = ((t - cr_t0) % (2 * BEAT)) / (2 * BEAT)
        n0 = math.floor((t - cr_t0) / (2 * BEAT))
        adv = smoother(u / 0.4)
        for i, ob in enumerate(self.packs):
            y = self.cr_y - 4 * pitch + ((i + n0 + adv) * pitch) % (pitch * len(self.packs))
            ob.location = (self.X, y, self.TOP + 0.095 + 0.004)
            ob.rotation_euler = (0, 0, 0)
            if y > self.cr_y + 0.9 or y < self.cr_y - 0.95:
                ob.location = Pool.PARK
        jz = 0.3
        if 0.45 < u < 0.85:
            k = (u - 0.45) / 0.4
            jz = 0.3 - 0.19 * math.sin(math.pi * clamp(k * 1.4))
        self.jaw_top.location = (self.X, self.cr_y + 0.05, self.TOP + jz)
        hot = clamp(1 - abs(u - 0.62) / 0.25)
        self.jaw_glow.color = (1.0 * hot * 10, 0.35 * hot * 10, 0.06 * hot * 10, 1)
        self.cr_light.data.energy = 3 * hot

# ------------------------------------------------------------------ PNEUMATIC TUBE: the standing order
class Tube:
    X, Y = -12.0, 140.0
    def __init__(self, H):
        self.c = coll('TUBE'); use(self.c)
        X, Y = self.X, self.Y
        brass = self.brass = mat_grimy('brass', (0.62, 0.42, 0.16), rough=(0.18, 0.4), metal=1.0, scale=5, dirt=0.35, bump=0.05)
        glass = mat_glass('tube_glass', (0.9, 0.95, 1.0), 0.03, 0.05)
        R = 0.2
        # loader cabinet
        box('tb_cab', (X, Y, 0.5), (0.9, 0.8, 1.0), H.m_green, bevel=0.02)
        box('tb_cab_top', (X, Y, 1.03), (0.95, 0.85, 0.06), brass, bevel=0.01)
        self.glass_z0, self.glass_z1 = 1.06, 1.86
        cyl('tb_glass', (X, Y, (self.glass_z0 + self.glass_z1) / 2), R, self.glass_z1 - self.glass_z0, glass, verts=48)
        for z in (self.glass_z0 + 0.03, self.glass_z1 - 0.03):
            cyl('tb_ring', (X, Y, z), R + 0.03, 0.07, brass, verts=48)
        # brass tube up to the roof
        cyl('tb_tube', (X, Y, (self.glass_z1 + 34) / 2), R, 34 - self.glass_z1, brass, verts=48)
        for z in range(3, 34, 3):
            cyl('tb_collar', (X, Y, z), R + 0.03, 0.08, brass, verts=48)

        # plaque
        pl = mat_image('plaque', TEX + 'plaque.png', rough=0.3, spec=0.8)
        pl_me = tbox_mesh('plaque', (0.48, 0.15, 0.01), dict(pz=0, nz=1, px=1, nx=1, py=1, ny=1))
        with_mats(obj('tb_plaque', pl_me, (X, Y - 0.405, 0.78), (1, 1, 1), (math.pi / 2, 0, 0)), [pl, brass])
        # valve lever
        self.lever = empty('tb_lever', (X + 0.38, Y - 0.25, 1.06))
        cyl('lever_rod', (0, 0, 0.18), 0.015, 0.36, H.m_reflector, parent=self.lever)
        obj('lever_knob', mesh_sphere(), (0, 0, 0.37), (0.06, 0.06, 0.06), mat=mat_basic('bakelite', (0.02, 0.01, 0.01), rough=0.25), parent=self.lever)
        # the carrier: glass capsule with brass caps holding this month's comic
        self.carrier = empty('carrier', (X, Y, 1.1))
        cm = mat_glass('carrier_glass', (1, 1, 1), 0.02, 0.03)
        cyl('car_glass', (0, 0, 0.19), R - 0.02, 0.3, cm, parent=self.carrier, verts=48)
        for z in (0.03, 0.35):
            cyl('car_cap', (0, 0, z), R - 0.015, 0.06, brass, parent=self.carrier, verts=48)
        self.m_comic = mat_image('comic_tube', TEX + 'comic_crop_1.png', rough=0.7, backface=PAPER)
        obj('car_comic', mesh_plane(), (0, 0, 0.19), (0.27, 0.27, 1), (math.pi / 2, 0, 0), mat=self.m_comic, parent=self.carrier)
        # roof hatch: a square of pre-dawn sky above the tube
        sky = mat_emit('hatch_sky', (0.18, 0.24, 0.42), 1.5)
        obj('hatch_sky', mesh_plane(), (X, Y, 33.9), (2.2, 2.2, 1), (math.pi, 0, 0), mat=sky, shadow=False)
        for s in (-1, 1):
            box('hatch_frame', (X + s * 1.15, Y, 33.6), (0.15, 2.45, 0.5), H.m_steel)
            box('hatch_frame', (X, Y + s * 1.15, 33.6), (2.45, 0.15, 0.5), H.m_steel)
        self.hatch_light = light('hatch_L', 'SPOT', (X, Y, 36), 2500, (0.55, 0.66, 1.0), size=0.8, spot=math.radians(30), blend=0.5)
        look_at(self.hatch_light, (X, Y, 0))
        self.key = light('tb_key', 'AREA', (X + 1.0, Y - 1.2, 2.2), 18, (1.0, 0.9, 0.78), size=0.8)
        look_at(self.key, (X, Y, 1.4))
        self.puff = Pool('tpuff', mesh_sphere('sph16', 16, 8), bpy.data.materials['steam'], 3, shadow=False)
        for o in self.puff.obs: o.color = (0, 0, 0, 1)

    def update(self, t, t_fire):
        X, Y = self.X, self.Y
        # lever pulled just before the fire
        k = smooth(ramp(t, t_fire - 0.5, t_fire - 0.15))
        self.lever.rotation_euler = (math.radians(-35 + 70 * k), 0, 0)
        # carrier: sits, shivers, then goes
        if t < t_fire:
            sh = 0.0015 * math.sin(t * 90) * ramp(t, t_fire - 0.5, t_fire)
            z = 1.2 + sh
        else:
            u = t - t_fire
            z = 1.2 + 2.5 * u * u + 7.0 * u * u * u   # accelerates away
        self.carrier.location = (X, Y, min(z, 33.5))
        if z > 33.4:
            self.carrier.location = Pool.PARK
        # a hiss of vented air at the base
        for j, ob in enumerate(self.puff.obs):
            age = t - t_fire
            if 0 <= age < 1.6:
                sz = 0.3 + 0.8 * ease_out(age / 1.6)
                ob.location = (X + (j - 1) * 0.35, Y - 0.2, 1.0 + 0.3 * age)
                ob.scale = (sz, sz, sz)
                ob.color = (3.0 * (1 - age / 1.6) ** 2, 0, 0, 1)
            else:
                ob.location = Pool.PARK; ob.color = (0, 0, 0, 1)

# ------------------------------------------------------------------ THE ARMS: each one building the next
class Arm:
    L1, L2, LT = 1.35, 1.15, 0.42
    SH = Vector((0, 0.18, 1.0))
    def __init__(self, name, loc, yaw, mats, stage=9):
        cream, steel, dark, glowm = mats
        self.root = empty(name, loc); self.root.rotation_euler = (0, 0, yaw)
        self.parts = {}
        self.parts['base'] = [cyl(name + '_base', (0, 0, 0.18), 0.5, 0.36, dark, parent=self.root, verts=32)]
        self.turret = empty(name + '_tur', (0, 0, 0.36), self.root)
        self.parts['turret'] = [cyl(name + '_turc', (0, 0, 0.12), 0.4, 0.24, cream, parent=self.turret, verts=32),
                                box(name + '_turb', (0, 0.05, 0.5), (0.5, 0.5, 0.6), cream, parent=self.turret, bevel=0.04)]
        self.sh = empty(name + '_sh', (self.SH.x, self.SH.y, self.SH.z - 0.36), self.turret)
        self.parts['upper'] = [cyl(name + '_shj', (0, 0, 0), 0.2, 0.62, steel, rot=(0, math.pi / 2, 0), parent=self.sh, verts=24),
                               box(name + '_ua', (0, self.L1 / 2, 0), (0.3, self.L1, 0.34), cream, parent=self.sh, bevel=0.05)]
        self.el = empty(name + '_el', (0, self.L1, 0), self.sh)
        self.parts['fore'] = [cyl(name + '_elj', (0, 0, 0), 0.16, 0.5, steel, rot=(0, math.pi / 2, 0), parent=self.el, verts=24),
                              box(name + '_fa', (0, self.L2 / 2, 0), (0.22, self.L2, 0.24), cream, parent=self.el, bevel=0.04),
                              cyl(name + '_mot', (0.16, 0.1, 0), 0.1, 0.18, dark, rot=(0, math.pi / 2, 0), parent=self.el, verts=16)]
        self.wr = empty(name + '_wr', (0, self.L2, 0), self.el)
        self.roll = empty(name + '_roll', (0, 0, 0), self.wr)
        self.parts['wrist'] = [cyl(name + '_wrj', (0, 0.06, 0), 0.1, 0.14, steel, rot=(math.pi / 2, 0, 0), parent=self.roll, verts=24),
                               box(name + '_tool', (0, 0.25, 0), (0.06, 0.3, 0.1), dark, parent=self.roll),
                               cyl(name + '_torch', (0, 0.36, -0.03), 0.018, 0.12, steel, rot=(math.pi / 2, 0, 0), parent=self.roll, verts=12)]
        self.tip = empty(name + '_tip', (0, self.LT, -0.03), self.roll)
        self.set_stage(stage)
        self.pose(math.radians(40), math.radians(-20), math.radians(-60))

    def set_stage(self, stage):
        order = ['base', 'turret', 'upper', 'fore', 'wrist']
        for i, k in enumerate(order):
            for ob in self.parts[k]:
                ob.hide_render = i >= stage
                ob.hide_viewport = i >= stage

    def pose(self, a1, a2, a3, yaw=None, roll=0.0):
        """absolute elevations (from horizontal) of upper arm, forearm and tool"""
        if yaw is not None:
            self.turret.rotation_euler = (0, 0, yaw)
        self.sh.rotation_euler = (a1, 0, 0)
        self.el.rotation_euler = (a2 - a1, 0, 0)
        self.wr.rotation_euler = (a3 - a2, 0, 0)
        self.roll.rotation_euler = (0, roll, 0)

    def ik(self, target, a3=math.radians(-55), roll=0.0):
        """point the tool tip at a world target; returns (yaw, a1, a2, a3)"""
        R = self.root.matrix_basis
        local = R.inverted() @ Vector(target)
        yaw = math.atan2(-local.x, local.y)
        # into the turret plane
        r = math.hypot(local.x, local.y) - self.SH.y
        h = local.z - self.SH.z
        wr = r - self.LT * math.cos(a3); wh = h - self.LT * math.sin(a3)
        d = min(math.hypot(wr, wh), self.L1 + self.L2 - 1e-3)
        c2 = (d * d - self.L1 ** 2 - self.L2 ** 2) / (2 * self.L1 * self.L2)
        q2 = -math.acos(clamp(c2, -1, 1))     # elbow up
        q1 = math.atan2(wh, wr) - math.atan2(self.L2 * math.sin(q2), self.L1 + self.L2 * math.cos(q2))
        return yaw, q1, q1 + q2, a3

class Arms:
    X = 0.0
    Y0 = 262.0
    GAP = 3.4
    N = 9
    def __init__(self, H):
        self.c = coll('ARMS'); use(self.c)
        cream = mat_grimy('robot_paint', (0.36, 0.36, 0.34), rough=(0.28, 0.42), scale=1.2, dirt=0.12, bump=0.02)
        dark = mat_grimy('robot_dark', (0.04, 0.04, 0.045), rough=(0.3, 0.6), metal=0.5, scale=4)
        mats = (cream, H.m_reflector, dark, None)
        self.arms = []
        for k in range(self.N):
            y = self.Y0 + k * self.GAP
            box('jig%d' % k, (self.X, y, 0.06), (1.6, 1.6, 0.12), H.m_steel, bevel=0.02)
            a = Arm('arm%d' % k, (self.X, y, 0.12), 0.0, mats, stage=5)
            self.arms.append(a)
        # the forearm that gets seated on arm 1: a spare forearm on a hoist
        self.hoist = empty('hoist', (0, 0, 0))
        self.chain = cyl('chain', (0, 0, 0), 0.012, 1.0, H.m_steel)
        # weld flashes: a point light per arm pair + spark pool
        self.welds = [light('weld%d' % k, 'POINT', (0, 0, -50), 0.0, (0.75, 0.85, 1.0), size=0.02, shadow=(k < 2)) for k in range(self.N)]
        self.sparks = Pool('wspark', mesh_sphere('sph8', 8, 4), bpy.data.materials['spark'], 160, (0.02, 0.02, 0.02), shadow=False)
        self.key = light('arm_key', 'SPOT', (6, self.Y0 - 4, 9), 9000, (1.0, 0.55, 0.2), size=1.0, spot=math.radians(40), blend=0.7)
        look_at(self.key, (0, self.Y0 + 2, 1.5))

    def update(self, t, T0):
        """T0: start of the reveal. Arm 0 welds arm 1; at T0+6.5 arm 1's forearm has been seated and it wakes;
        every other arm k welds arm k+1 on its own rhythm."""
        si = 0
        for k, a in enumerate(self.arms):
            nxt = self.arms[k + 1] if k + 1 < self.N else None
            # the arm being worked on holds a resting pose (upper arm up, forearm forward)
            rest = (math.radians(62), math.radians(5), math.radians(-40))
            if nxt is None:
                a.pose(*rest, yaw=0.0)
                continue
            # target: the next arm's elbow, jittering like a weld bead
            ph = t * 1.3 + k * 1.7
            jitter = Vector((0.04 * math.sin(ph * 5), 0.03 * math.sin(ph * 3.3), 0.04 * math.cos(ph * 4.1)))
            elbow = Vector((self.X, nxt.root.location.y, 0)) + Vector((0, Arm.SH.y + Arm.L1 * math.cos(rest[0]), 0.12 + Arm.SH.z + Arm.L1 * math.sin(rest[0])))
            tgt = elbow + Vector((0.28, -0.25, 0.05)) + jitter
            if k == 1 and t > T0 + 6.6:
                # arm 1 wakes: wrist turns once, then it turns to the next jig and reaches
                wk = t - (T0 + 6.6)
                yaw0, a1, a2, a3 = a.ik(tgt)
                rollv = 2 * math.pi * smoother(clamp(wk / 1.6))
                u = smoother(clamp((wk - 1.8) / 2.6))
                p_rest = rest
                y_, b1, b2, b3 = yaw0, lerp(p_rest[0], a1, u), lerp(p_rest[1], a2, u), lerp(p_rest[2], a3, u)
                a.pose(b1, b2, b3, yaw=lerp(0.0, y_, u), roll=rollv)
                weld_on = wk > 4.6
            elif k == 1:
                a.pose(*rest, yaw=0.0)
                weld_on = False
            else:
                yaw, a1, a2, a3 = a.ik(tgt)
                a.pose(a1, a2, a3, yaw=yaw)
                weld_on = True
            if k == 0:
                weld_on = T0 + 1.0 < t < T0 + 6.2
                if not (T0 + 1.0 < t < T0 + 6.4):
                    # arm 0 draws back after welding
                    u0 = smooth(clamp((t - (T0 + 6.2)) / 1.2)) if t > T0 + 6.2 else 1 - smooth(clamp((t - (T0 + 0.2)) / 0.8))
                    yaw, a1, a2, a3 = a.ik(tgt)
                    back = (math.radians(55), math.radians(20), math.radians(-30))
                    a.pose(lerp(a1, back[0], u0), lerp(a2, back[1], u0), lerp(a3, back[2], u0), yaw=lerp(yaw, 0.0, u0))
            # stage of the next arm: arm 1 lacks its forearm and wrist until they are lowered in
            L = self.welds[k]
            flick = 0.5 + 0.5 * math.sin(t * 47 + k * 3) * math.sin(t * 31 + k)
            bpy.context.view_layer.update() if False else None
            tip = a.root.matrix_basis @ a.turret.matrix_basis @ a.sh.matrix_basis @ a.el.matrix_basis @ a.wr.matrix_basis @ a.roll.matrix_basis @ Vector((0, Arm.LT + 0.02, -0.03))
            if weld_on:
                L.location = tip + Vector((0, 0, 0.05))
                L.data.energy = 220 * (0.35 + 0.65 * max(0.0, flick))
                for j in range(14):
                    if si >= len(self.sparks.obs): break
                    ob = self.sparks.obs[si]; si += 1
                    r = random.Random(int(t * 24) * 131 + j * 7 + k * 1000)
                    age = ((t * 24) % 1) / 24 + r.uniform(0, 0.45)
                    v = Vector((r.uniform(-1.5, 1.5), r.uniform(-1.5, 1.5), r.uniform(0.5, 2.5)))
                    p = tip + v * age + Vector((0, 0, -4.9 * age * age))
                    ob.location = p
                    kk = 1 - age / 0.45
                    ob.color = (kk * kk * 1.3, kk * kk, kk * kk, 1)
            else:
                L.data.energy = 0.0
                L.location = (0, 0, -50)
        for j in range(si, len(self.sparks.obs)):
            self.sparks.obs[j].location = Pool.PARK
        # arm 1's missing forearm: hidden before, lowered by the hoist between T0+2 and T0+5
        a1 = self.arms[1]
        seat = smoother(ramp(t, T0 + 1.6, T0 + 4.8))
        for ob in a1.parts['fore'] + a1.parts['wrist']:
            ob.hide_render = False
        a1.el.location = (0, Arm.L1, 0)
        drop = (1 - seat) * 1.4
        a1.el.location = (0, Arm.L1, 0)
        a1.el.matrix_basis = Matrix.Translation(Vector((0, Arm.L1, 0)) + (a1.sh.matrix_basis.to_3x3().inverted() @ Vector((0, 0, drop)))) @ a1.el.matrix_basis.to_3x3().to_4x4()
        ew = a1.root.matrix_basis @ a1.turret.matrix_basis @ a1.sh.matrix_basis @ Vector((0, Arm.L1, 0)) + Vector((0, 0, drop))
        top_z = 12.0
        self.chain.location = (ew.x, ew.y, (ew.z + 0.2 + top_z) / 2)
        self.chain.scale = (0.024, 0.024, max(top_z - ew.z - 0.2, 0.01))
        self.chain.hide_render = seat >= 1.0

# ------------------------------------------------------------------ THE LOADING DOCK at dawn
class Dock:
    DX = 40.0            # the +x wall
    Y = 170.0
    DOOR_W, DOOR_H = 10.0, 8.0
    def __init__(self, H, P):
        self.c = coll('DOCK'); use(self.c)
        wallc = bpy.data.materials['wall_concrete']
        Y = self.Y
        # cut the door: replace the +x lower wall with two pieces and a lintel
        bpy.data.objects['wall1'].hide_render = True
        use(H.c)
        L0, L1 = HM_Y0 - 10, HM_Y1 + 10
        a, b = Y - self.DOOR_W / 2, Y + self.DOOR_W / 2
        box('dwall_a', (self.DX + 0.5, (L0 + a) / 2, 9.1), (1, a - L0, 18.2), wallc)
        box('dwall_b', (self.DX + 0.5, (b + L1) / 2, 9.1), (1, L1 - b, 18.2), wallc)
        box('dwall_lintel', (self.DX + 0.5, Y, (self.DOOR_H + 18.2) / 2), (1, self.DOOR_W, 18.2 - self.DOOR_H), wallc)
        use(self.c)
        box('door_drum', (self.DX - 0.3, Y, self.DOOR_H + 0.4), (0.7, self.DOOR_W + 0.6, 0.7), H.m_steel)
        # the raised roller door's bottom slats peeking below the drum
        box('door_slat', (self.DX + 0.1, Y, self.DOOR_H - 0.15), (0.08, self.DOOR_W, 0.3), mat_grimy('door', (0.35, 0.37, 0.38), rough=(0.4, 0.7), metal=0.6, scale=3))
        # the dock edge: a raised platform lip and bumpers
        box('dock_lip', (self.DX + 1.2, Y, -0.6), (2.4, self.DOOR_W + 2, 1.2), H.m_concrete if hasattr(H, 'm_concrete') else wallc)
        for s in (-1, 1):
            box('bumper', (self.DX + 2.45, Y + s * 3.5, -0.45), (0.2, 0.5, 0.6), H.m_rubber)
        # outside: yard below the dock, fog, fence, lamp post, far buildings
        yard = mat_grimy('yard', (0.16, 0.16, 0.16), rough=(0.15, 0.7), scale=0.2, dirt=0.5, bump=0.05)
        obj('yard', mesh_plane(), (self.DX + 150, Y, -1.2), (300, 400, 1), mat=yard)
        fence = H.m_steel
        for i in range(-12, 13):
            box('fpost', (self.DX + 34, Y + i * 3.0, 0.3), (0.08, 0.08, 3.0), fence)
        for z in (1.6, 0.4):
            box('frail', (self.DX + 34, Y, z), (0.05, 75, 0.05), fence)
        box('lamppost', (self.DX + 14, Y - 9, 3.0), (0.18, 0.18, 8.4), fence)
        box('lamparm', (self.DX + 13.2, Y - 9, 7.1), (1.6, 0.12, 0.12), fence)
        rnd = random.Random(5)
        far = mat_basic('far', (0.05, 0.055, 0.06), rough=0.9)
        for i in range(14):
            w, h = rnd.uniform(8, 30), rnd.uniform(6, 28)
            box('far_bldg', (self.DX + rnd.uniform(90, 170), Y + rnd.uniform(-120, 120), h / 2 - 1.2), (rnd.uniform(10, 30), w, h), far)
        for i in range(3):
            cyl('chimney', (self.DX + 140 + i * 9, Y - 40 + i * 12, 20), 1.6, 44, far)
        # dawn mist outside
        self.mist = obj('mist', mesh_box(), (self.DX + 100, Y, 8), (196, 300, 20), mat=mat_volume('mist', 0.012, (0.85, 0.9, 1.0), 0.3), shadow=False)
        # sky dome visible through the door (emissive, lights nothing)
        sky = self.sky_mat()
        obj('sky', mesh_sphere('sky_sph', 48, 24), (self.DX, Y, 0), (900, 900, 900), mat=sky, shadow=False)
        # daylight through the door
        self.door_light = light('door_L', 'AREA', (self.DX + 0.8, Y, self.DOOR_H / 2), 0.0, (0.62, 0.72, 0.95), size=self.DOOR_W,
                                shadow=True)
        self.door_light.data.shape = 'RECTANGLE'; self.door_light.data.size = self.DOOR_H; self.door_light.data.size_y = self.DOOR_W
        self.door_light.rotation_euler = (0, math.radians(-90), 0)
        # the pallet and the goods
        self.px, self.py = self.DX - 2.4, Y + 0.5
        wood = mat_grimy('pallet_wood', (0.36, 0.26, 0.15), rough=(0.6, 0.9), scale=8, dirt=0.3, bump=0.2)
        pparts = []
        for i in range(7):
            pparts.append(('box', (0, -0.5 + 0.03 + i * (0.94 / 6), 0.13), (1.2, 0.1, 0.022)))
        for x in (-0.55, 0, 0.55):
            pparts.append(('box', (x, 0, 0.06), (0.1, 1.0, 0.1)))
        import hall as _h
        obj('pallet', _h.merged('pallet', pparts), (self.px, self.py, 0), (1, 1, 1), (0, 0, math.radians(8)), mat=wood)
        top = 0.141
        g = empty('goods', (self.px, self.py, top)); g.rotation_euler = (0, 0, math.radians(8))
        self.goods = g
        box('carton', (0.3, 0.05, 0.16), (0.4, 0.62, 0.32), bpy.data.materials['cardboard'], parent=g, bevel=0.008)
        la = math.radians(14)
        def stand():
            n = Vector((-math.cos(la), 0, math.sin(la))); up = Vector((math.sin(la), 0, math.cos(la)))
            xl = up.cross(n)
            return Matrix((xl, up, n)).transposed().to_euler()
        e = stand()
        bk = P.book('dock_book', (0.1 - 0.017 * math.cos(la) - 0.0855 * math.sin(la), 0.15, 0.0855 * math.cos(la) + 0.017 * math.sin(la) + 0.001), e, parent=g)
        P.pack('dock_pack', (0.1 - 0.004 - 0.059 * math.sin(la), -0.02, 0.059 * math.cos(la) + 0.002), e, parent=g)
        P.kit('dock_kit', (-0.14, -0.2, 0.036), (0, 0, math.radians(-98)), parent=g)
        m_c = mat_image('comic_dock', TEX + 'comic_crop_4.png', rough=0.6, backface=PAPER)
        cw = 0.36; chh = cw * 755 / 2114
        obj('dock_comic', mesh_plane(), (-0.37, 0.1, 0.003), (cw, chh, 1), (0, 0, math.radians(-86)), mat=m_c, parent=g)
        obj('dock_sleeve', mesh_plane(), (-0.37, 0.1, 0.0045), (cw + 0.02, chh + 0.02, 1), (0, 0, math.radians(-86)),
            mat=mat_glass('sleeve', (1, 1, 1), 0.08, 0.1), parent=g, shadow=False)
        self.fill = light('dock_fill', 'AREA', (self.px - 1.8, self.py - 0.2, 2.2), 0.0, (1.0, 0.62, 0.3), size=1.5, shadow=False)
        look_at(self.fill, (self.px - 0.2, self.py, 0.4))
        # birds
        bird = mat_basic('bird', (0.01, 0.01, 0.012), rough=0.9)
        self.birds = [obj('bird%d' % i, mesh_box(), (0, 0, -500), (0.35, 0.08, 0.02), mat=bird, shadow=False) for i in range(4)]
        self.wings = []

    def sky_mat(self):
        m, nt, out = _n('dawn_sky')
        L = nt.links
        e = nt.nodes.new('ShaderNodeEmission')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
        cr = nt.nodes.new('ShaderNodeValToRGB')
        els = cr.color_ramp.elements
        els[0].position = 0.0; els[0].color = (0.55, 0.52, 0.5, 1)
        e1 = els.new(0.02); e1.color = (0.42, 0.46, 0.55, 1)
        els[-1].position = 0.25; els[-1].color = (0.10, 0.14, 0.26, 1)
        L.new(sep.outputs[2], cr.inputs[0])
        L.new(cr.outputs[0], e.inputs['Color'])
        e.inputs['Strength'].default_value = 1.0
        L.new(e.outputs[0], out.inputs[0])
        return m

    def update(self, t, T0):
        for i, b in enumerate(self.birds):
            u = t - T0 - i * 0.6
            x = self.DX + 60 + i * 8
            y = self.Y + 60 - u * 9
            z = 14 + i * 1.5 + 0.6 * math.sin(u * 2 + i)
            b.location = (x, y, z)
            b.rotation_euler = (0.5 * math.sin(u * 18 + i), 0, math.pi / 2)

HM_Y0, HM_Y1 = -24.0, 384.0
