# Production worker tools

The controller gives you one job, accepted inputs, a workspace and a result
contract. Complete that job. You own the creative and implementation choices;
the controller owns ordering, retries, validation and packaging.

## Working rules

Read `TASK.md`. Write `handoff.md` during long work. All new files stay in your
assigned workspace. Shared repositories and source libraries are read-only.
Keep tool processes in the foreground. The controller terminates your process
group when your session ends. Do not spawn more agents or use paid APIs.

Declare every output/dependency in `result.json.files`, with a relative path and
kind. The controller copies these into an accepted artifact directory and checks
hashes before reuse. Downstream workers get those accepted paths. Use JSON
numbers for measurements, not estimates presented as measurements.

## Local audio

Run the audio helper with `config.audio.python`. No model packages are imported
by the controller. Use the repository path in `TASK.md` to locate the helper:

```sh
"/configured/audio/python" /path/to/repo/harness/audio.py voice-request.json take.wav
```

Kokoro voice request:

```json
{"provider":"kokoro","text":"I need a minute.","voice":"af_heart","speed":1.0,"seed":7,"device":"cpu"}
```

Chatterbox expressive voice request (requires its own installed runtime):

```json
{"provider":"chatterbox","text":"I need a minute.","exaggeration":0.6,"cfg":0.4,"device":"cpu"}
```

Stable Audio Open Small effects request (requires its own runtime and model access):

```json
{"provider":"stable-audio","prompt":"One wooden die bouncing on a wooden table, dry close recording","seconds":3,"seed":7,"device":"cpu"}
```

The helper emits a 48 kHz PCM16 WAV, the native-rate WAV and a JSON measurement/
provenance sidecar. Listen or use available audio tools; generation alone is not
quality evidence. Generate separate takes with performance direction and select
what works. Do not call every synthetic voice expressive merely because a model
generated it. Do not silently switch to Piper when a neural provider fails.

For procedural effects and mixing, inspect `studio/audio.py`. Its legacy mixer
expects normalized audio; resample imports and normalize sample formats first.
You may instead write a small mix script using available numpy/scipy or FFmpeg.
Record event onset times and keep individual stems. Supplied music must retain
its source/rights evidence. No music is often better than arbitrary music.

Required timeline shape:

```json
{
  "fps":24,"sample_rate":48000,"duration":10,
  "dialogue":[{"speaker":"A","text":"I need a minute.","start_sample":48000,"end_sample":120000}],
  "events":[{"name":"die lands","sample":240000}],
  "sound_rationale":"Dry dialogue and die impact; no music."
}
```

All timings must reflect actual generated audio. Preserve text/voice/seed/model
metadata. Write viseme or envelope alignment when applicable and state which it
is. No guessed phoneme timestamps labeled as measured alignment.

## Animation and editing

Blender's Python has its own libraries. Invoke configured Blender with a local
script, for example:

```sh
blender -b --python-exit-code 1 --python scene.py
```

Import reusable helpers by adding the read-only repository's `blender/` directory
to `sys.path`. Existing `studio` CLI film commands assume `films/` inside the
repository; do not write there. Adapt a scene runner to write into your workspace.
Read `PLAYBOOK.md` for rendering/contact lessons. Run-owned script decisions and
current input instructions take precedence over historical creative rules.

Use the configured 3D library's current rig and coordinate conventions. Do not
copy its specialized five-ad campaign unchanged. Make your own staging and
timing. Render sparse stills and an animatic first. Keep accepted audio timing
through final edits; changing a voice requires updating captions and movement.

Final master: requested size and fps, H.264, yuv420p, 48 kHz audio, within the
requested duration range. Even a deliberately silent film has an explicit empty
dialogue list, sound rationale, and an audio stream. Frame adds an overlay CTA
after edit; leave safe space and avoid duplicate copy. `cta: "none"` is supported
when an ad should have no CTA. CTA text should be short copy only; the configured
website supplies the destination.

## Review evidence

Inspect the actual artifact at meaningful timestamps, including the beginning,
turn, product shot and end. Record what you saw and the tools used. Do not claim
to have watched or listened if you only inspected metadata. Be adversarial about
real flaws and economical about fixes; no endless cosmetic polishing.
