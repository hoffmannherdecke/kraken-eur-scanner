# V3 successor: coin-specific entry evidence v1 — inactive (2026-10-09)

## Verified root cause

Active `tools/v2r4-paper-local-runtime.py` builds a scanner handoff with percent returns, price, spread and turnover. Active `paper_context.build_context()` enriches with fresh Kraken ticker, AssetPairs, a **BTC/ETH/SOL** OHLC market proxy, derivatives and official headline context. **It does not supply candidate-specific closed 1m/5m/15m OHLC, volume ratios or ATR/structural stop features**. Yet `paper_evaluator/evaluate.py` requires confirmation and a defensible ATR/structural stop for BUY_SCOUT. This is a verified feature-provenance gap, not proof that rejected trades were profitable.

## Frozen prospective V2R4 evidence

As of 2026-10-09 ~17:15 UTC, Supabase had 1,163 decisions across two technically rotated V2R4 series with the same strategy fingerprint: 403 initial REJECT, 760 initial WAIT, zero initial BUY_SCOUT, zero V2R4 paper trades; 738 WAIT had ended REJECT. 768 valid 6h follow-ups contained 186 observations with MFE >=5%; 155 of those had initial spread <=0.5%, representing 31 different pairs. Observations overlap by asset and hour. MFE is NOT an executable profit, and ex-post OHLC must never be imported as known-at entry evidence. Actual liquidity/depth, stop feasibility, MAE, fees 0.60% each way, spread, slippage and pair/6h episode clustering remain required.

Technical series cutover at 2026-10-09 11:01 UTC does NOT restart the strategy observation age from the original 2026-10-07 18:42 UTC.

## Implemented research adapter (not attached)

`paper_evaluator/successor_coin_entry_evidence_v1.py` exposes an offline-pure entry feature builder plus an *optional manually invoked* Kraken public OHLC collector (exactly 1/5/15m reads). Data: most recent fully **closed** candle close/high/low, last volume vs prior five contiguous closed candles, 15m ATR(14) and last-eight-closed-bars low when derivable. Every output distinguishes `observed_at_utc` and `known_at_utc`; never treated as known before the latter. Last mutable bar discarded; gaps, stale data, zero denominator, invalid data and source failure yield explicit missing/incomplete indicators, not a bearish veto. No raw archive, database change, model request, trade authority, order or schedule.

Deterministic local tests (7): `python -m unittest tests.test_successor_coin_entry_evidence_v1 -v` — verified PASS in isolated local environment.

## Existing next gate / decision rule

1. At the existing V2R4 24h/72h/productivity review, use a small fixed, time-clustered positive and negative control cohort. Inspect each originally available decision input. Distinguish feature-delivery omission, legitimate risk veto, premature/late detection, WAIT expiry and data uncertainty. Do not claim the module fixes low BUY conversion before this validation.
2. Freeze **one** inactive successor hypothesis using these point-in-time features and otherwise unchanged fees, stop, timing and risk controls. Compare same-snapshot baseline vs successor prospectively. Count BUY/WAIT/REJECT, net-cost trade feasibility, false positives, false REJECT, true rejections and missed second legs.
3. An independent Mini-PC **small smoke**, source cost/budget gate, consistent sample, rollback and existing separate user/release approval are mandatory before changing live PAPER. No changes to active V2R4, H3, scanner, runner, Work, Supabase, secrets or real-money paths.

Status: **INACTIVE_IMPLEMENTED_NOT_VALIDATED_IN_REAL_RUNTIME**. Research/test contract only. No autonomous deployment.
