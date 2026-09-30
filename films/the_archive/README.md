# GNV-LPV-B2-001 THE ARCHIVE

A monumental low-poly vignette (GLPV-001) for **Goosnav Book 2**. It is 9:16 at 1080×1920 (rendered at 540×960 and upscaled exactly 2× with nearest-neighbour), 24 fps, with a 4:5 centre crop (1080×1350).

Adapted from AD 13 "THE ARCHIVE" (54 Video Ad Scripts), in the Giant Archive template (GLPV-001 §23, §38A).

**One sentence:** An archivist logging obsolete media at the foot of an endless archive puts down Goosnav Book 2, the one thing that needs nothing but eyes.

| Person | Want | Obstacle | Turn | Product |
|---|---|---|---|---|
| An archivist. | To log every item on his desk. | Every medium needs a machine to read it. | "What does that one need?" "Eyes." | Book 2 is the one object that still works; he opens it and reads real drawings. |

**Monumental wide:** 0–5 s: a 62-metre archive aisle receding into haze, one desk and one lamp at its foot.

## Dialogue transcript

- ARCHIVIST: Floppy disk. Needs a drive.
- ARCHIVIST: Compact disc. Needs a drive.
- ARCHIVIST: Phone. Needs a charger.
- ASSISTANT: What does that one need?
- ARCHIVIST: Eyes.

**Cast (voices):** ARCHIVIST: `en_US-norman-medium` (public domain). ASSISTANT, far down the aisle on a ladder: `en_GB-cori-medium` (public domain).

## End card (CTA)

- Paper remains compatible.
- Goosnav Book 2. $19.95.
- www.goosnav.shop (Times, link blue, underlined)

These are white end cards in Helvetica: one product, one destination (GLPV-001 §40). Prices were checked against www.goosnav.shop on 2026-09-29.

## Files

| File | Use |
|---|---|
| `GNV-LPV-B2-001_THE_ARCHIVE_Goosnav_9x16.mp4` | master, 1080×1920, H.264, AAC |
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
python3 films/cast_vo.py the_archive                                  # voices
blender -b --factory-startup -P films/the_archive/film.py -- --format lpv
python3 films/the_archive/sound.py && python3 films/the_archive/type.py
python3 -m studio assemble the_archive --format lpv --name GNV-LPV-B2-001_THE_ARCHIVE
```

Render time is about 1 s per frame at 540×960 on the studio machine, so about 10 minutes.
