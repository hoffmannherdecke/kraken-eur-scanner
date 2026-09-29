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

### 4. Preserve the two-stage entry

Default paper sizing remains:

- scout: EUR 50;
- stage 2: EUR 50;
- stage 2 still needs its own explicit confirmation trigger.

The goal is to enter promising momentum earlier with a small scout and demand more
confirmation before full paper exposure.

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
8. Only then create a separate V2R4 paper series.
9. Keep V2R3 artifacts immutable as the comparison control.

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
