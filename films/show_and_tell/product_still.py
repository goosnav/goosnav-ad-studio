"""Product still for the end card: generic Book 2 and Goosklerf on white (Eevee, Standard view)."""
import sys, os, math
_BL = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_BL[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
sys.argv += ['--', '--format', 'lpv']
from bstudio import *   # noqa
from lowpoly import *   # noqa
from studio import config
TEX = str(config.textures()); SRC = str(config.sources())
OUT = str(config.path('work', 'show_and_tell', 'lpv', 'ov', 'products.png'))
scene = setup_scene(samples=64, bloom=(2.0, 0.0, 1.0), look='None')
scene.view_settings.view_transform = 'Standard'
scene.render.resolution_x, scene.render.resolution_y = 1400, 900
fog_world(sky_top='#FFFFFF', sky_horizon='#FFFFFF', strength=0.55, density=0.0)
box('floor', (20, 20, 0.02), mat('white', '#FFFFFF', 0.9), (0, 0, -0.01))
area('key', (-0.7, -0.8, 1.2), 1.0, 70, '#FFFFFF', (math.radians(40), 0, math.radians(-40)))
area('fill', (0.9, -0.6, 0.8), 1.5, 18, '#FFFFFF', (math.radians(55), 0, math.radians(50)))
book = product_book('book2', 1.0, TEX)
book.rotation_euler = (math.radians(76), 0, math.radians(-24))         # standing, leaning back, spine and edge showing
book.location = (-0.12, 0.06, 0.03)
gk = product_cardbox('gk', 1.4, TEX, SRC); gk.location = (0.19, -0.1, 0); gk.rotation_euler = (0, 0, math.radians(14))
for i in range(4):
    c = card(f'c{i}', TEX); c.location = (0.03 + 0.045 * i, -0.2 + 0.01 * i, 0.001 + 0.0006 * i)
    c.rotation_euler = (0, 0, math.radians(-30 + 16 * i))
pk = make_box('pack', (0.07, 0.012, 0.115), {(0, -1, 0): tex_mat('pack', os.path.join(TEX, 'gen_pack.png'), 0.3, 512)}, mat('foil', '#C8CCD4', 0.25, 0.9))
pk.location = (0.3, 0.05, 0.057); pk.rotation_euler = (math.radians(-8), 0, math.radians(-20))
cam, cd = make_camera()
cam_d = cd
aim_camera(cam, cd, (0.05, -1.25, 0.55), (0.06, 0.0, 0.1), 50)
cd.sensor_fit = 'HORIZONTAL'
scene.render.film_transparent = False
bpy.context.view_layer.update()
os.makedirs(os.path.dirname(OUT), exist_ok=True)
scene.render.filepath = OUT; bpy.ops.render.render(write_still=True)
print('PRODUCTS', OUT)
