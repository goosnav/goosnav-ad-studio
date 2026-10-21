# PLAYBOOK: product-grounded films worth watching

**Current owner direction: October 21, 2026.** Read this before choosing a generation route. Earlier production lessons remain preserved in [the historical playbook](docs/history/PLAYBOOK-before-product-taste.md); its old creative constraints are not the current brief. Tool-specific safety and technical contracts remain authoritative.

## 1. The creative objective

**Give people a taste of the actual product.** The film should be entertaining and make a viewer curious about a particular book, game or object—not just make them aware that something is for sale.

Start from a real drawing, comic premise, card interaction, rule, physical feature or product experience. Let that concrete material cause what happens. Avoid abstract praise, sacred-object pedestal shots without a story, or unrelated banter followed by a pasted-on product name.

The owner preferred the new GET YOUR OWN ad to the usual studio output. That is a creative judgment, not demonstrated sales or audience performance. The reusable lesson is product-specific curiosity, not "all ads must be two people in a library."

## 2. Source first, then script, then production

1. Identify the exact product and verify current buyer-facing claims.
2. Inspect the actual material. Record its file/asset, page/card locator, what it contains, and why it belongs to this edition. Never infer edition membership just from an asset name or year.
3. Select the specific detail that is interesting on its own. Explain what the viewer will experience and what makes them want more.
4. Write a scene that develops that detail through character wants, reactions, demonstrations, tension or a reveal. The form may be dialogue, a performed comic premise, a demonstration, narration, or another motivated structure.
5. Preserve a causal connection between the experience and the purchase invitation. Use a natural ending; no mandatory joke count, shot count, number of product details, or universal narrative formula.
6. Read/perform it, then measure real voice takes. Plan useful reaction gaps, inserts and sound. Let the edit determine the length.
7. Preview the weak points cheaply before a full render. Repair actual defects while retaining successful work.

Use [the source-grounded brief](prompts/product-taste-brief.md). If source material is unavailable, name the gap. Do not invent an interior gag and claim it is in the product.

## 3. Reference: GET YOUR OWN

The [production log](dev/AD_LOG_2026-10-21_get-your-own.md) describes a reader sharing specific Book Two inventions with a friend who cannot see the pages. Reactions escalate toward wanting to see the book; the refusal, "Get your own," is both payoff and purchase invitation. Inserts let the audience see real material, and a final librarian reaction extends the scene rather than changing it into a generic sales pitch.

The log records an important provenance trap: the openable Book Two model contains newer pages as well as material selected for the advertised edition. Do not assume every embedded texture belongs to Book Two.

Reported implementation lessons include reusable page-turn/slam helpers, three-quarter views for long-nosed characters, page inserts, measured and distinct voice performances, purposeful foley, and low-resolution contact sheets. These are source/log-derived lessons. The final video must still be viewed/listened to before an independent audiovisual verdict; the source log's QA is not a substitute.

## 4. Runtime and production time

**No arbitrary film length or production-time deadline is the default creative constraint.** A shorter film is not automatically better, nor is a longer one. Keep what earns attention; remove what does not. Do not hurry speech, remove the product's actual appeal, or pad a film to fit a preset.

A real owner/platform placement requirement can constrain a particular delivery. Record that requirement explicitly and preserve a fuller master when appropriate. Duration must remain internally consistent across voice, action, edit, render and end card.

Efficiency comes from reusable rigs, verified product art, sets, camera helpers, measured voice takes, checkpoints and targeted repairs. Track time and cost for improvement, not as a proxy for creative quality. No instruction here authorizes unlimited provider spending or disabling runaway-process protection.

### Current harness limitation

`./ad` and its compact harness still use configured runtime ranges and preset execution controls. This documentation does not make them dynamically story-led. For unconstrained product-taste work, prefer the direct film/toolkit route used in `films/get_your_own/`, or configure a fresh run to the selected story duration before generation. Do not silently change a running job's contract or describe unchanged defaults as fixed.

## 5. Preserve artwork, product truth and current formatting

- Real Goosnav drawings remain real: do not redraw, extend or generate substitute canonical art. Use authentic, legible source material.
- Confirm editions, variants, contents, prices, availability, shipping, signed-copy/bonus promises and promotional terms before using them. Historical numbers in logs are not live facts.
- Default delivery remains 4:5 portrait, 1080×1350, unless the owner requests another placement. Reframe deliberately rather than crop away the action.
- The established early-3D/`retro_world` character world remains available. A distinct setting supports the story; a new set is not required for every ad.
- Use the actual configured Frame policy for typography/URLs/end-card rendering. A previous film's exact end card is not a mandatory two-link or price template.
- Character interaction is allowed when its capability is verified. Reuse `blender/book2.py`, `blender/shots.py` and existing rigs when suitable; do not fake a missing action. Simpler staging must retain the product-specific idea.

## 6. Production sequence and reuse

Use the existing working tools, not a new pipeline for each film:

`source selection → script/performance → measured timing → blocked scene/animatic → targeted corrections → render/edit/mix → Frame finish → review → delivery`

Relevant implementation references:

- [GET YOUR OWN build](films/get_your_own/README.md): authored film and reusable helpers.
- [Worker guide](dev/WORKER_GUIDE.md): existing contracts and tool calls.
- [Operations](dev/OPERATIONS.md): runtime, retries and delivery.
- [Worlds and staging](docs/worlds.md): set/rig capabilities and framing.
- [Library](docs/library.md): asset IDs, provenance and publication.
- [Historical playbook](docs/history/PLAYBOOK-before-product-taste.md): original film-specific Blender, audio and rendering lessons. Resolve old instructions against current tool contracts; do not reactivate retired creative rules.

Checkpoint accepted work. Do not re-synthesize unchanged accepted voice takes, rebuild a working prop, rerender a good shot, or run full-book research for every variant. Fix the actual weak line, unreadable page, bad contact, camera or mix. A successful export is not creative approval.

## 7. Final acceptance review

Ask, with evidence rather than a formula:

- Is the sample real and correctly attributed to this product/edition?
- Would the specific moment be worth watching without a sales caption?
- Does the product cause the action/curiosity rather than appear as an interchangeable prop?
- Can the audience understand the important line, reaction and product detail?
- Does the ending lead honestly to the advertised product and a functioning destination?
- Does the pacing serve the performance, without rushing or filler?
- Were visuals and sound actually inspected? What remains unverified?

Do not replace taste with a numeric score or pretend a schema can prove an ad is funny. Preserve separate records for technical checks, owner creative assessment, and later audience/commerce results. A few good product-grounded films are preferable to a queue of generic technically valid ones.
