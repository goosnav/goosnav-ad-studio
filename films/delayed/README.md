# GNV-LPV-GK-001 DELAYED

A monumental low-poly vignette (GLPV-001) for **Goosklerf**. It is 9:16 at 1080×1920 (rendered at 540×960 and upscaled exactly 2× with nearest-neighbour), 24 fps, with a 4:5 centre crop (1080×1350).

Adapted from AD 39 "AIRPORT", in the bible's terminal and GAME CONSEQUENCE patterns (§23, §37.10).

**One sentence:** Two travellers stuck in a vast empty terminal start a game of Goosklerf and let their plane leave without them.

| Person | Want | Obstacle | Turn | Product |
|---|---|---|---|---|
| Two travellers. | To get home. | The flight is delayed two hours, in an empty hall the size of a hangar. | Boarding is called mid-game: "Finish the turn." | Goosklerf cards and dice on a suitcase; the plane taxis away. |

**Monumental wide:** 0–5.6 s and 18.5–21 s: a 32-metre-high departure hall and its glass wall, with a floodlit airliner outside and two tiny figures at a suitcase.

## Dialogue transcript

- PA: Flight two seventy one is delayed. Another two hours.
- A: You brought it?
- B: Yeah.
- PA: Now boarding. Flight two seventy one.
- A: Finish the turn.

**Cast (voices):** A: `en_US-john-medium` (public domain). B: `en_US-ljspeech-high` (public domain). PA: `en_US-kristin-medium` (public domain), band-limited like a real PA.

## End card (CTA)

- Goosklerf.
- The trading card game. From $13.95.
- www.goosnav.shop (Times, link blue, underlined)

These are white end cards in Helvetica: one product, one destination (GLPV-001 §40). Prices were checked against www.goosnav.shop on 2026-09-29.

## Files

| File | Use |
|---|---|
| `GNV-LPV-GK-001_DELAYED_Goosnav_9x16.mp4` | master, 1080×1920, H.264, AAC |
| `..._9x16_web.mp4` | lighter version for posting |
| `..._4x5.mp4` | 1080×1350 centre crop; all type sits inside the 4:5 band |
| `..._thumb.jpg` | thumbnail and review still |

## Asset and licence manifest

| Asset | Source | Licence |
|---|---|---|
| All geometry, sets, characters and props | built procedurally in Blender by `blender/lowpoly.py` and the film script | Goosnav-owned; no third-party models |
| Product textures (generic Book 2, Goosklerf card and box) | `studio/textures.py`, from the flat Goosklerf logo file on www.goosnav.shop | Goosnav-owned |
| Drawings and comics on paper | real Goosnav scans (2025 drawing sheets, 2026 comic boards) | Goosnav-owned |
| Voices | Piper TTS; see the cast below | cleared for commercial use (`studio/vo.py SAFE_VOICES`) |
| Music and effects | synthesized with numpy (`studio/audio.py`) | Goosnav-owned |
| Fonts | Nimbus Sans (Helvetica metrics) and Liberation Serif (Times metrics) | URW / GPL-with-font-exception and SIL OFL |

No Quaternius, Kenney, Mixamo, Sketchfab or Poly Haven assets were used.

## Rebuild

From `~/Desktop/code/goosnav-ad-studio`:

```
python3 films/cast_vo.py delayed                                  # voices
blender -b --factory-startup -P films/delayed/film.py -- --format lpv
python3 films/delayed/sound.py && python3 films/delayed/type.py
python3 -m studio assemble delayed --format lpv --name GNV-LPV-GK-001_DELAYED
```

Render time is about 1 s per frame at 540×960 on the studio machine, so about 10 minutes.
