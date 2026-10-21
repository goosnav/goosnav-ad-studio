"""Bounded real-Blender integration checks; all generated files stay under tmp_path.

Run: PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_worlds.py
Requires Blender 4.0+. Missing Blender skips the suite, never mocks a successful build.
"""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "blender" / "worlds.py"
BLENDER = shutil.which("blender")
WORLDS = ("industrial-service-room", "remote-outpost", "overgrown-courtyard")
pytestmark = pytest.mark.skipif(not BLENDER, reason="requires real Blender")


def run_blender(arguments, timeout=90, no_display=False):
    env = dict(os.environ, LIBGL_ALWAYS_SOFTWARE="1", PYTHONDONTWRITEBYTECODE="1")
    if no_display:
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", *arguments],
                            capture_output=True, text=True, timeout=timeout, env=env)
    assert result.returncode == 0, result.stdout[-10000:] + result.stderr[-5000:]
    return result.stdout


def run_check(tmp_path, body, timeout=90, no_display=False):
    script = tmp_path / "check.py"
    script.write_text("import sys\nsys.dont_write_bytecode = True\n"
                      + f"sys.path.insert(0, {str(SCRIPT.parent)!r})\n"
                      + "import worlds, bpy, json\nfrom pathlib import Path\n"
                      + f"root = Path({str(tmp_path)!r})\n" + body)
    return run_blender(["--python", str(script)], timeout, no_display=no_display)


@pytest.mark.parametrize("world", WORLDS)
def test_cli_render_saved_contract_and_clear_staging(tmp_path, world):
    output = tmp_path / "directory with spaces" / "custom.scene.blend"
    stdout = run_blender(["--python", str(SCRIPT), "--", "--world", world,
                          "--output", str(output), "--preview", "--resolution", "320", "200",
                          "--samples", "8", "--threads", "2"])
    assert "WORLD_BUILD " in stdout
    meta = json.loads(output.with_suffix(".build.json").read_text())
    manifest = json.loads(output.with_suffix(".manifest.json").read_text())
    assert meta["inventory"]["object_count"] < 400
    assert 500 < meta["inventory"]["mesh_triangles"] < 15000
    assert meta["measurements"]["preview_seconds"] > 0
    assert output.stat().st_size < 2_000_000
    assert manifest["content_sha256"] == meta["content_sha256"]
    assert manifest["provenance"]["external_inputs"] == []
    for record in (meta, manifest):
        assert record["proxy"] is False and record["dependencies"] == []
        assert record["unresolved_proxies"] == []
        assert record["product"]["anchor"] == "anchor.product"
        assert record["product"]["mode"] == "anchor_only"
    assert all(not Path(p).is_absolute() for p in manifest["artifacts"].values())
    assert {a["name"] for a in manifest["anchors"]} == {
        "anchor.product", "anchor.character_a", "anchor.character_b", "anchor.entrance", "anchor.look_at"}
    png = output.with_suffix(".preview.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (320, 200)
    assert len(png) > 5000
    glb = output.with_suffix(".glb").read_bytes()
    assert struct.unpack("<4sII", glb[:12]) == (b"glTF", 2, len(glb))
    length, kind = struct.unpack("<I4s", glb[12:20])
    assert kind == b"JSON"
    gltf = json.loads(glb[20:20 + length])
    assert len(gltf["cameras"]) == 3
    assert all("uri" not in entry for entry in gltf.get("buffers", []) + gltf.get("images", []))
    nodes = {n["name"]: n for n in gltf["nodes"]}
    assert nodes["anchor.character_a"]["extras"]["role"] == "character_feet"
    assert nodes["anchor.character_a"]["extras"]["up_axis"] == "+Y"
    assert {n for n in nodes if n.startswith("product.")} == {"product.plinth", "product.plinth.rim"}
    assert not any(n.get("extras", {}).get("proxy") or n.get("extras", {}).get("is_proxy") for n in nodes.values())
    assert any(name.endswith(".portable") for name in nodes)
    assert any(m["pbrMetallicRoughness"]["baseColorFactor"][0] < .4 for m in gltf["materials"])
    # Reopen the actual deliverable and test scene contracts independently of JSON.
    run_check(tmp_path, f'''
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
bpy.ops.wm.open_mainfile(filepath={str(output)!r})
scene = bpy.context.scene
assert scene.camera.name == "camera.wide"
assert scene.world and scene.render.engine == "BLENDER_EEVEE"
assert not bpy.data.libraries
assert not bpy.utils.blend_paths(absolute=True, packed=False)
assert not any(o.get("proxy") or o.get("is_proxy") or "placeholder" in o.name.lower() for o in bpy.data.objects)
assert {{o.name for o in bpy.data.collections["Product"].all_objects}} == {{"product.plinth", "product.plinth.rim"}}
assert all(i.packed_file for i in bpy.data.images if i.source == "FILE")
body = bpy.data.objects["product.plinth"]
rim = bpy.data.objects["product.plinth.rim"]
body_top = max((body.matrix_world @ Vector(p)).z for p in body.bound_box)
rim_top = max((rim.matrix_world @ Vector(p)).z for p in rim.bound_box)
assert rim_top - body_top > .06
assert abs(rim_top - bpy.data.objects["anchor.product"].location.z) < 1e-5
saved = json.loads(bpy.data.texts["world.manifest.json"].as_string())
assert saved["content_sha256"] == scene["world_content_sha256"]
assert worlds.inventory() == json.loads(Path({str(output.with_suffix('.build.json'))!r}).read_text())["inventory"]
# Top floor faces must be separated from their foundation to avoid EEVEE z-fighting.
base_name = "foundation" if {world!r} == "industrial-service-room" else "terrain.shelf" if {world!r} == "remote-outpost" else "courtyard.base"
base = bpy.data.objects[base_name]
base_top = max((base.matrix_world @ Vector(p)).z for p in base.bound_box)
assert base_top < -.005
for name in ("camera.wide", "camera.stage", "camera.product"):
    camera = bpy.data.objects[name]
    p = bpy.data.objects["anchor.product"].location + Vector((0, 0, .4))
    screen = world_to_camera_view(scene, camera, p)
    assert .05 < screen.x < .95 and .05 < screen.y < .95 and screen.z > 0
for name in ("anchor.character_a", "anchor.character_b"):
    anchor = bpy.data.objects[name]
    # A body-sized box must not intersect any original geometry above the floor.
    lo = anchor.location + Vector((-.5, -.5, .05))
    hi = anchor.location + Vector((.5, .5, 1.9))
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
        lower = [min(p[i] for p in corners) for i in range(3)]
        upper = [max(p[i] for p in corners) for i in range(3)]
        assert not all(lower[i] < hi[i] and upper[i] > lo[i] for i in range(3)), (name, obj.name)
print("REOPEN_OK")
''')


def test_determinism_seed_controls_and_collision_protection(tmp_path):
    run_check(tmp_path, '''
def make(name, *extra):
    return worlds.build(worlds.parse_args(["--output", str(root / name),
                        "--world", "overgrown-courtyard", *extra]))
first = make("one")
second = make("two")
assert first["inventory"] == second["inventory"]
assert first["content_sha256"] == second["content_sha256"]
changed = make("three", "--seed", "9")
assert changed["content_sha256"] != first["content_sha256"]
assert changed["inventory"] != first["inventory"]
custom = make("custom", "--palette", "arctic", "--light", "dusk", "--light-strength", ".7",
              "--camera", "product", "--product-position", "1", "-2", "1.2", "--product-yaw", "30")
assert bpy.context.scene.camera.name == "camera.product"
assert abs(bpy.data.objects["anchor.product"].location.z - 1.2) < 1e-5
assert abs(bpy.data.objects["anchor.product"].rotation_euler.z - worlds.math.pi / 6) < 1e-5
assert custom["settings"]["palette"] == "arctic"
before = (root / "one/overgrown-courtyard.blend").read_bytes()
try:
    make("one")
except FileExistsError:
    pass
else:
    raise AssertionError("existing output overwritten without --overwrite")
assert before == (root / "one/overgrown-courtyard.blend").read_bytes()
assert make("one", "--overwrite")["content_sha256"] == first["content_sha256"]
''')


def test_explicit_image_packed_and_survives_source_removal(tmp_path):
    run_check(tmp_path, '''
image = bpy.data.images.new("fixture", width=4, height=4)
image.generated_color = (.2, .6, .9, 1)
image.filepath_raw = str(root / "original.png")
image.file_format = "PNG"
image.save()
result = worlds.build(worlds.parse_args(["--output", str(root / "packed.blend"),
                      "--product-texture", str(root / "original.png")]))
assert result["inventory"]["object_count"] > 10
(root / "original.png").unlink()
bpy.ops.wm.open_mainfile(filepath=str(root / "packed.blend"))
images = [i for i in bpy.data.images if i.source == "FILE"]
assert len(images) == 1 and images[0].packed_file
assert not bpy.utils.blend_paths(absolute=True, packed=False)
manifest = json.loads(bpy.data.texts["world.manifest.json"].as_string())
assert manifest["provenance"]["external_inputs"][0]["kind"] == "user_image"
assert len(manifest["provenance"]["external_inputs"][0]["sha256"]) == 64
assert bpy.data.objects["product.artwork"].data.uv_layers
assert manifest["product"]["mode"] == "supplied_image"
# Exercise the EEVEE helper's dependency contract after the image source is gone.
assert not [i.name for i in bpy.data.images if i.source == "FILE" and not i.packed_file]
bpy.context.scene.render.resolution_x = 160
bpy.context.scene.render.resolution_y = 100
bpy.context.scene.eevee.taa_render_samples = 2
bpy.context.scene.render.filepath = str(root / "packed-source-removed.png")
bpy.ops.render.render(write_still=True)
assert (root / "packed-source-removed.png").is_file()
''')


def test_rejects_proxy_marked_product_imports(tmp_path):
    run_check(tmp_path, '''
for marker in ("proxy", "is_proxy"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    bpy.context.object[marker] = True
    source = root / (marker + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    output = root / (marker + "-output.blend")
    try:
        worlds.build(worlds.parse_args(["--output", str(output), "--product-blend", str(source)]))
    except ValueError as exc:
        assert "proxy objects" in str(exc)
    else:
        raise AssertionError("proxy-marked product accepted")
    assert not output.exists()
''')


@pytest.mark.parametrize("select_collection", [True, False], ids=["collection", "whole-file"])
def test_explicit_blend_hierarchy_normalized_and_self_contained(tmp_path, select_collection):
    run_check(tmp_path, f"select_collection = {select_collection!r}\n" + '''
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
collection = bpy.data.collections.new("RequestedProduct")
bpy.context.scene.collection.children.link(collection)
parent = bpy.data.objects.new("offset.parent", None)
collection.objects.link(parent)
parent.location = (4, 3, 2)
bpy.ops.mesh.primitive_cube_add(size=2, location=(5, 3, 4))
cube = bpy.context.object
for coll in list(cube.users_collection):
    coll.objects.unlink(cube)
collection.objects.link(cube)
transform = cube.matrix_world.copy()
cube.parent = parent
cube.matrix_world = transform
source = root / "supplied.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(source))
worlds.build(worlds.parse_args(["--output", str(root / "imported.blend"),
    "--product-blend", str(source), "--product-size", "1.5", "--product-position", "1", "-2", "1"] +
    (["--product-collection", "RequestedProduct"] if select_collection else [])))
source.unlink()
bpy.ops.wm.open_mainfile(filepath=str(root / "imported.blend"))
assert not bpy.data.libraries
assert not any(d.library_weak_reference for d in bpy.data.user_map())
assert not bpy.utils.blend_paths(absolute=True, packed=True)
cube = bpy.data.objects["Cube"]
points = [cube.matrix_world @ Vector(p) for p in cube.bound_box]
low = [min(p[i] for p in points) for i in range(3)]
high = [max(p[i] for p in points) for i in range(3)]
assert abs(max(high[i] - low[i] for i in range(3)) - 1.5) < 1e-5
assert abs(low[2] - 1) < 1e-5
assert abs((low[0] + high[0]) / 2 - 1) < 1e-5
assert abs((low[1] + high[1]) / 2 + 2) < 1e-5
manifest = json.loads(bpy.data.texts["world.manifest.json"].as_string())
assert not manifest["capabilities"]["original_geometry"]
assert manifest["provenance"]["external_inputs"][0]["kind"] == "user_blend"
''')


def test_cli_rejects_invalid_options_before_creating_outputs(tmp_path):
    run_check(tmp_path, '''
for bad in (["--world", "unknown"], ["--samples", "0"], ["--resolution", "-1", "200"],
            ["--light-strength", "nan"], ["--product-position", "inf", "0", "1"],
            ["--product-collection", "missing"], ["--product-blend", str(root / "missing.blend")]):
    try:
        worlds.parse_args(["--output", str(root / "must-not-exist"), *bad])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError(bad)
assert not (root / "must-not-exist").exists()
''')


def test_cycles_cpu_preview_without_display(tmp_path):
    # A real CPU fallback matters on hosts without an OpenGL display.
    run_check(tmp_path, '''
result = worlds.build(worlds.parse_args(["--output", str(root / "cpu.blend"),
    "--engine", "cycles", "--resolution", "160", "100", "--samples", "2", "--threads", "2", "--preview"]))
assert bpy.context.scene.cycles.device == "CPU"
assert (root / "cpu.preview.png").stat().st_size > 1000
assert result["measurements"]["preview_seconds"] > 0
''', timeout=120, no_display=True)
