"""LIGHTS OUT — a Goosnav industrial film. One Blender scene, driven by update(t).
blender -b --factory-startup -P film.py -- [--start F] [--end F] [--step N] [--preview] [--still T ...] [--out DIR]"""
import bpy, sys, os, math, time, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib, lib, hall, sets
for m in (lib, hall, sets):
    importlib.reload(m)
from lib import *
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
DUR = 90.0
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None, cast=str):
    if name in argv:
        return cast(argv[argv.index(name) + 1])
    return default
PREVIEW = '--preview' in argv
RES = arg('--res', 0.5 if PREVIEW else 1.0, float)
SAMPLES = arg('--samples', 8 if PREVIEW else 12, int)
OUT = arg('--out', os.path.join(HERE, 'prev' if PREVIEW else 'frames'))
BLUR = '--blur' in argv or (not PREVIEW and '--noblur' not in argv)

# ------------------------------------------------------------------ scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
PORTRAIT = '--portrait' in argv
os.environ['LO_PORTRAIT'] = '1' if PORTRAIT else ''
if PORTRAIT:
    sc.render.resolution_x = int(1080 * RES); sc.render.resolution_y = int(1350 * RES)
else:
    sc.render.resolution_x = int(1920 * RES); sc.render.resolution_y = int(1080 * RES)
sc.render.resolution_percentage = 100
sc.render.fps = FPS
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '8'
sc.render.film_transparent = False
ee = sc.eevee
ee.taa_render_samples = SAMPLES
ee.use_gtao = True; ee.gtao_distance = 1.5; ee.gtao_factor = 1.2
ee.use_bloom = True; ee.bloom_threshold = 1.2; ee.bloom_intensity = 0.06; ee.bloom_radius = 6.5
ee.bloom_color = (1.0, 0.8, 0.6)
ee.use_ssr = True; ee.use_ssr_halfres = True; ee.ssr_thickness = 0.3; ee.ssr_max_roughness = 0.35
ee.use_soft_shadows = True
ee.shadow_cube_size = '1024'; ee.shadow_cascade_size = '4096'
ee.use_shadow_high_bitdepth = True
ee.use_volumetric_lights = True; ee.use_volumetric_shadows = True
ee.volumetric_tile_size = '16'; ee.volumetric_samples = 64; ee.volumetric_start = 0.5; ee.volumetric_end = 260
ee.volumetric_light_clamp = 0.0; ee.volumetric_shadow_samples = 16
ee.light_threshold = 0.02
ee.use_motion_blur = BLUR; ee.motion_blur_shutter = 0.3; ee.motion_blur_steps = 2
for kv in os.environ.get('EEV', '').split(';'):
    if kv:
        k, v = kv.split('=')
        setattr(ee, k, type(getattr(ee, k))(v) if not isinstance(getattr(ee, k), str) else v)
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.view_settings.exposure = 0.0
world = bpy.data.worlds.new('W'); sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1); bg.inputs[1].default_value = 0.0

cam_data = bpy.data.cameras.new('cam'); cam_data.sensor_width = 36
cam = bpy.data.objects.new('cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
cam_data.clip_start = 0.02; cam_data.clip_end = 900

H = hall.Hall()
S = sets.build(H)
import builtins; builtins.film_H = H; builtins.film_S = S

# ------------------------------------------------------------------ timeline
import timeline
importlib.reload(timeline)
T = timeline.T

def update(t):
    timeline.update(t, sc, cam, H, S)

def frame_handler(scene, depsgraph=None):
    # motion blur samples subframes around the frame: keep them inside this frame's shot so nothing smears across a cut
    base = scene.frame_current / FPS
    t = (scene.frame_current + scene.frame_subframe) / FPS
    starts = [s[0] for s in timeline.SHOTS] + [DUR + 10]
    for a, b in zip(starts, starts[1:]):
        if a <= base < b:
            t = min(max(t, a), b - 1e-4)
            break
    update(t)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    stills = None
    if '--still' in argv:
        stills = []
        for x in argv[argv.index('--still') + 1:]:
            if x.startswith('--'): break
            stills.append(float(x))
    bpy.app.handlers.frame_change_pre.clear()
    if BLUR:
        bpy.app.handlers.frame_change_pre.append(frame_handler)
    t_start = time.time()
    if stills is not None:
        tag = arg('--tag', 's')
        for ts in stills:
            f = int(round(ts * FPS))
            sc.frame_set(f); update(f / FPS); bpy.context.view_layer.update()
            sc.render.filepath = os.path.join(OUT, '%s_%06.2f.png' % (tag, ts))
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print('STILL %.2f %.1fs' % (ts, time.time() - t0), flush=True)
    else:
        start = arg('--start', 0, int); end = arg('--end', int(DUR * FPS) - 1, int); step = arg('--step', 1, int)
        resume = '--resume' in argv
        flist = range(start, end + 1, step)
        if '--frames' in argv:
            flist = [int(x) for x in argv[argv.index('--frames') + 1].split(',')]
        for f in flist:
            path = os.path.join(OUT, 'f_%05d.png' % f)
            if resume and os.path.exists(path):
                continue
            sc.frame_set(f); update(f / FPS); bpy.context.view_layer.update()
            sc.render.filepath = path
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print('FRAME %d %.1fs' % (f, time.time() - t0), flush=True)
    print('DONE %.1fs' % (time.time() - t_start))
