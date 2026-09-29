"""The Goosnav works: an enormous concrete hall with steel trusses, sodium high-bay lamps, haze and conveyors.
Hall runs along +Y from y=-24 to y=384, x in [-40, 40], trusses at z~26..33."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
from lib import *

HX = 40.0          # half width
Y0, Y1 = -24.0, 384.0
BAY = 12.0
ZT = 26.0          # truss bottom chord
LAMP_Z = 21.5
LAMP_X = (-27.0, -9.0, 9.0, 27.0)
# station footprints kept clear of generic machinery: (x0, x1, y0, y1)
ZONES = [(-21, -4.5, 20, 104), (4.5, 21, 36, 136), (-21, -4.5, 124, 156), (-24, 24, 240, 340), (22, 40, 158, 184)]
def in_zone(x, y, pad=3.0):
    return any(x0 - pad < x < x1 + pad and y0 - pad < y < y1 + pad for x0, x1, y0, y1 in ZONES)

def merged(name, parts):
    """build one mesh from boxes/cylinders: parts = [('box'|'cyl', loc, size, rot)]"""
    if name in bpy.data.meshes:
        return bpy.data.meshes[name]
    bm = bmesh.new()
    for part in parts:
        kind, loc, size = part[:3]; rot = part[3] if len(part) > 3 else (0, 0, 0)
        mi = part[4] if len(part) > 4 else 0
        tmp = bmesh.new()
        if kind == 'box':
            bmesh.ops.create_cube(tmp, size=1.0)
        elif kind == 'cone':
            bmesh.ops.create_cone(tmp, cap_ends=True, segments=16, radius1=0.5, radius2=0.05, depth=1.0)
        else:
            bmesh.ops.create_cone(tmp, cap_ends=True, segments=16 if kind == 'cyl' else 8, radius1=0.5, radius2=0.5, depth=1.0)
        for f in tmp.faces:
            f.material_index = mi
            f.smooth = kind in ('cyl', 'cone')
        M = Matrix.Translation(loc) @ Euler(rot).to_matrix().to_4x4() @ Matrix.Diagonal((*size, 1))
        bmesh.ops.transform(tmp, matrix=M, verts=tmp.verts)
        me_t = bpy.data.meshes.new('_t'); tmp.to_mesh(me_t); tmp.free()
        bm.from_mesh(me_t); bpy.data.meshes.remove(me_t)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    from lib import _uv_box
    _uv_box(me)
    return me

def beam(a, b, w, h=None):
    """box part from point a to b with cross-section w x h"""
    a, b = Vector(a), Vector(b)
    d = b - a
    L = d.length
    q = d.to_track_quat('Z', 'Y')
    return ('box', (a + b) / 2, (w, h or w, L), q.to_euler())

class Hall:
    def __init__(self):
        self.c = coll('HALL')
        use(self.c)
        self.lamps = []      # (fixture_glow_obj, light_obj_or_None, y, strike_time)
        self.movers = []
        rnd = random.Random(7)

        concrete = self.m_concrete = self.concrete_mat()
        wallc = mat_grimy('wall_concrete', (0.24, 0.23, 0.21), rough=(0.7, 0.95), scale=0.8, dirt=0.45, bump=0.25)
        steel = self.m_steel = mat_grimy('steel_dark', (0.07, 0.075, 0.08), rough=(0.35, 0.7), metal=0.7, scale=2.0, dirt=0.5)
        steel_cream = self.m_cream = mat_grimy('machine_cream', (0.52, 0.49, 0.42), rough=(0.3, 0.6), scale=1.5, dirt=0.45)
        steel_green = self.m_green = mat_grimy('machine_green', (0.10, 0.14, 0.12), rough=(0.3, 0.6), scale=1.5, dirt=0.4)
        rubber = self.m_rubber = mat_basic('rubber', (0.02, 0.02, 0.02), rough=0.75)
        self.m_belt = mat_grimy('belt', (0.035, 0.035, 0.035), rough=(0.55, 0.85), scale=6, dirt=0.3, bump=0.1)
        roofm = mat_basic('roof', (0.02, 0.02, 0.022), rough=0.9)
        self.m_glass_dark = mat_basic('window_night', (0.01, 0.012, 0.015), rough=0.15, spec=0.8)
        self.m_lampglow = mat_glow_objcolor('lamp_glow', base=(0.3, 0.25, 0.2), rough=0.3, strength=1.0)
        self.m_reflector = mat_basic('lamp_reflector', (0.25, 0.25, 0.24), rough=0.25, metal=1.0)

        L = Y1 - Y0
        # floor + ceiling + walls
        obj('floor', mesh_plane(), (0, (Y0 + Y1) / 2, 0), (2 * HX + 20, L + 40, 1), mat=concrete)
        obj('roofdeck', mesh_plane(), (0, (Y0 + Y1) / 2, 34.0), (2 * HX + 4, L + 4, 1), (math.pi, 0, 0), mat=roofm)
        for s in (-1, 1):
            obj('wall%d' % s, mesh_box(), (s * (HX + 0.5), (Y0 + Y1) / 2, 9.1), (1, L + 20, 18.2), mat=wallc)
            obj('wallt%d' % s, mesh_box(), (s * (HX + 0.5), (Y0 + Y1) / 2, 29.4), (1, L + 20, 9.2), mat=wallc)
        obj('wall_back', mesh_box(), (0, Y0 - 0.5, 17), (2 * HX + 2, 1, 34), mat=wallc)
        obj('wall_end', mesh_box(), (0, Y1 + 0.5, 17), (2 * HX + 2, 1, 34), mat=wallc)

        # column mesh (I-section) and truss mesh
        colm = merged('column', [('box', (0, 0, 13), (0.9, 0.08, 26)), ('box', (0, 0.35, 13), (0.9, 0.06, 26)),
                                 ('box', (0, -0.35, 13), (0.08, 0.7, 26)), ('box', (0, 0, 0.3), (1.3, 1.3, 0.6))])
        colm = merged('column_I', [('box', (0, -0.35, 13), (0.9, 0.06, 26)), ('box', (0, 0.35, 13), (0.9, 0.06, 26)),
                                   ('box', (0, 0, 13), (0.08, 0.7, 26)), ('box', (0, 0, 0.3), (1.3, 1.3, 0.6))])
        parts = [beam((-HX, 0, ZT), (HX, 0, ZT), 0.35), beam((-HX, 0, ZT + 1.5), (0, 0, 33.2), 0.35),
                 beam((HX, 0, ZT + 1.5), (0, 0, 33.2), 0.35)]
        n = 16
        for i in range(n + 1):
            x = -HX + 2 * HX * i / n
            ztop = ZT + 1.5 + (33.2 - ZT - 1.5) * (1 - abs(x) / HX)
            parts.append(beam((x, 0, ZT), (x, 0, ztop), 0.18))
            if i < n:
                x2 = -HX + 2 * HX * (i + 1) / n
                zt2 = ZT + 1.5 + (33.2 - ZT - 1.5) * (1 - abs(x2) / HX)
                if x < 0: parts.append(beam((x, 0, ztop), (x2, 0, ZT), 0.14))
                else: parts.append(beam((x, 0, ZT), (x2, 0, zt2), 0.14))
        trussm = merged('truss', parts)
        # purlins along the hall between trusses
        purl = merged('purlins', [beam((x, -BAY / 2, ZT + 1.5 + (33.2 - ZT - 1.5) * (1 - abs(x) / HX) + 0.3),
                                       (x, BAY / 2, ZT + 1.5 + (33.2 - ZT - 1.5) * (1 - abs(x) / HX) + 0.3), 0.14)
                                  for x in range(-36, 37, 6)])
        # lamp fixture: reflector cone + stem, glow disc separate
        fixt = merged('fixture', [('cyl', (0, 0, 0.35), (0.9, 0.9, 0.5), (0, 0, 0)), ('cyl', (0, 0, 0.75), (0.35, 0.35, 0.4), (0, 0, 0)),
                                  ('box', (0, 0, (ZT - LAMP_Z) / 2 + 0.6), (0.04, 0.04, ZT - LAMP_Z - 0.6))])
        glow = mesh_cyl('glowdisc', 24)
        mparts = [('box', (0, 0, -3.3 + 6.6 * i / 4), (0.12, BAY - 2.2, 0.1)) for i in range(5)]
        mparts += [('box', (0, -(BAY - 2.2) / 2 + (BAY - 2.2) * j / 6, 0), (0.12, 0.1, 6.6)) for j in range(7)]
        mull = merged('mullions', mparts)
        win = mesh_plane()

        nb = int((Y1 - Y0) // BAY)
        for k in range(nb + 1):
            y = Y0 + 6 + k * BAY
            if y > Y1: break
            obj('truss%02d' % k, trussm, (0, y, 0), mat=steel)
            if k < nb:
                obj('purl%02d' % k, purl, (0, y + BAY / 2, 0), mat=steel)
            for x in (-HX + 0.9, -13.5, 13.5, HX - 0.9):
                obj('col%02d_%d' % (k, x), colm, (x, y, 0), mat=steel)
            # high clerestory windows on both walls: piers, mullions, dark glass (glass casts no shadow)
            for s in (-1, 1):
                obj('pier%02d%d' % (k, s), mesh_box(), (s * (HX + 0.5), y, 21.5), (1.2, 2.2, 6.6), mat=wallc)
                obj('mull%02d%d' % (k, s), mull, (s * (HX + 0.3), y + BAY / 2, 21.5), mat=steel)
                g = obj('win%02d%d' % (k, s), win, (s * (HX + 0.6), y + BAY / 2, 21.5), (BAY - 2.2, 6.6, 1),
                        (0, -s * math.pi / 2, 0), mat=self.m_glass_dark, shadow=False)
            # lamps
            for x in LAMP_X:
                f = obj('fix%02d_%d' % (k, x), fixt, (x, y, LAMP_Z), mat=self.m_reflector)
                g = obj('glow%02d_%d' % (k, x), glow, (x, y, LAMP_Z + 0.08), (0.62, 0.62, 0.04), mat=self.m_lampglow,
                        shadow=False)
                g.color = (0, 0, 0, 1)
                self.lamps.append([g, None, y, x])

        # conveyors running the length of the hall
        belt = merged('conv_seg', [('box', (0, 0, 0.9), (1.1, 12.0, 0.12), (0, 0, 0), 1), ('box', (0.58, 0, 0.8), (0.06, 12.0, 0.3)),
                                   ('box', (-0.58, 0, 0.8), (0.06, 12.0, 0.3)),
                                   ('box', (0.5, -3, 0.4), (0.08, 0.08, 0.8)), ('box', (-0.5, -3, 0.4), (0.08, 0.08, 0.8)),
                                   ('box', (0.5, 3, 0.4), (0.08, 0.08, 0.8)), ('box', (-0.5, 3, 0.4), (0.08, 0.08, 0.8))])
        self.conv_x = (-20.0, -3.0, 3.0, 20.0)
        for cx in self.conv_x:
            for k in range(int((Y1 - Y0 - 30) // 12)):
                if abs(cx) < 5 and Y0 + 20 + k * 12 > 232:
                    continue
                cb = obj('conv%d_%02d' % (cx, k), belt, (cx, Y0 + 20 + k * 12, 0), mat=steel_green)
                if len(belt.materials) < 2:
                    belt.materials.append(None)
                cb.material_slots[1].link = 'OBJECT'; cb.material_slots[1].material = self.m_belt
        # parcels riding the conveyors (establishing-shot life)
        cardboard = mat_grimy('cardboard', (0.42, 0.30, 0.17), rough=(0.7, 0.9), scale=4, dirt=0.2, bump=0.05)
        pm = mesh_box()
        for cx in self.conv_x:
            if cx == 3.0:
                continue      # the book line
            for k in range(40):
                ob = obj('parcel', pm, (cx, 0, 1.2), (0.8, 0.6, 0.45), mat=cardboard)
                self.movers.append((ob, cx, k * 9.0 + rnd.uniform(0, 3), 1.2 if cx > 0 else -1.2))

        # the "city" of machines between the conveyors: a few multi-part variants, instanced
        variants = [self.machine_variant(i) for i in range(6)]
        mats3 = [steel_cream, steel, steel_green]
        for k in range(nb):
            y = Y0 + 12 + k * BAY
            for side in (-1, 1):
                for xr in ((8.0, 11.0), (24.5, 28.0), (31.0, 34.5)):
                    if rnd.random() < 0.72:
                        me = rnd.choice(variants)
                        x = side * rnd.uniform(*xr)
                        if in_zone(x, y):
                            continue
                        ob = obj('mach', me, (x, y + rnd.uniform(-2.5, 2.5), 0), (1, 1, 1), (0, 0, rnd.choice([0, math.pi]) + (math.pi / 2 if rnd.random() < 0.3 else 0)))
                        m1 = rnd.choice([steel_cream, steel_green, steel_cream])
                        for i, mm in enumerate([m1, steel, rubber]):
                            ob.material_slots[i].link = 'OBJECT'; ob.material_slots[i].material = mm
            # overhead pipe runs
        for i, (x, z, r) in enumerate([(-15.5, 17, 0.35), (-16.3, 17.2, 0.25), (15.5, 16.5, 0.4), (32, 12, 0.5), (-33, 13, 0.45)]):
            obj('pipe%d' % i, mesh_cyl('cyl16', 16), (x, (Y0 + Y1) / 2, z), (2 * r, 2 * r, Y1 - Y0), (math.pi / 2, 0, 0), mat=steel)
        # gantry crane spanning the hall (moves in S1)
        self.crane = empty('crane', (0, 120, 0))
        cm = merged('crane_m', [beam((-HX + 1, -1.2, 24.5), (HX - 1, -1.2, 24.5), 0.8, 1.4),
                               beam((-HX + 1, 1.2, 24.5), (HX - 1, 1.2, 24.5), 0.8, 1.4),
                               ('box', (6, 0, 25.4), (3, 3.4, 1.4), (0, 0, 0)),
                               beam((6, 0, 24.6), (6, 0, 15), 0.06), ('box', (6, 0, 14.6), (1.0, 0.5, 0.7), (0, 0, 0))])
        obj('crane_body', cm, (0, 0, 0), mat=steel_cream, parent=self.crane)

        # the viewing gantry at the back wall (opening shot stands on it)
        gp = [('box', (0, Y0 + 3.5, 17.2), (30, 5, 0.15)), ('box', (0, Y0 + 6.0, 18.3), (30, 0.07, 0.07)),
              ('box', (0, Y0 + 6.0, 17.75), (30, 0.05, 0.05))]
        gp += [('box', (x, Y0 + 6.0, 17.75), (0.06, 0.06, 1.1)) for x in range(-15, 16, 2)]
        gp += [('box', (0, Y0 + 6.0, 17.0), (30, 0.1, 0.35))]
        obj('gantry', merged('gantry', gp), (0, 0, 0), mat=steel)
        # moonlight through the clerestory (cold, faint); retuned per shot
        self.moon = light('moon', 'SUN', (0, 0, 60), 30.0, (0.50, 0.62, 1.0), size=math.radians(0.6))
        self.set_moon_dir((0.86, 0.22, -0.46))
        self.moon.data.shadow_cascade_max_distance = 420
        self.moon.data.shadow_cascade_exponent = 0.9
        self.moon.data.shadow_cascade_fade = 0.05
        self.moon.data.shadow_cascade_count = 4
        # haze: one big volume box
        self.haze_mat = mat_volume('haze', density=0.010, color=(1, 1, 1), aniso=0.45)
        obj('haze', mesh_box(), (0, (Y0 + Y1) / 2, 17), (2 * HX, Y1 - Y0, 34), mat=self.haze_mat, shadow=False)

    def machine_variant(self, i):
        r = random.Random(100 + i)
        P = []
        if i in (0, 3):   # press-like: side frames, rollers, top housing, motor
            w, d, h = r.uniform(3, 4.5), r.uniform(5, 8), r.uniform(3.5, 6)
            P += [('box', (0, 0, 0.3), (w + 0.6, d + 0.6, 0.6), (0, 0, 0), 1)]
            for sx in (-1, 1):
                P += [('box', (sx * w / 2, 0, h / 2 + 0.6), (0.35, d, h), (0, 0, 0), 0)]
            for j in range(4):
                P += [('cyl', (0, -d / 2 + d * (j + 0.5) / 4, 1.6 + (j % 2) * 1.2), (0.7, 0.7, w - 0.3), (0, math.pi / 2, 0), 1)]
            P += [('box', (0, 0, h + 0.9), (w + 0.4, d * 0.6, 1.2), (0, 0, 0), 0),
                  ('cyl', (w / 2 + 0.7, d / 3, 1.4), (1.2, 1.2, 1.6), (0, math.pi / 2, 0), 1),
                  ('box', (-w / 2 - 0.5, -d / 2 + 0.6, 1.4), (0.6, 1.0, 1.8), (0, 0, 0), 0)]
        elif i in (1, 4):  # tank on legs with ladder and pipework
            rr, h = r.uniform(1.4, 2.3), r.uniform(5, 10)
            P += [('cyl', (0, 0, h / 2 + 1.5), (2 * rr, 2 * rr, h), (0, 0, 0), 0),
                  ('cone', (0, 0, 1.0), (2 * rr, 2 * rr, 1.2), (math.pi, 0, 0), 0)]
            for a in range(4):
                an = a * math.pi / 2 + math.pi / 4
                P += [('box', (math.cos(an) * rr * 0.8, math.sin(an) * rr * 0.8, 0.9), (0.15, 0.15, 1.8), (0, 0, 0), 1)]
            for sx in (-0.25, 0.25):
                P += [('box', (rr + 0.25, sx, h / 2 + 1.5), (0.05, 0.05, h), (0, 0, 0), 1)]
            for j in range(int(h / 0.4)):
                P += [('box', (rr + 0.25, 0, 1.6 + j * 0.4), (0.04, 0.5, 0.04), (0, 0, 0), 1)]
            P += [('cyl', (0, 0, h + 1.5 + 2.5), (0.35, 0.35, 5), (0, 0, 0), 1),
                  ('box', (0, 0, h + 1.8), (2 * rr * 0.9, 2 * rr * 0.9, 0.6), (0, 0, 0), 0)]
        elif i == 2:       # control cabinets with a hood
            n = r.randint(3, 6)
            for j in range(n):
                P += [('box', (0, (j - n / 2) * 1.05, 1.1), (0.8, 1.0, 2.2), (0, 0, 0), 0),
                      ('box', (0.41, (j - n / 2) * 1.05, 1.5), (0.04, 0.8, 0.9), (0, 0, 0), 1)]
            P += [('box', (0, -0.5, 2.35), (1.0, n * 1.05 + 0.2, 0.12), (0, 0, 0), 1)]
        else:              # hopper and chute on a frame, with a walkway
            w = r.uniform(3, 4); h = r.uniform(6, 9)
            P += [('box', (0, 0, h), (w, w, 2.5), (0, 0, 0), 0),
                  ('cone', (0, 0, h - 2.4), (w * 1.3, w * 1.3, 2.4), (math.pi, 0, 0), 0)]
            for sx in (-1, 1):
                for sy in (-1, 1):
                    P += [('box', (sx * w / 2, sy * w / 2, h / 2), (0.2, 0.2, h), (0, 0, 0), 1)]
            P += [('box', (0, 0, h - 3.3), (0.5, 0.5, 2.0), (0, 0, 0), 1),
                  ('box', (0, w / 2 + 0.8, h - 1.2), (w + 1.5, 1.4, 0.1), (0, 0, 0), 1),
                  ('box', (0, w / 2 + 1.5, h - 0.7), (w + 1.5, 0.05, 0.05), (0, 0, 0), 1)]
        me = merged('machine_%d' % i, P)
        for _ in range(3):
            me.materials.append(None)
        return me

    def set_moon_dir(self, d):
        q = Vector(d).normalized().to_track_quat('-Z', 'Y')
        self.moon.rotation_mode = 'QUATERNION'; self.moon.rotation_quaternion = q

    def concrete_mat(self):
        m, nt, out = _nodes_('floor_concrete')
        L = nt.links
        p = nt.nodes.new('ShaderNodeBsdfPrincipled')
        tc = nt.nodes.new('ShaderNodeTexCoord')
        # large mottling
        n1 = nt.nodes.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value = 0.08; n1.inputs['Detail'].default_value = 10
        n1.inputs['Roughness'].default_value = 0.65
        L.new(tc.outputs['Object'], n1.inputs[0])
        c1 = nt.nodes.new('ShaderNodeValToRGB')
        c1.color_ramp.elements[0].position = 0.3; c1.color_ramp.elements[0].color = (0.10, 0.095, 0.09, 1)
        c1.color_ramp.elements[1].position = 0.75; c1.color_ramp.elements[1].color = (0.26, 0.245, 0.225, 1)
        L.new(n1.outputs['Fac'], c1.inputs[0])
        # slab joints every 6 m
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
        def joint(axis_out):
            d = nt.nodes.new('ShaderNodeMath'); d.operation = 'DIVIDE'; d.inputs[1].default_value = 6.0
            L.new(axis_out, d.inputs[0])
            fr = nt.nodes.new('ShaderNodeMath'); fr.operation = 'PINGPONG'; fr.inputs[1].default_value = 0.5
            L.new(d.outputs[0], fr.inputs[0])
            lt = nt.nodes.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = 0.004
            L.new(fr.outputs[0], lt.inputs[0])
            return lt.outputs[0]
        jx = joint(sep.outputs[0]); jy = joint(sep.outputs[1])
        jm = nt.nodes.new('ShaderNodeMath'); jm.operation = 'MAXIMUM'
        L.new(jx, jm.inputs[0]); L.new(jy, jm.inputs[1])
        mixj = nt.nodes.new('ShaderNodeMix'); mixj.data_type = 'RGBA'
        L.new(jm.outputs[0], mixj.inputs[0]); L.new(c1.outputs[0], mixj.inputs[6])
        mixj.inputs[7].default_value = (0.05, 0.05, 0.05, 1)
        L.new(mixj.outputs[2], p.inputs['Base Color'])
        # wet patches -> glossy
        n2 = nt.nodes.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value = 0.05; n2.inputs['Detail'].default_value = 6
        L.new(tc.outputs['Object'], n2.inputs[0])
        c2 = nt.nodes.new('ShaderNodeValToRGB')
        c2.color_ramp.elements[0].position = 0.48; c2.color_ramp.elements[0].color = (0.06, 0.06, 0.06, 1)
        c2.color_ramp.elements[1].position = 0.58; c2.color_ramp.elements[1].color = (0.7, 0.7, 0.7, 1)
        L.new(n2.outputs['Fac'], c2.inputs[0])
        L.new(c2.outputs[0], p.inputs['Roughness'])
        n3 = nt.nodes.new('ShaderNodeTexNoise'); n3.inputs['Scale'].default_value = 3.0
        L.new(tc.outputs['Object'], n3.inputs[0])
        bpn = nt.nodes.new('ShaderNodeBump'); bpn.inputs['Strength'].default_value = 0.08
        L.new(n3.outputs['Fac'], bpn.inputs['Height']); L.new(bpn.outputs[0], p.inputs['Normal'])
        p.inputs['Specular IOR Level'].default_value = 0.6
        L.new(p.outputs[0], out.inputs[0])
        return m

    def lamps_setup(self, n_real=60, shadow_ys=()):
        """make real spot lights for the nearest n_real lamps"""
        use(self.c)
        for i, l in enumerate(self.lamps):
            g, _, y, x = l
            if i < n_real:
                sh = any(abs(y - sy) < 1 for sy in shadow_ys)
                lo = light('L_%d' % i, 'SPOT', (x, y, LAMP_Z - 0.05), 1.0, SODIUM, size=0.35,
                           spot=math.radians(75), blend=0.35, shadow=sh)
                l[1] = lo

    def update_lamps(self, t, t_on=0.0, dt=0.09, warm=3.2, power=9000.0, order=None):
        """lamps strike near-to-far from t_on. Each warms from a dull red ember to sodium orange."""
        for i, (g, lo, y, x) in enumerate(self.lamps):
            ts = t_on + (y - Y0) / BAY * dt * 4 + (0.03 * (hash((int(x), int(y))) % 7))
            u = clamp((t - ts) / warm)
            if t < ts:
                c = (0, 0, 0); e = 0.0
            else:
                flick = 1.0
                if u < 0.12:  # the strike: a couple of flickers
                    flick = 0.4 + 0.6 * (math.sin((t - ts) * 90) > -0.2)
                col = vlerp(SODIUM_RED, SODIUM, smooth(u))
                lvl = (0.08 + 0.92 * smooth(u) ** 1.5) * flick
                c = tuple(col * lvl); e = lvl
            g.color = (c[0] * 60, c[1] * 60, c[2] * 60, 1)
            if lo is not None:
                lo.data.energy = power * e
                lo.data.color = vlerp(SODIUM_RED, SODIUM, smooth(u))

    def update_movers(self, t, speed=1.0):
        span = Y1 - Y0 - 60
        for ob, cx, off, v in self.movers:
            y = Y0 + 30 + ((off + t * v * speed) % span)
            if abs(cx) < 5 and y > 226:
                ob.location = (0, 0, -500); continue
            ob.location = (cx, y, 1.2)

def _nodes_(name):
    from lib import _nodes
    return _nodes(name)
