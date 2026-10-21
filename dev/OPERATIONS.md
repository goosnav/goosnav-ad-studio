# Operating the harness

How to run, watch, recover and set up the agent-operated ad engine. The
design is in [HARNESS_SPEC.md](HARNESS_SPEC.md); what is proven is in
[STATE.md](STATE.md).

## Make ads

The everyday command is `./ad "description"` (one 10 s ad, detached; `-n` ads, `-s` seconds);
`CLI.txt` lists its variations. It wraps `python3 -m harness make` below. A run started
while another is in progress queues behind it. The GUI (`./ad gui`) listens on every
interface by default and prints its LAN address; `--local` limits it to this computer.
There is no login, so expose it only on trusted networks. If other computers cannot
connect, the host firewall is blocking the port (`sudo ufw allow from <lan>/24 to any
port 8788:8807 proto tcp`).

```sh
cd ~/Desktop/code/goosnav-ad-studio
python3 -m harness doctor                       # tools, CLI logins, Frame, sources
python3 -m harness make --count 3               # open brief: agents pick the idea
python3 -m harness make --concept "A paperweight takes its job too seriously" --count 2
python3 -m harness make --count 1 --plan        # create the run, start nothing
python3 -m harness make --count 2 --seconds 15  # target length per ad (default 10 s)
./"Start Ad Studio.sh"                          # the same, from a browser page (port 8788)
```

`make` reads `harness.local.json` when it exists (it is git-ignored); pass
`--config FILE` for another project. `--concept`, `--website`, `--count` and `--seconds`
override the file for one run. The run's configuration is frozen when it is
created; editing the config later does not change a run already started.

Finished ads are copied to `output.folder/<run-id>/ad-NN.mp4` (with a matching
`ad-NN.zip` review package) when `output.folder` is set. The full record of
every run lives in the harness home, default `~/.local/share/goosnav-ad-studio`:

```text
state.sqlite3                 run state, events, provider cooldowns
delivery-worker.log           delivery attempts and worker diagnostics
delivery-worker-health.json   worker PID, source fingerprint, phase and heartbeat
runs/<id>/sources/            text snapshots of brand docs, script banks, inspiration
runs/<id>/workspaces/<task>/  each worker's sandbox: TASK.md, handoff.md, result.json
runs/<id>/artifacts/<task>/   read-only accepted copies (hash-checked before reuse)
runs/<id>/logs/               one JSONL session log per worker attempt
gui-logs/                     output of controllers started from the GUI
```

## Watch and control

New runs give a short script guide directly to an animator that owns scene,
voices, timing and rendering, followed by an editor and deterministic finishing.
The writer has at most 60 seconds for one guide (up to 120 for larger batches);
the animator gets most of the production effort. Targets are soft: a late compact
run finishes existing work, with no shrinking repair allowance. The requested creative model tier
remains in use instead of switching to a cheaper storyboard recovery at 12 minutes.
Legacy runs retain their original graphs and finishing policy. Neither replaces the story with a
full-length floating-item end card. The closing card remains short; QA/packaging
check that the preceding story picture matches the edited source. Upload/retry
filters reject the prior product_only package type. Resuming such a run restores
its skipped story stages, preserving old files/receipts. Completed real ads are
untouched and upload individually through the normal durable Drive queue.
Only historical pre-compact runs at their hard ceiling need an explicit finishing allowance:
`./ad resume RUN_ID --extra-minutes 10`. This preserves checkpoints/spending.

```sh
python3 -m harness list
python3 -m harness status RUN_ID           # full JSON state: tasks, attempts, models, feedback
python3 -m harness events RUN_ID
python3 -m harness pause RUN_ID            # stops after the current task
python3 -m harness cancel RUN_ID           # stop one worker/run
python3 -m harness cancel --all            # cancel every unfinished run in this harness home
# Short forms: ./ad cancel all    or    ./ad cancel -a
python3 -m harness resume RUN_ID           # continue paused, cancelled, interrupted or waiting runs
python3 -m harness retry RUN_ID --task ad-01-animate
python3 -m harness models                  # what each role resolves to right now
```

`./ad status` also displays the current model, elapsed time and the age of the
worker's most recent log output. An unchanging status alone does not prove a
hang. To apply updated timeouts to an already-running old controller, cancel
its active worker, pull, then resume the run (completed tasks and checkpoints
are retained): `./ad cancel RUN_ID`, `git pull`, `./ad resume RUN_ID`.

Bulk cancellation atomically sets every unfinished run's control flag to
`cancel` and updates its status. Workers launched by the harness observe this
flag, and their managed subprocess groups are terminated by the supervisor.
Queued and provider-cooldown controllers check for cancellation every second
(previously every 30 seconds). Completed runs, outputs and the SQLite event
history are not deleted. Only runs under the chosen harness home are affected;
other Python/Blender processes are not killed. Controller-side work that does
not poll cancellation may need to finish its current operation first.

Independent CLI launches run concurrently, with one controller per run ID.
Use explicit IDs with `./ad status`, `watch`, `pause`, `resume` and `cancel`;
omitting one selects the latest run. Shared provider cooldowns still apply.
Drive transfers use a separate global lock and durable retry queue. A controller
started before this update retains its old workspace-wide lock until it exits.
The GUI uses the same commands, so a run started
in the browser can be paused from a terminal and vice versa.

Generation exit codes: 0 complete, 1 the run stopped in a non-complete state (`partial`,
`needs_review`, `waiting_provider`, `failed`, `cancelled`), 2 input or setup
error, 130 interrupted (state is saved; `resume`). A successful generation exit
does not confirm Drive delivery; check the separate delivery receipt/status below.

## Automatic Drive delivery

Set `output.folder` and `delivery.drive` in the run configuration and authorize
the rclone remote on the render host. Normal `./ad "description"` then delivers
each completed MP4 automatically; ZIP review packages remain local. No manual
upload, retry reset or approval is needed for a queued run. Filenames retain the
script title, UTC timestamp and stable run/ad suffix across attempts.

The presentation status is `awaiting_upload` when generation is complete but
configured Drive delivery remains pending. The internal generation status stays
`complete`. CLI status/list and GUI use this distinction; `./ad watch RUN_ID`
continues through pending uploads, stopping when delivery is verified or its
retries are paused/cancelled. `./ad status RUN_ID` shows the verified count,
error, effective maximum of the run and shared retry deadlines, and worker health.
Queued entries without a receipt and orphaned `uploading` records expose worker
health too. `./ad upload RUN_ID` remains an optional diagnostic command; it respects
saved cooldowns and is not a required recovery step.

`harness.streaming` persists exponential backoff of 2–3 seconds initially, capped
at 64–65 seconds including jitter, with no attempt limit. Existing long waits,
including legacy 18-minute deadlines, and their obsolete shared delivery cooldown
are normalized to at most 64 seconds ahead. Current-policy deadlines remain
authoritative across restarts. The fair queue favors least-recently-attempted
runs, skips busy/deferred/broken entries, and serializes all transfers. While a
controller owns its run during the next animator stage, its worker-monitor callback
checks earlier packaged ads for due delivery about every five seconds. These
intervals govern scheduling, not time to successful delivery: API quota, transfer
duration, verification and contention can delay an attempt or its success.

New receipts (`verification_version=2`) require a unique remote object ID,
matching byte size and a supported checksum. Verification rejects ambiguous or
duplicate objects and missing checksums. An uncertain-copy marker is saved before
transport; after timeout, lost acknowledgement or process death, remote content is
reconciled before another copy. Matching remote bytes are acknowledged without
recopying; proved absence or mismatch permits a copy. Historical uploaded receipts
retain their prior trust without an API re-probe merely because code was upgraded;
this does not retroactively give them the new proof format. Matching current
receipts avoid repeated remote verification. For receipts carrying a target,
local bytes, names and destination must still match that saved receipt.

### Worker supervision and recovery

The detached singleton worker survives controller/terminal exit. Without a usable
user service manager, process death still requires CLI/GUI recovery; persisted
receipts alone do not restart a dead process. Opening make/run/resume/upload/status
or the GUI recovers saved work. A living worker fingerprints `delivery_queue.py`,
`delivery.py`, `streaming.py` and `store.py`; it adopts changes by self-exec between
attempts, retaining the open singleton lease. Code adoption never overlaps an old
transfer. Delivery I/O uses bounded watchdogs, retains transfer leases until exit,
and is excluded from the generation budget.

Optional, explicit Linux setup installs a restarting user service for the chosen
harness home:

```sh
python3 -m harness.delivery_service
# For a non-default harness home, use the same path as generation:
python3 -m harness.delivery_service --home /absolute/path/to/harness-home
```

The unit name is `goosnav-ad-delivery-<home-hash>.service`; setup enables it with
`Restart=always`. Normal CLI recovery respects the installed service and its
restart delay instead of spawning a competing detached worker. Without a usable
user manager, detached delivery remains available. This render host's unit is
enabled and active as of 2026-10-21. Review confirmed a user-owned `0600` unit,
valid systemd syntax, a service PID owning the singleton lease, and a fresh heartbeat.
The installer does not elevate privileges or copy credential contents into the unit.
It also does not create an OAuth client or authorize Drive.

User-unit startup follows the user's service manager: without separately configured
lingering it normally starts at login after logout/reboot. Setup does not enable
lingering. A powered-off host cannot upload. Changed unit settings (repository
location, interpreter or environment) require restarting the service; rerunning
setup reloads/enables the unit but does not restart an already-running process.
Source self-exec applies delivery code changes, not these unit settings.

Shared rclone client-project quotas can materially delay delivery. Rclone's
[official own-client guidance](https://rclone.org/drive/#making-your-own-client-id)
states its shared client is retiring during 2026; configure your own OAuth client
to avoid that dependency. The service does not change this prerequisite. Revoked
credentials or a full Drive also require correcting their cause, not resetting
the queue. Keep tokens and credential-file contents out of diagnostics and Git.

### Observed delivery on this host

Run `20261021-054836-2aaeeb2d` reached verified Drive delivery on automatic attempt
6 at **2026-10-21 06:37:38 PDT** after prior `rateLimitExceeded` failures. Its saved
version-2 receipt contains remote identity, size and checksum proof. The final
attempt took about 19 seconds: roughly 15 seconds through acknowledgement,
including pre-copy reconciliation, then 4 seconds for verification. The transport
copy itself took about 5 seconds. No manual upload or retry reset was used.
This is one observed recovery, not a promise that future outages clear within a
few minutes. For validation coverage, see [STATE.md](STATE.md); this section
records the delivery evidence only.

## What happens in a run

```text
campaign-script (one guide per ad)
then per ad:
animate (scene, measured voices, render) -> edit (review + cut)
    -> frame (end card, loudness) -> qa -> package -> MP4 upload
```

Agent stages are separate `codex exec` / `claude -p` sessions, continuing the same
workspace after provider interruption. The writer uses its selected model with low
reasoning effort. Animation retains the requested effort. `harness.production_tools`
measures and aligns full voice takes, reuses cached audio, submits portable results
and assembles the editor's explicitly reviewed cut. No extra agent is needed for
those mechanical jobs. An editor may request one focused animation repair; it
judges the actual measured plan instead of restoring intentionally shortened lines.
Controller media checks remain mandatory. The final technical QA checks speech
once, not in repeated planning stages. No human production approvals are requested.

### Legacy stage graphs

The following separate-stage contracts describe older saved runs. Their accepted
work and original scheduling remain usable on resume; new runs use the graph above.

`direct` is the director: on the quality tier it writes the plan every later
stage follows (timed beats, cast with voice and gender, timed lines, the end card
title and picture, mix direction). The controller rejects a plan with gaps between
beats, beats under 0.75 s, lines over 3 words/s, or a Kokoro voice whose gender
contradicts the character. The director also runs `review` (animatic) and
`creative_qa` (final cut).

Gates that are controller code, not opinion: the audio stage must voice every
planned line in order with its cast voice, and the mix must keep dialogue as the
lead (each line's loud half >= -24 dBFS and >= 8 dB over the median bed; nothing
outside dialogue more than 3 dB over the loudest line). `qa` measures the finished
video's audio again.

`frame`: Goosnav Frame writes all end text. The last `output.end_card_seconds`
(default 2.5; the director may lengthen it) become a native Frame stacked card:
the director's title in Frame's bold type over the closing picture, the website as
blue (#0000ee), underlined Times New Roman (bundled Times-compatible Termes fallback),
white ground, Frame's own sizes scaled to the canvas. The card uses stable aliased
pixel type and ordered Bayer product-image dithering: an early-web-2002 screen.
Everything before it is the edit's picture; the audio runs straight through.
`output.frame: "full"` frames the whole ad with the same type but no added media
dithering, so the story picture isn't crunched by a closing-card effect.

`output.look` sets the visual era of the production. `clean` (the default) is a normal
render. `ps1` asks every stage for a PS1 cutscene: the library's PS1 models rendered
natively at 1/5 size with no anti-aliasing, nearest textures, fog and body motion on
twos, then a 5x nearest upscale. Frame leaves the story picture untouched. The
owner's 2026-10-20 end-card policy supersedes the older clean-type rule: the card
has pixel type and ordered picture dither, but no scanlines, RGB split, jitter,
blinking cursor or typewriter animation. Workers still bake no text into scenes.

A review that says `revise` rewinds to the stage it names in `restart` (scripts go
back to `revise`; an ad to `direct`, `assets`, `audio`, `animate` or, after the
final cut, `edit`; `audio` if unnamed), with its findings as the repair brief, up
to the configured repair allowance. Modern runs honor `board_repairs` and
`review_repairs`, then use a bounded `autonomous_replans` allowance to adapt the
affected ad to supported capabilities. They never require operator review for
ordinary findings. Unresolved important/blocking defects fail that ad after
automatic recovery is spent; other ads continue. Every successful package becomes
eligible for automatic upload independently of sibling ads, subject to API quota
and transfer availability. Matching verified videos are not copied again, and
delivery time is tracked outside the generation budget.

### Models and fallback

`./ad -e low|medium|high` selects the model preset (medium by default).
`-p openai|anthropic` sets the preferred provider; the other provider remains
available for failover. `./ad models -e high` previews current routes without
starting an ad. All aliases, combinations, thinking efforts and JSON precedence
are documented in `CLI.txt`.

| Preset | Primary | Writer, animator, director | QA/story/research |
|---|---|---|---|
| high | OpenAI | current Astra, high effort | current Sol, medium |
| medium | Anthropic | latest Opus, medium | latest Sonnet, medium |
| low | OpenAI | current Luna, low | current Luna, low |

Anthropic high uses Opus at max effort and Sonnet for QA. Anthropic low uses
Sonnet and Haiku. OpenAI medium uses Sol and Luna. Producer/editor roles use
Sol for OpenAI high/medium, Luna for low, and Sonnet for Anthropic.

If a worker runs out of usage, capacity or context mid-task (or times out), the
next route continues in the same workspace. Its brief carries a `HANDOFF` note:
the files written so far, the end of `handoff.md` and the interrupted worker's
last actions, plus the task's original repair notes. When the backup is also
limited, the run waits and the note is kept for the resumed attempt.

Animation has its own `workers.animator` routes, selected by the preset alongside
writer and director. Timeout/quota fallback applies immediately. Saved runs
created before this role retain their original producer routing.

New scripts default to ordinary characters and a clear spoken exchange. The
animator uses `blender/performance.py` and the asset-owned conversation motion bank:
`conversation_cues(timeline, rigs)` supplies talk/listen windows and gentle partner
gaze; `apply(..., cues=cues, library_root=...)` preserves measured mouths and authored
poses. Explicit gesture and in-place walk cues are optional. Static props remain intact; unsupported actions such
as opening an unrigged book are simplified before animation. No new stages or
changes to the retry/review state machine are involved. See the reproducible
[speaking example](WORKER_GUIDE.md#talking-characters-and-reusable-motion).

Codex models are normally discovered from the account's live catalog
(`codex app-server` metadata, no inference). If that catalog is unreachable
or does not describe an appropriate model, the Codex route now **remains
available** and runs without `-m`, allowing the installed Codex CLI to
choose its own default model. If a previously selected Codex model is later
rejected as unsupported, the scheduler retries that task once using the CLI
default, without consuming a creative repair. On resume/provider waits,
automatic selectors and moving aliases for unfinished roles are re-resolved,
including saved `unavailable` Codex routes. Explicit version pins are preserved,
and historical attempts retain the concrete models actually used. A failed or
unexpectedly formatted `codex login status` check alone no longer prevents a
Codex attempt: the actual CLI reports any real authentication error instead.
Claude aliases are recorded as the concrete model observed in a session and
refresh through the moving alias when the controller resumes unfinished work.
Override any role in the config:

```json
"workers": {"writer": [{"provider": "claude", "model": "opus"}, {"provider": "codex", "model": "auto:quality", "effort": "high"}]}
```

Routes are tried in order, each with `limits.repairs + 1` attempts. Critics only reach the balanced routes after the cheap ones fail the output
contract (in the first live run Haiku twice reviewed well but never wrote
`result.json`). A timeout, silent stall or oversized log **immediately switches
routes** instead of retrying that same model. Research now has economy routes
after balanced and writing has balanced routes after quality. A fully valid
`result.json` is salvaged even if its worker timed out; otherwise `handoff.md`
notes and files remain available to the next worker. There is no reliable
CLI-specific 'answer now' command; these safeguards are the equivalent without
risking an incomplete result entering production.

A quota/usage-limit error puts that provider on cooldown
(`limits.provider_cooldown_seconds`, default 1 h) and the same role moves to
the other CLI. The state machine only reports `waiting_provider` once its
usable routes really are exhausted; `./ad status` now prints the reason each
route was skipped, and `./ad watch` exits if the run cannot progress. Writers may downgrade to the balanced tier if quality routes stall or fail. Both CLIs report when their limit resets ("resets 5:40pm", "try again at
4:24 PM"); that time becomes the cooldown. Quota failures do not use up a task's
repair budget. If every route is cooling down, `make`/`resume`/`retry` sleep until
the earliest reset and continue (`--no-wait` stops at `waiting_provider` instead).
A logged-out CLI has no cooldown, so the run stops for a person. API-key
environment variables are removed from worker environments, so workers only
use the logged-in subscriptions (`codex login`, `claude auth login`).

## Configuration

`harness.example.json` is the blank public template. Copy it to
`harness.local.json`, or edit it on the GUI's Config page, which validates
before saving. Unknown keys are errors.

| Key | Meaning |
|---|---|
| `website` | Advertised domain. Used for the Frame CTA link. Empty = no link CTA. |
| `products` | `[{name, description, url?}]`. Writers sell these; facts must be sourced. |
| `concept`, `count` | Optional idea; number of finished ads (1-50). |
| `generation` | `effort`: low/medium/high (default medium); `provider`: auto/openai/anthropic (default auto). `./ad -e high -p openai` overrides these for a new run. See `CLI.txt` for all role/provider combinations and `./ad models` for a live preview. |
| `brand.name/direction/documents` | Brand voice and PDF/DOCX/TXT/MD brand docs or URLs. |
| `sources.scripts` | Example or ready-made scripts for writers to learn from or use. |
| `sources.inspiration` | Theory, style bibles, reference notes or URLs. |
| `sources.assets` | Read-only folders of 3D assets, photos, footage. |
| `sources.characters` | Rigged character `.blend` files that star in every ad. When set, the director must cast each speaker from this list (`model`) and the scene check verifies the speaker's skeleton matches that file. |
| `output` | `target_seconds` (default 10; writers time scripts to it), `min/max_seconds` (0 = 80-130 % of target), `width/height/fps` (1080x1350 at 24), `cta`, `folder`. |
| `audio` | `python` (the local model venv), `voice_provider`, `voice`, `music`, `allow_piper_fallback`. |
| `tools` | `blender/ffmpeg/ffprobe` commands, `frame_root`, `frame_python`. |
| `workers`, `limits` | Role routing; `quick_timeout_seconds` (600), `review_timeout_seconds` (900), `idle_timeout_seconds` (300), production timeout (14400), repair rounds, cooldown and log cap. |

## Local audio environment

Agents call `harness/audio.py` with `audio.python`. The controller never
imports model libraries. The current Goosnav machine has Kokoro installed
in `~/.cache/goosnav-ad-studio/audio` (uv venv, Python 3.12, CPU torch).
To rebuild it (versions are those installed on 2026-10-15):

```sh
uv venv --python 3.12 ~/.cache/goosnav-ad-studio/audio
uv pip install --python ~/.cache/goosnav-ad-studio/audio/bin/python \
  --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple \
  torch kokoro==0.9.4 soundfile espeakng-loader huggingface_hub
uv pip install --python ~/.cache/goosnav-ad-studio/audio/bin/python \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
echo '{"provider":"kokoro","text":"Testing.","voice":"af_heart"}' > /tmp/req.json
~/.cache/goosnav-ad-studio/audio/bin/python harness/audio.py /tmp/req.json /tmp/take.wav
```

Kokoro weights (`hexgrad/Kokoro-82M`, Apache-2.0) download on first use.
Chatterbox and Stable Audio Open are supported by `audio.py` but not
installed here; Stable Audio Open's weights need a Hugging Face login and
licence acceptance. Until they are, agents make effects procedurally
(`studio/audio.py`). Piper is only used when `allow_piper_fallback` is true,
and only with the voices `studio/vo.py` lists as commercially cleared.

## Troubleshooting

- Asset moves: missing character files are relocated only when an exact filename
  has one active match inside the configured asset libraries. Archived models
  (including symlinks into archives) are excluded, even if still configured.
  Missing inspiration documents are optional and recorded in `source_warnings`
  and the `sources_reconciled` event. Brand/script documents and library roots
  remain required. No remaining usable character is an actionable configuration
  error; the controller never substitutes an archived or arbitrary model.
  On resume, an accepted direction with a retired cast restarts at `direct`.
- Invalid worker handoff: after normal provider fallback, `limits.contract_repairs`
  permits one targeted format correction by default. It does not bypass media
  checks or review findings. Its allowance is durable across resume; quota waits
  do not spend it. Valid empty diagnostic `.log` files declared as `notes` are
  accepted; production media and sources must still be nonempty.
- `waiting_provider`: both CLIs are out of quota, logged out, or in cooldown.
  `python3 -m harness doctor`, then `resume` when a provider is back.
- `failed` task: `status RUN_ID` shows the attempt kind (`invalid`, `crash`,
  `timeout`, ...) and feedback. Read the worker's `handoff.md` and log, then
  `retry --task`. A retry gives the worker the previous failure as its brief.
- `Another controller owns this workspace`: a run is already active. Use
  `status`/`pause`, or wait.
- `Source snapshot changed`/`Accepted artifact changed`: someone edited a
  run's frozen files. Make a new run rather than editing artifacts.
- Frame CTA failure: check `tools.frame_root`/`frame_python` with `doctor`;
  the Frame step's log is `runs/<id>/workspaces/ad-NN-frame/frame.log`.

Frame CTA appears during the final two seconds of the actual master. The original
audio is retained. Leave this hold clear when scripting and editing.

Run the controller test suite with `python3 -m pytest -q`. Collection is restricted
to `tests/`; the asset submodule also contains Blender build scripts named
`*_test.py`, which need Blender's `bpy` interpreter and are not controller tests.
