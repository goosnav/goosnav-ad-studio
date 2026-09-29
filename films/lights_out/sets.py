"""Stations of the Goosnav works. Each station is a class with build() in __init__ and update(t)."""
import bpy, math, random
from mathutils import Vector, Matrix, Euler
from lib import *
import hall as HM

BEAT = 0.625          # 96 BPM
BAR = 4 * BEAT
PAGE_ORDER = [0, 4, 5, 1, 2, 3]
PAPER = (0.93, 0.91, 0.86)

def beat_phase(t, period):
    return (t % period) / period

# ------------------------------------------------------------------ paper
def mat_paper_blank(name='paper_blank', col=PAPER):
    m, nt, out = _n(name)
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*col, 1)
    p.inputs['Roughness'].default_value = 0.7
    p.inputs['Specular IOR Level'].default_value = 0.25
    # faint fibre so a moving web reads as moving
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.name = 'scroll'
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 6
    nt.links.new(tc.outputs['Object'], mp.inputs[0]); nt.links.new(mp.outputs[0], nz.inputs[0])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.05
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs[0], p.inputs['Normal'])
    nt.links.new(p.outputs[0], out.inputs[0])
    return m

def _n(name):
    from lib import _nodes
    return _nodes(name)

def mat_reel_side():
    """paper roll end-grain: fine concentric rings"""
    m, nt, out = _n('reel_side')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    # radial distance in the object's YZ plane
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(sep.outputs[1], comb.inputs[0]); nt.links.new(sep.outputs[2], comb.inputs[1])
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(comb.outputs[0], ln.inputs[0])
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 900
    nt.links.new(ln.outputs['Value'], mul.inputs[0])
    sn = nt.nodes.new('ShaderNodeMath'); sn.operation = 'SINE'; nt.links.new(mul.outputs[0], sn.inputs[0])
    cr = nt.nodes.new('ShaderNodeMapRange'); cr.inputs['From Min'].default_value = -1
    cr.inputs['To Min'].default_value = 0.8; cr.inputs['To Max'].default_value = 0.97
    nt.links.new(sn.outputs[0], cr.inputs[0])
    cm = nt.nodes.new('ShaderNodeCombineColor')
    for i, f in enumerate((1.0, 0.97, 0.9)):
        mm = nt.nodes.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = f
        nt.links.new(cr.outputs[0], mm.inputs[0]); nt.links.new(mm.outputs[0], cm.inputs[i])
    nt.links.new(cm.outputs[0], p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = 0.8
    nt.links.new(p.outputs[0], out.inputs[0])
    return m

def mat_ink():
    return mat_basic('ink', (0.004, 0.004, 0.005), rough=0.08, spec=1.0)

def mat_spark():
    return mat_emit('spark', (1.0, 0.55, 0.2), 60.0, objcolor=True)

def mat_steam():
    """volume puff whose density follows ob.color.r"""
    m, nt, out = _n('steam')
    v = nt.nodes.new('ShaderNodeVolumePrincipled')
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # soft sphere falloff * noise
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; nt.links.new(tc.outputs['Object'], ln.inputs[0])
    fall = nt.nodes.new('ShaderNodeMapRange'); fall.inputs['From Min'].default_value = 0.5; fall.inputs['From Max'].default_value = 0.1
    nt.links.new(ln.outputs['Value'], fall.inputs[0])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.5; nz.inputs['Detail'].default_value = 4
    nt.links.new(tc.outputs['Object'], nz.inputs[0])
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'
    nt.links.new(fall.outputs[0], m1.inputs[0]); nt.links.new(nz.outputs['Fac'], m1.inputs[1])
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(oi.outputs['Color'], sep.inputs[0])
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'
    nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(sep.outputs[0], m2.inputs[1])
    nt.links.new(m2.outputs[0], v.inputs['Density'])
    v.inputs['Color'].default_value = (0.9, 0.9, 0.92, 1)
    v.inputs['Anisotropy'].default_value = 0.3
    nt.links.new(v.outputs[0], out.inputs['Volume'])
    return m

class Pool:
    """a fixed set of objects re-used by transforms; parked far away when unused"""
    PARK = (0, 0, -500)
    def __init__(self, name, me, mat, n, scale=(1, 1, 1), shadow=True):
        self.obs = [obj('%s%03d' % (name, i), me, self.PARK, scale, mat=mat, shadow=shadow) for i in range(n)]
    def park(self, i):
        self.obs[i].location = self.PARK

# ------------------------------------------------------------------ PAPER LINE: reel -> rollers -> press -> cutter
class PaperLine:
    X = -11.5
    REEL_Y, REEL_Z, REEL_R, W = 34.0, 9.4, 9.0, 3.5
    PRESS_Y = 76.0
    BED_Z = 1.35
    SHEET_W, SHEET_L = 4.0, 4.0 * 1080 / 1400     # W along the web (y), L across it (x)
    PITCH = 4.0
    def __init__(self, H):
        self.c = coll('PAPER'); use(self.c)
        X = self.X
        steel = H.m_steel; cream = H.m_cream; green = H.m_green
        self.m_blank = mat_paper_blank()
        self.m_pages = [mat_image('page%d' % i, TEX + 'page_%02d.png' % i, rough=0.65, backface=PAPER) for i in range(6)]
        # --- the reel
        self.reel = empty('reel', (X, self.REEL_Y, self.REEL_Z))
        rs = mat_reel_side()
        obj('reel_body', mesh_cyl('cyl96', 96), (0, 0, 0), (2 * self.REEL_R, 2 * self.REEL_R, self.W), (0, math.pi / 2, 0),
            mat=self.m_blank, parent=self.reel)
        for s in (-1, 1):
            obj('reel_side%d' % s, mesh_cyl('cyl96', 96), (s * (self.W / 2 + 0.002), 0, 0), (2 * self.REEL_R - 0.02, 2 * self.REEL_R - 0.02, 0.01),
                (0, math.pi / 2, 0), mat=rs, parent=self.reel)
            obj('reel_hub%d' % s, mesh_cyl('cyl32', 32), (s * (self.W / 2 + 0.4), 0, 0), (2.4, 2.4, 0.8), (0, math.pi / 2, 0), mat=steel, parent=self.reel)
            for k in range(6):  # hub bolts, so the rotation reads
                a = k * math.pi / 3
                obj('bolt', mesh_cyl('cyl16', 16), (s * (self.W / 2 + 0.85), math.cos(a) * 0.8, math.sin(a) * 0.8), (0.22, 0.22, 0.2),
                    (0, math.pi / 2, 0), mat=cream, parent=self.reel)
        obj('reel_axle', mesh_cyl('cyl32', 32), (X, self.REEL_Y, self.REEL_Z), (0.9, 0.9, self.W + 5), (0, math.pi / 2, 0), mat=steel)
        # A-frame stands
        for s in (-1, 1):
            xs = X + s * (self.W / 2 + 1.6)
            for d in (-1, 1):
                a = Vector((xs, self.REEL_Y + d * 7.0, 0)); b = Vector((xs, self.REEL_Y, self.REEL_Z))
                mid = (a + b) / 2; L = (b - a).length
                ang = math.atan2(d * 7.0, self.REEL_Z)
                obj('aframe', mesh_bevel_box('bb05', 0.05), mid, (0.9, 0.7, L), (ang, 0, 0), mat=green)
            obj('bearing', mesh_bevel_box('bb05', 0.05), (xs, self.REEL_Y, self.REEL_Z), (1.2, 1.8, 1.8), mat=green)
            obj('foot', mesh_bevel_box('bb05', 0.05), (xs, self.REEL_Y, 0.3), (1.6, 16, 0.6), mat=green)
        # --- web path: reel top -> R1 (high) -> R2 (low) -> bed -> press -> cutter
        top = Vector((X, self.REEL_Y, self.REEL_Z + self.REEL_R))
        self.R1 = Vector((X, 46.0, 21.0)); self.R2 = Vector((X, 58.0, 2.6)); self.R3 = Vector((X, 62.0, self.BED_Z))
        for i, (pnt, r) in enumerate([(self.R1, 0.6), (self.R2, 0.6), (self.R3, 0.35)]):
            obj('roller%d' % i, mesh_cyl('cyl32', 32), pnt, (2 * r, 2 * r, self.W + 0.8), (0, math.pi / 2, 0), mat=steel)
            for s in (-1, 1):
                obj('rstand', mesh_bevel_box('bb05', 0.05), (X + s * (self.W / 2 + 0.6), pnt.y, pnt.z / 2), (0.4, 0.6, pnt.z + 0.4), mat=green)
        self.webs = []
        for a, b in [(top + Vector((0, 0, 0.0)), self.R1 + Vector((0, 0, 0.6))), (self.R1 + Vector((0, 0.6, 0)), self.R2 + Vector((0, -0.6, 0))),
                     (self.R2 + Vector((0, 0, -0.6)), self.R3 + Vector((0, 0, 0.0)))]:
            d = b - a
            ob = obj('web', mesh_plane(), (a + b) / 2, (self.W, d.length, 1), mat=self.m_blank)
            ob.rotation_euler = (math.atan2(d.z, d.y), 0, 0)
            self.webs.append(ob)
        # --- press
        py = self.PRESS_Y
        self.bed_top = self.BED_Z
        box('bed', (X, py + 6, self.BED_Z / 2 - 0.01), (self.W + 2.2, 30, self.BED_Z), cream, bevel=0.04)   # long table under the web
        for sx in (-1, 1):
            for sy in (-1, 1):
                box('ppost', (X + sx * 3.1, py + sy * 2.9, 7.5), (0.75, 0.75, 15.0), green, bevel=0.06)
                box('ppost_foot', (X + sx * 3.1, py + sy * 2.9, 0.35), (1.3, 1.3, 0.7), steel, bevel=0.03)
                for k in range(4):
                    box('ppost_band', (X + sx * 3.1, py + sy * 2.9, 3.2 + k * 3.2), (0.82, 0.82, 0.18), steel)
        box('crown', (X, py, 15.8), (7.6, 7.0, 2.6), green, bevel=0.12)
        box('crown_cap', (X, py, 17.3), (7.0, 4.0, 0.6), steel, bevel=0.05)
        cyl('ram_housing', (X, py, 13.8), 1.3, 2.2, steel)
        self.platen = empty('platen', (X, py, 5.0))
        box('platen_block', (0, 0, 0.9), (self.SHEET_L + 0.9, self.SHEET_W + 0.9, 1.8), steel, parent=self.platen, bevel=0.05)
        box('platen_face', (0, 0, 0.02), (self.SHEET_L + 0.3, self.SHEET_W + 0.3, 0.06), H.m_rubber, parent=self.platen)
        box('platen_top', (0, 0, 2.2), (self.SHEET_L + 0.3, self.SHEET_W - 0.4, 0.8), green, parent=self.platen, bevel=0.05)
        self.ram = cyl('ram', (X, py, 9), 0.55, 8.0, H.m_reflector)
        # guide rods
        for sx in (-1, 1):
            for sy in (-1, 1):
                cyl('guide', (X + sx * 2.3, py + sy * 1.4, 8.6), 0.12, 14.0, H.m_reflector)
        # inking roller in front of the press + the ink tray
        self.ink_roller = cyl('ink_roller', (X, py - 4.6, 2.2), 0.7, self.W + 0.6, mat_ink(), rot=(0, math.pi / 2, 0))
        box('ink_tray', (X, py - 4.6, 1.3), (self.W + 1.0, 1.9, 0.5), steel, bevel=0.03)
        # cutter (guillotine) downstream
        self.CUT_Y = py + 10.0
        for s in (-1, 1):
            box('cut_col', (X + s * 3.0, self.CUT_Y, 2.4), (0.8, 1.2, 4.8), green, bevel=0.05)
        box('cut_top', (X, self.CUT_Y, 4.9), (6.8, 1.4, 0.8), green, bevel=0.05)
        self.blade = box('blade', (X, self.CUT_Y, 3.0), (self.W + 0.6, 0.12, 1.2), H.m_reflector)
        # --- sheets: a chain on the bed from R3 to beyond the cutter
        self.n_sheets = 16
        self.sheets = [obj('sheet%02d' % i, mesh_plane(), (0, 0, -500), (self.SHEET_W, self.SHEET_L, 1), (0, 0, math.pi / 2),
                           mat=self.m_blank) for i in range(self.n_sheets)]
        # --- ink rain
        self.m_ink = self.ink_roller.material_slots[0].material
        self.drops = Pool('drop', mesh_cyl('cyl8', 8), self.m_ink, 220, (0.035, 0.035, 0.5), shadow=False)
        self.splash = Pool('splash', mesh_sphere('sph8', 8, 4), self.m_ink, 60, (0.05, 0.05, 0.05), shadow=False)
        # --- sparks + steam
        self.sparks = Pool('spark', mesh_sphere('sph8', 8, 4), mat_spark(), 90, (0.035, 0.035, 0.035), shadow=False)
        self.m_steam = mat_steam()
        self.steam = Pool('steam', mesh_sphere('sph16', 16, 8), self.m_steam, 10, (1, 1, 1), shadow=False)
        for o in self.steam.obs: o.color = (0, 0, 0, 1)
        # a beam of light from the roof onto the web (the reel shot) and a key over the press
        self.shaft = light('shaft_reel', 'SPOT', (X - 3, 44, 33), 90000, (1.0, 0.62, 0.3), size=0.6, spot=math.radians(14), blend=0.4)
        look_at(self.shaft, (X, 47, 16))
        self.pkey = light('press_key', 'SPOT', (X + 6, py - 9, 14), 30000, (1.0, 0.58, 0.24), size=1.2, spot=math.radians(40), blend=0.6)
        look_at(self.pkey, (X, py, 2))
        self.rng = random.Random(3)
        self.drop_seed = [(self.rng.uniform(-2.3, 2.3), self.rng.uniform(-0.9, 0.9), self.rng.uniform(0, 1), self.rng.uniform(0.8, 1.2))
                          for _ in range(len(self.drops.obs))]
        self.slams = []
        self.visible_from = 0.0

    # press cycle: web advances one pitch in the first 45% of a half-bar, then the platen comes down on the next beat
    CYCLE = 2 * BEAT
    def web_pos(self, t):
        n = math.floor(t / self.CYCLE); u = (t % self.CYCLE) / self.CYCLE
        adv = smoother(u / 0.42)
        return (n + adv) * self.PITCH
    def platen_z(self, t):
        u = (t % self.CYCLE) / self.CYCLE   # slam at u=0.5 (on the second beat)
        top, bottom = 5.2, self.BED_Z + 0.004
        if u < 0.36: return top
        if u < 0.5: return lerp(top, bottom, ease_in((u - 0.36) / 0.14, 3))
        if u < 0.62: return bottom
        return lerp(bottom, top, smooth((u - 0.62) / 0.38))
    def slam_times(self, t0, t1):
        n0 = math.floor(t0 / self.CYCLE); out = []
        for n in range(n0, n0 + int((t1 - t0) / self.CYCLE) + 2):
            ts = n * self.CYCLE + 0.5 * self.CYCLE
            if t0 <= ts <= t1: out.append(ts)
        return out

    def update(self, t, printing=True, rain=1.0):
        X = self.X
        # reel turns with the web
        wp = self.web_pos(t)
        self.reel.rotation_euler = (wp / self.REEL_R, 0, 0)
        self.ink_roller.rotation_euler = (t * 2.0, math.pi / 2, 0)
        for w in self.webs:
            w.material_slots[0].material = self.m_blank
        self.m_blank.node_tree.nodes['scroll'].inputs['Location'].default_value = (0, -wp, 0)
        # platen
        pz = self.platen_z(t)
        self.platen.location = (X, self.PRESS_Y, pz)
        self.ram.location = (X, self.PRESS_Y, pz + 2.6 + 4.0)
        # sheets: sheet k's centre = R3 + k*pitch - offset; sheet index s = global index
        y_start = self.R3.y + self.SHEET_W / 2
        base = math.floor(wp / self.PITCH)
        frac = wp - base * self.PITCH
        slam_now = self.platen_z(t) < self.BED_Z + 0.05
        for i, ob in enumerate(self.sheets):
            k = i  # slot along the bed
            g = base - k            # global sheet id (increases as sheets are fed)
            y = y_start + k * self.PITCH + frac
            z = self.BED_Z + 0.006
            # beyond the cutter the sheets pull away faster, gap opens
            if y > self.CUT_Y:
                y = self.CUT_Y + (y - self.CUT_Y) * 1.6
            ob.location = (X, y, z)
            # printed once it has passed under the press centre (swap happens while the platen is down)
            printed = printing and (y > self.PRESS_Y + 0.05 or (abs(y - self.PRESS_Y) < 0.05 and slam_now))
            ob.material_slots[0].material = self.m_pages[PAGE_ORDER[g % 6]] if printed else self.m_blank
        # blade drops each cycle when the web is still
        u = (t % self.CYCLE) / self.CYCLE
        bz = 3.0 - 1.55 * (math.sin(math.pi * clamp((u - 0.48) / 0.16)) if 0.48 < u < 0.64 else 0)
        self.blade.location = (X, self.CUT_Y, bz)
        # ink rain: streaks fall from the dark onto the inking roller
        top_z, bot_z = 30.0, 2.9
        for i, ob in enumerate(self.drops.obs):
            dx, dy, ph, sp = self.drop_seed[i]; dx *= 0.8
            if rain <= 0 or i > len(self.drops.obs) * rain:
                ob.location = Pool.PARK; continue
            fall_t = 1.35 / sp
            u2 = ((t / fall_t) + ph) % 1.0
            z = top_z - (top_z - bot_z) * (u2 ** 1.6)
            ob.location = (X + dx, self.PRESS_Y - 4.6 + dy * 0.6, z)
            ob.scale = (0.035, 0.035, 0.25 + 0.9 * u2)
        # sparks + steam from recent slams
        self._fx(t)

    def _fx(self, t):
        X, py = self.X, self.PRESS_Y
        slams = self.slam_times(t - 1.6, t)
        rng = random.Random(11)
        si = 0
        for ts in slams:
            age = t - ts
            n_s = 30
            for j in range(n_s):
                if si >= len(self.sparks.obs): break
                ob = self.sparks.obs[si]; si += 1
                r = random.Random(int(ts * 1000) + j)
                life = r.uniform(0.35, 0.9)
                if age > life:
                    ob.location = Pool.PARK; continue
                # spray from platen edge corners outward
                side = r.choice([-1, 1])
                p0 = Vector((X + side * (self.SHEET_L / 2 + 0.6), py + r.uniform(-1.8, 1.8), self.BED_Z + 0.1))
                v = Vector((side * r.uniform(2, 7), r.uniform(-3, 3), r.uniform(2, 7)))
                p = p0 + v * age + Vector((0, 0, -9.8 * 0.5 * age * age))
                if p.z < 0.05: p.z = 0.05
                ob.location = p
                k = 1 - age / life
                ob.color = (k * k, k * k, k * k, 1)
                sp = v.length
                ob.scale = (0.03, 0.03, 0.03 + 0.05 * k)
        for j in range(si, len(self.sparks.obs)):
            self.sparks.obs[j].location = Pool.PARK
        si = 0
        for ts in self.slam_times(t - 2.4, t):
            age = t - ts
            for j in range(3):
                if si >= len(self.steam.obs): break
                ob = self.steam.obs[si]; si += 1
                r = random.Random(int(ts * 777) + j)
                side = (-1, 1, 0)[j]
                p0 = Vector((X + side * 3.0, py + r.uniform(-2, 2), self.BED_Z + 0.6))
                sz = 1.2 + 4.0 * ease_out(age / 2.4)
                ob.location = p0 + Vector((side * 1.5 * ease_out(age / 2.4), 0, 2.8 * ease_out(age / 2.4)))
                ob.scale = (sz, sz, sz * 0.8)
                d = 1.6 * (1 - age / 2.4) ** 1.5
                ob.color = (d, 0, 0, 1)
        for j in range(si, len(self.steam.obs)):
            self.steam.obs[j].location = Pool.PARK
            self.steam.obs[j].color = (0, 0, 0, 1)


def build(H):
    import sets2
    S = {}
    S['paper'] = PaperLine(H)
    P = sets2.Products()
    S['products'] = P
    S['bind'] = sets2.Bindery(H, P)
    S['gk'] = sets2.Goosklerf(H, P)
    S['tube'] = sets2.Tube(H)
    S['arms'] = sets2.Arms(H)
    S['dock'] = sets2.Dock(H, P)
    return S
