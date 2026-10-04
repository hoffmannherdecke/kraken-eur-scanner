# V2R3 Clean-Series Strategy Adjustment Hypotheses — V2 Interim Update

**Card ID:** `V2R3-ADJ-HYP-20261004-V2`  
**Status:** HYPOTHESIS ONLY / NOT ACTIVE / REVIEW AT V2R3 FINAL GATE  
**Source series:** `PAPER-V2R3-CLEAN-20261001T0925Z`  
**Active strategy remains:** `V2R3-2026-09-28`

This V2 does not replace or rewrite V1. It records the materially larger mature-24h evidence from Work batch 001 and routes the four resulting lessons into existing successor-version research. No V2R3 strategy/runtime rule is changed.

## 1 — Trade frequency is a strategy/routing question, not primarily a scanner failure

At the analyzed snapshot there were 553 unique candidate outcomes but only 1 BUY_SCOUT. Integrity was HEALTHY and initial evaluation latency was comparatively stable.

**Consequence:** preserve V2R3 unchanged; treat low conversion as a first-class successor-version objective. V2R4/V3 comparisons must report candidate→WAIT/REJECT→BUY conversion and net-after-cost trade frequency separately from infrastructure health.

**Routing:** V2R4 comparison/readiness + V3 H7/meta-gate label design after final V2R3 review. Do not loosen thresholds merely to increase count.

## 2 — Rejected candidates often move later, but MFE is not an entry signal

Among 447 mature REJECTs, p50 24h MFE was +3.594%, while p50 24h close was -0.283% and p50 MAE -3.512%.

**Consequence:** missed-move research must reconstruct a realistic post-detection entry path, including ordering of MFE/MAE, spread, slippage, fees, stop and entry timing. A later high alone cannot relabel a REJECT as a missed profitable trade.

**Routing:** final V2R3 missed-move audit + V3 H4/H7 research. No direct BUY relaxation.

## 3 — Anti-chase remains justified

For 129 mature `already_run` REJECTs, p50 MFE was +5.629%, but median 24h close remained -0.338%.

**Consequence:** keep anti-chase protection. Do not convert `already_run` into immediate entry eligibility merely because later upside existed.

**Routing:** retain as guardrail; evaluate only through a separate pullback/rebuild/second-leg hypothesis.

## 4 — The most promising successor path is bounded watch → pullback/rebuild → fresh full recheck

EXTENDED evidence showed meaningful upside but also materially adverse excursion; WAIT revalidation is additionally delayed beyond requested TTL in many cases.

**Consequence:** combine existing HYP-01/HYP-04/HYP-05 direction into a testable successor architecture:
1. initial rejection/WAIT never directly triggers BUY;
2. selected viable candidates may enter a bounded watch state;
3. a pullback/rebuild/second-leg condition may request a **fresh whole-strategy paper recheck only**;
4. cost/edge hurdle and anti-chase remain intact;
5. compare prospectively against frozen V2R3 using net costs, MAE/MFE, conversion, false triggers and timing.

This is substantially already prepared by the inactive V2R4 bounded WAIT runtime. The new evidence therefore **strengthens the rationale but does not authorize activation or alter its trigger thresholds**. More structural pullback/rebuild logic remains V3 research.

## Fasttrack disposition

- No duplicate implementation is needed for bounded WAIT/fresh-recheck mechanics: V2R4 already has this prepared and inactive.
- No V2R3 code/config change is allowed.
- The next useful fasttrack work is evidence/contract preparation for a prospective pullback/rebuild/second-leg comparison, not threshold tuning.
- Final dispositions remain mandatory at the V2R3 completion gate using `CONFIRM / CHANGE / ADD / REJECT / MORE_TESTING_REQUIRED`.
- V2R4 activation, V3 promotion and all real-money actions remain separately gated.
