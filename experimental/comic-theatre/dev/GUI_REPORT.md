# GUI handoff

Implemented only `web/index.html`, `web/app.mjs`, `web/style.css`,
`tests/gui.browser.mjs`, and this report. No commits, subagents, framework,
external fonts, parent-runtime imports, server edits, AI calls, or render jobs.

## Behavior

- Catalog-driven templates/scenes and reviewed source-image cards with IDs,
  printed/PDF page numbers, transcripts, full-size image links, and selected order.
  Template changes preserve page IDs and dialogue; incompatible choices are
  explained rather than silently replaced. Random sample calls `/api/select`.
- Editable dialogue speaker/text/emotion/gesture/page, add/remove/reorder controls,
  and full JSON editing for face/reaction, actions, pauses, shots, output and audio.
  Advanced fields survive form edits. JSON upload/download and local/server
  validation work. Invalid or unapplied JSON cannot be silently replaced.
- Following the owner's lock clarification, scripts retain `sourceLock` through
  dialogue edits, uploads, and pasted/applied JSON, even when the incoming
  selection differs from the current editor. Stale saved locks reach the backend
  unchanged and are rejected. Intentional page/template changes using the form
  clear the previous lock; JSON authors must explicitly remove it to reselect.
  Validate records the server's new lock and resolved defaults and displays exact
  source hashes. Derived cast and timeline line IDs are omitted from authoring
  JSON. A line's omitted comic uses the current page.
- AI Draft is an explicit `/api/draft` request. For unwritten pages, only that
  request receives placeholder lines required by the server's input resolver.
  Missing writer configuration preserves the editor. Responses changing selected
  IDs, template or explicitly locked settings are rejected. Late draft/sample/
  validation responses cannot overwrite newer edits. Only `/api/draft` has a
  250-second client deadline, allowing two 120-second writer attempts plus
  overhead. Other POST and GET deadlines remain 120 and 15 seconds respectively.
- Generate sends `/api/render` with `voice: "kokoro"` by default, without drafting.
  Recorded audio is an explicit alternative and requires line audio paths. Jobs
  poll separately, display text or numeric progress and errors, and link completed
  MP4s from their local `/output/…` video field. No preview endpoint is assumed.
- Every POST uses same-origin JSON and the token from `/api/session`. Dynamic
  content uses DOM text/value assignment, never HTML interpolation; image and
  video links are restricted to local asset/output paths.

## Verification

Tests were written before implementation; missing-GUI and subsequent integration
regressions were observed failing before fixes. Initial GUI verification was
**13 passed, 0 failed, 0 skipped**. After the bounded source-lock/deadline fix,
the GUI suite has **16 passed, 0 failed, 0 skipped**, including the opt-in
real-server integration test, using the installed pinned browser without an
executable override.
The HTTP fixtures exercise actual browser input, requests, uploads, downloads,
polling, injection-shaped text, source-lock transitions, and response/edit races.
The real-server case verifies actual image loads, authenticated selection and
validation, lock preservation/recreation, and HTTP 400 rejection of a stale
uploaded lock without invoking AI or rendering.
Desktop layout was visually inspected with the actual catalog; the 390 px mobile
layout and editing were checked in Chromium.

Current `npm test`: **25 passed, 1 skipped, 0 failed** (initial verification was
19 passed, 1 skipped). The existing optional offline-local-voice installation
test was skipped. GUI/test ESM syntax checks passed. This is GUI verification,
not final-film visual/audio QA.

The review regressions were observed red before the fix: both uploaded and pasted
locks disappeared, the real validator incorrectly returned 200 after that loss,
and the GUI aborted a draft before its repair window ended. All four checks now
pass. The deadline test uses Playwright's virtual clock with actual pending HTTP
requests: draft survives 240 seconds, aborts at 250 seconds, and ordinary POSTs
still abort at 120 seconds. It does not wait minutes or call a real writer.

From `experimental/comic-theatre`:

```sh
# Scoped mocked browser suite (real-server case skipped by default)
node --test tests/gui.browser.mjs

# Include the implemented local server; still no AI/render jobs
THEATRE_GUI_REAL_SERVER=1 node --test tests/gui.browser.mjs

npm test
node --check web/app.mjs
node --check tests/gui.browser.mjs
```

Historically the initial GUI run used an already-installed alternative Chromium
because the pinned browser was absent. The pinned browser is now installed;
the portable commands above were used for the final follow-up verification.

Without a usable installed Playwright/browser, the GUI tests report skips with
setup guidance. `THEATRE_TEST_CHROMIUM` can point to another installed executable.
Backend validation remains authoritative for supported performance values, book
state transitions, file integrity, voice availability, and production safeguards.
