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

## Animation scope

The default ad is a short spoken scene: one or two planted characters, one set,
a two-shot and perhaps a close-up, then an intact product hero. Put the premise
in the dialogue and delivery. Most body motion should come from an existing idle
or gesture clip. Walking is optional and uses an existing cycle. Do not plan
silent physical spectacle unless the owner explicitly requests it.

Inspect the actual asset before promising an interaction. A static book stays
closed; no new hinge, mesh splitting, page rig or custom hand IK to rescue a
script. Keep hands free and put the product on a stand or in a separate shot.
If an action is unsupported, document the limit and simplify the action to a
spoken exchange. Reviewers should accept a well-delivered standing conversation;
more arm motion or camera travel is not a quality requirement.

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

## Talking characters and reusable motion

The library already contains motion assets. v10/astronaut rigs have NLA clips
such as `idle`, `walk`, `speech` and `gesture`; older rigs have saved actions such
as `pose_idle` and `pose_talk`. Names and capabilities come from the actual file,
not assumptions based on a README. Use the shared helper instead of rebuilding
the character, writing a new motion generator or hand-keying a conversation.

The accepted audio supplies the measured timeline and `mouths.json` (per-speaker
openness per frame). This is the normal complete speaking setup, run after
appending the actors and arranging the cameras/product:

```python
import sys; sys.path.insert(0, '<repo>/blender')
import performance
rigs = {'GUY': 'guy', 'FRIEND': 'gal'}  # actual speaker IDs and armature names
models = {'GUY': '<cast source>/goosnav_guy_ps1.blend',
          'FRIEND': '<cast source>/goosnav_gal_ps1.blend'}
report = performance.apply('<audio artifacts>/timeline.json',
                           '<audio artifacts>/mouths.json', rigs, models=models)
bpy.ops.wm.save_as_mainfile(filepath='scene.blend')
```

`apply` copies each source idle/pose_idle, loops it over the measured duration,
adds restrained speech-timed head nods and staggered blinks, then applies the
measured mouth curves. Actors stay in place. The helper owns animation tracks on
these characters, removes imported mouth demos and stale hand IK, and never edits
the source files or the scene's cameras/product. Include silent listeners in
`rigs`. v10 uses mouth morphs; older rigs use the jaw. Keep the saved report.
Run this after positioning the actors, before any optional library gesture. It
replaces old character animation tracks, so it is not a layer over custom hand
contact. A planted pose is intentional. If a freeze check fails, inspect the idle
and mouth setup instead of adding arbitrary waving or camera travel.

For an optional motion that serves the line, reuse an existing body clip:

```python
print(performance.available_clips('guy', models['GUY']))
# Frame numbers, end exclusive. Only do this if the shot actually needs it.
performance.play_clip('guy', 'gesture', 25, 73, model=models['GUY'])
# An in-place walk cycle is also supported; travel/contact is not invented.
performance.play_clip('guy', 'walk', 73, 121, model=models['GUY'], loop=True)
```

Missing motions raise a clear error listing available names. Choose an existing
motion or simplify the shot. `play_clip` strips the source demo jaw/object tracks,
so the measured mouths and actor placement remain authoritative. It copies the
body action; it does not rewrite the source clip. Walking/gestures are optional,
not something every ad needs. `lipsync.apply` remains available for a specifically
authorized custom body animation, called after that body's keys are complete.

The controller runs `harness/scene_check.py` on the saved `scene` with your `rigs` map. For
every line it needs the speaker's jaw open on at least 30 % of the line's frames, shut while
they are silent, and the head inside the active camera's frame, at least 3.5 % of the frame
wide/tall and not blocked by a prop (camera ray hits the character) for 30 % of the line.

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

Use the configured 3D library's current rig and coordinate conventions. Reuse
motion clips and speaking helpers while writing original dialogue and staging.
Render sparse stills and an animatic first. The dedicated editor may trim
the approved source with an explicit edit-plan EDL. Cut picture and audio together,
using harness.editing to rebase speech timestamps for final QA; never pass a stale
audio timeline after shortening footage. Changing a voice requires updating
captions and mouth movement. Established Goosnav characters and static staging
are valid; dialogue coherence and pacing, not constant movement, are the gates.

Final master: requested size and fps, H.264, yuv420p, 48 kHz audio, within the
requested duration range. Even a deliberately silent film has an explicit empty
dialogue list, sound rationale, and an audio stream.

Goosnav Frame writes all end text. Never render titles, URLs, captions or end cards
into the picture. After the edit, the controller hands the last `end_card.seconds` of
the master to Frame, which lays it out in its stacked format: the director's title in
Frame's bold type above the picture, the web address in Frame's blue underlined link
below, on white. That window of the master should therefore be a clean product hero
shot. Prefer an existing floating-item clip: the controller maps `end_card.product`
(the exact configured product name), or the selected script's product, through
`output.end_card_clips` and resolves its asset ID in the configured library. It
trims a video-only excerpt and keeps the ad audio. Do not recreate an available clip.
For an unmapped product, animate the real model with slow item-style bob/rotation,
preserving its artwork and silhouette. With `output.frame: full`
Frame frames the whole ad the same way. The ad's audio runs unchanged under the card.
`cta: "none"` is supported when an ad should have no CTA. With `output.look: ps1`,
render at native 1/3 resolution and run `blender/ps1_finish.py` once for the library
dither and nearest 3x upscale. Frame uses clean typography and leaves the finished
picture alone. No scanlines, jitter or typewriter effects.

## The director

The `direct` stage writes the plan every later stage follows: contiguous beats with
shot sizes and timings, the cast (speaker, character, gender, voice, performance),
timed lines (at most 3 words per second), the end card (seconds, title, picture) and
mix direction. The controller validates it. The director also reviews the animatic and
signs off the final cut in the final creative QA; a `revise` names `restart` (the earliest stage actually wrong)
so a bad cut does not re-render animation and a bad mix does not re-cast.

## Review evidence

Inspect the actual artifact at meaningful timestamps, including the beginning,
turn, product shot and end. Record what you saw and the tools used. Do not claim
to have watched or listened if you only inspected metadata. Be adversarial about
real flaws and economical about fixes; no endless cosmetic polishing.

## Controller gates (what gets a result rejected)

Every gate is measured by the controller on your actual files. A rejection comes back as
your repair brief, with the numbers.

| Stage | Gate |
|---|---|
| direct | beats contiguous, each at least 0.75 s; at most 3 words/s; cast voice matches gender; every line has `delivery`; the speaker's face is in a beat's `faces` during the line (or `offscreen` gives the reason) |
| assets | one board image per beat plus `end_card` |
| audio | lines at least -24 dBFS and 8 dB over the bed; no effect 3 dB over speech; each planned line voiced in order by its cast voice; `dialogue_stem` present; every line's 2-5 kHz presence at least -13 dB; a local Whisper hears 80 % of the planned words and half of every line |
| animate | the animatic has no freeze of 1.9 s or more, no black gap, no washed-out stretch (luma range under 30 for 1 s); in the saved `scene`, each speaker's jaw is open on 30 % of their line and shut in silence, and their face is on camera, at least 3.5 % of the frame, and unblocked for 30 % of the line |

## Measured scratch voices: director → audio handoff

Before finalizing shots, generate the spoken lines with the batch voice helper in
the configured `audio.python` environment. Run from the repository directory (or
put that directory on `PYTHONPATH`); keep requests and outputs in your assigned
workspace. The command takes a JSON request path and a new output directory:

```sh
python -m harness.voice voice-request.json scratch
```

Here `python` means the configured audio interpreter, not necessarily the system
Python. `-` can replace the request path to read JSON from stdin. Success writes
`scratch/manifest.json`, copies its raw and polished WAV dependencies below
`scratch/takes/`, and prints the manifest as JSON. Failure exits nonzero and never
substitutes another provider. Python API:

```python
from harness.voice import run_batch, verify_take
manifest = run_batch(request, output_dir)  # returns the same dict written to manifest.json
verify_take(manifest['lines'][0]['takes'][0], output_dir)  # raises on corruption
```

The batch runs lines sequentially in one process. It reuses Kokoro's loaded model
and language pipeline, including across compatible voices. `harness.audio` also
exports `AudioSession`, `generate(request, output, session=None)`, and
`measure_wav(path)` for existing single-take callers. Heavy dependencies are loaded
only when synthesis/model resolution is needed; explicit take reuse works without
Kokoro, Chatterbox, torch, numpy, soundfile, or FFmpeg installed.

Example request (all seconds and speeds are numbers):

```json
{
  "provider": "kokoro",
  "effort": "medium",
  "fast": false,
  "cache_dir": "workspace/voice-cache",
  "local_files_only": true,
  "voice_profiles": {
    "GUY": {"voice": "am_michael", "speed": 1.0},
    "FRIEND": {"voice": "af_heart", "speed": 1.0}
  },
  "lines": [
    {
      "id": "setup",
      "speaker": "GUY",
      "text": "One minute. That is all.",
      "delivery": "Earnest, then quietly defensive. Listen for the turn.",
      "phrasing": ["One minute.", "That is all."],
      "pauses": {"before": 0, "between": 0.2, "after": 0.15},
      "auditions": [{}, {"speed": 0.93}]
    },
    {
      "id": "reply",
      "speaker": "FRIEND",
      "text": "Take your time.",
      "delivery": "A sincere reply, no sales-announcer voice."
    }
  ]
}
```

`lines` is nonempty. Every line needs `speaker`, `text`, and a `voice` either on the
line or supplied by its profile/global default. Give lines stable `id` values;
omitted IDs become `line-1`, `line-2`, etc. Persist and reuse the same caller-owned
`voice_profiles` mapping across ads, keyed by stable character/speaker IDs. If a
script uses different speaker labels, the caller maps the character's existing
profile to those labels. There is no built-in cast or machine-specific profile
path. Profile voice/model/language/reference conflicts and voice changes for the
same speaker within a batch are rejected. Per-line speed/delivery changes are
allowed; they do not recast the character.

Top-level generation defaults, then the profile, then the line supply `voice`,
`speed`, `seed`, `threads`, `device`, `model`, `revision`, `language`, `reference`,
`exaggeration`, `cfg`, `phrasing`, `pauses`, `polish`, and `local_files_only`, where
supported by the provider. Defaults are CPU, four threads, seed 0, speed 1.0,
polishing on, and local files only. Relative request paths, cache paths and
reference paths resolve from the command's working directory. The default cache
is `OUTPUTDIR/.voice-cache`; supply a shared caller-owned `cache_dir` to reuse
across runs. No dependency installation is performed.

Kokoro supports speed, punctuation and explicit phrase segmentation. `phrasing`
must be a list of nonempty pieces whose words and punctuation join back to `text`
(whitespace may differ). `pauses` accepts `before`, `between`, and `after`, each
0–10 seconds; `between` requires at least two explicit phrases. These insert real
silence samples. Speed must be 0.25–4; prefer shortening the line to rushing it.
`delivery` is a director/listening note, **not an emotion prompt sent to Kokoro**.
Changing only that note does not invalidate its audio cache. Listen to candidates
to assess the acting; ASR checks intelligibility, not sincerity, timing of a joke,
or emotional quality. This helper performs no ASR and claims no acting score.

Chatterbox is optional, with its own installed runtime and local model weights.
This adapter uses `ChatterboxTTS.from_local` with a resolved snapshot, including
CPU support, and refuses versions lacking that loader. It accepts `exaggeration`
(0–2), `cfg` (0–1), phrasing and pauses; speed must stay 1.0. `voice: "default"`
uses its built-in voice. Other stable voice labels require a caller-supplied
`reference` audio file; reference contents are hashed into the take recipe.
References/conditionals are reset between lines to prevent voice leakage.
Kokoro rejects Chatterbox-only controls, and this English Chatterbox adapter
rejects a language override. Neither provider interprets arbitrary delivery prose.

### Audition and defect budgets

Caps are per line per batch invocation: low 1, medium 2, high 3; `fast: true`
always caps auditions at 1. Omitting `auditions` generates **one** candidate, not
the maximum. A supplied list replaces that default; use `{}` for the base take.
Only the first capped entries are attempted. Entries may override speed, seed,
phrasing, pauses, exaggeration, cfg, and delivery; they cannot recast the voice.
Identical recipes reuse cached audio rather than synthesize duplicate auditions.

A line may additionally provide one targeted technical defect retry:

```json
"defect_retry": {
  "reason": "The first attempt is silent; try a slower short phrase.",
  "settings": {"speed": 0.95}
}
```

It runs only after a measured empty, silent, clipped, or invalid-rate take (or a
provider-reported empty/non-finite segment), once per line beyond the audition
cap. Controls must actually change. Without targeted settings, no blind retry
runs. Missing packages/weights, unsupported controls, and infrastructure errors
fail immediately. If every bounded candidate fails, no success manifest is
published. For an audible pronunciation/acting defect, record the listening
finding and request a corrected line explicitly; do not repeatedly regenerate
the entire cast or call ASR approval an acting review. The controller owns any
budget across separate invocations.

### Accept and reuse the exact selected take

An initial manifest selects the first technically usable candidate only for
planning, with `acceptance: "provisional_requires_listening"`. It does not claim
that candidate is the strongest performance. Listen where tools permit, choose
the intended take, and create the accepted manifest with explicit selections:

```json
{
  "provider": "kokoro",
  "voice_profiles": {"GUY": {"voice": "am_michael"}},
  "lines": [{
    "id": "setup", "speaker": "GUY", "text": "One minute. That is all.",
    "selected_take": {
      "manifest": "scratch/manifest.json",
      "line_id": "setup",
      "take_id": "COPY_THE_CHOSEN_TAKE_ID_FROM_THE_MANIFEST"
    }
  }]
}
```

Run this into a new directory, for example `accepted-voices`. `line_id` defaults
to the requested ID and `take_id` to that source line's selection. This copies
the exact raw and polished WAV bytes, verifies both SHA-256 hashes and remeasures
both files. It sets `acceptance: "caller_selected"`, meaning the caller selected
it; document separately whether listening was available. Explicit reuse does not
resolve/download current model weights or regenerate missing/corrupt audio. It
fails if files, hashes, measurements, speaker, text, voice, provider, or explicit
line-level performance controls disagree. Select a nondefault audition by its
ID; do not repeat stale base-speed overrides when selecting a different speed.
Selected lines cannot also request auditions/retries.
For selected Chatterbox takes the original reference is unnecessary: omit
`reference` from the reuse request/profile. If supplied, its content hash must
still match the accepted take, preventing a changed reference under the same
voice label from silently passing as the established voice.

Declare the accepted `manifest.json` (kind `notes` or `voice_manifest`) **and every
raw/polished WAV referenced by it** (kind `audio`) in `result.json.files`. Prefix
those paths by the output directory relative to your task workspace. All paths
inside the manifest are relative to the manifest directory, so the controller
can copy the complete tree into accepted artifacts without machine paths. The
audio worker must consume that accepted manifest, using `selected_take` for each
unchanged line; scratch acceptance is not a reason to synthesize again. Reuse
unchanged lines even when another line needs repair. Only new/corrected lines
need synthesis. Existing output manifests are never overwritten.

Manifest schema 1 has `sample_rate` (48000), total `frames`/`duration`, caps,
explicit quality limitations, and ordered `lines`. Each line records:

- `id`, `speaker`, `voice`, `text`, `delivery`, `acceptance`, `selected_take_id`.
- Measured `duration`, `start_sample`/`end_sample` in a sequential assembly, and
  `active_start_sample`/`active_end_sample` from an amplitude envelope (~−50 dBFS).
- `takes`: each has `id`, actual `settings`, `recipe` with immutable model/file
  identity and processing provenance, `reused`, and `raw`/`polished` file records.
  Records contain relative `path`, `sha256`, frames, sample rate, channels,
  duration, peak, RMS, clipping count, and local active bounds.
- `attempts`: audition/retry kind, actual seed/speed, reuse, measured wall time,
  and defect/retry reason where applicable.

The full file durations include inserted pauses and measured trailing silence.
Use those durations before fixing shot lengths, and reserve natural reply gaps
and reaction time. The helper does not mix the film or generate lip sync. Its
active bounds are amplitude measurements, not recognized words or phonemes.
When the audio worker adds intentional timeline gaps, offset the measured take
bounds accordingly, then generate mouths/visemes from the final accepted mix.

The cache keys actual generation controls, resolved model commit, model/config/
voice/reference file hashes, runtime versions, adapter code and FFmpeg treatment.
`main` is resolved to an immutable snapshot once per process; subsequent batches
resolve it again. Offline mode uses the currently cached ref and does not claim
it is the latest upstream revision. Set `local_files_only: false` explicitly to
allow model acquisition. Ordinary cache corruption is quarantined and the take
regenerated; explicitly selected accepted artifacts always fail closed.

Local benchmark on 2026-10-19: installed Kokoro 0.9.4, CPU, three tiny English
lines across two voices used one model/pipeline. Cold batch 17.1 s; a fresh-session
verified cache run 1.7 s. Measured durations were 1.675, 2.825 (two phrases with
0.2 s pause, speed 0.9), and 1.625 s. This is a small timing observation, not an
acting assessment or throughput guarantee. Chatterbox was not installed here;
no Chatterbox performance/CPU latency claim has been validated and no heavy
dependencies were installed for this work.

### Compact director receipt and deterministic accepted-take mixing

Directors should use compact stdout, not paste the full voice manifest into logs:

```bash
python -m harness.voice voice-request.json scratch --summary
```

`--summary` changes stdout only; `scratch/manifest.json` retains the full recipe,
model identity, hashes, measurements, and audition evidence. Default stdout is
unchanged for existing callers. The compact object contains the absolute
`manifest` path, total `duration`, `sample_rate`, `frames`, and `lines` with `id`,
`speaker`, `text`, `voice`, `selected_take_id`, `duration`, `frames`, local-to-take
`active_start_sample`/`active_end_sample`, and absolute selected `raw`/`polished`
WAV paths. Those absolute stdout paths are convenience locators, not portable
manifest contents. Declare `result.scratch_takes` and the manifest's WAV files as
described above; the manifest on disk remains the authoritative handoff.

The audio worker can assemble accepted scratch takes without inventing a mixer:

```bash
python -m harness.mix /accepted/direct/accepted.json audio --no-bed --fps 24
python -m harness.mix /accepted/direct/accepted.json audio-with-bed --bed licensed-bed.wav --bed-gain-db -30 --fps 24
python -m harness.mix --request audio/request.json replay-audio
```

Inside a worker workspace that already contains `TASK.md`, use this integration
form (paths are resolved from the current working directory):

```bash
python -m harness.mix /accepted/direct/accepted.json generated-audio --no-bed --fps 24 --stage-result result.json
```

`generated-audio/` must be absent/empty, but the workspace does not need to be.
`--stage-result` writes a **new** workspace-root result and prints that same object.
The destination's parent must equal the output directory's parent. Symlinks and
existing destinations are refused before assembly; even a previous helper result
is never overwritten. The staged result prefixes `files[].path` and only the
known declared artifact references (`mix`, `dialogue_stem`, `timeline`, `source`,
`audit`) with `generated-audio/`. Summaries, arbitrary strings, nested notes,
and on-disk request/timeline/voice manifests are not rewritten. All declared
output hashes are rechecked before staging. `TASK.md` and other workspace files
remain untouched. This flag also works with `--request` replay.

Use an absent or empty output directory. Pass the production fps explicitly
(otherwise `direction.fps`, then 24). Choose **either** `--no-bed` **or** a real
caller-supplied PCM16 WAV; silence is not presented as a fabricated music bed.
Gain defaults to −30 dB, permitted range −120 through −12 dB. A short bed is padded
with silence, never looped; a long bed is trimmed to the film. Only bed conversion
requires FFmpeg. No model or extra Python dependency is loaded for mixing.

Python API: `harness.mix.assemble(direct_result_path, output_dir, *, fps=None,
bed=None, bed_gain_db=-30, no_bed=False)` returns the complete result object.
`harness.mix.replay(request_path, output_dir)` verifies and replays saved inputs.
`harness.mix.stage_result(output_dir, destination)` stages an already completed
helper result using the same sibling-path/no-overwrite rules; `assemble` is unchanged.
`harness.voice.summarize(manifest, output_dir)` returns the compact voice receipt.

The mixer accepts promoted absolute declarations inside the accepted directory
or relative declarations. It checks declared file hashes/sizes when present,
requires the manifest and both selected raw/polished WAVs to be declared, and
uses `verify_take` to verify recipe/settings identity, hashes and real measurements.
Paths escaping their artifact root, traversal, and symlinks fail closed.
Each directed line matches an unused manifest entry by stable ID when provided,
plus speaker, whitespace-normalized text, and cast voice. Without IDs it matches
that tuple with multiplicity, not array order. Reordered take manifests, intentional
overlapping speech and offscreen lines are supported. Match text to the selected
take's generation settings too: relabeling a manifest line is not valid reuse.

`direction.duration` and every line's `start`/`end` are seconds; all are converted
once to 48,000-Hz sample positions. The bounded helper handles films up to 300 s,
PCM16 mono/stereo takes at 48 kHz, and produces stereo PCM16. Mono voices are
duplicated without changing level. A take keeps all original samples if it fits.
If necessary, only exact-zero trailing silence, then exact-zero leading silence,
is removed. Quiet nonzero breaths/consonants and internal pauses are never cut,
and speech is never sped up, stretched or resampled. Insufficient slots fail:
extend direction or explicitly audition a new take upstream. This deliberately
does not use the voice manifest's threshold-based activity bounds as cut points.
Overlaps are summed; if headroom is needed, uniform attenuation of mix and stem
prevents clipping without changing time, and its gain is audited.

Outputs: `mix.wav`, `dialogue.wav`, `timeline.json`, `audit.json`, reproducible
`request.json`, copied inputs under `inputs/`, and a final **complete** `result.json`.
The result declares every dependency/output except itself and supplies `mix`,
`dialogue_stem`, `timeline`, `source`, `audit`, `summary`, `quality`, and `files`.
Mix, dialogue stem, and timeline share exactly the same frame count, including
trailing silence. Timeline dialogue follows direction order at planned starts;
it includes source line IDs/take IDs and preserves offscreen notes. No effects
are invented (`events: []`), and the bed/no-bed choice has an explicit rationale.
Audit records source hashes, selected take IDs, exact edge trims and gain.

The copied selected WAVs, relative manifest, normalized direct snapshot and bed
make `request.json` replayable after moving the whole output tree or removing the
original accepted directory. Replay revalidates inputs. Repeated identical input
and options produce deterministic outputs with no timestamps. FFmpeg bed output
is reproducible within the same installed FFmpeg implementation. The controller
still checks cast/timing, loudness, intelligibility and mouths/ASR; this helper
reports `asr: not_run` and `emotional_quality: not_assessed`, not creative approval.
| edit | H.264/yuv420p, 48 kHz audio, delivery size, fps and duration; output timeline recalculated from the approved EDL, with every retained spoken line kept whole |
| frame/qa | the final is normalised to -14 LUFS / -1.5 dBTP; the mix gates and the Whisper check pass again on the finished video; the story picture passes the freeze/black/contrast checks; the Frame end card is present (differs from the edit, dark type on a light ground) |

Voice takes from `harness/audio.py` are polished by default (`VOICE_CHAIN`: high-pass, mud
cut, presence lift, light compression); the untreated take is kept as `<name>.dry.wav`. Clear
Kokoro voices measured here: am_michael, bm_lewis, am_adam, am_fenrir, bf_emma, af_heart,
af_nicole. Dull ones (need help or recasting): am_onyx, af_bella, bm_george, bm_daniel.
