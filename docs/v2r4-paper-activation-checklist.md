# V2R4 Paper Activation Checklist

Status: **COMPLETED RELEASE RECORD / V2R4 PAPER ACTIVE / NO REAL-MONEY PATH**

## Completion record — 2026-10-08

All release gates were completed and the approved Paper successor was activated as `PAPER-V2R4-20261007T184255Z`. This checklist is now a historical release/rollback record, not a recurring gate. It must not be rerun merely because V2R4 accumulates new evidence. A new release gate is required only for a separately versioned successor or an explicit rollback/re-release. Echtgeld remains unauthorized.

This checklist exists so the later V2R4 paper start is a bounded release operation rather than an improvised set of edits.

It does **not** authorize activation.

## Gate 0 — automatic blockers

Read `public.v2r4_activation_readiness`.

Required before release approval:
- `automatic_activation_allowed = false` must remain false permanently;
- active V2R3 clean series completion gate must be satisfied under
  `EVIDENCE_DIVERSITY_FASTTRACK_V2`;
- clean-series integrity must be `HEALTHY`;
- V2R4 shadow maturity must be archived;
- current MINI-PC status must be fresh / HEALTHY / OK;
- `strategy_release_decisions.final_review_completed_at` must be set only after the completed V2R3 causal review;
- `strategy_release_decisions.migration_review_completed_at` must be set only after every material finding has an explicit successor disposition;
- `strategy_release_decisions.status` must explicitly become `APPROVED_PAPER`.

Until all of these hold, `public.v2r4_activation_readiness` remains blocked/manual.
Even `APPROVED_PAPER` does not activate anything automatically.

If any automatic blocker is present, stop. Do not tune around the blocker.

## Gate 1 — freeze and review V2R3 clean evidence

Final-review control surface:

- `public.v2r3_release_review_snapshot`
- `final_review_allowed` is fail-closed;
- it stays false until the documented completion gate is ready **and** clean-series integrity is `HEALTHY`;
- it bundles timing, direct WAIT-TTL lag, outcome, interim horizon, reason-family and mature missed-move evidence into one read-only row;
- `automatic_strategy_change_allowed=false` is permanent.

Current state at creation: `WAITING_COMPLETION`; no mature 24h missed-move rows yet.


Before changing the active paper strategy:
- snapshot the final active V2R3 series ID and counts;
- wait only until the fixed qualifying cohort reaches the documented maturity/coverage
  floor from the evidence-diversity policy; do not add an arbitrary calendar delay;
- produce the final V2R3 report across BUY/WAIT/REJECT paths;
- include MFE/MAE, edge decay, costs, missed moves, latency chain and data-quality incidents;
- classify findings as strategy / timing-infrastructure / data-quality / technical-runtime / cost;
- record every finding as `CONFIRM`, `CHANGE`, `ADD`, `REJECT`, or `MORE_TESTING_REQUIRED`;
- preserve the clean V2R3 artifacts immutable after closure;
- **before any V2R4 activation mutation**, generate a content-addressed rollback reference with `tools/paper-release-rollback-snapshot.py` and archive it with the release evidence;
- the rollback snapshot must validate the active V2R3 freeze manifest and exact strategy/runtime fingerprints before it is accepted.

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

### Binding sizing decision

Decision memo: `docs/v2r4-sizing-release-decision.md`
Binding machine contract: `research/v2r4/paper_strategy_spec_v2r4_release_candidate.json`

For the **first full V2R4 Paper series**, sizing is fixed at **50 EUR scout + 50 EUR stage 2**, inherited from V2R3. This isolates the timing/discovery/revalidation hypothesis.

Adaptive setup-quality sizing is explicitly deferred to a later, separately versioned experiment. No 75+75 or adaptive tier may enter the first V2R4 series merely because it appeared in earlier smoke preparation.

## Gate 3 — code candidate

The former Draft-PR #9 is superseded/closed and must not be revived.

Before release:
- materialize and validate the fresh V2R4 candidate from the cleaned current `main` against the binding machine contract;
- ensure the diff contains only the intended V2R4/release changes;
- first full-series sizing must be 50+50 EUR;
- runtime evidence destination must be Supabase/bounded MINI-PC state, never high-frequency `main` commits;
- shared Kraken execution/market semantics must import the canonical `market_data` layer;
- rerun V2R4 validation and only the smokes whose relevant implementation changed;
- no active V2R3 state files may be unintentionally changed;
- real-money/order flags must remain false.

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
3. restore only the protected code/configuration files identified by the last-known-good rollback snapshot; **never reset the whole repository** because paper evidence/state continues to evolve;
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
