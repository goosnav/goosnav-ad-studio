# Deterministic renderer handoff — 2026-10-21

Main-agent integration note: the final follow-up also moves the lamp out of both
close-up face/upper-chest regions and fixes opening/reopening to update the actual
physical spread through shared `bookSpread`. The updated real-GLB tests pass,
including zero lamp overlap in both checked close-ups and correct spread 19/11
across opening, reopening and reverse seeks. Main personally inspected both new
close-ups and final demo contact sheet. Earlier notes below about foreground lamp
overlap describe the previous revision, not the final framing. Grip limitations
remain unchanged. See VERIFICATION.md for integrated test/demo evidence.

Implemented against `dev/BUILD_CONTRACT.md` and the current `src/timeline.mjs` contract. Renderer source is ready for the owner's separate end-to-end demo review. This report records my browser-test observations, not approval or inspection of the final demo film.

## Final bounded follow-up: lamp, open/reopen, portable test artifacts

At the owner's request, moved only the practical lamp's stem, shade, and light from `(x=.86, z=.54)` to the table's rear edge `(x=0, z=.20)`. The corrected speaker camera is unchanged. I personally inspected both new **432×540** speaker stills: faces and upper chests are unobstructed, with only the shade edge visible at the outer edge of each shot. An occlusion-preserving raster regression measures lamp-shade overlap against the projected face/upper-chest region: reader **0 pixels**, friend **0 pixels** (friend previously **4,681**).

Fixed the independently reported book selection defect: `open` now sets both comic and target spread at the start of opening, before pages become visible. `pageFor` imports and uses the owner's `bookSpread()` from `./book-pages.mjs`. The actual bundled GLB regression reproduces selection order 020/036, initial open to 036, dialogue changing to 020, close/reopen to 036, then close/reopen to 020 and reverse seeking. It now returns physical spread **19** for 036 and **11** for 020 throughout the appropriate openings and subsequent dialogue. Before the fix, opening to 036 changed the label but incorrectly retained spread 11. No grip methods or other book behavior changed in this follow-up.

All test screenshot/image destinations now use `path.join(os.tmpdir(), filename)`; no `/tmp` dependency remains in the test. Latest inspection filenames are `comic-theatre-lamp-fixed-reader.png` and `comic-theatre-lamp-fixed-friend.png` in the system temporary directory. Previous fixed-frame filenames below are retained as historical inspection evidence; regenerate the assigned browser tests for current composition.

Latest Node suite: **25 passed, 0 failed, 1 conditional voice skip**. The targeted eye/composition/open-reopen regression passed on the pinned browser; the general renderer regression is recorded below after completion. This follow-up touched only `src/player.mjs`, `src/book.mjs`, the assigned browser test, and this report. No actor, camera, grip, package, server, catalog, or asset changes.

## Eye review correction and source freeze

After the owner's review of `.local/review/speaker.png`, I reproduced the exact demo time **7 seconds / frame 84 at 12 fps**, compared both eye primitives against the original bundled GLB, and rendered with the procedure disabled by restoring untouched source positions. Both actors had `eyeOpen: 1`. Maximum vertex difference was **exactly zero**, and the restored-source render was **pixel-identical**. The exported eye positions are Y-up in mesh space; this was not a Blender Z-up conversion failure or an accidental blink at that frame.

The visible problem was the inside close-up camera nearly lining up with the long nose, making the original small side-mounted eye difficult to read against the head. The camera now sits on the outside of the inward-facing cast. The original eye location is preserved. In an isolated, occlusion-preserving white-eye visibility pass at 432×540, visible sclera coverage increased from **292 to 369 pixels**. I personally inspected the revised full-set frame: the near eye and pupil are clear, but the far eye remains hidden by the head/nose. That initial camera correction exposed a foreground-lamp torso overlap, subsequently fixed by the bounded follow-up above.

Two related regressions were fixed: partial eye closure now uses each original primitive's own vertical center (pupil-center drift was **1.958 mm**, now **zero**), and fully open eyes restore the original Float32 vertices exactly. Reading now removes partner-facing yaw and pitches down toward the book. The tested head-forward vector in actor space changed from `[-0.315, -0.274, 0.909]` to approximately `[0, -0.559, 0.829]`.

The new browser regression was observed failing before these changes and now passes. It compares original/default/restored vertices, render pixels with eye processing disabled, narrow-eye center drift, actual raster visibility using the production camera, and the reading direction. This correction changed only the non-grip eye/gaze portion of `src/actor.mjs`, the speaker-camera side in `src/player.mjs`, the assigned test, and this report. **No book or grip methods were touched during the eye correction. Renderer source is frozen for the owner's rerender.**

Additional personally inspected temporary 432×540 views:

- `comic-theatre-demo-speaker-fixed.png` — actual saved demo timeline at 7 seconds, rendered with the corrected camera (before the lamp move).
- `comic-theatre-eyes-fixed.png` — isolated original actor with the production speaker camera.
- `comic-theatre-reading-fixed.png` — same actor/camera with the reading pose.

## Files changed by this renderer task

- `src/player.mjs`
- `src/actor.mjs`
- `src/book.mjs`
- `tests/player.browser.mjs`
- `dev/RENDERER_REPORT.md`

No package, catalog, server, other source, parent checkout, or asset edits; no commits or subagents.

## Delivered behavior

`await createPlayer(canvas, { timeline, catalog, assetBase: '' })` returns `renderAt(integerFrameIndex)`, `diagnostics()`, and idempotent `dispose()`. Asset paths resolve as `assetBase + '/' + catalogPath`. Three and its addons use the host import map. Rendering consumes no audio, paid service, parent-checkout module, wall clock, requestAnimationFrame, animation-mixer accumulation, or frame-history state. Invalid or out-of-range frame indices throw. Output dimensions come from the timeline, with pixel ratio fixed at 1.

The actual bundled sealed-face Homunculus GLB is skeleton-cloned for each cast member. Skeletons and bone objects are independent across actors; mutable eye geometry is also cloned. Rest-relative skeletal poses are recomputed on every frame. Solid mouth aperture, lip curve, and separate eyebrows attach to the head bone using the authored face coordinates. Measured, line-relative mouth samples are interpolated; the mouth returns to zero outside the samples and during holds. Supported contract emotions are neutral, thoughtful, curious, skeptical, dry, pleased, concerned, and exasperated. Gestures include explain, nod, head_tilt, shrug, and page_glance. Face controls include brow_left, brow_right, eye_open, mouth_curve, and deterministic auto/once/off blink. Gaze uses bounded partner/speaker head turns and downward page/reading poses.

Listener reactions honor actor, at, and duration. A line_end reaction starts in the following hold event; it does not fire during speech. Holds remain silent. When the compiler retains a speaker shot on the hold, its camera favors the reacting listener. Speaker shots use three-quarter angles that expose the long nose rather than placing it directly in front of the mouth.

Library and fireside are procedural, lit sets with a wood table, shelves, abstract decorative spines, rug, brass details, and lamp. Library has a window; fireside has a side fireplace and warm practical light. The optional catalog environment GLB is intentionally not loaded. No decorative spine is presented as an actual Goosnav product.

Source events and source shots show the selected exact JPEG, aspect-contained with the whole page visible, using an unlit, untone-mapped image plane. No crop, redrawing, transcript replacement, or invented panels. Comic changes update both source insert and the physical book spread; reverse seeking restores the earlier source. The renderer rejects unknown, unselected, unverified, or unmappable sources. Cryptographic catalog verification remains the host's responsibility.

## Actual book and rails

The full v2 catalog book GLB is used, including its original cover/spine/back materials and all 72 double-sided leaves. No replacement book artwork or proxy geometry was needed. The exported demonstration animation is not played. Cover_Hinge and Page_NN_Hinge transforms plus leaf Curl morphs are derived directly from timeline time. PDF pages 3–146 map to the real exported interior; the required number of turned leaves is `floor((pdfPage - 2) / 2)`.

| Rail | Implemented state/pose |
| --- | --- |
| open | Smooth cover/selected stack opening; table-open at completion; hand targets follow cover and supporting board. |
| turn | Deterministic leaf hinge/curl interpolation to the requested spread, or one next leaf when no comic is supplied. |
| hold | Smooth table-to-reader transform with two bounded wrist targets and aligned palm normals. |
| read | Maintains table or held state; reader looks down at the book. |
| place | Returns the book to its fixed table pose and releases the held pose. |
| close | Closes cover and turned leaves, restoring table-closed at completion. |
| slam | Accelerated closure, finishing at 65% of the rail; remaining time is a closed hold. No physics or sound. |

Action bookState is treated as the resulting state, not applied at the action start. Normal timelines start table-open; an initial explicit open begins closed. Source switches are deliberate cuts to a spread, not simulated flipping through every intermediate page. While held, both hands remain assigned to the book; a held turn currently animates the leaf without a separate finger peel.

## Verification actually run

Test-first: the initial browser test failed at the missing player import before production modules were written. Further observed failures covered missing brow controls, premature line_end reactions, missing palm alignment, and missing/overextended opening contact targets. These were implemented or corrected and rerun.

Final commands used the installed pinned browser, with no executable override:

```sh
npm test
npm run test:browser
node --check src/player.mjs
node --check src/actor.mjs
node --check src/book.mjs
```

- Node suite after the eye correction: **23 passed, 0 failed, 1 skipped**. Skip: optional offline local-voice installation check.
- Browser suite after the eye correction: **14 passed, 0 failed, 1 skipped**. Skip: GUI real-server integration test, which requires `THEATRE_GUI_REAL_SERVER`. Both renderer tests passed and were not skipped. The owner's separately reported real-server GUI pass is not counted as my own verification.
- Pinned Chromium reported **151.0.7922.34**, Playwright browser revision **1234**, using SwiftShader for the renderer tests. Final browser suite took approximately 47 seconds.
- Renderer test loads only bundled assets/catalog. It checks independent skeletons, head attachment, measured mouth interpolation and silence, reaction timing, source changes, source containment, rail state boundaries, turn midpoint/end, bounded hand targets, reverse seeks, invalid frames, unverified-source rejection, both sets, and disposal/recreation.
- After an arbitrary later seek, returning to frame 60 produced **byte-identical canvas PNG data** and identical diagnostics. Held poses also restored after seeking past a slam. This establishes determinism in this browser/GPU configuration, not pixel identity across different graphics drivers.
- No uncaught browser errors were recorded.

Measured in the fixture at 24 fps, with model/world units in meters:

| Pose | Left wrist target error | Right wrist target error |
| --- | ---: | ---: |
| Held, frame 126 | 0.00805 m | 0.02342 m |
| Opening midpoint, frame 228 | 0.09321 m | 0.000000071 m |

Held palm-normal errors (`1 - dot`) were 0 and approximately 1.01e-8. These measure wrist/palm transforms, not fingertip contact or appearance. The test's opening threshold is 0.12 m; it is a reach bound, **not a natural-grip acceptance criterion**.

## Personally inspected views and visible limitations

I opened the rendered 960×540 source/close-up/held/fireside images and the final **432×540** portrait source, close-up, held, turn, opening, and fireside views. The long noses and mouth aperture are visible in close-up. Source inserts preserve every panel and printed page number. At portrait size, original small lettering is necessarily small; landscape comics leave substantial top/bottom space when shown whole. The physical book's lettering is too small for reading in the wide conversation shot; full source inserts carry that task.

Held hands are now flatter along/under the book edges instead of hanging in their rest orientation. They remain stylized: fingers can overlap paper or sit slightly away from an edge, and there is no collision solver or fingertip/thumb grip constraint. The opening screenshot shows an awkward reaching/crossing arm and the measured supporting-wrist shortfall of about **93 mm**. Therefore grip quality is explicitly **not guaranteed**. Open/close/turn rails are controlled model poses, not realistic paper handling. Slam has no secondary impact dynamics. The two-shot leaves substantial headroom at portrait size, and the side fireplace is partly clipped at the right edge. Fire geometry is static, and blinking squeezes the original eye geometry rather than adding anatomically accurate skin lids.

Reproducible temporary inspection artifacts (in `os.tmpdir()`, regenerated by the browser test; not repository assets):

- `comic-theatre-portrait-closeup.png`
- `comic-theatre-portrait-held.png`
- `comic-theatre-portrait-turn.png`
- `comic-theatre-portrait-opening.png`
- `comic-theatre-portrait-reaction.png`
- `comic-theatre-portrait-fireside.png`
- `comic-theatre-portrait-source.png`

The owner's `an-inside-source-2026-10-21T23-58-11-505Z-ee0331af` final film was not watched or listened to for this report. I inspected its supplied speaker still and reproduced the single 7-second frame from its saved timeline for the eye correction above. These stills and state tests do not establish timing quality, natural acting, owner creative approval, audience attention, or commerce performance.

## Read-only provenance

- `homunculus/web/room.js`: named bones, saved rest transforms, local rest-relative quaternion poses, forward-axis convention.
- `homunculus/web/browser-room.js`: sealed-face expression coordinates, head-bone attach pattern, separate brow and mouth geometry concepts. The realtime/damped animation and procedural speech oscillator were not adopted.
- `goosnav-3D-assets/scripts/build_openable_book2.py` and its v2 validation JSON: hinge naming, exported coordinate conversion, original-page mapping, closed/open leaf stack offsets, and Curl morph semantics.

These were inspected read-only. Runtime assets come exclusively from this experiment's bundled catalog, and the final test has no reference-checkout fallback.
