# Ad Studio development

The harness (`harness/`) is the hands-off ad engine: a deterministic state
machine that hires `codex` and `claude` CLI sessions as scoped workers and
turns an optional concept into N finished, CTA-framed short videos.

Read in this order:

1. [STATE.md](STATE.md): what works, what is proven, what is next. Start here.
2. [OPERATIONS.md](OPERATIONS.md): running, recovery, configuration, audio setup.
3. [HARNESS_SPEC.md](HARNESS_SPEC.md): the design and acceptance criteria.
4. [WORKER_GUIDE.md](WORKER_GUIDE.md): the tool guide every worker receives.
5. [BUILD_PLAN.md](BUILD_PLAN.md): decisions and the build checklist.
6. [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) and
   [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md): the original pre-build design
   decomposition and inventory. They are historical. The module layout
   that was built is smaller than the roadmap's (see STATE.md).

## Module map

| File | Owns |
|---|---|
| `harness/cli.py` | `python -m harness` commands, `doctor` |
| `harness/gui.py` | local browser page over the same store and commands |
| `harness/config.py` | strict config schema and defaults (no brand data) |
| `harness/store.py` | SQLite run state, events, controls, cooldowns, controller lock |
| `harness/workflow.py` | the task graph, scheduling, repair loops, provider fallback |
| `harness/workers.py` | exact CLI command lines, supervision, failure classification |
| `harness/models.py` | role tier -> concrete model resolution |
| `harness/briefs.py` | the job description each worker gets |
| `harness/contracts.py` | `result.json` validation and artifact promotion |
| `harness/media.py` | FFprobe/FFmpeg checks, Frame CTA, packaging |
| `harness/sources.py` | brand/script/inspiration snapshots |
| `harness/audio.py` | local Hugging Face voice/effects runner (own venv) |
| `harness/frame_runner.py` | runs inside Frame's venv |

Rules for the next implementer:

- Record actual implementation and verification in `STATE.md`.
- Keep the controller deterministic and small. Creative judgment belongs in
  `briefs.py` job descriptions and the workers, not in controller code.
- Preserve existing films, the legacy `python -m studio` CLI and user edits.
- Keep customer configuration, imported documents, media, weights, run state
  and logs out of version control (`.gitignore` covers them).
- Never describe fake-worker tests as evidence of a real agent or audio run.
- `python3 -m pytest -q tests` must stay green.
