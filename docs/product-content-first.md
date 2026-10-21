# Product-content-first advertising

**Source:** Owner instruction dated October 21, 2026; repository production log `dev/AD_LOG_2026-10-21_get-your-own.md`. This is creative/authoring guidance, not evidence of conversion improvement or a runtime implementation change.

## The rule

Let the audience experience a specific, authentic sample of what they would buy. Build the scene around that sample. A product name, cover, slogan or end card alone is not a taste of the product.

A book sample may be an actual invention, drawing or premise from its pages. A card-game sample may be a real choice, interaction or absurd rule situation. An object sample may be its distinctive real use. Do not force all products into the same dialogue structure.

## Source packet

Keep a short packet beside the script. It can be Markdown; no new database is needed:

- Exact product/edition/variant.
- Each selected source file or asset ID and page/card locator.
- What the source actually says/shows, keeping interpretation separate from quotations.
- Evidence that it belongs to the advertised product; list uncertainties.
- Current factual claims and their verification date.
- The proposed fictional advertising setup, clearly distinguished from product contents.

**Mixed-library trap:** GET YOUR OWN's log says the openable book model mixes 2025 and 2026 pages. Verify membership, not merely asset availability or date. Reject the claim "this is in Book Two" when the only evidence is a texture being stored in the Book Two model.

## What to learn from GET YOUR OWN

The log documents a 24.5-second scene whose product-specific observations create the friend's curiosity. Reaction close-ups and page inserts support that curiosity. "Get your own" connects the payoff and purchase action. Sound and the final librarian reaction belong to the world rather than functioning as generic commercial decoration.

Keep these principles, not the literal formula. Do not mandate a reading room, two characters, three examples, a withheld page, that exact phrase, or a 24.5-second length.

The log records measured audio, inspected frames and final QA. An agent reading the log may attribute those findings to it, but may not claim to have performed the viewing, listening or measurements itself. No audience metrics were supplied for this reference in the October 21 request.

## Writer / director / reviewer instructions

**Writer:** begin with the authentic sample and one compelling premise. Make dialogue respond to that sample; do not insert a generic product claim where a concrete observation should be. Avoid copied quotations not present in the source. A verbal setup can withhold some information to build curiosity, but the film must still provide an authentic taste, not only say that unseen content is wonderful.

**Director:** use legible source artwork, purposeful inserts, character wants/reactions and measured performance. Verify any necessary manipulation before production. Reuse the book/shot helpers where relevant. Atmosphere is useful when it enriches the encounter, not when it delays the only interesting event.

**Editor:** cut weak beats, not meaningful reaction time. Do not speed up or clip words to satisfy a default preset. Product connection and entertainment should survive the edit. Keep picture, sound and end-card timing consistent.

**Reviewer:** test whether replacing the product title would leave the entire script unchanged. If so, investigate whether the idea is generic. This is a diagnostic question, not an automatic ban on every cover/hero shot. Require true product details and an honest purchase connection; do not approve merely because all technical checks pass.

## Time policy and implementation boundary

Story/performance determines screen length unless the owner or actual placement provides a real constraint. Production-time targets are information for optimization, not creative pass/fail gates. Existing safety, budget, process and stall controls are not waived.

Implemented for new compact runs: `output.target_seconds` is a guideline, unset bounds default to a wide 0.5x-2.5x window, and the audio step grows a plan to fit its measured takes (see AGENTS.md). Explicit owner bounds and saved runs keep their contracts. Do not falsify timing, mutate saved jobs or bypass safety checks.

## Efficiency improvements to pursue without weakening the film

Reuse the source packet across related ads; retain successful takes and scene assets; preview the risky interaction or camera angle at low resolution; cache completed work; repair the weakest actual defect; leave production notes for the next film. Track rework separately from necessary creative effort. Do not build a new ad engine merely to encode this lesson.

## Automated handoff and visual follow-up

The modern worker briefs now carry this direction through `harness.creative.job`;
no extra agent, schema field or research pass is added. Within the existing two-source
budget, research puts a compact `Taste:` note in `creative_directions` (exact product,
source locator, observed detail and membership evidence). Writing retains it in
`visual_direction`; direction puts it in the relevant `beat.picture`. Those existing
fields survive the scoped handoffs. Selection and final review check the resulting
sample and reaction as part of their existing jobs, not a separate report.

The supplied video was inspected visually across its cut: page inserts around 8–10 s
and 14–16 s return to character reactions. The transferable lesson is that connection,
not the exact sequence. This observation does not claim independent listening or an
audience-performance measurement. Its small uploaded copy is not a readability standard.
Make the chosen detail legible on a phone with an accurate crop, angle and lighting;
a washed-out spread is not enough. Printed lettering on actual pages/cards is product
content, not a promotional overlay to remove. Preserve original art and match spoken
references to the displayed detail. A simple source-art insert may replace expensive
page-turn/hand-contact work without deleting the joke. When editing, protect the sample
and the setup/reaction it supports rather than only preserving the closing product shot.

These are short stage-specific creative instructions, not deterministic proof of
source membership or humor. Existing runtime validators, watchdogs, voices, animation
helpers, contracts and legacy brief paths remain unchanged. Focused prompt regression
coverage: `python -m pytest -q tests/harness/test_product_taste.py`.
