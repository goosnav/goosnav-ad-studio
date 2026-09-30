# Three Brags

A 26-second character-led Goosnav animation following the supplied desert/pyramid/bomb script. It uses the Goosnav Ad Studio's `lowpoly.Human` rig rather than imported stock figures. The first character makes one full turn, the second makes two and a half unstable turns, and the third delivers the bomb line without competing for attention. The final overhead shot develops into a large faceted mushroom cloud. The white card resolves the joke with **“TWO OF THESE ARE FOR SALE.”**

## Deliverables

- 4:5 master and smaller web MP4; H.264/AAC, 1080 × 1350, 24 fps.
- Burned dialogue captions and a separate SRT.
- End card featuring the supplied real Book Two cover and Goosklerf pack images, prices, and `www.goosnav.shop`.
- `SCRIPT.md` is the shot-by-shot storyboard; `film.py`, `sound.py`, and `type.py` are the reproducible source.

## Production and credits

Characters, pyramids, desert, bomb, cloud and debris are original procedural geometry built using the studio's `blender/lowpoly.py` and `blender/bstudio.py`. Product images are the local Goosnav-owned textures `book_front.png` and `pack_front.png` in the Ad Studio assets folder. Dialogue uses studio-cleared Piper voices: John (public domain), Cori (public domain), and Joe (CC0). Wind, movement, fuse and explosion effects are synthesized with `studio.audio`; no third-party music or sound recordings are used. Type uses the studio's Helvetica-compatible Nimbus Sans and Times-compatible serif system.

Prices were checked against the live `www.goosnav.shop` shop catalog on September 29, 2026: Book Two $19.95, Goosklerf $13.95. Recheck before paid publication. The explosion is stylized, with no depiction of injury.

## Rebuild

From `code/goosnav-ad-studio` with the studio environment configured:

```bash
python3 -m studio preview three_brags --format 4x5 --times 0,7,11.5,17.35,19.4,21.6
python3 -m studio render three_brags --format 4x5
python3 -m studio sound three_brags --format 4x5
python3 -m studio type three_brags --format 4x5
python3 -m studio assemble three_brags --format 4x5 --name THREE_BRAGS
python3 -m studio qa three_brags --format 4x5 --name THREE_BRAGS
```
