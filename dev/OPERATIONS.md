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
runs/<id>/sources/            text snapshots of brand docs, script banks, inspiration
runs/<id>/workspaces/<task>/  each worker's sandbox: TASK.md, handoff.md, result.json
runs/<id>/artifacts/<task>/   read-only accepted copies (hash-checked before reuse)
runs/<id>/logs/               one JSONL session log per worker attempt
gui-logs/                     output of controllers started from the GUI
```

## Watch and control

Creative budgets now protect a deterministic finishing reserve. For a medium
9-second ad without animation, model repair loops stop at 16 minutes, before the
25-minute hard ceiling. Runs with real animation retain more editing/QA time.
The controller packages an already approved film, or makes a clearly labelled
product-only fallback from the selected product's active floating-item footage:
product name and shop link, intentional silence, no unrelated story dialogue.
Fallbacks undergo media/motion/picture checks and upload individually through the
normal durable Drive queue. Completed ads are untouched; missing product footage
is reported, never replaced with an archived model. See CLI.txt for clip mappings.
Old runs already at their hard ceiling need an explicit finishing allowance:
`./ad resume RUN_ID --extra-minutes 3`. This preserves checkpoints/spending.

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

Only one controller runs per harness home (file lock). `status`, `pause` and
`cancel` work while it runs. The GUI uses the same commands, so a run started
in the browser can be paused from a terminal and vice versa.

Exit codes: 0 complete, 1 the run stopped in a non-complete state (`partial`,
`needs_review`, `waiting_provider`, `failed`, `cancelled`), 2 input or setup
error, 130 interrupted (state is saved; `resume`).

## What happens in a run

```text
research -> write (3 scripts per ad) -> critique -> [revise -> critique_final] -> select
then per selected ad:
direct -> assets (+storyboard) -> board_review -> audio -> animate -> review -> edit
       -> frame (end card, loudness) -> qa -> creative_qa -> package
```

Agent stages are separate `codex exec` / `claude -p` sessions with their own
workspace and full local tools. Lightweight campaign stages get 10 minutes per
attempt (with a 5-minute no-activity timeout); direction/reviews get 15 minutes;
asset building, audio, animation and final editing keep a 4-hour budget and
have no automatic idle cutoff (rendering can legitimately be quiet).
`frame`, `qa` and `package` are controller code. `revise` and `critique_final` are
skipped when the first critique passes. `board_review` is the director looking at one
still per beat, rendered from the blocked scene, before voices or animation exist.
Every stage's result is checked by controller code before it is accepted; the full
list of gates is in [WORKER_GUIDE.md](WORKER_GUIDE.md#controller-gates-what-gets-a-result-rejected).

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
automatic recovery is spent; other ads continue. Every successful package is
uploaded immediately, independently of sibling ads. Verified videos are not
copied again, and delivery time is tracked outside the generation budget.

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

New scripts default to spoken scenes with one or two planted characters. The
animator uses `blender/performance.py` to reuse library idle motion, add small
timed nods/blinks and apply the measured mouth curves. Existing named walk and
gesture clips are optional. Static props remain intact; unsupported actions such
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
