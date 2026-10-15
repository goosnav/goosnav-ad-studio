# Hands-off ad engine build plan

The owner approved proceeding on 2026-10-15, with these refinements: minimal
input, existing subscription CLI workers, explicit quality/cost model routing,
bounded research, robust exceptions, and creative autonomy inside scoped jobs.

## Decisions

- Build in `harness/` on `feat/agent-harness`; preserve the existing local
  checkout and its uncommitted playbook. No worktree or repository migration.
- CLI first: `python -m harness make` is the main production interface. A GUI
  is a separate optional surface; it is not required to use the engine.
- Website plus optional `{name, description, url}` products are sufficient.
  Brand sources and asset roots come from ignored local configuration.
- Use native CLI agent loops, not API calls. Remove API-key environment
  overrides and check subscription authentication before launching workers.
  Subscription quota is finite; do not market execution as unlimited/free.
- Strong writers, affordable critics/checkers, capable production workers.
  Explicit model and effort are recorded on every attempt; provider failure
  moves to the same role on the other CLI rather than degrading writing quality.
- Persist state in SQLite; store large artifacts in isolated run workspaces.
  Serialize controllers with an OS file lock. Durable attempts and artifacts
  provide recovery; successful subprocess exit is not proof of success.
- Agents get task briefs, tools, deadlines, deliverables and repair notes.
  Controller code handles state and media checks, not advertising creativity.
- Keep a short sourced research stage. Translate references into techniques;
  never ask workers to copy scenes/dialogue or reproduce another company's ad.
- Preserve actual model/audio/asset provenance. Do not label an untested optional
  model as installed or validated.

## Work sequence and tests

- [ ] Configuration and state: strict input validation, blank public config,
  verified Goosnav local config, atomic state, locking, source snapshots.
  Tests: invalid inputs, immutable snapshots, escaping paths, concurrent locks.
- [ ] CLI workers: exact command arrays, explicit role models, timeouts,
  cancellation, streaming logs, quota/context classification and backup handoff.
  Tests: quota primary -> backup, missing/invalid output, hung subprocess,
  denied tools, quota cooldown, no key-based billing fallback.
- [ ] Workflow: research -> writing -> critique -> revise -> final critique ->
  selection -> per-ad assets/audio/animation/review/edit -> Frame -> media QA ->
  creative QA -> package. Tests: actual graph order, review rejection/repair
  bounds, insufficient selections, restart, invalid artifacts, partial batches.
- [ ] Production helpers: supervised commands, media validation, Frame wrapper,
  local Hugging Face voice/effects runner, measured audio manifest. Tests: real
  FFmpeg fixture, audio preservation, missing model/dependency, local path checks.
- [ ] CLI and documentation: make/plan/status/run/pause/cancel/resume/retry,
  doctor and local outputs. Tests: subprocess CLI and subscription worker smoke.
- [ ] Verification: run behavioral tests and actual interface checks, fresh
  review, fix important findings, record exact evidence and remaining limits.

## Scope discipline

No hosted service, generic plugin marketplace, distributed queue, custom agent
framework, automatic ad publishing, or elaborate scoring UI. Use a small number
of modules and readable JSON contracts. Every document records decisions,
trade-offs and evidence, not private deliberation or a running thought transcript.
