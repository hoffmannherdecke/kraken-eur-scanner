# V2R4 Release Readiness

Status: **PREPARED / NOT ACTIVE / PAPER ONLY**

This document is the compact release-readiness control point for V2R4. It does not replace `docs/strategy-version-map.md`, the V2R3 completion gate, the Mini-PC runbook, the explicit behavior matrix in `docs/v2r4-v2r3-release-diff.md`, the sizing decision memo in `docs/v2r4-sizing-release-decision.md`, or the release/rollback sequence in `docs/v2r4-paper-activation-checklist.md`.

## Current code candidate

- active preparation PR: **Draft-PR #9**
- old PR #8: superseded/closed because the branch had drifted 995 commits behind `main`
- PR #9 reproduces the same 21-file V2R4 delta on top of current `main`
- V2R4 PR validation **Run #11: SUCCESS**
- safety boundary remains paper-only; no private Kraken order path and no real-money activation

## Existing technical gates

Verified before any V2R4 paper activation:

- broad Kraken Spot-EUR realtime feed on the MINI-PC
- live Kraken `AssetPairs` universe, not a static whitelist/blacklist
- WS-shadow physical smoke
- restart / Internet-recovery evidence for shadow transport
- deterministic WAIT trigger contract
- trigger -> fresh paper recheck E2E
- Altrady transport E2E as an additional, non-exclusive trigger
- GitHub cloud path remains independent fallback
- Slack push path separately verified
- no order API / no real-money path
- inactive bounded WAIT-plan lifecycle runtime prepared in PR #9; Kraken remains condition truth, Altrady is wakeup-only; PR validation **Run #14 SUCCESS**
- refreshed trigger→fresh-recheck E2E workflow points to PR #9 and **Run #2 SUCCESS**

## Evidence snapshot — 2026-10-01 15:01 UTC

### V2R3 clean control series

Series: `PAPER-V2R3-CLEAN-20261001T0925Z`

- Candidate-Outcomes: **48**
- completed trades: **0**
- BUY_SCOUT: **0**
- current final decisions: **7 WAIT / 41 REJECT**
- integrity state: **HEALTHY**
- duplicate candidate IDs: **0**
- missing queue/timing/ticker/fingerprint provenance: **0**
- distinct strategy fingerprints: **1**
- distinct runtime fingerprints: **1**
- 24h-mature candidates: **0**
- completion gate: **NOT READY / COLLECTING_AGE**
- alternative gate remaining at this snapshot: **952 outcomes** and about **162.4 hours** to the 7-day age floor

Runtime timing at this snapshot:

- WAIT p50 detection -> evaluation complete: **36.882 s**
- WAIT p90: **44.116 s**
- REJECT p50: **37.739 s**
- REJECT p90: **56.034 s**
- no clean-series case above 300 s
- this is a major improvement versus the compromised predecessor's persistence-driven severe latency tail, but it is not strategy-performance evidence

### V2R4 WS-shadow operational evidence

- total shadow events: **353**
- prospective post-tracker events: **335**
- due 6h outcomes: **34**
- completed due 6h outcomes: **34**
- unresolved due 6h outcomes: **0**
- current 6h archival coverage: **100%**
- operational readiness state: **MATURE_COHORT_ARCHIVED**
- complete outcomes with no tracker gap: **16**
- complete outcomes marked tracker-gap-affected: **18**
- feed -> shadow latency p50: **~2.04 s**
- feed -> shadow latency p90: **~3.63 s**

A separate fail-closed comparison control is now available as `public.realtime_path_comparison_readiness`; it reports sample sufficiency and keeps `ranking_allowed=false` until event identity and sample size are genuinely adequate.

Scanner matching is still sparse and must not be used as a winner ranking:

- shadow events in match-quality view: **353**
- same-pair scanner match within 30m: **22**
- within 15m: **17**
- within 5m: **7**
- temporal proximity is not proof of the same impulse

## Continuous WAIT runtime readiness

The readiness review found that the existing single-plan watcher and trigger→fresh-recheck E2E proved the mechanics but did not yet define the full 24/7 plan lifecycle. Draft-PR #9 now prepares that missing runtime shape without activating it.

Prepared in PR #9:

- `paper_evaluator/v2r4_wait_runtime.py`
- `tests/test_v2r4_wait_runtime.py`

Contract:

- discovers persisted initial and chained WAIT trigger plans;
- normal fallback Kraken checks continue even if Altrady is silent;
- locally consumed Altrady events may only wake the same pair for an earlier Kraken check;
- Altrady data can never satisfy a trigger condition by itself;
- trigger match can only request one `FRESH_PAPER_RECHECK_ONLY`;
- handled plans are idempotent;
- recheck failure fails closed rather than auto-hammering the model;
- long-running mode requires an explicit executable-paper flag;
- no private Kraken API, order method or real-money action exists;
- no scheduled task has been installed and nothing is active.

Validation:

- MINI-PC V2R4 WAIT runtime smoke **Run #1: SUCCESS** on a Windows-shaped runner;
- one local Altrady wakeup hint caused exactly one same-pair Kraken condition check and one fresh paper recheck;
- trigger -> recheck start in that bounded smoke: **0.002 s**;
- second run on identical state produced **0 duplicate rechecks** (`IDEMPOTENT_PASS`);
- heartbeat proved `kraken_public_is_condition_truth=true`, `altrady_role=WAKEUP_HINT_ONLY`, `strategy_action=FRESH_PAPER_RECHECK_ONLY`, `order_api=false`, `real_money_actions=false`;

- V2R4 PR validation **Run #14: SUCCESS**, including the new runtime tests;
- refreshed trigger→fresh-recheck E2E **Run #2: SUCCESS** against PR #9.

Real-transport release harness preparation:

- `tools/v2r4-real-altrady-release-smoke.py`
- `tools/minipc-v2r4-real-altrady-release-smoke.ps1`
- plan-only by default; explicit execute token required;
- temp worktree/temp runtime only; active V2R3/live V2R4 state is not mutated;
- helper compile + PowerShell parse + plan guardrails are covered by **MINI-PC tools smoke Run #111: SUCCESS**;
- an earlier CI Run #110 failed only because the Python helper was accidentally included in the PowerShell parser file list; this CI wiring defect was corrected immediately and did not affect runtime/strategy state.

Still required at the actual release boundary:

- physical combined Altrady-wakeup → Kraken-fresh-condition → paper-recheck smoke;
- final directory/control/series wiring for the new immutable V2R4 paper series;
- no activation before the V2R3 release review and explicit sizing/release decision.

## V2R3 clean-series freeze guard

To prevent accidental contamination while the clean control series is still collecting, the repository now contains an explicit fail-closed freeze contract:

- manifest: `research/v2r3/clean-series-freeze-20261001.json`
- validator: `tools/validate-v2r3-clean-series-freeze.py`
- workflow: `.github/workflows/v2r3-clean-series-freeze-guard.yml`
- first validation: **Run #1 SUCCESS**

The guard verifies:

- exact active series/test/strategy revision;
- frozen strategy-spec fingerprint;
- frozen evaluator/revalidator/context runtime fingerprint;
- frozen legacy scanner package checksum;
- frozen 10-minute scanner cadence and scanner runtime settings.

It intentionally allows documentation, observability and inactive V2R4 preparation, but it makes any silent V2R3 entry/stop/sizing/scanner/cadence drift visible immediately.

The freeze must be retired or replaced explicitly after the documented V2R3 completion/release review; expected hashes must not be silently rewritten while the series is active.

## V2R3 final-review evidence pack

A single fail-closed Supabase evidence surface is now prepared for the eventual completion boundary:

- `public.v2r3_release_review_snapshot`
- current `review_state = WAITING_COMPLETION`
- current `final_review_allowed = false`
- current integrity = `HEALTHY`
- mature 24h missed-move rows = **0** at creation time
- `automatic_strategy_change_allowed = false`

Once the completion gate matures, this view will expose the already-versioned clean evidence in one place without changing the active series: initial timing, WAIT-TTL lag, outcomes, horizon summaries, reason families and mature missed-move candidates. It reduces the later release review to evidence classification rather than fresh data plumbing.

## Current blocker to V2R4 activation review

The technical preparation is largely green, but the **V2R3 clean control series has not matured enough for the mandatory release review**.

Specifically:

1. no clean V2R3 candidate has a mature 24h follow-up yet;
2. therefore the required BUY/WAIT/REJECT, MFE/MAE, missed-move, cost and latency review cannot yet be completed on the clean series;
3. the formal V2R3 completion gate is still collecting;
4. V2R4 shadow outcome data is operational evidence only and cannot substitute for the V2R3 strategy review.

Therefore V2R4 remains **NOT ACTIVE**. No threshold, entry, stop, sizing or real-money change is authorized by this snapshot.

## MINI-PC health note found during readiness review

A remote status sample marked the MINI-PC `WARNING / FEED_STALE` solely because the V2R4 shadow watcher heartbeat was **18.3 s** old while:

- status was `DUPLICATE_SKIPPED`
- its underlying source age was only **1.679 s**
- Kraken universe heartbeat was healthy
- Kraken canary was healthy
- outcome tracker was healthy

This was classified as a health-taxonomy / jitter false positive, not a proven Kraken feed outage.

Repository-side repair prepared on 2026-10-01:

- watcher-heartbeat tolerance widened from 15 s to 30 s while keeping underlying source freshness strict at 15 s;
- `FEED_STALE` is now reserved for underlying Kraken canary/universe failures;
- shadow/outcome support-process issues fall through to `DEGRADED` when Kraken source transport remains healthy;
- MINI-PC tools smoke for the first tolerance change passed; final taxonomy change remains subject to the same CI/local verification path.

No strategy logic was changed.

## Next actions before user input is needed

Repository-side preparation is now complete for the current maintenance/release-readiness block:

- refreshed V2R4 candidate preflight now targets PR #9 by default;
- MINI-PC V2R4 local preflight smoke **Run #4: SUCCESS** against the refreshed candidate;
- bundled safe local sync/readiness script exists at `tools/minipc-v2r4-readiness-sync.ps1`;
- its plan-only/guardrail smoke is CI-green in MINI-PC tools smoke **Run #103: SUCCESS**;
- watchdog/taxonomy fixes are repository-verified and do not require interrupting evidence collection.

Until a genuine local maintenance or release gate is reached, continue without user action:

1. keep V2R3 clean series frozen and collecting;
2. keep V2R4 shadow/outcome evidence collecting without evaluator/orders;
3. keep PR #9 draft; do not churn/rebase it merely because runtime-state commits move `main`;
4. monitor the fail-closed Supabase activation-readiness view;
5. wait for sufficient clean V2R3 maturity before any activation review.

At the eventual local maintenance/release boundary, use one bundled pull + read-only effectiveness/preflight/restore verification rather than piecemeal MINI-PC edits.

A V2R4 paper activation decision is a separate explicit gate and must never be inferred from technical green status alone.


## Latest control snapshot — 2026-10-01 15:53 UTC

This later snapshot supersedes the earlier same-day counts for operational status only; it does not replace the frozen release rules above.

### V2R3 clean series

- Candidate-Outcomes: **56**
- completed trades / BUY_SCOUT: **0 / 0**
- final decisions: **6 WAIT / 50 REJECT**
- integrity: **HEALTHY**
- duplicate candidate IDs: **0**
- missing queue/timing/ticker/fingerprint provenance: **0**
- distinct strategy/runtime fingerprints: **1 / 1**
- 24h-eligible outcomes: **0**
- completion gate: **COLLECTING_AGE**
- remaining to alternate outcome floor: **944**
- remaining to 7-day age floor: about **161.5 h**

Timing at this snapshot:
- WAIT p50 / p90 total latency: **31.98 s / 43.72 s**
- REJECT p50 / p90: **37.31 s / 54.98 s**
- no case above **300 s**

### V2R4 shadow operational evidence

- total shadow events: **372**
- prospective post-tracker events: **354**
- due 6h: **95**
- completed due 6h: **95**
- unresolved due 6h: **0**
- current due-6h archival coverage: **100.00%**
- due-6h cohort fully archived; current operational state: **MATURE_COHORT_ARCHIVED**
- feed -> shadow latency p50: **~1.65 s**
- feed -> shadow latency p90: **~3.12 s**

The currently due 6h cohort is fully archived. This remains an operational-maturity fact, not strategy-performance evidence.

### MINI-PC / activation control

- latest centrally observed MINI-PC: **HEALTHY / OK / issues none**
- Kraken canary, Kraken universe, WS shadow, outcome tracker, cloud sync, Altrady transport and runtime supervisor were healthy
- fail-closed activation view: **BLOCKED_V2R3_COMPLETION**
- `automatic_activation_allowed = false`

This snapshot confirms that the current blocker is **V2R3 clean-series maturity**, not V2R4 shadow archival maturity and not an active infrastructure failure.

## Supabase / analytics hardening — 2026-10-01

The release-readiness review also exposed a database-linter issue that was independent of strategy performance:

- five analytics/readiness views were flagged as owner-permission / security-definer views;
- all five repository view definitions now explicitly use `security_invoker=true`;
- the matching Supabase migration was applied;
- security advisor recheck: **no remaining security-definer-view ERROR**;
- the remaining `RLS enabled, no policy` notices are INFO-level and intentional for the current server-only/fail-closed tables; no anonymous/client policy was added merely to silence the advisor;
- one unused-index performance INFO remains and is not a release blocker.

Affected views:
- `public.v2r3_clean_integrity_summary`
- `public.v2r3_interim_horizon_summary`
- `public.v2r4_shadow_completion_readiness`
- `public.v2r4_shadow_outcome_metrics`
- `public.v2r4_shadow_scanner_match_quality`

This was an infrastructure/security hardening change only; no strategy rule, score, threshold, stop, sizing or order path changed.


## Additional WS-shadow support-process recovery sample — 2026-10-01 16:44–16:54 UTC

A later status sample again showed the local **old-revision** watchdog as `WARNING / FEED_STALE` because the WS-shadow support heartbeat had stopped advancing for about 10 minutes. During that window:

- Kraken canary remained healthy;
- Kraken universe remained healthy at full coverage;
- outcome tracker remained healthy;
- cloud sync and Altrady transport remained healthy;
- no real-money/order path existed.

By 16:54 UTC, without user intervention:

- MINI-PC returned to **HEALTHY / OK / issues=[]**;
- WS-shadow heartbeat resumed at age ~0 s;
- source age was ~2.4 s;
- shadow event count advanced again;
- runtime supervisor was HEALTHY.

This is retained as a short operational evidence gap, not strategy-performance evidence. It also confirms that no emergency user action was required. The repository-side jitter/taxonomy hardening remains queued for the single planned local sync rather than interrupting the clean V2R3 series.

## MINI-PC watchdog false-stale hardening — repository verified

A transient remote sample had reported `WARNING / FEED_STALE` while the underlying Kraken source was fresh. The repository fix is now CI-verified:

- harmless V2R4 watcher heartbeat scheduling jitter gets up to 30 s;
- underlying Kraken source freshness remains strict at 15 s;
- `FEED_STALE` is reserved for Kraken canary/universe source failures;
- shadow/outcome support-process failures classify as `DEGRADED` when source transport is still healthy;
- MINI-PC tools smoke **#99 SUCCESS** for heartbeat tolerance;
- MINI-PC tools smoke **#100 SUCCESS** for the taxonomy correction.

A subsequent centrally observed MINI-PC sample returned naturally to **HEALTHY / OK / issues none** with Kraken canary, universe feed, WS-shadow, outcome tracker, cloud sync, Altrady transport and runtime supervisor all healthy.

The bundled local maintenance sync was subsequently completed successfully on 2026-10-01. The MINI-PC fast-forwarded cleanly to `29cafc3d4479604c0ec549b43f9de91ba6007d91`, and the post-pull watchdog-effectiveness, V2R4 preflight and backup-restore checks all passed. Later routine/runtime commits may move `main` again; that alone is not a reason to interrupt evidence collection. A final release-boundary fast-forward/readiness verification remains appropriate immediately before any V2R4 paper activation review.


## Activation-control integrity hardening

The fail-closed Supabase release-control view now also consumes `public.v2r3_clean_integrity_summary`.

New behavior:

- completion readiness alone is no longer sufficient to reach manual release review;
- if the clean V2R3 series is not `HEALTHY`, the view returns `BLOCKED_V2R3_INTEGRITY`;
- the view exposes duplicate candidate/queue counts and distinct strategy/runtime fingerprint counts;
- `automatic_activation_allowed` remains hard-coded `false`.

This means a future completion-gate pass cannot accidentally route to manual release review if the prospective clean-series integrity has drifted.

## Fail-closed activation control view

Supabase now exposes `public.v2r4_activation_readiness` as a compact read-only control plane.

It combines:
- the active V2R3 completion gate;
- V2R4 shadow 6h operational maturity;
- the latest MINI-PC health sample.

Important semantics:
- `automatic_activation_allowed` is hard-coded **false**;
- the view can only block or route to `MANUAL_RELEASE_REVIEW_REQUIRED`;
- it can never authorize or perform activation;
- the first blocking condition is currently `BLOCKED_V2R3_COMPLETION`.

At creation-time snapshot:
- V2R3: 48 clean outcomes, 0 completed trades, 0 mature 24h outcomes, `COLLECTING_AGE`;
- V2R4 shadow: 343 prospective events, 47/47 due 6h outcomes archived, 100% 6h coverage;
- MINI-PC: an old local watchdog revision intermittently still labels harmless WS-shadow heartbeat jitter as `FEED_STALE`, while Kraken canary/universe remain fresh. The repository correction is CI-green but has intentionally not interrupted evidence collection for a local pull yet.

This view is a release-safety guard, not strategy-performance evidence.


## Latest verified control snapshot — 2026-10-01 16:55 UTC

Direct Supabase control-plane verification at **2026-10-01 16:55:58 UTC**:

### V2R3 clean series
- series: `PAPER-V2R3-CLEAN-20261001T0925Z`
- Candidate-Outcomes: **64**
- completed trades / BUY_SCOUT: **0 / 0**
- final decisions: **6 WAIT / 58 REJECT**
- integrity: **HEALTHY**
- duplicate candidate IDs / duplicated queue IDs: **0 / 0**
- distinct strategy/runtime fingerprints: **1 / 1**
- 24h-eligible / complete: **0 / 0**
- completion gate: **COLLECTING_AGE**
- remaining to alternate outcome floor: **936**
- remaining to 7-day age floor: **160.48 h**

### V2R4 shadow
- total events: **407**
- prospective events: **389**
- due 6h: **141**
- completed due 6h: **138**
- unresolved due 6h: **3**
- 6h archival coverage: **97.87%**
- readiness state: **MATURE_OUTCOMES_PENDING**

The unresolved rows are current cohort maturation/archival lag, not evidence of a strategy fault.

### MINI-PC / activation control
- latest MINI-PC observation: **2026-10-01 16:54:26 UTC**
- centralized state: **HEALTHY / OK**
- status age at verification: **1.53 min**
- activation review state: **BLOCKED_V2R3_COMPLETION**
- `automatic_activation_allowed = false`

A transient local `WARNING / FEED_STALE` sample immediately before this observation self-cleared without intervention. Together with fresh Kraken-source evidence, this remains consistent with the already-known older local watchdog/shadow-heartbeat false-stale classification rather than a Kraken transport outage. The repository-side watchdog/readiness hardening remains queued for the next bundled local sync; no interruption of the running evidence collection is warranted solely for this.

### Draft-PR #9 drift handling
At this snapshot the refreshed V2R4 draft branch is **29 commits ahead / 115 commits behind** `main`, and GitHub currently reports `mergeable=false`. The connector does not expose a reliable conflict reason here, so this must not be interpreted as a proven code conflict solely from the commit counts. Because runtime/evidence commits continue moving `main`, per the existing release rule do **not** churn/rebase merely to keep the draft cosmetically current. Final branch sync and any required conflict resolution belong at the actual activation-review boundary, after V2R3 completion and before any merge decision.

## Physical bundled MINI-PC readiness sync — 2026-10-01 17:26 UTC

The planned local maintenance/readiness gate was completed successfully without activating V2R4.

Verified sequence:
- the only dirty-tree blocker was an untracked `.paper-work/runtime-reconciliation-audit.json` produced by the existing read-only reconciliation audit;
- that artifact was confirmed to be reproducible diagnostic output, removed locally, and `.paper-work/` was added to `.gitignore` so the same harmless artifact cannot block future safe syncs;
- the pre-sync MINI-PC HEAD `89acd285a080b0b8a40e03313de3fc2264350003` was proven to be a direct ancestor of current `main` with **123 commits ahead on main / 0 divergent**;
- the MINI-PC was fast-forwarded cleanly to `29cafc3d4479604c0ec549b43f9de91ba6007d91`;
- bundled readiness summary: **PASS**;
- post-pull helper verification: **PASS**;
- watchdog effectiveness: **PASS**;
- isolated V2R4 preflight: **PASS**;
- backup restore smoke: **PASS**;
- guardrails remained false for strategy change, paper activation, evaluator activation, private Kraken API, orders and real-money actions.

The first centralized status upload after the pull showed the intended taxonomy correction in effect:
- Kraken canary: **HEALTHY**;
- Kraken universe: **HEALTHY**, 501/501 observed;
- runtime supervisor: **HEALTHY**;
- WS-shadow support heartbeat temporarily exceeded its 30 s process-heartbeat tolerance while its underlying Kraken source remained ~1.6 s fresh;
- operational health therefore classified as **DEGRADED**, not `FEED_STALE`.

This is the expected fail-safe distinction: support-process lag does not masquerade as a Kraken transport outage when the source feed is fresh.

At the same control point, the V2R4 shadow due-6h cohort had fully archived again (**172/172, 100%**), while V2R3 remained **HEALTHY / COLLECTING_AGE** and activation stayed **BLOCKED_V2R3_COMPLETION**.

No further local MINI-PC action is required for this maintenance block. The remaining physical V2R4 release proof is the separate real-transport Altrady-wakeup → Kraken-fresh-condition → paper-recheck smoke at the actual release boundary, followed by the normal final fast-forward/readiness verification if `main` has advanced.

