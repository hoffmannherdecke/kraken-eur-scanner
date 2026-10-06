# V2R3 adjustment hypothesis card V4 — 2026-10-06

Status: **HYPOTHESIS ONLY / NOT ACTIVE**

Source: [Batch 003 analysis](../work-analysis/2026-10-06-v2r3-mature-24h-batch-003.md)

## New evidence

- 191 newly mature 24h cases; all final REJECT.
- 180 were raw WAIT → REJECT; no new paper trade.
- 24h p50 MFE +2.925%, p50 MAE -2.294%, p50 close -0.136%.
- 18 candidates reached ≥10% MFE, but these collapse to only five unique pair/6h episodes.
- Already-run cases: p50 MAE -3.777% and close -1.877%, materially worse than not-already-run cases (-1.454% / +0.165%).
- WAIT TTL lag remains high (p50 344 s, p90 1,214 s).

## Dispositions

| Finding | Interim disposition | V2R4 inheritance |
|---|---|---|
| Low trade frequency | Evidence strengthened; final gate required | MORE_TESTING_BEFORE_V2R4 |
| WAIT → REJECT lifecycle | Existing successor mechanism, validate prospectively | ALREADY_COVERED_V2R4 |
| Re-trigger dependence | Add pair/time-clustered measurement | NO_V2R4_CHANGE |
| Anti-chase | Retain; no relaxation | NO_V2R4_CHANGE |
| Revalidation delay | Separate runtime class | ALREADY_COVERED_V2R4 |
| Temporal/regime heterogeneity | Stratify final audit | NO_V2R4_CHANGE |

No strategy, threshold, runtime, activation, sizing, stop, scanner or real-money change is authorized by this card.
