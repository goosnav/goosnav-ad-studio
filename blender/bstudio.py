"""bstudio: the reusable Blender (Eevee) layer of goosnav-ad-studio.

A film is one Python file that builds a scene and exposes update(t) -> black(bool). This module
supplies everything else: CLI flags, output formats, scene/render setup, materials, geometry,
object-pool sheets (paper, cards), camera helpers and the render loop.

    import sys, os; sys.path.insert(0, <repo>/blender)
    from bstudio import *
    scene = setup_scene()
    ... build ...
    run(update, dur=90.0)

Hard-won rules baked in here (see PLAYBOOK.md):
  * animate with object transforms only (mesh edits between batch renders render stale in Eevee)
  * one render process at a time; wrap the blender call in flock <render_lock>
  * motion blur via a frame_change_pre handler; re-render hard-cut frames without blur
"""
import bpy, bmesh, math, sys, os, json, time
import numpy as np
from mathutils import Vector, Matrix

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
from studio import config  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None, cast=str):
    if name in argv:
        return cast(argv[argv.index(name) + 1])
    return default
def flag(name):
    return name in argv

PREVIEW = flag('--preview')
FORMAT = arg('--format', '16x9')
FULL_W, FULL_H, LENS_SCALE = config.FORMATS[FORMAT]
W, H = (FULL_W // 2, FULL_H // 2) if PREVIEW else (FULL_W, FULL_H)
PORTRAIT = FULL_H > FULL_W
RNG = np.random.default_rng(0)

def set_rng(r):
    """share the film's generator so object pools draw from the same random sequence"""
    global RNG
    RNG = r

def ss(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)
def sm(a, b, x):  # smootherstep
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)
def lerp(a, b, t):
    return a + (b - a) * t
def v3(*a):
    return np.array(a, float)
def norm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)

HIDE = v3(0, 0, -500)

# ---------------------------------------------------------------- scene
def setup_scene(fps=24, samples=20, bloom=(1.0, 0.06, 6.5), look='AgX - Medium High Contrast'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.fps = fps
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    ee = scene.eevee
    ee.taa_render_samples = 6 if PREVIEW else int(arg('--samples', samples))
    ee.use_bloom = True
    ee.bloom_threshold, ee.bloom_intensity, ee.bloom_radius = bloom
    ee.use_gtao = True
    ee.gtao_distance = 3.0
    ee.use_soft_shadows = True
    ee.shadow_cascade_size = '4096'
    ee.shadow_cube_size = '1024'
    ee.use_ssr = False
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = look
    except Exception:
        pass
    return scene

# ---------------------------------------------------------------- materials
def img(path):
    return bpy.data.images.load(path, check_existing=True)

def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    return m, nt, out

def mat_color(name, rgb, rough=0.6, metal=0.0, emit=None, emit_strength=0.0):
    m, nt, out = new_mat(name)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = emit_strength
    nt.links.new(b.outputs[0], out.inputs[0])
    return m

def mat_image(name, path, rough=0.5, spec=0.3, coat=0.0):
    m, nt, out = new_mat(name)
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = img(path); t.interpolation = 'Cubic'
    t.extension = 'EXTEND'
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    b.inputs['Coat Weight'].default_value = coat
    nt.links.new(t.outputs[0], b.inputs['Base Color'])
    nt.links.new(b.outputs[0], out.inputs[0])
    return m

def mat_two_sided(name, front, back, rough=0.75, translucent=0.18, gloss=0.25, glow=0.22, alpha=False):
    """front image seen from the -Y side of a sheet, back image (mirrored UV) from +Y side."""
    m, nt, out = new_mat(name)
    uv = nt.nodes.new('ShaderNodeUVMap')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Location'].default_value = (1, 0, 0)
    mp.inputs['Scale'].default_value = (-1, 1, 1)
    nt.links.new(uv.outputs[0], mp.inputs[0])
    tf = nt.nodes.new('ShaderNodeTexImage'); tf.image = img(front); tf.extension = 'EXTEND'
    tb = nt.nodes.new('ShaderNodeTexImage'); tb.image = img(back); tb.extension = 'EXTEND'
    nt.links.new(uv.outputs[0], tf.inputs[0])
    nt.links.new(mp.outputs[0], tb.inputs[0])
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    nt.links.new(geo.outputs['Backfacing'], mix.inputs['Factor'])
    nt.links.new(tf.outputs[0], mix.inputs[6])
    nt.links.new(tb.outputs[0], mix.inputs[7])
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = gloss
    nt.links.new(mix.outputs[2], b.inputs['Base Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(mix.outputs[2], tr.inputs['Color'])
    ms = nt.nodes.new('ShaderNodeMixShader')
    ms.inputs[0].default_value = translucent
    nt.links.new(b.outputs[0], ms.inputs[1])
    nt.links.new(tr.outputs[0], ms.inputs[2])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs[1].default_value = glow
    nt.links.new(mix.outputs[2], em.inputs[0])
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(ms.outputs[0], add.inputs[0]); nt.links.new(em.outputs[0], add.inputs[1])
    if alpha:  # rounded corners: cut out by the image alpha
        tp = nt.nodes.new('ShaderNodeBsdfTransparent')
        mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tf.outputs['Alpha'], mx.inputs[0])
        nt.links.new(tp.outputs[0], mx.inputs[1]); nt.links.new(add.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs[0])
        m.blend_method = 'CLIP'; m.shadow_method = 'CLIP'; m.alpha_threshold = 0.5
    else:
        nt.links.new(add.outputs[0], out.inputs[0])
    m.use_backface_culling = False
    return m

def mat_emit(name, rgb, strength, alpha_blend=False):
    m, nt, out = new_mat(name)
    e = nt.nodes.new('ShaderNodeEmission')
    e.inputs[0].default_value = (*rgb, 1)
    e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0])
    return m

# ---------------------------------------------------------------- geometry helpers
def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj

UV_AXES = {  # face normal -> (u axis, v axis)
    (0, -1, 0): ((1, 0, 0), (0, 0, 1)), (0, 1, 0): ((-1, 0, 0), (0, 0, 1)),
    (-1, 0, 0): ((0, -1, 0), (0, 0, 1)), (1, 0, 0): ((0, 1, 0), (0, 0, 1)),
    (0, 0, 1): ((1, 0, 0), (0, 1, 0)), (0, 0, -1): ((1, 0, 0), (0, -1, 0)),
}

def make_box(name, size, face_mats, default_mat, bevel=0.0):
    """Box centered at origin. face_mats: {normal tuple: material}; each face UV'd 0..1."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    uvl = bm.loops.layers.uv.new('UVMap')
    mats = [default_mat] + [m for m in face_mats.values() if m is not None]
    for f in bm.faces:
        n = tuple(int(round(c)) for c in f.normal)
        ua, va = UV_AXES[n]
        us = [v.co.dot(Vector(ua)) for v in f.verts]; vs = [v.co.dot(Vector(va)) for v in f.verts]
        for loop in f.loops:
            u = (loop.vert.co.dot(Vector(ua)) - min(us)) / (max(us) - min(us))
            v = (loop.vert.co.dot(Vector(va)) - min(vs)) / (max(vs) - min(vs))
            loop[uvl].uv = (u, v)
        f.material_index = mats.index(face_mats[n]) if n in face_mats else 0
    bm.to_mesh(me); bm.free()
    for m in mats:
        me.materials.append(m)
    ob = link(bpy.data.objects.new(name, me))
    if bevel > 0:
        md = ob.modifiers.new('bevel', 'BEVEL'); md.width = bevel; md.segments = 3
        md.harden_normals = True
        me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(40)
    return ob

def look_at_quat(eye, target, roll=0.0):
    d = Vector(target) - Vector(eye)
    q = d.to_track_quat('-Z', 'Y')
    if roll:
        q = q @ Matrix.Rotation(roll, 4, 'Z').to_quaternion()
    return q

def frames_from(normal, up):
    """Rotation matrices (n,3,3) whose local -Y maps to `normal` and local +Z towards `up`."""
    N = norm(normal); U = norm(up)
    X = norm(np.cross(U, N))
    Y = -N
    Z = np.cross(X, Y)
    return np.stack([X, Y, Z], axis=-1)

def rot_axis(axis, ang):
    """Rodrigues, vectorized: axis (n,3), ang (n,) -> (n,3,3)"""
    a = norm(axis); c = np.cos(ang)[:, None, None]; s = np.sin(ang)[:, None, None]
    K = np.zeros(a.shape[:-1] + (3, 3))
    K[..., 0, 1] = -a[..., 2]; K[..., 0, 2] = a[..., 1]; K[..., 1, 0] = a[..., 2]
    K[..., 1, 2] = -a[..., 0]; K[..., 2, 0] = -a[..., 1]; K[..., 2, 1] = a[..., 0]
    I = np.eye(3)[None]
    return I + s * K + (1 - c) * (K @ K)

def euler_mats(e):
    """e (n,3) XYZ euler -> (n,3,3)"""
    cx, cy, cz = np.cos(e[:, 0]), np.cos(e[:, 1]), np.cos(e[:, 2])
    sx, sy, sz = np.sin(e[:, 0]), np.sin(e[:, 1]), np.sin(e[:, 2])
    R = np.empty((len(e), 3, 3))
    R[:, 0, 0] = cy * cz; R[:, 0, 1] = sx * sy * cz - cx * sz; R[:, 0, 2] = cx * sy * cz + sx * sz
    R[:, 1, 0] = cy * sz; R[:, 1, 1] = sx * sy * sz + cx * cz; R[:, 1, 2] = cx * sy * sz - sx * cz
    R[:, 2, 0] = -sy; R[:, 2, 1] = sx * cy; R[:, 2, 2] = cx * cy
    return R

class Sheets:
    """A pool of thin rectangular sheets. Each sheet is its own object sharing one of a few
    pre-curled meshes per material; motion is written as object transforms each frame."""
    CURLS = (-0.22, 0.0, 0.22)
    _cache = {}

    @staticmethod
    def sheet_mesh(w, h, nx, nz, curl, mat):
        key = (w, h, nx, nz, curl, mat.name)
        if key in Sheets._cache:
            return Sheets._cache[key]
        xs = np.linspace(-w / 2, w / 2, nx + 1); zs = np.linspace(-h / 2, h / 2, nz + 1)
        gx, gz = np.meshgrid(xs, zs)
        gy = curl * (gx / (w / 2)) ** 2 * w * 0.25
        verts = np.stack([gx.ravel(), gy.ravel(), gz.ravel()], -1)
        uv = np.stack([(gx.ravel() + w / 2) / w, (gz.ravel() + h / 2) / h], -1)
        faces = []
        for j in range(nz):
            for i in range(nx):
                a = j * (nx + 1) + i
                faces.append((a, a + 1, a + nx + 2, a + nx + 1))
        me = bpy.data.meshes.new('sheet')
        me.from_pydata(verts.tolist(), [], faces)
        me.update()
        uvl = me.uv_layers.new(name='UVMap')
        uvl.data.foreach_set('uv', np.array([uv[v] for f in faces for v in f]).ravel())
        me.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
        me.materials.append(mat)
        Sheets._cache[key] = me
        return me

    def __init__(self, name, n, w, h, mats, mat_ids, nx=6, nz=5, thickness=0.0, curl_ids=None):
        self.n, self.w, self.h = n, w, h
        if curl_ids is None:
            curl_ids = RNG.integers(0, 3, n)
        self.obs = []
        for i in range(n):
            me = Sheets.sheet_mesh(w, h, nx, nz, Sheets.CURLS[int(curl_ids[i])], mats[int(mat_ids[i])])
            ob = link(bpy.data.objects.new(f'{name}{i:03d}', me))
            self.obs.append(ob)
        self.ob = self.obs[0]

    def set(self, pos, R, curl=None, scale=None, wave=None):
        M = np.zeros((self.n, 4, 4)); M[:, 3, 3] = 1
        Rs = R if scale is None else R * scale[:, None, None]
        M[:, :3, :3] = Rs; M[:, :3, 3] = pos
        for ob, m in zip(self.obs, M):
            ob.matrix_world = Matrix(m.tolist())


def shake(t, amp, freq=1.0):
    return amp * v3(math.sin(t * 13.1 * freq) * 0.6 + math.sin(t * 29.7 * freq + 1.3) * 0.4,
                    math.sin(t * 11.3 * freq + 2.1) * 0.5 + math.sin(t * 23.9 * freq) * 0.5,
                    math.sin(t * 17.9 * freq + 0.7) * 0.6 + math.sin(t * 31.3 * freq + 2.4) * 0.4)
def sway(t, amp):
    return amp * v3(math.sin(t * 0.61) + 0.4 * math.sin(t * 1.37), 0.5 * math.sin(t * 0.47), math.sin(t * 0.83 + 1) * 0.6)

# ---------------------------------------------------------------- camera
def make_camera(clip_end=3000):
    scene = bpy.context.scene
    cam_d = bpy.data.cameras.new('cam'); cam_d.sensor_width = 36
    cam_d.clip_start = 0.05; cam_d.clip_end = clip_end
    cam = link(bpy.data.objects.new('cam', cam_d)); scene.camera = cam
    cam.rotation_mode = 'QUATERNION'
    return cam, cam_d

def aim_camera(cam, cam_d, eye, tgt, lens, roll=0.0):
    """lens is authored for 16:9; LENS_SCALE keeps the horizontal framing in other formats"""
    cam.location = Vector(eye)
    cam.rotation_quaternion = look_at_quat(eye, tgt, roll)
    cam_d.lens = lens * LENS_SCALE

# ---------------------------------------------------------------- render loop
def run(update, dur, fps=24, out=None, events=None):
    """flags: --out DIR --start F --end F --step N --times t1,t2 --resume --mblur [--shutter S --mbsteps N]
              --cuts f1,f2 (frames rendered without motion blur) --preview --format 16x9|4x5|1x1|9x16"""
    scene = bpy.context.scene
    out = arg('--out', out)
    os.makedirs(out, exist_ok=True)
    cuts = set(int(x) for x in arg('--cuts', '').split(',') if x)
    mblur = flag('--mblur')
    def on_frame(scn, depsgraph=None):
        update((scn.frame_current + scn.frame_subframe) / fps)
    if mblur:
        scene.eevee.motion_blur_shutter = float(arg('--shutter', 0.25, float))
        scene.eevee.motion_blur_steps = int(arg('--mbsteps', 3, int))
        bpy.app.handlers.frame_change_pre.append(on_frame)
    if events:
        events()
    times = arg('--times')
    if times:
        todo = [(float(x), None, f'{out}/t_{float(x):06.2f}.png') for x in times.split(',')]
    else:
        s = int(arg('--start', 0, int)); e = int(arg('--end', int(dur * fps) - 1, int)); st = int(arg('--step', 1, int))
        todo = [(f / fps, f, f'{out}/f_{f:05d}.png') for f in range(s, e + 1, st)]
    for t, f, path in todo:
        if flag('--resume') and os.path.exists(path):
            continue
        t0 = time.time()
        black = update(t)
        blur_here = mblur and f is not None and f not in cuts
        scene.eevee.use_motion_blur = blur_here
        if blur_here:
            scene.frame_set(f)
        scene.render.filepath = path
        if black:
            im = bpy.data.images.new('blk', scene.render.resolution_x, scene.render.resolution_y)
            im.pixels.foreach_set(np.tile(np.array([0, 0, 0, 1], np.float32), scene.render.resolution_x * scene.render.resolution_y))
            im.filepath_raw = path; im.file_format = 'PNG'; im.save(); bpy.data.images.remove(im)
        else:
            bpy.context.view_layer.update()
            bpy.ops.render.render(write_still=True)
        print(f'FRAME {path} t={t:.2f} {time.time() - t0:.1f}s', flush=True)
