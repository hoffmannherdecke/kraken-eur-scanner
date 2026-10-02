# V2R3 Clean-Series Strategy Adjustment Hypotheses — V1

**Card ID:** `V2R3-ADJ-HYP-20261002-V1`  
**Status:** HYPOTHESIS ONLY / NOT ACTIVE / REVIEW AT V2R3 FINAL GATE  
**Evidence snapshot:** 2026-10-02 16:57:19 UTC  
**Source series:** `PAPER-V2R3-CLEAN-20261001T0925Z`  
**Active strategy remains:** `V2R3-2026-09-28`

Machine-readable companion: `research/v2r3/strategy-adjustment-hypotheses-v1.json`.

## Why this card exists

This file freezes the first clean-series strategy-adjustment hypotheses in a versioned, searchable form so they are not lost between chats or releases. It is **not** a strategy change. V2R3 stays frozen until its documented completion/release review.

Snapshot at capture:
- 324 Candidate-Outcomes;
- 321 REJECT / 3 WAIT / 0 BUY_SCOUT / 0 completed trades;
- 64/66 currently eligible 24h follow-ups complete = 96.97%;
- integrity = HEALTHY;
- one strategy fingerprint / one runtime fingerprint.

## HYP-01 — WAIT lifecycle is too terminal

Current evidence:
- 60 mature `WAIT_TO_REJECT` cases;
- 50 later reached >= +2% MFE;
- 30 later reached >= +5%;
- 15 later reached >= +10%;
- p50 24h MFE = +4.974%;
- p50 24h MAE = -1.8725%.

Candidate direction:
- do **not** loosen entry directly;
- replace the single late TTL recheck with a bounded event-near watch state;
- trigger match may only request a fresh whole-strategy recheck, never a direct BUY.

Routing: **V2R4 first**, then inherit evidence into V3.

## HYP-02 — Continuation / second-leg handling is underweighted

Current mature `CONTINUITY` sample:
- n = 16;
- 13 >= +2%;
- 8 >= +5%;
- 5 >= +10%;
- p50 24h MFE = +5.8645%;
- p50 24h MAE = -1.546%.

Candidate direction:
- keep viable candidates alive after the first impulse;
- test explicit continuation / second-leg confirmation separately from first-breakout entry;
- avoid assuming that a missed first impulse means the whole trade is gone.

Routing: **V2R4 + V3**.

## HYP-03 — Resistance/breakout caution may be too terminal

For `RESISTANCE_BREAKOUT / BLOCKING_OR_CAUTION`:
- 56 mature post-detection 24h cases;
- p50 post-detection 24h MFE = +6.163%.

Candidate direction:
- do **not** delete resistance logic;
- test whether selected cases should become WAIT/watch with explicit confirmation conditions instead of immediate terminal rejection.

Routing: **V2R4 + V3**.

## HYP-04 — Extended setups need pullback/rebuild logic, not broad relaxation

Current mature `EXTENDED` sample:
- n = 17;
- 10 >= +5%;
- 5 >= +10%;
- p50 24h MFE = +5.263%;
- p50 24h MAE = -2.93%.

Interpretation:
- substantial upside can remain;
- adverse excursion is materially worse than in CONTINUITY;
- therefore the likely research direction is pullback / rebuild / second leg, **not chase**.

Routing: **V3**.

## HYP-05 — Cost-edge failures may sometimes mean "bad entry now", not "dead setup"

For `COST_EDGE / BLOCKING_OR_CAUTION`:
- 39 mature post-detection 24h cases;
- p50 24h MFE = +4.932%.

Candidate direction:
- preserve fee/spread/slippage hurdle;
- distinguish `SETUP_DEAD` from `ENTRY_INEFFICIENT_NOW`;
- test bounded watch/re-entry conditions instead of treating both identically.

Routing: **V2R4 + V3**.

## HYP-06 — Tradability authority must be live Kraken public metadata

At this snapshot:
- 7 QNT/EUR candidates were still forced to REJECT by the legacy static `PAIR_BLOCKED` path;
- `account_tradability_unavailable` appeared in 32/324 initial reason sets and in 24 revalidations.

Candidate direction:
- successor versions use current public Kraken `AssetPairs`, online Spot-EUR only, as operational tradability truth;
- absence of private account-specific tradability data must not become negative paper evidence when public Kraken metadata is valid.

Routing: **V2R4**. This is already prepared in the V2R4 release policy and must be reconfirmed at release review.

## Required disposition at the next strategy review

At the final V2R3 review, every hypothesis above must receive exactly one status:

`CONFIRM` / `CHANGE` / `ADD` / `REJECT` / `MORE_TESTING_REQUIRED`

Then:
1. timing/watch changes route into the V2R4 release candidate;
2. larger signal/state/entry-structure changes route into V3 research;
3. anything not supported by mature evidence remains a hypothesis;
4. no item may silently disappear during version migration.

## Versioning rule

This V1 card is an immutable interim snapshot. Do **not** silently overwrite its evidence when the series matures. If the evidence materially changes before final review, create `V2R3-ADJ-HYP-...-V2` (or a final-review disposition artifact) and link both versions.
