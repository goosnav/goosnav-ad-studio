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

The compact `./ad` path now carries the October 21 lessons in code (tests: `tests/harness/test_product_content.py`):

- **Product content inventory.** `harness/product_content.json` lists real viewable content per product (covers, the current offer, Book Two drawing sheets, Goosklerf cards and rulebook lines), each with a locator and a `confirmed`/`unconfirmed` membership status. `harness/content.py` hands it to the script and animator stages as `PRODUCT_CONTENT` (compact form in modern briefs). Mark items `confirmed` there once the printed edition is checked; that is how ads may claim more.
- **Script and animator prompts** (`harness/production.py`): product taste first, the comedy craft that worked (deadpan, withholding, escalation, reactions in tight close-ups, a button, a closing line that can double as the CTA), legible page/card inserts, the Book Two helpers, three-quarter camera angles for long noses, and `shots.face_camera`.
- **Story-led duration.** `output.target_seconds` is a guideline. Unset bounds default to 0.5x-2.5x the target (at least target+15 s), and the audio step grows a plan's duration to fit its measured takes plus a reply beat, up to the maximum, instead of rejecting it.
- **Ambience and foley.** A plan's `direction.sounds` (`ambience` plus events placed against lines) becomes a procedural bed (`harness/foley.py`) mixed under the dialogue within the existing mix gates.

There is still no automatically enforced paid-value field. Never falsify timings, mutate an active run behind the controller, or bypass resource safeguards.

## Source and review integrity

- Verify each page/card/rule/feature against the exact advertised edition. Presence in a model or a drawing date is not proof.
- Original Goosnav art remains unchanged. Do not generate replacement canonical drawings or imply an invented advertising scene appears in the book.
- Do not invent unpublished pages, subscription benefits, card rarity, ease of play, benchmark results, customer quotes or conversion lift.
- Distinguish source/log interpretation from personally viewing/listening to the final render. Prior QA recorded by another agent is not your own inspection.
- Technical validity, owner creative approval, audience attention and incremental commerce are different results.
- Keep this public repository free of private customer/account data, business finances and credentials. Private buyer research belongs in the company brain.
- Do not publish ads, spend, change live offers or upload assets beyond explicit authorization.
