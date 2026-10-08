# V3 Research Framework / Strategy Knowledge Base

Status: ACTIVE RESEARCH  
Created: 2026-09-28  
Current active Shadow baseline: `PAPER-V2R4-20261007T184255Z` / `V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION`  
Primary research log: GitHub Issue #7 — V3 Research Track – Jansen evidence framework  
Version relationship: `docs/strategy-version-map.md`

## 1. Purpose

This document is the compact, versioned source of truth for the V3 development track. V3 includes research, validation, integration and eventual successor-strategy construction.

It does **not** modify the currently active Paper baseline in place. New literature findings, historical analyses and paper-trade observations may create hypotheses and test candidates, but production rules must never change silently. Current active state is declared only in `project-current-state.json`.

V2R3 remains an immutable historical comparison baseline. The active H3 Shadow is bound to the current V2R4 Paper baseline declared in `project-current-state.json`. The eventual V3 successor inherits the best validated V2/V2R4 knowledge rather than being built from scratch.

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
   - No effect on the active baseline decisions.
   - Predefined minimum sample and promotion gates.
   - Technical failures are excluded from statistical strategy conclusions.
   - A causal decision divergence counts only when a same-snapshot baseline replay reproduces the official baseline decision.
   - At most one strategy-changing Shadow may run at once; passive no-authority observation tracks may run in parallel.
   - After individual components are reviewed, retained components require a separately versioned integration candidate before combined promotion.

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
Status: `REJECTED`  
Stage: `V3-H1-SHADOW-001_FIXED_REVIEW_COMPLETE_STANDALONE_AUTHORITY_REJECTED`  
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
- incremental `V3-H1-INCR-001` review completed with the sealed holdout untouched; no threshold/pair/transform winner was selected;
- one-change pilot `V3-H1-SHADOW-001` then completed its preregistered gate: **200/200 PASS context records, 100% capture, 9 decision divergences**;
- runtime control is now disabled with `closed_reason=PREREGISTERED_MINIMUM_GATE_MET_200_OF_200_PASS`;
- fixed review of the 9 divergences is complete; standalone H1 decision authority is rejected. H1 remains research diagnostics only and must not be silently bundled into a later candidate.

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
Status: `SHADOW`  
Stage: `V3_H3_SHADOW_001_ACTIVE_COLLECTING`  
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

Current prospective association status:
- `V3-H3-ASSOC-001` remains INVALID_TECHNICAL only (0 rows from unreachable scheduler branch), never strategy evidence;
- replacement `V3-H3-ASSOC-002` completed the frozen collection gate with **four valid >=1800s MINI-PC sessions across two UTC dates**;
- final valid rows: **BTC=1252 / ETH=1314 / SOL=1331**;
- fixed descriptive association review is PASS, but effects are symbol/feature/horizon-specific rather than a universal cross-symbol direction;
- no threshold/transform/pair/horizon search, fill inference or automatic promotion occurred.

Current shadow status:
- `V3-H3-SHADOW-001` is frozen against active baseline `PAPER-V2R4-20261007T184255Z` / `V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION`;
- physical Kraken L2 reconciliation PASS: **931 updates / 937 checksum PASS / 0 failures** with bounded reconnect/resubscribe;
- isolated candidate -> baseline -> +H3 E2E PASS with V2R4 unchanged, no orders and no real-money path;
- only XBT/EUR, ETH/EUR and SOL/EUR are eligible; all other pairs are baseline passthrough;
- frozen gate: >=20 eligible matched candidates, >=2 UTC dates, >=95% H3 capture success; <3 causal divergences => `INCONCLUSIVE_LOW_IMPACT`; no tuning or automatic extension;
- H3 divergence counts require a same-snapshot baseline control replay that matches the official V2R4 decision, reducing false attribution from evaluator instability;
- runtime evidence is Supabase-primary with bounded MINI-PC local state; no per-event Git persistence;
- promotion remains manual and requires separate after-cost review.


### H4 — Regime-Dependent Stops / TTL
Status: `PRECHECK`  
Stage: `DATA_READINESS_ONLY`  
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
Status: `KEEP_TESTING`  
Stage: `INCREMENTAL_REVIEW_COMPLETE_WAIT_FOR_SEQUENCE_GATE`  
Priority: B

Use only transparent primitives:
- multi-horizon price trend
- multi-horizon volume trend
- price/volume agreement
- normalized trend ratios

Do not copy a large CTREND implementation unless simple primitives first show incremental Kraken-EUR OOS value.

Current evidence: synthetic PIT price/volume primitives are green and `V3-H6-INCR-001` completed its fixed incremental review with the sealed holdout untouched. Incremental volume contribution beyond fixed price direction is small/near zero; partial-correlation signs are internally consistent by stratum, while simple True-vs-False effects are not uniformly sign-stable. No threshold/transform winner was selected. H6 stays third in the chosen H1 → H3 → H6 sequence and must not be promoted before the earlier stage reviews.

### H7 — Meta Gate: TAKE / NO-TAKE
Status: `DEFERRED`  
Stage: `LABELS_NOT_READY`  
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
- V2R3 final review is complete; H7 remains deferred because its label/cost/split contract is not frozen and sufficient clean V2R4-era labels are not yet available;
- label definition is `NOT_FROZEN`;
- no logistic/Lasso/tree trial may start before the label/cost/split contract is frozen after mature V2R3/V2R4 evidence;
- H7 readiness guard: **SUCCESS**.

### H8 — On-Chain State
Status: `PRECHECK`  
Stage: `PROSPECTIVE_ONLY_STATE_SMOKE_GREEN_ASSOCIATION_DEPTH_PENDING`  
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
Status: `DEFERRED`  
Stage: `FILL_MODEL_BLOCKED_ACCOUNT_TIER_QUEUE_CONTRACT_PENDING`  
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
Status: `SHADOW`  
Stage: `PROSPECTIVE_CAPTURE_ACTIVE_FIRST_REVIEW_COMPLETE_MORE_TESTING_REQUIRED`  
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

Current source precheck:
- official Hyperliquid public Info endpoint is registered read-only; no signer/private key/order path is authorized;
- bounded CI smoke **Run #1 SUCCESS**: `allMids` returned 1,141 numeric mids; public-address `openOrders` and `userFills` response shapes were reachable without auth;
- this proves transport/shape only, **not** trader quality, wallet identity or predictive value;
- canonical evidence: `research/v3/h10-h11-public-source-evidence-20261002.json`;
- **selection V1 is now preregistered before any Kraken-outcome join:** `research/v3/h10-trader-cohort-selection-contract-v1.json` / trial `V3-H10-COHORT-001`;
- target cohort = **20 primary + 6 active controls**. Primary wallets must pass fixed account/activity/anomaly guards and be positive across week/month/allTime; selection inside fixed account-value strata is deterministic SHA-256, not ranked by seen PnL. Controls pass the same activity floor but are not positive across all three windows;
- discovery uses Hyperliquid's public stats leaderboard **only as an unstable discovery source**; official `api.hyperliquid.xyz/info` `userRole`, `portfolio` and 30-day `userFillsByTime` must verify every included address;
- selection explicitly forbids Kraken future returns/MFE/MAE, V2R3/V2R4 outcomes, future Hyperliquid performance, identity guesses and manual post-outcome cherry-picking;
- CI workflow `.github/workflows/v3-h10-smart-money-cohort-precheck.yml` first runs a 3-address bounded smoke, then executes the frozen cohort selection only if the smoke passes; no schedule and no active strategy coupling;
- cohort execution **Run #1 SUCCESS**: 46,994 leaderboard rows inspected; deterministic cohort frozen as `research/v3/h10-trader-cohort-v1.json` with **20 primary + 6 active controls** after 81 official-address verification attempts;
- first prospective capture **SUCCESS**: 26/26 wallets, 0 errors, 63 current positions and 652 source-timestamped fill events seen in the 45-minute lookback; Supabase `public.v3_h10_capture_health` = `HEALTHY`;
- active cloud bootstrap capture: `.github/workflows/v3-h10-smart-money-shadow-capture.yml` at :17/:47 each hour. It is intentionally a coarse bootstrap/fallback path; source fill timestamps remain exact, but GitHub scheduler timing must not be interpreted as 60-second observation latency;
- storage is compact and server-side only: `v3_h10_capture_batches`, `v3_h10_wallet_states`, `v3_h10_fill_events`, `v3_h10_capture_errors`; MINI-PC receives no Supabase admin/service key;
- anti-HFT aggregation is explicit: `v3_h10_wallet_asset_activity_30m` counts each wallet once per asset/window and `v3_h10_asset_consensus_30m` measures independent-wallet agreement, so hundreds of fills from one trader cannot masquerade as broad Smart-Money consensus;
- first descriptive review is preregistered in `research/v3/h10-first-analysis-gate-v1.json`: minimum 72h, >=95% healthy capture, >=100 batches, >=100 primary wallet-asset windows and >=20 multi-wallet same-asset windows; this gate matured on 2026-10-08 and the first evidence-only review is complete (`research/v3/h10-first-analysis-review-20261008.json`). Result: MORE_TESTING_REQUIRED. Capture reliability is strong, but predictive scoring remains blocked until a dedicated point-in-time Kraken-EUR outcome/context join plus one frozen false-positive label are preregistered; no wallet/coin/threshold/horizon selection from seen outcomes;
- next gate: let the frozen cohort collect prospectively; after the analysis gate matures, join only point-in-time online Kraken Spot-EUR assets at fixed 15m/1h/3h/6h/24h horizons and compare primary cohort versus active controls. No active strategy change before that review.


### H11 — Prediction-Market Event Layer
Status: `PRECHECK`  
Stage: `TWO_CAPTURE_STATE_CHANGE_GREEN`  
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

## First V3 shadow candidate readiness

Canonical snapshot: `research/v3/shadow-candidate-readiness-20261002.json`.

Purpose:
- show which single-component shadow routes are near materialization;
- name exactly one remaining gate per route where possible;
- keep optional/data-maturity/later-execution branches from blocking unrelated forward progress;
- avoid selecting a candidate before its frozen evidence review exists.

Current practical focus:
- H1 fixed shadow review is complete and standalone decision authority is rejected; features remain diagnostics only;
- H3 one-change shadow is active on the MINI-PC against V2R4 and is collecting toward its frozen minimum gate; H6 remains sequenced after H3 review;
- H5: one FOMC risk-gate variant is already preregistered but waits for the appropriate baseline freeze;
- H2/H4/H7/H8/H9/H10/H11 are not mandatory blockers for the first shadow unless one is explicitly selected as the changed component.

A first shadow candidate must still obey the one-change contract. This readiness snapshot does not select a winner, freeze a candidate, promote a strategy, alter V2R3/V2R4, or authorize orders.

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

**The currently active baseline is never modified in place by this file.**

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

V2R4 is now active as its own immutable Paper series. It does not replace V3. Future V3 Shadow candidates must bind explicitly to the active baseline declared in `project-current-state.json`, and completed predecessor gates are not reopened by ordinary new evidence.

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

Current source precheck:
- official Polymarket public market-data/CLOB paths are registered read-only; no wallet/auth/order path is authorized;
- bounded CI smoke **Run #1 SUCCESS**: active event/market discovery returned 20/20 records and the first tested active market exposed a timestamped/hashed CLOB book plus midpoint/spread shape;
- this proves public transport/shape only, **not** objective probability, crypto direction or incremental predictive value;
- canonical evidence: `research/v3/h10-h11-public-source-evidence-20261002.json`;
- next gate: freeze event-selection + point-in-time prospective capture contract before any scheduled collection or surprise-score research.

First prospective state capture:
- frozen bounded contract: `research/v3/h11-polymarket-prospective-state-contract-v1.json`;
- fixed first-stage selection: first 5 active Gamma markets in API response order, no rerank/topic/performance filter;
- **Run #3 SUCCESS**: 5 markets / 10 token states captured; public read-only only, no auth/wallet/orders/schedule;
- canonical evidence: `research/v3/h11-polymarket-prospective-state-evidence-20261002.json`;
- next gate: at least one temporally separated second capture, then review only state-change observability/known-at quality — still no signal, threshold, surprise score or Kraken outcome join.

Two-capture state-change review:
- identical code/contract, workflow Run #4 attempts 1→2, 24.525 s apart;
- same 5 markets / same 10 token states;
- 10/10 order-book hashes changed and 10/10 book timestamps advanced;
- midpoint changes 0/10 and spread changes 0/10 in this short interval — this is reported, not treated as failure;
- therefore public state change is technically observable, but probability-change usefulness/predictive value remains untested;
- canonical review: `research/v3/h11-polymarket-two-capture-state-change-review-20261002.json`;
- next gate: freeze a longer-horizon prospective sampling + event-relevance contract before any Kraken outcome association or surprise-score research.


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

## 13. Future live-feedback contract

V3 and all later generations must be designed so that eventual real-money execution produces
versioned learning evidence for the next successor rather than becoming a terminal production
state. Live fills, costs, slippage, stop/exit behavior, missed opportunities, regime context,
manual overrides and execution incidents must be joinable back to the originating strategy
version and decision provenance.

Live evidence may generate new hypotheses or successor changes, but it may not retune the
currently active strategy in place. Any material change follows the same frozen-candidate,
validation, migration-ledger, rollback and explicit live-release process as other strategy changes.


## Evidence-Diversity Fast-Track inheritance — permanent from 2026-10-05

V3 and every later research/strategy generation inherit
`docs/fasttrack-evidence-diversity-policy.md`.

Promotion is therefore not tied to a fixed 7-day/14-day calendar duration. Each frozen
candidate preregisters its sample unit/floor, maturity horizon and any component-specific
regime requirement. The final continue/reject/promote decision is taken at the earliest
point where the required sample, temporal diversity, maturity, follow-up coverage,
PIT/provenance integrity and release controls are all satisfied.

Default high-frequency temporal-diversity guard: >=max(48h, 2×required follow-up horizon),
>=3 UTC dates, <=50% from one UTC date and <=60% in any rolling 24h window. A stricter
component-specific gate may be preregistered when the research question genuinely needs
more regime/event diversity; it must not be relaxed post-hoc because results are weak.

The same principle continues into the later live phase: live observations accelerate the
creation/evaluation of inactive successors, but the active real-money version never
self-retunes and live execution-safety/release gates remain independent hard requirements.

### Multiple markets/news/primary sources: context first, strategy later (2026-10-08)

The permanent, scoped source/freshness/conﬂict/anti-overfilter contract is `docs/market-context-source-fusion-v1.md`; `research/source-registry.json` distinguishes manually verified CoinGecko/CMC reads, existing Kraken/Fed/SEC paths, and not-yet-integrated official CFTC/BLS/Coinbase/events/smart-money sources. All additional aggregate/news feeds are **CONTEXT_ONLY**; they cannot silently alter V2R4, H3, H6 order, entry/WAIT/REJECT, stops, H1-standalone rejection, or Work cadence. H10/H8/H11 preserve their own proof gates. V3 regime decision candidate must measure incremental value **beyond** existing market context using independent phase/time diversity, costs, trade conversion and missed-move controls; discordant/stale feeds never cast hard vetoes. Later live successors inherit this capability, not an unvalidated source-driven strategy mechanic.

### V3 decision candidate — Marktphasen-Kontext mit messbarem Zusatznutzen (2026-10-08)

**Status: RESEARCH / PRECHECK — NICHT AKTIVE ENTSCHEIDUNGSLOGIK.**
Der dauerhaft aktive `MARKET_REGIME_EPISODE_V1`-Lernradar aus
`research/v3/market-phase-reversal-observation-v1.md` darf **spätestens
im V3-Integrationsreview** als potentielles *zeitpunktbekanntes*
Market-State-/Confirmation-Feature beurteilt werden. Das ist ein
geplanter Test eines eigenständigen Forschungsansatzes, **keine**
Reaktivierung der bereits abgelehnten H1-Standalone-Decision-Authority.
Auch der anfängliche CoinGecko-`MARKET_REGIME_SEED_V1` ist nur
historischer Kontext, kein zulässiges Kraken-EUR-Kandidatensignal.

**Die konkrete Frage:** Liefert ein vor dem Kandidaten-Zeitpunkt
prospektiv bestätigtes, hinreichend frisches `RISK_OFF` /
`STABILIZING` / `RECOVERY_CONFIRMED` **zusätzlichen** netten Nutzen
gegenüber der eingefrorenen V2R4-Baseline *und deren bereits
vorhandenem BTC-/ETH-/Marktbreitenkontext*? Mögliches Einsatzgebiet:
diagnostische Bewertung von Früh-/Reclaim-/Continuation-Kandidaten
oder später ein **einzeln getesteter** Confirmation-/Risk-State-Layer.
Ein pauschaler Risk-off-Stop kann den bestehenden Low-Trade-Engpass
verschlimmern; Kandidaten- und Trade-Häufigkeit ist deshalb
gleichberechtigtes Bewertungskriterium neben vermiedenen Fehltrades.

**V3-Gate, in dieser Reihenfolge:**
1. Zuerst den ersten echten prospektiven Kraken-EUR-Episodenmarker
   sowie über mehrere voneinander unabhängige Marktphasen gereifte
   Kandidaten-/Outcome-Daten nachweisen. Kein `SEED_V1` als Entry-Label,
   kein rückwirkendes Umklassifizieren, kein Look-ahead. Zeitstempel,
   Feed-Abdeckung und Phasen-Freshness am **Kandidatenzeitpunkt**
   müssen valide sein; bei `UNKNOWN`/stale fehlt das Feature.
   Die 2h-Radaruhr ist kein schneller Entry-Trigger.
2. Ein **einziger eng abgegrenzter, vorab eingefrorener** Vergleich:
   bestehende V2R4/V3-Entscheidung ohne neues Feature gegen
   denselben Kandidatenstrom / dieselbe Uhr mit genau **einer**
   zusätzlichen Market-State-Verwendung; keine simultane
   H3-/H6-/Stop-/Sizing-Änderung. Bereits getestete H1-Varianten
   nicht unter neuem Namen erneut durchsuchen. Vorher Sample,
   Phasenvielfalt, Datenmaturität, Netto-Kosten, Trade-Frequenz,
   Fehltrade-/Missed-Move-Grenzen und Abbruchkriterien festlegen.
3. Erst bei echtem inkrementellem Vorteil nach Kosten und
   prospektivem Holdout/Shadow darf ein inaktiver
   Integrationskandidat vorbereitet werden. H3s aktiven
   strategieändernden Shadow nicht unterbrechen; H6s bereits
   vorgesehene Sequenz nicht heimlich verdrängen.
4. **Spätestens vor V3-Promotion** einen ausdrücklichen Befund im
   Migration-Ledger dokumentieren: `PROMOTE_CANDIDATE` nur nach
   allen separaten Sicherheits-/Research-Gates, sonst
   `NO_SUCCESSOR_CHANGE`, `REJECT_WITH_EVIDENCE` oder bei
   sachlich fehlender Marktreife ein **begründetes**
   `DEFER_TO_LATER_GENERATION` nach V4+. Ungeprüfte Daten
   erzwingen keine V3-Handelsregel und dürfen den Fortschritt
   einer ansonsten qualifizierten Strategie nicht endlos
   blockieren.

**Wichtig:** Die passive Beobachtung und Lernweitergabe bleibt
in jeder Generation bestehen, selbst wenn die aktive V3-
Entscheidungsanwendung abgelehnt oder verschoben wird. Keine
automatische Schwellen-/Entry-/Stop-/Sizing-/Orderänderung und
keine zusätzliche Work-/Scanner-/Sensor-Aufgabe für diesen Gate.

## Marktphasen-Episoden — passive Beobachtung / lernfähige Auswertung (2026-10-08)

Vertrag: `research/v3/market-phase-reversal-observation-v1.md`. Der bestehende Marktphasen-Wächter darf ausschließlich kompakte, nachweisbare Phasenwechsel unter `MARKET_REGIME_EPISODE_V1` im bestehenden V3-Research-Issue #7 vermerken. Diese Ereignisse sind **Kontext**, keine Strategie- oder Orderautorität. Die bestehende V3-H1-Standalone-Ablehnung bleibt gültig. Bei einem ohnehin geöffneten Analyse-Gate sind Regime-Ereignisse zeitpunktgerecht mit reifen V2R4-Outcomes/Missed-Moves zu verknüpfen, auf inkrementellen Nutzen und Fehlerquellen zu prüfen und nur über die normalen Hypothesen-/Migrations-/Release-Gates weiterzuverarbeiten. Keine zusätzliche Work-Ausführung und keine laufende Regeländerung.

### Permanente Marktphasen-Beobachtung über V3 hinaus (2026-10-08)

Die bestehende `MARKET_REGIME_EPISODE_V1`-Beobachtung und ihre
point-in-time-Auswertung aus
`research/v3/market-phase-reversal-observation-v1.md` sind ein
**generationenübergreifender Forschungsbaustein**: alle künftigen
Marktbewegungen, V4+ und später — bei gesonderter Freigabe — Echtgeld-
Nachfolger. Sie bleiben von aktivem Trading getrennt und werden im
predecessor→successor-Migrationsledger nachvollziehbar übernommen,
bewusst weiterentwickelt oder evidenzbasiert ersetzt. H1 bleibt als
eigene Decision-Authority verworfen. Eine Marktphase ist ein
Kontext-/Segmentierungsmerkmal, **kein automatisch aktivierbarer Filter**.
Keine neuen Work-Läufe, Pushs oder Live-Rechte.
