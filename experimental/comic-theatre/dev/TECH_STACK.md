# Technology stack and reuse audit

Date: 2026-10-21. Proposed stack; no packages installed by this design change.

Implementation update: see [BUILD_CONTRACT.md](BUILD_CONTRACT.md) and
[VERIFICATION.md](VERIFICATION.md). The implemented prototype uses the simpler
template contract with explicit JavaScript validation, offline Kokoro or recordings,
and an optional OpenAI-compatible image-aware HTTP writer. Flite, CLI-agent writers,
general manifest schemas and parent-harness integration remain unimplemented ideas.

## Recommendation

Use **Node.js + Three.js + a controlled Chromium renderer + FFmpeg**. Treat each
episode as a deterministic game cutscene, not a newly authored Blender project.
Blender stays the asset/rail-authoring tool: build a working grip, page-turn or
slam once, then sample it repeatedly through JSON commands. Python supplies the
default local Kokoro voices and is unnecessary only in recorded-audio mode.
No paid API, Codex or Claude process is part of animation or normal rendering.

| Layer | Proposed choice | Reason / boundary |
| --- | --- | --- |
| CLI, jobs, compiler | Node ESM, Node >=22.12 | Matches the adjacent game's runtime floor; portable, one main language |
| Validation | JSON Schema 2020-12 + Ajv | Public authoring contract, strict errors, editor assistance |
| Rendering | Three.js WebGLRenderer | Existing Homunculus rig/face approach; modest geometry and inexpensive lighting |
| Asset interchange | GLB + JSON manifest | Portable skins/meshes, explicit capability and source metadata |
| Preview | Small loopback server + browser | Same compiled timeline and renderer as export |
| Export control | Playwright + pinned Chromium | Drive exact frame time and inspect errors; no wall-clock recording dependency |
| Encoding/mix | FFmpeg + ffprobe | H.264/AAC MP4, PCM measurement, mux, integrity checks |
| Recorded voice | User WAV/FLAC/etc decoded to PCM | Fully authored performance; no speech-model dependency |
| Optional non-neural voice | Flite adapter | No-AI animatics; not a high-quality acting promise |
| Default automatic voice | Local Python/Kokoro adapter | No paid service or agent calls; one-time explicit install/cache |
| Optional writer | Operator-configured CLI adapter | One structured draft, no agents during animation/export |
| Tests | node:test + real-browser integration | Pure timing tests plus actual rendered frames/audio/export validation |

Pin tested dependency versions in the new package lock during implementation,
including a known browser build. Homunculus currently declares Three.js 0.186.1,
playwright-core 1.62.1 and Node >=22.12.0; these are reuse candidates, not a promise
that whatever is newest will work. No floating dependency/model upgrades during
an active run. Model selection can resolve current operator policy at job creation;
receipts retain the exact model identity used for reproducibility.

## Why not another renderer?

- **Blender EEVEE:** strongest immediate reuse of Ad Studio's existing film helpers,
  but the GET YOUR OWN log reports about 2.6 seconds/frame at 540×675. That is a
  measurement from that film, not a benchmark performed here. Its bespoke scene
  scripts and renderer do not best fit the desired lightweight repeatable engine.
- **Godot:** plausible cutscene/movie runtime, but requires a new import and facial
  performance integration while the relevant game already uses Three.js.
- **AI-generated video/motion:** inconsistent identity/props, service dependency,
  cost and poor repeatability. It defeats the requested human-JSON/no-AI mode.

Three.js does not magically make video export free. Even a game-style renderer must
produce every output frame. Savings come from reusable geometry/poses, simple
lighting, cached assets, and deterministic playback—not skipping required frames.
Browser pixel transfer and encoding may dominate; benchmark those early.

## Capture implementation choice

First implement exact-time canvas capture with a browser-owned render target and
per-frame readback, writing bounded frame sequences per segment. The documented
[Three.js render-target readback API](https://threejs.org/docs/pages/WebGLRenderer)
supports an asynchronous path. For the simplest initial spike, canvas screenshots
are acceptable; measure their overhead before choosing the shipping capture path.
[Playwright screenshot controls](https://playwright.dev/docs/api/class-page#page-screenshot)
do not freeze custom WebGL animation: the renderer itself must accept explicit time.

The public API is `Player.renderAt(frameIndex)`, with an integer zero-based frame
index. It derives time internally as `frameIndex / fps`, and performance sample
as `floor(frameIndex * sampleRate / fps)`. Preview, export and resume use that same
contract. Use a fixed frame count derived from PCM duration.
GLTF clips can use an explicitly controlled
[AnimationMixer time](https://threejs.org/docs/pages/AnimationMixer.html).
No MediaRecorder as the authoritative export path: a wall-clock recorder can drop
frames under load and complicates interruption/restart. Interactive preview may
use requestAnimationFrame; offline export must not.

Start with 5-second segments and bounded frame buffering. Encode video-only
segments with identical settings and independent keyframes; concatenate in order
and mux the full measured audio once, avoiding AAC gaps at every segment boundary.
Resume by exact integer frame range. Preserve a segment only after ffprobe/decode
checks and a content-key receipt. Disk and memory budgets must be checked before
export. Avoid both an unbounded all-frames RAM buffer and millions of permanent PNGs.

Use low-cost Lambert/unlit materials, nearest-filtered world textures where
appropriate, restrained fog, static contact shadows and a few lamps. Source-art
inserts use a separate readability-preserving pass: do not dither or downsample
lettering into illegibility to achieve a retro look. The 2002 atmosphere belongs
in staging/light/palette, not random visual damage to the comic.

## Actual reuse evidence

Inspected Homunculus commit: `e52576f96f9d2fdb2a0190cd825cb5081e6cdc68`.
Inspected asset submodule checkout: `0b1bccff8e78a5ef2591adfe1170dd1255ea9216`.
These are audit identifiers, not pinned application source paths.

| Existing material | What it provides | What must change / remain separate |
| --- | --- | --- |
| Homunculus `web/room.js` | Rest-relative bone poses, sitting, gestures, gaze, inexpensive world rendering | Extract actor-only logic; remove wall clock, random fidgets, UI, single-resident assumptions and delta-dependent smoothing |
| Homunculus `web/browser-room.js` | Head-attached mouth geometry and eyebrows on sealed-face character | Extract face rig; replace sine-wave “speech” with measured per-speaker audio; do not inherit gameplay states |
| Homunculus `web/expressions.js` | Existing mood-to-brow/mouth mapping | Useful starting geometry/values, not a sufficient neutral/curious/deadpan acting vocabulary |
| Assets `exports/ps1guy_v10_homunculus.glb` | Rest-pose skinned character with sealed mouth surface | No clips or morph targets; cannot claim imported facial animation is already present |
| Assets `scripts/conversation_motion.py` | Literal recipe bank: idle/talk/gesture/gaze/walk | Consume only as validated data or exported JSON; Blender bone/axis semantics need adapter tests, not blind rotation copying |
| Assets `environments/reading-room/scene.glb` | Existing library set, metadata reports 87,756 triangles | Choose a validated seating/table arrangement, scale to people, evaluate materials/lights |
| Assets openable Book Two v2 | 72 leaf hinges and synchronized opening/turning GLB clip | Author tested open/adjacent-turn/hold/read/place/close/slam rails, grip sockets and camera coverage; no need to play the complete multi-minute clip |
| Ad Studio `harness/voice.py`, `harness/audio.py` | Cached measured takes, stable profiles, voice capability checks | Preserve concepts or extract a small optional adapter; core must not import parent harness |
| Ad Studio `blender/performance.py` | Conversation cues and rest-relative layered motion | Reuse semantics/tests; bpy-based implementation is not a browser runtime dependency |
| GET YOUR OWN film/log | Tight reactions, three-quarter views, measured takes, readable inserts | A source of craft lessons, not a template to reproduce in every episode |

The new actor runtime must not instantiate the full Homunculus Room just to get a
face. That pulls in unwanted environment assets, game behavior, real-time loops
and single-actor assumptions. Extract a small versioned adapter with attribution
and tests; do not edit Homunculus itself as part of the first milestone.

## Source discrepancy to resolve before a product-linked demo

Homunculus `web/assets/comic/PROVENANCE.json` records source PDF hash
`4519506a600186cc6cce979f80256b989b98c9722c9672337730e59c588b8b04` and cover
title “Meditations of the Elusive Idea Bladder.” Its page-36 image was personally
viewed during this design work; raw OCR is visibly unreliable in its excerpt file.

The current asset `textures/book2_openable_v2/pages.json` records PDF hash
`0b9edc67fc3ba74f8ec257d1c2cc86b35c5e7b1fa894f0395b622cc3125bb3a5` and the v2
notes say the previous exterior artwork is retained. This does not establish the
two PDFs, covers and sold edition are interchangeable. Compare the specific
images/page records and exact offered edition before adding product claims.
An explicitly marked local developer draft can exercise the renderer while this
is resolved, but cannot be delivered as a verified book-selling episode. Product
binding is mandatory in normal v1 runs, including episodes without a closing card.

## Packaging and assets

No nested `.git` required while experimental. Own package manifest, lockfile,
README, schemas, tests, CLI, optional Python voice extra, notices and output ignore
rules make this directory extractable. Runtime configuration never imports
`../../harness` or assumes an adjacent Homunculus checkout. Dev audit references
are just references, not resolution logic.

Keep large source models and new wardrobe exports in the asset library under its
current active layout, with Git LFS, builders, provenance and visual checks. Let
the manifest map symbolic actor/set/page IDs to that layout. No archived assets
or speculative migration of the user's ongoing asset refactor.

Homunculus code/art are marked all-rights-reserved to the owner; Three.js is MIT.
Keep provenance and relevant dependency notices when reusing code. Do not add an
MIT license over the owner's art or infer public redistribution permission. The
extracted project's packaging must not accidentally bundle the entire book,
credentials, private research, source recordings without rights, or model weights.

## Performance test, not wishful budgeting

Benchmark the representative 60-second duet with source inserts and real audio:
540×675 and 1080×1350, 24 fps, cold versus warm cache, isolated versus queued behind
another job. Record hardware, graphics backend (including software rendering),
dependency versions, segment size, render/readback/encode/audio time, peak RAM,
disk high-water mark and throughput. Compare with a one-character baseline.

Optimize the measured bottleneck: capture transport, environment complexity,
material count, frame encoding or TTS. Do not “optimize” by deleting dialogue,
turning the result into an end card, skipping source inserts or lowering quality
without an explicit output profile. Never promise real-time throughput until
measured on the actual deployment machine.
