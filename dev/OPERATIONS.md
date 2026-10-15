# Operating the harness

How to run, watch, recover and set up the agent-operated ad engine. The
design is in [HARNESS_SPEC.md](HARNESS_SPEC.md); what is proven is in
[STATE.md](STATE.md).

## Make ads

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

```sh
python3 -m harness list
python3 -m harness status RUN_ID           # full JSON state: tasks, attempts, models, feedback
python3 -m harness events RUN_ID
python3 -m harness pause RUN_ID            # stops after the current task
python3 -m harness cancel RUN_ID           # kills the current worker's process group
python3 -m harness resume RUN_ID           # continue paused, cancelled, interrupted or waiting runs
python3 -m harness retry RUN_ID --task ad-01-animate
python3 -m harness models                  # what each role resolves to right now
```

Only one controller runs per harness home (file lock). `status`, `pause` and
`cancel` work while it runs. The GUI uses the same commands, so a run started
in the browser can be paused from a terminal and vice versa.

Exit codes: 0 complete, 1 the run stopped in a non-complete state (`partial`,
`needs_review`, `waiting_provider`, `failed`, `cancelled`), 2 input or setup
error, 130 interrupted (state is saved; `resume`).

## What happens in a run

```text
research -> write (3 scripts per ad) -> critique -> revise -> critique_final -> select
then per selected ad:
assets -> audio -> animate -> review -> edit -> frame (CTA) -> qa -> creative_qa -> package
```

Agent stages are separate `codex exec` / `claude -p` sessions with their own
workspace, full local tools and a long deadline (1 h campaign, 4 h production).
`frame`, `qa` and `package` are controller code. A review that says `revise`
rewinds to the stage it criticises (`revise` for scripts, `audio` for an ad)
with its findings as the repair brief, up to `limits.repairs` rounds. When the
rounds run out, non-blocking findings travel on as notes (`accepted_with_notes`)
and only `blocking` findings stop for a person (`needs_review`).

### Models and fallback

| Role | Tier | Codex (first) | Claude (backup) |
|---|---|---|---|
| researcher, producer | balanced | latest workhorse | `sonnet` |
| writer, selector | quality | frontier model, high effort | `opus` |
| critic, checker | economy | affordable model, low effort | `haiku` |

Codex models are discovered from the account's live catalog (`codex
app-server` metadata, no inference). Claude aliases are pinned to the concrete
model observed in the first session. Override any role in the config:

```json
"workers": {"writer": [{"provider": "claude", "model": "opus"}, {"provider": "codex", "model": "gpt-6-astra", "effort": "high"}]}
```

A quota/usage-limit error puts that provider on cooldown
(`limits.provider_cooldown_seconds`, default 1 h) and the same role moves to
the other CLI. Writers never downgrade to a cheaper tier. If every route is
unavailable the run stops as `waiting_provider`; `resume` it later. API-key
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
| `brand.name/direction/documents` | Brand voice and PDF/DOCX/TXT/MD brand docs or URLs. |
| `sources.scripts` | Example or ready-made scripts for writers to learn from or use. |
| `sources.inspiration` | Theory, style bibles, reference notes or URLs. |
| `sources.assets` | Read-only folders of 3D assets, photos, footage. |
| `output` | `target_seconds` (default 10; writers time scripts to it), `min/max_seconds` (0 = 80-130 % of target), `width/height/fps` (1080x1350 at 24), `cta`, `folder`. |
| `audio` | `python` (the local model venv), `voice_provider`, `voice`, `music`, `allow_piper_fallback`. |
| `tools` | `blender/ffmpeg/ffprobe` commands, `frame_root`, `frame_python`. |
| `workers`, `limits` | Role routing (above); timeouts, repair rounds, cooldown, log cap. |

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
