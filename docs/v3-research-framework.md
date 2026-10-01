# V3 Research Framework / Strategy Knowledge Base

Status: ACTIVE RESEARCH  
Created: 2026-09-28  
Baseline: `V2R3-2026-09-28`  
Primary research log: GitHub Issue #7 — V3 Research Track – Jansen evidence framework  
Version relationship: `docs/strategy-version-map.md`

## 1. Purpose

This document is the compact, versioned source of truth for the V3 development track. V3 includes research, validation, integration and eventual successor-strategy construction.

It does **not** modify the active V2R3 paper strategy. New literature findings, historical analyses and paper-trade observations may create hypotheses and test candidates, but production rules must never change silently.

V2R3 remains the frozen comparison baseline for the current series. However, the eventual V3 successor will inherit the best validated V2/V2R4 knowledge as its starting baseline rather than being built from scratch.

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
   - Exactly one material strategy component per Shadow candidate; contract: `research/v3/shadow-candidate-contract-v1.json`.
   - `tools/validate-v3-shadow-candidate.py` rejects multi-change candidates and rejects Shadow freeze before sample/cost/promotion gates are predefined.
   - Freeze parameters before prospective evaluation; no mid-run tuning.

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
Status: `PRECHECK`  
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

Current methodology precheck:
- preregistration: `research/v3/h1-cross-crypto-breadth-precheck-v1.json`;
- synthetic 5-pair PIT feature smoke: **Run #3 SUCCESS**;
- exact 15m/1h/4h closed-bar lookbacks, explicit breadth denominator and future-row rejection are proven;
- an intentionally missing XRP 1h lookback remains missing while 15m/4h stay usable;
- no performance trial, pair/month/threshold selection or holdout access has begun.
- initial red smoke runs were only negative-assertion-polarity wiring defects, not feature leakage or hypothesis failures; after advancing the prereg status, the expected old-state guard mismatch occurred once, and the final advanced-state guard is **Run #5 SUCCESS**.

### H2 — Basis / Premium / Funding / OI State Layer
Status: `PRECHECK`  
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

Current preregistered precheck:
- `research/v3/h2-derivatives-state-precheck-v1.json`;
- public Kraken Futures coverage/semantics audit is real-network CI green;
- H2 guard **Run #4 SUCCESS** after the coverage gate advanced; intervening Run #3 failure was only the old guard still asserting the pre-coverage `next_gate`, not a market-data or hypothesis failure;
- current observed coverage: 142 mapped Perpetual bases across 501 online Kraken Spot-EUR bases (**28.34%**);
- bounded XBT/ETH/SOL/XRP/ADA OI/Funding/Basis probe: **15/15 successful with data**;
- incomplete derivatives coverage is represented as missing state, never future-filled or treated as an error;
- Binance public USD-M remains supplementary cross-market context only.

No H2 performance trial, threshold sweep, pair/month selection or holdout access has begun.

Kraken Spot EUR remains the execution/fill reference.

### H3 — Orderflow / Depth / Imbalance
Status: `PRECHECK_L2_SNAPSHOT_GREEN_WEBSOCKET_PENDING`  
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

Current precheck:
- `research/v3/h3-orderbook-depth-precheck-v1.json`;
- public Kraken REST Depth snapshot semantics are real-network green for XBT/EUR, ETH/EUR and SOL/EUR;
- top-of-book spread and top-10 quote depth can be measured without account/private API;
- sample values are diagnostic only and cannot become thresholds;
- this does **not** prove order-flow deltas, queue position, maker fill probability, adverse selection or resiliency;
- next gate is a bounded public MINI-PC WebSocket book capture with reconnect/staleness and snapshot/delta reconciliation.

### H4 — Regime-Dependent Stops / TTL
Status: `PRECHECK_DATA_READINESS_ONLY`  
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

Current preregistered precheck:
- `research/v3/h4-regime-stop-ttl-precheck-v1.json`;
- clean-series snapshot at preregistration: 84 candidate rows; mature MAE/MFE counts 75/66/57/28 at 30m/60m/120m/360m;
- mature post-detection 24h MAE/MFE: **0**; completed trade-return rows: **0**;
- therefore no stop/TTL/trailing parameter testing is permitted yet;
- first later trial must change exactly one component (stop **or** TTL **or** trailing **or** timeout), keep the same candidate stream/market clock, and preregister sample/cost/promotion gates;
- regime definition itself must be point-in-time and frozen before metrics;
- H4 precheck guard **SUCCESS**; no holdout or active runtime change.

### H5 — Macro Event Risk Gate
Status: `PRECHECK`  
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

Current precheck: DST-aware FOMC event timing and `known_at` point-in-time semantics are green. H5 guard **Run #4 SUCCESS** after state progression; no event-window, edge, sizing or performance winner has been selected.

### H6 — Simple Multi-Horizon Price × Volume Trend
Status: `PRECHECK_PIT_METHOD_GREEN`  
Priority: B

Use only transparent primitives:
- multi-horizon price trend
- multi-horizon volume trend
- price/volume agreement
- normalized trend ratios

Do not copy a large CTREND implementation unless simple primitives first show incremental Kraken-EUR OOS value.

Current precheck: synthetic PIT price/volume primitives are green; future bars are ignored, missing prior-volume windows remain missing rather than zero-filled, and the transparent/no-search/no-holdout guard is **Run #4 SUCCESS**. No performance trial has started.

### H7 — Meta Gate: TAKE / NO-TAKE
Status: `DEFERRED_LABELS_NOT_READY`  
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

Current readiness control:
- `research/v3/h7-meta-gate-readiness-v1.json`;
- `public.v3_h7_meta_gate_readiness`;
- training/model selection are explicitly false;
- current live state is `WAITING_V2R3_FINAL_REVIEW`;
- label definition is `NOT_FROZEN`;
- no logistic/Lasso/tree trial may start before the label/cost/split contract is frozen after mature V2R3/V2R4 evidence;
- H7 readiness guard: **SUCCESS**.

### H8 — On-Chain State
Status: `PRECHECK_COVERAGE_GREEN_KNOWN_AT_PENDING`  
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

Current precheck:
- first public source candidate: Coin Metrics Community, no API key;
- representative asset catalog: BTC/ETH/SOL/XRP/ADA all returned;
- Active Addresses / MVRV / TxCount coverage: **4/5** each (ADA/BTC/ETH/XRP);
- Exchange In/Out Flow coverage: **2/5** (BTC/ETH);
- New Address coverage in checked community catalog: **0/5**;
- SOL currently lacks the checked target metric groups;
- coverage audit guard: **Run #6 SUCCESS**;
- metric interval timestamp is **not** treated as publication/known-at time;
- historical trials remain blocked until prospective availability/publication lag is measured;
- missing metrics/coins remain missing; no backfill or performance-based subset selection.

### H9 — Maker-vs-Taker Fill Probability
Status: `DEFERRED_FILL_DATA_NOT_READY`  
Priority: later execution layer

Concept:
Readiness blocker: `research/v3/h9-maker-taker-readiness-v1.json`. H9 modelling remains prohibited until bounded WS book deltas and same-clock public trade prints exist, together with versioned fee/deadline/cleanup semantics. REST snapshots alone cannot identify queue position or fill probability.

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

### H10 — Smart-Money / Trader-Activity Layer
Status: `NEW`  
Priority: A/B

Purpose:
- Use observable behavior of demonstrably relevant traders/wallets as an additional information layer.
- This is **not copy-trading** and must never blindly mirror another trader's orders.
- Initial implementation is read-only / observational and remains isolated from execution.

Candidate public/read-only sources:
- Hyperliquid public trader/position/trade data as the primary candidate source.
- Arkham public wallet/entity activity where available.
- Nansen Smart Money only where access is economically/technically sensible; no dependency on a paid feed is assumed.
- Binance public trader/leaderboard-style data only if stable, lawful and technically accessible.

Candidate features:
- number of independently selected high-quality traders active in the same asset/window;
- direction/concentration and change in aggregate exposure;
- entry/exit clustering and position build-up/reduction;
- notional/exposure acceleration;
- repeated accumulation/distribution by tracked wallets;
- divergence or confirmation versus Kraken-EUR price/volume/orderflow;
- lead time from observed trader activity to Kraken-EUR move.

Trader/wallet selection must avoid simple ROI chasing and survivorship bias. Evaluate, where data permits:
- sufficient history and sample size;
- persistence across multiple horizons;
- drawdown/risk profile;
- consistency rather than one-off outliers;
- liquidity and realistic observability;
- stability of the public identifier/data source.

Initial research design:
1. build a watch cohort (roughly 20–30 candidate traders/wallets);
2. observe prospectively for several weeks without affecting V2/V2R4 decisions;
3. measure hit rate, lead time, false positives, asset coverage and incremental information;
4. retain only a small subset if they show persistent value;
5. only then test as a V3 state/confirmation or candidate-ranking feature.

Promotion requirement:
- measurable incremental prospective/OOS value after accounting for latency, source instability and selection bias;
- no dependence on a single trader, wallet or platform;
- no automatic order-following.

### H11 — Prediction-Market Event Layer
Status: `NEW`  
Priority: A/B

Purpose:
- Use prediction markets as an independent collective-expectations / event-surprise layer.
- Primary planned source: Polymarket public/read-only data.
- Secondary cross-check candidate: Kalshi where accessible and useful.
- No betting/trading integration, wallet, private key or order rights.

Candidate features:
- implied probability level;
- probability change over 5m / 1h / event-relative windows;
- probability-change acceleration / surprise;
- bid/ask spread and liquidity;
- volume and volume acceleration;
- order-book depth / recent trade activity where available;
- time to resolution;
- divergence between related markets.

Primary role:
- macro/regulation/ETF/geopolitical/event state and catalyst detection;
- not a simplistic rule that a prediction-market move directly means “buy coin X”.

Possible later derived feature:
- Prediction-Market Surprise Score, tested point-in-time and prospectively.

Promotion requirement:
- prove that the information arrives early enough and adds incremental value beyond existing news, macro, derivatives and price/orderflow inputs.

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

## 8a. Timing evidence intake

Timing/infrastructure evidence is deliberately kept separate from signal/filter
evidence. Canonical read-only snapshot: `public.v3_timing_evidence_snapshot`.

It combines:
- V2R3 candidate detection → evaluator timing;
- one-shot WAIT requested TTL → actual revalidation lag;
- V2R4 prospective shadow maturity;
- Kraken-native WS-shadow vs. legacy scanner temporal proximity;
- Altrady relay transport evidence.

Current control semantics are fail-closed:
- no path ranking while the underlying comparison view says samples are insufficient;
- timing evidence may motivate an infrastructure/timing variant;
- it does **not** automatically justify loosening entry filters;
- no automatic entry-rule change or strategy promotion is allowed.

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
7. Smart-Money / Trader-Activity observation (read-only; Hyperliquid-first feasibility)
8. Prediction-Market Event Layer (Polymarket-first; Kalshi secondary)
9. Simple Price × Volume Trend
10. Meta TAKE/NO-TAKE gate after enough labels
11. On-Chain after timing/data preflight
12. Fill-probability / maker-vs-taker model before live execution API

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


## 13. Relationship to V2R4 fast-trigger work

V2R4 and V3 are separate but connected tracks.

- **V2R4** is a narrow tactical paper variant focused on WAIT/trigger/revalidation latency,
  Mini-PC event monitoring and earlier scout timing while preserving most V2R3 risk logic.
- **V3** is the broader evidence-driven successor that may change signal families, state
  conditioning, stop/exit logic, sizing methodology and other major mechanics only after
  the full research pipeline.

V2R4 may begin as a separate paper series once the Mini-PC base and one end-to-end
paper-only smoke test are stable. It does not replace V3 and does not require V2R3 to
artificially reach 20 completed trades first.

V2R4 results become V3 evidence, especially:
- trigger and decision latency;
- WAIT → trigger → BUY conversion;
- MFE/MAE and edge decay;
- false-trigger rate;
- cost impact of earlier entries;
- setup-quality and paper-size tier outcomes;
- Kraken / Altrady / local-runtime timing and feed reliability.

Routing rule:
- timing / trigger / revalidation improvements → V2R4;
- major signal / state / stop / exit / sizing / ML changes → V3 research;
- watchdog / recovery / backup / runtime reliability → infrastructure backlog.

The canonical definitions and status of V2R3, V2R4 and V3 are maintained in
`docs/strategy-version-map.md`.


## 14. V2/V2R4 → V3 inheritance and integration

V3 is not a research-only side project. It is the **living successor strategy**.

### Default-preserve rule

The latest validated V2/V2R4 behavior is the default starting point for V3.
A proven component is preserved unless a new candidate has stronger evidence.

This applies to, where still relevant:
- candidate detection and review lessons;
- Kraken-EUR execution reality and cost treatment;
- timing and trigger handling;
- scout / confirmation architecture;
- tradability and liquidity safeguards;
- late-chase protection;
- MAE/MFE and follow-up measurement;
- state vs signal separation;
- logging, auditability and data-quality fail-closed rules;
- watchdog / stale-data / recovery principles;
- sizing lessons that survive validation.

### Evidence hierarchy

When old and new ideas conflict, use this order as the default evidence hierarchy:

1. clean prospective evidence on comparable market conditions;
2. robust point-in-time OOS / walk-forward evidence after realistic costs;
3. repeated evidence across regimes and liquidity buckets;
4. well-supported V2/V2R4 operational observations;
5. literature-supported but locally unvalidated hypotheses;
6. intuition / anecdote.

This means established V2 lessons are weighted more strongly than fresh untested ideas,
but they can still be replaced by better evidence.

### Migration ledger

Before any V3 candidate is considered complete, every material V2/V2R4 component must
have one explicit migration status:

- `INHERITED_UNCHANGED`
- `INHERITED_MODIFIED`
- `REPLACED_BY_TESTED_V3_COMPONENT`
- `REJECTED_WITH_EVIDENCE`
- `NOT_APPLICABLE`
- `OPEN_RESEARCH`

A V3 release candidate is incomplete if relevant V2/V2R4 knowledge is unclassified.

Canonical living ledger: `research/v3-migration-ledger.json`. It is guarded by `.github/workflows/v3-migration-ledger-guard.yml` + `tools/validate-v3-migration-ledger.py`. Every `OPEN_RESEARCH` component must name its next evidence gate; closed statuses may not retain a pending gate. Initial ledger validation **Run #1 SUCCESS**. Current initialization intentionally classifies durable authority/governance/reliability rules immediately while leaving unresolved strategy mechanics open until V2R3/V2R4 evidence matures.

### Integrated target

The target V3 is therefore one coherent strategy assembled from:
- inherited validated V2/V2R4 components;
- promoted V3 research candidates;
- Mini-PC / realtime timing evidence;
- Kraken historical and prospective evidence;
- explicit cost / risk / reliability constraints.

Research remains the input pipeline. **Integration into the successor strategy is the goal.**
