# Goosnav Ad Studio: agent entrypoint

## Read before creating an ad

1. Read [PLAYBOOK.md](PLAYBOOK.md) for current creative and production direction.
2. Read [purchase value](docs/purchase-value.md) and the relevant row in [product-class routing](docs/product-class-routing.md). Do not load unrelated business strategy.
3. Read [product-content-first.md](docs/product-content-first.md) for source grounding and technical handoffs. The modern harness already carries product-taste notes through existing worker fields; preserve that implementation.
4. Read only relevant product sources and tool documentation. For the October 21 reference, use [GET YOUR OWN log](dev/AD_LOG_2026-10-21_get-your-own.md) and [film folder](films/get_your_own/README.md).
5. Use [the reusable brief](prompts/product-taste-brief.md). Review with [commercial review](prompts/commercial-review.md) before expensive production and again on the finished film.

## Current owner direction: product taste plus a reason to buy

Give viewers an authentic taste of the product. Make an entertaining film, not a generic pitch wearing its logo. Then establish why the intended viewer would value owning or paying for the real product, beyond enjoying this free sample. A book's pages, a game interaction or a demonstrated function should cause the interest and relevant action.

These are planning questions, not a mandatory beat sequence: audience, current substitute, desired use/ownership situation, actual paid difference, evidence, destination. Do not turn the successful reference into a required library, cast count, joke count or punchline. Do not make every product a book commercial.

No arbitrary runtime or minutes-per-ad production target is the creative success criterion. Develop and perform the scene, measure real takes, and let useful performance determine length. Reuse successful work instead of rushing dialogue or deleting the product experience. Budget, stall, asset, licensing and existing run-contract safeguards remain active.

## Implementation boundary

This revision changes the authoring playbook, briefing and commercial-review artifacts. It preserves the October 21 `harness.creative.job` product-taste implementation, tests and source handoffs. It does not claim to add an automatically enforced paid-value field or dynamically story-led duration to the compact harness.

For an unconstrained story, use the direct film/toolkit route demonstrated by `films/get_your_own/`, or deliberately configure a fresh run after duration is known. Compact `./ad` runtime validators and speed presets remain in code. Never falsify timings, mutate an active run behind the controller, or bypass resource safeguards. A future code-level paid-value handoff requires implementation and regression tests, not a documentation claim.

## Source and review integrity

- Verify each page/card/rule/feature against the exact advertised edition. Presence in a model or a drawing date is not proof.
- Original Goosnav art remains unchanged. Do not generate replacement canonical drawings or imply an invented advertising scene appears in the book.
- Do not invent unpublished pages, subscription benefits, card rarity, ease of play, benchmark results, customer quotes or conversion lift.
- Distinguish source/log interpretation from personally viewing/listening to the final render. Prior QA recorded by another agent is not your own inspection.
- Technical validity, owner creative approval, audience attention and incremental commerce are different results.
- Keep this public repository free of private customer/account data, business finances and credentials. Private buyer research belongs in the company brain.
- Do not publish ads, spend, change live offers or upload assets beyond explicit authorization.
