# V3 Research Framework / Strategy Knowledge Base

Status: ACTIVE RESEARCH  
Created: 2026-09-28  
Baseline: `V2R3-2026-09-28`  
Primary research log: GitHub Issue #7 — V3 Research Track – Jansen evidence framework

## 1. Purpose

This document is the compact, versioned source of truth for the V3 research track.

It does **not** modify the active V2R3 paper strategy. New literature findings, historical analyses and paper-trade observations may create hypotheses and test candidates, but production rules must never change silently.

V2R3 remains the frozen comparison baseline until an explicitly versioned successor passes the full research, shadow and promotion process.

## 2. Status model

Each V3 hypothesis must have exactly one status:

- `NEW` — captured but not yet tested
- `PRECHECK` — data/timing/feasibility being verified
- `OFFLINE_TEST` — historical point-in-time / walk-forward evaluation
- `SHADOW` — prospective paper/shadow comparison against the frozen baseline
- `KEEP_TESTING` — promising but evidence is not yet sufficient
- `PROMOTE_CANDIDATE` — passed research gates; ready for controlled integration review
- `PROMOTED` — integrated into a new explicitly versioned strategy
- `REJECTED` — failed robustness, economic or operational requirements
- `DEFERRED` — useful idea, but prerequisites/data/infrastructure are not ready

## 3. Research → Test → Promotion workflow

1. **Research intake**
   - Record source, mechanism, affected component, required data, expected benefit and known failure modes.
   - Convert narrative ideas into measurable hypotheses.

2. **Relevance / feasibility precheck**
   - Deduplicate against existing logic.
   - Check fit to Kraken-EUR, actual holding horizon and realistic data availability.
   - Reject unnecessary complexity early.

3. **Offline validation**
   - Point-in-time data only.
   - Chronological walk-forward / rolling-origin evaluation.
   - Purging / label buffer and feature embargo where required.
   - Real Kraken fees + spread + slippage.
   - Regime- and liquidity-conditioned results.
   - Search-accounting / trial ledger.

4. **Selection-bias controls**
   - FDR/BH for large feature screens.
   - Deflated Sharpe / Probabilistic Sharpe where appropriate.
   - SPA / Reality-Check style controls for broader strategy families.
   - PBO/CPCV only where sample size is sufficient.
   - A search is allowed to produce **no winner**.

5. **Frozen candidate**
   - Version exact change vs baseline.
   - Prefer one meaningful mechanics change per candidate.
   - Freeze parameters before prospective evaluation.

6. **Shadow / paper**
   - Same candidate stream and market clock as baseline.
   - No effect on V2R3 decisions.
   - Predefined minimum sample and promotion gates.
   - Technical failures are excluded from statistical strategy conclusions.

7. **Promotion review**
   - Candidate must add robust **net** value after costs, or materially reduce risk without unacceptable loss of edge.
   - Must not depend on one narrow regime.
   - Must have prospective evidence.
   - No automatic promotion to real-money trading.

8. **Controlled integration**
   - New strategy version.
   - End-to-end smoke test.
   - Config diff and rollback point.
   - Last-known-good version retained.

## 4. Non-negotiable research rules

- Strategy mechanics, universe, decision clock, costs, stops, sizing and score→trade mapping are versioned.
- A mechanics change creates a new version; it is not silent tuning.
- Final holdout is sealed until selection is complete and is not reused for retuning.
- Every tested parameter/feature/stop/sizing/ensemble variant counts as a trial.
- Backtests are primarily falsification tools, not proof by attractive equity curve.
- Signal and state/conditioning variables are kept conceptually separate.
- Feature horizon must match the trading horizon.
- One-knob-at-a-time exploration is preferred.
- Highly redundant features are deduplicated.
- A published paper is evidence for a hypothesis, not permission to deploy a rule.
- 20 paper trades are an operational/prospective milestone, not sufficient statistical proof of edge.

## 5. Cost model

Current V2R3 reference assumption:
- Kraken taker fee: ~0.60% per side
- Round trip before spread/slippage: ~1.20%

V3 must evaluate:
- commission
- spread
- slippage
- turnover
- re-entry cost
- maker-vs-taker only when fill probability and edge decay can be modeled

Required output:
- net performance
- cost-sensitivity curve
- break-even cost / break-even edge

## 6. Priority hypotheses

### H1 — Cross-Crypto Lead/Lag + Breadth
Status: `NEW`  
Priority: A

Candidate features:
- BTC/ETH returns: 5m / 15m / 1h / 4h
- return acceleration
- percentage of Kraken-EUR universe positive
- cross-sectional dispersion
- peer/sector basket return
- leader-minus-follower return

Test principle:
- Simple rules / regression first.
- More complex models only if clear nonlinear residual structure remains.

Promotion requirement:
- Incremental OOS value above existing momentum / market-breadth context after full costs.

### H2 — Basis / Premium / Funding / OI State Layer
Status: `NEW`  
Priority: A

Candidate features:
- perp-vs-index / perp-vs-spot basis
- basis/premium z-score
- delta / acceleration
- funding level / delta / persistence / half-life
- open-interest delta
- cross-venue Kraken/Binance divergence
- cross-sectional funding/premium dispersion

Default interpretation:
- State / crowding / confirmation first.
- Directional use only after OOS evidence.

Kraken Spot EUR remains the execution/fill reference.

### H3 — Orderflow / Depth / Imbalance
Status: `DEFERRED`  
Priority: A after Mini-PC/WebSocket layer

Capture:
- bid/ask spread
- L1/L2 depth
- bid/ask imbalance
- signed/aggressor volume
- order-flow imbalance
- OFI normalized by depth
- liquidity shock
- resiliency after shock
- feed staleness and latency

Sequence:
1. simple OFI/depth baseline
2. regime/liquidity conditioning
3. nonlinear/tree models only if justified
4. deep LOB models only much later

### H4 — Regime-Dependent Stops / TTL
Status: `NEW`  
Priority: A

Per trade capture:
- MAE / MFE
- time-to-MAE / time-to-MFE
- edge decay at 5m / 15m / 1h / 4h / 24h
- stop-out then recovery
- re-entry cost
- volatility / spread / liquidity / regime at entry
- entry type and signal strength

Candidates:
- no stop
- fixed stop
- trailing stop
- time exit
- scale-out

Thresholds:
- calibrate only on calibration data
- freeze before OOS / paper evaluation

### H5 — Macro Event Risk Gate
Status: `NEW`  
Priority: A/B

Start with:
- FOMC announcement windows

Later:
- CPI
- US labor-market releases
- other scheduled high-impact events

Test variants:
- baseline
- no new entries in event window
- higher required edge/confidence
- reduced size

Default role:
- risk/state gate, not directional signal

### H6 — Simple Multi-Horizon Price × Volume Trend
Status: `NEW`  
Priority: B

Use only transparent primitives:
- multi-horizon price trend
- multi-horizon volume trend
- price/volume agreement
- normalized trend ratios

Do not copy a large CTREND implementation unless simple primitives first show incremental Kraken-EUR OOS value.

### H7 — Meta Gate: TAKE / NO-TAKE
Status: `DEFERRED`  
Priority: B, after enough clean labels

Purpose:
- Primary scanner continues to find candidates.
- Secondary layer estimates whether current expected **net** edge is sufficient.

Potential inputs:
- scanner score
- spread
- volatility
- breadth
- derivative state
- event state
- lead/lag
- orderflow

Preferred starting models:
- logistic regression
- Lasso / ElasticNet
- simple trees only if required

Do not start before enough correctly labelled prospective/historical candidate outcomes exist.

### H8 — On-Chain State
Status: `DEFERRED`  
Priority: C/B

Possible inputs:
- MVRV
- active/new addresses
- exchange inflow/outflow
- stablecoin flow
- usage/activity measures

Default role:
- state/confirmation, not primary trigger

Precondition:
- timing/availability and coin-coverage audit.

### H9 — Maker-vs-Taker Fill Probability
Status: `DEFERRED`  
Priority: later execution layer

Concept:
Expected cost must include:
- fill probability
- maker fee
- adverse selection
- deadline cleanup/taker cost
- edge decay

Potential inputs:
- limit distance
- spread
- depth
- imbalance
- volatility
- queue proxy
- recent fill behavior
- deadline

Non-fills/cancels must be retained as censored observations, not discarded.

## 7. Explicitly deprioritized

Do not prioritize as directional trading logic without new evidence:
- Fear & Greed index
- broad social-sentiment pipelines
- expensive social/search-attention feeds
- Deep Learning only because it is complex
- DeepLOB before simple microstructure features work
- Funding = direct buy/sell rule
- CTREND copied as a ready-made strategy
- a universal “optimal” stop
- a backtest winner without search-bias correction
- complex ensemble weights before a mean/median baseline

## 8. Forecasting / modeling rules

- Evaluation horizon must match intended holding horizon.
- Always retain a naïve/simple baseline.
- Inspect residual/error autocorrelation for unexploited structure.
- Simple mean/median combination is the default ensemble benchmark.
- Ridge/Lasso/ElasticNet preferred when many correlated features appear.
- Trees/boosting only when simple linear models miss demonstrable nonlinear structure.
- Statistical forecast metrics are secondary to economic net edge after realistic costs.

## 9. Production / Mini-PC architecture rules

These may be integrated into infrastructure without changing trading logic:

- strategy version + config hash on every decision
- last-known-good rollback
- shadow/canary releases instead of big-bang replacement
- monitoring:
  - latency
  - workload/traffic
  - errors
  - resource saturation
  - feed staleness
  - queue backlog
- actionable alerts only
- reboot / internet-loss / API-failure / feed-silence / stale-state / reconciliation fault tests
- structured logs and replay:
  - candidate
  - inputs
  - config version
  - decision
  - paper fill / real fill later
  - rejection
  - outcome
  - health/breaker transitions
- least privilege
- research read-only
- future trading API without withdrawal rights
- persistent kill switch
- startup reconciliation
- stale-data rejection
- duplicate-order and price-deviation gates
- order lifecycle state machine + audit trail
- circuit breakers with CLOSED / OPEN / HALF_OPEN recovery

## 10. Current V3 research order

1. Measurement / validation layer:
   - trial ledger
   - cost accounting
   - MAE/MFE
   - holdout rules
2. Cross-Crypto Lead/Lag + Breadth
3. Basis / Premium / Funding / OI
4. Regime-dependent Stop / TTL research
5. Orderflow / Depth / Imbalance on Mini-PC
6. Macro Event Risk Gate
7. Simple Price × Volume Trend
8. Meta TAKE/NO-TAKE gate after enough labels
9. On-Chain after timing/data preflight
10. Fill-probability / maker-vs-taker model before live execution API

## 11. Sources / evidence families already reviewed

Core:
- Stefan Jansen — Machine Learning for Trading, 3rd ed. companion material
- An Introduction to Statistical Learning with Applications in Python
- Forecasting: Principles and Practice
- White — data snooping / Reality Check
- Bailey / López de Prado et al. — PBO / Deflated Sharpe
- UCL work on execution probability / order placement
- Kaminski & Lo — stop-loss rules
- crypto factor / momentum / basis / cross-crypto predictability literature
- crypto orderflow / market microstructure research
- Google Site Reliability Engineering material

The detailed literature notes, source-specific caveats and chronology remain in GitHub Issue #7.

## 12. Change-control boundary

**V2R3 is not modified by this file.**

No hypothesis above may alter scanner thresholds, entry logic, stops, position sizing or execution behavior until it:
1. passes the required offline evidence path,
2. is frozen as a versioned candidate,
3. passes prospective shadow/paper testing,
4. receives an explicit promotion into a new strategy version.

This document is therefore a strategy research knowledge base and promotion contract — not an active trading configuration.
