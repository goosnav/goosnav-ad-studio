# Development state

Updated: 2026-10-15 (second session)

## Current position

**The harness is implemented and usable.** CLI, GUI, state machine, worker
supervision with provider fallback, contracts, media checks, Frame CTA and
packaging are built and tested. A first real end-to-end batch on the Goosnav
configuration is in progress (see below).

Start a batch: `python3 -m harness make --count N [--concept "..."]` or
`./"Start Ad Studio.sh"`. Operating guide: [OPERATIONS.md](OPERATIONS.md).

## What was built

Session 1 (commit `7194eb7`): the whole `harness/` package except the GUI,
blank `harness.example.json`, local `harness.local.json` with the Goosnav
links, `.gitignore` for configs/media/run state, tests, and the design docs.

Session 2:

- `harness/gui.py` + `python -m harness gui` + top-level `Start Ad Studio.sh`,
  `.command` and `.bat` (the `.bat` goes through WSL; the harness is POSIX-only).
  The GUI never runs workers in-process: it spawns the CLI detached, so the
  controller lock still holds, and it serves files only from the harness home.
  It binds to localhost by default because it can launch agents and has no
  login; `--lan` exposes it.
- Review exhaustion no longer stalls a hands-off batch: after the last repair
  round, non-blocking findings continue downstream as `accepted_with_notes`;
  only `blocking` findings stop for a person.
- `output.folder`: delivered ads are copied to `<folder>/<run>/ad-NN.mp4|zip`.
  Locally `business/studio/output/harness`.
- Target length: `output.target_seconds` (default 10). The accepted range is
  derived as 80-130 % unless `min/max_seconds` are set. Every worker brief states
  it, writers time scripts to it, and `check_video` enforces the range. It can be
  set with `make --seconds N`, the GUI's "Target seconds" field, or the config.
- Fixed `finish_frame` with relative paths (subprocess ran with `cwd=work`).
- Owner film rules (www. addresses, real drawings only, library product models,
  usable over polished) added to the local `brand.direction`.
- Docs: `OPERATIONS.md` (new), `dev/README.md` module map, root README quickstart.

## Evidence

Fixture tests (scheduling, not creative quality): `python3 -m pytest -q tests`,
46 passing. They cover config validation, store/lock, contracts and path escape,
quota failover, resume without repeating work, repair rewinds, exhausted
reviews, a two-ad pipeline with real FFmpeg media and delivery copies, CLI
errors, and the GUI.

Live evidence on this machine (2026-10-15):

| Check | Result |
|---|---|
| `doctor` with Goosnav config | ffmpeg, blender, both CLIs logged in via subscription, Frame, all sources present |
| Codex worker (session 1) | research stage completed on `gpt-6.1-sol`, 109 s, valid sourced brief |
| Claude worker smoke | `claude -p` Haiku wrote a valid `result.json`, 6 s, model observed `claude-haiku-4-5-20251001` |
| Provider failover (live) | Codex returned a usage-limit error after 2.4 s; it was classified `quota`, put on cooldown, and research moved to Claude Sonnet, which succeeded |
| Kokoro voice (session 1) | `audio.py` produced 48 kHz WAV + provenance sidecar, CPU, 6.7 s |
| Frame CTA | synthetic 8 s 1080x1350 master -> Frame overlay "READ THE BOOK." + `www.goosnav.shop`, audio kept, passed `check_video` |
| GUI | pages render, `/file` refuses paths outside the home, bad config and `count=0` rejected in-browser |

### First Goosnav end-to-end batch

Run `20261015-130307-23007d15`, `make --count 1`, no concept (open brief),
Goosnav local config. The Codex quota was exhausted, so every stage after
the failover ran on Claude.

- research: succeeded (Sonnet). Ingested both brand PDFs, both script banks and
  the vignette bible. Verified live prices ($29.95 Book Two, from $14.95
  Goosklerf), flagged the script bank's prices as stale, and proposed five
  directions using the 3D character library.
- writing contest and production: in progress.

## Known limits

- Audio: Kokoro is installed and proven. Chatterbox and Stable Audio Open are
  wired in `audio.py` but not installed; Stable Audio needs a Hugging Face login
  and licence acceptance. Effects therefore come from procedural synthesis.
- The GUI has no authentication. Keep it on localhost or a trusted LAN.
- POSIX only (fcntl, process groups). Windows means WSL.
- A run's config is frozen at creation. Code changes apply to a running
  controller only after `resume`.
- Creative quality of animation depends on the producer model and the time
  budget (4 h per production attempt). Review loops catch failures; they do
  not guarantee taste.

## Next steps (for whoever continues)

1. Finish or resume the end-to-end batch above and record the outcome here.
2. Watch the first real `animate`/`edit` sessions: if workers regularly run
   out of time, raise `limits.production_timeout_seconds` or split rendering
   into its own controller step.
3. Install Chatterbox in the audio venv for more expressive voices; consider
   Stable Audio Open Small once the HF licence is accepted.
4. Optional: let two writers (Codex and Claude) each draft candidates when both
   quotas are available, for more diverse scripts.
