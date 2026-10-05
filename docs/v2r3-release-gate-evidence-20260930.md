# V2R3 release-gate evidence snapshot — 2026-09-30

Status: **READ-ONLY EVIDENCE SNAPSHOT / NO STRATEGY ACTIVATION**

Active series: `PAPER-V2R3-FINAL-20260928T1752Z`  
Strategy: `V2R3-2026-09-28`

This snapshot aggregates the persisted active-series decisions, revalidations and follow-ups. It is evidence for the V2R4 release gate; it does **not** itself activate V2R4 or claim profitability.

## Sample status

Latest read-only aggregation:
- 570 active-series decisions;
- 519 initial `WAIT`;
- 51 initial `REJECT`;
- 513 `WAIT -> REJECT`;
- 6 WAITs still pending at snapshot time;
- **0 WAIT -> BUY_SCOUT**;
- **0 paper BUY_SCOUT in the series**.

This is now a material strategy/test finding: the active V2R3 decision path is extremely selective and has produced no simulated entries despite a large candidate sample.

## Timing evidence

- scanner detection -> evaluation complete:
  - median: **37.162 s**
  - p90: **72.107 s**
- WAIT TTL -> revalidation lag:
  - median: **329.676 s**
  - p90: **776.343 s**

Interpretation for release-gate purposes:
- initial evaluation latency is measurable but not the dominant multi-minute issue;
- the one-shot WAIT lifecycle routinely revalidates several minutes after the intended TTL;
- V2R4's local/event-driven recheck path directly targets this measured gap.

## Post-detection opportunity evidence

511 candidates had a complete 6-hour follow-up at this snapshot.

Observed MFE after the actual V2R3 decision point:
- >= 5%: **88 / 511**
- >= 8%: **46 / 511**
- >= 10%: **29 / 511**
- >= 15%: **7 / 511**

These are **opportunity/missed-move measurements, not hypothetical trade PnL**. They do not include a valid entry/stop/fill path and therefore cannot be interpreted as profits V2R3 would have earned.

The broader post-detection audit also shows why filters cannot simply be removed:
- 24h MFE median: **+3.999%**
- 24h MFE p90: **+16.144%**
- 24h MAE median: **-3.533%**

Large later upside often coexists with meaningful adverse movement. The appropriate V2R4 response is therefore a fresh conditional recheck/trigger path, not blind entry into every rejected candidate.

## "Already moved" / scanner-late evidence

Among 6h-complete cases with scanner-late evidence, the analyzed cases were not scanner-late, yet 87 still reached >=5% MFE afterward.

The explicit "already run" audit also contradicts the simple assumption that an earlier move necessarily removes the remaining opportunity:
- flagged-as-already-run: median subsequent 6h MFE **2.625%**, p90 **10.257%**;
- not flagged: median subsequent 6h MFE **1.597%**, p90 **6.034%**.

This is not causal evidence that extended setups should be bought. It is evidence that **"first impulse missed" must not automatically mean "trade opportunity finished"** and that continuation/pullback/second-leg paths need explicit measurement.

## Tradability/data-quality finding

The frozen V2R3 evaluator still contained a stale hard-coded block for `DUSK/EUR`, `QNT/EUR` and `TION/EUR`.

In the current series, `PAIR_BLOCKED` appeared in 12 complete 6h cases; 9 of those later reached >=5% MFE. QNT produced several of the largest missed-move examples.

This is classified as a **tradability/data-quality defect**, not evidence that the market filters themselves failed.

Canonical project policy is now:
- current public Kraken `AssetPairs` is the operational source;
- only current `online` Spot-EUR pairs are considered;
- no static pair blacklist may decide operational tradability;
- private account tradability is not required for paper evaluation and its absence must not itself be negative evidence.

The inactive V2R4 draft has been patched accordingly. V2R3 history remains unchanged for auditability.

## Reason-code analytics limitation

Reason codes are not yet a clean taxonomy. Equivalent meanings occur with differences in casing and wording, so raw frequency counts understate semantic families.

V2R4 measurement therefore requires normalized reason-code analytics. This is an analytics/data-quality change, not a retroactive rewrite of V2R3 decisions.

## Release-gate classification

### CONFIRM
- retain paper-only / no-real-money guardrail;
- retain current Kraken-EUR execution reality and fee accounting;
- retain public minimum-order/status verification;
- retain structural stop requirement before a scout;
- retain two-stage confirmation;
- retain "trigger never equals order" architecture.

### CHANGE
- replace static tradability blocks with live public Kraken `AssetPairs`;
- private-account-tradability-unavailable must not act as standalone negative evidence;
- replace timing-critical one-shot WAIT handling with local/event-driven trigger monitoring plus **fresh paper recheck**;
- do not treat "already moved" as an automatic terminal rejection without measuring continuation/re-entry opportunity.

### ADD
- broad pre-candidate visibility across current online Kraken Spot-EUR pairs;
- deterministic trigger timestamps and trigger->recheck latency;
- normalized reason-code analytics;
- Kraken-native local realtime path plus optional non-exclusive Altrady wake-up.

### MORE_TESTING_REQUIRED
- which volume/resistance/market-regime filters are genuinely protective versus overly restrictive;
- setup-lane-specific entry timing;
- pullback / continuation / second-leg entries;
- whether earlier rechecks improve net results after fees, spread, slippage and stops.

## Gate conclusion

The evidence is sufficient to justify **continuing V2R4 preparation and one small end-to-end paper smoke**.

It is **not** sufficient to claim that relaxing V2R3 filters broadly would be profitable, and it does not authorize real-money trading.

V2R3 remains the preserved comparison baseline. V2R4 must start, if activated, as a separate paper series with its own version/fingerprint.


---

## Clean replacement series — prospective status 2026-10-01

The predecessor series above is retained for diagnosis but is no longer accepted as clean release evidence because a runtime-persistence defect allowed repeated evaluation before the candidate state was committed.

The replacement control series is:

- series: `PAPER-V2R3-CLEAN-20261001T0925Z`
- strategy: `V2R3-2026-09-28`
- runtime/strategy fingerprints: internally consistent
- integrity state: **HEALTHY**
- duplicate candidate IDs: **0**
- rule changes during series: **none**

### Historical gate note — superseded 2026-10-05

The `COLLECTING_AGE` / 7-day-age-floor values in the dated snapshot below are retained
only as historical evidence of the control state that existed on 2026-10-01. The current
governing completion rule is `EVIDENCE_DIVERSITY_FASTTRACK_V1` from
`docs/fasttrack-evidence-diversity-policy.md`; no fixed 7-day minimum remains.

### Current clean-series maturity snapshot

Read-only snapshot around 2026-10-01 16:26 UTC:

- candidate outcomes: **62**
- completed trades / BUY_SCOUT: **0 / 0**
- decisions: **56 REJECT / 6 WAIT**
- eligible mature 24h outcomes: **0**
- clean-series completion state: **COLLECTING_AGE**
- remaining to alternate 1,000-outcome floor: **938**
- remaining to 7-day age floor: about **161.0 h**

This clean series is therefore **not yet eligible for final strategy/release conclusions**.

### Interim descriptive horizons

These values are recorded to verify that the analysis machinery works prospectively. They must not be used to tune V2R3 or V2R4 before the documented completion gate.

For current REJECT cases:

- 30m mature: **56**
  - median MFE: **+0.389%**
  - median MAE: **-0.458%**
  - MFE >=2%: **7**
- 60m mature: **53**
  - median MFE: **+0.516%**
  - median MAE: **-0.589%**
  - MFE >=2%: **9**
- 120m mature: **43**
  - median MFE: **+0.516%**
  - median MAE: **-1.009%**
  - MFE >=2%: **10**
- 360m mature: **7**
  - median MFE: **+1.064%**
  - median MAE: **-2.144%**
  - MFE >=2%: **1**
- post-detection 4h mature: **29**
  - median post-detection MFE: **+0.741%**

WAIT cases are too young at this snapshot for meaningful comparable horizons.

### Interim reason-family diagnostics

The normalized reason-family views are now working prospectively on the clean series.

Largest blocking/caution families among current REJECT evidence:

- resistance / breakout: **52 reason instances / 42 candidates**
- volume confirmation: **34 / 33**
- cost / edge: **34 / 32**
- trend / continuity: **29 / 26**
- extension / late entry: **14 / 14**
- market regime: **13 / 13**
- tradability/data: **10 / 10**
- catalyst/context: **10 / 10**

These are descriptive overlaps, not mutually exclusive labels.

At the current immature 4h horizon, no family is authorized for promotion/removal. In particular:

- tradability/data blocking cases currently show low median post-detection MFE in the small mature subset;
- resistance/breakout and extension families show some later upside in a subset;
- those observations remain exploratory until 24h maturity and the final clean-series gate.

### Direct WAIT TTL-lag diagnostics

The clean series now has a dedicated prospective revalidation-timing view: `public.v2r3_revalidation_timing_summary`.

Current clean-series snapshot:

- revalidated candidates: **52**
- median requested WAIT TTL: **30 min**
- median scheduler/runtime lateness *after the requested TTL*: **262.149 s**
- p90 TTL lateness: **908.851 s**
- p99 TTL lateness: **1,170.903 s**
- maximum TTL lateness: **1,401.471 s**
- TTL lateness >60 s: **42 / 52**
- TTL lateness >300 s: **22 / 52**

This separates two timing layers cleanly:

1. scanner detection -> initial evaluator completion is now generally tens of seconds;
2. V2R3's one-shot WAIT lifecycle can still revalidate several minutes after the evaluator-requested TTL.

This is classified as a **timing-infrastructure finding**, not as proof that a different entry rule would be profitable. V2R4's local/event-driven WAIT runtime is designed to remove this avoidable scheduling delay while still requiring a fresh Kraken paper recheck.

### Current timing evidence

The clean series no longer shows the severe multi-minute persistence tail seen in the compromised predecessor:

- WAIT p50 total detection -> evaluation complete: roughly **32 s**
- WAIT p90: roughly **44 s**
- REJECT p50: roughly **37 s**
- REJECT p90: roughly **55 s**
- no clean-series case above **300 s** at the current snapshot

This supports classifying the predecessor's extreme latency tail as at least partly a runtime/persistence infrastructure defect. It does **not** yet prove that the remaining strategy selectivity is correct.

### Current release interpretation

The clean evidence currently supports only the following:

- **timing infrastructure is substantially healthier** than in the compromised predecessor;
- **V2R3 is still producing no paper entries** in the young clean sample;
- the reason/outcome and missed-move analytics pipeline is now ready for mature evidence;
- V2R4 technical preparation may continue;
- V2R4 activation remains fail-closed until the clean V2R3 completion/review gate is satisfied.

No Entry/Stop/Sizing/Scanner rule is changed from these interim numbers.
