# Source provenance and third-party notices

The Goosnav characters, comic drawings, book images and environment exports remain
the owner's material. Inclusion here does not place that artwork under an open
source license or grant third parties publication/merchandising rights. Original
comic artwork is copied unchanged; no canonical drawings were generated.

## Included creative assets

`assets/catalog.json` records SHA-256 hashes for every included asset and selected
page. These are portable snapshots, not runtime links to the source checkouts.

- Character: Homunculus sealed-face character export; inspected source checkout
  commit `e52576f96f9d2fdb2a0190cd825cb5081e6cdc68`. Runtime face and gesture
  controls adapt its procedural game-character approach. Two independent skeleton
  instances are used. The legacy sealed-face export is retained for compatibility.
- Theatre clothing variants: Goosnav-3D-assets commit
  `65f9ae1f791b86b5e2ce2b235ee0d2f00908557a`, active v10 white/beady-eye characters
  with blue/rust/olive clothes,
  packed portable GLBs and editable Blender sources in Goosnav-3D-assets. The
  original silhouette and rig are reused; no replacement canonical drawings.
  Reusable facial presets are mirrored from `exports/theatre-performance.mjs`.
- Book, cover, library and comic JPEGs: active Goosnav-3D-assets at commit
  `0b1bccff8e78a5ef2591adfe1170dd1255ea9216`. Book export is the openable v2
  interior. The library export is included for future scene work; current scene
  staging is procedural and does not claim to reproduce that entire environment.
- Reviewed pages: printed 20, 36 and 95; PDF pages 24, 40 and 99 respectively.
  Source PDF SHA-256 is recorded in the catalog. Verification establishes supplied
  file/page identity, not that a particular live store offer uses that edition.

New source additions require manual image/transcript review and an exact embedded
book-page match. See the tutorial. Changing a file without reviewing its catalog
entry causes a deliberate validation error.

## Software and voice dependencies

Bundled Liberation Serif Regular and Liberation Sans Bold are unmodified fonts
under the SIL Open Font License 1.1. Full copyright and license text is included
in `assets/fonts/NOTICE.txt`. They provide portable Times/Helvetica-compatible
metrics; they are not the proprietary Times New Roman or Helvetica font files.

Node dependencies are version-pinned in `package-lock.json`; their installed
packages contain their respective licenses. Three.js and proper-lockfile are MIT;
Playwright is Apache-2.0. Browser binaries are installed separately by Playwright.
FFmpeg is an external executable: check the license of the build you distribute.

Optional local speech uses the installed Kokoro/misaki/PyTorch/phonemizer stack,
espeak-ng loader, and the separately downloaded hexgrad/Kokoro-82M voice/model
files. Their package/model licenses and notices apply independently. They are not
included in this repository or relicensed here. Recordings remain the recording
owner's material; only use voices and performances you have permission to use.

An optional remote writer sends selected page images/transcripts to the endpoint
you explicitly configure. Ensure that provider use is appropriate for your rights
and privacy requirements. The normal manual render makes no such request.
