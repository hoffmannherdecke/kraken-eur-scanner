# V2R4 fast-trigger / Mini-PC preparation

Status: **PREPARED, NOT ACTIVE**

This preparation must not change the active V2R3 series. V2R3 remains the control.
V2R4 is a separate future paper series. A Mini-PC end-to-end smoke is necessary but
**never sufficient** for activation. The binding release sequence is the fail-closed
V2R3 completion/integrity/final-review/migration gate plus mature V2R4 shadow evidence,
healthy MINI-PC state and an explicit APPROVED_PAPER release decision.

## Research conclusion behind V2R4

The current V2R3 evidence does not support broadly relaxing the entry filters.
Most candidates did not produce enough immediate upside after Kraken costs.

The stronger hypothesis is narrower:

> V2R3 can identify useful WAIT setups, but one-shot TTL revalidation can miss a
> valid trigger that occurs between the initial evaluation and the later recheck.

Therefore V2R4 changes **timing/monitoring first**, not general risk appetite.

## Core design

### 1. WAIT becomes an actively watched state

A V2R4 WAIT decision must emit a small machine-readable trigger plan.
The plan contains only deterministic conditions such as:

- price / bid / ask above or below a threshold;
- 1m, 5m or 15m closed candle above a level;
- closed-candle volume ratio above a defined minimum;
- spread below a maximum.

Free-text conditions remain useful for explanation but are not sufficient for the
local watcher.

### 2. The Mini-PC watches cheap public data locally

Preferred runtime after setup:

- Kraken public data = primary truth source;
- local deterministic watcher = normal trigger detection;
- Altrady = optional additional wake-up source only;
- periodic Kraken fallback polling remains active even if Altrady is silent;
- GitHub scheduled workflows are not timing-critical for the fast path.

Initial target polling interval: **10 seconds**, with a supported floor of 5 seconds.
The interval can later be tuned from measured reliability / rate-limit evidence.

### 3. Trigger match never equals buy

A deterministic trigger match performs only:

`FRESH_PAPER_RECHECK_ONLY`

The fresh recheck must again obtain current Kraken EUR execution data and apply:

- liquidity / spread;
- structural stop viability;
- cost-adjusted remaining edge;
- late-chase protection;
- public Kraken tradability / minimum-order gate;
- market state and supporting derivatives context.

Only that fresh paper evaluation may create BUY_SCOUT.

This keeps the improvement focused on **latency**, not removal of safety gates.

### 4. Preserve the two-stage entry; first full series uses fixed 50+50 EUR

The first full V2R4 Paper series **must** use the V2R3 comparison sizing:
50 EUR scout + 50 EUR Stage 2. This isolates the timing/discovery/revalidation
hypothesis and prevents sizing from becoming a confounder.

The older 75+75 smoke default and adaptive research tiers are not part of this release.
Adaptive setup-quality sizing remains a separate, later, explicitly versioned experiment.

The second stage always requires an explicit confirmation trigger. Position size must
not be increased merely to reach a nominal target, and late chasing remains prohibited.

See `docs/v2r4-sizing-release-decision.md` on `main` for the release decision memo.

## Role of broader context in V2R4

The proposal records the following research hypothesis for later validation:

- major-market regime: state / risk scaler, not an automatic veto by itself;
- derivatives: supporting context, not mandatory for every setup;
- coin-specific catalyst: positive evidence when present, but not mandatory for a
  technically strong setup;
- missing data: stays explicitly missing and is never fabricated.

These are proposed hypotheses, not proven improvements. They must be validated in a
new versioned paper series and compared with V2R3.

## Binding V2R4 activation sequence

Technical setup and smoke tests are prerequisites only. The release order is:

1. Keep V2R3 frozen while its evidence-diversity collection continues.
2. Stop new V2R3 intake automatically when its sample/temporal-diversity collection gate is met.
3. Let the frozen V2R3 cohort finish required 24h maturity/follow-up.
4. Require V2R3 integrity = HEALTHY.
5. Complete the final V2R3 causal review.
6. Give every material finding an explicit predecessor→successor migration disposition.
7. Require V2R4 shadow/runtime maturity and current MINI-PC HEALTHY/OK.
8. Record `final_review_completed_at` and `migration_review_completed_at` in the
   backend-only strategy release record.
9. Record an explicit `APPROVED_PAPER` decision.
10. Only then create/start a **new immutable V2R4 Paper series**.

`automatic_activation_allowed=false` is permanent. A green smoke test never starts
V2R4 by itself.

Runtime evidence for this and later strategy generations belongs in Supabase and
bounded MINI-PC state. High-frequency runtime evidence must not be committed to
GitHub `main`.

## Required measurements

V2R4 must log at least:

- candidate detection -> initial evaluation latency;
- WAIT creation -> trigger detection latency;
- trigger detection -> fresh recheck latency;
- trigger detection -> BUY_SCOUT latency when applicable;
- trigger-to-buy rate;
- false-trigger rate;
- MFE / MAE at 30, 60, 120 and 360 minutes;
- realized paper P&L after fees, spread and slippage;
- win rate, profit factor and expectancy;
- number of opportunities rejected for late-chase reasons.

## Discovery examples and overfitting guard

CRV and ICP cases that motivated this work are **discovery examples**.
They must not be treated as independent validation evidence for V2R4.
The new version must prove itself prospectively on new candidates.

All future threshold / feature changes must be recorded as separate tested variants
under the existing search-accounting discipline.

## Files in this preparation

- `research/v2r4/paper_strategy_spec_v2r4_proposed.json`
- `paper_evaluator/v2r4_trigger_contract.py`
- `paper_evaluator/v2r4_wait_watcher.py`
- `tests/test_v2r4_trigger_contract.py`

Nothing in this preparation is wired into the active V2R3 workflow.

## Ongoing research intake before Mini-PC activation

New findings discovered while V2R3 continues may be added to this V2R4 preparation,
but only as explicitly documented hypotheses. Any change that alters entry, exit,
sizing, trigger, state handling or cost assumptions must be versioned before it is
tested; the active V2R3 control remains untouched.

This allows the preparation to improve before Mini-PC activation without silently
rewriting the live comparison series.


## Pre-candidate blind-spot lane

The KSM / TRAC review on 2026-09-30 exposed a separate problem from WAIT latency:
a pair can produce a multi-hour move yet never reach the evaluator because the
liquidity filter is applied before candidate visibility.

V2R4 therefore separates **discovery** from **execution eligibility**.

- Discovery watches all Kraken EUR spot pairs and does not require EUR 150k turnover.
- A triggered pair stays visible even when liquidity is not yet sufficient.
- The existing EUR 150k / spread gate remains the normal execution-review path.
- A second paper-only shadow class tests whether EUR 50k-150k pairs with spread
  <=0.60% and strong 1%-book depth can safely reach a fresh evaluator recheck.
- Pairs below those review gates remain WATCH_ONLY and are rechecked if liquidity improves.

The rolling discovery tape observes 10m / 30m / 1h / 3h / 6h / 12h changes. Broad
recognition triggers include fast momentum and persistent/stair-step trends. These
are discovery rules, not entry rules, and KSM/TRAC remain discovery examples rather
than validation evidence.

Files:
- `paper_evaluator/v2r4_precandidate_discovery.py`
- `paper_evaluator/v2r4_precandidate_watcher.py`
- `tests/test_v2r4_precandidate_discovery.py`

The active V2R3 control remains unchanged.

## Inactive continuous WAIT runtime preparation

The earlier single-plan watcher and trigger->fresh-recheck E2E proved the mechanics.
This clean successor branch preserves the validated inactive bounded WAIT-plan runtime:

- `paper_evaluator/v2r4_wait_runtime.py`
- `tests/test_v2r4_wait_runtime.py`

Safety/behavior:

- discovers persisted `v2r4_trigger_plan` and chained `next_wait_trigger_plan` records;
- Kraken public data remains the only trigger-condition truth;
- locally consumed Altrady events are **wakeup hints only** for a same-pair early check;
- an Altrady event can never satisfy a condition or create a buy by itself;
- normal Kraken fallback checking continues even when Altrady is silent;
- one matched plan can request only one fresh paper recheck;
- handled plans are idempotently recorded;
- a failed fresh recheck fails closed and is not automatically hammered/retried;
- no private Kraken API, order endpoint or real-money action exists;
- long-running mode requires explicit `--execute-recheck`; receipt-only mode is
  restricted to bounded smoke use.

This module is **not installed or started**.  Scheduled-task installation and real
series wiring remain part of the later explicit V2R4 paper activation gate.

## MINI-PC WebSocket shadow bridge

The production-shaped V2R4 discovery path must not depend on the older broad REST
ticker poller once the MINI-PC realtime transport is available.

A separate inactive shadow consumer now exists:

- `paper_evaluator/v2r4_ws_shadow_watcher.py`
- input: the compact `kraken-eur-ticker-latest.json` snapshot written by the
  already-running `CryptoMiniPC-KrakenUniverse` service;
- no exchange connection of its own;
- no evaluator invocation;
- no order/account API;
- no mutation of the active V2R3 series.

The consumer builds rolling point-in-time 10m/30m/1h/3h/6h/12h returns from the
local event-driven feed, writes a bounded timing ledger and emits only
`V2R4_WS_SHADOW_DISCOVERY` observations.  Even when a shadow setup would qualify
for a fresh recheck, the shadow action remains `SHADOW_OBSERVE_ONLY`.

Recovery semantics are explicit:

- stale global snapshots are rejected;
- duplicate snapshots are not reprocessed into repeated events;
- stale per-pair updates are ignored;
- after a material feed gap/reconnect, the first fresh snapshot is consumed but
  trigger emission is suppressed for one cycle;
- no pre-gap condition is blindly replayed after reconnect;
- continuous state is persisted on a bounded interval rather than rewritten every
  one-second poll cycle.

This bridge exists specifically to prove feed freshness, timestamp semantics,
dedup/TTL behavior and discovery latency before V2R4 paper activation.

Files:
- `paper_evaluator/v2r4_ws_shadow_watcher.py`
- `tests/test_v2r4_ws_shadow_watcher.py`

The older REST pre-candidate watcher remains useful as a research/fallback harness,
but it is not the intended timing-critical MINI-PC primary path.

## Kraken tradability / universe rule

Kraken tradability is a live market-data property, not a remembered whitelist.

- The MINI-PC primary universe is refreshed by the local Kraken realtime service from public `/0/public/AssetPairs`; the WS shadow consumer inherits that current online-EUR universe from the feed snapshot. The legacy REST research watcher may still refresh `AssetPairs` directly per run.
- Only Spot EUR pairs whose Kraken `status` is `online` belong to the actionable discovery universe.
- Symbol aliases must be resolved from Kraken metadata (`wsname`, `altname`, pair key); a chat-memory or manually maintained symbol list must never be the primary source.
- A periodic 14-day universe audit may remain as an integrity check for alias/listing drift, but it is not the operational source of truth.
- Coin-specific reviews must not classify a symbol as unavailable on Kraken without a fresh Kraken-universe lookup.
- This is infrastructure/data-quality behavior only; it does not modify V2R3 entry, stop, sizing or scoring rules.



## Architecture cleanup inheritance — 2026-10-05

This clean V2R4 candidate is based on the post-cleanup `main` and supersedes old
Draft-PRs #8/#9.

Binding architecture:
- `market_data/` is the canonical public Kraken market/transport semantics layer for
  successor assessment code; intentional research transforms must be explicitly versioned;
- Supabase is the durable structured runtime/evidence archive;
- MINI-PC stores only bounded operational state/logs/heartbeats;
- GitHub stores code, contracts, tests, canonical docs and compact release evidence;
- `EVIDENCE_DIVERSITY_FASTTRACK_V2` governs the earliest valid completion point;
- no automatic paper activation and no real-money path.
