# Implementation and verification record

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
