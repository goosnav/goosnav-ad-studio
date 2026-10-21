# GET YOUR OWN — a hand-made Book Two ad (2026-10-21)

A 24.5 s, 1080×1350, 24 fps ad for *The Goosnav Dilemma* (Goosnav Comic Collection No. 2),
made by an operator working directly with the studio's tools rather than through an
unattended harness run. This log records the whole approach, so the next ad can reuse what
worked and avoid what didn't.

- Film code: `films/get_your_own/` (run `films/get_your_own/make.sh`).
- New shared helpers: `blender/book2.py` (perform the openable Book Two, hand-on-page IK)
  and `blender/shots.py` (face-aimed close-ups).
- New library assets (goosnav-3D-assets PR #2, merged as `cdf61f1`): the
  `props/ps1/library_book_rest` prop and its builder, plus the production record in
  `ads/book2-get-your-own/`.
- Final film: `~/Desktop/business/studio/output/films/get_your_own/get_your_own.mp4`.

## 1. The brief, and what "compelling" had to mean

The ask: entertaining, and it should make people genuinely curious about Book Two and want
to buy it. Owner rules that bound the work (from earlier sessions): the ad stars the library
3D characters; the early-3D game look; all text comes from the Goosnav Frame end card, in
clean type; speakers visibly talk, with clear dialogue; and tight close-ups are funny (said
during this production).

**Product facts, checked live** (`goosnav.shop/products/goosnav-book-two.json`): "The Goosnav
Comic Collection No. 2", a hardcover of Goosnav's best 2025 comics; every order gets a
limited signed copy and a free eBook PDF; $29.95; ships in 1–2 weeks. The cover title is
*The Goosnav Dilemma*.

**The source of curiosity is the book's real content.** The library's openable Book Two has
13 interior pages from real scans. Seven are September 2026 comics, which are not Book Two
material. The six March/April 2025 drawing sheets are pages 8–13: Foot Oiling Machine, Shoe
Multipliers, Gnome Deflacator ("NOTE: GNOMES REPRODUCE BY MITOSIS"), Toe Truck, Freak,
Automated Gnome Armorer, Accountant on the Hunt, Emotion Nullifier, Snace, Sack of Mischief,
and Self-Filling Coffee Mug. These are absurd, specific and visual, which is exactly what makes
someone want to see the rest. So the ad opens the book at spread 8|9 and only ever shows
2025 pages. No drawing was imitated or regenerated.

**Correction (later the same day):** membership of these sheets in the printed Book Two is
*not* verified. A drawing date and a texture inside the Book Two model are not edition proof,
and several of the same inventions also appear as Goosklerf card art (footoil,
shoemultipliers, gnomedeplacator, gnomearmorer, freak, spiglet). `harness/product_content.json`
therefore lists them as `unconfirmed` until the owner confirms the printed pages.

## 2. Concept

Rejected directions: the book on a pedestal as a sacred object (no joke); a character
struggling to open it (it's about the object, not the content); a montage of pages (no
people, no tension).

Chosen: **someone reading Book Two aloud to a friend who can't see it.** Hearing a
deadpan description of an impossible invention, without seeing it, builds curiosity
directly. The friend's escalating need ("Why?" → "Made of what?" → "Let me see.") is the
audience's own. The reader refuses with "Get your own", which is both the punchline and the
call to action. The end card picks up that line: "Get your own signed copy". A distant
librarian's "Shh!" after the slam gives a second laugh and makes the vast hall feel lived in.

Final script (READER = plate-eyed v10, PAL = beady v10):

| t (s) | Shot | Line / action |
|---|---|---|
| 0.0 | Wide, slow push | Vast reading room; a pool of lamplight at one desk |
| 2.4 | Two-shot (¾ front-right) | READER: "There's a machine that oils your feet." |
| 5.3 | Tight CU PAL | PAL: "Why?" |
| 6.4 | Tight CU READER | READER: "Doesn't say." |
| 7.85 | Insert, left page | Hand flicks leaf 5 over: *Toe Truck* page lands |
| 8.85 | (over insert → CU READER) | READER: "This one's a truck made of toes." |
| 11.1 | Extreme CU PAL | PAL: "Made of what?" |
| 12.2 | Tight CU READER | READER: "Toes. Lots of toes." then turns leaf 6 |
| 14.15 | Insert, right page | *Self-Filling Coffee Mug* revealed |
| 15.0 | (over insert → two-shot) | READER: "Self-filling coffee mug." |
| 17.1 | Book's-eye view | PAL leans in, nose first: "Let me see." |
| 17.95 | Two-shot | READER slams the book shut, presses it down: "Get your own." |
| 19.85 | Wide | The slam echoes through the hall; distant "Shh!" |
| 21.5 | Frame end card (3 s) | Floating Book 2 clip, "Get your own signed copy", www.goosnav.shop |

## 3. Pipeline: reuse what worked, build what was missing

| Need | Reused | Built |
|---|---|---|
| Voices | `harness.voice` Kokoro batch (measured takes, provenance) | Casting round plus Whisper/pitch measurement |
| Mix | `harness.direction.check_mix` gate, `harness.lipsync.mouth_curves` | `sound.py`: placement plus synthesized foley |
| Set | `environments/reading-room` | Scaled to 0.4, re-lit, desk cleared |
| Characters | v10 plate and beady rigs; `performance.apply` (idle, gaze, talk, blinks, mouths) | Authored leans and whole-body slide; IK hands |
| Book | `props/hq/book2_goosnav_dilemma_openable` and its demo actions | `blender/book2.py` retiming, page turns, slam |
| Prop | none | `library_book_rest` (3D library) |
| QA | `harness/scene_check.py` | Animatic contact sheets; hand-gap measurement |
| End card | `harness.media.finish_frame` and the library Book 2 floating clip | none |

### Voices
Casting round (`casting.json`): four reader and four friend candidates on one line each, measured
for median pitch and transcribed with the local Whisper (`openai/whisper-small.en`). Reader
**am_onyx** (≈92 Hz, calm, deadpan); PAL **am_puck** (≈137 Hz, brighter, curious). The
pitch gap keeps the two voices distinct. am_eric was misheard ("holds your feet") and
dropped. Final takes: two auditions per line (`voices.json`), choosing the clean ASR match.
Plain "Toes." was misheard every time ("Those", "Dozen"), so the line became "Toes. Lots of
toes." (`voices_toes.json`), which transcribes perfectly and lands the joke harder.

### Sound (`sound.py`)
Takes are trimmed to their measured active speech, high-passed, and levelled to a −19 dBFS
loud-part RMS, with a touch of short room reverb. Everything else is synthesized:
low hall air, a far clock ticking once a second through a 5 s stone-hall impulse response,
paper page turns (rustle, crinkle bursts and a landing flap), the slam (pitched thump, slap and
crack, then that hall tail), and a band-limited noise "Shh!" that is mostly reverb and panned right.
The studio's dialogue gate passes: lines at −18.6 to −19.5 dBFS over a −54 dB bed, with the loudest
non-dialogue window (the slam echo) at −16.8 dB, within the 3 dB rule. `mouths.json` is
measured from the dialogue stem by `harness.lipsync`.

### Set and staging (`scene.py`)
The reading room is built at about 2.2× human scale (2 m desks). Scaling it by 0.4 turns its
desks into 0.86 m standing desks while the hall stays immense, which is the joke's scale:
two small people, one book, a cathedral of silence. Hall lights are rescaled by S²
(inverse square). One green banker's lamp is kept, screen-left of the pair. A warm lamp key,
a face fill and a cool hall rim are added. Texture sampling is set to Closest for the crunchy
128 px patterns. Chairs and generic open volumes near the actors are removed.
The v10 arms are short and the IK hands hang at 0.8 m, so a book lying flat on the desk is
out of reach. Hence the new **library book rest**, which tilts Book Two up to the hand.

### Acting (`animate.py`, `blender/book2.py`, `blender/shots.py`)
1. **Book**: `book2.retime` samples the asset's own demo actions on the cut: hold spread
   8|9, flick leaf 5 (0.5 s), hold, flick leaf 6, then all leaves and the cover swing shut in
   0.25 s, accelerating, with the paper flexing mid-slam and the whole book jolting on impact.
2. **Hands**: the rig's forearm IK (influence 0 at rest) is keyed on for each turn. The wrist
   rides the turning leaf's free edge, sampled per frame from the evaluated mesh with curl
   included. For the slam, the hand grabs the turned stack's edge, rides it over, then presses
   the closed book down through "Get your own".
3. **Bodies**: leans keyed on spine, chest and neck; `performance.apply` then leaves those authored
   channels alone and composes the library idle, gaze cues (`look_at` the page or the other
   actor), talk motion, blinks and the measured mouths. The desk hides the PAL's feet, so his
   lean-in is a whole-body slide and turn toward the book, then a recoil at the slam.
4. **Cameras**: tight 50 mm close-ups where the faces fill the frame; an extreme close-up
   for "Made of what?"; page inserts square to each page; and for "Let me see" a camera built
   by `shots.face_camera` at the moment of the lean: from the book's point of view, looking up
   at the PAL's face along his real gaze, swung 0.6 so the nose reads in three-quarter view.
   Cuts are timeline markers. The reader's head and torso are hidden only during inserts, so
   the page cameras can sit where his chest is while his hand and sleeve stay visible.

### Render and finish
EEVEE, 540×675 native at 32 samples (≈2.6 s/frame on this machine), PNG sequence that
resumes after interruption, then one nearest-neighbour 2× upscale to 1080×1350 (`retro_world`:
native ≥540×675, upscale once). The master holds its last frame for 3 s. `finish_frame`
replaces that window with Frame's stacked card over the library Book 2 item clip and
normalizes loudness.

## 4. Problems found and how they were caught

| Symptom | Cause | Fix |
|---|---|---|
| Book missing from every board | `matrix_world` read before the depsgraph updated, so the book sat at the origin | `view_layer.update()` before seating |
| Rest sunk into the desk | Desk top is 0.86 m (slab centre 2.0, 0.3 thick), not 0.83 | Computed from the slab |
| Left half of the spread invisible | The opened cover hinges ~1 cm below the book's base and sank into the slope | Seat lift 0.079 m, recorded on the prop |
| Two-shot showed the back of the reader's head | Straight-on camera: the long nose pointed at the lens (end-on), hiding the mouth | ¾ front-right camera |
| Insert dissolved into white during flips | The camera sat inside the 0.23 m arc a leaf sweeps | 0.42 m away, longer lens |
| White blob under the book after the slam | IK ends at the wrist; the fingers hang 6–9 cm below it, through the book | Target offset by the hand length |
| `scene_check` failed the extreme close-up | Camera on the far side of a face looking at the reader | Camera on the facing side |
| "Let me see" showed the top of a head | Downcast face shot from eye level | Book's-eye view along the real gaze |
| Whisper heard "Those" for "Toes." | One-word line, no context | "Toes. Lots of toes." |
| Analysis scripts failed on `import numpy` | A scratch `inspect.py` shadowed the standard library | Scratch scripts moved to `scratch/` |
| Animatic failed to encode | 50 % of 675 is odd; H.264 needs even sizes | 40 % previews |

## 5. Final QA (measured on the delivered file)

- `get_your_own.mp4`: 24.50 s, 1080×1350 H.264 at 24 fps, AAC 48 kHz stereo, 8.1 MB; −14.3 LUFS
  integrated, −2.2 dBTP.
- Dialogue gate on the final audio: every line −13.3 to −14.7 dBFS over a −50.5 dB bed;
  loudest non-dialogue window −12.2 dB (the slam), within 3 dB of the loudest line. Pass.
- Whisper on the final audio heard all nine lines exactly ("Toes, lots of toes" for
  "Toes. Lots of toes.").
- `harness/scene_check.py`: every line's speaker has an open mouth on 65–75 % of the line and a
  visible, unblocked, readable face (0.52–1.0 of the line; the inserts are voice-over by design).
- Reviewed visually: contact sheets every 0.5 s across the film, plus full-resolution
  close-ups, inserts and the end card.
- Render: 516 story frames at about 2.6 s each (EEVEE, 32 samples), slower while other
  Blender jobs ran. The Frame finish took 1.4 min.

## 6. Lessons for the next ad

- **Long-nosed characters need ¾ angles.** Any camera on the nose axis hides the mouth;
  `scene_check` may still pass. Look at the frames.
- **Real product content is the strongest hook**, but check provenance per page:
  the openable book mixes 2026 comics into "Book Two".
- **Scale borrowed environments to people.** The reading room at 0.4 gave human-height
  desks inside a monumental hall.
- **Author body acting first, then call `performance.apply`.** It preserves authored
  channels and composes gaze, talk, blinks and mouths around them.
- **IK targets are wrists.** Offset by the hand length when the fingers must touch something.
- **Contact sheets every 0.5 s of a low-res animatic** caught every staging problem
  before the expensive render.
