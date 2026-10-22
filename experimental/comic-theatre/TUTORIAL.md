# From a comic to a conversation

Comic Theatre is an experimental local cutscene engine. You write a small JSON
script (or use the editor), select real comics, and let reusable code perform it.
The renderer never asks Codex, Claude or a paid API to animate. Local voice synthesis
is automatic after setup. Optional AI writing is a separate button/command.

## 1. Install on a new computer

You need **Node.js 22.12 or newer**, **FFmpeg with ffprobe on PATH**, and, for local
voices, **Python 3.10–3.12**. Windows, macOS and Linux use the same Node commands.
The implementation is tested on Linux; Windows/macOS setup is designed to be
portable but has not yet been exercised on those operating systems.

Clone the repository, then enter `experimental/comic-theatre`. Alternatively copy
this entire directory into its own repository. Its `assets/` contains the character,
book, environment export and verified comic excerpts; there are no runtime links
to another checkout, a home directory, or archived models. The directory is about
30 MB before dependencies. Node packages, browser binaries and voice weights are
installed once, not checked in.

```sh
npm ci
npm run setup:browser
node bin/theatre.mjs doctor
python tools/setup_voice.py
```

Use `python3` instead of `python` on machines where that is the Python command.
On Windows you can use `py -3.12 tools/setup_voice.py`. The setup creates `.venv`
inside this project and downloads the local voice model. It needs an internet
connection once. Subsequent renders use cached model files offline. If Linux
Chromium reports missing system libraries, install the dependencies listed by
Playwright (`npx playwright install-deps chromium` may require administrator rights).

To use an existing compatible Python environment, set `THEATRE_PYTHON` to its
Python executable. This is a local override, not a path saved in the source code.
`FFMPEG`, `FFPROBE` and `THEATRE_BROWSER` are optional executable overrides; normally
leave them unset. The project's pinned browser is the supported default.

**No speech model required:** use your own recordings with `--voice recorded`
(section 6). `doctor` checks browser, assets and video tools; voice setup is separate.

## 2. Open the editor

```sh
npm start
```

Open the loopback address printed by the terminal, normally
`http://127.0.0.1:8777`. Keep the terminal open while jobs run. This is a local app,
not a public web service: do not expose its port to the internet. No account needed.

Choose a template, then select comic thumbnails or use **Random selection**. The
gallery shows the actual image, printed/PDF page numbers, stable ID and transcript.
Write dialogue rows, choose speaker/emotion/gesture, or edit the JSON directly.
Validate, download a copy of your script, and generate the video. The jobs area
shows progress/errors and the completed MP4. UI labels may be shortened to fit.
The clothing selectors distinguish the readers without changing their familiar
silhouette. The end-card fields edit the closing title, supporting text, URL and
duration; disabling the card never removes dialogue.

The AI draft action is optional, requires explicit configuration (section 7), and
sends only the selected comic images and source packet to that configured provider.
It does not silently replace manual work or activate while rendering.

## 3. Choose a template

| Template ID | Comics | Speakers | Typical use |
| --- | --- | --- | --- |
| `book-duet` | Exactly 1 | `reader`, `friend` | A reading, disagreement, dry reaction |
| `fireside-reader` | Exactly 1 | `reader` | Solo commentary |
| `page-tour` | 2–3 | `reader`, `friend` | Compare several comics or build an argument |

The template provides cast, voice defaults and compatible staging. You do not need
to specify models, rigs, camera coordinates, lighting or frame numbers.

Current comic IDs:

| ID | Printed page | Subject |
| --- | --- | --- |
| `book2-020` | 20 | Great men of history / cookies / postponed ambition |
| `book2-036` | 36 | The brain parasite's advice |
| `book2-095` | 95 | Repainting white walls eggshell versus ivory |

These are the deliberately small **reviewed selection**, not a claim that the book
contains only three comics. See `assets/catalog.json` for exact PDF locators and
hashes. Additional pages need the review procedure in section 9 before random
selection can use them.

## 4. The smallest useful script

Save this as `my-script.json` in this folder:

```json
{
  "template": "book-duet",
  "title": "A Second Opinion",
  "comics": ["book2-036"],
  "lines": [
    {
      "speaker": "reader",
      "text": "My brain parasite says you're toxic.",
      "shot": "source"
    },
    {
      "speaker": "friend",
      "text": "That's a very convenient second opinion.",
      "emotion": "skeptical"
    }
  ]
}
```

```sh
node bin/theatre.mjs validate my-script.json
node bin/theatre.mjs render my-script.json --preview
node bin/theatre.mjs render my-script.json
```

`--preview` makes a complete small video at 432×540/12 fps. Normal output defaults
to 1080×1350/24 fps. Both include the same dialogue; preview never means “end card
only.” Speech is measured, so you do not enter a duration. Pauses and reactions
extend the episode rather than cutting words off.

The first line quotes the visible comic. The friend's line is fictional commentary,
not a new comic panel. Keep that distinction when writing your own episodes.

## 5. Optional acting controls

Add only the fields you need:

```json
{
  "speaker": "reader",
  "text": "He's known him longer.",
  "emotion": "dry",
  "gesture": "head_tilt",
  "face": {"brow_left": 0.1, "brow_right": 0.5, "eye_open": 0.7},
  "pause": 0.6,
  "reaction": {
    "actor": "friend",
    "at": "line_end",
    "emotion": "exasperated",
    "duration": 1
  }
}
```

- Emotions: `neutral`, `thoughtful`, `curious`, `skeptical`, `dry`, `pleased`,
  `concerned`, `exasperated`. Omitted means neutral.
- Gestures: `none`, `explain`, `nod`, `head_tilt`, `shrug`, `page_glance`.
  Omitted means none, with restrained automatic talk/listening motion.
- Face: `brow_left`, `brow_right`, `mouth_curve` from -1 to 1; `eye_open` from 0
  to 1; `blink`: `auto`, `once`, `off`. Unspecified channels use the emotion preset.
  Audio still controls speech-mouth opening. These settings control the visible
  face, not guaranteed emotional TTS delivery.
- Reaction: the other actor, `line_start` or `line_end`, emotion, optional face/
  gesture, duration. A solo template has no listener, so omit reactions there.
- `pause`: seconds after the spoken line, default 0.4. A longer line-end reaction
  gets its full time. It is not cut short by a smaller pause.
- `shot`: `auto` (default), `speaker`, `two-shot`, `over-shoulder`, `book`, or
  `source`. Auto chooses a repeatable varied sequence using the seed, starting
  with both readers when appropriate. Explicit choices always win. `book` slowly
  approaches the real open book and selected page; `source` shows the unchanged
  page flat for maximum reading clarity. Before each new comic, a three-second
  physical-book reveal establishes it. Use `shot: source` for a longer reading.

At the **top level** (alongside `template`, not inside a dialogue row), optional
clothing and end-card controls look like this:

```json
{
  "characters": {"reader":"blue", "friend":"rust"},
  "product": "book2",
  "endCard": {
    "enabled": true,
    "title": "Goosnav Book Two",
    "text": "A book of comics.",
    "url": "www.goosnav.shop",
    "seconds": 3
  }
}
```

Merge these fields into a complete script. Available variants: `blue`, `rust`,
`olive` have white eyes; `blue-beady`, `rust-beady`, `olive-beady` have small black
eyes without whites. You can mix the eye styles in one cast. Default readers wear
different colors. Book Two is the currently supported
product. Omitted end-card values use the example defaults. Title/text/URL limits
are 120/240/160 characters; duration is 1–12 seconds. The card is appended after
every spoken line and reaction. Its white, aliased early-web layout has a dithered
product image and blue underlined Times-compatible URL. Original comic pages are
not dithered. Fonts are bundled so another computer does not change the typeface.

Mouth motion uses measured speech energy with smooth jaw/round/wide shapes and
onset/offset easing. It is not phoneme-accurate lip sync. Expressions blend in and
out instead of snapping; all evaluation remains seekable and deterministic.

Local Kokoro currently has stable reader/friend voices, not a reliable direct
“angry” or “sad” synthesis knob. Use punctuation, short phrase structure and pauses,
or supply a recorded take. Do not expect a facial tag to change the voice magically.

## 6. Multiple comics, scene variation, book actions and recordings

For `page-tour`, list 2–3 IDs and put a `comic` on the line where the subject changes:

```json
{
  "template": "page-tour",
  "title": "Ambition and Interior Decorating",
  "seed": 42,
  "comics": ["book2-020", "book2-095"],
  "lines": [
    {"speaker":"reader","comic":"book2-020","text":"He plans to define an era."},
    {"speaker":"friend","text":"After the cookies."},
    {"speaker":"reader","comic":"book2-095","text":"This one has already transformed his entire house."},
    {"speaker":"friend","text":"From white to white.","emotion":"dry"}
  ]
}
```

Lines inherit the last comic ID. Every selected comic needs a dialogue line, and
you cannot reference an undeclared comic. A change to a nonadjacent page is a
deliberate edit/source cut, not a fake continuous page flip.

`scene` may be `library` or `fireside`, if compatible with the template. Omit it
for seeded selection. Omit `seed` for fresh variation; the chosen seed and all
defaults are saved in the run. Resume retains them. Randomness never changes the
words, comic IDs, voice identity or an explicitly specified reaction.

Optional action rows go in `lines` between spoken rows:

```json
{"action":"hold"}
```

Supported states: start table-open, unless the very first row is `open` (then
start closed). `hold` lifts an open book; `read` holds a silent reading beat;
`place` returns a held book to the table; `close` or `slam` closes a table-open
book; `open` reopens it. `turn` needs an explicit `comic` target on an adjacent
spread in the catalog. The
three starter excerpts are nonadjacent, so use subject cuts for them. Actions
accept optional `seconds` within 0.3–8. Invalid transitions are rejected before
rendering. Gestures that require the reader's occupied hands are rejected while
holding. **Experimental:** physical hand/finger contact is still subject to the
renderer review notes; do not assume every pose is production-approved.

Recorded audio:

```json
{"speaker":"reader","text":"Your performed line.","audio":"takes/reader.wav"}
```

Audio paths are relative to the input JSON file for CLI runs, and relative to this
project for GUI runs. No absolute paths or `../` escapes. Use WAV, FLAC, MP3, OGG
or M4A. In `--voice recorded` every spoken line needs audio; otherwise the run
fails clearly rather than silently synthesizing or inserting silence. With the
default local voice mode, individual supplied recordings override those lines.

## 7. Optional AI JSON producer

Copy `writer.example.json` to ignored `writer.local.json`. Set `model` to the
current image-capable model you want, and set its key in the environment variable
named by `keyEnv`. The endpoint uses the OpenAI-compatible Chat Completions
interface, including selected image attachments. It can also use an explicitly
configured local compatible server (`local: true`). No model name is hardcoded.

```sh
node bin/theatre.mjs draft --template book-duet --seed 21 --out episode.json
node bin/theatre.mjs validate episode.json
node bin/theatre.mjs render episode.json
```

This first chooses source material from the reviewed catalog, then asks the writer
for dialogue about those exact pages. For an existing selection, use
`draft my-script.json --out episode.json`. The GUI exposes the same operation.

There is at most one repair of invalid JSON, never an open-ended animator-agent
loop. Cooldown/authentication errors leave the selection/manual script intact.
Output cannot silently select another comic/template/scene. Writer prose can still
be wrong: image/hash checks prove which source was used, **not the truth or humor
of every interpretation**. Review the page and dialogue before spending on or
publishing a campaign. No live paid writer call was required to test rendering.

Never put keys in an episode, a catalog, or a committed file. Optional writer usage
can cost money; ordinary manual/local-voice rendering does not call that API.

## 8. Outputs, errors, resume and multiple runs

Each run gets its own directory inside `output/`, containing resolved `script.json`,
`timeline.json`, measured `mix.wav`, segment receipts, status, and the full MP4.
The video name contains your title, a UTC timestamp and random run ID.

```sh
node bin/theatre.mjs status
node bin/theatre.mjs resume RUN_ID
```

You may launch multiple commands or GUI runs. They queue in independent run
directories; this version limits production to one active worker per project to
avoid exhausting CPU/GPU memory. It does not coordinate with a separately running
Ad Studio Blender controller. Run this experiment on a dedicated worker while
testing, or wait for the other renderer to finish.

Failed captures preserve verified five-second segments. Resume checks their input
hashes before reuse; changed code/audio invalidates stale segments. Never edit a
running run's files. Edit your source JSON and start a new run instead.

The app does **not upload or publish** experimental videos. Success means a complete
local MP4 passed technical checks, not owner approval or measured sales performance.
Google Drive integration remains separate future work. No source ZIP is uploaded.

Common fixes: `npm ci` for packages; `npm run setup:browser` for the pinned browser;
voice setup for missing local weights; restore/review assets for a hash mismatch;
use a compatible template/page count for validation errors. Do not bypass source
verification to get around an asset mismatch.

## 9. How source consistency works—and how to add a comic

One stable comic ID connects: GUI thumbnail → transcript/source packet → selected
JSON → writer image → book page → source insert → final receipt. PDF hash, PDF page,
printed page and image hash are recorded separately so similarly named editions
cannot be silently mixed. Rendering verifies actual bytes, not filenames alone,
including the JPEG embedded in the physical book GLB. A render serves a frozen
snapshot of verified assets so a mid-render file edit cannot swap its source.

To extend the reviewed catalog, this is a one-time development/content-curation
step, not something an AI writer can do during a run:

1. Locate the exact supplied edition and its provenance. Never infer membership
   from a file date or an older openable book model.
2. Copy its unchanged page image into `assets/comics/`; do not generate replacement
   canonical art or alter text. Inspect the image yourself and correct its transcript.
3. Add a unique ID, title, relative path, SHA-256, PDF/printed page numbers, transcript
   and factual observations to `assets/catalog.json`. Keep the edition binding.
   If using a different edition, create/review a matching book adapter/catalog
   rather than attaching arbitrary art to the existing book's page indices.
4. Confirm the book GLB contains the matching image at that page. Inspect a rendered
   book shot and source insert. A matching metadata field alone is not sufficient.
5. Mark it verified only after those checks. Run `npm run verify:assets`, tests and
   a real preview. Commit the image and catalog together with a review note.

Saved scripts contain a `sourceLock`; changing the selection means intentionally
reselecting/reviewing the new page. If manually editing JSON, remove the old
`sourceLock` only when making that deliberate new selection, then validate again.
Do not remove it from an existing run to bypass detection of changed assets.

## 10. The best way to get a good episode

Show/read something specific from the comic; give the two readers different wants
or interpretations; let one short reply or reaction land. Use `shot: source` while
reading text the viewer needs to see. Facial cues should underline dialogue that
already makes sense. Avoid depending on a complex prop maneuver to explain the joke.

The repeatable engine can remove production drudgery; it cannot prove a script is
funny or persuasive. Keep good scripts, voice takes and reviewed performance
presets as reusable examples. The card-hand format is recorded in
`dev/V2_CARD_GAME.md`; card selection/animation is not implemented in v1.
