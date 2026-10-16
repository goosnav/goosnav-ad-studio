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
{"provider":"kokoro","text":"I need a minute.","voice":"am_onyx","speed":1.0,"seed":7,"device":"cpu"}
```

Use the voice the director cast. Kokoro IDs encode language and gender: `af_`/`bf_`
female, `am_`/`bm_` male (American/British). The controller rejects a cast whose voice
gender contradicts the character.

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
  "dialogue":[{"speaker":"A","voice":"am_onyx","text":"I need a minute.","start_sample":48000,"end_sample":120000}],
  "events":[{"name":"die lands","sample":240000}],
  "sound_rationale":"Dry dialogue and die impact; no music."
}
```

Dialogue is the lead of every mix. The controller measures the mixed WAV and rejects it
unless, for every line, the loud half of its 50 ms frames is at least -24 dBFS and 8 dB above
the median non-dialogue level, and no 400 ms stretch outside dialogue is more than 3 dB
louder than the loudest line. The finished video is measured again after Frame. Effects
that should feel big get there by contrast and timing, not by burying speech.

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
dialogue list, sound rationale, and an audio stream.

Goosnav Frame writes all end text. Never render titles, URLs, captions or end cards
into the picture. After the edit, the controller hands the last `end_card.seconds` of
the master to Frame, which lays it out in its stacked format: the director's title in
Frame's bold type above the picture, the web address in Frame's blue underlined link
below, on white. That window of the master should therefore be a clean product hero
shot (the real product model, large and square to camera). With `output.frame: full`
Frame frames the whole ad the same way. The ad's audio runs unchanged under the card.
`cta: "none"` is supported when an ad should have no CTA. With `output.look: ps1`,
Frame also crunches the whole picture and types the end text out in pixel type, and
your brief carries the PS1 rendering rules (native 1/5 resolution, nearest 5x upscale).

## The director

The `direct` stage writes the plan every later stage follows: contiguous beats with
shot sizes and timings, the cast (speaker, character, gender, voice, performance),
timed lines (at most 3 words per second), the end card (seconds, title, picture) and
mix direction. The controller validates it. The director also reviews the animatic and
signs off the final cut; a `revise` names `restart` (the earliest stage actually wrong)
so a bad cut does not re-render animation and a bad mix does not re-cast.

## Review evidence

Inspect the actual artifact at meaningful timestamps, including the beginning,
turn, product shot and end. Record what you saw and the tools used. Do not claim
to have watched or listened if you only inspected metadata. Be adversarial about
real flaws and economical about fixes; no endless cosmetic polishing.
