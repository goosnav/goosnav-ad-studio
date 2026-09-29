"""Shared helpers for LIGHTS OUT: primitives, materials, easing. Everything is animated by object transforms."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler

TEX = '/home/goosnav/goosnav-sessions/B_how_it_is_made/tex/'
SODIUM = (1.0, 0.50, 0.16)
SODIUM_RED = (1.0, 0.16, 0.05)

# ------------------------------------------------------------------ easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x
def lerp(a, b, t):
    return a + (b - a) * t
def smooth(t):
    t = clamp(t); return t * t * (3 - 2 * t)
def smoother(t):
    t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10)
def ramp(t, t0, t1):
    return clamp((t - t0) / (t1 - t0)) if t1 != t0 else float(t >= t0)
def ease_in(t, p=2):
    return clamp(t) ** p
def ease_out(t, p=2):
    return 1 - (1 - clamp(t)) ** p
def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)
def keys(t, pts, ease=smooth):
    """piecewise interpolation through [(t, value), ...]; value float or tuple"""
    if t <= pts[0][0]:
        v = pts[0][1]
    elif t >= pts[-1][0]:
        v = pts[-1][1]
    else:
        for (t0, a), (t1, b) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                u = ease((t - t0) / (t1 - t0))
                if isinstance(a, (tuple, list, Vector)):
                    return Vector(a).lerp(Vector(b), u)
                return a + (b - a) * u
    return Vector(v) if isinstance(v, (tuple, list, Vector)) else v

# ------------------------------------------------------------------ collections
def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in (parent or bpy.context.scene.collection).children:
        (parent or bpy.context.scene.collection).children.link(c)
    return c

_cur = [None]
def use(c):
    _cur[0] = c
def link(ob):
    c = _cur[0] or bpy.context.scene.collection
    for u in list(ob.users_collection):
        u.objects.unlink(ob)
    c.objects.link(ob)
    return ob

# ------------------------------------------------------------------ meshes (shared, cached)
_mesh = {}
def mesh_box(name='box'):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(me); bm.free()
    _uv_box(me)
    _mesh[name] = me; return me

def _uv_box(me):
    """simple per-face planar UVs so textures land sensibly"""
    me.uv_layers.new(name='UVMap')
    uv = me.uv_layers.active.data
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if ax == 0: u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1: u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else: u, v = co.x, co.y * (1 if n.z > 0 else -1)
            uv[li].uv = (u + 0.5, v + 0.5)

def mesh_bevel_box(name, bevel=0.08, segs=2):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=segs, affect='EDGES', profile=0.5)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.use_auto_smooth = True; me.auto_smooth_angle = math.radians(40)
    _uv_box(me)
    _mesh[name] = me; return me

def mesh_cyl(name='cyl', verts=32, smooth_=True):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=0.5, radius2=0.5, depth=1.0,
                          calc_uvs=True)
    bm.to_mesh(me); bm.free()
    if smooth_:
        for p in me.polygons: p.use_smooth = True
        me.use_auto_smooth = True; me.auto_smooth_angle = math.radians(50)
    _mesh[name] = me; return me

def mesh_sphere(name='sph', seg=24, rings=12):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=0.5, calc_uvs=True)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    _mesh[name] = me; return me

def mesh_plane(name='plane'):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-.5, -.5, 0), (.5, -.5, 0), (.5, .5, 0), (-.5, .5, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name='UVMap')
    for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        me.uv_layers.active.data[i].uv = uv
    _mesh[name] = me; return me

def mesh_torus(name='torus', R=0.5, r=0.05, seg=48, rs=12):
    if name in _mesh: return _mesh[name]
    me = bpy.data.meshes.new(name)
    vs, fs = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        for j in range(rs):
            b = 2 * math.pi * j / rs
            vs.append(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
    for i in range(seg):
        for j in range(rs):
            a = i * rs + j; b = ((i + 1) % seg) * rs + j
            c = ((i + 1) % seg) * rs + (j + 1) % rs; d = i * rs + (j + 1) % rs
            fs.append((a, b, c, d))
    me.from_pydata(vs, [], fs)
    for p in me.polygons: p.use_smooth = True
    _mesh[name] = me; return me

def obj(name, me, loc=(0, 0, 0), scale=(1, 1, 1), rot=(0, 0, 0), mat=None, parent=None, shadow=True):
    ob = bpy.data.objects.new(name, me)
    link(ob)
    ob.location = loc; ob.scale = scale; ob.rotation_euler = rot
    if mat is not None:
        ob.material_slots  # noqa
        if len(me.materials) == 0:
            me.materials.append(None)
        ob.material_slots[0].link = 'OBJECT'
        ob.material_slots[0].material = mat
    if parent is not None:
        ob.parent = parent
    if not shadow:
        ob.visible_shadow = False
    return ob

def box(name, loc, size, mat, rot=(0, 0, 0), parent=None, bevel=None, shadow=True):
    me = mesh_bevel_box('bbox_%g' % bevel, bevel) if bevel else mesh_box()
    return obj(name, me, loc, size, rot, mat, parent, shadow)

def cyl(name, loc, r, h, mat, rot=(0, 0, 0), parent=None, verts=32, shadow=True):
    return obj(name, mesh_cyl('cyl%d' % verts, verts), loc, (2 * r, 2 * r, h), rot, mat, parent, shadow)

def empty(name, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, None)
    link(ob); ob.location = loc
    if parent: ob.parent = parent
    return ob

# ------------------------------------------------------------------ materials
def _nodes(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    return m, nt, nt.nodes['Material Output']

def principled(nt):
    return nt.nodes.new('ShaderNodeBsdfPrincipled')

def mat_basic(name, color, rough=0.5, metal=0.0, spec=0.5, emit=None, emit_strength=0.0):
    m, nt, out = _nodes(name)
    p = principled(nt)
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    p.inputs['Specular IOR Level'].default_value = spec
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1)
        p.inputs['Emission Strength'].default_value = emit_strength
    nt.links.new(p.outputs[0], out.inputs[0])
    return m

def mat_grimy(name, color, rough=(0.35, 0.8), metal=0.0, scale=3.0, dirt=0.35, seed=0.0, bump=0.15):
    """painted/raw surface with noise-driven dirt and roughness variation (object coords, so it tiles on any size)"""
    m, nt, out = _nodes(name)
    L = nt.links
    p = principled(nt)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Location'].default_value = (seed, seed * 1.7, 0)
    L.new(tc.outputs['Generated' if False else 'Object'], mp.inputs[0])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale
    nz.inputs['Detail'].default_value = 8; nz.inputs['Roughness'].default_value = 0.6
    L.new(mp.outputs[0], nz.inputs[0])
    cr = nt.nodes.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].position = 0.35; cr.color_ramp.elements[1].position = 0.75
    L.new(nz.outputs['Fac'], cr.inputs[0])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    mix.inputs[6].default_value = (*[c * (1 - dirt) for c in color], 1)
    mix.inputs[7].default_value = (*color, 1)
    L.new(cr.outputs[0], mix.inputs[0])
    L.new(mix.outputs[2], p.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange')
    rr.inputs['To Min'].default_value = rough[0]; rr.inputs['To Max'].default_value = rough[1]
    L.new(cr.outputs[0], rr.inputs[0])
    L.new(rr.outputs[0], p.inputs['Roughness'])
    p.inputs['Metallic'].default_value = metal
    if bump:
        nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = scale * 12
        L.new(mp.outputs[0], nz2.inputs[0])
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.02
        L.new(nz2.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs[0], p.inputs['Normal'])
    L.new(p.outputs[0], out.inputs[0])
    return m

def mat_image(name, path, rough=0.6, emit=0.0, alpha=False, backface=None, spec=0.3, interp='Cubic', sat=1.0):
    """image-textured material; optional flat 'backface' colour for two-sided paper, optional alpha clip"""
    m, nt, out = _nodes(name)
    L = nt.links
    p = principled(nt)
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(path, check_existing=True)
    tx.interpolation = interp
    tx.extension = 'CLIP' if alpha else 'EXTEND'
    col = tx.outputs['Color']
    L.new(col, p.inputs['Base Color'])
    p.inputs['Roughness'].default_value = rough
    p.inputs['Specular IOR Level'].default_value = spec
    if emit:
        L.new(col, p.inputs['Emission Color']); p.inputs['Emission Strength'].default_value = emit
    shader = p.outputs[0]
    if backface is not None:
        p2 = principled(nt)
        p2.inputs['Base Color'].default_value = (*backface, 1)
        p2.inputs['Roughness'].default_value = rough
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        mx = nt.nodes.new('ShaderNodeMixShader')
        L.new(geo.outputs['Backfacing'], mx.inputs[0])
        L.new(p.outputs[0], mx.inputs[1]); L.new(p2.outputs[0], mx.inputs[2])
        shader = mx.outputs[0]
    if alpha:
        L.new(tx.outputs['Alpha'], p.inputs['Alpha'])
        m.blend_method = 'CLIP'; m.shadow_method = 'CLIP'; m.alpha_threshold = 0.5
    L.new(shader, out.inputs[0])
    return m

def mat_emit(name, color, strength=5.0, objcolor=False):
    """pure emission; with objcolor=True the emission is scaled by the object's colour (animate ob.color)"""
    m, nt, out = _nodes(name)
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*color, 1)
    e.inputs['Strength'].default_value = strength
    if objcolor:
        oi = nt.nodes.new('ShaderNodeObjectInfo')
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
        mul.inputs[0].default_value = 1.0
        mul.inputs[6].default_value = (*color, 1)
        nt.links.new(oi.outputs['Color'], mul.inputs[7])
        nt.links.new(mul.outputs[2], e.inputs['Color'])
    nt.links.new(e.outputs[0], out.inputs[0])
    return m

def mat_glow_objcolor(name, base=(0.05, 0.05, 0.05), rough=0.4, strength=20.0):
    """a surface that glows by ob.color (rgb = emission colour, alpha unused). Black ob.color = unlit."""
    m, nt, out = _nodes(name)
    p = principled(nt)
    p.inputs['Base Color'].default_value = (*base, 1)
    p.inputs['Roughness'].default_value = rough
    oi = nt.nodes.new('ShaderNodeObjectInfo')
    nt.links.new(oi.outputs['Color'], p.inputs['Emission Color'])
    p.inputs['Emission Strength'].default_value = strength
    nt.links.new(p.outputs[0], out.inputs[0])
    return m

def mat_glass(name, tint=(0.9, 0.95, 1.0), rough=0.05, alpha=0.15):
    m, nt, out = _nodes(name)
    p = principled(nt)
    p.inputs['Base Color'].default_value = (*tint, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Alpha'].default_value = alpha
    p.inputs['Specular IOR Level'].default_value = 1.0
    m.blend_method = 'BLEND'; m.shadow_method = 'NONE'; m.show_transparent_back = False
    m.use_screen_refraction = False
    nt.links.new(p.outputs[0], out.inputs[0])
    return m

def mat_volume(name, density=0.01, color=(1, 1, 1), aniso=0.4):
    m, nt, out = _nodes(name)
    v = nt.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = density
    v.inputs['Color'].default_value = (*color, 1)
    v.inputs['Anisotropy'].default_value = aniso
    nt.links.new(v.outputs[0], out.inputs['Volume'])
    return m

# ------------------------------------------------------------------ lights
def light(name, kind, loc, energy, color=SODIUM, size=0.2, spot=None, blend=0.3, rot=(0, 0, 0), shadow=True,
          parent=None, vol=1.0, spec=1.0):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy; ld.color = color
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    if kind == 'SPOT':
        ld.spot_size = spot or math.radians(60); ld.spot_blend = blend
    if kind == 'AREA':
        ld.size = size
    if kind == 'SUN':
        ld.angle = size
    ld.use_shadow = shadow
    ld.volume_factor = vol
    ld.specular_factor = spec
    ob = bpy.data.objects.new(name, ld)
    link(ob); ob.location = loc; ob.rotation_euler = rot
    if parent: ob.parent = parent
    return ob

def look_at(ob, target, roll=0.0):
    d = Vector(target) - Vector(ob.location)
    q = d.to_track_quat('-Z', 'Y')
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = q @ Matrix.Rotation(roll, 4, 'Z').to_quaternion()
