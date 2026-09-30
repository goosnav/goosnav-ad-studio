# GNV-LPV-PAT-001 CONTINUATION DEPARTMENT

A monumental low-poly vignette (GLPV-001) for **The Goosnav Patreon**. It is 9:16 at 1080×1920 (rendered at 540×960 and upscaled exactly 2× with nearest-neighbour), 24 fps, with a 4:5 centre crop (1080×1350).

Adapted from AD 33 "CONTINUATION DEPARTMENT" plus the bible's SUPPORT INPUT skeleton (§37.11, §38F).

**One sentence:** A man ticks YES on a form at a single window in a colossal concrete building, and the whole building lights up.

| Person | Want | Obstacle | Turn | Product |
|---|---|---|---|---|
| A visitor. | For Goosnav to continue. | An enormous institution with one small window and a form. | He ticks YES ($3 a month); the stamp comes down; floor by floor the building powers on. | A real comic page drifts down to him: the Patreon, $3 a month. |

**Monumental wide:** 0–5 s and 14.6–20 s: a 120-metre concrete facade with a grid of windows; one person at a service window at its foot.

## Dialogue transcript

- CLERK: Name?
- VISITOR: Sam.
- CLERK: Purpose?
- VISITOR: I like Goosnav.
- (form: WOULD YOU LIKE GOOSNAV TO CONTINUE? [x] YES - $3 A MONTH [ ] NO)
- CLERK: Very good.

**Cast (voices):** CLERK: `en_GB-jenny_dioco-medium` ("Jenny (Dioco)", commercial use permitted). VISITOR: `en_US-joe-medium` (CC0).

## End card (CTA)

- Goosnav continues.
- The Goosnav Patreon. $3 a month.
- www.patreon.com/goosnav (Times, link blue, underlined)

These are white end cards in Helvetica: one product, one destination (GLPV-001 §40). Prices were checked against www.goosnav.shop on 2026-09-29.

## Files

| File | Use |
|---|---|
| `GNV-LPV-PAT-001_CONTINUATION_DEPARTMENT_Goosnav_9x16.mp4` | master, 1080×1920, H.264, AAC |
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
python3 films/cast_vo.py continuation_department                                  # voices
blender -b --factory-startup -P films/continuation_department/film.py -- --format lpv
python3 films/continuation_department/sound.py && python3 films/continuation_department/type.py
python3 -m studio assemble continuation_department --format lpv --name GNV-LPV-PAT-001_CONTINUATION_DEPARTMENT
```

Render time is about 1 s per frame at 540×960 on the studio machine, so about 10 minutes.
