# UNDER THE DOOR

A Goosnav film, 4:5 portrait (1080×1350), 58.5 s, Blender 4.0 Eevee. Working title "3:14 A.M."

A bedroom at 3:14 a.m. A comic slides under the door, then another, then the tide. The room floods with paper and the camera sinks into a slow, dark sea of drifting pages whose ink glows faintly. Far off, Goosnav Book 2 stands on a tower of paper like a lighthouse, turning an amber beam through the water. The bed floats overhead like a boat, the dice bob like buoys, and Goosklerf cards swim in schools. At dawn the room is dry again, with one comic left by the door. Then the prices and the white card.

It advertises the **Goosnav Patreon** (it leads), **Goosnav Book 2** and **Goosklerf**.

## Files

| File | What |
|---|---|
| `SCRIPT.md` | Scenes, timings, narration, sound (written first) |
| `lines.txt` | Narration (`ID|text`, `...` = pause) |
| `vo.py` | Narration build: Piper `en_GB-jenny_dioco-medium`, slow 0.97, length 1.18, a short soft room (1.1 s IR), light reverb |
| `film.py` | The Blender scene, `update(t)`, events.json, cut frames |
| `sound.py` | Synth mix: music box, underwater pad, paper hush, clock, foghorn, knocks; underwater muffle; voice duck |
| `type.py` | Price lines (the Patreon first) and the white end card |
| `edit.json` | Overlay timings for `studio.assemble` |

## Rebuild

```
python3 films/under_the_door/vo.py
python3 -m studio preview  under_the_door --format 4x5 --every 12
python3 -m studio render   under_the_door --format 4x5
python3 -m studio sound    under_the_door --format 4x5
python3 -m studio type     under_the_door --format 4x5
python3 -m studio assemble under_the_door --format 4x5 --name UNDER_THE_DOOR
python3 -m studio qa       under_the_door --format 4x5 --name UNDER_THE_DOOR
python3 -m studio deliver  under_the_door --name UNDER_THE_DOOR
```

## Facts on screen and their sources

- The Patreon, $3 a month, full archive, new art monthly: owner brief (COMMON_BRIEF.md).
- Goosnav Book 2, $19.95: `www.goosnav.shop/products.json`, "Goosnav Book Two (Hardcover)" 19.95, checked 2026-09-29. "Someone signed it" refers to the signed edition (owner brief).
- Goosklerf, from $13.95: products.json, "Goosklerf: The Trading Card Game", Booster Pack (12 Cards) 13.95, checked 2026-09-29.
- Addresses: `www.patreon.com/goosnav`, `www.goosnav.shop`.
- No counts, sales or awards are stated.

## Real versus built

- **Real art:** the 2026 comic boards `comic_00`–`comic_06` (scans cropped and levelled by `studio.textures`). The opener's comic is `comic_01` ("Cheer up buddy, your wife probably just hasn't been born yet"), and the one left by the door at dawn is `comic_03` ("Sleeping wastes so much time"). Underwater, a render-time emission follows the darkness of the scanned ink, so the ink glows. The drawings themselves are not altered, redrawn or extended.
- **Generic products:** Book 2 is the Book Two blue `#0033A0` hardcover (`gen_book_front/back/spine.png`), used on the desk and at 12× scale as the lighthouse. The Goosklerf pack is `gen_pack.png`, the card is `gen_card.png` (alpha clip) and the dice use `die_*` faces. No product photographs.
- **Built:** the room, door, gap light, lamp, the clock (a generated prop texture reading "3:14"), bed, desk, window sky, water volume, paper tower, beams, and all sound.

## Notes

- Portrait lenses are authored directly (`P(lens)` divides by `LENS_SCALE`, so `aim_camera` restores them).
- Underwater uses an Eevee world volume (density 0.045) only between the cuts. The sea suns have `volume_factor` 0 / 0.05, otherwise their in-scatter turns the water grey under AgX.
- The lampshade cone's normals face inward. Its emissive "inside" is keyed on Backfacing accordingly.
- Render cost is about 4 s per frame at 20 samples on the studio iGPU.

## Proposed studio changes

- `studio preview --times` doesn't clear old stills from `preview/`, so the contact sheet mixes runs. Clear the folder (or use a per-run subfolder).
- `Mix.report_voice()` uses a fixed 2.5 s window, which under-reports very short lines (a 1 s whisper followed by a music note reads as 1.5 dB). Measure over the voice clip's own length.
- `studio vo` only passes `--voice`. Exposing the room size and decay (as `vo.py` here does via `vo.build`) would allow intimate narrators without a film-side script.
