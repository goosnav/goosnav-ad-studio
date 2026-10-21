# Retro-world starter builder

`blender/worlds.py` builds three original, reusable environments with Blender 4.0:

| `--world` | Set and details | Default palette |
| --- | --- | --- |
| `industrial-service-room` | Cutaway maintenance room, pressure tanks, console, vents, floor trench, service door | `oxide` |
| `remote-outpost` | Relay bunker, antenna, solar panels, landing pad, supply cases, layered rock horizon | `arctic` |
| `overgrown-courtyard` | Ruined archway, garden beyond, planters, vines, bench, broken columns, drainage channel | `moss` |

The style uses modest faceted geometry, broad silhouettes, stepped procedural color,
and visible foreground/background separation. It draws on early exploration games'
spatial language without copying their assets. There is no dithering requirement,
external service, asset download, or implicit library search.

Default bundles contain only the environment, product plinth, and stable
`anchor.product` empty. No dummy product, placeholder mesh, or demo artwork is
generated. Product geometry appears only when a caller explicitly supplies a
`.blend` asset or image. Images become flat artwork cards, not generic product boxes.

## Run

From this project, with Blender on `PATH`:

```sh
blender -b --factory-startup --python-exit-code 1 \
  --python blender/worlds.py -- \
  --world industrial-service-room \
  --output ./build/environments/starter-industrial-service-room/starter-industrial-service-room.blend \
  --preview
```

The script can also be copied elsewhere and invoked by its new path. It has no
project imports, embedded library layout, configuration dependency, or machine paths.
`--output` accepts a directory or an exact `.blend` filename, including spaces.
When given a directory, the basename is the selected world name. Parent directories
are created. Existing artifacts cause failure unless `--overwrite` is explicit;
an input asset can never also be the output file. Use `--python-exit-code 1` so
Blender reports Python failures to automation.

For an economical software-rendered EEVEE preview on Linux with Mesa:

```sh
LIBGL_ALWAYS_SOFTWARE=1 blender -b --factory-startup --python-exit-code 1 \
  --python blender/worlds.py -- \
  --world remote-outpost --output ./build/outpost --preview \
  --resolution 768 480 --samples 24 --threads 4
```

EEVEE needs a working OpenGL context, which may be supplied by a display or a
headless driver. It does not require NVIDIA. If OpenGL is unavailable, select
`--engine cycles`; this explicitly selects CPU rendering, three bounces, and no
denoiser, so builds of Blender without OpenImageDenoise also work. `--threads`
limits Blender render threads; Mesa may use its own worker count. Rendering is
optional: omit `--preview` for scene, GLB, metadata, and manifest only.

## Controls

| Option | Values / default | Effect |
| --- | --- | --- |
| `--seed` | Integer, `7` | Local deterministic geometry variation and procedural texture seed |
| `--palette` | `oxide`, `arctic`, `moss`; world-specific default | Concrete, metal, foliage, soil, accent, and emission colors |
| `--light` | `day`, `dusk`, `emergency`; `day` | Key/fill colors, light energy, and world ambient |
| `--light-strength` | Positive number, `1` | Scales light and ambient energy |
| `--camera` | `wide`, `stage`, `product`; `wide` | Selects the saved/rendered camera; all three are retained |
| `--product-position` | Three finite numbers, `0 -0.35 0.9` | Product base position in meters; moves its plinth too |
| `--product-yaw` | Degrees, `0` | Rotation around the upward axis |
| `--product-size` | Positive meters, `0.85` | Artwork-card height or imported product's maximum bounding-box dimension; also frames product camera |
| `--product-texture` | Explicit image file | Packs supplied artwork on a flat card at the anchor |
| `--product-blend` | Explicit trusted `.blend` file | Appends a static product, centers it, scales it, places its bottom at the anchor |
| `--product-collection` | Collection name | Selects a collection inside the supplied product `.blend` |
| `--engine` | `eevee`, `cycles`; `eevee` | EEVEE with economical AO/shadows, or Cycles CPU |
| `--resolution` | Two positive integers, `768 480` | Preview dimensions |
| `--samples` | Positive integer, `32` | EEVEE render samples or Cycles samples |
| `--threads` | Positive integer, `4` | Blender render thread count |
| `--preview` | Flag | Renders the selected camera to PNG |
| `--overwrite` | Flag | Allows replacing the exact named output artifacts |

Example product framing:

```sh
blender -b --factory-startup --python-exit-code 1 \
  --python blender/worlds.py -- \
  --world overgrown-courtyard --output ./build/product-shot.blend \
  --palette moss --light dusk --camera product \
  --product-texture ./inputs/cover.png --product-yaw -10 --preview
```

Image and `.blend` inputs are mutually exclusive. Product `.blend` imports support
mesh/empty hierarchies; apply modifiers, shape keys, instances, poses, and animation
before exporting the source product. Use a collection when a file also contains
cameras or lights. The builder rejects unsupported object types, linked dependencies,
external caches/media, and images it cannot pack. Packed images are retained with
relative paths. Only explicitly provided product inputs are read; none are edited.
Product source filenames and SHA-256 digests are recorded without absolute paths.
Rights to supplied assets remain the caller's responsibility.

## Output contract

For an output named `starter-industrial-service-room.blend`, the sibling files are:

| File | Purpose |
| --- | --- |
| `starter-industrial-service-room.blend` | Editable scene, procedural materials, packed images, lights, cameras, anchors, embedded `world.manifest.json` text |
| `starter-industrial-service-room.glb` | Self-contained glTF 2.0 geometry, palette PBR materials, supported image textures, cameras, anchor nodes and role extras |
| `starter-industrial-service-room.build.json` | Resolved settings, object/geometry inventory, stable content hash, artifact hashes, measured build/export/render seconds and bytes |
| `starter-industrial-service-room.manifest.json` | Versioned catalog record, relative artifact names, provenance, bounds, capabilities, anchor transforms, portability limits |
| `starter-industrial-service-room.preview.png` | Render from the saved camera, only with `--preview` |

The GLB uses palette colors in place of Blender's procedural shader patterns. It
does not bake those patterns or reproduce Blender's lighting: a consuming application
must light it. Text signs become mesh geometry. Product image textures supported by
Blender's glTF exporter are embedded; arbitrary imported shader graphs are subject
to the exporter's material limitations. The `.blend` is the full-fidelity source.

The manifest uses schema `retro-world.asset/v1`; the build report uses
`retro-world.build/v1`. Both declare `proxy: false`, `dependencies: []`, and
`unresolved_proxies: []` only after dependency packing and proxy validation.
Objects carrying a truthy `proxy` or `is_proxy` property, or a placeholder name,
are rejected, including imported products. Their `product` record always identifies
`anchor.product`, the `Product` collection, both plinth objects, and a mode:
`anchor_only` (default), `supplied_blend`, or `supplied_image`.
`content_sha256` incorporates generator source, Blender
version, settings, source hashes, packed image hashes, and scene inventory. The
same inputs with the same script and Blender version yield the same scene-content
hash independent of output directory. `.blend`/GLB binary bytes, elapsed times,
and pixels across different graphics drivers are not promised to be identical.
Mesh triangle counts exclude tessellated text; GLB includes the converted signs.

A successful invocation prints a final `WORLD_BUILD` JSON line. Failure may leave
partial artifacts; absence of a successful exit and final record means the bundle
is incomplete. Retry into a fresh directory or explicitly overwrite that bundle.
If overwriting a previously rendered bundle without `--preview`, any old PNG is
unreferenced by the new manifest and must not be treated as a current preview.

## Scene and staging contract

The `.blend` uses meters, +Z up, and character forward -Y. GLB uses standard +Y up
and character forward +Z: `(x, y, z)` becomes `(x, z, -y)`. JSON anchor coordinates
are in Blender space. The GLB anchor extras describe its converted axes.

| Stable object | Placement / purpose |
| --- | --- |
| `anchor.character_a` | Feet at `(-2, -0.85, 0)` |
| `anchor.character_b` | Feet at `(2, -0.85, 0)` |
| `anchor.entrance` | Feet at `(0, 2, 0)`; secondary blocking target |
| `anchor.look_at` | Gaze target at `(0, 0.2, 1.4)` |
| `anchor.product` | Product bottom at the configured position |
| `camera.wide` | Establishing view with environment detail |
| `camera.stage` | Closer framing for staged characters |
| `camera.product` | Frames the configured product anchor and size |

Character A/B locations reserve approximately 0.55 m radius and 1.9 m height at
default product placement. The automated check verifies a 1 x 1 x 1.85 m body
box there. Custom product placement may obstruct those spaces. The product plinth
is 0.9 m tall; changing the anchor height moves it vertically without resizing it.
Large props and arbitrary camera moves require normal scene blocking checks.

Collections are `Architecture`, `Details`, `Vegetation`, `Product`, `Staging`,
`Cameras`, and `Lighting`. No characters, animation, collision meshes, navigation
meshes, or game-specific export bindings are included. Empties are staging aids,
not visible stand-in characters. Parent a character root to the matching anchor
with local location zero, or copy its world matrix while preserving your rig setup.

The Python entry point is `build(parse_args([...]))`, intended for Blender Python.
It resets the current scene with factory-empty settings. Run it in a dedicated
background Blender process; do not call it inside unsaved interactive work.

## Measured actor placement and camera fitting

`blender/staging.py` is a separate, reusable Blender-Python helper. It does not reset
the scene, choose shots, create animation, or search an asset library. Import it from
the configured repository's `blender` directory in a background Blender process
started with `--disable-autoexec --python-exit-code 1`.

```python
import bpy
import staging

scene = bpy.context.scene
# `camera` is the worker's chosen/created camera object.
# Paths come from the accepted catalog. Coordinates are destination world meters.
actor_a = staging.import_actor(character_path, "actor.A", (-1.0, 0, 0), 1.8)
actor_b = staging.import_actor(other_path, "actor.B", (1.0, .4, 0), 1.65,
                               rig_name="actual_source_armature")
rig_a = bpy.data.objects[actor_a["staging_rig"]]

# The worker chooses lens, render aspect, direction, margin and subjects.
scene.render.resolution_x, scene.render.resolution_y = 540, 675
camera.data.lens = 50
report = staging.frame_subjects(camera, [actor_a, actor_b], margin=.08,
                                view_direction=(0, 1, -.15))
assert report["all_inside_margin"]
# Persist report with the board, then visually inspect the actual render.
```

`import_actor(sourceblend, name, location, height_m, *, rig_name=None)` returns a
placement Empty. `name` is its destination name; `rig_name` is an optional **source**
armature name. A multi-rig source must specify it; the helper never silently chooses
the first rig. Only that rig, meshes bound by parenting or armature modifiers, and
needed structural/control empties enter the destination scene. Unrelated actors,
scenery, cameras and lights are discarded. Dependencies on another rig or scenery
fail explicitly. Use a local, self-contained actor source; linked rig/mesh data is
rejected. This helper is for actors, not arbitrary scene or product imports.

Normalization measures evaluated mesh vertices, including active shape keys,
modifiers, poses, source offsets and nonuniform scales. At the **current frame**,
XY bounds center and the lowest Z become `location`; total height becomes
`height_m`. A normalization Empty underneath the placement root applies the uniform
scale/offset. Original local transforms, parent chains, actions, NLA, skinning and
shape keys remain intact. Move/rotate the placement root, not the animated rig.
The root records `staging_rig`, `staging_height_m`, `staging_reference_frame` and
the source basename. Imported objects retain `staging_source_name` for lookup.
Each call creates a separate instance. Source files are never saved or modified;
appending does not open the source scene or execute its embedded text scripts.
Pack image/media dependencies in the final scene before publication, as usual.

`world_bounds(subjects)` returns JSON-safe `min`, `max`, `center` and `size` in
world coordinates. Pass a root, a mesh, or a list of them. Descendant mesh geometry
is included, excluding `hide_render` meshes. This is a current-frame measurement,
not an animation-envelope, collision, face-recognition or occlusion test.

`frame_subjects(camera, subjects, margin=.08, view_direction=None)` accepts the same
subjects, plus explicit `{name, min, max}` world-space regions. Without a direction,
it preserves the camera's current world rotation, including roll. A supplied vector
points **from camera toward subjects**; for example `(0, 1, -.15)` looks toward +Y
and slightly downward. The helper centers the supplied bounds and fits distance
(perspective) or `ortho_scale` (orthographic). It preserves lens, sensor settings,
shifts and render/pixel aspect; it can expand far clipping. Margin is the fraction
reserved at **each** image edge, in `[0, .5)`. Panoramic and actively constrained
cameras are rejected rather than producing an unreliable fit.

The projected report contains each subject's world bounds, `projected_min` and
`projected_max` (X/Y normalized to the image, Z in camera-depth units),
`inside_margin`, and overall `all_inside_margin`. Its validation explicitly covers
only current-frame frustum containment. Being inside the image does **not** prove
that a wall isn't hiding the face, the actor faces the camera, or the framing is
large enough for a phone. Still render and review every board.

For a deliberately chosen close-up, pass a separate head mesh, or derive an explicit
region without pretending it is an automatically detected face:

```python
b = staging.world_bounds(actor_a)
upper_body = {"name": "A upper body", "min": b["min"][:], "max": b["max"][:]}
upper_body["min"][2] += .65 * b["size"][2]  # worker-chosen crop, not a helper rule
report = staging.frame_subjects(camera, [upper_body], .1, view_direction=(.3, 1, -.1))
```

For a dialogue two-shot, stage the partners near each other and fit both upper-body
regions, not the entire set or distant environment spawn anchors:

```python
conversation = []
for name, actor in (("A", actor_a), ("B", actor_b)):
    b = staging.world_bounds(actor)
    region = {"name": name, "min": b["min"][:], "max": b["max"][:]}
    region["min"][2] += .5 * b["size"][2]  # chosen waist-up crop
    conversation.append(region)
staging.frame_subjects(camera, conversation, .08, view_direction=(.3, 1, -.05))
```

Choose the horizontal direction for the actual actors' orientation; this example
is not a universal facing direction. Start near eye level rather than looking
down at the tops of heads. Inspect a delivery-size frame: both expressions should
be legible. More ambitious staging remains available when it serves the exchange.

For a moving shot, measure the intended poses/frames and fit their union as an
explicit region, or author the camera motion deliberately and inspect its framing.
Do not refit every animation frame automatically: that can introduce camera pumping.
These primitives work for reused low-effort shots and custom high-effort angles;
they impose no new look, cuts, choreography or composition policy.

Tests use only synthetic files in temporary directories:

```sh
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_staging.py --durations=5
```

Each real Blender invocation has a 45-second bound. Checks cover source hashing,
rig/mesh hierarchy, independent imports, shape keys/NLA, offset and scaled geometry,
ambiguous rigs, portrait perspective/orthographic projection, camera shifts,
non-square pixels, chosen angles and explicit upper-body regions. They inspect
actual projected vertices independently of the helper's own report.

## Dialogue motion cues

`blender/performance.py` consumes the active asset library's declarative
`scripts/conversation_motion.py` bank. The caller supplies the library root from
configuration/catalog resolution, or supplies model paths whose ancestor contains
that file. There is no machine path or sibling-checkout fallback, and archived
paths are rejected. The adapter reads a literal `BANK` with `ast.literal_eval`;
it never executes asset-library Python. Keep the bank with the selected active
library when relocating it. The managed submodule contains the bank; an older
external checkout may not.

```python
import performance

# timeline/mouths are accepted measured audio artifacts (paths or dictionaries).
# rigs maps speaker IDs to actual imported armatures (objects or names).
report = performance.apply(
    timeline, mouths, rigs,
    models={"A": character_path, "B": other_path},
    library_root=active_library_root,
    cues=[
        {"speaker": "A", "kind": "talk", "start": 0, "end": 2},
        {"speaker": "B", "kind": "listen", "start": 0, "end": 2},
        {"speaker": "A", "kind": "gesture", "start": .5, "end": 1.5},
        {"speaker": "B", "kind": "look_at", "start": 0, "end": 2, "target": "A"},
        {"speaker": "B", "kind": "talk", "start": 2, "end": 4},
    ],
)
```

Times are seconds from the measured timeline start, not absolute scene frames.
Adjust these example windows to the actual accepted dialogue. All cues must fit
the timeline. Optional `intensity` is in [0, 1]. Request `talk` for each intended
speaking window; it is gated by that speaker's actual dialogue. `listen` supplies
quiet idle. `gesture` uses the existing take once, fitted to its window. `look_at`
accepts another speaker or a fixed Blender-world XYZ point. Speaker gaze targets
are sampled at the beginning of the bake, not tracked continuously.

For ordinary conversation, avoid hand-writing speaking windows:

```python
cues = performance.conversation_cues(timeline, speakers=rigs)
# Optional: append one deliberately timed gesture for a meaningful line.
report = performance.apply(timeline, mouths, rigs, models=models,
                           library_root=active_library_root, cues=cues)
```

`conversation_cues(timeline, speakers=None)` accepts a timeline path or dictionary.
It merges adjacent/overlapping lines, fills each actor's listen gaps and adds mild
listener gaze during another actor's line. Omit `speakers` to infer the speaking
cast; pass IDs or the rig map to include silent listeners. It does not generate
speech or automatic gestures, and it does not change Blender state. A listener
missing from `mouths["speakers"]` gets an explicit closed-mouth curve.

`walk` reuses the in-place take at its source 24 fps, including when rendering at
30 fps. Author placement-root travel separately (roughly 0.4 m/s times actor scale
for the native cycle). There is no navigation, prop contact or hand IK inference.
Prefer a simple planted conversation when travel adds nothing to the dialogue.

Cue motion is baked into a single owned composite action, leaving authored action,
active NLA and driver channels protected. Idle and cues are offsets from the
existing pose; constraint settings and non-XYZ bone rotations are preserved.
`report[speaker]["skipped_authored_paths"]` identifies channels that the adapter
could not own. Check it when an intentional cue is not visible. Measured mouth
curves run last and own the jaw/visemes. Body recipes never open mouths. Each
actor's face data is isolated so speech does not leak across instances.

Repeated `apply` calls replace generated channels and preserve the original
baseline across save/reopen. Pass `cues=[]` to remove prior cue motion while
keeping quiet idle and measured speech. Omit `cues` to retain the legacy idle/nod
behavior. Use cues for composed conversation instead of layering `play_clip`
after `apply`; the older raw-NLA helper can be masked by an active body action.
Exact duplicate cues are deduplicated; same-kind overlaps and talk/listen overlap
on one speaker fail explicitly. The existing bank's character catalog capabilities
remain unchanged: these are consumer recipes, not newly embedded character takes.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  -p no:cacheprovider tests/harness/test_motion_bank.py \
  tests/harness/test_performance.py tests/harness/test_performance_pose.py
```

Set `MOTION_REVIEW=1` for three optional 360x450 review stills under pytest's
temporary output directory. Checks evaluate visible hand/head/foot movement,
silent-mouth ownership, source fps, protected authored channels, repeat/reopen,
relocated libraries and refusal to execute a nonliteral bank. Preview stills are
visual evidence only; review dialogue timing on the parent's finished ad trials.

## Publication boundary

This builder does not modify or search any configured asset checkout or submodule.
Generate into a temporary staging directory and let the asset-library owner publish
reviewed bundles with distinct starter names. A shallow `category/asset/file`
layout works directly with the exact output filename option, for example:

```text
environments/starter-industrial-service-room/starter-industrial-service-room.blend
environments/starter-remote-outpost/starter-remote-outpost.blend
environments/starter-overgrown-courtyard/starter-overgrown-courtyard.blend
```

Each asset's GLB, JSON records, and preview sit beside its `.blend`. The generator
can live in the destination library's top-level scripts area without code changes.
Publication, licensing decisions, catalog registration, commits, and pushes belong
to the library owner. No in-progress user environment builds are reused.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/test_worlds.py --durations=10
```

The suite skips only when Blender is absent. Each real Blender subprocess is bounded
to 90 seconds (120 for the Cycles fallback). It renders all three worlds at 320x200,
reopens saved scenes, checks staging clearance and camera framing, validates the GLB
container/cameras/anchors/embedded dependencies, compares deterministic rebuilds,
checks custom options and collision protection, and verifies image/mesh imports
after removing their temporary source files. It rejects proxy-marked imports,
checks that default Blender/GLB outputs contain no demo product, and renders a
packed image in EEVEE after deleting its source. It also renders with Cycles CPU with
display environment variables removed. All test artifacts are generated under
pytest temporary directories. The tested target is Blender 4.0; later EEVEE API
changes may require adapting engine identifiers or shadow settings.

Measured on Blender 4.0.2, Intel i7-6700, Mesa software EEVEE, 768x480,
24 samples, four Blender render threads (process startup excluded):

| Starter | Mesh triangles | Build including GLB | Preview render | `.blend` / GLB bytes |
| --- | ---: | ---: | ---: | ---: |
| Industrial service room | 1,764 | 0.567 s | 3.202 s | 123,620 / 205,340 |
| Remote outpost | 1,624 | 0.584 s | 3.755 s | 127,430 / 170,160 |
| Overgrown courtyard | 3,420 | 0.768 s | 3.329 s | 159,360 / 397,816 |

These environment-only bundles contain no demo product. The owned test suite
passed all ten cases in 40.35 seconds. These are reference
measurements on a shared machine, not performance guarantees. Current per-build
measurements and artifact hashes are always recorded in the build JSON.
