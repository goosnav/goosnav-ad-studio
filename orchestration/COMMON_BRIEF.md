# Brief: a Goosnav film, built with goosnav-ad-studio

You are an independent Claude Code session running unattended. Nobody will answer questions, so make every decision yourself and write down why. The account has usage limits, so work efficiently. If you are cut off mid-task, the orchestrator will resume you with your context.

## Scope (owner, 2026-09-29): "Let's not polish a cannonball. We just need some usable social media content."

- Aim for **45–60 s**. Keep the idea strong and simple, with fewer set pieces done well.
- Do one full-length preview pass (the gate below) and **fix only real problems**: unreadable exposure, products cut off or wrong, broken motion, clipping audio. Don't chase perfection.
- Move quickly. Script, build, one preview pass, final render, assemble, QA, deliver.

## The job

Make one world-class animated film, good enough for a portfolio, as a **Blender scene**: a real 3D world with camera, light and physical motion, not motion graphics. It advertises:

1. **Goosnav Book 2**: a hardcover comic collection (the shop lists it as "Goosnav Book Two"). $19.95, signed, 2025 drawings.
2. **Goosklerf**: a trading card game by Goosnav. Players fight with dice and items, shelter in fortresses, and win by capturing fortresses or eliminating enemies. Booster pack (12 cards) $13.95; kits $29.95 / $49.95 / $89.95.
3. **The Goosnav Patreon**: $3 a month, a full digital archive with new art added monthly.

The addresses are always **www.goosnav.shop** and **www.patreon.com/goosnav**, with the `www.`. Never state facts you can't verify (comic counts, sales, awards). The live catalogue is at `https://www.goosnav.shop/products.json`.

The owner said: "Think *Xavier: Renegade Angel*. Don't think about constraints, just make a good script." After the first films he said "really incredible animations". Keep that standard: strange, funny, and executed far more seriously than the premise deserves.

**Format: 4:5 portrait, 1080×1350.** Compose for portrait from the first storyboard. Don't make a landscape film and crop it.

## Existing films. Watch them and do not repeat them

Finished films are in `<output>/` (run `python3 -m studio config` to see where `<output>` is). Extract frames with `python3 -m studio.qa video FILM.mp4 sheet.jpg` and look at them.

- **THE DILEMMA**: a pastel paper-dune desert with three suns and a giant blue Book 2 monolith. The book explodes into a page tornado, cards build a fortress, comics fall from a slot in the sky, and everything rewinds. Cosmic-prophecy narrator.
- **LIGHTS OUT**: an unmanned, sodium-lit 1970s factory that makes the products. A BBC documentary narrator slowly realises the factory is building itself.

Your lane (world, palette, narrator register, structure, set pieces) is in your own prompt below. It must feel like a different film.

## Rules that are not negotiable

- **Real art only for drawings and comics.** Scans may be cropped, rectified, levelled and upscaled. Never draw, redraw, extend or AI-generate Goosnav artwork. Everything else in the 3D world (sets, weather, light, props, dice) is yours to build.
- **Products are rendered generic.** The owner rejected a book textured from a cropped photo: "If you can't get a great render of a book or item (ie stuff is cut off) then you just render a generic version (ie helvetica saying Goosnav book 2 on a generic book)." So:
  - Book 2 is always the generic Book Two blue (`#0033A0`) hardcover with white Helvetica "Goosnav / Book 2", using `gen_book_front/back/spine.png`.
  - Goosklerf uses `gen_card.png` (the flat logo file on a teal card; its corners are alpha, so use alpha clip) and `gen_pack.png`.
  - **Never** use `book_front/back/spine.png`, `card_back.png`, `card_face.png`, `pack_front.png`, or any product photo as a texture.
  - Anything else you can't render perfectly gets a plain generic version with Helvetica type.
- On screen the book is **"Goosnav Book 2"**. Prices are stated like measurements. There are no fake testimonials and no urgency.

## The studio: use it. It is the house pipeline

The repo is `goosnav-ad-studio`; its path is in your prompt. Read `README.md` and `PLAYBOOK.md` there first. PLAYBOOK holds every lesson learned so far and will save you hours. Then read the reference film `films/the_dilemma/` (film.py, sound.py, type.py, edit.json, lines.txt).

Build your film as **`films/<your_film_id>/`** inside the repo, with the same shape:

| File | What it is |
|---|---|
| `SCRIPT.md` | Written FIRST, before any code: scenes, timings, narration, sound |
| `film.py` | The Blender scene. `from bstudio import *`; `setup_scene()`, `make_camera()`, `aim_camera()`, `Sheets` object pools, and `run(update, DUR, FPS, out=..., events=...)`. Author lenses for 16:9; `aim_camera` scales them for the format. Use `PORTRAIT` to tune shots. |
| `lines.txt` | Narration, `ID|text`; `...` makes a pause |
| `sound.py` | Uses `studio.audio` (`Mix`, instruments, `duck`, `report_voice`, `master`) |
| `type.py` | Uses `studio.typeset` (`lines_overlay`, `end_card`, `title_card`) |
| `edit.json` | Overlay timings for `studio.assemble` |
| `README.md` | What it is, files, facts and their sources, real versus built, how to rebuild |

Commands, run from the repo root:

```
python3 -m studio config
python3 -m studio vo <film> --voice en_GB-alan-medium        # other voices: see PLAYBOOK
python3 -m studio preview <film> --format 4x5 --times 3,10,25,40     # or --every 12 for the whole film
python3 -m studio render <film> --format 4x5                  # final frames; takes the GPU lock itself
python3 -m studio sound <film> --format 4x5
python3 -m studio type <film> --format 4x5
python3 -m studio assemble <film> --format 4x5 --name <TITLE>
python3 -m studio qa <film> --format 4x5 --name <TITLE>
python3 -m studio deliver <film> --name <TITLE>
```

- Do **not** edit `studio/`, `blender/` or other films. If you need a helper, put it in your film folder, and list any proposed core improvements in your README under "Proposed studio changes".
- Do not run git commands. The orchestrator commits.

## Machine realities (details in PLAYBOOK.md)

- The GPU is weak and shared: Blender 4.0 Eevee on an Intel iGPU, about 4–6 s per 4:5 frame at 20 samples.
- **One final render at a time.** `studio render` waits on the machine-wide lock automatically. Previews do not take the lock.
- Launch the final render in the background with `setsid nohup python3 -m studio render <film> --format 4x5 > render.out 2>&1 &`. Keep working while it runs (sound, type, README), and poll with foreground `sleep` of at most 9 minutes. Don't end your session until the film is delivered and verified.
- Budget: the final render should take at most about 2 hours. Length 45–60 s at 24 fps.

## Status file (required)

Keep `STATUS.md` in your session folder (path in your prompt) current. The orchestrator uses it to schedule the next film.

```
PHASE: SCRIPT | BUILD | LOOKDEV | PREVIEW | RENDERING | ASSEMBLY | DELIVERED | FAILED
PROGRESS: <integer 0-100>      (during RENDERING: frames done / total * 100)
UPDATED: <date -Is>
NOTE: <one line>
```

## Preview gate (hard rule)

A previous session started its 3-hour final render after 6 preview stills. The orchestrator stopped it: the film was underexposed (the table read as black water) and the opening was a static hold. **Before the final render you must:**

1. Render the whole film with `python3 -m studio preview <film> --format 4x5 --every 12`.
2. Open every contact sheet with Read, and write down in `<session>/PREVIEW_NOTES.md` what you checked and what you fixed:
   - exposure: the key subject reads and the darks are legible
   - every shot moves
   - the opening grabs within 3 s
   - products are fully in frame and generic
   - hero drawings are readable
3. Repeat until nothing on the sheet embarrasses you.
4. Only then set `PHASE: RENDERING`.

The orchestrator reviews your first rendered frames and will stop a render that isn't at standard.

## Definition of done

1. `SCRIPT.md` exists, is good, and the film follows it or improves on it.
2. Before the final render: a full-length low-res preview at `--every 12`, contact sheets reviewed with the Read tool, and problems fixed. Check cut frames and anything that pops, clips or leaves frame.
3. `<output>/<film>/` contains `<TITLE>_Goosnav_4x5.mp4` (the master), `_4x5_web.mp4` (about 40 MB or less), `.srt`, a poster JPG, `SCRIPT.md` and `README.md`.
4. QA passed: the stills sheet has been reviewed, loudness is about −14 LUFS, voice sits ≥ 8 dB over effects, every URL carries `www.`, and prices match the shop.
5. `python3 -m studio deliver` succeeded. It verifies on Drive itself.
6. `STATUS.md` says `PHASE: DELIVERED`, with the Drive folder in NOTE.
