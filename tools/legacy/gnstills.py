#!/usr/bin/env python3
"""Goosnav product stills: white cove (iPod register) and black void (modern register)."""
import argparse, math, os, sys
from pathlib import Path

import bpy
from mathutils import Euler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gnscenes import (GOOSKLERF, BOOK2, srgb, reset, setup, world, camera, area,
                      principled, bevel, shade_smooth, ASSETS)


def cove(sc, size=7, z=0.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    floor = bpy.context.object
    floor.data.materials.append(principled("covefloor", "FFFFFF", rough=0.96, spec=0.04))
    return floor


def studio_white(sc):
    world(sc, "FFFFFF", 0.34)
    area(sc, (-3.4, -3.0, 3.2), (math.radians(48), 0, math.radians(-44)), 240, 6.0)
    area(sc, (3.6, -2.4, 2.4), (math.radians(62), 0, math.radians(56)), 130, 6.0)
    area(sc, (0, -4.4, 0.9), (math.radians(86), 0, 0), 60, 7.0)
    area(sc, (0, 2.6, 3.6), (math.radians(148), 0, 0), 260, 7.0, "FFFFFF")
    area(sc, (0, 1.4, 6.0), (0, 0, 0), 900, 14.0, "FFFFFF")


def studio_void(sc):
    world(sc, "000000", 0.0)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    bpy.context.object.data.materials.append(principled("vfloor", "050505", rough=0.26, spec=0.62))
    area(sc, (-2.8, -2.4, 3.0), (math.radians(50), 0, math.radians(-46)), 260, 2.6)
    area(sc, (3.1, 2.6, 1.9), (math.radians(108), 0, math.radians(132)), 420, 1.8, "DCE8FF")
    area(sc, (0, -4.0, 0.5), (math.radians(88), 0, 0), 70, 4.0, "9FB8E0")


def book(sc, loc=(0, 0, 0), rotz=-22):
    W, Hh, D = 1.294, 1.0, 0.115
    bpy.ops.mesh.primitive_cube_add(size=1)
    bk = bpy.context.object
    bk.scale = (W, D, Hh)
    bpy.ops.object.transform_apply(scale=True)
    bevel(bk, 0.012, 4)
    cov = ASSETS / "book2_cover.png"
    spn = ASSETS / "book2_spine.png"
    mats = [
        principled("cov", image=cov if cov.exists() else None,
                   color=None if cov.exists() else BOOK2, rough=0.30, spec=0.66),
        principled("bck", color="98AEC9", rough=0.38),
        principled("spn", image=spn if spn.exists() else None,
                   color=None if spn.exists() else "98AEC9", rough=0.38),
        principled("pgs", color="F4EFE4", rough=0.78),
    ]
    for m in mats:
        bk.data.materials.append(m)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in bk.data.polygons:
        n = p.normal
        p.material_index = 0 if n.y < -0.5 else 1 if n.y > 0.5 else 2 if n.x < -0.5 else 3
    bk.location = (loc[0], loc[1], loc[2] + Hh / 2)
    bk.rotation_euler = Euler((0, 0, math.radians(rotz)))
    return bk


def die(sc, loc, size, color, rot):
    bpy.ops.mesh.primitive_cube_add(size=size)
    d = bpy.context.object
    bevel(d, size * 0.15, 6)
    shade_smooth(d)
    d.data.materials.append(principled("d" + color, color, rough=0.24, spec=0.9))
    d.location = (loc[0], loc[1], size / 2)
    d.rotation_euler = Euler(rot)
    return d


def cardstack(sc, loc=(0, 0, 0), n=26, w=0.63, h=0.88, t=0.011, rotz=14):
    import random
    random.seed(5)
    paper = principled("card", "FAF7F0", rough=0.72, spec=0.32)
    edge = principled("cardedge", "EDE7DA", rough=0.8, spec=0.2)
    obs = []
    for i in range(n):
        bpy.ops.mesh.primitive_cube_add(size=1)
        c = bpy.context.object
        c.scale = (w, h, t)
        bpy.ops.object.transform_apply(scale=True)
        bevel(c, 0.006, 2)
        c.data.materials.append(paper)
        c.data.materials.append(edge)
        jx, jy = random.uniform(-0.004, 0.004), random.uniform(-0.004, 0.004)
        c.location = (loc[0] + jx, loc[1] + jy, loc[2] + t / 2 + i * t)
        c.rotation_euler = Euler((0, 0, math.radians(rotz + random.uniform(-0.9, 0.9))))
        obs.append(c)
    return obs


def _catch(sc, floor):
    floor.is_shadow_catcher = True
    sc.render.film_transparent = True
    sc.render.image_settings.color_mode = "RGBA"


# ------------------------------------------------------------------- shots

def shot_book_cove(sc):
    studio_white(sc)
    _catch(sc, cove(sc))
    book(sc, rotz=-24)
    cam, tgt = camera(sc, (0, -3.4, 0.62), (0, 0, 0.47), 62)
    cam.location = (0.42, -3.35, 0.78)
    tgt.location = (0, 0, 0.46)


def shot_book_void(sc):
    studio_void(sc)
    book(sc, rotz=-19)
    cam, tgt = camera(sc, (0.30, -3.05, 0.70), (0, 0, 0.50), 58)


def shot_dice_cove(sc):
    studio_white(sc)
    _catch(sc, cove(sc))
    die(sc, (-0.66, 0.16), 0.62, GOOSKLERF[0], (0.10, 0.06, math.radians(18)))
    die(sc, (0.06, -0.26), 0.76, GOOSKLERF[1], (0.04, -0.08, math.radians(-14)))
    die(sc, (0.80, 0.14), 0.54, GOOSKLERF[2], (-0.07, 0.05, math.radians(32)))
    cam, tgt = camera(sc, (0.08, -5.50, 0.86), (0.06, 0.02, 0.32), 62)


def shot_dice_void(sc):
    studio_void(sc)
    die(sc, (-0.55, 0.06), 0.62, GOOSKLERF[0], (0.09, 0.05, math.radians(20)))
    die(sc, (0.16, -0.20), 0.76, GOOSKLERF[1], (0.03, -0.07, math.radians(-12)))
    die(sc, (0.86, 0.14), 0.54, GOOSKLERF[2], (-0.06, 0.04, math.radians(30)))
    cam, tgt = camera(sc, (0.14, -5.10, 0.80), (0.10, 0, 0.32), 62)


def shot_book_macro(sc):
    studio_void(sc)
    bk = book(sc, rotz=-8)
    cam, tgt = camera(sc, (-0.50, -1.62, 0.58), (-0.34, -0.02, 0.50), 68)
    area(sc, (-1.9, -1.5, 1.3), (math.radians(60), 0, math.radians(-50)), 260, 1.4)


def shot_stack_void(sc):
    studio_void(sc)
    cardstack(sc, (0, 0, 0), n=48, rotz=6)
    die(sc, (0.92, -0.30), 0.40, GOOSKLERF[1], (0.06, 0.04, math.radians(24)))
    area(sc, (-2.4, -1.4, 0.55), (math.radians(90), 0, math.radians(-62)), 220, 1.2, "FFF4E2")
    area(sc, (2.6, 0.9, 0.62), (math.radians(90), 0, math.radians(108)), 300, 1.0, "DCE8FF")
    cam, tgt = camera(sc, (0.05, -2.30, 0.30), (0, 0, 0.24), 88)


SHOTS = {
    "book_cove": shot_book_cove,
    "book_void": shot_book_void,
    "dice_cove": shot_dice_cove,
    "dice_void": shot_dice_void,
    "book_macro": shot_book_macro,
    "stack_void": shot_stack_void,
}


def render(name, outdir, w, h, samples):
    sc = reset()
    setup(sc, w, 1, "EEVEE", samples)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    SHOTS[name](sc)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out / name)
    bpy.ops.render.render(write_still=True)
    print("STILL %s -> %s %dx%d" % (name, out / (name + ".png"), w, h), flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", required=True)
    ap.add_argument("--out", default="stills")
    ap.add_argument("--w", type=int, default=1350)
    ap.add_argument("--h", type=int, default=1688)
    ap.add_argument("--samples", type=int, default=48)
    a = ap.parse_args(argv)
    names = list(SHOTS) if a.shot == "all" else [a.shot]
    for n in names:
        render(n, a.out, a.w, a.h, a.samples)


if __name__ == "__main__":
    main()
