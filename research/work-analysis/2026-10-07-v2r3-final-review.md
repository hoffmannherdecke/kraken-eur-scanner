# V2R3 Final Causal Review — 2026-10-07

Status: **FINAL REVIEW COMPLETE / NO AUTOMATIC STRATEGY CHANGE / V2R4 NOT ACTIVE**

Series: `PAPER-V2R3-CLEAN-20261001T0925Z`  
Frozen qualification cohort: first **1,000** outcomes ordered by `evaluated_at,candidate_id`  
Policy: `EVIDENCE_DIVERSITY_FASTTRACK_V2`

## Gate evidence

At the review snapshot the canonical release surface reported:

- completion gate `ALTERNATIVE_READY`;
- `final_review_allowed=true`;
- integrity `HEALTHY`;
- 1,005 total outcomes, with the first 1,000 frozen as the qualification cohort;
- 955 24h-eligible and 946 complete 24h follow-ups (99.06% coverage of eligible cases);
- one strategy fingerprint and one runtime fingerprint;
- zero duplicate candidate IDs and intake stopped.

The final review therefore uses the frozen 1,000-case cohort. The 54 not-yet-complete 24h outcomes are not treated as zero outcomes and do not alter the already-satisfied gate.

## Decision and trade frequency

| Item | Result |
|---|---:|
| Initial WAIT | 942 |
| Initial REJECT | 58 |
| Final BUY_SCOUT | 1 |
| Final REJECT | 999 |
| Completed trades | 1 |
| BUY conversion | 0.10% |

The single trade (`20261002-192833-MON-EUR-r37054155891`) opened a 50 EUR scout at the fresh Kraken best ask, never filled stage 2, and closed on the initial stop after about 29 minutes. Net P&L was **-1.5462 EUR / -3.0924%**. Entry and exit fees totalled **0.5943 EUR** under the frozen 0.60% per-side assumption. One trade cannot calibrate win rate, profit factor, sizing, stop, trailing, TTL or exit logic.

The near-zero conversion is primarily a **strategy/filter and WAIT-lifecycle selectivity** result, not a missing-data result: integrity and initial evaluation timing were healthy, while 941/942 initial WAITs ended as REJECT. Runtime timing remains a separate material contributor because V2R3's one-shot revalidation often ran late.

## Mature 24h REJECT evidence

The 945 mature final REJECT paths show:

| Horizon | p50 MFE | p50 MAE |
|---|---:|---:|
| 30m | +0.304% | -0.401% |
| 60m | +0.472% | -0.584% |
| 120m | +0.734% | -0.806% |
| 360m | +1.510% | -1.377% |
| 24h | +3.148% | -2.923% |

The 24h median close was **-0.365%**. Candidate-level MFE counts were 612 at >=2%, 291 at >=5%, and 103 at >=10%. Those counts are not independent: the 291 >=5% cases compress to **174 pair/6h episodes**, and the 103 >=10% cases to **65 pair/6h episodes**. Missed movement is real, but raw candidate counts overstate independent opportunities.

### Anti-chase

Among mature final REJECTs:

| Cohort | n | p50 MFE24 | p50 MAE24 | p50 close24 |
|---|---:|---:|---:|---:|
| not already run | 630 | +2.899% | -2.260% | -0.077% |
| already run | 321 | +3.821% | -4.133% | -1.311% |

Higher upside excursions in already-run cases came with materially worse adverse excursion and close. This supports retaining anti-chase. It does not justify chasing; a pullback/rebuild/second-leg concept remains a separate prospective hypothesis.

### Timing and WAIT lifecycle

In the mature cohort there were 891 WAIT→REJECT paths, 54 direct REJECT paths, and one WAIT→BUY path. For mature revalidations, extra TTL lag was p50 **348.293 s**, p90 **1,203.496 s**, p99 **8,312.371 s**; 814 exceeded 60 s and 502 exceeded 300 s.

This confirms the timing/runtime problem, but does not prove that a faster recheck should buy. The successor action remains bounded WAIT plans and a fresh whole-strategy recheck, never direct execution from a wake-up signal.

### Scanner score

The persisted scanner score was available for all mature audit rows. Its linear association with 24h MFE was **-0.024** and with 24h close **-0.035**. Score 10.0–13.7 did not outperform score 5.1–9.9 on median MFE or close. The score is therefore not supported as a sizing or entry override in this cohort.

### Tradability-policy confounder

130 mature cases carried `ACCOUNT_TRADABILITY_UNAVAILABLE` or `PAIR_BLOCKED`; 109 of them were simultaneously verified as public online Kraken Spot-EUR pairs. Their p50 MFE24 was +3.719%; 52 reached >=5% and 20 reached >=10%. This confirms removal of account-private absence and legacy static blocking as negative paper evidence when current public Kraken `AssetPairs` verifies an online Spot-EUR pair. It does not imply those cases should automatically buy.

### Temporal heterogeneity

Daily p50 MFE24 ranged from +4.974% (2026-10-01 UTC) to +1.597% (2026-10-06 UTC), while p50 close24 ranged from +0.946% to -3.791%. This is a measurement guardrail, not an active time-of-day or regime rule.

## Causal classification

| Class | Final finding |
|---|---|
| Strategy/filter | Very low conversion is real; broad threshold loosening is not justified. Selected WAIT/watch routing should be tested prospectively. |
| Timing/runtime | One-shot TTL scheduling is materially late. Existing V2R4 bounded WAIT/fresh-recheck design addresses the mechanism and still requires prospective proof. |
| Data/provenance | HEALTHY. Re-trigger dependence requires pair/time episode reporting. |
| Cost/execution | Costs materially affected the only trade. Keep 0.60%/side and 50+50 sizing for causal isolation. |
| No-change | Anti-chase, two-stage entry, current stop/exit structure and real-money lock remain unchanged for the first V2R4 comparison. |

## Final V2R3 conclusion

V2R3 is technically clean but too selective to establish a tradable edge: one completed trade out of 1,000 outcomes is insufficient for performance claims. At the same time, hundreds of REJECT paths later moved, showing that the system should distinguish “not tradable now” from “dead setup” more effectively.

No new V2R4 mechanism is warranted beyond the already prepared release contract:

- deterministic bounded WAIT/watch conditions;
- optional Altrady wake-up only;
- fresh Kraken condition truth and fresh whole-strategy paper recheck;
- public online Kraken `AssetPairs` authority;
- inherited 50+50 sizing, fees, anti-chase, two-stage entry and exits.

The exact final hypothesis dispositions are versioned in `research/v2r3/strategy-adjustment-hypotheses-final-20261007.json`. V2R4 remains inactive. Separate release gates, a current-main candidate, bounded physical smoke, healthy shadow completion and an explicit `APPROVED_PAPER` decision remain mandatory.
