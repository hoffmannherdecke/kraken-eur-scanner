# V2R4 fast-trigger / Mini-PC preparation

Status: **PREPARED, NOT ACTIVE**

This preparation must not change the active V2R3 series. V2R3 remains the control.
V2R4 is a separate future paper series and may only be activated after the Mini-PC
runtime has passed a minimal end-to-end smoke test.

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

### 4. Preserve the two-stage entry, but not the old 50-EUR default

V2R4 restores the later agreed adaptive paper sizing rather than treating EUR 50
packages as the normal default:

- B+ / early scout: EUR 75 + EUR 75 => EUR 150 total;
- A-: EUR 75 + EUR 75 => EUR 150 total;
- A: first stage EUR 100-125, confirmed total EUR 200-300;
- A+: first stage EUR 150-200, confirmed total EUR 300-600.

The second stage still requires an explicit confirmation trigger. Position size must
not be increased merely to reach a nominal target, and late chasing remains prohibited.

The research goal is to test whether earlier small-but-meaningful scouts plus quality-
dependent scaling improve expectancy after fees, spread and slippage.

## Role of broader context in V2R4

The proposal records the following research hypothesis for later validation:

- major-market regime: state / risk scaler, not an automatic veto by itself;
- derivatives: supporting context, not mandatory for every setup;
- coin-specific catalyst: positive evidence when present, but not mandatory for a
  technically strong setup;
- missing data: stays explicitly missing and is never fabricated.

These are proposed hypotheses, not proven improvements. They must be validated in a
new versioned paper series and compared with V2R3.

## Mini-PC activation sequence

Do not activate the V2R4 fast path immediately on first boot.

1. Finish Windows / driver / network / time synchronization.
2. Configure automatic recovery after power loss and unattended login/runtime.
3. Install repository runtime and verify read-only Kraken connectivity.
4. Start logging, watchdog and local health status.
5. Run `v2r4_wait_watcher.py --once` against a harmless synthetic plan.
6. Run a live-market PAPER-only smoke test with one candidate and no order path.
7. Verify receipt persistence, timestamps and watchdog recovery.
8. As soon as that single end-to-end PAPER smoke test passes, create a separate V2R4
   paper series; do not wait for V2R3 to somehow reach 20 completed trades first.
9. Keep V2R3 artifacts immutable as the comparison control.

A future major **V3** is not scheduled by calendar date. It is a separate strategy
generation and should only be opened after prospective V2R4 evidence plus historical
walk-forward validation shows that a larger mechanic change is justified.

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
