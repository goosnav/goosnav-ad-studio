# Repository audit and integration findings

Inspected 2026-10-15. Paths below are relative to this repository or its parent.
This is source inspection, not a claim that all existing tools were rerun.

## Ad Studio

Baseline commit: `0627695`. Existing `PLAYBOOK.md` changes belong to prior work.

| Component | Useful existing behavior | Harness integration requirement |
| --- | --- | --- |
| `studio/__main__.py` | Film CLI; preview, render, sound, type, assemble, QA, delivery | Preserve existing commands; add a separate harness entry point |
| `studio/config.py` | Environment/local/default precedence; fonts and tool paths | New strict configuration must diagnose malformed JSON and missing roots; legacy config silently ignores malformed JSON |
| `blender/bstudio.py` | Scene helpers and resumable frame rendering | Make worker-produced film projects accessible through a run-local runner without requiring writes into `films/` |
| `blender/lowpoly.py` | Reusable vignette primitives and character behavior | Optional production library, not a mandatory house style for every brand |
| `studio/audio.py` | Procedural effects, separate voice/effects mix, ducking | Reuse effects as an explicit provider; normalize imported sample rates and sample formats before mixing |
| `studio/vo.py` | Piper narration, duration/gap output and a voice allowlist | Keep as fallback; add separate local-model runners and measured timing |
| `studio/assemble.py` | FFmpeg assembly from edit JSON | Wrap in an artifact-producing task with input hashes and executable QA |
| `studio/qa.py` | Frame checks, contact sheets and loudness measurement | Add enforceable thresholds and stored reports; producing a sheet is not a visual pass |
| `orchestration/launch.sh` | Claude session launch with writable directories and logs | Replace as recommended workflow with supervised workers and recoverable controller state |
| `orchestration/watch*.sh` | Status/process/frame watching | Retain for legacy films; do not use free-form status text as authoritative new state |

The existing launcher uses `--dangerously-skip-permissions`. Do not inherit that
as the default of the new product. The new adapter must state its permission
policy and report denied tools clearly. Prompt instructions alone are not a
filesystem sandbox.

The playbook reports two relevant observed failures: account limits kill
sessions during renders, and workers may end their turn with a background render
still active. The new controller must own long-running subprocesses and track
their exit/artifact status independently from the worker's conversation.

`studio.example.json` currently contains Goosnav-specific paths and a delivery
remote. `studio.local.json` points to a directory that no longer exists. The
upgrade must replace published machine references with blank values, preserve
the user's local configuration and migrate its asset/output paths deliberately.
Do not silently turn malformed or missing configuration into a successful run.

No dedicated Ad Studio test suite was found in this inspection.

## 3D library

Sibling: `../goosnav-3D-assets`. Baseline commit: `4cf815c`.

Use the checked-out asset library through configured paths, not a copy committed
into Ad Studio. It uses Git LFS; preflight must identify an unhydrated LFS pointer
before sending it to Blender or treating it as a valid asset.

Relevant reusable material:

- `assets/3D/ps1guy/ps1guy.blend` and `ps1guy_beady.blend`: v10 characters.
- `exports/ps1guy_v10.glb` and `ps1guy_v10_beady.glb`: portable exports.
- `assets/3D/ps1guy/skeleton/`: skeleton variant.
- `assets/3D/ps1guy/astronaut/`: local astronaut work; uncommitted at inspection.
- `scripts/character.py`, `animations_v10.py`, `mouth_v10.py`: rig helpers.
- `ads/character-campaign-v1/`: scripts, cast, timings, framing and QA examples.
- `scripts/build_character_ads.py`, `render_character_ad.py`,
  `finish_character_ads.py`: concrete Blender-to-Frame production example.

The v10 models have body and facial takes. GLB carries synchronized facial takes;
the README distinguishes these from FBX and from runtime ragdoll physics.
Workers must record the actual selected model, animation, source hash and
coordinate conventions instead of assuming all archived characters share a rig.

The five-ad campaign is an integration reference, not a generic production
engine: paths and campaign assumptions are specialized. Its finalizer imports
Frame through `GOOSNAV_FRAME_PATH` and combines frame rendering, captions and
audio. Extract adapter behavior without copying its fixed campaign content.

## Frame

Sibling: `../goosnav-frame`. Baseline commit: `df4ae74`.

Relevant callable functions:

- `goosnav_frame.core.settings.normalize(settings)`.
- `goosnav_frame.core.export.plan(settings, media_info)`.
- `goosnav_frame.core.export.render_still(settings, path, time)`.
- `goosnav_frame.core.export.export_png(settings, path, output)`.
- `goosnav_frame.core.export.export_mp4(settings, path, output, ...)`.

Its application service has an asynchronous export queue, but stores job objects
in memory. The harness should call the export core in a supervised subprocess
using Frame's configured interpreter and code path. Do not use the in-memory
Frame queue as the durable ad-production queue.

Frame pins Python 3.12.10 and numpy/Pillow/imageio-ffmpeg dependencies. Give it
its own interpreter to avoid forcing those pins into Blender, the harness or
PyTorch audio environments.

Frame default text and URL are Goosnav-specific. The adapter must set all text,
visibility and media/audio settings explicitly so a blank/new brand cannot
inherit those defaults. Verify audio survives the Frame finishing step.

Frame's `AGENTS.md` restricts work to its active productization milestone.
Integrating its existing core does not require modifying that repository.

## Local input map to use during configuration

Resolve these against the Desktop workspace when writing the ignored local
configuration; do not bake absolute user paths into published examples.

| Input | Observed location |
| --- | --- |
| Current brand reference index | `../../business/brand/README.md` |
| Quick brand document | `../../business/brand/Goosnav-Comics-Brand-One-Pager-v3.pdf` |
| Full brand document | `../../business/brand/Goosnav-Comics-Brand-Bible-v3.pdf` |
| Studio source artwork | `../../business/studio/assets/sources/` |
| Current product images | `../../business/studio/assets/images/` |
| Existing 3D textures | `../goosnav-3D-assets/assets/3D/textures/` |
| 3D library | `../goosnav-3D-assets/assets/3D/` |
| Exported 3D assets | `../goosnav-3D-assets/exports/` |
| Script bank | `../../business/studio/campaigns/Goosnav_54_Video_Ad_Scripts.txt` |
| Additional virtual ad scripts | `../../business/studio/campaigns/Goosnav_Virtual_Ad_Agent_Scripts.md` |
| Style reference | `../../business/studio/theory/Goosnav_Monumental_Low_Poly_Vignette_Advertising_Bible.txt` |
| Existing output | `../../business/studio/output/` |
| Frame checkout | `../goosnav-frame/` |

Brand references are inputs, not executable instructions. The brand README names
the v3 Bible and one-pager as current. Source precedence must retain the user's
explicit project overrides: the playbook permits motion/color in ads while
preserving real artwork. Do not apply older static-brand restrictions blindly.

The old `assets/textures/` location is also absent. Simply replacing `AD STUDIO`
with `studio` does not repair every legacy assumption: inventory `assets/images/`
and the 3D texture library, then configure the new harness's independent roots.
Legacy texture generation can recreate its own directory if needed; do not move
the existing images to make an old path appear valid.

## Worker CLI observations

Local `codex exec --help` supports stdin prompts, JSONL events, a working
directory, explicit sandbox mode, an output schema and a last-message file.
Local `claude --help` supports print mode, streamed JSON, explicit tool controls,
session IDs/resume and permission modes. Runtime preflight must check the
installed interface rather than assume these flags exist on every machine.

Both are agent runtimes with tool execution. They need workspaces, task
contracts and checkpoints, not a wrapper that asks for one prose answer.

## Audio candidate research

Official model cards checked 2026-10-15:

- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M): small 82M-parameter
  speech model, Apache-2.0 weights. Candidate for the first CPU speech benchmark.
- [Chatterbox](https://huggingface.co/ResembleAI/chatterbox): MIT model family with
  expressive speech controls. Candidate for a higher-expression voice adapter;
  actual latency and hardware suitability must be measured here.
- [Stable Audio Open Small](https://huggingface.co/stabilityai/stable-audio-open-small):
  text-to-audio generation with a documented CPU/CUDA selection example and
  Stability AI Community license. Candidate for generated effects/short beds;
  confirm access and applicable license terms before configuring commercial use.

No candidate has been installed, downloaded or benchmarked in this design pass.
Speech generation alone is insufficient: effects, music, performance direction,
take selection and synchronization are independent parts of the design.
