# Book Two reaction shorts (2026-10-22)

Quick, low-sample follow-ups to GET YOUR OWN and DRAW YOUR OWN on the same reading desk:
the reader reads a real printed page of Book Two (v2, actual interior) aloud, and the
friend, who can't see it, reacts. Each short is five lines; `layout.py` times its shots from
the measured takes with the beat pattern that passes `harness/scene_check.py`.

| Short | Printed page | Lines | Card |
|---|---|---|---|
| `brain_surgery` | comic 60: BARGAIN BIN BRAIN SURGERY & BUTCHER BOT, SLEEP BOT, JAR FOR THE BRAIN | "Bargain bin brain surgery." / "How bargain?" / "Butcher bot. And a jar for the brain." / "Can I go first?" / *slam* "Get in line." | Get in line for Book Two |
| `littlest_librarian` | comic 65: THE LITTLEST LIBRARIAN | "The littlest librarian." / "Where?" / "She's smaller than the books." / "Is she here?" / *a tiny "Shh!", the book eased shut* "Probably." | Read Book Two quietly |
| `wissors` | comic 65: WISSORS | "Wissors." / "Scissors?" / "Wissors. They're made of worms." / "Can I borrow them?" / *slam* "Get your own." | Get your own copy |

Build one (WORK = `~/goosnav-studio-work/shorts/SLUG`; the blocking scene is DRAW YOUR OWN's):

```sh
AUDIO_PY=... ; F=films/reaction_shorts/SLUG; W=~/goosnav-studio-work/shorts/SLUG
$AUDIO_PY -m harness.voice $F/voices.json $W/voice
python3 films/reaction_shorts/layout.py SLUG $W
python3 films/draw_your_own/sound.py $F/cut.json $W
blender -b ~/goosnav-studio-work/draw_your_own/blocking.blend --python films/draw_your_own/animate.py -- $F/cut.json $W $W/scene.blend
blender -b $W/scene.blend --python films/draw_your_own/render.py -- $F/cut.json $W/frames --samples 8
python3 films/draw_your_own/finish.py $F/cut.json $W OUTPUT_DIR
```

A new short is a new `SHORTS` entry in `layout.py` (page leaf, insert side, card title)
plus a five-line `voices.json` with the ids r1, p1, r2, p2, r3.
