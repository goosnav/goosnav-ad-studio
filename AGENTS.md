# Goosnav Ad Studio — agent entrypoint

## Read before creating an ad

1. Read [PLAYBOOK.md](PLAYBOOK.md): current creative and production direction.
2. Read [product-content-first.md](docs/product-content-first.md): source grounding, quality review, and duration policy.
3. Read only the relevant product sources and tool documentation. For the October 21 reference, use [GET YOUR OWN production log](dev/AD_LOG_2026-10-21_get-your-own.md) and its [film folder](films/get_your_own/README.md).
4. Use [the reusable brief](prompts/product-taste-brief.md) to launch a product-grounded film. The method is not a mandatory scene template.

## Owner direction — October 21, 2026

**Give viewers a taste of the actual product. Make an entertaining film, not a generic pitch wearing the product's logo.** Real contents, situations, card mechanics, or object behavior should motivate the scene, reactions and curiosity.

An arbitrary runtime or a minutes-per-ad production target is not the success criterion. Develop the scene, measure actual performance and let the edit determine length. Reuse assets and successful work to reduce wasted production time; do not reduce quality to hit an invented deadline.

This direction supersedes conflicting creative shortcuts in older documents. It does NOT disable process/stall watchdogs, spending limits, factual checks, licensing, asset safeguards or existing run contracts.

## Important implementation boundary

This update changes agent-facing authoring/review instructions. It does **not** silently rewrite the compact harness's runtime validators, saved-run configurations or retry/watchdog logic. The compact `./ad` defaults still encode a chosen duration and speed-oriented presets. They are not the default creative brief for an unconstrained owner request.

For a story that does not fit those settings, use the direct film/toolkit route demonstrated by `films/get_your_own/`, or deliberately configure a fresh run after the story duration is known. Do not truncate speech or misreport timings to pass a validator, mutate an active run behind the controller, or claim story-led duration is implemented end-to-end in the harness. An automated duration-planning change would need separate implementation and regression tests.

## Source and review integrity

- Verify that each depicted/referenced page, card, rule, feature or benefit belongs to the exact advertised product/edition. Presence in a mixed asset library is not proof.
- Original Goosnav art stays unchanged; animation may present it, not invent replacement canonical drawings.
- Do not claim to have watched/listened to media when only its script, source code or production log was available. Label source-derived observations.
- Owner preference, technical QA, audience response and attributable commerce are distinct evidence. No invented performance lift.
- Keep public repository material limited to production guidance and non-sensitive product references. Do not copy private personal/financial strategy, customer data or credentials here.
- Do not spend, publish ads, change live offers, or upload new assets beyond existing explicit authorization.
