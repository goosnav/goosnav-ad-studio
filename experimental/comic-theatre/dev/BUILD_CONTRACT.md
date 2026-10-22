# Approved implementation addendum — 2026-10-21

The owner approved execution and added templates, simple JSON, a source-selection
GUI, optional AI drafting, a tutorial and assets contained in the project. This
addendum supersedes conflicting details in the initial design.

## Public input v1

`{version:1, template:'book-duet'|'fireside-reader'|'page-tour', title:string,
comics:[catalogComicId], seed?:integer, scene?:'library'|'fireside',
lines:[{speaker:'reader'|'friend',text:string,comic?:catalogComicId,
emotion?:string,gesture?:string,face?:object,reaction?:object,pause?:number,
shot?:'speaker'|'two-shot'|'source',audio?:relativePath} |
{action:'open'|'turn'|'hold'|'read'|'place'|'close'|'slam',comic?:catalogComicId,
seconds?:number}], output?:{width,height,fps}}`.

Everyday scripts need template/title/comics/lines only (version defaults to 1).
Fixed cast/voices come from template. A selected comic must be used by at least one
line; no undeclared comic references. Template sets page count/cast. Defaults are
resolved once and stored. Optional actions obey a book state machine. The normal
generated skeleton starts open; author-specified open can override this. No paid
calls in rendering. Local Kokoro defaults; recorded audio is supported explicitly.

## Internal contracts for independent components

Catalog at assets/catalog.json:
`{version:1,edition:{id,title,pdfSha256,evidence},assets:{actor:{path,sha256},
book:{path,sha256},environment?:{path,sha256}},comics:[{id,title,path,sha256,
pdfPage,printedPage,transcript,observations,verified:true}],templates:[{id,label,
minComics,maxComics,speakers,scenes}],scenes:[{id,label}]}`.

Assets paths are relative to project root, e.g. assets/actor.glb. No runtime access
to the parent studio required. All included files content-hashed. Only reviewed
comics may be sampled; no automatically trusted OCR. Copy exact source images.

Resolved script retains the public fields and adds seed/scene/output defaults,
sourceLock:[{id,sha256,pdfPage,pdfSha256}], cast voice IDs and normalized line IDs.

Timeline: `{version:1,fps,width,height,duration,frames,seed,scene,template,
cast:['reader','friend'],events:[{id,type:'line'|'source'|'action'|'hold',
start,end,comic,speaker?,text?,emotion?,gesture?,face?,reaction?,shot?,
mouth?:[{t,value}],rail?,bookState?}],sources:[catalogComicId]}`.
All times are seconds. `mouth.t` is line-relative seconds. `bookState` is one of
table-open/table-closed/held-open. Source inserts are auto-added before each new
comic (up to 5 seconds overlapping narration), not in place of or before dialogue.
Explicit shots/actions take priority. Compile duration from real audio.

Renderer owns src/player.mjs and src/actor.mjs (may add src/book.mjs).
`createPlayer(canvas,{timeline,catalog,assetBase:''}) -> Promise<Player>`;
`renderAt(frameIndex)`, `diagnostics()`, `dispose()`.
Asset URLs = assetBase + '/' + catalog path. Browser serves three via import map.
Independent actor skeletons. No audio playback in renderer; preview host owns it.
All events/poses seekable from frame index without accumulated state.

GUI owns web/index.html, web/app.mjs, web/style.css. Backend endpoints:
- GET /api/catalog → catalog
- POST /api/select {template,seed?} → {script} (editable skeleton, not AI)
- POST /api/validate {script} → {script:resolved}
- POST /api/draft {script} → {script} using explicitly configured optional writer
- POST /api/render {script,voice?:'kokoro'|'recorded'} → {id,status}
- GET /api/jobs → {jobs:[{id,status,progress?,error?,video?:'/output/…'}]}
- GET /api/jobs/:id → job
- GET /assets/... → catalog-allowlisted local images/models
Errors: HTTP 400/409/500 JSON {error:string}. GUI POSTs same-origin JSON only.
Server will enforce Origin/Host and CSRF token supplied GET /api/session → {token};
GUI sends X-Theatre-Token on every POST. No GUI ability to configure executables.

## Rulings and progress

- Work happens on feat/comic-theatre and only in this new folder. Existing dirty
  parent edits/submodule work are preserved; no new worktree or parent integration.
- Book first, card schema remains roadmap. New template selection is seeded and
  source-locked before optional writing. Invalid generated output cannot change it.
- Public JSON is intentionally simpler than the original internal-beat proposal.
  Engine behavior, source integrity and error safety remain binding.
- Asset snapshots are included, with origin hashes/notices; no checkout-specific
  imports. Original large asset sources remain in the 3D repo; compact portable
  exports and verified excerpts travel with the experiment.
- Production claims of perfectly natural acting remain subject to real visual/audio
  review. Record supported actions and limitations rather than claiming success.
- The author-facing validator is a small explicit contract checker with helpful
  field/choice errors, not a second independent AJV schema that could drift.
  Source resolution checks the actual embedded book image, and capture freezes
  verified bytes. Saved final receipts are rechecked against the video on disk.
