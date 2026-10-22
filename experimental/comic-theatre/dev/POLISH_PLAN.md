# Comic Theatre performance and cinematography implementation plan

> Execute the owner's six requested improvements with test-first changes and
> independent asset/renderer/GUI work. Preserve the existing portable engine.

**Goal:** clearer speech/emotions, visibly different everyday readers, recognizable
physical comic-book presentation, editable retro end cards, and reproducible varied shots.

**Architecture:** reuse current v10/Homunculus geometry and rig; export clothing
variants and reusable facial performance resources to the 3D asset library. Bundle
verified snapshots here. Compile all variation into the saved timeline, never
randomize during rendering. Keep normal rendering local/no paid animator.

**Tech stack:** existing Node/Three/Playwright/FFmpeg, Blender for asset exports.

**Spec:** owner's six-point follow-up and clarification: prioritize different-color
clothes, use comics as reference, do not reinvent characters. Push both repos and
integrate studio changes into main when checks and actual render pass.

## Shared contract

- Public `characters?: {reader: variantId, friend: variantId}`; omitted gets distinct
  clothing defaults. IDs `blue`, `rust`, `olive`, plus `blue-beady`, `rust-beady`,
  `olive-beady` for the owner's follow-up request: black beady eyes without whites.
  No hats/body rebuild required now. Existing white-eye versions remain available.
- Catalog `variants: [{id,label,asset}]` refers to catalog.assets keys. Preserve
  `assets.actor` as compatible default. All variant GLBs are hash-verified/bundled.
- Public `product?: 'book2'` and `endCard?: {enabled, title, text, url, seconds}`.
  Defaults product book2, enabled true, title `Goosnav Book Two`, text `A book of comics.`,
  url `www.goosnav.shop`, seconds 3. JSON/GUI edits persist. Plain-text lengths bounded;
  no HTML or invented pricing. End-card link blue, underlined, Times family; ordered
  dither/low-resolution early-computer treatment, original product art unchanged.
- `shot`: `auto` (new default), `speaker`, `two-shot`, `over-shoulder`, `book`, `source`.
  Explicit values win. Auto compilation guarantees an early two-person shot for
  duet templates, avoids repeating identical setups, and uses seeded choices.
- Timeline retains existing `cast` string IDs and adds `characters`, `product`,
  `endCard`; line events get resolved non-auto shot. Source intro events get
  `shot:'book'` and slow camera push/pan over the real open GLB on the selected page.
  Explicit `source` remains the exact flat-art readability override.
- Append `{id:'end-card',type:'endcard',...endCard,start,end}` only after all dialogue
  and reactions. Existing timelines lacking it remain playable.
- Facial performance resources belong in asset repo (data, rebuild scripts,
  editable blends, GLB exports and review images). Imported model geometry wins
  over floating mouth blobs where feasible; no archive imports. Runtime acting must
  remain seekable; continuous speech shapes and emotion blends, not visibility pops.
- Main owns contracts/timeline/audio/library/catalog/server/docs/integration.
  Asset worker owns new asset-repo resources + actor.mjs/facial helper + focused tests.
  Renderer worker owns player.mjs/endcard.mjs/camera helper + new renderer tests.
  GUI worker owns web files + focused GUI tests. Do not edit another worker's files.

## Tasks / acceptance

- [x] Asset/performance: failing geometry/variant/performance tests; build six
  color variants with original geometry provenance, coherent facial controls; check
  source hashes, skeleton independence, all supported emotions, silent closures,
  continuous motion and visual review. `make check-layout` and LFS checks before push.
- [x] Contract/compiler: test old inputs, invalid variants/end-card text, defaults,
  explicit shot precedence, seeded variation, duet coverage, complete measured
  dialogue followed by end card. Implement normalization and saved shot decisions.
- [x] Renderer: actual open-book reveal and correct selected spread, bounded camera
  rails, two-shot/OTS/readability, distinct variant models, retro end-card texture.
  Test reverse seeking, portrait framing and exact custom end-card text.
- [x] GUI: editable variants, end-card fields/enable/duration and shot selection;
  import/export/validate/draft keep authored choices and source locks intact.
- [x] Integration: snapshot reusable assets, documentation/tutorial, full suites,
  fresh preview and inspected frames. Review changes; push asset commit/LFS before
  parent pointer, merge studio main without discarding existing work, verify remotes.

## Review focus

Old saved inputs/timelines remain usable; automatic shots cannot hide the product;
new camera geometry cannot clip noses or shrink both actors out of portrait frame;
silent end-card time must not truncate speech; copied standalone folder must include
every new asset/module/font and use no developer-machine absolute paths.
