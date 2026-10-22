# GET YOUR OWN (Book Two, 2026-10-21)

A reader describes Book Two's real 2025 inventions to a friend who can't see them, then
slams it shut: "Get your own." 24.5 s, 1080×1350, 24 fps, early-3D `retro_world` look,
Frame end card "Get your own signed copy" / www.goosnav.shop.

```sh
films/get_your_own/make.sh            # everything; finished stages under WORK are kept
```

| File | Stage |
| --- | --- |
| `casting.json`, `voices.json`, `voices_toes.json` | Kokoro casting round and final takes (`harness.voice`) |
| `cut.json` | The single source of truth: line takes and start times, sound events, shots |
| `sound.py` | Places takes, synthesizes foley and hall acoustics, writes mix/stem/timeline/mouths |
| `scene.py` | Set (reading room ×0.4), cast, Book Two on the library book rest, lights, cameras |
| `animate.py` | Book retime, IK page turns and slam, leans, `performance.apply`, cut markers |
| `render.py` | Resumable 540×675 EEVEE PNG render of the story frames |
| `finish.py` | 2× nearest upscale, mux, Frame end card via `harness.media.finish_frame` |

Approach, measurements and lessons: `dev/AD_LOG_2026-10-21_get-your-own.md`.
