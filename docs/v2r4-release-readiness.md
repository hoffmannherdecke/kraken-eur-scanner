# V2R4 Release Readiness

Status: **PREPARED / NOT ACTIVE / PAPER ONLY**

This document is the compact release-readiness control point for V2R4. It does not replace `docs/strategy-version-map.md`, the V2R3 completion gate, or the Mini-PC runbook.

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

Scanner matching is still sparse and must not be used as a winner ranking:

- shadow events in match-quality view: **353**
- same-pair scanner match within 30m: **22**
- within 15m: **17**
- within 5m: **7**
- temporal proximity is not proof of the same impulse

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

1. keep V2R3 clean series frozen and collecting;
2. keep V2R4 shadow/outcome evidence collecting without evaluator/orders;
3. keep PR #9 draft and periodically reconcile it with `main` only when needed;
4. verify the watchdog/taxonomy repair in CI;
5. prepare one bundled local MINI-PC pull + effectiveness verification command;
6. wait for sufficient clean V2R3 maturity before any activation review.

A V2R4 paper activation decision is a separate explicit gate and must never be inferred from technical green status alone.


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


## MINI-PC watchdog false-stale hardening — repository verified

A transient remote sample had reported `WARNING / FEED_STALE` while the underlying Kraken source was fresh. The repository fix is now CI-verified:

- harmless V2R4 watcher heartbeat scheduling jitter gets up to 30 s;
- underlying Kraken source freshness remains strict at 15 s;
- `FEED_STALE` is reserved for Kraken canary/universe source failures;
- shadow/outcome support-process failures classify as `DEGRADED` when source transport is still healthy;
- MINI-PC tools smoke **#99 SUCCESS** for heartbeat tolerance;
- MINI-PC tools smoke **#100 SUCCESS** for the taxonomy correction.

A subsequent centrally observed MINI-PC sample returned naturally to **HEALTHY / OK / issues none** with Kraken canary, universe feed, WS-shadow, outcome tracker, cloud sync, Altrady transport and runtime supervisor all healthy.

The local MINI-PC repository had not yet pulled these final repository-side watchdog refinements at the time of that sample. They remain a low-risk bundled local pull + effectiveness verification for the next genuine local maintenance gate; there is no need to interrupt the running evidence collection solely for this.
