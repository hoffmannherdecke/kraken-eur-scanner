# V2R4 Paper Activation Checklist

Status: **PREPARED CHECKLIST / NOT AUTHORIZED / NO REAL-MONEY PATH**

This checklist exists so the later V2R4 paper start is a bounded release operation rather than an improvised set of edits.

It does **not** authorize activation.

## Gate 0 — automatic blockers

Read `public.v2r4_activation_readiness`.

Required before entering a manual release review:
- `activation_review_state = MANUAL_RELEASE_REVIEW_REQUIRED`
- `automatic_activation_allowed = false` must remain false
- active V2R3 clean series completion gate must be satisfied
- V2R4 shadow maturity must be archived
- current MINI-PC status must be fresh / HEALTHY / OK

If any automatic blocker is present, stop. Do not tune around the blocker.

## Gate 1 — freeze and review V2R3 clean evidence

Before changing the active paper strategy:
- snapshot the final active V2R3 series ID and counts;
- wait for all required 24h follow-ups to mature to the documented coverage floor;
- produce the final V2R3 report across BUY/WAIT/REJECT paths;
- include MFE/MAE, edge decay, costs, missed moves, latency chain and data-quality incidents;
- classify findings as strategy / timing-infrastructure / data-quality / technical-runtime / cost;
- record every finding as `CONFIRM`, `CHANGE`, `ADD`, `REJECT`, or `MORE_TESTING_REQUIRED`;
- preserve the clean V2R3 artifacts immutable after closure.

Do not use the compromised predecessor series as promotion evidence.

## Gate 2 — explicit V2R4 behavior diff

Review `docs/v2r4-v2r3-release-diff.md`.

Required:
- no undocumented mechanical difference;
- live Kraken `AssetPairs` remains the operational tradability source;
- WAIT trigger match remains only `FRESH_PAPER_RECHECK_ONLY`;
- no direct order path;
- reconnect/stale/dedup guardrails remain enabled;
- pre-candidate discovery remains discovery/review, not a buy rule.

### Mandatory sizing decision

Prepared decision memo: `docs/v2r4-sizing-release-decision.md`

The current proposal contains an unresolved sizing confounder.

Choose and version **one** approach before activation:

**A. Timing-isolation series**
- retain V2R3 paper sizing for the first V2R4 series;
- test timing/discovery/revalidation changes first;
- adaptive sizing becomes a later separately versioned experiment.

**B. Combined timing+sizing series**
- first implement a deterministic, tested setup-quality sizing mapper;
- freeze the mapper in the V2R4 spec;
- accept that comparison against V2R3 combines timing/discovery and sizing effects.

No implicit fallback to 75+75 is allowed for a full series merely because that value was used in E2E smoke preparation.

## Gate 3 — code candidate

Before merge:
- refresh Draft-PR #9 onto the then-current `main` once, at the actual release boundary;
- ensure the diff contains only the intended V2R4/release changes;
- rerun V2R4 PR validation;
- compile/unit/model-contract/public-Kraken smokes must pass;
- no active V2R3 state files may be unintentionally changed by the PR;
- real-money/order flags must remain false.

Do not continuously rebase PR #9 during data collection just because paper-state commits move `main`.

## Gate 4 — create a new immutable paper series

Use a **new** series and test ID. Never rewrite the closed V2R3 series into V2R4.

The activation change must explicitly set:
- new `series_id`;
- new `test_id`;
- frozen `strategy_revision`;
- exact UTC `series_started_at_utc`;
- `paper_only=true`;
- `real_money_actions_enabled=false`;
- target completed paper trades;
- predecessor/reference V2R3 series ID;
- exact strategy fingerprint and runtime fingerprint provenance.

Do not reuse an earlier diagnostic or shadow series ID.

## Gate 5 — one small end-to-end release smoke

Prepared physical real-transport harness:

- `tools/minipc-v2r4-real-altrady-release-smoke.ps1`
- plan-only by default;
- requires an explicitly confirmed execute token;
- consumes only a **recent real MINI-PC Altrady transport event**;
- maps that event to current public online Kraken Spot-EUR;
- creates all candidate/WAIT/recheck state in an isolated temp tree;
- Altrady is wake-up only; fresh Kraken public data is the condition truth;
- performs one isolated fresh PAPER recheck and then proves idempotency;
- never mutates the active V2R3 series or live V2R4 state;
- no private Kraken API, order path or real-money action.

This converts the remaining physical combined Altrady→Kraken release proof into one bounded command once a fresh real Altrady event is available.


After the release candidate exists but before broad collection:
- one harmless candidate/trigger path;
- deterministic trigger receipt;
- fresh Kraken recheck;
- paper-only decision;
- persistence to the new series;
- no duplicate evaluation on immediate repeat;
- watchdog/effectiveness healthy;
- Supabase archive sees the new series;
- Slack only if a defined actionable/important event occurs;
- no order/account/private Kraken write action.

If the smoke fails, roll back before collecting a large cohort.

## Gate 6 — MINI-PC local sync

At the actual release boundary:
- MINI-PC repository must be on `main`;
- working tree must be clean;
- use fast-forward-only pull;
- run the bundled read-only post-fix/effectiveness verification;
- verify canary, universe, WS-shadow, outcomes, supervisor, status-sync and Altrady transport;
- verify local time/network health;
- no drive-D dependency.

Repository-side watchdog jitter/taxonomy hardening should be included in this single planned local sync instead of interrupting evidence collection beforehand.

## Gate 7 — start V2R4 paper collection

Only after Gates 0–6:
- enable the new V2R4 **paper** series;
- keep real-money disabled;
- archive the release SHA/spec fingerprint;
- start completion/provenance monitoring;
- compare against frozen V2R3 evidence using predeclared metrics;
- no mid-series threshold/entry/stop/sizing edits.

If a rule must change, stop/freeze the series and create a new version.

## Rollback plan

Rollback is technical, not a strategy retune.

If V2R4 release smoke/runtime is unhealthy:
1. disable the new V2R4 paper runtime;
2. leave already-written V2R4 evidence intact and mark the series technical/diagnostic as appropriate;
3. restore the last-known-good paper runtime/code configuration;
4. keep Kraken/health/shadow transport read-only paths running where safe;
5. reconcile queue/TTL/persistence before any restart;
6. do not silently append post-rollback data to a supposedly homogeneous failed V2R4 series.

A rollback does not automatically reopen or extend the completed V2R3 clean series.

## Echtgeld boundary

Nothing in this checklist authorizes:
- private Kraken trading rights;
- live orders;
- leverage;
- withdrawal rights;
- automatic capital scaling.

Those remain a separate later execution-security program.
