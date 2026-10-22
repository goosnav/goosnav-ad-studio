# Comic Theatre Implementation Plan

**Historical design plan.** The owner's later template/GUI/portable-assets request
is implemented under [BUILD_CONTRACT.md](BUILD_CONTRACT.md). The original task
checklists below are retained as design history, not the current task/status list.
See [VERIFICATION.md](VERIFICATION.md) for delivered behavior, evidence, deviations
and remaining scope; do not infer that every original ambition is implemented.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. This plan is not an implementation claim. All unchecked items remain future work.

**Goal:** Render a complete book-selling conversation from human-authored JSON, with explicit facial/reaction controls, tested book-action rails and local voices, without paid APIs or an AI animator.

**Architecture:** Validate an episode and explicit asset manifest, prepare measured takes, compile a deterministic performance timeline, and render it through a reusable Three.js stage. Encode verified segments to a complete MP4. Keep optional AI, local voice backends and delivery outside the deterministic core.

**Tech Stack:** Node ESM >=22.12, JSON Schema 2020-12/Ajv, Three.js WebGL, Playwright/Chromium, FFmpeg/ffprobe; optional Python/Kokoro and non-neural Flite.

**Spec:** [DESIGN.md](DESIGN.md), with [TECH_STACK.md](TECH_STACK.md) for evidence and tradeoffs.

## Global Constraints

- Human JSON + installed local speech must work with network blocked, without paid APIs, Codex or Claude. Recorded mode also works without a speech model.
- JSON owns expressions, face overrides, reactions and book actions; omitted settings use documented defaults, never an AI animator.
- Book opening/turning/holding/reading/placing/closing/slamming are required for v1. Card-hand gameplay is v2 only.
- The package must work outside Ad Studio; no parent/sibling imports or fixed asset roots.
- Archived assets, external asset URLs, path escapes and LFS pointer files are rejected.
- Preserve original art, source provenance, actor identity and measured speech timing.
- No silent filler/end-card substitution, truncation, automatic voice change or success on incomplete output.
- No automated asset promotion, public publication or credentials in checked-in files.
- Preserve existing dirty parent files, submodule changes and active runs.
- No mandatory generation-time deadline; benchmark targets are not abort thresholds.
- All runtime tests/commands in this plan are proposed and become available as their tasks land.

## Review Focus

1. Asset refactors and symlink/GLTF escapes: relocated manifests work; unavailable or unsafe assets fail before synthesis (Task 1).
2. Two actors sharing a model: skeleton, expressions and clothing remain independent; seeking matches sequential playback; book grip/page identity survive every rail (Tasks 2–3B).
3. Browser crash, partial segment or changed audio during resume: only verified matching work is reused; full dialogue is preserved (Task 4).
4. Simultaneous jobs, stale leases, and a parent studio render: no collisions or unbounded GPU work; errors remain visible (Task 4).
5. No network, missing TTS, unsupported emotional control, and mismatched comic edition: manual production stays usable; no false quality or source claims (Tasks 1, 5–7).

## File and responsibility map (planned)

```text
bin/theatre.mjs                 CLI only
schemas/episode.schema.json    human/AI authoring contract
schemas/library.schema.json    asset/source/voice manifest contract
src/contracts.mjs              structural + semantic validation, helpful errors
src/library.mjs                root-safe resolution, hashes, rig capabilities
src/audio.mjs                  recorded takes, PCM measurement, mix, cache
src/timeline.mjs               sample-time beat/shot/performance compilation
src/performance.mjs            pure arbitrary-time actor/face state evaluation
src/actor.mjs                  cloned GLTF skin and head-attached face adapter
src/stage.mjs                  validated stage anchors, cameras, book/page display
src/book-rails.mjs             book state machine, authored tracks and grip constraints
src/player.mjs                 preview and renderAt(frame) surface
src/server.mjs                 allowlisted loopback media/module serving
src/capture.mjs                browser lifecycle and exact-frame segments
src/encode.mjs                 checked subprocesses, segment/final MP4 checks
src/jobs.mjs                   atomic receipts, invalidation, resume and status
src/lease.mjs                  process-safe shared resource admission
src/adapters/                  optional writer/voice/studio lease/delivery adapters
presets/                       versioned scene, performance and voice recipes
examples/                      human-editable episodes + source packets
tests/                         node unit, integration and browser tests
tools/benchmark.mjs            actual latency/resource measurement
dev/                           design, plan, review and measured results
```

Add own `package.json`, lockfile, `.gitignore`, notices, and optional voice setup
instructions in the task that needs them. Do not install the whole game stack,
create a nested Git repository, or add this to the main `./ad` command yet.

## Task 1 — Validate a portable episode and library

**Files:** `schemas/*`, `src/contracts.mjs`, `src/library.mjs`,
`tests/contracts.test.mjs`, `tests/library.test.mjs`, package metadata and example manifest.

**Interfaces:**

- `loadEpisode(file, libraryFile) -> Promise<{episode, library}>` throws an error
  with code, JSON pointer and actionable message.
- `resolveAsset(library, id) -> Promise<{id, path, sha256, kind, capabilities}>`.
- Library shape: `{schema: "comic-theatre-library/v1", roots: {name: path},
  assets: {id: {root, path, sha256, kind, adapter?, capabilities?}},
  products: {id: {edition_id, book_asset, sources, evidence, allowed_scenes}},
  scenes: {id: {preset, environment?, slots, book?, rails}},
  sources: {id: {image, pdf_sha256, pdf_page, printed_page?, spread_id, side, transcript,
  edition_status, edition_id?, evidence?, panels?}}, voices: {id: profile}}`.
  `image` is an asset ID; hashes live on asset records. Rig `adapter` names are
  built-in enum values, never executable plugin paths supplied by the manifest.
- Scene slot records have actor position/yaw, rest-pose ID, gaze anchors and camera
  anchors; exact transforms are authored/verified in Task 3, not guessed by scripts.
- Voice profiles name adapter and backend-supported settings. Credentials and
  executable configuration belong in local operator configuration, not episode JSON.

- [ ] Write failing table-driven tests covering the design's beat union, all enums,
  duplicate IDs, unknown fields, missing sources/speakers, bad ranges and NaN.
- [ ] Test omitted scene/seed/default face fields, per-channel explicit overrides,
  invalid supplied values, and product-to-source/exterior bindings even without
  an end card. Test that missing evidence blocks normal output, not just upload;
  developer draft mode is explicit and never deliverable.
- [ ] Write relocation tests: identical files under a moved root resolve to the
  same hashes; changing cwd does not change resolution. Reject archive symlinks,
  traversal, malicious GLTF references and LFS text stubs before audio is invoked.
- [ ] Run `node --test tests/contracts.test.mjs tests/library.test.mjs`; confirm
  failures are the missing implementation, not missing test tooling.
- [ ] Implement JSON Schema validation plus semantic/reference checks. Manifest
  source claims cannot be upgraded by an episode. Every normal book-v1 episode
  needs confirmed edition evidence and matching book metadata. At run creation,
  save generated seed and selected compatible scene/appearance in resolved JSON;
  validation alone must not mutate the script or silently pick incompatible assets.
- [ ] Run the tests to green; manually inspect one diagnostic for a misspelled
  emotion to ensure it lists the allowed values.
- [ ] Commit only these experimental files, with no parent or submodule changes.

## Task 2 — Recorded audio and pure performance compiler

**Files:** `src/audio.mjs`, `src/timeline.mjs`, `src/performance.mjs`,
`tests/audio.test.mjs`, `tests/timeline.test.mjs`, `tests/performance.test.mjs`.

**Consumes:** validated Episode and resolved Library from Task 1.

**Produces:**

- `prepareAudio(episode, library, options) -> Promise<TakeMap>`;
  `TakeMap[lineId] = {pcmPath, sha256, sampleRate:48000, sampleCount, activity}`.
  `activity` is an array of `{startSample,endSample}` intervals relative to the take.
- `compileTimeline(episode, takes, presets, railSchedule) -> Timeline`, with schema/version,
  sample rate, duration samples, lines `{id,speaker,startSample,endSample,takeId}`,
  shots, source windows, expression/gaze/gesture/blink/reaction events, book-rail
  events and mouth curves.
- `evaluatePerformance(timeline, sample) -> {actors, camera, source, book}`;
  actor states contain rest-relative transforms and explicit face parameters.
  Until Task 3B lands, tests use an empty rail schedule and an already-open stage
  fixture, not a claim that book actions are implemented.

- [ ] Write tests using tiny generated PCM fixtures with known sample counts:
  starts follow the preceding take plus authored pause; the final line and reaction
  survive; frame count is the ceiling of duration × FPS; no word-count timing.
- [ ] Write tests for silence, clipping, corrupted audio, Unicode filenames, audio
  cache keys, overlapping-line rejection, and distinct per-speaker mouth activity.
- [ ] Write seek/replay tests: evaluate time B alone, after A, and after C; compare
  identical state. Repeat at 24/30 fps. Same seed reproduces events; changed seed
  changes only permitted variation, never lines/source order or explicit cues.
- [ ] Test left/right brows, eye openness, mouth curvature and blink overrides;
  omitted channels inherit emotion defaults. Test reaction start/end/offset times,
  bounded channels, overlap errors, pause extension and speaker mouth ownership.
  Test resumed runs use the saved scene/seed and do not select new assets.
- [ ] Run the three test files and observe red; implement measured PCM processing,
  deterministic scheduling and absolute-time performance interpolation.
- [ ] Run to green; inspect a generated dry audio mix with ffprobe. Include actual
  recorded speech in later integration testing; synthetic wave fixtures only prove
  measurements, not intelligibility or acting.
- [ ] Commit the standalone compiler milestone.

## Task 3 — One convincing library stage in real WebGL

**Files:** `src/actor.mjs`, `src/stage.mjs`, `src/player.mjs`, `src/server.mjs`,
`presets/library-table.json`, `tests/actor.test.mjs`, `tests/player.browser.test.mjs`,
`dev/PROVENANCE.md`, example source packet and two-actor manifest.

**Consumes:** Timeline, `evaluatePerformance`, validated resolved assets.

**Produces:**

- `createActor(asset, adapter, appearance) -> Promise<Actor>` with
  `applyState(state)` and `dispose()`.
- `createPlayer(canvas, {timeline, library, preset}) -> Promise<Player>`;
  `Player.renderAt(frame)`, `Player.diagnostics()` and `Player.dispose()`.
- Diagnostics identify visible actors, selected shot/source ID, missing materials,
  runtime errors, frame number and render backend. They are evidence, not a claim
  to measure humor.

- [ ] Write real-browser tests for two separately cloned skins and materials: moving
  one actor's head or face does not move/change the other. Match direct seek and
  sequential render within same-device image tolerance.
- [ ] Write tests for mouth closing in pauses, expression blending, head attachment
  under extreme approved poses, missing bones, removed GLB and corrupted images.
- [ ] Run red. Extract the small rest-pose/face logic from the audited Homunculus
  files with owner provenance; do not instantiate Room or copy unrelated gameplay.
- [ ] Implement seeded talk/listen/nod/shrug/page-glance recipes and eight bounded
  expression presets. Validate against the real sealed-face model. Missing rig
  capability produces an explicit preflight error, not invisible acting.
- [ ] Implement the library seating/camera anchors and already-open source display.
  Verify both the real page texture on the book and full-size/panel inserts. Use
  the model's correct axes and scale; preserve original artwork pixels.
- [ ] Render preview frames and watch/listen to a short two-voice performance.
  Inspect three-quarter faces, source readability at phone size, seated pose,
  clothes, desk clipping and gaze. Record actual observations, not prior-film QA.
- [ ] Run browser tests to green and commit. No wardrobe generation yet.

## Task 3B — Book-specific animation rails (required v1)

**Files:** `src/book-rails.mjs`, `schemas/rail.schema.json`,
`presets/book-rails.json`, `tests/book-rails.test.mjs`,
`tests/book-rails.browser.test.mjs`, `dev/BOOK_RAIL_REVIEW.md`.
Author additive rail/rig assets in the configured 3D library following its current
instructions; choose exact new paths after checking its active layout and dirty
work. Do not overwrite existing character/book files.

**Interfaces:**

- `compileBookRails(episode, takes, library) -> RailSchedule` validates the finite
  states in DESIGN.md and supplies duration/contact/camera markers to Task 2.
- `evaluateBookRail(schedule, sample) -> {bookPose, leafPoses, gripTargets,
  reservedChannels, activeSpread, foleyEvents}`. Values are absolute and seekable.
- Rail data declares source/book/actor hashes, states, anchor transforms, tested
  speed range, grip sockets, page map, contact tolerance and permitted cameras.
  Start with maximum 0.02 m grip-position error at human scale; revise only with
  recorded measurement and visual justification, never hide a failing fixture.

- [ ] Write failing tests for legal/illegal state transitions, adjacent-only turns,
  selected spread identity, unsupported actor/scene combinations, action speed
  bounds and hand-channel conflicts during line gestures. A rejected action must
  not become a no-op or a teleport.
- [ ] Test a turn to a new focus source followed by implicit full/panel/source-line
  shots; all follow the new source. Explicit inserts may select the other current
  page, not an unrelated page. Reject closed-book inserts and wrong panel IDs.
- [ ] Author open, adjacent turn, lift/hold, read, place, close and slam once for
  the supported book and Homunculus rig, using measured grip sockets and baked
  animation/constraints. Use Blender offline if useful; runtime is Three.js.
- [ ] Implement the finite-state rail evaluator and approved reveal cuts. Lines
  with `posture: read` work in table-open or held-open state while speaking;
  `book.read` is a timed silent-reading beat. Track one explicit book owner and
  reject another actor's simultaneous grip/manipulation; handover is not v1.
- [ ] Add real-model tests sampling every frame at allowed speed extremes: grip
  distance, required contact, book/hand transforms, selected leaf textures and
  closed/open state. Assert no motion on the listener's cloned rig.
- [ ] Render and inspect short real clips of each action from its approved cameras.
  Check fingers/cover intersections, believable weight, page readability and face
  visibility; numeric grip tests alone do not prove good animation. Attach timed
  foley to contact markers, never wall clock.
- [ ] Put reusable source/exports/metadata/previews in the active asset repo, run
  rig/export/layout checks and record provenance. No automatic unreviewed asset
  promotion. Commit only owned files; push only when authorized.
- [ ] Run rail tests and a complete open → read dialogue → turn → hold/read → place
  → slam episode. Record defects honestly. Do not call book-v1 complete without
  this demonstration.

## Task 4 — Complete MP4, reliable restart and parallel launches

**Files:** `src/capture.mjs`, `src/encode.mjs`, `src/jobs.mjs`, `src/lease.mjs`,
`bin/theatre.mjs`, `tests/capture.test.mjs`, `tests/jobs.test.mjs`,
`tests/end-to-end.test.mjs`, `tools/benchmark.mjs`, CLI documentation.

**Consumes:** Task 3 Player, Task 2 takes/timeline, Task 1 contracts.

**Produces:**

- `runEpisode({episodeFile, libraryFile, outputRoot, voiceMode}) -> Promise<RunReceipt>`.
- `resumeRun(runId, outputRoot) -> Promise<RunReceipt>`.
- `RunReceipt = {runId, status, inputKey, stages, video?, verification?, error?}`;
  `video = {path,sha256,width,height,fps,frames,durationSeconds}`.
- `acquireRenderLease(config, signal) -> Promise<{release()}>`;
  `renderSegments(playerConfig, timeline, runDir) -> Promise<SegmentReceipt[]>`.
- Segments contain `{startFrame,endFrame,path,sha256,inputKey}` with end exclusive.

- [ ] Write failure-injection tests for browser death midway through a segment,
  encoder nonzero exit, disk exhaustion, missing/corrupt segment, stopped parent,
  changed source/audio and attempted overwrite of a completed output.
- [ ] Write integration tests launching three independent CLI processes with one
  GPU lease. Assert isolated directories/receipts and bounded concurrent export.
  Test stale owner detection and release on cancellation without stealing a live lease.
- [ ] Add a test where frames 0..N contain dialogue but a late segment is missing:
  no final MP4 is reported verified, and no end-card-only artifact is substituted.
- [ ] Run red; implement per-run directories, atomic receipts, cache identity,
  exact half-open segments, bounded retries, progress output and resumable errors.
- [ ] Implement FFmpeg concat/mux and final decode/ffprobe checks: audio+video
  present, dimensions correct, all frames accounted for, last line included, A/V
  durations within one frame plus encoder padding. Check representative content
  windows against compiled shots so a wrong static source cannot pass on duration alone.
- [ ] Run the full recorded-voice flow with external network blocked. Rename/copy
  the experimental folder to an unrelated temporary directory and rerun there with
  a relocated manifest; the parent repository must be unnecessary.
- [ ] Benchmark the full 60-second example at both sizes, cold/warm, under a recorded
  hardware/backend configuration. Optimize measured capture overhead before adding
  more features; document misses rather than weakening the episode.
- [ ] Run tests to green, update README with working commands and measured limits,
  and commit. This is a recorded-voice technical candidate; book-v1 additionally
  requires Task 3B's action rails and Task 5's local speech path.

## Task 5 — Local automatic voices without paid calls

**Files:** `src/adapters/flite.mjs`, `src/adapters/kokoro.mjs`,
`voices/kokoro_worker.py`, voice setup/lock files, `presets/voices.json`,
`tests/voice-adapters.test.mjs`, `dev/VOICE_REVIEW.md`.

**Interface:** `VoiceAdapter.capabilities()` and
`VoiceAdapter.synthesize({text, profile, settings, outputPath}) -> Promise<Take>`;
Take must pass the same measurement contract as recorded audio.

- [ ] Write tests proving recorded mode imports no optional TTS package and never
  starts a model process or network request. Missing backend yields installation
  instructions before rendering; unsupported controls are reported explicitly.
- [ ] Test the normal default Kokoro path with model files preinstalled, network
  blocked and no Codex/Claude/API credentials available. Model download is an
  explicit one-time setup action, not an automatic surprise during a render.
- [ ] Write tests for stable voice identity, cached take reuse, changed model/settings
  invalidation and no truncation during provider failure. Retry only the failed take.
- [ ] Run red; implement explicit adapters with shell-free argv invocation, pinned
  model identity in receipts, process timeout/cancellation and bounded concurrency.
  Cache prepared PCM, not just a path to possibly changed external audio.
- [ ] Run to green. Prepare one stable contrasting voice pair and listen to plain,
  curious and dry readings; record which emotion controls are supported versus
  advisory. Don't treat a delivery note as an implemented synthesis parameter.
- [ ] Compare TTS episode with original recordings; preserve the latter as the
  quality reference. Commit with documentation using the owner's intended meaning:
  no paid APIs or agent calls; local speech is normal, recordings are optional.

## Task 6 — Solo format, limited variation and reusable wardrobe

**Files:** `presets/fireside-reader.json`, tested variation recipes,
`tests/presets.browser.test.mjs`, source/wardrobe manifests and review records.
Asset files are additive within the **configured active 3D repository**, not a
hardcoded checkout path. Resolve its instructions, layout and dirty state again
before touching it. Record exact chosen new paths in the task receipt.

**Interface:** same Player/Timeline contract; scene capabilities declare one/two
seats, legal shot choices and actor adapters. Clothing changes preserve rig IDs.

- [ ] Write tests for one-person validation, two-person stage rejection when
  incompatible, deterministic legal variation and explicit camera/gesture overrides.
- [ ] Implement solo fireside placement and test quiet listening/reading intervals;
  no pipeline fork, script rewrite or agent required. Validate all requested book
  rails in this arrangement; exclude incompatible presets from random selection.
- [ ] Add two non-destructive wardrobe variants, for example a muted cardigan and
  a restrained jacket, using approved character geometry. Keep adjustable appearance
  metadata per actor; do not recolor canonical comic art or invent brand lore.
- [ ] In the asset repository, include editable source, reproducible builder,
  portable export, hash/provenance and face/sitting/gesture previews. Run relevant
  rig/export checks and `make check-layout`; verify LFS handling. Never stage the
  user's unrelated asset changes. Push only when authorized and checks pass.
- [ ] Generate/view/listen to one duet and one solo, including more than one seed.
  Compare readable comic detail, reaction timing and voice/cast consistency. Record
  technical QA and owner creative feedback separately.
- [ ] Commit engine/preset changes; document the asset revision without forcing
  parent submodule updates over ongoing user work.

## Task 7 — Optional writer, delivery integration and extraction proof

**Files:** `src/adapters/writer.mjs`, `src/adapters/studio-delivery.mjs`,
`src/adapters/studio-lease.mjs`, `tests/writer.test.mjs`,
`tests/delivery.test.mjs`, `dev/EXTRACTION.md`, final README.

**Interfaces:**

- `draftEpisode({brief, sourcePacket, writerConfig}) -> Promise<Episode>`;
  exactly the same validation as human input, saved before production.
- `DeliveryAdapter.enqueue(verifiedVideo, metadata) -> Promise<DeliveryReceipt>`;
  no enqueue from unverified video or missing provenance. No silent source archive.
- Lease adapter honors the parent resource contract when explicitly enabled;
  standalone still works without either studio adapter.

- [ ] Write tests for invalid writer JSON, timeout/cooldown, credential redaction,
  one repair maximum, refusal to alter source membership, and no writer invocation
  from normal render/resume. Pin model choice in receipt after dynamic policy resolution.
- [ ] Implement a compact source-grounded writer prompt: one observable comic
  premise; a clear difference between characters; understandable dialogue; an
  optional over-serious interpretation; no physical stunt required to understand
  the joke. No manufactured quotation, author psychology or sales benefit.
- [ ] Write delivery tests for duplicate enqueue, 429/backoff, transient server errors,
  restart, auth-blocked delivery, a lost response after accepted upload and three
  concurrently finished videos. Verify one complete MP4 per unique run and immediate
  per-video eligibility. Do not perform live uploads in automated tests.
- [ ] Integrate only with a verified durable uploader contract; if unavailable,
  leave delivery explicitly unsupported rather than writing another best-effort
  upload-and-forget path. Keep local rendering available regardless.
- [ ] Run an extraction test from a clean standalone copy, with its own locks and
  manifest; exercise manual, local-TTS and mocked writer/delivery paths separately.
  Confirm credentials, full books, unlicensed voices and cache/output binaries are
  absent from the distributable source package.
- [ ] Run the complete experimental test suite and review one real final video plus
  benchmark results. Update feature status and known limitations. Recommend a
  separate repository only after this proof; do not create one automatically.

## Completion record required from implementation

Record test commands/results, real sample output paths, what was personally viewed
and listened to, hardware-specific performance, remaining defects and source/asset
provenance. Never mark the plan executed merely because documentation exists.
Normal runs should require no human intervention after valid input; initial design,
asset promotion and creative format review are development decisions, not new
per-episode gates.
