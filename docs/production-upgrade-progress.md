# Production upgrade implementation ledger

Approved plan: faster ads, richer worlds, and a growing production library (2026-10-19 conversation).

Constraints: preserve current asset refactor; use configurable roots and stable asset identities;
never reuse retired assets; keep dynamic providers; local voice first; character comedy central.
Normal nine-second budgets low/medium/high 10/20/40 minutes, fast 5/10/20,
with at most 25% overtime, scope reduction and checkpoint recovery.

User contract: the CLI turns a product premise and approved assets into a reviewed,
playable nine-second advertisement, with bounded execution and recoverable failures.
The live happy path remains under validation; test fixtures are not proof of creative quality.

## Work

- Runtime policy, deadlines, CLI and targeted invalidation: implemented; regression checks pass.
- Relocatable catalog and publication: implemented; temporary-remote and relocation tests pass.
  First-catalog bootstrap now preserves committed active `.blend` LFS content OIDs;
  catalog reads require hydrated bytes rather than silently dropping inventory.
- Local voice cache and measured takes: implemented; an earlier isolated three-line
  sample measured 17.1s cold / 1.7s cached, not full-ad latency or a quality verdict.
- Verified-take mix/replay and workspace result staging: implemented; no synthesis,
  speech stretching, automatic ASR or emotional-quality assessment. Uniform dialogue
  gain targets −21 dBFS, capped at +18 dB with peak protection and measured audit;
  unsafe/unreachable speech floors block assembly.
- Actor placement/current-frame camera containment and resumable rendering: implemented;
  repeated staging tests now pass after bone-world assumption/orthographic-centering
  fixes. Containment is not visibility review.
- Three reusable environment builders/previews: proxy-free bundles built, inspected and validated.
  Latest reported asset commit `c2328b0` has 70 content-verified records, including
  4 approved characters and 15 products; archives are excluded. It includes upstream
  red mesas/pyramids and nested brain `ae51`. Active inventory is hydrated in the clean
  checked-in submodule; the dirty artist checkout remains untouched/adoption pending.
- Creative briefs, product-scoped feedback/reuse and metrics: implemented, not model training.
- Technical docs: reviewed against current module/CLI interfaces. End-to-end benchmarks,
  final integrated verification and release approval remain pending; main's full suite
  is running; v3 medium-fast, medium and high have resumed with the corrected catalog.

## Decisions

- Work in the shared feature workspace; preserve concurrent edits and the user's dirty asset checkout.
- Use parallel agents only for disjoint modules; main agent owns integration and scheduling.
- Existing saved runs retain legacy execution policy. New runs receive versioned budgets.
- Time targets scale linearly with ad duration and count; cold dependency downloads are
  reported separately and should be completed by preflight before a timed benchmark.
- Asset publication is a post-production operation and cannot invalidate a completed ad.

## Verification

Final main integrated suite: **519 passed, 7 skipped in 236.01 seconds**
(`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q`). Independent review also
passed 153 targeted tests and reported no outstanding findings. These overlapping
counts are not additive and do not establish end-to-end creative acceptance.
The audit collector ran three available checks; eleven were skipped because tools
were unavailable or checks were opt-in. Dedicated security/dependency scanners
were not available; no security-clean or comprehensive static-analysis claim is made.

Live v1 benchmarks exposed an overly short attempt allowance hidden from workers:
they saw only total remaining time and spent writing time exploring asset files.
Attempt deadlines are now explicit in prompts, and writing uses supplied facts/catalog;
the director owns capability inspection. Timeout recovery now can change model within
an available provider when the other provider is cooling down. These changes have
regression coverage. Benchmark runs use separate job state from user jobs.

Observed v2 failures: low/low-fast timed out in direction; medium-fast failed in audio
after repeated missing output fields. Do not describe these as successful speed benchmarks.
Root-cause repairs include persistent route identities, alternate-model search across both
providers, compact stage-specific instructions, verified scratch speech, and reusable mixing.
The normal-medium run passed direction/audio but is now `needs_review`, with scene
assembly blocked. V2 high was not run.

The first three v3 runs are terminal failures: low-fast at 154 seconds (before
the director-floor fix), high-fast at 1,130 seconds, and low at 587 active seconds.
The low run's 793-second controller wall measurement includes the benchmark queue
being suspended for catalog repair after the child finished; it is not a comparable
end-to-end speed measurement. Earlier trials also ran during implementation and
some concurrent tests, so they are failure evidence, not controlled comparisons.
Low failed at `board_review` after five unsafe-path rounds: referenced accepted
inputs were incorrectly listed as output `files`. Common instructions and review
error feedback now explain `files: []` for reviews without new outputs; cite inputs
in `findings.target` instead. The remaining medium-fast, medium and high runs have
resumed with the corrected catalog and are still in progress. No successful v3
full-ad timing or final creative approval is established here.
Direction now requests a 90/120/180-second attempt floor for low/medium/high,
including fast mode, still limited by the stage ceiling and remaining global
budget. This preserves the hard cap while allowing mandatory local synthesis and
measured-plan assembly. Scene assembly/animation similarly allow 120/180/300
seconds per attempt, still bounded by the same configured/global ceilings.

The 10/20/40-minute normal and 5/10/20-minute fast targets are policy budgets, not
measured performance claims. Isolated voice/world/render measurements and temporary
Git remote tests do not establish the full advertisement workflow.

Review regression ledger:

| Boundary | Observed defect | Evidence/disposition |
| --- | --- | --- |
| Recovery | Temporary route indices collided with appended routes | Reproduced; stable route IDs and regression pass |
| Legacy resume | New idle limit leaked into runs without execution policy | Reproduced; policy gate and regression pass |
| Budget exhaustion | Media timeouts became generic failure; CLI returned success | Frame/QA ceiling and nonzero-exit regressions pass |
| Director allowance | Short attempt slices repeatedly interrupted useful scratch synthesis | 90/120/180-second effort floors implemented and regression-covered; global cap remains authoritative |
| Running status | A fallback attempt could retain stale task status | Running state/current route persisted before attempt-start reporting; regression-covered |
| Asset selection | Same-basename replacement could precede saved identity; retirement was not authoritative | Catalog and full-engine relocation regressions pass |
| Publication | Outgoing ancestors could include unrelated commits; adoption dirtied expected gitlink | Live-tip ancestry and receipted pin-transition checks implemented; latest asset checkpoint above, dirty-source adoption pending |
| Catalog bootstrap | Smudge-disabled worktree omitted non-whitelisted active LFS products/sets | First-catalog inventory preserves content OIDs; existing catalog repaired explicitly, active payloads hydrated and verified, archives excluded |
| Publication integrity | Accepted artifacts/manifests could change before post-production publication | Artifact and accepted-manifest hash revalidation now precedes publication/retry; tamper regressions covered |
| Nested publication checks | Isolated layout validation lacked pinned nested reference files | Recursive pinned submodule initialization and owned-worktree cleanup implemented; temporary-Git regressions pass |
| Render reuse | External dependencies were not checked on cache hits | Dependency checks now run on every invocation; per-frame hashes authorize resume, not creative approval |
| Staging | Bone-world assumption and orthographic centering caused earlier failures | Fixed; repeated staging tests reported passing, not proof of live scene success |
| Voice timing | A plan could pass without measured scratch speech or full-file fit | Full selected polished WAV must fit its slot, including pauses/tails; active bounds alone are insufficient; fit regressions covered |
| Review strictness | A pass verdict could coexist with unresolved important defects | Blocking/important findings cannot pass strict review contracts; regression-covered |
| Review artifacts | Board review listed accepted input paths as newly authored files | Common instructions/error guidance require new local outputs only; reviews normally use `files: []`; focused 55-test pass reported |
| Audio level | Quiet takes could miss the speech floor | Measured uniform boost capped at +18 dB toward −21 dBFS, peak protection and final-level audit; unsafe floors still block |
| Direction submission | Manual result assembly could omit portable scratch dependencies | `submit-direction` verifies local WAVs and declares dependencies without altering authored timing; controller approval still required |

Scope ruling: the user's early-3D animated-world direction supersedes the branding skill's
white-ground print layout here. Original comic/product art, one clear idea, honest claims,
and understated copy remain protected. Generated sets are original 3D production assets,
not canonical comic drawings or invented brand lore.

Ruling: local Chatterbox is absent; retain Kokoro and explicit unsupported-provider errors,
with no heavy install or unmeasured expressiveness claim. Cost: richer synthesis requires
an optional runtime setup and listening comparison later.

Ruling: a dirty artist checkout is never advanced automatically. Validated assets may be
pushed from an isolated worktree, while local adoption and parent pin are retryable.
Cost: new assets are not available in that dirty checkout until it can safely adopt them.

## Operator entry points and limits

See [CLI.txt](../CLI.txt) and [README](../README.md#production-helpers-and-their-boundaries)
for voice requests, `harness.creative submit-direction`, accepted-direction mixing,
replay, scene rendering and budget
extensions. [Library API](library.md) documents saved identities, publication receipts
and independent push/adoption/parent-pin outcomes. `./ad feedback RUN_ID --rating
good|okay|bad --note "..."` records user evidence; `./ad metrics RUN_ID` reports
measured work, not subscription dollar cost. `./ad publish RUN_ID` is a publication
retry, not a render retry or an instruction to reset artist work.

Remaining acceptance requires v3 runs to reach their actual terminal outcomes
and human review of finished speech,
blocking, readability and comedy. No test count or remote asset push substitutes
for those checks.
