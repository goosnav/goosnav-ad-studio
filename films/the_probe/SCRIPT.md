# WHAT WE SENT

*Working title: THE PROBE.* A Goosnav film, 4:5 portrait (1080×1350), 60 s, Blender 4.0 Eevee.

A deep-space probe in the Voyager tradition, launched long ago and still going. Gold foil, aluminium
struts, a white dish. Bolted to its side is humanity's message to whoever finds it: not a golden record,
but **Goosnav Book 2** (the generic blue hardcover), a **sealed Goosklerf pack**, and a **pneumatic
canister** into which a new comic arrives every month, by means nobody has explained. That canister is
**the Patreon**.

Shot like the most beautiful space documentary ever made. Black space, one hard white sun, honest lens
flares, planetshine. Three procedural planets in the Goosklerf colours: a teal ice giant, an orange
gas giant with storm bands, a purple ringed world. The probe is tiny against them, then enormous in macro.

**Narrator:** a warm, awestruck cosmic-science presenter (Piper `en_US-ryan-high`, slow 0.96, length 1.14,
a small planetarium dome of about 1.6 s). He is sincerely moved that this is what we sent. The sincerity
is the joke. He never winks.

**The impossible thing:** past the rings, the probe passes a Goosklerf die the size of a moon, tumbling in
the dark. It comes up six. The probe does not stop.

**Palette:** black space, hard white sunlight, gold foil, and teal / orange / purple on the planets.
No pastel, no sodium, no storm blue, no night blue.

## Shots and timings

| # | Time | Shot | Narration (VO start) |
|---|---|---|---|
| 1 | 0.0–6.4 | **Sunrise over the ice giant.** Black. At 0.3 s the white sun breaks over the limb of a vast teal ice giant that fills the lower frame; flare ghosts streak across the portrait frame. The probe, tiny, drifts across the upper third and catches the light. Slow rising move. | 01 @1.0 "Billions of kilometres from home... something we made is still travelling." |
| 2 | 6.4–14.9 | **Macro glide.** Enormous in close-up: crinkled gold foil, struts, the dish rim sliding past in the foreground. The camera glides down the bus to the payload plate and reveals it on the words: the book (≈9.4 s), the sealed pack (≈11.4 s), the tube (≈13.8 s). | 02 @6.4 "We had one chance to tell the universe who we were. We sent a book... a sealed pack of cards... and a tube." |
| 3 | 14.9–20.3 | **The book.** Slow push on Goosnav Book 2 in its gold bracket. The sun rakes across the blue cover. Behind, the edge of the teal planet. | 03 @14.9 "The book is Goosnav Book 2. Signed... in case they want to know who." |
| 4 | 20.3–28.0 | **The gas giant.** An orange gas giant with storm bands and a great storm fills the frame. The probe crosses it as a small silhouette with a lit rim; the camera slowly turns until the pack glints on the plate. | 04 @20.3 "The cards are Goosklerf. Dice and fortresses. Out here... two players. One table." |
| 5 | 28.0–39.9 | **The canister.** Extreme close-up on the aluminium tube and its open pneumatic pipe, which just ends in space. At ≈31.2 s a hiss and a thunk: the cap swings open and a curled comic slides out, uncurls, and drifts to the lens. The camera reads it: the real comic "Cheer up buddy, your wife probably just hasn't been born yet" (`comic_01`). | 05 @28.0 "And every month, by means no one has explained... the tube receives a new comic." 06 @33.8 "This one says... cheer up, buddy. Your wife probably just hasn't been born yet." |
| 6 | 39.9–46.8 | **The impossible thing.** A purple ringed world. The probe crosses the ring plane. From frame left a teal die the size of a moon tumbles past, slowing; at ≈43.6 s it shows six. The probe does not stop. Last month's comics drift in a long trail behind it. | 07 @39.9 "Past the outer rings, it met a die the size of a moon. It came up six. The probe did not stop." |
| 7 | 46.8–49.8 | **Recede.** The probe, small, going away into the black. The sun is just a bright star now. | 08 @46.8 "It is still out there. Still receiving." |
| 8 | 49.8–55.5 | **Hero / one more comic.** The payload plate in macro, the three products in frame with black space above. At 50.1 s: hiss, thunk, the cap opens and one more comic (`comic_03`, "Sleeping wastes so much time") slides out. Price lines appear in the black above. | 09 @50.3 "Goosnav Book 2. Goosklerf. And the tube is the Patreon." |
| 9 | 55.5–60.0 | **White card** with the addresses. | 10 @55.9 "W W W dot goosnav dot shop." |

Overlay (Helvetica Bold, top left, white on black space) from 50.5 s:

- Goosnav Book 2. $19.95.
- Goosklerf. From $13.95.
- The Patreon. $3 a month.
- `www.goosnav.shop`

End card: "Goosnav continues." with `www.goosnav.shop` and `www.patreon.com/goosnav`.

## Sound

All synthesized (`studio.audio`), rights-clean.

- **Score:** a slow analogue-synth "cosmos" pad: detuned saw stacks, lowpassed, a long chord progression
  (D major add9, B minor, G, A), with a soft bell arpeggio shimmer. It swells at the sunrise, drops to almost
  nothing in macro, swells under the die, resolves on the recede.
- **Space:** a deep sub drone; very quiet radio telemetry (filtered noise, a faint periodic beep) whenever
  we are close to the probe; nothing on the wides but music, as in every good space documentary.
- **Canister:** a pneumatic hiss (bandpassed whoosh), a metallic thunk, a small latch click, a paper flutter
  as the comic slides out. The same again at the end, closer.
- **Die:** a vast low swell and a soft sub "thump" as it shows six.
- Voice ducked (`Mix.duck`), ≥ 8 dB over effects, master near −14 LUFS.

## Real versus built

- **Real art:** `comic_01` (read in extreme close-up), `comic_03` (the one that arrives at the end), and the
  other 2026 comic boards `comic_00`–`comic_06` in the trail of drifting pages. Scans only; never redrawn.
- **Generic products:** Book 2 from `gen_book_front/back/spine.png`; the pack from `gen_pack.png`; the die from
  the `die_teal_*` faces. No product photographs.
- **Built:** the probe, the planets, the rings, the stars, the sun, the flares, the canister and pipe.
