#!/usr/bin/env python3
"""Goosnav Family III Blender scenes. Renders a PNG sequence per reel."""
import argparse, math, os, random, sys
from pathlib import Path

import bpy
from mathutils import Vector, Euler

GOOSKLERF = ["00B2A9", "FE5000", "330072"]
BOOK1, BOOK2, BOOK3, RESERVE = "DA291C", "0033A0", "009639", "FFCD00"
SPECTRUM = [BOOK1, BOOK2, BOOK3, RESERVE] + GOOSKLERF

ASSETS = Path(os.environ.get("GN_ASSETS", Path(__file__).resolve().parent.parent / "assets"))


def srgb(h, a=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (out[0], out[1], out[2], a)


def engine_id(pref):
    items = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    order = ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"] if pref == "EEVEE" else ["CYCLES"]
    for c in order:
        if c in items:
            return c
    return items[0]


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def setup(sc, res, frames, engine, samples, fps=30):
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * 16 / 9)
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.view_settings.exposure = 0.0
    except Exception:
        pass
    eng = engine_id(engine)
    sc.render.engine = eng
    if eng == "CYCLES":
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.max_bounces = 8
        try:
            sc.cycles.device = "GPU"
        except Exception:
            pass
    else:
        ev = sc.eevee
        for attr, val in (("taa_render_samples", samples), ("use_bloom", True),
                          ("use_gtao", True), ("use_ssr", True), ("use_motion_blur", True)):
            if hasattr(ev, attr):
                try:
                    setattr(ev, attr, val)
                except Exception:
                    pass
    return sc


def world(sc, color="000000", strength=1.0):
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = srgb(color)
    bg.inputs[1].default_value = strength
    return w


def camera(sc, loc, look=(0, 0, 0), lens=70):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    cam = bpy.data.objects.new("Cam", cd)
    sc.collection.objects.link(cam)
    cam.location = loc
    sc.camera = cam
    tgt = bpy.data.objects.new("Target", None)
    sc.collection.objects.link(tgt)
    tgt.location = look
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam, tgt


def area(sc, loc, rot, energy, size=3.0, color="FFFFFF"):
    d = bpy.data.lights.new("A", "AREA")
    d.energy = energy
    d.size = size
    d.color = srgb(color)[:3]
    o = bpy.data.objects.new("A", d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    return o


def emissive(name, color, strength=6.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = srgb(color)
    e.inputs[1].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], out.inputs[0])
    return m


def principled(name, color=None, rough=0.35, metal=0.0, image=None, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    if image:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(str(image))
        try:
            tex.image.colorspace_settings.name = "sRGB"
        except Exception:
            pass
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    elif color:
        b.inputs["Base Color"].default_value = srgb(color)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for key in ("Specular IOR Level", "Specular"):
        if key in b.inputs:
            b.inputs[key].default_value = spec
            break
    return m


def bevel(ob, width=0.004, segments=3):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    return m


def shade_smooth(ob):
    for p in ob.data.polygons:
        p.use_smooth = True


def _fcurves(ad):
    act = ad.action
    if act is None:
        return []
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    slot = getattr(ad, "action_slot", None)
    for layer in getattr(act, "layers", []):
        for strip in getattr(layer, "strips", []):
            cb = None
            try:
                cb = strip.channelbag(slot) if slot else None
            except Exception:
                cb = None
            if cb is None:
                for c in getattr(strip, "channelbags", []):
                    out += list(c.fcurves)
            else:
                out += list(cb.fcurves)
    return out


def kf(ob, path, frames_vals, interp="BEZIER", index=-1):
    for f, v in frames_vals:
        if index >= 0:
            getattr(ob, path)[index] = v
        else:
            setattr(ob, path, v)
        ob.keyframe_insert(data_path=path, frame=f, index=index)
    ad = ob.animation_data
    if ad:
        for fc in _fcurves(ad):
            for k in fc.keyframe_points:
                k.interpolation = interp
                k.easing = "EASE_IN_OUT"


# ---------------------------------------------------------------- R01 LIGHT

def build_light(sc, frames):
    world(sc, "000000", 0.0)
    W, Hh, D = 1.294, 1.0, 0.115
    bpy.ops.mesh.primitive_cube_add(size=1)
    bk = bpy.context.object
    bk.name = "Book"
    bk.scale = (W, D, Hh)
    bpy.ops.object.transform_apply(scale=True)
    bevel(bk, 0.012, 4)

    cover = ASSETS / "book2_cover.png"
    spine = ASSETS / "book2_spine.png"
    m_cov = principled("cover", image=cover if cover.exists() else None,
                       color=None if cover.exists() else BOOK2, rough=0.33, spec=0.6)
    m_back = principled("back", color="98AEC9", rough=0.38)
    m_spine = principled("spine", image=spine if spine.exists() else None,
                         color=None if spine.exists() else "98AEC9", rough=0.38)
    m_page = principled("pages", color="F2EDE2", rough=0.75)
    for m in (m_cov, m_back, m_spine, m_page):
        bk.data.materials.append(m)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in bk.data.polygons:
        n = p.normal
        if n.y < -0.5:
            p.material_index = 0
        elif n.y > 0.5:
            p.material_index = 1
        elif n.x < -0.5:
            p.material_index = 2
        else:
            p.material_index = 3

    bk.rotation_euler = Euler((0, 0, math.radians(-20)))

    key = area(sc, (-3.2, -2.2, 1.4), (math.radians(62), 0, math.radians(-52)), 230, 2.8)
    kf(key, "location", [(1, (-3.6, -2.6, 1.5)), (frames, (3.6, -2.6, 2.1))])
    kf(key, "rotation_euler", [(1, Euler((math.radians(62), 0, math.radians(-62)))),
                               (frames, Euler((math.radians(62), 0, math.radians(56))))])
    area(sc, (2.9, 2.6, 2.4), (math.radians(120), 0, math.radians(142)), 110, 2.0, "CFE0FF")
    area(sc, (0, -4.6, -1.4), (math.radians(-18), 0, 0), 45, 6.0, "8FA8C8")

    cam, tgt = camera(sc, (0, -3.0, 0.35), (0, 0, 0.0), 45)
    r = 3.15
    a0, a1 = math.radians(-14), math.radians(8)
    kf(cam, "location", [(1, (r * math.sin(a0), -r * math.cos(a0), 0.62)),
                         (frames, (r * math.sin(a1), -r * math.cos(a1), 0.16))])
    kf(cam.data, "lens", [(1, 43), (frames, 49)])
    return sc


# ------------------------------------------------------------ R02 CLOSED SET

def build_closed_set(sc, frames):
    world(sc, "05060A", 1.0)
    random.seed(7)
    specs = [(-1.05, -0.15, 2.10, GOOSKLERF[0], 0.84),
             (0.15, 0.55, 3.05, GOOSKLERF[1], 1.02),
             (1.25, -0.35, 1.55, GOOSKLERF[2], 0.72)]
    for i, (x, y, z0, col, s) in enumerate(specs):
        bpy.ops.mesh.primitive_cube_add(size=s)
        d = bpy.context.object
        d.name = "Die%d" % i
        bevel(d, s * 0.14, 6)
        shade_smooth(d)
        d.data.materials.append(principled("die%d" % i, col, rough=0.28, spec=0.85))
        land = -0.62 + s / 2
        kf(d, "location", [(1, (x, y, z0 + 2.4)), (int(frames * 0.52), (x, y, land + s * 0.55)),
                           (int(frames * 0.66), (x, y, land)), (frames, (x, y, land))])
        rx, ry, rz = random.uniform(2, 5), random.uniform(2, 5), random.uniform(2, 5)
        kf(d, "rotation_euler",
           [(1, Euler((0, 0, 0))),
            (int(frames * 0.66), Euler((rx, ry, rz))),
            (frames, Euler((rx + 0.06, ry + 0.04, rz + 0.05)))])

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.62))
    bpy.context.object.data.materials.append(principled("floor", "05060A", rough=0.30, spec=0.45))

    for i, col in enumerate(GOOSKLERF):
        ang = math.radians(90 + i * 120)
        a = area(sc, (5.6 * math.cos(ang), 5.6 * math.sin(ang), 3.0),
                 (math.radians(58), 0, ang + math.pi / 2), 600, 2.6, col)
        kf(a.data, "energy", [(1, 260), (int(frames * 0.64), 1100), (frames, 520)])
    area(sc, (0, -2.0, 7.0), (0, 0, 0), 420, 4.0, "FFFFFF")
    area(sc, (0, -7.5, 1.4), (math.radians(80), 0, 0), 160, 5.0, "E8F0FF")

    cam, tgt = camera(sc, (0, -7.4, 0.9), (0, 0, 0.15), 45)
    kf(cam, "location", [(1, (-1.9, -7.6, 3.1)), (frames, (1.5, -7.0, 0.30))])
    kf(tgt, "location", [(1, (0, 0, 1.5)), (frames, (0, 0, 0.0))])
    kf(cam.data, "lens", [(1, 42), (frames, 52)])
    return sc


# ---------------------------------------------------------------- R03 BRICK

def build_brick(sc, frames):
    world(sc, "000000", 0.0)
    bpy.ops.mesh.primitive_cube_add(size=1)
    b = bpy.context.object
    b.name = "Brick"
    b.scale = (0.95, 0.46, 0.27)
    bpy.ops.object.transform_apply(scale=True)
    bevel(b, 0.022, 4)
    bpy.ops.object.modifier_add(type="SUBSURF")
    b.modifiers["Subdivision"].levels = 2
    b.modifiers["Subdivision"].render_levels = 2

    m = principled("brickmat", "7A2E1E", rough=0.72, spec=0.22)
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 52.0
    nz.inputs["Detail"].default_value = 8.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.42
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = srgb("5E2419")
    ramp.color_ramp.elements[1].color = srgb("94371F")
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    b.data.materials.append(m)
    b.rotation_euler = Euler((0, 0, math.radians(-24)))
    kf(b, "rotation_euler", [(1, Euler((0, 0, math.radians(-40)))),
                             (frames, Euler((0, 0, math.radians(26))))], interp="LINEAR")

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.30))
    bpy.context.object.data.materials.append(principled("gnd", "070707", rough=0.34, spec=0.5))

    area(sc, (-2.6, -2.2, 2.6), (math.radians(52), 0, math.radians(-46)), 1050, 2.4)
    rim = area(sc, (2.9, 2.4, 1.4), (math.radians(104), 0, math.radians(130)), 1100, 1.4, "FFE2B8")
    area(sc, (2.6, -2.8, 0.3), (math.radians(84), 0, math.radians(58)), 330, 2.0, "9FC4FF")
    kf(rim.data, "energy", [(1, 420), (int(frames * 0.5), 1500), (frames, 700)])

    cam, tgt = camera(sc, (0, -3.1, 0.34), (0, 0, 0.0), 45)
    kf(cam, "location", [(1, (-0.45, -3.25, 0.92)), (frames, (0.38, -2.95, 0.10))])
    kf(cam.data, "lens", [(1, 42), (frames, 50)])
    return sc


# -------------------------------------------------------- R04 STANDING ORDER

def build_standing(sc, frames):
    world(sc, "07070A", 1.0)
    random.seed(19)
    sheets = sorted(ASSETS.glob("sheet_*.png"))
    mats = []
    for i, p in enumerate(sheets):
        mats.append(principled("sheet%d" % i, image=p, rough=0.85, spec=0.2))
    if not mats:
        mats = [principled("paper", "FFFFFF", rough=0.85, spec=0.2)]

    N = 150
    for i in range(N):
        t = i / N
        ang = t * math.pi * 7.5 + random.uniform(-0.12, 0.12)
        rad = 1.15 + 0.55 * math.sin(t * math.pi * 2.2) + random.uniform(-0.06, 0.06)
        z = -5.5 + t * 13.0
        bpy.ops.mesh.primitive_plane_add(size=1)
        s = bpy.context.object
        s.scale = (0.62, 0.80, 1)
        s.location = (rad * math.cos(ang), rad * math.sin(ang), z)
        s.rotation_euler = Euler((math.radians(90 + random.uniform(-16, 16)),
                                  random.uniform(-0.25, 0.25), ang + math.pi / 2))
        s.data.materials.append(mats[i % len(mats)])
        kf(s, "rotation_euler",
           [(1, s.rotation_euler.copy()),
            (frames, Euler((s.rotation_euler.x + random.uniform(-0.2, 0.2),
                            s.rotation_euler.y + random.uniform(-0.2, 0.2),
                            s.rotation_euler.z + 0.42)))], interp="LINEAR")

    for i, col in enumerate([BOOK2, GOOSKLERF[0], RESERVE, BOOK1]):
        ang = math.radians(i * 90)
        area(sc, (5.4 * math.cos(ang), 5.4 * math.sin(ang), -2.0 + i * 2.2),
             (math.radians(74), 0, ang + math.pi / 2), 150, 4.0, col)
    area(sc, (0, -4.6, 3.0), (math.radians(70), 0, 0), 250, 7.0, "FFFFFF")
    area(sc, (0, -4.6, -3.0), (math.radians(70), 0, 0), 200, 7.0, "FFFFFF")

    cam, tgt = camera(sc, (0, -4.2, -3.2), (0, 0, 0), 30)
    kf(cam, "location", [(1, (0.5, -4.35, -5.0)), (frames, (-0.5, -3.85, 5.2))], interp="LINEAR")
    kf(tgt, "location", [(1, (0, 0, -3.2)), (frames, (0, 0, 6.6))], interp="LINEAR")
    return sc


# ------------------------------------------------------------- R05 SPECTRUM

def build_spectrum(sc, frames):
    world(sc, "020204", 1.0)
    random.seed(3)
    ring = 22
    layers = 9
    for L in range(layers):
        z = -4.0 + L * 1.0
        rad = 1.5 + 0.42 * math.sin(L * 0.8)
        col = SPECTRUM[L % len(SPECTRUM)]
        mat = principled("spec%d" % L, col, rough=0.17, spec=1.0, metal=0.15)
        emi = emissive("glow%d" % L, col, 3.2)
        for i in range(ring):
            a = (i / ring) * math.tau + L * 0.19
            bpy.ops.mesh.primitive_cube_add(size=1)
            o = bpy.context.object
            o.scale = (0.085, 0.085, 0.62 + 0.3 * math.sin(i * 0.7 + L))
            o.location = (rad * math.cos(a), rad * math.sin(a), z)
            o.rotation_euler = Euler((math.radians(90), a * 1.4, a + math.pi / 2))
            bevel(o, 0.018, 3)
            shade_smooth(o)
            o.data.materials.append(emi if i % 6 == 0 else mat)
            kf(o, "rotation_euler",
               [(1, o.rotation_euler.copy()),
                (frames, Euler((o.rotation_euler.x, o.rotation_euler.y + 1.1,
                                o.rotation_euler.z + (1.7 if L % 2 else -1.7))))],
               interp="LINEAR")
            kf(o, "location",
               [(1, o.location.copy()),
                (frames, (rad * 1.55 * math.cos(a + 0.9), rad * 1.55 * math.sin(a + 0.9), z + 0.5))])

    for i, col in enumerate(SPECTRUM):
        a = (i / len(SPECTRUM)) * math.tau
        area(sc, (5.2 * math.cos(a), 5.2 * math.sin(a), 1.2 + i * 0.4),
             (math.radians(72), 0, a + math.pi / 2), 900, 3.2, col)

    cam, tgt = camera(sc, (0, -5.0, 0), (0, 0, 0), 30)
    kf(cam, "location", [(1, (0.3, -6.4, -3.2)), (frames, (-0.3, -4.6, 3.8))], interp="LINEAR")
    kf(tgt, "location", [(1, (0, 0, -1.5)), (frames, (0, 0, 3.0))], interp="LINEAR")
    kf(cam.data, "lens", [(1, 24), (frames, 34)])
    return sc


SCENES = {"light": build_light, "closed_set": build_closed_set, "brick": build_brick,
          "standing": build_standing, "spectrum": build_spectrum}


def render(name, outdir, res, frames, engine, samples):
    sc = reset()
    setup(sc, res, frames, engine, samples)
    SCENES[name](sc, frames)
    out = Path(outdir) / name
    out.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out) + "/f"
    bpy.ops.render.render(animation=True)
    n = len(list(out.glob("f*.png")))
    print("RENDERED %s -> %s (%d frames, %s)" % (name, out, n, sc.render.engine))
    return out


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=1080)
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--engine", default="EEVEE")
    ap.add_argument("--samples", type=int, default=64)
    a = ap.parse_args(argv)
    for s in (SCENES if a.scene == "all" else [a.scene]):
        render(s, a.out, a.res, a.frames, a.engine, a.samples)


if __name__ == "__main__":
    main()
