# Development state

Updated: 2026-10-20

## Current position

2026-10-20 production simplification: the user contract is a short
script guide -> animator-owned scene/audio/render -> editor -> deterministic
finish/technical checks -> immediate per-ad MP4 upload. Independent CLI launches
must run concurrently with separate run locks and a throttled delivery queue.
Existing stage graphs stay resumable. Baseline is 4a23af2; the latest medium run
20261020-143234-5a7e7a9f took 1439 seconds and 22 model attempts, with 811 seconds
in assets/board review, then failed despite a rendered cut. The animation helper
also reproducibly replaced the staged head/neck pose. Acceptance requires real
fresh CLI runs, timed script/animation/edit phases, preserved scene poses,
concurrent generation, correct full-story exports, and verified MP4 delivery.
Unit scheduling fixtures alone do not satisfy that acceptance contract.

Implemented: new CLI jobs use script -> animate -> edit -> frame -> qa -> package.
The writer emits one guide at low reasoning using the selected model; animation
keeps the chosen intensity. Measured audio/render/edit helpers preserve portable
checkpoints and existing poses. Independent CLI launches use per-run leases;
same-second launcher logs are unique and controls print explicit IDs. Drive has a
separate serialized transfer lease and shared cooldown. Optional reusable assets
from the animator still enter the validated publication path after packaging.

Live verification: medium 20261020-154021-1b7cc5e1 ran alongside low
20261020-154022-5a11c602. The medium film completed autonomously in 631.9 active
seconds (script 13.6, animation 453.9, edit 82.9, Frame 38.6, QA 31.9, package 1.9).
The 9.002-second H.264/AAC export contains the full gate/card-game story and a
2.5-second rotating-product end card; sampled frames were independently viewed.
Drive first rate-limited it, then verified the MP4 on attempt 2 while another
run was generating. The old background uploader was restarted once to load the
per-run lock update. No manual verdict or budget extension was used.

The first low trial failed at 12.3 minutes: a speech-model/character-path collision
prompted bad cached-line reuse, then an overly strict two-second freeze rejection
spent a full rerender before the editor rejected the missing product/story.
It was NOT uploaded or counted as success. Fixes separate those model namespaces,
keep explicit reused-take constraints, measure short holds cumulatively (reject
mostly static films), and check speaking scenes before full render. Low guides
now limit construction to a small existing setup; high remains unrestricted by
that low-scope rule. The second low trial, 20261020-155220-99a6096f, failed at
10.0 minutes and was withheld from upload: an oversized hand-imported product
was repaired, but the film remained frozen. Disabled library NLA clips were
incorrectly protecting every channel from generated idle/reaction motion. A
failing real-Blender regression reproduced this; procedural performance now
ignores muted demo tracks/strips while preserving active authored animation.
An independent face-direction regression also found that a head-center ray
accepted the back of a skull; preflight now follows the posed anatomical forward
direction. Production prompts recommend the tested product import helper and
a small preview before full rendering. A diagnostic rerender restored subtle
motion but remained too static; that was not counted as a passed ad.

Fresh low 20261020-160947-f81d18f3 completed autonomously in 377.2 active seconds
(6.3 minutes), with a 7.7-second writer invocation and 28.7-second editor invocation.
The animator's first submission needed an asset-ID correction; automatic Sonnet
fallback reused the existing film in 39.5 seconds, without another render. The
submission helper now checks exact catalog IDs before the worker finishes, so
future mistakes can be repaired in-session. The final 9.002-second 1080x1350
H.264/AAC film contains the full conversation and approach, followed by the 2.5-second
rotating product card with blue underlined serif URL. Final frames were independently
viewed; no manual approval, verdict edit or time extension was applied. The first
Drive attempt received the shared-project quota error; durable retry is pending.
Minor limitations remain: basic movement, small opening product, no ambient bed;
voice acting was not independently listened to. These are observed runs, not a
guarantee that every generated story will pass. Writer memory now explicitly
discourages repeating recent premises unless the user requests a variation.

Verification checkpoint: full suite 766 passed, 2 skipped in 391.6 seconds; latest
changed-module regressions 61 passed. Independent review findings (script resume budget, strict
editor verdicts, versioned edit reuse, selected-take controls, full-frame CTA
contract, freeze accumulation) have targeted reproductions and fixes. Fresh
independent concurrency/delivery and motion/face-check reviews found no evidenced
blockers. The nested
brain pin was advanced from ae51c66 to upstream 1831fdd after a clean-tree check;
asset layout/archive-isolation checks pass. The pointer-only asset commit 6b268b0
was pushed and its remote tip verified. No retired assets were revived.

## Earlier implementation history (superseded where noted above)

2026-10-20 correction: the product-only deadline fallback shipped in eb96475 was
wrong. Run 20261020-115141-80834b37 never reached animation/editing; the controller
uploaded a full-length end card instead. Technical motion/encoding checks did not
prove story completion. That path is removed. Recovery must finish the same story
in one bounded fast-production pass, preserving script/voices/scene/checkpoints.
Approved films are packaged unchanged. Story-prefix comparisons run before
packaging; delivery rejects the old product_only type. Old substituted runs reopen
their skipped stages on resume, without deleting files or historical receipts.
No end-card-only output may be counted as a completed ad.
Verification recovery: 20261020-115141-80834b37 now has its original 12-second film
(9.5-second character story plus 2.5-second card), accepted technical QA and a
separate actual-media creative review. Vocal acting was not listened to by that
reviewer and remains unverified. The already-spent old run needed explicit
operator finishing allowances; future low/medium runs enter recovery earlier,
and identity editing avoids another model/rerender for a complete animatic.
The corrected local export replaces the old read-only convenience copy atomically;
the original accepted card-only artifact remains available in history. At this
verification checkpoint Drive is quota-throttled; durable upload retries continue.

2026-10-20 end-card policy update: the owner's early-web-2002 direction supersedes
the historical clean black Helvetica URL notes below. New cards use a blue,
underlined Times New Roman URL (bundled Times-compatible fallback), steady aliased
type and ordered Bayer dithering on the floating product image. Story picture/audio
remain untouched; no scanlines, RGB splitting, jitter, cursor or typewriter animation.

**The harness is implemented and usable.** CLI, GUI, state machine, worker
supervision with provider fallback, contracts, media checks, Frame CTA and
packaging are built and tested. The first Goosnav MVP video is delivered. Final CTA correction and acceptance
were completed by the supervising assistant when both worker quotas were exhausted.

Start a batch: `python3 -m harness make --count N [--concept "..."]` or
`./"Start Ad Studio.sh"`. Operating guide: [OPERATIONS.md](OPERATIONS.md).

## Session 4: quality gates before features

Owner feedback on the DRAW DISTANCE export (run `20261015-232206-803b773f`): scanlines and
jittery typed text do not work; mouths look like an afterthought; dialogue was unclear; scripts
must specify every shot and who is speaking; the GUI fails when its port is taken. Priority:
consistently good ads with minimal intervention before more features or bigger batches.

Measured causes, then fixes:

| Problem | Measured | Fix |
|---|---|---|
| Unclear dialogue | GUY (`am_onyx`) had 0.6 % of its energy at 2-5 kHz (clear speech ~5-10 %); final at -23 LUFS | `audio.py` polishes every take (`VOICE_CHAIN`); presence gate (-13 dB) on the dialogue stem; Whisper (local `openai/whisper-small.en`) must hear the words on the mix and the final; final normalised to -14 LUFS / -1.5 dBTP; director told which Kokoro voices are clear |
| Mouths | Library jaw at 17 deg barely shows past the snout; nothing keyed or checked it; GUY spoke from behind the book | Controller measures `mouths.json` from the stem; `blender/lipsync.py` keys it (28 deg); `harness/scene_check.py` opens the saved `.blend` and requires jaw motion on each line, a shut mouth in silence, and the speaker's face on camera, readable and unblocked (camera ray) |
| Who speaks / shot detail | Plans had no face or delivery fields | Writer brief: numbered shot list (camera, framing, action, who speaks, how, whose face); director plan: `faces` per beat, `delivery` per line, `offscreen` reason or the line is rejected |
| Text and look | Frame retro mode: scanlines, RGB split, jitter, typewriter | Frame never post-processes; clean type only; `look: ps1` now only changes production (models, native low-res, nearest upscale) |
| Slideshow animation | RETURN SLOT froze 2.4 s and 2.0 s mid-story; opening contrast 27/255; CTA overlay barely changed the picture | `check_picture`: freezes of 1.9 s or more, black gaps, washed-out stretches, and a real Frame card, on the animatic and the final. RETURN SLOT fails all four; DRAW DISTANCE passes |
| Expensive mistakes found late | Review only after full animation | `assets` blocks the film and renders one board per beat; director `board_review` gates before audio/animation |
| Redundant sessions | Rewrite + second critique even when the first critique passed | Skipped when the critique passes; rewinds carry a TARGETED REPAIR brief; workers get `previous_runs` to reuse assets |
| GUI start | Fixed port, no reuse | `/health`; an Ad Studio already serving the same home is reused; a busy port moves to the next free one |
| Late dependency failures | Discovered mid-run | `harness/preflight.py` before any agent (also in `doctor` as `run_blockers`) |

Characters (owner, 2026-10-16: "the entire point is to use the 3-D character assets"; low-res
late-90s game look is wanted). The run after these fixes had built generic "OWNER/BORROWER"
actors: nothing required the library and the brand bible's no-mascot rule pushed the director
away from it. Now `sources.characters` lists the cast (locally PS1 guy v10 plate/beady and the
guy, gal, expert); briefs say the ads star them; the director must set `model` per speaker; the
scene check verifies each speaker's skeleton against that file. Lip-sync drives v10's
`open/round/wide` mouth morphs (its jaw bone moves nothing) and the older rigs' jaw. PS1 spec
follows the library: 360x450 native, `blender/ps1_finish.py` (15-bit Bayer dither, 3x nearest).

Legs: the `characters/` guy, gal and expert bent their knees backward (IK pole angle -90, copied
from the arms; ps1guy and creatures use +90). Fixed in goosnav-3D-assets `82ec840` (six .blend
files and goosguy.py) with `tests/check_knees.py` in `run_checks.sh`, which fails on the old rig.

Graph now: research, write, critique, [revise, critique_final], select, then per ad direct,
assets (+boards), board_review, audio, animate, review, edit, frame, qa, creative_qa, package.

Tests: 88 passing, including real-rig Blender scene checks (good / silent / blocked) and real
FFmpeg loudness/presence/picture checks calibrated on the two earlier exports.

## Session 3: director, mix gates, Frame end card

The first delivered ad (RETURN SLOT) was rejected by the owner as very bad. Measured causes:

- Buried dialogue. Lines sat around -27 dBFS while the wind bed's median was -19.6
  and the chute peaked at -9.7. The audio worker reported "16 dB voice over FX" and
  nothing checked it.
- Miscasting. The config default voice `af_heart` (female) voiced the male borrower.
- Pacing. Three lines were crammed into 3.3 s over a static medium shot. The reveal
  was a few specks in a wide shot, and the opening wide held 1.8 s on a tiny figure.
- End text was a 56 px Frame overlay over a 3D shot, not Frame's own layout.

Changes:

- `direct` stage (role `director`, quality tier) after `select`. It writes beats, cast,
  timed lines, the end card and mix direction. `harness/direction.py` validates it.
  The director also runs `review` and `creative_qa` (the `checker` role is gone).
- Mix gates (`check_mix`) on the audio stage and again on the finished video in `qa`.
  `check_cast` requires each planned line, in order, with its cast voice. The real
  RETURN SLOT mix is a regression test and is rejected.
- `finish_frame` makes a native Frame stacked end card from the last
  `end_card_seconds` of the master. It uses Frame's fonts and sizes, a balanced
  two-line title, white ground and a black Helvetica URL without underline, and saves `end_card.png`.
  `output.frame: full` frames the whole ad.
- `restart` on review results rewinds only from the named stage.
- No default voice. Briefs for every stage carry the end-card budget, phone
  readability and the "no baked text" rule.

- `output.look: ps1` (owner request, 2026-10-16) is the crunchy late-90s console look.
  Frame crunches the story picture (pixel 5, 15-bit dither, scanlines) and types
  the end card in retro pixel type with a cursor. Briefs require PS1-native
  production: PS1 library models, 1/5-size render, nearest upscale. The local
  config uses it.

Tests: 68 passing (`python3 -m pytest -q tests`).

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
- Workers run with full access by owner decision: `claude --dangerously-skip-permissions`
  and `codex exec --dangerously-bypass-approvals-and-sandbox` (no sandbox or approval
  prompts to stall an unattended job). Live-smoked: Claude ran Blender unprompted.
- Usage limits (found live): Claude's subscription 429 "session limit" was
  misread as a crash, burning all attempts in seconds. Now any `api_error_status`
  429 or "session limit" is `quota`, the announced reset time sets the cooldown,
  quota attempts do not use up repair budget, and the CLI waits out cooldowns.
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
52 passing. They cover config validation, store/lock, contracts and path escape,
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
- writing competition selected RETURN SLOT. Real Kokoro dialogue, Blender animation,
  full-resolution edit and Frame CTA are delivered: 10 s, 1080×1350, 24 fps.
- Fixed a deterministic Frame integration bug: CTA previously covered the entire
  story. The adapter now shows it only in the final two seconds, preserving audio.
  A real Frame/FFmpeg regression test checks early and late frames.
- Agent review sent the finished video through an unnecessary production loop;
  workers exhausted both subscriptions. The supervising assistant restored the
  accepted original production chain, applied the controller fix, inspected the
  contact sheet, ran media QA, and packaged it. The run records manual completion,
  not a fully autonomous success.
- Local delivery: `business/studio/output/harness/20261015-130307-23007d15/`
  contains `ad-01.mp4` and the editable-source `ad-01.zip`.
- Remaining visual limitations are minor hand/book intersection and faint distant
  queue figures. Accepted for MVP rather than spending another render cycle.

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

## MVP scope / handoff

Use the GUI launcher or `python3 -m harness make --count 1 --seconds 10`.
No further architecture or audio-model installs are required for the MVP.
Worker subscriptions remain an external limit; existing cooldown/fallback handles
that, but unattended creative completion is not guaranteed. If future reviews
only concern CTA, fix the Frame stage instead of rerendering animation.

Drive delivery: the first two attempts (2026-10-15) hit Google HTTP 403
RATE_LIMIT_EXCEEDED on rclone's shared client. A retry on 2026-10-16 06:00 UTC
succeeded: `agent-exchange:deliverables/claude/20261016T060046Z-claude-RETURN-SLOT/RETURN-SLOT-10s.mp4`
(MD5 matches the local master). A copy is also in the local Agent Exchange folder.
