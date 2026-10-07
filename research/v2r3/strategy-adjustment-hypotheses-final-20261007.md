# V2R3 Final Hypothesis Dispositions — 2026-10-07

Status: **FINAL / HYPOTHESIS AND RELEASE ROUTING ONLY / NOT ACTIVE**

The machine-readable authority is `strategy-adjustment-hypotheses-final-20261007.json`.

| ID | Disposition | V2R4 routing |
|---|---|---|
| HYP-01 | CONFIRM | ALREADY_COVERED_V2R4 |
| HYP-02 | MORE_TESTING_REQUIRED | V3_ONLY |
| HYP-03 | CHANGE | ALREADY_COVERED_V2R4 |
| HYP-04 | CONFIRM | V3_ONLY |
| HYP-05 | CHANGE | ALREADY_COVERED_V2R4 |
| HYP-06 | CONFIRM | ALREADY_COVERED_V2R4 |
| LOW_TRADE_FREQUENCY | CONFIRM | MORE_TESTING_BEFORE_V2R4 |
| REJECT_LATER_MFE | CONFIRM | NO_V2R4_CHANGE |
| RETRIGGER_EPISODE_DEPENDENCE | CONFIRM | NO_V2R4_CHANGE |
| TEMPORAL_REGIME_HETEROGENEITY | CONFIRM | NO_V2R4_CHANGE |
| REVALIDATION_DELAY | CONFIRM | ALREADY_COVERED_V2R4 |
| WAIT_TO_REJECT_SELECTIVITY | CONFIRM | ALREADY_COVERED_V2R4 |
| SCANNER_SCORE_MONOTONICITY | ADD | NO_V2R4_CHANGE |
| TRADE_SAMPLE_LIMIT | ADD | NO_V2R4_CHANGE |

No new V2R4 strategy diff is proposed. Existing bounded WAIT/fresh-recheck and public `AssetPairs` mechanisms cover the confirmed successor needs. V2R4 activation remains separately gated and real money remains disabled.
