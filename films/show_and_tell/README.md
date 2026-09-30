# GNV-LPV-MIX-001 SHOW AND TELL

A monumental low-poly vignette for **Goosnav Book 2 and Goosklerf**, from the owner's script (2026-09-30). It is 23.5 s, 9:16 at 1080×1920 (rendered at 540×960 and upscaled exactly 2× nearest-neighbour), with a 4:5 centre crop.

**One sentence:** three men in an infinite desert take turns showing off what they have, and the third one has a bomb.

| Time | Shot |
|---|---|
| 0–3.2 s | An infinite desert with black pyramids on the horizon |
| 3.2–5.4 s | Overhead, far away: three dots |
| 5.4–15.8 s | Closer: the three of them |
| | "I have a Goosklerf trading card deck." He lifts the pack and turns 360°. |
| | "Well, I have a Goosnav book." He lifts Book 2 and spins three and a half times, chaotically. |
| | "Well... I have a bomb." He lifts a cartoon bomb with a lit fuse. |
| 15.8 s | White flash |
| 15.9–21 s | The same overhead shot: an extremely chaotic mushroom cloud (fireball, twisting stem, rolling cap, ground surge, shockwave, secondary blasts, debris). The camera pulls back as it climbs. |
| 21–23.5 s | White end card |

## End card

- **Two of these are for sale.**
- A product still: the generic Book 2 and the Goosklerf box, cards and pack, on white
- Goosnav Book 2. $19.95.
- Goosklerf. From $13.95.
- www.goosnav.shop (Times, link blue, underlined)

## Cast (voices, all cleared for commercial use)

| Character | Voice | Licence |
|---|---|---|
| P1 | `en_US-john-medium` | public domain |
| P2 | `en_US-bryce-medium` | public domain |
| P3 | `en_US-norman-medium` | public domain |

## Assets

Everything was built procedurally: desert, pyramids, actors, bomb and explosion. The products use Goosnav's generic textures. Sound is synthesized. No third-party assets were used.

## Rebuild

```
python3 films/cast_vo.py show_and_tell
blender -b --factory-startup -P films/show_and_tell/film.py -- --format lpv
blender -b --factory-startup -P films/show_and_tell/product_still.py
python3 films/show_and_tell/type.py && python3 films/show_and_tell/sound.py
python3 -m studio assemble show_and_tell --format lpv --name GNV-LPV-MIX-001_SHOW_AND_TELL
```
