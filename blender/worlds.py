"""Original, deterministic retro-world starter sets. Run with Blender's Python.

blender -b --factory-startup --python-exit-code 1 --python worlds.py -- \
    --world industrial-service-room --output ./service --preview

No project imports or asset-library assumptions. See docs/worlds.md for the contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

import bmesh
import bpy
from mathutils import Vector


VERSION = "1.1.0"
WORLDS = ("industrial-service-room", "remote-outpost", "overgrown-courtyard")
PALETTES = {
    "oxide": {"stone": "637476", "dark": "27363C", "metal": "82918B",
              "accent": "EAA74D", "soil": "746451", "leaf": "6F8855", "light": "A4E2DD"},
    "arctic": {"stone": "7F969E", "dark": "283D53", "metal": "B4C6CC",
               "accent": "EE8056", "soil": "697C89", "leaf": "487E79", "light": "B5E8F5"},
    "moss": {"stone": "94957E", "dark": "384B46", "metal": "73847A",
             "accent": "E2B866", "soil": "70644C", "leaf": "60864C", "light": "D6E7AC"},
}
DEFAULT_PALETTES = dict(zip(WORLDS, ("oxide", "arctic", "moss")))
LIGHTS = {
    "day": ((1.0, .89, .71), (0.55, .77, 1.0), 1.0, .28),
    "dusk": ((1.0, .58, .32), (.43, .65, 1.0), .75, .16),
    "emergency": ((1.0, .26, .12), (.25, .72, .85), .55, .12),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rgb(value):
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
                 for c in channels)


class Builder:
    """Small scene-local primitive kit; never reads global random state or assets."""

    def __init__(self, seed, palette):
        self.rng = random.Random(seed)
        self.collections = {}
        for name in ("Architecture", "Details", "Vegetation", "Product", "Staging", "Cameras", "Lighting"):
            coll = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(coll)
            self.collections[name] = coll
        self.group = "Architecture"
        self.materials = {}
        for role, color in PALETTES[palette].items():
            self.materials[role] = self.material(role, color, seed, emit=role == "light")

    def material(self, name, color, seed, emit=False):
        mat = bpy.data.materials.new("world." + name)
        mat.diffuse_color = (*rgb(color), 1)
        mat.use_nodes = True
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        shader = nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = (*rgb(color), 1)
        shader.inputs["Roughness"].default_value = .86
        shader.inputs["Specular IOR Level"].default_value = .22
        coord = nodes.new("ShaderNodeTexCoord")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.noise_dimensions = "4D"
        noise.inputs["W"].default_value = (seed % 100003) / 113
        noise.inputs["Scale"].default_value = 2.4 if name != "soil" else 1.7
        noise.inputs["Detail"].default_value = 1.0
        links.new(coord.outputs["Object"], noise.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        base = rgb(color)
        # Keep broad concrete/metal surfaces quiet so wear supports the silhouettes.
        low, high = (.65, 1.12) if name in {"leaf", "soil"} else (.8, 1.04)
        for element, pos, factor in zip(ramp.color_ramp.elements, (.28, .68), (low, high)):
            element.position = pos
            element.color = (*(min(1, c * factor) for c in base), 1)
        mid = ramp.color_ramp.elements.new(.42)
        mid.color = (*(c * .96 for c in base), 1)
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
        if emit:
            shader.inputs["Emission Color"].default_value = (*base, 1)
            shader.inputs["Emission Strength"].default_value = 2.2
        return mat

    def link(self, obj, group=None):
        self.collections[group or self.group].objects.link(obj)
        return obj

    def mesh(self, name, bm, loc, material, scale=(1, 1, 1)):
        data = bpy.data.meshes.new(name)
        bm.to_mesh(data)
        bm.free()
        obj = self.link(bpy.data.objects.new(name, data))
        obj.location = loc
        obj.scale = scale
        data.materials.append(self.materials[material])
        return obj

    def box(self, name, loc, size, material="stone", yaw=0):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1)
        # Bake dimensions so texture density uses world-scale units.
        for v in bm.verts:
            v.co = Vector(tuple(v.co[i] * size[i] for i in range(3)))
        obj = self.mesh(name, bm, loc, material)
        obj.rotation_euler.z = yaw
        return obj

    def cylinder(self, name, loc, radius, depth, material="metal", vertices=10, axis="Z"):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=vertices,
                             radius1=radius, radius2=radius, depth=depth)
        obj = self.mesh(name, bm, loc, material)
        if axis == "X":
            obj.rotation_euler.y = math.pi / 2
        elif axis == "Y":
            obj.rotation_euler.x = math.pi / 2
        return obj

    def rock(self, name, loc, size, material="soil"):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1)
        for v in bm.verts:
            v.co *= self.rng.uniform(.83, 1.17)
            v.co = Vector(tuple(v.co[i] * size[i] for i in range(3)))
        obj = self.mesh(name, bm, loc, material)
        obj.rotation_euler.z = self.rng.uniform(-math.pi, math.pi)
        return obj

    def beam(self, name, start, end, width, material="metal"):
        delta = Vector(end) - Vector(start)
        obj = self.box(name, (Vector(start) + Vector(end)) / 2,
                       (width, width, delta.length), material)
        obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
        return obj

    def text(self, name, body, loc, size=.3, material="accent"):
        data = bpy.data.curves.new(name, "FONT")
        data.body, data.size, data.align_x = body, size, "CENTER"
        data.extrude = 0
        data.materials.append(self.materials[material])
        obj = self.link(bpy.data.objects.new(name, data))
        obj.location = loc
        obj.rotation_euler.x = math.pi / 2  # faces the open front (-Y)
        return obj

    def anchor(self, name, loc, role, yaw=0):
        obj = self.link(bpy.data.objects.new(name, None), "Staging")
        obj.location = loc
        obj.rotation_euler.z = yaw
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = .5
        obj["role"], obj["forward_axis"], obj["up_axis"] = role, "-Y", "+Z"
        return obj

    def lamp(self, name, loc, target, energy, color, size=5, kind="AREA"):
        data = bpy.data.lights.new(name, kind)
        data.energy, data.color = energy, color
        if kind == "AREA":
            data.shape, data.size = "DISK", size
        elif kind == "SUN":
            data.angle = .12
        obj = self.link(bpy.data.objects.new(name, data), "Lighting")
        obj.location = loc
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
        return obj

    def crate(self, name, loc, size=1):
        self.box(name, loc, (size, size, size), "dark")
        x, y, z = loc
        for dx in (-.38, .38):
            self.box(name + ".strap", (x + dx * size, y - .51 * size, z),
                     (.09 * size, .035, size), "metal")
        self.box(name + ".label", (x, y - .53 * size, z), (.32 * size, .02, .17), "accent")


def industrial(b):
    b.box("foundation", (0, .5, -.37), (12.5, 10, .5), "dark")
    for x in range(-5, 6, 2):
        for y in range(-3, 6, 2):
            b.box("floor.tile", (x, y, -.06), (1.95, 1.95, .12))
    b.box("rear.wall", (0, 5.1, 2.55), (12.4, .4, 5.1))
    b.box("left.wall", (-6.1, 1.2, 2.55), (.4, 8, 5.1))
    for x in (-5.7, -2.8, 2.8, 5.7):
        b.box("wall.rib", (x, 4.79, 2.5), (.22, .25, 5), "dark")
    b.box("wall.stripe", (0, 4.86, 1.18), (12, .045, .2), "accent")
    b.box("door.recess", (1.1, 4.72, 1.9), (2.75, .12, 3.8), "dark")
    for x in (.44, 1.76):
        b.box("door.leaf", (x, 4.61, 1.8), (1.27, .12, 3.3), "metal")
        b.box("door.vision", (x, 4.52, 2.25), (.8, .05, .25), "dark")
    for x in (-.38, 2.58):
        b.box("door.jamb", (x, 4.46, 1.95), (.18, .4, 3.9), "accent")
    b.box("door.header", (1.1, 4.46, 3.85), (3.15, .4, .2), "accent")
    b.text("door.sign", "SERVICE / 04", (1.1, 4.48, 4.18), .35)
    b.group = "Details"
    for z in (3.5, 3.95):
        b.cylinder("feed.pipe", (-2.9, 4.42, z), .13, 5.5, "metal", axis="X")
    for x in (-5.2, -4.0):
        b.cylinder("pressure.tank", (x, 3.4, 1.3), .43, 2.6)
        for z in (.25, 2.25):
            b.cylinder("tank.band", (x, 3.4, z), .46, .13, "accent")
        b.cylinder("tank.feed", (x, 3.4, 2.9), .09, .65)
    b.box("console.base", (-4.5, .7, .65), (1.7, .85, 1.3), "dark")
    b.box("console.surround", (-4.5, .66, 1.45), (1.85, .9, .35), "metal")
    b.box("console.screen", (-4.5, .195, 1.46), (1.22, .03, .19), "light")
    for x in (-5.0, -4.7, -4.4, -4.1):
        b.box("console.key", (x, .15, 1.22), (.12, .06, .08), "accent")
    b.text("console.id", "PUMP CONTROL", (-4.5, .24, .7), .16, "metal")
    b.box("vent.frame", (4.25, 4.65, 3.1), (1.8, .3, 1.5), "dark")
    for z in (2.55, 2.8, 3.05, 3.3, 3.55):
        b.box("vent.louver", (4.25, 4.42, z), (1.65, .28, .09), "metal")
    b.crate("parts.crate", (4.6, 3.6, .5))
    b.crate("parts.crate.upper", (4.6, 3.6, 1.4), .8)
    for y in range(-3, 5):
        b.box("trench.dark", (-5.4, y, .012), (.65, .94, .025), "dark")
        for dy in (-.3, 0, .3):
            b.box("trench.grate", (-5.4, y + dy, .035), (.65, .07, .035), "metal")
    for x in (-3.25, 3.25):
        for y in (-2.8, -1.8, -.8, .2, 1.2):
            b.box("lane.dash", (x, y, .012), (.09, .55, .022), "accent")
    for x in (-3, 3):
        b.box("ceiling.bracket", (x, 4, 4.65), (.15, 2.1, .18), "dark")
        b.box("strip.housing", (x, 3.2, 4.55), (1.9, .4, .17), "dark")
        b.box("strip.diffuser", (x, 3.2, 4.45), (1.7, .3, .04), "light")


def outpost(b):
    b.box("terrain.shelf", (0, 2, -.57), (27, 25, .9), "soil")
    # Surround the pad at ground level without a coplanar face underneath it.
    for x in (-9, 9):
        b.box("terrain.shoulder", (x, 2, -.06), (9, 25, .12), "soil")
    b.box("terrain.front", (0, -7.2, -.06), (9, 6.6, .12), "soil")
    b.box("terrain.rear", (0, 8.8, -.06), (9, 11.4, .12), "soil")
    b.box("landing.pad", (0, -.4, -.06), (9, 7, .12), "dark")
    for x in (-3.8, 3.8):
        for y in (-2.5, -1, .5, 2):
            b.box("pad.edge", (x, y, .02), (.14, .75, .04), "accent")
    b.box("bunker.body", (-1.8, 5, 1.8), (7, 4.5, 3.6))
    b.box("bunker.roof", (-1.8, 5, 3.75), (7.5, 5, .35), "dark")
    b.box("bunker.trim", (-1.8, 2.69, 2.65), (7.1, .14, .16), "accent")
    b.box("entry.shadow", (-1.4, 2.68, 1.3), (1.8, .12, 2.6), "dark")
    b.box("entry.door", (-1.4, 2.59, 1.25), (1.45, .08, 2.45), "metal")
    b.box("entry.window", (-1.4, 2.52, 1.8), (.85, .04, .35), "light")
    b.box("entry.canopy", (-1.4, 1.95, 2.9), (2.6, 1.7, .18), "dark")
    for x in (-2.55, -.25):
        b.beam("canopy.brace", (x, 2.5, 2), (x, 1.35, 2.8), .09)
    b.text("bunker.sign", "RELAY  /  07", (-1.8, 2.58, 3.13), .33)
    for x in (-4.3, .6):
        b.box("bunker.window", (x, 2.65, 1.8), (1.2, .08, .6), "dark")
        for dx in (-.35, 0, .35):
            b.box("window.mullion", (x + dx, 2.58, 1.8), (.06, .08, .6), "metal")
    b.group = "Details"
    b.cylinder("relay.mast", (4.7, 4.6, 3.7), .14, 7.4)
    for x, y in ((3.1, 4.1), (6.4, 4.2), (4.7, 6.2)):
        b.beam("mast.brace", (x, y, .1), (4.7, 4.6, 4.6), .065, "dark")
    b.beam("aerial.crossbar", (3.5, 4.6, 6.4), (5.9, 4.6, 6.4), .11)
    for x in (3.5, 4.1, 4.7, 5.3, 5.9):
        b.beam("aerial.prong", (x, 4, 6.4), (x, 5.2, 6.4), .065)
    b.cylinder("beacon", (4.7, 4.6, 7.45), .2, .27, "light")
    for x in (-7.2, -5.5):
        b.cylinder("solar.post", (x, .8, .85), .1, 1.7)
        panel = b.box("solar.panel", (x, .8, 1.8), (1.45, 2.6, .12), "dark")
        panel.rotation_euler.x = .3
        for j in range(5):
            slat = b.box("solar.cell", (x, -.2 + j * .49, 1.86 + (-1 + j * .49) * math.sin(.3)),
                         (1.3, .40, .025), "metal")
            slat.rotation_euler.x = .3
    b.crate("supply.case", (3.6, 1.9, .45), .9)
    b.crate("supply.case.second", (4.65, 2.2, .35), .7)
    for x, y in ((-4, -3), (4, -3), (4, 1)):
        b.cylinder("pad.bollard", (x, y, .38), .13, .76, "accent")
        b.cylinder("pad.lamp", (x, y, .8), .15, .13, "light")
    for i in range(28):
        x, y = b.rng.uniform(-12, 12), b.rng.uniform(-7, 12)
        if abs(x) < 8 and y < 8:
            continue
        b.rock("weathered.rock", (x, y, .2), (b.rng.uniform(.4, 1.4), .65, b.rng.uniform(.4, 1.1)))
    # Stepped horizon landmarks give distance without sky images or heavy terrain.
    for x, y, width, height in ((-9, 12, 5, 5.4), (-3, 15, 6, 7), (5, 14, 5, 4.8), (11, 11, 4, 6)):
        for tier in range(3):
            b.rock("mesa.tier", (x, y, height * (.18 + tier * .22)),
                   (width * (1 - tier * .2), 2.6 - tier * .4, height * .28), "stone")


def courtyard(b):
    b.box("courtyard.base", (0, 1, -.26), (13, 12, .5), "soil")
    for x in range(-5, 6, 2):
        for y in range(-3, 6, 2):
            b.box("paving.block", (x, y, -.055), (1.88, 1.88, .11), "stone",
                  yaw=b.rng.uniform(-.015, .015))
    # Portal is a real opening: piers + stepped arch, with a garden beyond it.
    b.box("wall.left", (-4, 5.2, 2), (4.2, .65, 4))
    b.box("wall.right", (4, 5.2, 1.75), (4.2, .65, 3.5))
    for x in (-2, 2):
        b.box("arch.pier", (x, 5.1, 1.65), (.65, .9, 3.3), "metal")
        b.box("arch.step", (x * .85, 5.1, 3.15), (.9, .9, .55), "metal")
        b.box("arch.cap", (x * .66, 5.1, 3.58), (.9, .9, .35), "metal")
    b.box("arch.lintel", (0, 5.1, 3.9), (2.4, .9, .35), "metal")
    b.box("garden.beyond", (0, 7, -.03), (4, 4, .12), "soil")
    b.box("garden.wall", (0, 9.1, 1.1), (6, .5, 2.2), "dark")
    for x in (-4.8, -2.7, 2.8, 5):
        b.box("wall.buttress", (x, 4.68, 1.8), (.3, .5, 3.6), "dark")
    b.box("side.ruin", (-6, 1.4, 1.15), (.65, 6.8, 2.3))
    b.box("side.ruin.cap", (-6, 1.4, 2.35), (.85, 6.8, .2), "metal")
    b.group = "Details"
    for x in (-4.4, 4.5):
        b.box("planter", (x, 2.8, .38), (2.1, 1.65, .76), "dark")
        b.box("planter.rim", (x, 2.8, .8), (2.25, 1.8, .15), "metal")
        b.box("planter.soil", (x, 2.8, .9), (1.95, 1.5, .08), "soil")
    b.box("bench.seat", (-4.5, -.5, .55), (1.9, .65, .16), "metal")
    for x in (-5.15, -3.85):
        b.box("bench.leg", (x, -.5, .25), (.2, .55, .5), "dark")
    b.text("wall.inscription", "GARDEN  /  03", (-3.9, 4.82, 2.6), .25, "accent")
    for x in (3.7, 5.1):
        b.box("broken.column.base", (x, -.8, .17), (.85, .85, .34), "metal")
        b.cylinder("broken.column", (x, -.8, .85 if x < 4 else .55), .29,
                   1.4 if x < 4 else .8, "stone", vertices=8)
    # Low segmented channel, deliberately outside the central standing area.
    for y in range(-3, 5):
        b.box("channel.water", (5.7, y, .03), (.48, .95, .04), "dark")
        b.box("channel.edge", (5.35, y, .09), (.15, .95, .18), "metal")
    b.group = "Vegetation"
    for x, y, base in ((-4.4, 2.8, .95), (4.5, 2.8, .95), (-1, 7.7, 0), (1.2, 8, 0)):
        b.beam("shrub.trunk", (x, y, base), (x + .15, y, base + 1.5), .17, "soil")
        for i in range(5):
            b.rock("shrub.crown", (x + b.rng.uniform(-.7, .7), y + b.rng.uniform(-.5, .5),
                                   base + b.rng.uniform(1, 1.9)), (.65, .6, .55), "leaf")
    for x in (-5.4, -3.2, 2.8, 4.7):
        for i in range(8):
            z = .4 + i * .43
            px = x + math.sin(i * 1.3) * .18
            b.beam("vine.stem", (px, 4.77, z), (px + .12, 4.77, z + .4), .045, "soil")
            b.rock("vine.leaf", (px, 4.68, z), (.26, .11, .2), "leaf")
    for i in range(34):
        x, y = b.rng.uniform(-5.7, 5.5), b.rng.uniform(-3.5, 4)
        if abs(x) < 3.4 and y < 2.2:
            continue  # reserve central blocking space
        b.rock("moss.patch", (x, y, .035), (.35, .27, .055), "leaf")
        for dx in (-.12, .06):
            b.beam("grass.blade", (x + dx, y, .05), (x + dx + .1, y, .35), .04, "leaf")


def add_product(b, args):
    b.group = "Product"
    anchor = b.anchor("anchor.product", args.product_position, "product_base", math.radians(args.product_yaw))
    x, y, z = anchor.location
    b.box("product.plinth", (x, y, z - .485), (1.35, 1.1, .83), "dark")
    b.box("product.plinth.rim", (x, y, z - .035), (1.46, 1.2, .07), "accent")
    sources = []
    if args.product_blend:
        path = args.product_blend.resolve()
        with bpy.data.libraries.load(str(path), link=False) as (source, target):
            if args.product_collection:
                if args.product_collection not in source.collections:
                    raise ValueError("Product collection not found: " + args.product_collection)
                target.collections = [args.product_collection]
            else:
                target.objects = list(source.objects)
        if args.product_collection:
            coll = target.collections[0]
            b.collections["Product"].children.link(coll)
            objects = list(coll.all_objects)
        else:
            objects = [o for o in target.objects if o]
            for obj in objects:
                b.collections["Product"].objects.link(obj)
        if any(o.type in {"LIGHT", "CAMERA"} for o in objects):
            raise ValueError("Product assets must contain geometry, not cameras/lights; select a product collection")
        if any(o.type not in {"MESH", "EMPTY"} or o.modifiers or o.constraints or
               o.animation_data or o.instance_type != "NONE" or
               (o.type == "MESH" and o.data.shape_keys) for o in objects):
            raise ValueError("Product must be static mesh/empty objects: apply modifiers, poses and instances first")
        bpy.context.view_layer.update()
        points = [o.matrix_world @ Vector(p) for o in objects if o.type == "MESH" for p in o.bound_box]
        if not points:
            raise ValueError("Product asset contains no mesh geometry")
        lower = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        upper = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        extent = max(upper - lower)
        if extent < 1e-6:
            raise ValueError("Product mesh bounds are empty")
        root = b.link(bpy.data.objects.new("product.asset_root", None))
        root.parent = anchor
        factor = args.product_size / extent
        root.scale = (factor,) * 3
        root.location = -Vector(((lower.x + upper.x) / 2, (lower.y + upper.y) / 2, lower.z)) * factor
        for obj in objects:
            if obj.parent not in objects:
                transform = obj.matrix_world.copy()
                obj.parent = root
                obj.matrix_parent_inverse.identity()
                obj.matrix_basis = transform
        sources.append({"kind": "user_blend", "name": path.name, "sha256": file_hash(path),
                        "collection": args.product_collection, "rights": "user-supplied; not verified"})
    elif args.product_texture:
        size = args.product_size
        path = args.product_texture.resolve()
        image = bpy.data.images.load(str(path), check_existing=False)
        image.pack()
        mat = bpy.data.materials.new("product.user_texture")
        mat.use_nodes = True
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image, tex.interpolation = image, "Closest"
        mat.node_tree.links.new(tex.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        # Explicit front-facing UV card containing only the supplied artwork.
        mesh = bpy.data.meshes.new("product.artwork")
        mesh.from_pydata([(-size * .36, -size * .13, 0), (size * .36, -size * .13, 0),
                          (size * .36, -size * .13, size), (-size * .36, -size * .13, size)], [], [(0, 1, 2, 3)])
        uv = mesh.uv_layers.new()
        for loop, xy in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop.uv = xy
        mesh.materials.append(mat)
        card = b.link(bpy.data.objects.new("product.artwork", mesh))
        card.parent = anchor
        sources.append({"kind": "user_image", "name": path.name, "sha256": file_hash(path),
                        "rights": "user-supplied; not verified"})
    return sources


def validate_product_module():
    """Assert the publication contract before claiming a bundle is proxy-free."""
    proxies = [o.name for o in bpy.data.objects
               if o.get("proxy") or o.get("is_proxy") or "placeholder" in o.name.lower()]
    if proxies:
        raise ValueError("Unresolved proxy objects are not publishable: " + ", ".join(proxies))
    anchor = bpy.data.objects.get("anchor.product")
    if anchor is None or anchor.type != "EMPTY" or anchor.get("role") != "product_base":
        raise ValueError("Missing stable product anchor")
    return {"anchor": anchor.name, "collection": "Product",
            "plinth_objects": ["product.plinth", "product.plinth.rim"],
            "unresolved_proxies": []}


def setup_scene(b, args):
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.engine = "CYCLES" if args.engine == "cycles" else "BLENDER_EEVEE"
    if args.engine == "cycles":
        scene.cycles.device, scene.cycles.samples = "CPU", args.samples
        scene.cycles.seed = args.seed % 2147483647
        # Distribution builds may omit OpenImageDenoise; no optional device required.
        scene.cycles.use_denoising = False
        scene.cycles.max_bounces = 3
    else:
        scene.eevee.taa_render_samples = args.samples
        scene.eevee.use_gtao = True
        scene.eevee.gtao_distance = 3
        scene.eevee.gtao_factor = 1.25
        scene.eevee.shadow_cube_size = "1024"
        scene.eevee.use_soft_shadows = True
    scene.render.resolution_x, scene.render.resolution_y = args.resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode, scene.render.threads = "FIXED", args.threads
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast"
    scene.view_settings.exposure, scene.view_settings.gamma = 0, 1
    scene.world = bpy.data.worlds.new("world.atmosphere")
    scene.world.use_nodes = True
    warm, cool, strength, ambient = LIGHTS[args.light]
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*cool, 1)
    bg.inputs["Strength"].default_value = ambient * args.light_strength
    multiplier = strength * args.light_strength
    b.lamp("light.key", (-4, -4, 9), (0, 1, 0), 1600 * multiplier, warm, 7)
    b.lamp("light.fill", (6, -2, 5), (0, 1, 1), 1100 * multiplier, cool, 6)
    b.lamp("light.rim", (0, 4, 7), (0, 0, 1), 1500 * multiplier, warm, 4)
    if args.world != "industrial-service-room":
        b.lamp("light.sun", (-8, -5, 12), (0, 2, 0), 1.7 * multiplier, warm, kind="SUN")
    b.anchor("anchor.character_a", (-2, -.85, 0), "character_feet", -.15)
    b.anchor("anchor.character_b", (2, -.85, 0), "character_feet", .15)
    b.anchor("anchor.entrance", (0, 2, 0), "character_feet", 0)
    b.anchor("anchor.look_at", (0, .2, 1.4), "gaze_target")
    px, py, pz = args.product_position
    cameras = {
        "wide": ((12.8, -18.5, 11.2), (0, 1.7, 1.5), 43),
        "stage": ((7.8, -15.5, 6.2), (0, .9, 1.35), 48),
        "product": ((px + 3.6, py - 6, pz + 2.6), (px, py, pz + args.product_size * .48), 55),
    }
    if args.world == "remote-outpost":
        cameras["wide"] = ((17, -24, 13), (0, 3.5, 2.1), 40)
    for name, (loc, target, lens) in cameras.items():
        data = bpy.data.cameras.new("camera." + name)
        data.lens, data.clip_start, data.clip_end = lens, .05, 250
        data.dof.use_dof = False
        obj = b.link(bpy.data.objects.new("camera." + name, data), "Cameras")
        obj.location = loc
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj["purpose"] = name
    scene.camera = bpy.data.objects["camera." + args.camera]
    scene.frame_set(1)
    bpy.context.view_layer.update()


def inventory():
    """Stable content inventory; excludes output paths, clocks, and Blender file bytes."""
    objects, triangles = [], 0
    bounds = []
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        row = {"name": obj.name, "type": obj.type,
               "matrix": [[round(v, 6) for v in r] for r in obj.matrix_world],
               "parent": obj.parent.name if obj.parent else None}
        if obj.type == "MESH":
            mesh = obj.data
            count = sum(len(p.vertices) - 2 for p in mesh.polygons)
            triangles += count
            row.update(triangles=count, geometry_sha256=digest({
                "vertices": [[round(v, 6) for v in vert.co] for vert in mesh.vertices],
                "faces": [list(p.vertices) for p in mesh.polygons]}),
                       materials=[m.name if m else None for m in mesh.materials])
            bounds.extend(obj.matrix_world @ Vector(p) for p in obj.bound_box)
        elif obj.type == "FONT":
            row.update(text=obj.data.body, size=round(obj.data.size, 6))
        elif obj.type == "CAMERA":
            row["lens"] = obj.data.lens
        elif obj.type == "LIGHT":
            row.update(energy=obj.data.energy, color=list(obj.data.color))
        objects.append(row)
    return {"objects": objects, "object_count": len(objects), "mesh_triangles": triangles,
            "bounds": {"min": [round(min(p[i] for p in bounds), 4) for i in range(3)],
                       "max": [round(max(p[i] for p in bounds), 4) for i in range(3)]}}


def pack_dependencies():
    """Fail rather than claiming portability for a missing or unpackable dependency."""
    if any(block.library for block in bpy.data.user_map()):
        raise ValueError("Product contains linked libraries; make them local before importing")
    # Blender 4.0 records read-only append-history paths on local IDs. A local copy
    # clears that history; remap users before removing the old ID, preserving names.
    for block in list(bpy.data.user_map()):
        if block.library_weak_reference:
            name = block.name
            local = block.copy()
            block.user_remap(local)
            bpy.data.batch_remove(ids=(block,))
            local.name = name
    # Append can retain an unused Library record (users=1) with no linked datablocks.
    for library in list(bpy.data.libraries):
        bpy.data.libraries.remove(library)
    if bpy.data.movieclips or bpy.data.sounds or bpy.data.volumes or bpy.data.cache_files:
        raise ValueError("Product has unsupported external media/cache dependencies")
    for image in bpy.data.images:
        if image.source not in {"FILE", "GENERATED", "VIEWER"}:
            raise ValueError("Unsupported image source: " + image.source)
        if image.source == "FILE" and not image.packed_file:
            image.pack()
        if image.source == "FILE" and not image.packed_file:
            raise ValueError("Could not pack image: " + image.name)
    bpy.ops.file.pack_all()
    for font in bpy.data.fonts:
        if font.filepath != "<builtin>" and not font.packed_file:
            raise ValueError("Could not pack font: " + font.name)
    # Reject any other unresolved external file reported by Blender's dependency API.
    # In Blender 4.0 packed=False excludes packed image paths (despite its docstring).
    if bpy.utils.blend_paths(absolute=True, packed=False):
        raise ValueError("Product has unpacked external dependencies")
    dependencies = []
    for image in bpy.data.images:
        if image.packed_file:
            dependencies.append({"name": image.name, "kind": "packed_image",
                "sha256": hashlib.sha256(bytes(image.packed_file.data)).hexdigest()})
            image.filepath = "//" + Path(image.name).name
    return sorted(dependencies, key=lambda item: item["name"])


def export_glb(path, builder):
    """Portable palette-material export; restore full procedural Blender materials."""
    removed_links, temporary_objects, temporary_meshes, anchor_axes = [], [], [], []
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    try:
        for mat in builder.materials.values():
            socket = mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"]
            for link in list(socket.links):
                removed_links.append((mat.node_tree, link.from_socket, link.to_socket))
                mat.node_tree.links.remove(link)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in builder.collections["Staging"].objects:
            anchor_axes.append((obj, obj["up_axis"], obj["forward_axis"]))
            obj["up_axis"], obj["forward_axis"] = "+Y", "+Z"
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in list(bpy.context.scene.objects):
            if obj.type in {"MESH", "EMPTY", "CAMERA"}:
                obj.select_set(True)
            elif obj.type == "FONT":
                mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
                copy = bpy.data.objects.new(obj.name + ".portable", mesh)
                bpy.context.scene.collection.objects.link(copy)
                copy.matrix_world = obj.matrix_world.copy()
                copy.select_set(True)
                temporary_objects.append(copy)
                temporary_meshes.append(mesh)
        status = bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB",
            use_selection=True, export_cameras=True, export_lights=False, export_extras=True,
            export_animations=False, export_yup=True)
        if "FINISHED" not in status:
            raise RuntimeError("GLB export did not finish")
    finally:
        for obj, up, forward in anchor_axes:
            obj["up_axis"], obj["forward_axis"] = up, forward
        for tree, source, target in removed_links:
            tree.links.new(source, target)
        for obj in temporary_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in temporary_meshes:
            bpy.data.meshes.remove(mesh)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active


def build(args):
    """Build a fresh scene and write artifacts. Destructively resets the current scene."""
    started = time.perf_counter()
    output = args.output.expanduser().resolve()
    blend = output if output.suffix.lower() == ".blend" else output / (args.world + ".blend")
    stem = blend.with_suffix("")
    paths = {"blend": blend, "glb": Path(str(stem) + ".glb"), "metadata": Path(str(stem) + ".build.json"),
             "manifest": Path(str(stem) + ".manifest.json"),
             "preview": Path(str(stem) + ".preview.png")}
    # Refuse collisions by default: output may point anywhere, including a user library.
    for key, path in paths.items():
        if path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {path}; choose a new path or pass --overwrite")
    for source in (args.product_blend, args.product_texture):
        if source and source.resolve() in paths.values():
            raise ValueError("Output must not overwrite an input asset")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    palette = args.palette or DEFAULT_PALETTES[args.world]
    b = Builder(args.seed, palette)
    {WORLDS[0]: industrial, WORLDS[1]: outpost, WORLDS[2]: courtyard}[args.world](b)
    sources = add_product(b, args)
    setup_scene(b, args)
    dependencies = pack_dependencies()
    product_module = validate_product_module()
    product_module["mode"] = ("supplied_blend" if args.product_blend else
                              "supplied_image" if args.product_texture else "anchor_only")
    scene = bpy.context.scene
    info = inventory()
    settings = {"world": args.world, "seed": args.seed, "palette": palette,
                "light": args.light, "light_strength": args.light_strength, "camera": args.camera,
                "product_position": list(args.product_position), "product_yaw": args.product_yaw,
                "product_size": args.product_size, "product_mode": product_module["mode"], "engine": args.engine,
                "samples": args.samples, "resolution": list(args.resolution), "threads": args.threads}
    source_hash = file_hash(__file__)
    content_hash = digest({"generator_sha256": source_hash, "blender_version": bpy.app.version_string,
                           "settings": settings,
                           "inventory": info, "inputs": sources, "packed_dependencies": dependencies})
    scene["world_builder_version"], scene["world_content_sha256"] = VERSION, content_hash
    anchors = [{"name": o.name, "role": o["role"], "position": list(o.location),
                "yaw_radians": o.rotation_euler.z, "forward_axis": "-Y", "up_axis": "+Z"}
               for o in sorted(b.collections["Staging"].objects, key=lambda o: o.name)]
    manifest = {
        "schema": "retro-world.asset/v1", "asset_id": f"retro-world/{args.world}/{content_hash[:16]}",
        "title": args.world.replace("-", " ").title(), "generator": {"name": "worlds.py", "version": VERSION,
        "sha256": source_hash}, "content_sha256": content_hash,
        "proxy": False, "dependencies": [], "unresolved_proxies": [], "product": product_module,
        "artifacts": {k: p.name for k, p in paths.items() if k != "preview" or args.preview},
        "capabilities": {"static_environment": True, "original_geometry": not bool(args.product_blend),
            "original_starter_geometry": True,
            "procedural_materials": True, "packed_dependencies": True, "character_staging": True,
            "product_placement": True, "animation": False, "collision_meshes": False,
            "navigation_mesh": False, "units": "meters", "up_axis": "+Z", "actor_forward": "-Y",
            "cameras": ["camera.wide", "camera.stage", "camera.product"],
            "collections": list(b.collections), "engines": ["BLENDER_EEVEE", "CYCLES_CPU"],
            "minimum_blender": "4.0", "tested_blender": bpy.app.version_string},
        "portable_export": {"format": "glTF 2.0 binary", "up_axis": "+Y", "actor_forward": "+Z", "units": "meters",
            "coordinate_mapping": "Blender (x, y, z) -> glTF (x, z, -y); JSON anchor positions use Blender coordinates",
            "materials": "Palette PBR colors; procedural shader patterns remain in the .blend",
            "images": "Supported product image textures embedded in GLB",
            "text": "Converted to mesh", "anchors": "Named nodes with role extras",
            "cameras": True, "lights": False,
            "lighting": "Supply lighting in the consuming application; Blender area lights are not exported"},
        "anchors": anchors, "bounds": info["bounds"],
        "staging_clearance": {"character_a_b_radius_m": .55, "character_height_m": 1.9,
                              "scope": "starter geometry at default product placement"},
        "provenance": {"starter": "Original geometry and procedural shaders generated by worlds.py; no third-party game assets",
            "style_reference": "Early polygonal exploration and industrial science-fiction environments",
            "external_inputs": sources, "packed_dependencies": dependencies,
            "rights": "Starter output follows the host project's licensing; no additional license asserted",
            "external_rights_verified": False if sources else None},
        "limitations": ["Static starter set; no collision or navigation data",
            "Mesh triangle budget excludes text tessellation and imported modifiers",
            "Determinism covers scene content on the same Blender version, not binary .blend bytes or cross-device pixels",
            "Imported products must be trusted static assets; cameras/lights and external caches are rejected"],
    }
    # Embed the catalog record so a .blend alone still carries its contract/provenance.
    bpy.data.texts.new("world.manifest.json").write(json.dumps(manifest, indent=2, sort_keys=True))
    blend.parent.mkdir(parents=True, exist_ok=True)
    export_started = time.perf_counter()
    export_glb(paths["glb"], b)
    export_seconds = time.perf_counter() - export_started
    scene.render.filepath = "//" + paths["preview"].name
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    build_seconds = time.perf_counter() - started
    render_seconds = None
    if args.preview:
        tick = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        render_seconds = time.perf_counter() - tick
    metadata = {"schema": "retro-world.build/v1", "generator_version": VERSION,
        "blender_version": bpy.app.version_string, "content_sha256": content_hash,
        "settings": settings, "inventory": info,
        "proxy": False, "dependencies": [], "unresolved_proxies": [], "product": product_module,
        "measurements": {"build_seconds": round(build_seconds, 3),
                         "glb_export_seconds": round(export_seconds, 3),
                         "preview_seconds": round(render_seconds, 3) if render_seconds is not None else None,
                         "total_seconds": round(time.perf_counter() - started, 3),
                         "blend_bytes": blend.stat().st_size, "glb_bytes": paths["glb"].stat().st_size},
        "artifact_sha256": {k: file_hash(p) for k, p in paths.items()
                            if k in {"blend", "glb"} or (k == "preview" and args.preview)}}
    paths["metadata"].write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("WORLD_BUILD " + json.dumps({"artifacts": manifest["artifacts"], "output_directory": str(blend.parent),
                                      "measurements": metadata["measurements"],
                                      "triangles": info["mesh_triangles"], "content_sha256": content_hash}))
    return metadata


def positive_float(value):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return result


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise argparse.ArgumentTypeError("must be finite")
    return result


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="Output directory or exact .blend filename")
    parser.add_argument("--world", choices=WORLDS, default=WORLDS[0])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--palette", choices=tuple(PALETTES), help="Defaults to a palette chosen for the world")
    parser.add_argument("--light", choices=tuple(LIGHTS), default="day")
    parser.add_argument("--light-strength", type=positive_float, default=1.0)
    parser.add_argument("--camera", choices=("wide", "stage", "product"), default="wide")
    parser.add_argument("--product-position", type=finite_float, nargs=3, metavar=("X", "Y", "Z"), default=(0, -.35, .9))
    parser.add_argument("--product-yaw", type=finite_float, default=0, help="Degrees about +Z")
    parser.add_argument("--product-size", type=positive_float, default=.85, help="Maximum product dimension in meters")
    assets = parser.add_mutually_exclusive_group()
    assets.add_argument("--product-blend", type=Path, help="Append a trusted static mesh product and pack its images")
    assets.add_argument("--product-texture", type=Path, help="Place this packed image on a flat artwork card; no dummy product")
    parser.add_argument("--product-collection", help="Optional collection name inside --product-blend")
    parser.add_argument("--engine", choices=("eevee", "cycles"), default="eevee")
    parser.add_argument("--samples", type=positive_int, default=32)
    parser.add_argument("--threads", type=positive_int, default=4)
    parser.add_argument("--resolution", type=positive_int, nargs=2, metavar=("WIDTH", "HEIGHT"), default=(768, 480))
    parser.add_argument("--preview", action="store_true", help="Render a PNG alongside the .blend and JSON records")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing artifacts at this exact output")
    args = parser.parse_args(argv)
    if args.product_collection and not args.product_blend:
        parser.error("--product-collection requires --product-blend")
    for path in (args.product_blend, args.product_texture):
        if path and not path.is_file():
            parser.error("Asset path is not a file: " + str(path))
    return args


if __name__ == "__main__":
    build(parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
