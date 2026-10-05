# V2R3 → V2R4 Release Diff

Status: **PRE-RELEASE DIFF / NO ACTIVATION AUTHORITY**

Purpose: make every behaviorally relevant V2R4 difference explicit before a later paper activation review. This prevents the phrase “V2R4 is mainly a timing change” from hiding unrelated mechanics.

Control:
- V2R3 runtime: `V2R3-2026-09-28`
- active clean series: `PAPER-V2R3-CLEAN-20261001T0925Z`
- Historical V2R4 module candidate: superseded PR #9 (evidence only)
- Binding first-series release contract: `research/v2r4/paper_strategy_spec_v2r4_release_candidate.json`

## Continuous V2R3 → V2R4 learning inheritance rule

V2R4 is not a static snapshot prepared once and then insulated from later V2R3 evidence.
Every material V2R3 interim/final analysis finding must be reconciled against this release diff
before V2R4 paper activation.

Required disposition per material finding:
`ALREADY_COVERED_V2R4` / `PROPOSE_V2R4_CHANGE` / `MORE_TESTING_BEFORE_V2R4` / `V3_ONLY` / `NO_V2R4_CHANGE` / `REJECTED`.

`PROPOSE_V2R4_CHANGE` means: prepare an exact bounded candidate diff plus evidence, validation
and rollback plan and raise `ENTSCHEIDUNG ERFORDERLICH`. It does **not** authorize silent
strategy modification. After explicit approval, apply the change to the inactive V2R4 candidate
and run the normal tests automatically. V2R4 activation remains separately gated.

Therefore the eventual V2R4 paper version must reflect the **latest approved V2R3 learnings**,
not merely the older draft state of PR #9.

## Behavioral diff matrix

| Area | V2R3 | V2R4 candidate | Release classification | Current status |
|---|---|---|---|---|
| Real money | disabled | disabled | CONFIRM | locked |
| Fees | 0.60% taker / side | same | CONFIRM | locked |
| Exit / trailing / max hold | current V2R3 structure | inherited unchanged in proposal | CONFIRM | no change intended |
| Two-stage entry | required | required | CONFIRM | no bypass allowed |
| Kraken tradability universe | evaluator still contains legacy static blocked-pair path | current public Kraken `AssetPairs`, online Spot-EUR only; no static pair blacklist | CHANGE | technically prepared/tested |
| WAIT representation | free-text missing triggers permitted | deterministic `watch_conditions` required for WAIT | CHANGE / ADD | technically prepared/tested |
| WAIT monitoring | one-shot TTL/revalidation path | local event-near watcher + optional Altrady wake-up | ADD | physical E2E green |
| Trigger action | normal scheduled lifecycle | `FRESH_PAPER_RECHECK_ONLY` | ADD | physical E2E green; never direct buy |
| Pre-candidate visibility | scanner candidate stream after current upstream filters | broad Kraken-EUR observation lane before normal execution review | ADD | WS shadow active; observation-only |
| Reconnect semantics | GitHub/runtime lifecycle | stale rejection, dedup, one-cycle post-gap suppression in WS shadow | ADD | restart/internet recovery green |
| Public tradability metadata unavailable | may become WAIT in V2R3 | V2R4 branch fails closed to REJECT if public tradability cannot be safely confirmed | CHANGE | covered by contract tests |
| Invalid/incomplete BUY two-stage plan | V2R3 fail-safe can downgrade to WAIT | V2R4 branch fail-safe rejects rather than creating an unwatchable WAIT | CHANGE | covered by contract tests |
| Account-private tradability unavailable | can appear in V2R3 decision evidence | explicitly not negative evidence when public online Spot-EUR metadata is valid | CHANGE | proposed/tested paper policy |
| Paper sizing | 50 EUR scout + 50 EUR stage 2 | **50 + 50 for first full V2R4 series** | CONFIRM / CONTROLLED | timing-isolation decision fixed 2026-10-05 |
| Setup-quality tier mapper | none | deferred to later separately versioned experiment | DEFER_TO_LATER_GENERATION | must not affect first V2R4 series |
| Major-market/derivatives/catalyst roles | current V2R3 evaluator behavior | proposal documents research roles | MORE_TESTING_REQUIRED | do not assume metadata equals wired behavior |
| Reason-code taxonomy | current free model reason codes | normalization explicitly required by proposal | MORE_TESTING_REQUIRED | not a reason to alter active V2R3 |
| Scanner cadence | ~10-minute target + event dispatch | local event-near discovery/recheck plus fallback | ADD | measure, do not infer superiority from heterogeneous samples |

## Prospective V2R3 tradability-policy diagnostic — 2026-10-01

The clean V2R3 control series provides a concrete example of why the V2R4 public-tradability policy must be treated as a real behavioral change rather than documentation cleanup.

At a prospective snapshot of the active clean V2R3 series:

- total candidate outcomes observed: **56**;
- candidates whose evaluator reason codes included `account_tradability_unavailable`: **9**;
- of those 9, **all 9** also carried:
  - `kraken_public_pair_verified = true`;
  - Kraken public pair metadata `status = online`.

So about **16.1%** of the current clean-series candidates had an account-private-availability reason attached even though public Kraken Spot-EUR metadata verified the pair as online.

Interpretation guardrail:

- this does **not** prove that those 9 decisions would have become BUY under V2R4;
- reason codes are multi-factor and the same cases also contain structural, volume, resistance, cost or continuity objections;
- no V2R3 rule is changed mid-series;
- no candidate is relabelled;
- this is release-diff evidence only, showing that V2R4's public-online-Spot-EUR policy can remove an account-private-data confounder from future paper decisions.

The later mature 24h outcome review should separately measure whether this reason cluster was associated with missed movement; do not infer that before follow-ups mature.

## Important release finding

The historical V2R4 proposal was **not purely a timing-only change**.

The timing/monitoring additions are the core hypothesis, but the proposed paper spec also changes paper sizing from V2R3's 50+50 EUR default to 75+75 EUR and describes larger adaptive tiers. The same spec says:

- `adaptive_sizing_contract_required_before_full_v2r4_series = true`
- `adaptive_sizing_runtime_status = NOT_YET_WIRED_USE_75_PLUS_75_FOR_E2E_SMOKE_ONLY`

The sizing confounder is now resolved for the first full V2R4 Paper series: **50+50 EUR is binding** so timing/discovery remains the main measured delta. Adaptive tiers are not part of that release candidate.

## Methodological guardrail for later activation review

Prepared sizing decision memo: `docs/v2r4-sizing-release-decision.md`

The first-series choice is now fixed to the timing-isolation approach:

1. **Timing-isolation approach**  
   Keep V2R3 paper sizing unchanged for the first V2R4 timing/revalidation series, so timing/discovery effects are easier to attribute. Adaptive sizing becomes a later separately versioned experiment.

Adaptive sizing remains a later separately versioned successor experiment. It must not be silently folded into the first V2R4 release candidate.

## What can continue without that decision

- V2R3 clean evidence collection;
- V2R4 WS shadow/outcome collection;
- scanner-vs-shadow timing matching;
- health/watchdog hardening;
- superseded PR #9 compile/unit/public-data validation as historical module evidence;
- release-readiness documentation;
- reason-code and outcome analysis that does not change the active strategy.

## Activation boundary

This diff does not permit merge or activation.

The fail-closed Supabase view `public.v2r4_activation_readiness` remains authoritative for automated blocking only, and `automatic_activation_allowed=false` by design. A later release review still requires mature clean V2R3 evidence plus an explicit manual decision.


## Evidence-diversity release timing — governance only

Effective 2026-10-05, V2R3→V2R4 release timing uses
`EVIDENCE_DIVERSITY_FASTTRACK_V2` from `docs/fasttrack-evidence-diversity-policy.md`.
This is **not** a V2R4 behavior/mechanics change. It removes the former fixed 7-day
completion floor and allows the release review at the earliest valid sample/diversity/
maturity/integrity point. Entry, stop, sizing, trigger, recheck and scanner behavior remain
subject to the exact diff in this document.
