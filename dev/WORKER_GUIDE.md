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
shot (the real product model, large and square to camera). With `output.frame: full`
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
| edit | H.264/yuv420p, 48 kHz audio, delivery size, fps and duration; output timeline recalculated from the approved EDL, with every retained spoken line kept whole |
| frame/qa | the final is normalised to -14 LUFS / -1.5 dBTP; the mix gates and the Whisper check pass again on the finished video; the story picture passes the freeze/black/contrast checks; the Frame end card is present (differs from the edit, dark type on a light ground) |

Voice takes from `harness/audio.py` are polished by default (`VOICE_CHAIN`: high-pass, mud
cut, presence lift, light compression); the untreated take is kept as `<name>.dry.wav`. Clear
Kokoro voices measured here: am_michael, bm_lewis, am_adam, am_fenrir, bf_emma, af_heart,
af_nicole. Dull ones (need help or recasting): am_onyx, af_bella, bm_george, bm_daniel.
