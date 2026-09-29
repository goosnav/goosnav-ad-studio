# LIGHTS OUT

A 90-second film for Goosnav Book 2, Goosklerf and the Goosnav Patreon. It is a Blender scene, not motion graphics.

It is shot like a 1970s British industrial documentary. A colossal factory makes Goosnav products with nobody in it. Automation engineers call a factory like that a *lights-out factory*: nobody needs to see, so nobody turns the lights on. This one keeps them on anyway.

The film opens as the sodium lamps strike, one bank at a time, down a hall of concrete and haze. A reel of paper as tall as a building feeds a four-post press. Ink falls like rain onto the inking roller, and the press stamps the real 2025 drawing sheets onto the page on every other beat. The pages are gathered, and an absurdly large casing press slams a blue board shut: Goosnav Book 2, which then rides a conveyor into the haze. On the Goosklerf line, dice come out of a kiln glowing and cool into teal, orange and purple before they hit the quench tank. A machine fans the cards, and heated jaws seal the packs. A brass pneumatic tube sends this month's comic up through the roof: "the standing order". At the far end of the hall, where the lamps never quite warmed up, one robot arm is building another, and the one it builds turns and starts on the next. The film ends at dawn, on a loading dock where Book 2, a Goosklerf pack and kit, and a Patreon comic sit on a pallet. Then the lights go out.

The narrator is calm, proud and British. He works out that there are no staff, and he never panics. He just gets quieter.

The whole factory runs at 96 BPM (15 frames a beat), so every slam, crimp and shuffle lands on the beat of the score.

## Files

| File | Use |
|---|---|
| `LIGHTS_OUT_Goosnav_1080p.mp4` | Master. 1920×1080, 24 fps, H.264 CRF 17, AAC 320k. Use it for the portfolio and any re-edit. |
| `LIGHTS_OUT_Goosnav_1080p_web.mp4` | The same film at about 35 MB, for uploads and phones. |
| `LIGHTS_OUT_Goosnav.srt` | Captions of the narration, for autoplay-muted feeds. |
| `LIGHTS_OUT_poster.jpg` | Poster frame: the paper reel in the hall. |
| `LIGHTS_OUT_still_*.jpg` | Stills: the press, the drawings, Book 2, the card shuffler, and the dock with prices. |
| `LIGHTS_OUT_Goosnav_4x5.mp4` | The 4:5 portrait version, 1080×1350, for feeds. Every shot was re-framed and re-rendered for portrait, not cropped from the 16:9. |
| `LIGHTS_OUT_Goosnav_4x5_web.mp4` | The 4:5 version at about 35 MB. |
| `SCRIPT.md` | The script, written before the build. |

## Facts stated on screen and in the narration

All of these come from www.goosnav.shop (`products.json`), checked on 2026-09-26:

- Goosnav Book 2 (listed as "Goosnav Book Two (Hardcover)"): $19.95, hardcover. Its pages are the 2025 drawings.
- Goosklerf, a trading card game played with dice: a booster pack of 12 cards is $13.95, and kits are $29.95, $49.95 and $89.95. The film says "Packs $13.95. Kits from $29.95."
- The Goosnav Patreon: $3 a month, with new art added monthly ("once a month… the standing order").
- Both addresses carry `www.`: www.goosnav.shop and www.patreon.com/goosnav.

The factory, its forty tonnes of paper, its staff (there are none) and its robots are fiction. The film states no comic counts, sales figures or awards.

## What is real and what is built

- **Real artwork, unaltered:** the six 2025 drawing sheets printed by the press (Foot Oiling Machine, Automated Gnome Armorer, Shoe Multipliers, Toe Truck, Emotion Nullifier, Self-Filling Coffee Mug), and two September 2026 comics from the full-resolution scans. "Cheer up buddy" is in the pneumatic carrier, and the "Sleep factory" strip is on the pallet. The comics are only cropped to their panel borders. Nothing is drawn, redrawn, extended or generated.
- **Generic products, so nothing is cut off, skewed or blurry:**
  - Book 2 is a plain Book Two blue (`#0033A0`) hardcover with white Helvetica "Goosnav / Book 2".
  - The Goosklerf cards, pack and kit box carry the flat Goosklerf logo file with Helvetica type. The kit box art is `prep_tex.py`.
  - The dice use the Goosklerf colours.
  - No product photographs are used.
- **Built in Blender:** the hall, machines, press, reel, kiln, tube, robots, dock, light, haze, ink, steam and sparks.
- **Sound:** the narrator is a synthetic voice (Piper TTS, `en_GB-alan-medium`) put through a 1970s broadcast chain: a band-limit, tape saturation, wow, and a small booth. All music and effects were synthesized in numpy, so the soundtrack is rights-clean. The score is a small Radiophonic-style cue built on the factory's rhythm, and it drops out at the reveal.

## Known departures from the brand bible

These were deliberate, on the owner's instruction not to be constrained by the ad doctrine:

- colour and motion around the work
- a narrator
- three products in one piece

The comics themselves stay black ink on white paper.

## Rebuilding

The project is at `/home/goosnav/goosnav-sessions/B_how_it_is_made/` on the Dell:

| Step | Command | Output |
|---|---|---|
| Type | `python3 overlays.py` | `ov/` |
| Kit box art | `python3 prep_tex.py` | kit box textures |
| Narration | `python3 vo/make_vo.py` | narration WAVs |
| Captions | `python3 make_srt.py` | `.srt` |
| Sound and mix | `python3 sound.py` | `mix.wav` |
| Picture | `./render.sh` (runs `film.py`) | `frames/` |
| Grade | `python3 grade.py frames graded 3` | `graded/` |
| Final encode | `./assemble.sh` | `deliver/` |

The scene code is split across four files:

- `film.py`: the scene
- `hall.py`: the hall
- `sets.py` and `sets2.py`: the stations
- `timeline.py`: shots and cameras

All timings live in `timing.py`, which both the picture and the sound read.

For a preview, run `blender -b --factory-startup -P film.py -- --preview --step 12 --out prev12`.

The final render is Eevee at 1920×1080, 12 samples, with motion blur. It takes about 3 hours on this machine's Intel GPU.

### 4:5 portrait

Run `blender -b --factory-startup -P film.py -- --portrait` (in `render45.sh`), then:

1. `LO_PORTRAIT=1 python3 grade.py frames45 graded45`
2. `python3 overlays45.py`
3. `./assemble45.sh`

In portrait, Blender fits the sensor to the height, so each shot carries its own lens scale and framing nudge. They are in `PORT` in `timeline.py`. All type sits between 12% and 88% of the frame height.

Every Blender run on this machine is wrapped in `flock /tmp/goosnav-render.lock` so renders never share the GPU.
