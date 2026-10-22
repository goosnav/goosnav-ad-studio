# Comic Theatre

Experimental, standalone **JSON → performed book conversation → MP4** engine.
Choose real comic pages, write the dialogue, and let ordinary game-engine code
handle faces, listening reactions, camera cuts, book states and measured speech.
Rendering uses no paid API, Codex or Claude call. An optional AI writer is separate.

**Implemented prototype, not a production-approved acting system.** The existing
Ad Studio pipeline is unchanged. This entire directory can be moved into its own
repository; all creative source assets are bundled here, not loaded from sibling
checkouts or archived asset folders.

## Start here

Requires Node.js 22.12+, FFmpeg/ffprobe, and Python 3.10–3.12 for local voices.

```sh
npm ci
npm run setup:browser
python tools/setup_voice.py
node bin/theatre.mjs doctor
npm start
```

Open the local URL printed by the terminal. Select a template and comic thumbnails,
write dialogue in the form or JSON editor, validate, then generate. Setup downloads
dependencies once. Recorded voice takes can replace local synthesis entirely.

**[Step-by-step tutorial, exact JSON examples and source IDs](TUTORIAL.md)**

```sh
node bin/theatre.mjs render examples/parasite.json --preview
node bin/theatre.mjs select page-tour --seed 42 --out my-script.json
node bin/theatre.mjs validate my-script.json
node bin/theatre.mjs render my-script.json
node bin/theatre.mjs status
node bin/theatre.mjs resume RUN_ID
```

Edit the selected skeleton's placeholder dialogue before rendering. `--preview`
produces the entire film at a smaller resolution, not a shortened placeholder.
Normal output is 1080×1350/24 fps. Duration follows measured speech and reactions.

## What is included

- Three templates: one comic/two readers, solo fireside reading, and 2–3-page tour.
- Three reviewed Book Two excerpts, visible in the GUI with IDs and transcripts.
- Exact-image checks: selection, optional writer, inserts and the 3D book agree.
  Catalog hashes are checked against the actual embedded book-page image bytes.
- Optional facial overrides, emotions, gestures, reactions and book-action rails.
- Seeded staging, independent character rigs, seekable frame-by-frame evaluation.
- Blue/rust/olive clothing with white or beady eyes, smooth mouths and emotion blends.
- Seeded close-ups/two-shots/over-shoulders and physical selected-page book reveals.
- Editable product-specific retro end card in both JSON and GUI, with bundled fonts and the existing spinning-book video.
- Narration starts immediately over up to five seconds of readable, reader-oriented book coverage; no automatic silent intro.
- Offline local speech or recordings; measured timing and speech-mouth activity.
- Checkpointed capture, per-run files, a shared production queue, explicit errors,
  and final audio/video verification. Resume refuses stale or damaged checkpoints.
- Optional image-grounded AI JSON producer with explicit endpoint/model settings.

This experiment delivers **local videos only**. It does not upload to Drive,
publish ads, select cards, or run an animation agent. Several requests can queue,
but only one production job runs at a time within this project.

## Development

```sh
npm test
npm run test:browser
npm run verify:assets
```

Linux is exercised; Windows/macOS are designed for but not yet tested. Frame/pose
evaluation is deterministic for the saved inputs; byte-identical GPU rendering
across operating systems is not promised. Natural acting, reliable finger contact,
emotional voice performance, humor and sales effectiveness still need evaluation.

- [Current implementation contract](dev/BUILD_CONTRACT.md)
- [Verification and limitations](dev/VERIFICATION.md)
- [Original detailed design](dev/DESIGN.md) and [tech stack](dev/TECH_STACK.md)
- [Implementation plan](dev/IMPLEMENTATION_PLAN.md)
- [V2 card-hand scenes](dev/V2_CARD_GAME.md)
- [Asset provenance and notices](NOTICES.md)
