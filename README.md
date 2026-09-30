# goosnav-ad-studio

The code and the repeatable process behind Goosnav's animated ads. Each ad is a Blender scene with narration, synthesized sound, type, and a white end card with the addresses, rendered for 4:5 portrait (or any other format).

The code and the method live here. The creative material lives in the business folder. The two are joined by paths in `studio.local.json`:

| What | Where (this machine) | Setting |
|---|---|---|
| Code, process, lessons | this repo, `~/Desktop/code/goosnav-ad-studio` | – |
| Source art and render textures | `~/Desktop/business/AD STUDIO/assets/{sources,textures}` | `assets` |
| Finished films (masters, web, scripts, READMEs) | `~/Desktop/business/AD STUDIO/output/films/<film>/` | `output` |
| Frames, previews, mixes (large, disposable) | `~/goosnav-studio-work/<film>/<format>/` | `work` |
| Piper venv and voices | `~/.cache/goosnav-studio/` | `cache` |

`AD STUDIO/code` and `AD STUDIO/tools` are symlinks back into this repo.

**Read [`PLAYBOOK.md`](PLAYBOOK.md) before making anything.** It holds every lesson learned so far: creative method, owner decisions, Eevee traps, sound, QA, delivery, and running unattended Claude sessions.

## Setup (any machine)

```
git clone <this repo> && cd goosnav-ad-studio
tools/setup.sh                 # checks blender/ffmpeg/rclone, builds the Piper venv, fetches voices,
                               # creates studio.local.json from studio.example.json
$EDITOR studio.local.json      # point assets/output/work at this machine's folders
python3 -m studio config       # verify paths and fonts (Helvetica on macOS, Nimbus Sans on Linux)
python3 -m studio textures     # rebuild textures from assets/sources (optional)
```

Nothing in the code hardcodes a machine path. Every setting can also be set with an environment variable (`STUDIO_ASSETS`, `STUDIO_WORK`, `STUDIO_OUTPUT`, `STUDIO_BLENDER`, ...).

Requirements:

- Blender 4.x (Eevee)
- ffmpeg
- Python 3.10+ with numpy, scipy and pillow
- rclone, for delivery to the Agent Exchange Drive folder

## Make a film

A film is a folder in `films/`. [`films/the_dilemma/`](films/the_dilemma) is the reference.

```
films/<film>/
  SCRIPT.md      written first
  lines.txt      narration, ID|text ("..." = pause)
  film.py        Blender scene: from bstudio import *; build; update(t); run(...)
  sound.py       studio.audio Mix + instruments, hit points from events.json
  type.py        studio.typeset overlays for the chosen format
  edit.json      overlay timings for studio.assemble
  README.md
```

```
python3 -m studio vo       the_dilemma                               # narration -> work/<film>/vo
python3 -m studio preview  the_dilemma --format 4x5 --times 5,20,48  # look at the contact sheet
python3 -m studio preview  the_dilemma --format 4x5 --every 12       # whole film, low res
python3 -m studio render   the_dilemma --format 4x5                  # final frames, GPU lock, resumable
python3 -m studio sound    the_dilemma --format 4x5
python3 -m studio type     the_dilemma --format 4x5
python3 -m studio assemble the_dilemma --format 4x5 --name THE_DILEMMA
python3 -m studio qa       the_dilemma --format 4x5 --name THE_DILEMMA
python3 -m studio deliver  the_dilemma --name THE_DILEMMA            # Drive via rclone, verified
```

Formats are `4x5` (1080×1350, the default), `16x9`, `1x1` and `9x16`.

## Layout

| Path | Contents |
|---|---|
| `studio/` | Plain-Python tools: `config` (paths, fonts, formats), `vo` (Piper narration), `audio` (synth instruments + mix), `typeset` (overlays), `textures` (scan cleanup, rectify, generic products), `assemble`, `qa`, `deliver`, and the CLI in `__main__` |
| `blender/bstudio.py` | Blender layer: scene setup, materials, two-sided paper, object-pool `Sheets`, geometry, camera, and the render loop with formats, motion blur, cut frames and resume |
| `films/` | One folder per film |
| `orchestration/` | Running films as unattended Claude Code sessions: `COMMON_BRIEF.md`, `lanes/*.md` (one creative lane per film), `launch.sh`, `watch.sh` |
| `tools/legacy/` | The earlier AD STUDIO tools (still-ad maker `make_ad.py`, type-and-photo film `make_film.py`, the first Blender reels `gnscenes.py`/`gnfilm.py`/`gnstills.py`/`gnad_apple.py`), now font-agnostic |
| `tools/setup.sh` | Machine setup |

## Films

| Film | Formats | Notes |
|---|---|---|
| `the_dilemma` | 4:5, 16:9 | Paper desert, Book 2 monolith explodes, page tornado, card fortress. Narrator `norman` (re-voiced 2026-09-29). |
| `lights_out` | 4:5, 16:9 | Unmanned 1970s factory. Imported session build (`IMPORTED.md`); re-voiced. |
| `the_longest_turn` | 4:5 | Goosklerf as a thunderstorm war epic on a continent-sized table. |
| `under_the_door` | 4:5 | A bedroom floods with Patreon comics; Book 2 lighthouse. |
| `the_archive` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-B2-001 (Book 2). |
| `continuation_department` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-PAT-001 (Patreon). |
| `delayed` | 9:16 + 4:5 crop | **Low-poly vignette** GNV-LPV-GK-001 (Goosklerf). |
| `the_probe` | – | Session stopped at the script stage (2026-09-29); not produced. |

## Two house styles

1. **Cinematic Eevee films** (the first four): `bstudio` plus a film script. 60–90 s, narrated, 4:5.
2. **Monumental Low-Poly Vignettes** (GLPV-001): `blender/lowpoly.py` builds primitive actors that walk, sit, reach, blink and jaw-flap to the dialogue, animated on 2s. It also holds the house materials, fog, and symbolic products (generic Book 2, Goosklerf box and cards, paper signs and forms). Vignettes run 12–25 s with 9:16 as the master. They render in the `lpv` format (540×960), are upscaled exactly 2× nearest-neighbour by `studio.assemble` (`"upscale"` in `edit.json`), and get a 4:5 centre crop (`"crops"`). Dialogue casts come from `films/cast_vo.py` (`studio.vo.build_cast`, with PA and radio processing). End cards come from `studio.typeset.vignette_card`, kept inside the 4:5 band.
   - Style bible: `AD STUDIO/theory/Goosnav_Monumental_Low_Poly_Vignette_Advertising_Bible.txt`.
   - Script bank: `AD STUDIO/campaigns/Goosnav_54_Video_Ad_Scripts.txt`. The three vignettes adapt ads 13, 33 and 39.

## Related projects

`~/Desktop/code/business-suite/ai-ad-factory` and `ps1-ad-factory` generate ad *plans* (briefs, copy, shot lists) from the Creator Commerce OS catalogue. This repo *produces* the films. A plan from either can become a lane prompt in `orchestration/lanes/`.
