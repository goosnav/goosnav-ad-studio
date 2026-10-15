# PLAYBOOK: how Goosnav films get made

These lessons were paid for in render hours on the first films: THE DILEMMA, LIGHTS OUT, and the sessions that followed. Read this before building anything. For the business-wide learning rule, see [`../../business/README.md`](../../business/README.md). Keep reusable animation lessons here and one-off notes in the film's README.

---

## 1. Creative method

1. **Script first, code second.** Write `SCRIPT.md` with scenes, timings, narration and sound before any Blender code. The owner's brief was "Think *Xavier: Renegade Angel*. Don't think about constraints, just make a good script." The films that worked had a real structure: set-up, escalation, detonation, reversal, product, prices, address.
2. **The joke is total sincerity.** A narrator who is completely sure of himself (the cosmic prophet, the BBC documentarian, the war broadcaster) treating a comic book and a card game as the most important objects in the universe. Never wink.
3. **Execute more seriously than the premise deserves.** Real light, real camera moves, motion blur, a real mix. Cheap-looking CG kills the joke.
4. **Each film gets its own world.** The palette, narrator register and set pieces must not overlap with earlier films. Watch the existing films before writing.
5. **Name the real drawings on screen.** When the narration names a drawing ("a machine for oiling feet"), a hero page with that drawing passes the lens during that sentence. Time it from `gaps.json` (sentence gaps in the dry VO), not by guessing.
6. **The ending is fixed.** Hero shot with the product lines and prices (Helvetica Bold), then a white card with the addresses as old web links (Times, `#0000EE`, underlined, bottom left). Always write `www.goosnav.shop` and `www.patreon.com/goosnav` with the `www.`.
7. **Length:** long-form films may run 60–90 s; short-form ads follow their brief (7–20 s for the current short-ad work). **Format: 4:5 portrait (1080×1350) is the default** (owner, 2026-09-28). Make alternates by re-rendering with `--format`, never by cropping.

## 2. Owner decisions (binding)

| Date | Decision |
|---|---|
| 2026-09-25 | Ads may break the brand bible's no-motion, no-colour rules ("don't be constrained by the business folder"). Real art stays real: never draw, redraw, extend or AI-generate Goosnav drawings. |
| 2026-09-26 (superseded 2026-09-29) | ~~Products are generic; do not use product photographs as textures.~~ **Correction:** use verified, current product artwork in ads when it is legible and unaltered (including the supplied Book Two and Goosklerf textures). Keep comic drawings real and unchanged. If the correct product art is missing or unusable, use a clearly identified proxy for a draft and replace it before delivery. |
| 2026-09-26 | On screen the book is "Goosnav Book 2". |
| 2026-09-28 | All films in **4:5 portrait**; existing films re-rendered in 4:5. |

Facts that may be stated (check `https://www.goosnav.shop/products.json` before each film):

- Book 2: $29.95 on the live shop as of 2026-10-08 (was $19.95), hardcover, signed, 2025 drawings. Always re-check products.json.
- Goosklerf (live 2026-10-08): booster $14.95 (12 cards); kits $34.95 / $59.95 / $99.95; game/rule book $19.95. Dice-based combat, fortresses; win by capturing fortresses or eliminating enemies.
- Patreon: $3/month entry price per the 2026-09-29 supplied script bank; verify the live offer before publishing. Do not promise particular benefits or posting frequency unless the current page states them.
- Never state comic counts, sales or awards.

## 3. Blender / Eevee on the studio machine

**Engine.** The Ubuntu build of Blender 4.0 has no OpenImageDenoise, so Cycles can't be denoised. Use Eevee (legacy). On the Intel HD 530 a frame takes about 4–6 s at 20 TAA samples (1080×1350) and about 5–9 s at 1920×1080. A 90 s film is roughly 2.5–3.5 h.

**One render at a time.** Two Blender processes in parallel are *slower* in total than one (0.18 vs 0.19 frames/s). `python3 -m studio render` takes the machine-wide lock (`render_lock`). Previews skip the lock and are cheap (<1 s/frame at half size, 6 samples).

**Animate with object transforms only.** This is the biggest trap. Editing mesh vertices between renders (`foreach_set('co')`, swapping `ob.data` for a copy, even with `update_tag` and `frame_set`) makes Eevee render stale or invisible geometry in batch mode. The one-off test render looks fine, which makes it worse. Use object pools: `bstudio.Sheets` gives every sheet (page, card, comic) its own object sharing a few pre-curled meshes, moved by `matrix_world`. Hundreds of objects are fine.

**Scene pattern.** One file builds the scene and exposes `update(t) -> black`. Drive every object from `t` with closed-form motion: easing, exponential settle, ballistic hops, wrapped orbits. Then any frame can be rendered alone, in any order, and resumed.

**Motion blur.** `--mblur` registers `update` as a `frame_change_pre` handler (with `frame_subframe`), sets shutter 0.25 and steps 3. It costs nothing extra at the same sample count.

- Motion blur smears across hard cuts, so list the cut frames in the film's `CUT_FRAMES`; `run()` renders them without blur. The cut frames are `round(T_cut * fps)` for every discontinuity, including teleports of objects between shots.
- A shutter of 0.4–0.5 double-images camera-locked text or pages. Keep it at 0.25.

**Portrait.** `sensor_fit AUTO` fits the 36 mm sensor to the *larger* dimension, so in 4:5 the horizontal field narrows. `aim_camera()` multiplies lenses by the format's `lens_scale` (0.8 for 4:5), which restores the 16:9 horizontal framing and adds headroom. Tighten individual shots with `PORTRAIT` (for example, THE DILEMMA's opener uses ×1.3 in portrait).

**Materials.**

- Two-sided paper: mix the front and back images by `Backfacing`, with the back UVs mirrored. Add translucency 0.12–0.18 so backlit pages glow, plus a small emission (0.2) so ink-on-paper stays white under coloured light.
- Cards with rounded corners: RGBA texture, transparent mix, `blend_method = shadow_method = 'CLIP'`.
- Principled input names in 4.0: `'Specular IOR Level'`, `'Coat Weight'`, `'Emission Color'`, `'Emission Strength'`. `ShaderNodeMix` RGBA uses inputs 6 and 7 and output 2.
- Colour management: AgX with "Medium High Contrast". A pastel sky plus AgX reads as a dream. Push saturation in the sky ramp, not in post.

**Lighting.**

- A warm key sun with cascaded shadows: `shadow_cascade_max_distance` about 90, `cascade_size` 4096. Larger distances make blotchy ground shadows.
- Coloured fill suns: set **`use_shadow = False`**. Their shadows only add blotches.
- Flashes: a point light of about 6e5 W for a moment plus a short world-strength bump. At 4e6 W the frame whites out.
- A light leaking from a book: at most 160 block emission plus a 9e3 W point light *behind* the cover plane. In front of it, the leak washes out the cover.

**Terrain.** Displace a grid with an analytic height function you can also evaluate in Python, so objects can sit on the ground. Flatten plateaus where the action is, and keep them wide enough that orbiting cameras never go under a dune. That happened twice: check every camera path in preview.

**Previews.** `python3 -m studio preview FILM --format 4x5 --times 3,9,16,...` for key moments, then `--every 12` for the whole film. Open the contact sheet and actually look. Every serious bug was caught this way: invisible pages, camera inside a dune, washed-out cover, a die blocking the product, smeared cut frames.

**Process hygiene.**

- Never `pkill -f <pattern>` from a shell whose own command line contains the pattern. It kills the shell. Use PIDs.
- Launch long renders with `setsid nohup ... &` so they outlive the agent's turn.
- `--resume` skips existing frames. Validate them afterwards with `studio.qa frames`, because a killed process can leave a half-written PNG.

## 4. Sound

- **Narration** comes from Piper TTS (`python3 -m studio vo FILM --voice ...`). **Voice licences matter: ads are commercial use.** Each Piper voice inherits its training dataset's licence, and several popular ones are non-commercial. `studio.vo` refuses any voice not in `SAFE_VOICES`.
  - Cleared: `en_US-norman-medium`, `en_US-bryce-medium` and `en_US-john-medium` (public-domain male); `en_US-joe-medium` (CC0 male); `en_US-kristin-medium`, `en_US-ljspeech-high` and `en_GB-cori-medium` (public-domain female); `en_GB-jenny_dioco-medium` (commercial use permitted).
  - Not cleared: `en_US-ryan-high` (CC BY-NC-SA), `lessac` (research-only), `amy` and `hfc_*` (derived from lessac or NC), `en_GB-alan-medium` (all rights reserved).
  - The first films used `ryan` and `alan` and were re-voiced on 2026-09-29.
  - Fetch cleared voices with `tools/setup.sh --voice NAME`, after checking the MODEL_CARD.
- `...` in a line becomes a real pause. Tape-slow 0.93 gives weight. Add reverb to taste.
- Say URLs phonetically in `lines.txt` ("W W W dot goosnav dot shop").
- **Everything else is synthesized** (`studio.audio`), which keeps it rights-clean: drone, wind, choir, bells, boom, slam, dice hits, paper flutter, whoosh, reverse swell. Hit points come from `events.json`, which the film writes with the exact times of every landing and slam.
- **Mix:** duck under voice (`Mix.duck(0.68)`) and check `Mix.report_voice()`. Every line should sit at **≥ 8 dB** voice over effects. Master to about **−14 LUFS** (`studio.qa loudness`).
- **True peak after AAC.** Sample-peak limiting isn't enough. `assemble` now limits at 4x oversampling after an 18 kHz lowpass (`alimiter` at 192 kHz), and `studio.audio` gives percussive hits a 2 ms attack. If `qa loudness` still shows Peak above −1 dBTP, find the moment (decode, upsample 4x, argmax) and lower that one sound. In THE DILEMMA it was a tanh-driven low boom whose squared-off top made the AAC decoder ring. Never let a loud sound end abruptly at full level either. One-pass `loudnorm` flattens the dynamics (LRA 7.9 to 4.9), so don't use it.
- Nobody in an agent session can listen. Check a spectrogram (`studio.qa spectrum`) for broadband hiss walls; the first vortex mix was too noisy. Ask the owner for one listen before posting.

## 5. Type, assembly, QA

- Overlays come from `studio.typeset`, sized from the frame (`min(W,H)/1080`), with the margin at 11.5% of the width in portrait. White Helvetica Bold product lines on the picture; black on the white end card.
- `studio.assemble` layers the frames, a vignette, grain 3 (hides sky banding), overlays with fades, the fade out and the mix. It writes a master at CRF 16 and a web version at CRF 22 (about 35–45 MB for 90 s).
- QA checklist before delivery:
  1. `studio qa`: frame check, stills every 1.5 s, loudness.
  2. Look at the sheet: cut frames clean, nothing cropped, prices right, every URL with `www.`.
  3. Voice ratios ≥ 8 dB.
  4. SRT captions for the narration.

## 6. Delivery

- Existing Claude film projects can use `python3 -m studio deliver FILM --name TITLE` to deliver under `agent-exchange:deliverables/claude/`.
- Other agents can upload a finished package with `rclone copy PACKAGE/ agent-exchange:deliverables/<agent>/<project>/`, then run `rclone check PACKAGE/ agent-exchange:deliverables/<agent>/<project>/ --one-way`. A local folder or sync queue alone is not proof of delivery.
- The `agent-exchange` remote was verified on this host on 2026-09-29. If it fails, keep the local source, report the failure, and verify Drive before saying the item is shared. Large video files should use the remote copy path.
- The shared rclone client ID is scheduled for retirement during 2026; migrate its configuration if the provider stops accepting it.

## 7. Running unattended Claude sessions

- `orchestration/launch.sh <lane> <film_id>` starts `claude -p` with the COMMON_BRIEF plus a lane prompt, in a session folder with `STATUS.md`. Sessions run with `--dangerously-skip-permissions`, because nobody is there to approve commands. The brief confines them to their film folder, the repo tools and the one Drive folder.
- **Sequencing (owner rule):** start the next session only when the previous one is almost done. `orchestration/watch.sh <session_dir>` (or `watch_frames.sh <frames_dir> <total>` when a session has ended its turn and left a render running) blocks until the final render reaches 60%, assembly after a render, delivered or failed, or the process dies.
  - Bug fixed on 2026-09-28: PROGRESS written as `72/2073` was read as 72%.
- **Run ONE Claude session at a time.** Two resumed sessions in parallel (B finishing plus C redoing look-dev) exhausted the account's usage window in under an hour on 2026-09-28, killing both mid-task. Sessions share one usage budget, so the "next session when the previous is almost done" rule also protects the budget. Put a session's long render on the GPU, but keep only one agent thinking at a time.
- **Account usage limits kill sessions mid-task** (LIGHTS OUT died at frame 2059/2073). Resume with the same context: `cd <session_dir>; claude -p --resume <session_id> "<what happened + what to do>" --dangerously-skip-permissions`. The session id is in `session.log`, in the final `"type":"result"` line.
- Tell sessions to write status as integer percentages, to work efficiently, and never to edit the core `studio/` or `blender/` code or other films. They propose core changes in their README instead.

### Orchestrator review

Sessions tend to rush into the final render. THE LONGEST TURN started after 34 minutes with 6 preview stills, and its frames were underexposed with a static opening.

- Always review a session's first 200 or so final frames with a contact sheet (`studio.qa sheet` on `frames/` with `[::12]`).
- Stop a weak render by PID (the blender process and its `studio render` parent).
- Resume the session with specific notes. The brief now has a hard preview gate and a `PREVIEW_NOTES.md` requirement.

## 8. Mistakes log

| Mistake | Fix |
|---|---|
| Book textured from a cropped, soft product photo | Generic Book 2 (owner rule) |
| Photo-rectified card faces and packs looked soft and skewed | Generic card and pack from the flat logo file |
| Pages invisible in batch renders | Transforms-only object pools |
| Two render processes in parallel | One at a time, with the lock |
| Camera inside a dune on orbit shots | Wider plateaus; preview every camera path |
| Leak light in front of the cover washed it out | Put it behind the cover plane at a lower energy |
| Die blocked the product in a push-in | Moved the rest position; check final-frame composition |
| Motion-blur smear on hard cuts | `CUT_FRAMES` rendered without blur |
| Explosion flash whited out the frame | Energy 6e5 W, short decay |
| Vortex soundbed was a hiss wall | Lowpass the flutter; lower gains; check the spectrogram |
| Watcher misread "72/2073" as 72% | The parser computes the fraction |
| `pkill -f` killed the calling shell | Kill by PID |
| Narration shipped in the non-commercial `ryan` and all-rights-reserved `alan` voices | Re-voiced with public-domain voices; `studio.vo` now refuses uncleared voices |
| The back of a low-poly head read as a blank face | `lowpoly.Human` has a hair-back piece |

## 9. Low-poly vignettes (GLPV-001): what worked

- The house actor (`lowpoly.Human`) is a few hundred triangles of primitives parented at the joints, posed by setting joint rotations every frame. It reads as an early-2000s NPC, and transform-only animation renders reliably in Eevee. Give every head a hair-back piece, or a figure seen from behind reads as a blank face.
- Jaw flap: `Lines` turns the dialogue WAVs into per-frame envelopes quantised to three openings. Blinks run every 3–7 s. Poses update on 2s (`on_twos`).
- Each vignette renders in about 10 minutes (540×960, 16 samples, no motion blur, which is the game look). Iterate on stills with `--times` and fix composition, not texture detail.
- Traps found:
  - A low sun behind a tall hall throws the whole apron outside into shadow. Light exterior hero objects with their own floods.
  - Background haze in the same colour as a white object hides it.
  - Glow thresholds must use world position (`Geometry > Position`), not per-object coordinates.
  - Cameras for insert shots land inside actors unless the actors are moved aside.
  - Dense PA or radio voices (band-limited plus saturation) measure about 10 dB hot. Mix them at about 0.3 gain.
- Every vignette ships with a README containing the brief grid (person, want, obstacle, turn, product), transcript, CTA text, and asset and licence manifest (bible §68).

## 10. Goosnav characters in 3D (2026-10-08)

The rigged characters (guy, gal, expert; HQ and PS1) and their scripts are in `business/studio/assets/3D/characters/`. Its README has the rig controls.

- **Look:** white toon emission (Shader to RGB), one cel-shadow tone and an inverted-hull ink outline (Solidify, flipped, backface-culled black). Render with the **Standard** view transform: AgX turns emission white grey.
- **Proportions that read as the comic:**
  - The head is a tall dome, widest at the eyes, about 27% of the height.
  - The snout comes out about two-thirds of the way up the head and is about 1.1× as long as the head is wide. The eyes sit on its root.
  - Hands are big mittens, feet are long flat paddles (0.4 m on a 1.74 m figure), and the shirt is tucked inside the pants.
- **Armature deformation renders reliably in batch Eevee** when every frame is keyed (bake, then `frame_set`). The section 3 trap is about editing vertices, not armatures.
- **Walking:**
  - **Stops:** time each stop with `Walk.stop_window()` so it lands with both feet planted, then use `Walk.settle()` for a closing step. A frozen mid-stride stop folds the back leg.
  - **Toe roll:** roll about the toe or heel only while the foot is on the ground. In the air, the pivot lift makes the foot kick up behind.
- **Props in hands:** animate the prop's transform in the character's armature space and drive the hands with `grip` (IK wrist position plus finger and palm directions). Don't parent the prop to a hand.
- **Prop scale in wide shots:** life-size products vanish at PS1 resolution in a wide two-shot (a booster pack is 7 cm). Scale them up as Minecraft-style drops, or cut to a close-up.

## 11. Session behaviour seen so far

- A `claude -p` session may end its turn with a render still running in the background ("I'll pick up when it finishes") despite the brief. Its STATUS.md then stops updating. Watch the frames folder with `watch_frames.sh`, and when the render ends, resume the session with `claude -p --resume <id> "render finished: assemble, QA, deliver"`.
