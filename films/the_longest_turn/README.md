# THE LONGEST TURN

An 87-second film (4:5 portrait, 1080×1350, 24 fps) for **Goosklerf**, **Goosnav Book 2** and the
**Goosnav Patreon**. Goosklerf leads.

One game of Goosklerf, filmed like the most important battle in human history. The film plays out at
night in a thunderstorm on a wet walnut table the size of a continent, and an American war-and-sports
broadcaster calls every roll. Card fortresses slam up hundreds of feet tall. A booster pack bursts
like a dam. A die falls from the clouds in the first three seconds; later three more come down together like meteors and crater the wood. The rulebook opens like
a cathedral door. One orange die tumbles in slow motion and lands on a five ("Nobody alive had seen a
five like it"), and a fortress falls. Then the storm passes, and the camera rises out of it into an
ordinary dining room on a weeknight. Book 2 lies on the corner of the table, and a Patreon comic slides
in under the door. The film ends on the products, prices, and a white card: *Your roll.*

The working title was THE TABLE. *The Longest Turn* borrows the cadence of *The Longest Day*.

## Files

| File | What it is |
|---|---|
| `SCRIPT.md` | Scenes, timings, narration and sound, written before any code |
| `film.py` | The Blender scene (Eevee). Units are cm; everything is driven by `update(t)` |
| `make_tex.py` | Builds the generic rulebook cover, spine and inner page (PIL) into `<work>/the_longest_turn/tex/` |
| `lines.txt` | Narration (Piper `en_US-joe-medium`) |
| `sound.py` | Storm, score, hits, room tone, and the broadcast voice chain; reads `events.json` |
| `type.py` | Title, war-documentary chyrons, product lines and end card, with soft drop shadows |
| `edit.json` | Overlay timings for `studio.assemble` |

## Rebuild

```
python3 films/the_longest_turn/make_tex.py
python3 -m studio.vo films/the_longest_turn/lines.txt ~/goosnav-studio-work/the_longest_turn/vo \
        --voice en_US-joe-medium --slow 0.97 --length 1.0 --pause 0.45 --reverb 0.0
python3 -m studio preview the_longest_turn --format 4x5 --every 12
python3 -m studio render the_longest_turn --format 4x5
python3 -m studio sound the_longest_turn --format 4x5
python3 -m studio type the_longest_turn --format 4x5
python3 -m studio assemble the_longest_turn --format 4x5 --name THE_LONGEST_TURN
python3 -m studio qa the_longest_turn --format 4x5 --name THE_LONGEST_TURN
python3 -m studio deliver the_longest_turn --name THE_LONGEST_TURN
```

`studio vo` is called through `studio.vo` directly because the CLI does not pass `--slow`/`--reverb`. The
reverb is off because `sound.py` builds the voice from the dry takes: high-pass 140 Hz, presence lift,
4:1 compression, a little drive, then a 105 ms and 235 ms stadium slapback plus a short tail.

## Facts and their sources

Everything was checked against `https://www.goosnav.shop/products.json?limit=250` on 2026-09-28:

- Goosnav Book Two (Hardcover): $19.95. On screen it is "Goosnav Book 2".
- Goosklerf: The Trading Card Game. Booster Pack (12 Cards) $13.95; Starter Kit $29.95; Game Kit
  $49.95; Treasure Box $89.95. On screen: "Packs $13.95. Kits $29.95 to $89.95." Narration: "Twelve
  cards to a pack."
- Goosnav Patreon: $3.00, at www.patreon.com/goosnav.
- The rules as stated (dice decide combat, items, fortresses as shelter, win by taking the fortresses or
  the enemy) come from the brief. The clock times (21:14, 21:20, 21:31) are part of the fiction, not
  claims about the product.

## Real versus built

- **Real Goosnav art:** one comic page, `comic_01.png` (the table cartoon, "Cheer up buddy..."), on the
  Patreon dispatch that slides under the door. Nothing was drawn, redrawn or generated.
- **Generic products (owner rule):** cards use `gen_card.png` (alpha clip). Packs use `gen_pack.png`.
  Book 2 uses `gen_book_front/back/spine.png` on a `#0033A0` hardcover. Dice use the `die_*` textures.
  The rulebook is new and generic: a purple `#330072` cover with the crisp `GOOSKLERF.jpg` logo and
  Helvetica "Goosklerf Rulebook", plus an inner page in Helvetica. No photo textures are used.
- **Exposure:** the storm is lit as a night film: `view_settings.exposure` +1.25 during the storm (falling to 0 at the reveal), a cool moon key with shadows, a fill, and lightning suns in the three Goosklerf colours.
- **Built:** the table, room, storm sky, rain, lightning bolts, meteors, craters, splinters, spray and
  all the light. All sound is synthesised (`studio.audio` plus the voice chain); there is no library audio.

## Technical notes

- **Scale:** 1 unit = 1 cm. During the battle the camera sits 0.4–3 cm above the table with wide lenses
  and no depth of field, so everything reads as enormous. For the reveal it rises to human height and
  depth of field (f/2.2) switches on, so the same table reads as small.
- **Slow motion:** `ts(t)` is a stretched clock (0.08× from 45.3 s to 50.0 s). The hero die, rain,
  droplets and lightning decay all run on it, so the rain streaks shorten into drops and the strobes
  linger.
- **The room** is parented to one empty that sits at a far parking spot until 58.0 s, when the camera is
  looking straight down at the die. It is moved by transform only, following the playbook's rule.
- **Screen-space reflections** are on for the final render only (previews skip them for speed). They make
  the wet table mirror the cards and the lightning.
- **Voice ratio:** `studio.audio.Mix.report_voice` measures a fixed 2.5 s window from each line's start,
  which also counts the big hits placed deliberately in the pauses (the pack tear, the dice impacts).
  `sound.py` also prints the ratio measured only while the voice is speaking. Every line is ≥ 9 dB by
  that measure.

## Proposed studio changes

1. `studio vo` should pass through `--slow/--length/--pause/--reverb` (argparse `REMAINDER` after the
   film name does not catch them).
2. `Mix.report_voice` could measure only voice-active samples (the helper is in `sound.py`).
3. `studio render` launched with `setsid nohup … &` from an agent's Bash tool was killed when the tool
   call returned (after frame 1). Launching it with the tool's own background mode worked. Worth a line
   in PLAYBOOK §3, "Process hygiene".
4. `studio preview` builds its contact sheet from every PNG in `preview/`, including stills from earlier
   runs. Clearing the folder first (or a `--clean` flag) avoids mixed sheets.
5. **Cut frames render the previous shot.** In `bstudio.run()`, a frame listed in `--cuts` skips
   `scene.frame_set(f)`. With `--mblur` the `frame_change_pre` handler is still registered, and the
   render re-evaluates it at the stale `scene.frame_current` (the previous frame). So every cut frame
   shows the last frame of the outgoing shot, and each cut lands one frame late. The next frame is
   clean, because its 0.25 shutter doesn't reach back across the cut, so this is harmless here. Fix:
   set `scene.frame_current = f` (or call `frame_set`) before rendering cut frames, with
   `use_motion_blur = False`.
