# Comic Theatre: a small stage, not a committee of agents

Date: 2026-10-21. Status: proposed design, updated with the owner's JSON/game-engine clarification.

## Intent

Turn an actual Goosnav comic into a performed conversation: a reader offers an
interpretation; another character challenges, misunderstands, or extends it.
The comic is visible, the dialogue is intelligible without successful physical
comedy, and the characters' timing and reactions supply the performance.

The user wants this almost entirely automated, fast enough to use repeatedly, and
portable into a separate repository. Human-written JSON must be sufficient. In the
owner's terminology, “no AI” means no paid API or Codex/Claude agent call; local
speech synthesis is welcome. Optional AI script generation must never become a
renderer dependency. The product is a specialized game/cutscene engine, not an AI
animator or an agent puppeteering a scene through tools.

This design makes the following implementation choices, not previously approved
owner decisions: Node/Three.js as the core; a seated library duet first; local
Kokoro as the initial automatic speech backend; a bounded set of shots and gestures;
local delivery before integration with the parent ad uploader.

## First product and later formats

**First technical slice, not the whole v1:** two ordinary Homunculus-derived characters at a library
table, a book already open, one real comic discussed, restrained expressions,
speaker/listener cuts, measured line audio, and a complete MP4 plus captions and
receipts. Begin with roughly 30–60 seconds for testing, not a mandatory duration.
This slice proves the renderer; it does not satisfy the book-action requirements alone.

**Book-specific v1:** reliable cover opening, page turning to a specified spread,
table reading, handheld reading, closing and a book slam, with explicit facial and
listener-reaction commands. Also local speech, a solo fireside preset and recipe-
based scene variation. Two wardrobe variants and optional writing/delivery follow
the working performance system. Build the book rails first, not a generic engine
for every product. The future card-hand format is recorded in [V2_CARD_GAME.md](V2_CARD_GAME.md).
The solo reader is an affable, theatrical commentator, not a celebrity voice clone.
A pipe can be a static costume prop later, not a physics dependency.

**Not v1:** open-world navigation, arbitrary character/rig support, arbitrary sets,
generated motion per episode, full physics, automatic clothing generation per run,
learning model weights, publishing unattended to public channels, or guaranteed
conversion. Do not import Homunculus's game simulation, autonomous mind, survival
states, or interaction UI into the production engine.

## The production boundary

```text
human JSON ────────────────────────────────┐
optional AI writer → validated draft JSON ─┤
                                          ▼
source + asset validation → voice takes → measured timeline
                                          ▼
                          performance/camera compiler
                                          ▼
                         deterministic Three.js playback
                                          ▼
                         chunk capture → FFmpeg → checks
                                          ▼
                     full MP4 + captions + receipt
                                          ▼
                         optional delivery adapter
```

There are no writer/director/animator/editor agents in the render path. The compiler
is the director/editor for a bounded set of proven stage arrangements. Creative
judgment is in the authored script and reusable recipes, not repeated orchestration.

## JSON authoring contract: `comic-theatre/v1`

The document below illustrates the proposed syntax. It is a design example, not
a runnable episode: its manifest IDs and recordings must be supplied. Quotes must
be transcribed from an inspected source, not trusted raw OCR.

```json
{
  "schema": "comic-theatre/v1",
  "title": "The Unreliable Adviser",
  "product": "book-edition-approved",
  "seed": 17,
  "scene": "library-table",
  "cast": {
    "reader": {"asset": "reader-plain", "voice": "reader"},
    "friend": {"asset": "friend-plain", "voice": "friend"}
  },
  "source": "comic-page-36",
  "beats": [
    {"id": "open", "kind": "action", "actor": "reader",
     "rail": "book.open", "spread": "comic-page-36"},
    {"id": "read", "kind": "show_source", "view": "full", "hold_seconds": 4},
    {
      "id": "a", "kind": "line", "speaker": "reader",
      "text": "He trusts the parasite more than his friend.",
      "audio": "takes/a.wav", "emotion": "thoughtful",
      "gesture": "explain", "look_at": "friend", "pause_after": 0.4,
      "face": {"brow_left": 0.15, "brow_right": 0.35, "eye_open": 0.8},
      "reactions": [{"actor": "friend", "at": "line_end",
                     "emotion": "skeptical", "gesture": "head_tilt"}]
    },
    {
      "id": "b", "kind": "line", "speaker": "friend",
      "text": "The parasite has an inside source.",
      "audio": "takes/b.wav", "emotion": "dry",
      "gesture": "none", "look_at": "reader", "pause_after": 0.6
    },
    {"id": "reaction", "kind": "hold", "seconds": 1,
     "actor": "reader", "emotion": "skeptical"}
  ],
  "output": {"width": 1080, "height": 1350, "fps": 24},
  "closing": {"mode": "none"}
}
```

The two commentary lines above are new fictional interpretation, not quotations
from the comic or assertions about the author's intent. The actual inspected page
shows a character eating dirt/grubs, a warning, and the reply about a brain parasite
calling the other character toxic. Whether this makes a good episode remains a
creative question; it is only a compact contract example.

### Required semantics

- `schema`, title, product, cast, source and nonempty beats are required. Seed,
  scene, acting controls, output and closing may be omitted. Defaults are explicit:
  scene is seeded compatible selection, output is 1080×1350/24 fps, closing is
  `none`, emotion is neutral, gesture is none, gaze is the current other speaker
  or the source for a solo reader, and face values come from the emotion preset.
  Unknown fields are errors with a JSON pointer and the
  accepted names. Fail before voice/render work; never silently ignore a typo.
- IDs are unique, stable strings. Cast has one or two entries compatible with the
  selected scene. Line speakers, gaze targets, sources and assets must exist.
- Beats are a tagged union: `line`, `show_source`, `hold`, or `action`. Actions
  invoke versioned book rails, never generated code. `show_source` means a
  legible insert of the unchanged source. `hold` means a deliberate silent reaction,
  not an excuse to substitute a title card for missing dialogue.
- A line may optionally specify `shot`: `auto`, `speaker`, `two-shot`, or
  `source`. `source` keeps the real comic visible while the character reads or
  comments off-screen. Default is `auto` with speaker visibility. `show_source`
  supports `full` or a named panel crop from the verified source manifest.
- `source` at episode level chooses the initial focus page. Each source record
  maps to an approved book spread and left/right side. Opening/turning with a
  `spread` argument names the target source ID; its manifest mapping resolves both
  the physical spread and the new focus page. Subsequent implicit source shots
  follow that focus page, not the episode's original page. `show_source` and lines
  with `shot: source` can supply `source` to select either page of the current
  spread; other pages require an explicit book action first. Panel names resolve
  only inside the selected source record. A source insert while the book is closed
  is invalid in this initial grammar. Tests must turn a page and verify that book
  textures, full inserts, panel crops and source-shot dialogue share the same IDs.
- Facial enums: `neutral`, `thoughtful`, `curious`, `skeptical`, `dry`, `pleased`,
  `concerned`, `exasperated`. Intensity optional, default 0.5, range 0–1. These are
  acting controls, not a promise that a voice provider supports those emotions.
- Optional `face` overrides individual normalized channels: `brow_left` and
  `brow_right` (-1 to 1), `eye_open` (0 to 1), `mouth_curve` (-1 frown to 1 smile),
  and `blink` (`auto`, `once`, `off`). Omitted channels inherit the emotion/default
  preset, not random guesses. Explicit channels win. Bounds are validated against
  the actor adapter. Speech opening remains audio-driven; mouth curvature is
  authorable without accidentally freezing lip sync.
- A line's `reactions` array specifies listener actor, `at` (`line_start`,
  `line_end`, or seconds after the measured line start), `emotion`, optional `face`,
  `gesture`, `look_at`, and `duration` (default 0.8 seconds). Numeric offsets must
  lie within the line. Missing reactions use quiet listening, not invented acting.
  Timed overlaps on the same actor/channel are errors. The compiler extends the
  post-line pause to fit a line-end reaction before the next sequential beat.
- Gesture enums: `none`, `explain`, `nod`, `head_tilt`, `shrug`, `page_glance`.
  Default `none`; automatic small talk motion and listener gaze are separate.
  No automatic walking, pointing to tiny moving props, or object exchanges.
- Timing numbers must be finite and nonnegative; holds must be positive. Reject
  NaN, unsafe dimensions, unsupported FPS, extreme files and resource estimates
  using explicit safety limits exposed in `--help`, not hidden story deadlines.
- v1 permits sequential speech only. Do not silently discard or serialize an
  author's overlapping dialogue request; report it as unsupported.
- `closing.mode` is `none` or `product`. `product` requires a verified product ID
  and a configured closing recipe, independent of the dialogue renderer.
- CLI voice mode selects `recorded`, `flite`, or `kokoro`; default `kokoro`.
  Recorded mode requires each line's audio. TTS modes synthesize missing audio
  while preserving supplied takes. A `delivery` note is permitted but must be
  reported as advisory if the selected backend cannot execute it.
- Lines can supply a supported voice-settings override (`speed`, `phrasing`,
  `pauses`) validated against the chosen adapter's capability list. No silent
  change of speaker identity, voice model, or words. No automatic voice cloning.

### Normal operation and optional writing

1. **Normal automated render:** authored JSON + locally generated speech. No paid
   API, API key, Codex or Claude call. After explicit one-time dependency/model
   setup it works offline. Local neural TTS is not excluded by the user's “no AI”
   requirement. Recordings can replace any take without changing the animation path.
2. **Recorded mode:** no speech model needed. Optional Flite supplies inexpensive
   non-neural animatic speech, not the recommended final acting quality.
3. **Optional AI writing:** an explicitly enabled writer produces the same JSON. It does
   not generate executable scene code or control the renderer. Rendering a saved
   script remains independent of that provider being available.

### Defaults and deterministic variation

An omitted scene is chosen from the product rail's approved compatible presets,
filtered by cast size, actor adapter and all requested book actions. Do not select
arbitrary files from an asset folder. If none qualifies, fail with the available
presets/capabilities. Optional wardrobe/set dressing uses the same constrained
approach; product edition, source pages and dialogue are never randomized.

Missing seed is generated once at run creation and saved with every resolved
default in `resolved-episode.json`. Same resolved JSON + asset versions + voice
takes produce the same performance. A fresh invocation with no seed may vary;
resuming never chooses again. A supplied seed makes selection reproducible from
the start. `validate` checks possibilities without committing an ephemeral seed.
Explicit configuration always overrides defaults. Invalid supplied values are
errors, not grounds for quietly switching to defaults.

## External manifest, not hardcoded paths

The application consumes a local `library.json` selected with `--library` or
`COMIC_THEATRE_LIBRARY`. No implicit scan of the parent repository is required.
The manifest declares named roots, asset IDs, relative paths, hashes, rig adapters,
capabilities, scene anchors, source provenance and optional voice profiles.
Relative roots resolve against the manifest file, never the current working
directory. Explicit absolute roots are allowed in a user's local config, not in
checked-in application defaults.

Resolve symlinks before containment checks. Reject archive/archives/archived path
components and root escapes, including GLTF external buffers/textures. Require
actual binary contents, not Git LFS pointer files. Serve only manifest-approved
files through an ephemeral loopback server, never the whole asset directory.
The renderer may not fetch arbitrary remote URLs embedded in an asset or script.

A validated asset snapshot records content hashes and capabilities per run. A
refactor changes the manifest, not application source or all existing scripts.
Two actors need independent skeletons, poses and per-instance mutable materials;
otherwise one character's gesture/clothing can alter the other.

## Source honesty and book handling

A source record contains an image asset ID (whose asset record holds its hash),
`pdf_sha256`, `pdf_page`, optional `printed_page`, book `spread_id` and `side`,
manually checked transcript, panel crops, and edition status:
`confirmed`, `unconfirmed`, or `not_applicable`. Edition confirmation also needs
an evidence note; an AI writer cannot upgrade it.

v1 is explicitly book-selling, so `product` is required even if the closing is
`none`. The manifest's `products[product]` binds an edition ID, approved book asset
ID, allowed source IDs and evidence note. Every displayed source must be confirmed
for that edition; the exterior must be approved for it. A branded book or dialogue
claim cannot evade this rule merely by disabling the end card. `not_applicable`
is not valid for this book-product path. Missing evidence fails preflight without
asking the user during rendering. Preparation resolves provenance once, upstream.

An explicit developer-only `--draft` may render unconfirmed material locally with
draft status and delivery disabled; it is not a normal product run or success
receipt. Do not infer edition identity from a filename or model. Technical output
and ready-for-delivery status remain separate. AI cannot modify these bindings.

The existing Homunculus PDF provenance and current v2 book provenance have
different hashes. They must remain separate records until the exact images and
edition mapping are checked. File names saying “Book Two” are not proof.

Show original art unchanged. A panel insert crops only through an explicit crop
definition; do not re-letter, recolor, redraw, or invent comic panels. Never turn
uncorrected OCR into an authoritative quotation. The proposed source packet keeps
quotation, observation and invented commentary separate.

## Book rails: the v1 animation engine

Each `action` beat names an actor and one finite-state rail:

| Rail | Required state → resulting state | Reliable visible result |
| --- | --- | --- |
| `book.open` | table-closed → table-open | Cover opens; optional target `spread` is shown through the approved reveal cut |
| `book.turn` | table-open → table-open | One adjacent spread turn, `spread` required; leaf and hands follow authored tracks |
| `book.hold` | table-open → held-open | Tested lift into a two-hand reading pose, with book and grips attached correctly |
| `book.read` | table-open or held-open → same | Reading posture, page gaze and restrained breathing for requested `seconds` |
| `book.place` | held-open → table-open | Tested return to the table without interpenetration |
| `book.close` | table-open → table-closed | Controlled closing with correct cover/leaves |
| `book.slam` | table-open → table-closed | Fast authored close, hand contact, brief reaction and timed foley |

Initial book state is table-closed, on the validated stage anchor. No action beat
may silently teleport it to satisfy an illegal transition. `book.open` can reveal
a selected spread with a predetermined camera cut, not fake a continuous turn
through an entire book. `book.turn` only accepts adjacent spreads so it never
pretends arbitrary pages are consecutive. A future explicit cut-to-spread command
can handle nonadjacent selections; it is not implicit in a turn.

Action duration comes from the rail (versioned start/contact/settle markers) unless
`seconds` is supplied within its tested speed range. `book.read` defaults to 1
second. For speech while holding/reading, set `posture: "read"` on the line; it
uses the current book state without blocking dialogue behind a separate silent
action. Hand/arm channels reserved by gripping cannot simultaneously shrug or
gesture; an incompatible explicit gesture is a clear validation error. Default
talk motion simply avoids reserved limbs. Speaker head/gaze changes stay within
the hand/face visibility envelope validated for that rail.

Author these rigs/tracks once in the 3D library using Blender as needed. Store grip
sockets, actor compatibility, book axes/page map, duration range, camera coverage
and contact tolerances in the rail metadata. Runtime code samples the tracks and
bounded deterministic constraints; no paid inference, Codex/Claude, generated
animation code, free-running physics, or frame-by-frame manual editing is involved.
JSON commands drive the same rails in preview and export. A slam cannot change
which comic was read; a close-up cannot display a different page to the book.

Table and handheld are separately tested arrangements, not arbitrary IK promises.
Use a prevalidated hand-grip pose/sockets and authored lift/place tracks for the
supported character/book dimensions. Record maximum measured grip error and
visible intersection checks across every rail, both actors, and allowed speeds.
If the model cannot meet these constraints, repair the reusable rail/asset instead
of hiding an unsuccessful action behind an end card. These capabilities are part
of book-v1 acceptance, not optional future polish.

## Performance and editing

Voice preparation precedes scheduling. Decode each take to 48 kHz PCM, measure
real duration/activity, retain deliberate pauses, then assign sample offsets.
Video time is derived from those offsets; never approximate speech from character
count, truncate speech to meet a target duration, or speed the whole mix up.

The compiler makes a locked timeline containing line boundaries, source windows,
shot boundaries, expression envelopes, gaze targets, gestures, blink events and
per-speaker amplitude mouth curves. All randomized choices use the script seed
plus actor/beat IDs and are resolved before rendering. A changed take invalidates
the affected timeline/segments, not unrelated accepted recordings.

`evaluatePerformance(timeline, sample)` returns the full state at any instant.
Rendering frame 500 directly must match rendering frames 0–500 sequentially on
the same stack. No accumulated sine offsets, wall clock, Math.random, game state,
or frame-rate-dependent damping in the export path. Preserve base/rest poses.

Compose layers: seated rest pose → breathing → speech gesture → authored gesture
→ gaze → facial expression → explicit JSON face/reaction overrides → measured
mouth opening. Book rails own their declared hand/arm channels over talk motion.
Face geometry stays attached
to the head, with per-rig attachment transforms. Speech owns the mouth opening;
emotion owns brows/mouth shape within tested limits. Listener mouths remain shut
except explicitly silent facial expression. RMS mouth movement is not phoneme-
accurate lip sync; an optional phoneme provider can improve it later.

The initial camera grammar is a two-shot, each actor's three-quarter close-up,
and a source insert. Hold shots through a thought. Cut on speaker changes or
authored reaction beats, not on every sentence. Protect page-reading time.
Avoid nose-axis views, crossing the conversation axis, and shots through furniture.
Only choose from validated stage slots; do not ask a model to invent camera XYZ.

Presets vary lamp direction, framing, restrained gesture selection, wardrobe and
set dressing within a tested envelope. Dialogue/personality supplies meaningful
novelty. Changing a seed must not rearrange plot, reorder panels, or randomize
expressions against the author's intent. Keep the default cast ordinary; astronaut
and skeleton remain explicitly selected, context-dependent future cast options.

## Voice quality

The safest high-quality path accepts original performances per line and keeps
them untouched except explicit technical processing. For TTS, choose contrasting
stable voices, phrase boundaries and reply pauses; audition a small bank once,
not every line of every episode. Cache accepted takes by text, voice/backend/model
identity, settings and processing version.

Kokoro is a useful existing local baseline, but an “exasperated” label cannot make
it reliably act exasperated. Report unsupported controls. Later expressive TTS
must demonstrate improved delivery with authorized voices before becoming a
default. Avoid celebrity imitation and keep the requested theatrical quality in
timing and writing rather than cloning a recognizable voice.

Keep dialogue prominent over quiet ambience. Supply an optional dry mix so room
effects cannot hide intelligibility. Silence/clipping checks are automated;
pronunciation, comic timing and emotion need listening to representative outputs.
Successful ASR is not proof of compelling acting.

## Runtime, restart and parallelism

Each run has its own directory, UUID, stage receipts and manifest. Suggested state:
`validating → audio → compiling → rendering → encoding → verified`; delivery, when
configured, is separately `pending → retrying → delivered` or `blocked` with reason.
Write stage receipts atomically only after checking their artifacts.

Capture deterministic short segments, then encode and concatenate them in order.
Segment frame ranges are integer half-open intervals covering every frame exactly
once. Hash/version all cache inputs. Resume verified segments only. A failed or
missing segment cannot become a repeated end card, silent filler, or a successful
finished video. A complete lower-resolution draft may be retained and clearly
labeled when final export fails; it is not silently delivered as final.

Retry transient browser/encoder failures up to two times per segment with backoff;
preserve checkpoints after exhaustion and return an actionable nonzero exit.
Invalid assets/scripts are not transient. Stalls have watchdogs. Soft performance
targets trigger progress warnings/profiling, not deletion of finished work or
forced story truncation. Safety bounds remain explicit and separate.

Multiple CLI launches enqueue independently. Default one GPU export at a time;
audio/validation may overlap within bounded CPU limits. Use a process-safe shared
lease, not just an in-memory semaphore. For Ad Studio coexistence use an optional
adapter to its existing resource lease; standalone uses its own configured shared
state directory. Never maintain two unrelated GPU locks and pretend they coordinate.

Outputs use a script-derived slug + UTC timestamp + short run UUID. Normal delivery
is the verified complete MP4 only, not the output folder or source ZIP. The
experimental renderer initially does not upload. A later explicit delivery adapter
uses a durable outbox, rate limiting, idempotent receipts and backoff; authentication
failures become visible blocked delivery, not silently successful runs. Each video
is eligible immediately after verification; no campaign-wide completion barrier.

## Proposed CLI (not implemented)

```sh
node bin/theatre.mjs validate episode.json --library library.json
node bin/theatre.mjs render episode.json --library library.json --voice recorded
node bin/theatre.mjs render episode.json --library library.json --voice kokoro
node bin/theatre.mjs preview episode.json --library library.json
node bin/theatre.mjs resume RUN_ID --output OUTPUT_ROOT
node bin/theatre.mjs status --output OUTPUT_ROOT
node bin/theatre.mjs draft brief.json --writer writer.local.json --output episode.json
```

Help lists all valid modes and enums. Error messages name the field and closest
legal options. Manual render never silently calls `draft`. `draft` uses operator-
configured provider/model policy, not an obsolete hardcoded model. User input is
data, never shell commands. AI failure leaves a draft error and never blocks
rendering an existing valid JSON script. Allow at most one structured repair of
invalid writer output; do not rebuild the old multi-agent planning loop.

## What it means to get better over time

Add versioned, reusable performance recipes, reviewed voice presets, stage layouts,
wardrobe exports, and source-verified comic packets. Keep existing successful takes
and run measurements. Use owner feedback on episodes to promote a new recipe;
do not auto-promote unreviewed generated assets or “learn” from completion counts.

Assets and reusable motion data belong in the 3D library; application/renderer code
belongs here. New wardrobe work is additive: editable Blender source, GLB, preview,
source hash and reproducible builder, without altering canonical character art.
No per-episode asset generation is required. Asset promotion/pushing is a deliberate
development step, never a side effect of rendering. Publish nothing in this design
phase. The library's existing dirty work remains untouched.

## Acceptance and limits

- A fresh standalone copy renders human JSON with installed local speech and
  network blocked, without Ad Studio imports, credentials, Codex or Claude. A
  recorded-audio test also runs without the optional speech model installed.
- JSON facial controls, listener reactions and defaults have visible tested effects.
  Seeded scene selection stays within product/rail-compatible presets.
- Opening, adjacent page turning, held reading, placing, closing and slamming all
  pass contact/page-identity/visibility checks; no AI animates them. The initial
  seated-only technical slice is not called a finished book-v1 engine.
- A full representative conversation includes every line, readable authentic art,
  distinct speaker voices, visible reactions and a valid MP4 with correct duration.
- Scrubbing, changed FPS, resumed capture and parallel launches do not alter timing
  or cross-contaminate files, skeletons, caches or output identity.
- Failures are named and checkpointed; no title-card-only “success.”
- A measured 60-second benchmark reports cold/warm audio, asset load, compile,
  capture and encode time, hardware/GPU backend, memory and contention. Initial
  engineering goals: warm export within 3 minutes at 540×675/24 fps and within
  10 minutes at 1080×1350/24 fps on the tested workstation. These are unproven
  optimization targets, not runtime abort thresholds or promises.
- Owner reviews at least one duet and one solo example before the format is called
  creatively successful. Automated execution need not request approval per episode;
  this initial format review is development, not a permanent runtime gate.
- Technical reliability, entertaining output, owner approval and conversion remain
  separate findings. No claim of almost-100% quality automation until examples
  and repeated unattended runs justify it.
