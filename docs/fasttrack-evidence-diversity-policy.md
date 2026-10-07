# Evidence-Diversity Fast-Track Policy

Status: **CANONICAL / BINDING GOVERNANCE POLICY**  
Policy ID: `EVIDENCE_DIVERSITY_FASTTRACK_V2`  
Effective: 2026-10-05  
Scope: V2R3, V2R4, V3, every later paper/shadow strategy generation, and successor validation during the later real-money phase.

## Purpose

The project must reach a decision at the **earliest methodologically defensible evidence point**.
A fixed calendar duration is never a sufficient reason by itself to keep a frozen strategy
running after the required evidence is already present.

Fast-track does **not** mean lowering evidence quality. It replaces arbitrary waiting with a
combination of sample size, evidence maturity, temporal diversity, integrity and explicit
release controls.

## Permanent rules

1. **Sample floor is version-specific and preregistered.**
   Each strategy/test contract defines the minimum number of independent qualifying outcomes,
   completed trades, labels or other decision-relevant observations needed for that question.

2. **The qualifying cohort is fixed.**
   Once the sample floor is reached, the earliest qualifying observations form the cohort used
   for the release/completion decision. Later observations may remain useful evidence but do not
   move the gate indefinitely.

3. **No fixed calendar wait by itself.**
   A strategy is not forced to run for 7 days, 14 days or another arbitrary duration merely
   because that period was once used as a default. A longer time requirement is allowed only
   when a component-specific maturity/regime contract was preregistered because the question
   genuinely requires it.

4. **Temporal diversity is mandatory.**
   The default guard for high-frequency candidate strategies is:
   - observation span >= `max(48h, 2 × required follow-up horizon)`;
   - >= 3 distinct UTC observation dates;
   - no single UTC date contributes > 50% of the qualifying cohort;
   - no rolling 24h window contributes > 60% of the qualifying cohort.

   A strategy-specific contract may require stricter values when regime/event dependence
   warrants it. It may not loosen these values after seeing results.

5. **Evidence maturity is mandatory.**
   By default, at least 95% of the qualifying cohort must have reached the required follow-up
   horizon, and at least 95% of those mature observations must have complete follow-up data.
   Documented data-quality exceptions remain explicit and cannot be silently treated as wins.

6. **Integrity and provenance remain hard gates.**
   Duplicate/stale/corrupt evidence, unresolved CRITICAL runtime/data-quality faults, PIT leakage,
   fingerprint drift or other validity failures block promotion regardless of sample size.

7. **No mid-run tuning.**
   Entry, stop, sizing, scanner, thresholds, model parameters or other material strategy mechanics
   are never silently changed inside a frozen collection series. A material change creates a new
   version/series with its own evidence.

8. **Stop intake before final maturity when the collection target is satisfied.**
   As soon as the preregistered sample/primary target and temporal-diversity gate are satisfied,
   no new candidates are admitted to that frozen cohort. Existing WAIT/revalidation, positions and
   required follow-ups continue until mature. This prevents unnecessary model calls and prevents
   the completion cohort from moving indefinitely.

9. **Immediate review at gate.**
   When sample, diversity, maturity and integrity gates are satisfied, the final/release review
   starts immediately. No arbitrary extra waiting period is added.

10. **Low trade frequency is evidence.**
   A large valid candidate cohort with very few or zero trades is a strategy result, not a reason
   to keep the same version running indefinitely.

11. **Safety gates are separate.**
    Fast-track never bypasses execution safety, least-privilege API controls, kill switch,
    reconciliation, stale/duplicate protection, rollback, explicit release approval or other
    live/private safety requirements.

12. **Completed-gate finality / no moving-target re-blocking.**
    Once a preregistered completion/release gate has been satisfied for its fixed qualifying
    cohort, the required review has been completed, and any required explicit approval has been
    recorded, that gate is frozen as a timestamped decision snapshot. Later rolling telemetry,
    newly arriving shadow events, denominator growth, or continuously accumulating observations
    must not retroactively turn that already-completed gate back into a blocker or force the same
    release/strategy transition into another waiting loop. New post-snapshot evidence belongs to
    ongoing monitoring or the successor evidence set.

    A completed gate may be reopened only by a **new material validity or safety defect** that
    specifically invalidates the frozen evidence, release artifact, runtime integrity, or safety
    assumptions used for the decision. Ordinary arrival of additional valid observations is not
    such a defect. This rule applies permanently to V2R4, V3, every later paper/shadow generation,
    all future strategy switches, and successor validation in the real-money phase.

## Current V2R3 application

Series: `PAPER-V2R3-CLEAN-20261001T0925Z`

Primary path:
- target completed paper trades: 20;
- temporal-diversity gate still required;
- once trade target + temporal diversity are reached, **new-candidate intake stops automatically**;
- the already admitted cohort is then allowed to mature without adding new observations;
- >=95% of that frozen primary cohort must be at least 24h old;
- >=95% 24h follow-up coverage among the mature primary cohort is required before `PRIMARY_READY`.

Alternative path:
- 1,000 qualifying Candidate-Outcomes;
- once 1,000 outcomes + temporal diversity are reached, **new-candidate intake stops automatically** while maturity finishes;
- qualifying cohort = earliest 1,000 valid outcomes;
- observation span >= 48h;
- >= 3 UTC dates;
- max single UTC date share <= 50%;
- max rolling 24h share <= 60%;
- >= 950/1,000 qualifying outcomes mature to 24h;
- >= 95% 24h follow-up coverage among the mature qualifying outcomes;
- downstream V2R3 integrity/release gates remain required.

This governance change does not alter V2R3 entry, stop, sizing, scanner, cost or execution
mechanics. It replaces only the former fixed 7-day completion floor.

## Future V2R4 / V3 / later generations

Every new strategy candidate must preregister:
- sample unit and minimum sample floor;
- required follow-up/maturity horizon;
- temporal-diversity thresholds;
- integrity/provenance requirements;
- exact decision the gate is intended to support;
- rollback/predecessor reference.

Default decision cadence:
- ~24h: technical/mechanical sanity only;
- ~72h: early productivity/pathology review;
- final continuation/promotion/replacement decision: **as soon as the preregistered
  evidence-diversity gate is satisfied**, not automatically at day 7.

If a low-frequency strategy cannot reasonably meet the default concentration metrics, its
contract must define an equivalent or stricter independent-window/regime rule **before**
performance is inspected.

## Real-money phase

The same principle continues after live trading starts.

Live evidence continuously feeds the successor pipeline:
`live evidence -> analysis -> inactive successor -> shadow/paper/OOS validation ->
evidence-diversity gate -> explicit live release`.

The currently active real-money strategy never self-retunes from live results. Fast-track
applies to how quickly a successor may be judged once enough diverse, mature, valid evidence
exists. It does not weaken live execution safety or human release gates.

## Authority and inheritance

This file is the single source of truth for the fast-track timing/evidence rule. Strategy
version maps, test runbooks, release checklists and automation should reference this policy
instead of copying a different fixed-duration rule.
