# Implementation and verification record

## Reading direction / immediate opening / spinning end card — 2026-10-21

Targeted owner-feedback fixes:

- Removed the compiler's automatic three-second silent source introduction.
  Up to five seconds of close physical-page coverage now overlaps measured speech.
  Source changes, explicit shots/actions and the end of dialogue bound that window.
- Turned the book toward its readers on the table and while held. Adjusted hand
  targets and inward finger orientation; retained bounded wrist/palm checks.
- Kept canonical image bytes and UVs unchanged. Only printed-page materials are
  unlit/non-tone-mapped to avoid room lights bleaching the ink. Room lights remain
  unchanged. The initial camera already frames the selected page, then pushes in.
- Bundled the existing spinning-book MP4 by catalog path/hash. End-card type stays
  editable, with a blue underlined Times-compatible URL. Removed the additional
  one-third-resolution raster and quantization; use the original video frames.
- Integration testing exposed Chromium's non-Range HTTP seeking failure and a
  fractional timestamp tolerance that was too strict. Load an owned local video
  blob, bound fetch/decode/seek waits, and allow 0.1ms timestamp rounding (far below
  one source frame). Missing/broken clips still report an error, never a static
  substitute. A request-generation guard prevents stale seeks repainting a newer
  conversation frame; dispose releases the video and its object URL.

Fresh unit suite with the installed local-voice identity check: **44 passed,
no skips**. All **16 bundled assets** pass hash verification. Independent review
found the inward-finger and stale-render issues above; both were reproduced with
regressions, fixed, and rechecked. Browser/capture evidence follows below.

An isolated copy populated from staged Git files also passes a clean cached
`npm ci --ignore-scripts --offline --no-audit --no-fund`, all 16 asset hashes and
all 44 unit tests. No sibling asset checkout is needed. This shares the installed
host voice/browser tools, not a fresh operating-system certification. The first
ordinary install was interrupted while its registry audit request stalled; the
offline install verifies portability, not a new dependency security audit.

The fresh capture/recovery run passes both watchdog and real-video recovery tests:
verified complete video, deleted final delivery rebuilt from valid segments, and
corrupt checkpoint regenerated. Early integration runs deliberately exposed the
HTTP and timestamp bugs above; those failed test artifacts are not deliveries.
All **39 browser cases pass across final scoped runs**: the broad run started
before the timestamp correction and retained that one capture failure; its other
36 cases passed. The fresh two-case capture run passed after the fix, as did both
opt-in real-server GUI cases. Fractional 12/24/30fps tests cover 36/72/90 closing
frames, backward and repeated seeks with identical pixels; maximum observed
timestamp drift is 1.67 microseconds. Long custom copy, stale completion races,
book orientation, actual page identity and original-asset hashes are covered.

### Inspected corrected preview

Run `an-inside-source-2026-10-22T02-28-51-438Z-cdba6b75` completed at
**16.0 seconds, 192 frames, 432×540/12fps**, with all four original spoken lines,
reactions and the three-second spinning end card. Wall time: **87.5 seconds**,
with cached local voices and concurrent tests, not a full-resolution benchmark.
SHA-256: `e2f27e6a9e4c6f6fbc618a541d43d7b96318acf72765591ef439f75072fc8be4`.

Main personally inspected extracted final-MP4 frames at the opening, four seconds,
the two-shot, speaker close-up and two different closing rotations. The physical
page is upright/readable and its original ink is clearer; the spinning product
and full-resolution title/URL replace the degraded static image. Measured audio
starts at timeline zero; the existing take's natural lead-in reaches -40dB at
0.262s, rather than waiting through the old additional three-second intro. Audio
was decoded/checked, not personally listened to. No upload or publication occurred.

## Performance/appearance follow-up — 2026-10-21

The follow-up adds six color/eye combinations (blue/rust/olive with white or beady
eyes), original recessed-mouth speech shapes, smooth expressions, physical-book
reveals, seeded conversation shots and an editable early-web end card. Asset
sources, GLBs, emotion bank and review sheets are published in Goosnav-3D-assets
commit `65f9ae1f791b86b5e2ce2b235ee0d2f00908557a`.

- All six editable sources preserve original base geometry, rig and visemes.
  Blender checks pass, including 324 actual exported-mouth rays and beady blink
  geometry. Asset layout and LFS integrity checks pass.
- Full unit suite: **41 passed, no skips** with the optional installed local-voice
  identity check enabled. Repeated from an isolated directory populated only by
  staged Git files, followed by fresh `npm ci` and `doctor`: **41 passed** again.
  No sibling asset checkout is needed. This uses the same Linux host's browser,
  FFmpeg and explicitly selected voice environment, not a new-OS certification.
- GUI integration: **27 passed**, including the real local server, clothing/eye
  selection, editable card/shot fields, imports/exports and source locks.
- Renderer/browser regressions: **5 passed** after the fixture corrections below;
  both portrait formats, physical page identity, mouth visibility, reverse seeking,
  custom card text, variant lookup and legacy/new book grip behavior are covered.
  Together with the **2 capture/watchdog tests**, all 34 browser cases pass across
  these final scoped runs. Browser test files run serially to avoid GPU contention.
- Recovery regression passed with the new renderer: full video, removed final
  delivery, reuse of valid segments and regeneration of a corrupted checkpoint.
- Independent review found pathological multiline end-card overflow; fixed with
  bounded wrapping/clipping and checked at full, preview and minimum sizes.
  Newlines in ordinary text remain supported. A previous portrait OTS wall
  obstruction and foreground nose overlap were corrected. Visibility tests now
  mask the actual mouth geometry rather than raycasting the obsolete overlay.
- The old sealed-face eye regression is retained, with its actor placed at the
  current production blocking. Modern morph-based eyes have separate tests.

### Inspected comparison render

`examples/parasite.json` now pairs `blue-beady` with `rust` and automatic shots.
Run `an-inside-source-2026-10-22T02-01-38-283Z-e88d364d` produced **19.0 seconds,
228 frames, 432×540/12 fps**, including every measured line/reaction and the final
three-second end card. Wall time **97.38 seconds**, with cached local voice takes
and concurrent browser tests; not a full-resolution or cold-start benchmark.
SHA-256: `164f8cdb6924be868d1908e1ae1866211d170c4c8f60e2f8c81f8c9ccead7856`.

Main personally inspected frames extracted from the final MP4: physical selected
page reveal/push, mixed-eye two-shot, speaking mouth in the over-shoulder view and
the final blue-underlined Times-compatible URL. Audio presence and full decoding
are technically checked; this is not a claim of personally listening to the audio.
The beady/white variant, emotion and viseme review sheets were also inspected.
The video remains local; no ad upload/publication was performed.

Remaining limitations: amplitude-driven mouths are not phoneme-accurate; hands and
natural acting remain experimental. Canonical comics are unchanged. No audience
response, owner final-film approval or sales effectiveness is claimed.

## Initial prototype verification (historical)

2026-10-21 local date. Scope: this experimental folder only. This is an implemented
prototype of the revised [build contract](BUILD_CONTRACT.md), not a declaration
that every item in the original design vision is complete.

## Delivered

| Requirement | Implementation / evidence |
| --- | --- |
| Simple human JSON | Four required author fields: template, title, comics, lines. Optional acting and action fields have defaults and actionable validation. Three editable examples and the tutorial. |
| Repeatable source selection | Seeded reviewed catalog; saved source locks bind IDs, image hashes, PDF pages and edition hash. |
| Correct physical book content | Catalog verification hashes actual JPEG bytes embedded in the book GLB at the declared PDF page. Shared spread mapping; open/reopen and arbitrary seeks tested. |
| Optional AI producer | Explicit configured image-capable HTTP endpoint/model; selected images and transcripts only; same locked selection; one bounded repair. Mock endpoint integration tested, no live paid call made. |
| GUI | Actual page gallery, transcript, template/seed selection, form and JSON editing, import/export, validation, optional draft, local generation and job/video status. Imported stale locks cannot be silently removed. |
| Deterministic animation | Three.js game-style frame evaluation; independent Homunculus skeletons; JSON emotion/face/gesture/reaction controls; no animation agent. Seek-back produces identical pixels in the tested browser configuration. |
| Speech | Offline local Kokoro or supplied recordings. Actual audio lengths and RMS activity drive timing/mouths. No silent replacement of missing recordings. |
| Book rails | Open, turn, hold, read, place, close and slam execute through authored hinge/pose code. Input state constraints are checked. Physical grip quality remains experimental. |
| Recovery | Independent run IDs, atomic receipts, per-run/production locks, checked segment hashes, browser watchdog and bounded retries. Missing final videos and corrupt checkpoints recover through resume. |
| Portable assets | Seven real asset files explicitly included despite parent media-ignore rules. Runtime has no fixed home/sibling/archive paths. Fresh dependency installation and tests exercised after copying outside parent checkout. |

## Tests and checks

- Final unit suite with installed local voice environment enabled: **27 passed,
  zero failures, zero skips**. Without a configured voice environment, its optional
  installation-identity test intentionally skips; recorded-mode tests still run.
- Final browser/integration suite: **20 passed, zero failures, zero skips** with
  real-server GUI tests enabled. It includes actual GLBs, both sets, source changes, opening and
  reopening, reactions, blink geometry, arbitrary seeks, GUI/source-lock operations,
  and the real local backend. Tests use the pinned Playwright Chromium.
- Real capture regression creates a short technical tone fixture, verifies a full
  audio/video MP4, removes delivery, resumes without recapturing valid segments,
  corrupts a checkpoint, and proves it is rerendered. A separate real-browser test
  stalls an evaluation and verifies the watchdog closes the browser.
- An independent read-only review found source-lock import, book reopen mapping,
  ignored bundled binaries and missing frame-watchdog defects. These were fixed
  with regressions. Scoped follow-up review found no remaining Important findings.
- `doctor`, catalog hashes, example validation and `npm audit` passed. No parent
  pipeline tests or changes were needed: no imports or integration were added there.
- Clone-content check: exported only this folder's staged Git-index files to a
  fresh temporary directory, ran `npm ci` and `doctor`, then both real browser
  watchdog/capture/recovery tests there (**2 passed**). This confirms the binaries
  travel in Git and the recorded-audio render needs no parent checkout. Browser
  cache and system FFmpeg remained installed on the same Linux host; this is not
  a separate-computer or Windows/macOS certification.

## Real local-voice demo

Example: `examples/parasite.json`, title **An Inside Source**.

- Run: `an-inside-source-2026-10-22T01-16-21-107Z-8efe8772`.
- Output: 16.0 seconds, 192 frames, 432×540 at 12 fps, dialogue audio present.
- Wall-clock command time: **45.10 seconds**, with already cached local voice takes
  and installed dependencies. This is a preview-resolution measurement on Linux,
  not a cold-install, uncached-voice or full-resolution benchmark. A renderer test
  also ran concurrently; do not treat this one measurement as a guarantee.
- MP4 SHA-256: `763d058eaf9c3f94cd15c22b302dd6737109fbed38de7b14e5cf199cdcf3987d`.
- Final technical checks: exact frame count, dimensions, duration, audio stream,
  full decode and checksum. Source lock identifies `book2-036`.
- Main agent personally inspected the actual final film's contact sheet and the
  revised character close-ups, plus the actual GUI. It did **not listen to the
  final film**. Audio measurements/decoding do not establish good vocal performance.

Generated output and review screenshots remain ignored local artifacts; they are
not published or uploaded. Regenerate the example on another machine rather than
assuming the above local run folder exists in a fresh clone.

## Important limits / deviations from the original vision

- This is a source-consistent production prototype, not certified natural acting
  or a conversion-tested ad system. Human creative approval remains separate.
- Only three personally reviewed comic excerpts are initially selectable. See the
  tutorial for adding exact unchanged pages. The full book GLB contains more pages,
  but mere inclusion is not permission to randomly select unreviewed material.
- Cast voices and outfits are currently fixed; actors stand at the table. No new
  characters/costumes, seated-performance system or automatic asset promotion.
- Source inserts show the whole original page. Small preview lettering can still
  be difficult to read; source shots hold it longer. There are no automatic captions.
- Finger/thumb contact and opening grips are not production-certified. The test
  measures about 8/23 mm held wrist error and about 93 mm supporting-wrist error
  during opening. These are not claimed to be realistic grips.
- Facial emotions work; local Kokoro is not an emotional-acting control surface.
  Use recordings for precise delivery. No slam foley or ambient sound bed yet.
- Procedural library/fireside sets are used; the bundled library GLB is reserved
  for later scene integration. No user-supplied executable animation code is accepted.
- One production worker per project; additional jobs queue. It does not coordinate
  resources with an independently running Ad Studio controller.
- 600-second audio/mix safety bound; long episodes should be split. Stall limits
  protect processes, not a creative instruction to truncate dialogue.
- Windows/macOS were not tested. Package/model installation needs internet once.
  Cross-platform pixel-identical GPU/TTS output is not promised; exact takes are
  cached and their identities are recorded.
- No Drive upload, publishing, cards, Flite adapter, CLI-agent writer, generalized
  asset manifests, live preview scrubber or parent `./ad` integration in this v1.
  The card-hand format is recorded in [V2_CARD_GAME.md](V2_CARD_GAME.md).

These limits are intentionally visible; no fallback replaces a failed episode
with an end card or reports an incomplete film as a successful delivery.
