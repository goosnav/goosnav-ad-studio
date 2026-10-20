# goosnav-ad-studio

## Hands-off ad engine

Quick start: `./ad "what the ad should be"` (see [`CLI.txt`](CLI.txt) for the variations).

Use `-e low|medium|high` for production scope/model intensity and `--fast` to halve
the time target while retaining the chosen model tier. Nine-second targets are
10/20/40 minutes normally, 5/10/20 with `--fast`, with at most 25% overtime before
checkpointing. These are budgets, not a claim that every ad finishes within them.
`./ad metrics RUN_ID` reports actual work; `./ad feedback RUN_ID --rating good --note
"The reaction worked"` supplies traceable guidance for later ads.

New runs use the `retro_world` look: character comedy in textured, atmospheric
early-3D worlds. Low reuses proven sets; high can build distinctive settings and
use verified motion. The library is configured/discovered, with stable asset IDs
and content hashes instead of fixed layout assumptions. See [asset publication](docs/library.md)
and [reusable worlds](docs/worlds.md).
First-catalog publication preserves committed active `.blend` inventory using
LFS content OIDs, without authorizing pointer files as geometry. Hydrate required
active assets, excluding archives, before catalog reads/use. Existing catalogs
remain authoritative and require explicit repair if entries were previously omitted.

Implemented helpers and passing module tests do not establish end-to-end production
success. See the [implementation ledger](docs/production-upgrade-progress.md) for
current test evidence, live-run outcomes, publication status and remaining limitations.

```sh
cp harness.example.json harness.local.json   # website, products, brand docs, script banks, asset folders
python3 -m harness doctor                    # checks tools, codex/claude logins, Frame, sources
python3 -m harness make --count 3            # or add --concept "..."; omit both for an open brief
./"Start Ad Studio.sh"                       # the same from a browser page: runs, videos, config, pause/resume
```

A deterministic state machine (`harness/`) uses bounded factual research, TWO scripts
per requested ad, and ONE selection/story-coherence review. Per ad: director,
measured local neural audio, blocked assets and ONE combined storyboard/performance
check, Blender animation, ONE video editor that plans and
performs the conform, Goosnav Frame CTA, deterministic technical QA, a short final
creative review and packaging. Each creative step is a budgeted, tool-using `codex exec`
or `claude -p` session using your existing subscriptions. `-e low|medium|high`
chooses the role/model preset; `-p openai|anthropic` chooses the preferred
provider while preserving automatic failover. Medium defaults to Opus for
writing/animation/direction and Sonnet for QA; high defaults to Astra with Sol
for QA, and low defaults to Luna. Release versions resolve dynamically, and
automatic model routes refresh for unfinished work on resume. See [CLI.txt](CLI.txt)
for all combinations and `./ad models -e high` for a live preview. The backup
continues interrupted work in the same workspace. Scripts default to simple spoken scenes; a shared
Blender helper reuses idle/gesture clips and drives mouths from the measured
dialogue, rather than rebuilding body animation for each ad. Static characters and products
are acceptable when the dialogue and timing work. The editor can trim dead air and
produces a new speech timeline for final QA. Static products stay intact. Worker example: [`dev/WORKER_GUIDE.md`](dev/WORKER_GUIDE.md#talking-characters-and-reusable-motion).
Operations: [`dev/OPERATIONS.md`](dev/OPERATIONS.md).
Status and next steps: [`dev/STATE.md`](dev/STATE.md).

### Production helpers and their boundaries

Run Python helpers from this repository. For voice, replace `/path/to/audio-python`
with `audio.python` from the run configuration; its local models and FFmpeg must
already be installed. A minimal voice request is:

```json
{
  "provider": "kokoro",
  "effort": "low",
  "voice_profiles": {"A": {"voice": "af_heart"}},
  "lines": [{"id": "line-1", "speaker": "A", "text": "Just one more page.",
             "delivery": "Quiet, dry reaction; listen before accepting."}]
}
```

```sh
/path/to/audio-python -m harness.voice request.json workspace/takes --summary
python3 -m harness.creative submit-direction plan.json takes/manifest.json --workspace workspace --output direct-result.json --direction-md direction.md
python3 -m harness.mix accepted/direct/result.json workspace/audio --no-bed --stage-result workspace/result.json
python3 -m harness.mix --request workspace/audio/request.json workspace/audio-replay
python3 -m harness.render --scene workspace/scene.blend --audio workspace/audio/mix.wav --output workspace/preview.mp4 --seconds 9 --effort low --fast --timeout 600
```

These are separate worker steps, not a complete executable pipeline.
`submit-direction` reads workspace-local `plan.json` (authored `summary` and
`direction`) and the verified voice manifest, declares its WAV dependencies, and
writes a new result without altering the plan or existing artifacts. The optional
`--direction-md` names an existing notes file. Paths are relative to `--workspace`.
The controller must still validate and promote this submission before mixing;
successful serialization is not approval.

Direction must schedule the **full selected polished WAV duration**, including
pauses and tails, with separate reply/reaction gaps. Active-speech bounds alone
cannot establish fit. Shorten/re-record speech or revise the plan when it cannot
fit; do not rely on downstream silence trimming or invented measurements.
Voice writes portable raw/polished WAVs and `manifest.json`, measures timing, and
checks cached bytes before reuse. The first usable take is provisional, not a
listening verdict. Preserve an audition through a line's `selected_take` reference
(`manifest`, optional `line_id`/`take_id`) in a new batch, keeping speaker/text/voice
consistent. Normal audition caps are 1/2/3 by effort, or one in fast mode; one
explicit defect retry is supported. Kokoro delivery notes are not emotional
synthesis controls. Chatterbox is optional, currently absent from the validation
setup, and never installed or substituted automatically.

Mixing requires an empty/new output directory and either `--no-bed` or
`--bed BED.wav --bed-gain-db -30`. It preserves verified selected speech, rejects
overflow that would cut active samples, and writes the mix, dialogue stem, timeline,
audit and portable replay inputs. `--stage-result` writes a new sibling result file
with workspace-relative artifact paths; it refuses to overwrite existing work.
Quiet dialogue receives measured uniform gain targeting −21 dBFS, capped at
+18 dB with peak protection. `audit.json` records gain and before/after levels;
an unreachable safe speech floor blocks assembly rather than relaxing checks.
Replay does not synthesize speech. Neither voice nor mix performs ASR or emotional
assessment; ordinary controller checks and listening remain necessary.
Worker `files` lists only new local outputs. Reviews normally return `files: []`
and reference accepted boards/media in `findings.target`; input paths are not outputs.

In Blender Python, use `blender.staging.import_actor(path, name, location, height_m,
rig_name=...)` to append one explicitly selected rig, `world_bounds(subjects)` to
measure it, and `frame_subjects(camera, subjects, margin=.08)` to fit the current
pose. These helpers do not choose shots, authorize cast, detect occlusion, or prove
face readability across animation. See [staging usage](docs/worlds.md).
The render helper requires self-contained scene dependencies, rechecks them on
every invocation including cache hits, and resumes only verified frame checkpoints.
An MP4 from this helper is not evidence of creative approval.

`harness.execution` accounts for active work and provider waiting separately;
ordinary resume retains spending. At the hard ceiling, an operator can explicitly
extend it with `./ad resume RUN_ID --extra-minutes 10`. Runs without the versioned
execution policy retain legacy behavior. Versioned direction attempts request a
minimum 90/120/180 seconds for low/medium/high, including fast mode, bounded by
the stage ceiling and remaining global budget. This does not extend the hard cap.
Strict review contracts reject a pass verdict with unresolved blocking or important
defects. `harness.learning` provides product-scoped,
source-linked feedback, reuse ordering, voice suggestions and hash-verified research
reuse (up to six hours); it does not train a model or turn technical success into
a quality rating. Use `./ad feedback` and `./ad metrics` as shown in [CLI.txt](CLI.txt).

Post-production publication runs only for declared candidates from accepted asset
tasks whose ad has a successful package. `./ad publish RUN_ID` retries it without
rendering: asset commit and LFS push precede local adoption and any matching parent
gitlink update. Each has a separate receipt/status; failures do not invalidate a
finished video. Accepted artifact hashes and the saved accepted-manifest hash are
revalidated before publication/retry; tampering blocks promotion. Dirty artist work
is not discarded to adopt assets. See [catalog, manifest and retry API](docs/library.md)
and the [live publication ledger](docs/production-upgrade-progress.md).

### Optional automatic Google Drive delivery

Configure `output.folder` (a local absolute path) and `delivery.drive` (an
rclone destination such as `agent-exchange:deliverables/ad-studio`) in
`harness.local.json`, then authorize that remote with `rclone config` on the
render machine. `./ad "prompt"` uploads only the finished MP4s to the configured
folder after rendering, using script-title filenames with stable UTC timestamps
and run/ad suffixes to avoid collisions. Source ZIPs remain local. It verifies the names via rclone,
and records the delivery status. Upload errors never delete local renders or
change a successful render status. Check `./ad status`; retry without
re-rendering via `./ad upload [RUN_ID]`. Leave `delivery.drive` blank to disable
Drive delivery entirely. See [`CLI.txt`](CLI.txt).

For floating product end cards, configure `output.end_card_clips` with product
names and active `end_card_video` catalog IDs. `output.end_card_library` can point
to the clip library independently of a character-library refactor. The asset
submodule includes the original Book 2 and Goosklerf pack item-drop videos;
`harness.example.json` shows the mappings. Frame trims or loops an excerpt to fit
the ending and preserves the ad audio. A missing clip falls back to the rendered
hero with a recorded reason; new animation is needed only for unmapped products.

## Film toolkit

The code and the repeatable process behind Goosnav's animated ads. Each ad is a Blender scene with narration, synthesized sound, type, and a white end card with the addresses, rendered for 4:5 portrait (or any other format).

The code and the method live here. The creative material lives in the business folder. The two are joined by paths in `studio.local.json`:

| What | Where (this machine) | Setting |
|---|---|---|
| Code, process, lessons | this repo, `~/Desktop/code/goosnav-ad-studio` | – |
| Source art and render textures | `~/Desktop/business/AD STUDIO/assets/{sources,textures}` | `assets` |
| Finished films (masters, web, scripts, READMEs) | `~/Desktop/business/AD STUDIO/output/films/<film>/` | `output` |
| Frames, previews, mixes (large, disposable) | `~/goosnav-studio-work/<film>/<format>/` | `work` |
| Piper venv and voices | `~/.cache/goosnav-studio/` | `cache` |

`AD STUDIO/code` and `AD STUDIO/tools` are symlinks back into this repo.

**Read [`PLAYBOOK.md`](PLAYBOOK.md) before making anything.** It holds every lesson learned so far: creative method, owner decisions, Eevee traps, sound, QA, delivery, and running unattended Claude sessions.

## Setup (any machine)

```
git clone <this repo> && cd goosnav-ad-studio
tools/setup.sh                 # checks blender/ffmpeg/rclone, builds the Piper venv, fetches voices,
                               # creates studio.local.json from studio.example.json
$EDITOR studio.local.json      # point assets/output/work at this machine's folders
python3 -m studio config       # verify paths and fonts (Helvetica on macOS, Nimbus Sans on Linux)
python3 -m studio textures     # rebuild textures from assets/sources (optional)
```

Nothing in the code hardcodes a machine path. Every setting can also be set with an environment variable (`STUDIO_ASSETS`, `STUDIO_WORK`, `STUDIO_OUTPUT`, `STUDIO_BLENDER`, ...).

Requirements:

- Blender 4.x (Eevee)
- ffmpeg
- Python 3.10+ with numpy, scipy and pillow
- rclone, for delivery to the Agent Exchange Drive folder

## Make a film

A film is a folder in `films/`. [`films/the_dilemma/`](films/the_dilemma) is the reference.

```
films/<film>/
  SCRIPT.md      written first
  lines.txt      narration, ID|text ("..." = pause)
  film.py        Blender scene: from bstudio import *; build; update(t); run(...)
  sound.py       studio.audio Mix + instruments, hit points from events.json
  type.py        studio.typeset overlays for the chosen format
  edit.json      overlay timings for studio.assemble
  README.md
```

```
python3 -m studio vo       the_dilemma                               # narration -> work/<film>/vo
python3 -m studio preview  the_dilemma --format 4x5 --times 5,20,48  # look at the contact sheet
python3 -m studio preview  the_dilemma --format 4x5 --every 12       # whole film, low res
python3 -m studio render   the_dilemma --format 4x5                  # final frames, GPU lock, resumable
python3 -m studio sound    the_dilemma --format 4x5
python3 -m studio type     the_dilemma --format 4x5
python3 -m studio assemble the_dilemma --format 4x5 --name THE_DILEMMA
python3 -m studio qa       the_dilemma --format 4x5 --name THE_DILEMMA
python3 -m studio deliver  the_dilemma --name THE_DILEMMA            # Drive via rclone, verified
```

Formats are `4x5` (1080×1350, the default), `16x9`, `1x1` and `9x16`.

## Layout

| Path | Contents |
|---|---|
| `studio/` | Plain-Python tools: `config` (paths, fonts, formats), `vo` (Piper narration), `audio` (synth instruments + mix), `typeset` (overlays), `textures` (scan cleanup, rectify, generic products), `assemble`, `qa`, `deliver`, and the CLI in `__main__` |
| `blender/bstudio.py` | Blender layer: scene setup, materials, two-sided paper, object-pool `Sheets`, geometry, camera, and the render loop with formats, motion blur, cut frames and resume |
| `films/` | One folder per film |
| `orchestration/` | Running films as unattended Claude Code sessions: `COMMON_BRIEF.md`, `lanes/*.md` (one creative lane per film), `launch.sh`, `watch.sh` |
| `tools/legacy/` | The earlier AD STUDIO tools (still-ad maker `make_ad.py`, type-and-photo film `make_film.py`, the first Blender reels `gnscenes.py`/`gnfilm.py`/`gnstills.py`/`gnad_apple.py`), now font-agnostic |
| `tools/setup.sh` | Machine setup |

## Films

| Film | Formats | Notes |
|---|---|---|
| `the_dilemma` | 4:5, 16:9 | Paper desert, Book 2 monolith explodes, page tornado, card fortress. Narrator `norman` (re-voiced 2026-09-29). |
| `lights_out` | 4:5, 16:9 | Unmanned 1970s factory. Imported session build (`IMPORTED.md`); re-voiced. |
| `the_longest_turn` | 4:5 | Goosklerf as a thunderstorm war epic on a continent-sized table. |
| `under_the_door` | 4:5 | A bedroom floods with Patreon comics; Book 2 lighthouse. |
| `the_archive` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-B2-001 (Book 2). |
| `continuation_department` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-PAT-001 (Patreon). |
| `delayed` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-GK-001 (Goosklerf). |
| `the_probe` | – | Session stopped at the script stage (2026-09-29); not produced. |

## Two house styles

1. **Cinematic Eevee films** (the first four): `bstudio` plus a film script. 60–90 s, narrated, 4:5.
2. **Monumental Low-Poly Vignettes** (GLPV-001): `blender/lowpoly.py` builds primitive actors that walk, sit, reach, blink and jaw-flap to the dialogue, animated on 2s. It also holds the house materials, fog, and symbolic products (generic Book 2, Goosklerf box and cards, paper signs and forms). Vignettes run 12–25 s with 9:16 as the master. They render in the `lpv` format (540×960), are upscaled exactly 2× nearest-neighbour by `studio.assemble` (`"upscale"` in `edit.json`), and get a 4:5 centre crop (`"crops"`). Dialogue casts come from `films/cast_vo.py` (`studio.vo.build_cast`, with PA and radio processing). End cards come from `studio.typeset.vignette_card`, kept inside the 4:5 band.
   - Style bible: `AD STUDIO/theory/Goosnav_Monumental_Low_Poly_Vignette_Advertising_Bible.txt`.
   - Script bank: `AD STUDIO/campaigns/Goosnav_54_Video_Ad_Scripts.txt`. The three vignettes adapt ads 13, 33 and 39.

## Related projects

`~/Desktop/code/business-suite/ai-ad-factory` and `ps1-ad-factory` generate ad *plans* (briefs, copy, shot lists) from the Creator Commerce OS catalogue. This repo *produces* the films. A plan from either can become a lane prompt in `orchestration/lanes/`.
