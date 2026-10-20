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
- Technical docs: reviewed against current module/CLI interfaces. Initial implementation
  and submodule pins were pushed as studio `daa767e`. End-to-end creative acceptance
  remains partial: the high trial completed; the other five trials did not.
  Follow-up handoff fixes were pushed as `cc62660`; final dependency fixes passed
  integrated verification and independent review. No benchmark controller or ad
  worker is left running.

## Decisions

- Work in the shared feature workspace; preserve concurrent edits and the user's dirty asset checkout.
- Use parallel agents only for disjoint modules; main agent owns integration and scheduling.
- Existing saved runs retain legacy execution policy. New runs receive versioned budgets.
- Time targets scale linearly with ad duration and count; cold dependency downloads are
  reported separately and should be completed by preflight before a timed benchmark.
- Asset publication is a post-production operation and cannot invalidate a completed ad.

## Verification

Final main integrated suite: **546 passed, 7 skipped in 246.85 seconds**
(`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q`). Independent review also
passed 153 targeted tests on the initial implementation and all 20 follow-up
submission/schema tests after the final path fix, plus 48 dependency/review tests
on the final delta, with no outstanding findings. These overlapping
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
in `findings.target` instead. Medium-fast then reached its 750-second cap during
real scene/framing repairs and unfinished asset submission. Read-only Blender
inspection reproduced correct placement-root rotation, not an importer defect;
one worker incorrectly assumed +X forward for a saved actor facing -Y.
Normal medium failed research in 60 seconds: three submissions represented
creative_directions as an object instead of a string. The original validation
message did not explain the type, and the retries repeated that error.
High completed in 1,740.07 seconds (29 minutes), including one targeted board
repair, with technical QA and final creative QA passing. The delivered video is
1080x1350, H.264, 24 fps, 216 picture frames and 48 kHz AAC; container duration
is 9.002 seconds including audio padding. Main inspected the frame contact sheet;
listening, acting naturalness and perceptual lip sync remain unverified. The
animator's 540x676 / four-sample render took 77.54 seconds, not the full run.
The successful artifact is `.local/benchmarks/retro-world-v3/videos/20261019-203109-181cbbc7/ad-01.mp4`.

| v3 preset | Terminal result | Observed time | Boundary |
| --- | --- | --- | --- |
| low-fast | failed | 154 s | Direction, before allowance fix |
| high-fast | failed | 1,130 s | Assets, before catalog/handoff repairs |
| low | failed | 587 active s | Board-review output paths; wall time confounded by queue suspension |
| medium-fast | budget_exhausted | 750 s | Scene repairs and incomplete submission |
| medium | failed | 60 s | Research text schema mismatch |
| high | complete | 1,740 s | Automated QA passed; acting/listening not signed off |

These runs were sequential but overlapped implementation and some regression tests.
They are a failure/acceptance ledger, not controlled preset speed comparisons.
One completed high run does not establish reliable low/fast generation. The smaller
presets need fresh, unchanged-code end-to-end trials before a production-ready claim.
Direction now requests a 90/120/180-second attempt floor for low/medium/high,
including fast mode, still limited by the stage ceiling and remaining global
budget. This preserves the hard cap while allowing mandatory local synthesis and
measured-plan assembly. Scene assembly/animation similarly allow 120/180/300
seconds per attempt, still bounded by the same configured/global ceilings.

Follow-up repairs from those live failures: research now receives the complete
plain-string schema, and text-contract errors include an explicit JSON example.
The new `harness.submission` helper stages only explicitly authored existing
scene/board/source/provenance artifacts, refuses unsafe paths and overwrites,
and keeps canonical references synchronized through promotion. It does not open
Blender, inspect images, infer rights/dependencies, or approve the scene.
The assets quickstart requests complete submission before optional polish and
avoids unrelated guide material. Modern assets prompts retain direction and
measured audio paths instead of redundant upstream file/hash inventories;
the inspected trial's upstream JSON shrank from 16,802 to 6,248 characters.
Complete accepted manifests remain authoritative on disk. This is measured
context reduction, not a measured runtime improvement. Quality gates remain intact.

The high run also exposed two final contract issues. Board review's modern prompt
omitted the severity enum; the prompt and compatible error message now enumerate
blocking/important/minor instead of requiring the worker to guess. Blender reported
119 append-origin references despite zero strong libraries and all textures being
packed. Render/publication validators now share an occurrence-counted scan that
subtracts provenance-only weak references without altering the source. A first
set-based version was rejected in review because it hid an IES shader input sharing
the same path; the final multiset regression preserves that real dependency and
rejects it, as well as a same-path linked library. Real appended scenes remain valid
after their origin file is deleted. Full cache hits are still revalidated.

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
| Append provenance | Fully local appended data retained old source paths, blocking render/publication | Shared occurrence-counted scan ignores only weak origin references; real same-path library/IES collisions still reject; real Blender regressions pass |
| Staging | Bone-world assumption and orthographic centering caused earlier failures | Fixed; repeated staging tests reported passing, not proof of live scene success |
| Voice timing | A plan could pass without measured scratch speech or full-file fit | Full selected polished WAV must fit its slot, including pauses/tails; active bounds alone are insufficient; fit regressions covered |
| Review strictness | A pass verdict could coexist with unresolved important defects | Blocking/important findings cannot pass strict review contracts; regression-covered |
| Review artifacts | Board review listed accepted input paths as newly authored files | Common instructions/error guidance require new local outputs only; reviews normally use `files: []`; focused 55-test pass reported |
| Review enum | Modern board-review prompt omitted allowed severity values | Explicit blocking/important/minor options in prompt and compatible error message; no acceptance threshold changed |
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

Acceptance status: **partial**. Implementation and all six v3 terminal outcomes
are recorded; one finished ad passed automated gates. Human listening/comedy review
and fresh successful low/fast trials remain. No test count or remote asset push
substitutes for those checks.
