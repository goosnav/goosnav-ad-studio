# Ad Studio harness implementation roadmap

Status: proposed sequencing, 2026-10-15. Specification: [HARNESS_SPEC.md](HARNESS_SPEC.md).
This is a decomposition for review and handoff. It is not an executed plan or
evidence of working code. Expand each slice into test-first implementation
steps after the written design is accepted.

## Global constraints

- Preserve existing `python -m studio` behavior and user changes.
- New core uses Python with SQLite and no model-runtime dependency imports.
- Provider/Frame/audio runtimes are subprocess adapters with separate environments.
- Run data and machine references stay out of git; public source references are blank.
- One active worker and one render by default; resource coordination crosses runs.
- Controller-owned validation and durable artifact contracts govern progression.
- No default external delivery or publishing.

## Slice 1 — configuration, contracts and recoverable state

Proposed files:

```text
harness/__init__.py
harness/__main__.py
harness/config.py
harness/contracts.py
harness/store.py
harness/artifacts.py
harness/service.py
harness/cli.py
harness.example.json
tests/harness/test_config.py
tests/harness/test_store.py
tests/harness/test_artifacts.py
```

Interfaces: `load_config(path, overrides)`, `create_campaign(config, brief)`,
`get_campaign(id)`, `transition(node_id, expected_revision, event)`,
`register_artifact(attempt_id, manifest)`. Application service owns writes;
CLI returns serializable domain results.

- [ ] Write behavioral tests before product code.
- [ ] Implement versioned config and artifact contracts, SQLite migrations,
  transactional transitions, leases and immutable run snapshots.
- [ ] Implement `doctor`, `new`, `status` and event inspection through the service.
- [ ] Add blank published config and ignored machine config; migrate actual
  Goosnav paths using the audit inventory and preserve existing local settings.
- [ ] Extend `.gitignore` for local configs, run roots, imported documents,
  weights, media, databases, generated scripts, credentials and logs. Do not
  untrack existing films/assets without an explicit migration decision.
- [ ] Verify staged/public files contain no new local paths or credentials;
  use `git check-ignore` on representative generated artifacts.

Acceptance: malformed JSON is an error; empty optional roots are valid; paths
with spaces/Unicode resolve; zero/negative counts reject; changed config does
not mutate a resumed run; concurrent starts cannot claim the same lease;
traversal/symlink escape and wrong hashes reject; an incomplete attempt cannot
advance the graph.

## Slice 2 — autonomous workers and process supervision

Proposed files:

```text
harness/workers/base.py
harness/workers/codex.py
harness/workers/claude.py
harness/workers/prompts.py
harness/processes.py
harness/controller.py
tests/harness/fixtures/fake_agent.py
tests/harness/test_workers.py
tests/harness/test_recovery.py
```

Interfaces: worker task/attempt/result contracts from slice 1;
`launch(task, profile)`, `poll(attempt)`, `cancel(attempt)`,
`classify_exit(attempt)`. Controller is the only scheduler.

- [ ] Implement real CLI subprocess adapters and streamed logs.
- [ ] Implement task staging, checkpoints, continuation, deadline handling,
  permission-error reporting and bounded provider fallback.
- [ ] Make renderer subprocesses controller-owned jobs.
- [ ] Implement pause/cancel/resume/retry and interrupted-attempt reconciliation.
- [ ] Add a small real-worker smoke task that writes a file and invokes a tool;
  record actual provider result separately from fake-agent test results.

Acceptance: fake primary quota failure invokes backup with surviving checkpoint;
two failures produce a waiting/failed state; exit zero without required output
fails; token/context exhaustion uses continuation; tool denial is not treated
as bad creative work; cancellation kills owned descendants; unrelated PIDs
survive; log volume is bounded in memory; orphaned/partial output is not accepted.

## Slice 3 — source import and writing competition

Proposed files:

```text
harness/sources.py
harness/stages/brand.py
harness/stages/writing.py
harness/prompts/{brief,writer,critic,reviser,selector}.md
tests/harness/test_sources.py
tests/harness/test_writing.py
```

Interfaces: source snapshots -> factual brief -> candidate set -> critique
findings -> candidate revisions -> selection of N script IDs. Preserve IDs and
source hashes throughout. Typed schemas live with the contracts.

- [ ] Implement file/URL source import and extraction with visible failures.
- [ ] Implement concept-free startup and reference/adapt/locked script modes.
- [ ] Run independent writer, critic and selector sessions.
- [ ] Require finding IDs, line/beat evidence and explicit repair outcomes.
- [ ] Enforce candidate diversity, requested count and revision limits.

Acceptance: no input can produce a labeled fictional demo; locked scripts remain
unchanged; insufficient candidates or unresolved hard blockers cannot pass;
final revisions receive critique; quota fallback preserves script revisions;
source text cannot change the controller graph; required facts retain citations.

## Slice 4 — assets, audio, timeline and animation

Proposed files:

```text
harness/stages/assets.py
harness/stages/production.py
harness/timeline.py
harness/audio/base.py
harness/audio/kokoro_runner.py
harness/audio/chatterbox_runner.py
harness/audio/stable_audio_runner.py
harness/audio/piper_runner.py
harness/audio/mix.py
harness/tools/blender.py
harness/tools/ffmpeg.py
tests/harness/test_timeline.py
tests/harness/test_audio.py
tests/harness/test_production.py
```

Interfaces: asset registry, AudioRequest/AudioResult, versioned timeline,
render-job spec and result. Reuse legacy effects/render helpers through bounded
adapters; do not let workers modify their shared code for one ad.

- [ ] Add asset metadata/proxy/LFS validation and library manifests.
- [ ] Install isolated audio runtimes and pin tested model revisions.
- [ ] Benchmark real CPU speech on this machine, recording wall time, memory,
  output duration and transcript; audition generated takes in the review UI.
- [ ] Implement generated effects and supplied/generated music with provenance.
- [ ] Normalize stems and derive measured dialogue/event timing.
- [ ] Implement animatic generation, independent preview review and targeted repair.
- [ ] Implement final Blender render jobs, frame recovery and resource leases.

Acceptance: missing/gated models produce actionable errors; fallback is visible
and obeys policy; no silent/NaN/clipped output passes; differing input sample
rates preserve pitch and duration; changed audio invalidates synchronization;
no speech is cut off; incomplete render sequences resume; unhydrated assets and
draft proxies cannot be packaged as finished production.

## Slice 5 — final editing, Frame and acceptance

Proposed files:

```text
harness/stages/edit.py
harness/tools/frame_runner.py
harness/stages/qa.py
harness/stages/package.py
tests/harness/test_frame.py
tests/harness/test_qa.py
tests/harness/test_package.py
```

Interfaces: accepted picture/timeline/mix -> edited master -> optional Frame
artifact -> QA report -> package manifest. Explicit input/output paths and hashes.

- [ ] Implement end-card, overlay and no-CTA modes through Frame's existing core.
- [ ] Validate encoded streams, audio, durations and per-format framing.
- [ ] Add captions, contact sheets, transcripts and independent creative QA.
- [ ] Implement bounded repair routing and honest partial-batch reporting.
- [ ] Export editable sources, provenance and reproducible run instructions.

Acceptance: Frame preserves audio and does not inject sample copy; blank CTA
skips explicitly; a broken MP4 with a valid extension rejects; alternative
formats do not inflate the distinct-ad count; package hashes match; missing
required output blocks completion; supplied footage remains attributable.

## Slice 6 — local GUI and shared API

Proposed files:

```text
harness/server.py
harness/static/index.html
harness/static/app.js
harness/static/app.css
tests/harness/test_http.py
tests/harness/e2e_gui.py
```

- [ ] Implement setup, writing comparison, production board and review/export.
- [ ] Use the same service mutations as CLI; expose revision conflicts clearly.
- [ ] Stream/tail events and serve registered media with seeking support.
- [ ] Implement loopback default, token/Origin validation and output containment.
- [ ] Exercise the real UI through browser automation and inspect screenshots.

Acceptance: GUI creates and controls the same jobs visible in CLI; refresh
preserves state; double-click start is idempotent; pause/resume/review work;
videos seek/play; script/brand content is escaped; path traversal, cross-origin
mutations and arbitrary command submission fail; keyboard operation works.

## Slice 7 — integration evidence and release handoff

- [ ] Run all relevant tests and an isolated fake-worker failure matrix.
- [ ] Run a real two-ad campaign through the installed worker CLIs and local
  audio, including actual animation and Frame finishing.
- [ ] Interrupt and resume an active campaign; demonstrate primary-to-backup
  recovery using an injected quota failure without consuming an account limit.
- [ ] Review visual output and listen to audio; distinguish automated checks
  from actual human/perceptual acceptance.
- [ ] Verify blank public configuration and ignored local media/config.
- [ ] Update README quickstart, CLI reference, config reference, worker protocol,
  recovery runbook, audio setup and `dev/STATE.md` with exact evidence/limitations.

Completion requires real artifacts and real interface demonstrations. Passing
unit tests with mocked workers is necessary but insufficient.

## Review focus for implementers

1. Worker says done but its background render is still running: controller must
   retain the job and wait for validated media.
2. Primary and backup share a quota/account: fallback must terminate within
   bounds and explain unavailable capacity.
3. Imported locked script or changed voice conflicts with duration: preserve
   intent, invalidate timing, surface an explicit decision instead of truncation.
4. GUI and CLI race or controller dies during artifact promotion: one committed
   transition, no duplicate accepted work and inspectable recovery.
5. Blank public config uses Frame defaults or a stale Goosnav path: no private
   content leakage and no accidental branding on another user's output.

Add tests for these cases in the owning slice before implementation, and keep
their observed outcomes in the final handoff.
