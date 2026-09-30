"""Three Brags: three house low-poly actors in an impossible desert."""
import json
import math
import os
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector

_script = [sys.argv[index + 1] for index, value in enumerate(sys.argv) if value == '-P'] or [__file__]
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(_script[0]))))
sys.path.insert(0, os.path.join(REPO, 'blender'))
from bstudio import *
from lowpoly import *
from studio import config

FILM = 'three_brags'
FPS = 24
DUR = 26.0
END_SCENE = 22.0
EXPLODE = 17.90
WORK = str(config.path('work', FILM, FORMAT))
VO = str(config.path('work', FILM, 'vo'))
TEX = str(config.textures())
VO_AT = {'01': 5.65, '02': 10.10, '03': 15.15}
SPEAKER = {'01': 'CARD', '02': 'BOOK', '03': 'BOMB'}
CUTS = [2.8, 4.5, 5.6, 9.45, 15.0, EXPLODE, 18.15, END_SCENE]

scene = setup_scene(fps=FPS, samples=20, bloom=(1.1, 0.07, 5.0), look='AgX - Medium High Contrast')
if not PREVIEW:
    scene.render.resolution_x = 540
    scene.render.resolution_y = 675
scene.view_settings.exposure = 0.30
fog_world(sky_top='#706477', sky_horizon='#E7B99A', strength=0.9, density=0.0006)

SAND = mat('ochre sand', '#BDA78C', 0.95, noise=0.16, noise_scale=0.11)
SAND_DARK = mat('dune shade', '#8F806B', 0.98)
OBSIDIAN = [mat(f'obsidian_{index}', shade, 0.82) for index, shade in enumerate(('#090B0C', '#151719', '#252628'))]
SMOKE = [mat(f'smoke_{index}', shade, 0.95) for index, shade in enumerate(('#151515', '#302A28', '#4D4138', '#766557', '#B09A7C'))]
FIRE = mat('furnace orange', '#FA5B12', 0.45, emit=5)
FLASH = mat('white flash', '#FFF3D7', 0.45, emit=15)
BOOK_BLUE = mat('book blue', '#0033A0', 0.55)
PACK_PURPLE = mat('card pack purple', '#330072', 0.55)

# One giant patterned ground mesh, flat where the cast stands and subtly ridged to infinity.
grid = 56
span = 760.0
vertices = []
faces = []
for row in range(grid + 1):
    yy = (row / grid - .5) * span
    for col in range(grid + 1):
        xx = (col / grid - .5) * span
        dist = math.hypot(xx, yy)
        flatten = min(1, max(0, (dist - 9) / 25))
        height = flatten * (.48 * math.sin(xx * .075 + yy * .025) + .34 * math.sin(yy * .12 - xx * .035))
        vertices.append((xx, yy, height))
for row in range(grid):
    for col in range(grid):
        index = row * (grid + 1) + col
        faces.append((index, index + 1, index + grid + 2, index + grid + 1))
ground_mesh = bpy.data.meshes.new('infinite desert')
ground_mesh.from_pydata(vertices, [], faces)
ground_mesh.materials.append(SAND)
ground_mesh.update()
ground = link(bpy.data.objects.new('infinite desert plane', ground_mesh))


def pyramid(name, center, width, height):
    x, y = center
    vertices = [(-width / 2, -width / 2, 0), (width / 2, -width / 2, 0),
                (width / 2, width / 2, 0), (-width / 2, width / 2, 0), (0, 0, height)]
    faces = [(0, 1, 2, 3), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for material in OBSIDIAN:
        mesh.materials.append(material)
    mesh.update()
    ob = link(bpy.data.objects.new(name, mesh))
    ob.location = (x, y, -.15)
    for index, polygon in enumerate(mesh.polygons):
        polygon.material_index = (index + 1) % len(OBSIDIAN)
    return ob


pyramid('western pyramid', (-28, 51), 28, 30)
pyramid('eastern pyramid', (30, 64), 34, 40)
pyramid('distant black pyramid', (0, 108), 58, 53)
pyramid('far western pyramid', (-103, 172), 64, 55)

key = sun(energy=3.3, color='#FBE6C7', elev=26, azim=-35, angle=2.0)
key.data.shadow_cascade_max_distance = 130
fill = sun(energy=0.65, color='#B4B5D8', elev=48, azim=132, angle=10)
fill.data.use_shadow = False
point('cast bounce', (0, -5, 6), 650, '#FFD9B5', 7)
blast_light = point('explosion light', (1.5, 0, 3), 0, '#FFB66C', 3)

# Claude's house rig: faceted heads, readable eyes and brows, hinged arms, jaw-flap speech.
card_actor = Human('card braggart', skin=SKIN[1], top='#535F5B', legs='#302E30', hair='#262A2D',
                   height=1.78, build=.95, hair_style='short', glasses=True)
book_actor = Human('book braggart', skin=SKIN[0], top='#7F746E', legs='#3E4040', hair='#4E3228',
                   height=1.91, build=.84, hair_style='long')
bomb_actor = Human('bomb braggart', skin=SKIN[2], top='#373B38', legs='#222629', hair='#161616',
                   height=1.69, build=1.12, hair_style='bald')
actors = (card_actor, book_actor, bomb_actor)
places = (-1.55, 0.0, 1.55)

deck_face = tex_mat('real hand-drawn Goosklerf pack', os.path.join(TEX, 'gen_pack.png'), size=512, emit=.18)
book_face = tex_mat('Goosnav Book 2 front', os.path.join(TEX, 'gen_book_front.png'), size=512, emit=.18)


def held_box(name, actor, dimensions, face, side):
    root = empty(f'{name} grip root', parent=actor.grip('R'))
    body = make_box(name, dimensions, {(0, -1, 0): face}, side)
    body.parent = root
    body.location = (0, -.04, -.17)
    root.rotation_euler.x = math.pi
    return root


deck = held_box('Goosklerf training deck', card_actor, (.28, .055, .39), deck_face, PACK_PURPLE)
book = held_box('Goosnav Book 2', book_actor, (.47, .062, .36), book_face, BOOK_BLUE)

bomb_root = empty('cartoon bomb grip root', parent=bomb_actor.grip('R'))
bomb_ball = ball('cartoon black bomb', .24, OBSIDIAN[0], seg=12, rings=8, loc=(0, -.04, -.16), parent=bomb_root)
cyl('bomb fuse collar', .05, .06, OBSIDIAN[2], 8, (0, -.04, -.40), bomb_root)
fuse = cyl('bomb fuse', .017, .15, SAND_DARK, 6, (0, -.04, -.51), bomb_root)
spark = ball('fuse spark', .058, FIRE, 8, 5, loc=(0, -.04, -.62), parent=bomb_root)

# Prebuilt faceted cloud and fragments. Only transforms change during rendering.
rng = np.random.default_rng(20260930)
cloud = []
for index in range(104):
    mesh = bpy.data.meshes.new(f'cloud mesh {index}')
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(SMOKE[index % len(SMOKE)])
    ob = link(bpy.data.objects.new(f'cloud lobe {index}', mesh))
    angle = rng.uniform(0, 2 * math.pi)
    radius = rng.uniform(.0, 1.0)
    spread = rng.uniform(.8, 1.3)
    size = rng.uniform(.65, 2.45)
    cloud.append((ob, angle, radius, spread, size, index % 5))

cloud_core = []
for index, (height, width, depth, material) in enumerate([
    (2.8, 3.3, 3.3, SMOKE[1]),
    (6.2, 3.8, 4.1, SMOKE[0]),
    (10.2, 3.1, 4.2, SMOKE[1]),
    (13.8, 4.3, 4.2, SMOKE[2]),
    (17.1, 8.6, 5.3, SMOKE[0]),
    (19.2, 10.3, 5.7, SMOKE[2]),
    (20.5, 7.4, 5.2, SMOKE[3]),
]):
    ob = ball(f'mushroom cloud core {index}', 1, material, seg=12, rings=8)
    cloud_core.append((ob, height, width, depth))

debris = []
for index in range(96):
    length = rng.uniform(.12, .63)
    ob = box(f'black debris {index}', (length, .08, .10), OBSIDIAN[index % 3])
    angle = rng.uniform(0, 2 * math.pi)
    speed = rng.uniform(3, 12)
    height = rng.uniform(2, 10)
    debris.append((ob, angle, speed, height, rng.uniform(0, 6)))

shock = []
for index in range(3):
    bpy.ops.mesh.primitive_torus_add(major_segments=48, minor_segments=5, location=(1.55, 0, .15))
    ob = bpy.context.object
    ob.name = f'dust shockwave {index}'
    ob.data.materials.append(SMOKE[3 + index % 2])
    shock.append(ob)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=(1.55, 0, 2.4))
flash = bpy.context.object
flash.name = 'instant white explosion'
flash.data.materials.append(FLASH)

lines = Lines([(SPEAKER[key], time, os.path.join(VO, f'vo_{key}.wav')) for key, time in VO_AT.items()], FPS)
camera, camera_data = make_camera(clip_end=1200)


def smooth(a, b, t):
    return float(ss(a, b, t))


def actor_animation(t):
    beat = math.floor(t * 12) / 12
    for index, actor in enumerate(actors):
        actor.place((places[index], 0, 0), yaw=0)
        actor.pose({})
        actor.idle(beat, .8)
        actor.blink(t, index + 2)
        actor.talk(lines.amount(('CARD', 'BOOK', 'BOMB')[index], t))
    raise_card = smooth(5.65, 6.8, beat)
    spin_card = smooth(7.30, 9.15, beat)
    card_actor.root.rotation_euler.z = 2 * math.pi * spin_card
    card_actor.add({'uarm_R': (-2.68 * raise_card, 0, -.10), 'farm_R': (-.46 * raise_card, 0, 0),
                    'uarm_L': (-.35 * raise_card, 0, .55 * raise_card),
                    'head': (-.15 * raise_card, 0, -.12 * raise_card)})
    card_actor.root.location.z = .05 * abs(math.sin(spin_card * 2 * math.pi))
    if 9.3 < t < 15.0:
        card_actor.look(yaw=-.18)

    raise_book = smooth(10.05, 11.35, beat)
    spin_book = smooth(11.70, 14.75, beat)
    chaotic = math.sin(spin_book * 5 * math.pi)
    book_actor.root.rotation_euler = (.13 * chaotic * spin_book, .20 * math.sin(spin_book * 4 * math.pi) * spin_book,
                                      spin_book * 5 * math.pi + .17 * chaotic)
    book_actor.root.location = (0.28 * math.sin(spin_book * 5 * math.pi),
                                .25 * math.sin(spin_book * 4 * math.pi),
                                .08 * abs(math.sin(spin_book * 7 * math.pi)))
    book_actor.add({'uarm_R': (-2.7 * raise_book, 0, -.10), 'farm_R': (-.42 * raise_book, 0, 0),
                    'uarm_L': (-.9 * spin_book, 0, .5 + .65 * chaotic * spin_book),
                    'head': (.14 * chaotic * spin_book, 0, -.22 * chaotic * spin_book)})
    book_actor.J['thigh_L'].rotation_euler.x = .24 * chaotic * spin_book
    book_actor.J['thigh_R'].rotation_euler.x = -.24 * chaotic * spin_book

    raise_bomb = smooth(16.05, 17.15, beat)
    bomb_actor.add({'uarm_R': (-2.75 * raise_bomb, 0, -.11), 'farm_R': (-.42 * raise_bomb, 0, 0),
                    'head': (-.05 * raise_bomb, 0, 0)})
    if 17.15 < t < EXPLODE:
        bomb_actor.look(pitch=-.1)
    spark.scale = (.9 + .32 * math.sin(t * 37),) * 3 if raise_bomb > .7 and t < EXPLODE else (0, 0, 0)
    if t >= EXPLODE:
        for index, actor in enumerate(actors):
            actor.root.location = (places[index] + (index - 1) * (t - EXPLODE) * 4,
                                   -(t - EXPLODE) * 1.5,
                                   -max(0, t - EXPLODE - .12) * 5)


def explosion_animation(t):
    age = max(0, t - EXPLODE)
    born = t >= EXPLODE
    blast_light.data.energy = 190000 * max(0, 1 - age / .22) if born else 0
    flash.scale = (max(.001, 5.0 * math.sin(math.pi * min(1, age / .24))),) * 3 if born and age < .24 else (0, 0, 0)
    core_growth = smooth(.05, 2.2, age) if born else 0
    core_rise = smooth(.05, 3.1, age) if born else 0
    for ob, height, width, depth in cloud_core:
        ob.location = (1.55, 0, .2 + height * core_rise)
        ob.scale = (width * core_growth, width * core_growth, depth * core_growth)
    for ob, angle, radius, spread, size, layer in cloud:
        if not born:
            ob.scale = (0, 0, 0)
            continue
        grow = smooth(0, 1.7, age)
        rise = smooth(.1, 3.5, age)
        if layer < 2:
            xy_radius = (1.0 + radius * 3.1) * spread * grow
            height = 1.7 + 12.0 * rise * (.40 + radius * .6)
        else:
            xy_radius = (3.0 + radius * 12.0) * spread * grow
            height = 9.0 * rise + 12.0 * rise * (1 - radius * .24) + 1.8 * math.sin(angle * 3 + age)
        ob.location = (1.55 + math.cos(angle) * xy_radius, math.sin(angle) * xy_radius, height)
        ob.scale = (size * grow * (1.45 + age * .07),) * 3
        ob.rotation_euler = (.3 * age, angle, .4 * age)
    for ob, angle, speed, height, phase in debris:
        if not born:
            ob.scale = (0, 0, 0)
            continue
        ob.location = (1.55 + math.cos(angle) * speed * age,
                       math.sin(angle) * speed * age,
                       .6 + height * age - 2.7 * age * age)
        ob.rotation_euler = (phase + age * 4, angle + age * 6, age * 8)
        ob.scale = (1, 1, 1) if age < 3.6 else (0, 0, 0)
    for index, ob in enumerate(shock):
        progress = smooth(index * .20, 2.3 + index * .25, age)
        radius = 1 + progress * (23 + index * 7)
        ob.scale = (radius, radius, .08 + .12 * (1 - progress)) if born and progress < .99 else (0, 0, 0)
        ob.location.z = .19 + .04 * index


def camera_animation(t):
    if t < 2.8:
        eye = lerp(v3(0, -44, 5.0), v3(0, -35, 4.3), smooth(0, 2.8, t))
        target, lens = v3(0, 38, 9), 29
    elif t < 4.5:
        eye, target, lens = v3(0, -3, 47), v3(0, 10, 0), 30
    elif t < 5.6:
        eye = lerp(v3(0, -17, 5), v3(0, -8.5, 2.7), smooth(4.5, 5.6, t))
        target, lens = v3(0, 0, 1.1), 31
    elif t < 9.45:
        eye = lerp(v3(-1.55, -3.9, 1.85), v3(-1.55, -3.6, 1.86), smooth(5.6, 9.45, t))
        target, lens = v3(-1.55, 0, 1.40), 42
    elif t < 15:
        eye, target, lens = v3(.10, -4.45, 2.02), v3(0, 0, 1.42), 39
    elif t < 18.15:
        eye = lerp(v3(1.50, -4.0, 1.92), v3(1.50, -3.65, 1.94), smooth(15, 18.15, t))
        target, lens = v3(1.55, 0, 1.47), 44
    else:
        overhead = smooth(19.15, 21.25, t)
        eye = lerp(v3(0, -3, 47), v3(20, -37, 23), overhead)
        target = lerp(v3(1.55, 5, 0), v3(1.55, 2, 11), overhead)
        lens = 28 + 11 * overhead
    aim_camera(camera, camera_data, eye, target, lens)


def update(t):
    camera_animation(t)
    actor_animation(t)
    explosion_animation(t)
    return t >= END_SCENE


def events():
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, 'events.json'), 'w') as file:
        json.dump({'voice_at': VO_AT, 'explode': EXPLODE, 'end_scene': END_SCENE,
                   'duration': DUR, 'cuts': CUTS}, file, indent=2)


if __name__ == '__main__':
    if '--cuts' not in argv:
        argv += ['--cuts', ','.join(str(round(value * FPS)) for value in CUTS)]
    run(update, DUR, FPS, out=os.path.join(WORK, 'frames'), events=events)
