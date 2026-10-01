# V2R3 → V2R4 Release Diff

Status: **PRE-RELEASE DIFF / NO ACTIVATION AUTHORITY**

Purpose: make every behaviorally relevant V2R4 difference explicit before a later paper activation review. This prevents the phrase “V2R4 is mainly a timing change” from hiding unrelated mechanics.

Control:
- V2R3 runtime: `V2R3-2026-09-28`
- active clean series: `PAPER-V2R3-CLEAN-20261001T0925Z`
- V2R4 code candidate: Draft-PR #9
- V2R4 proposed spec: `research/v2r4/paper_strategy_spec_v2r4_proposed.json`

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
| Paper sizing | 50 EUR scout + 50 EUR stage 2 | proposed default 75 + 75; higher adaptive tiers described | **UNRESOLVED / CONFOUNDER** | adaptive mapper not wired |
| Setup-quality tier mapper | none | proposed but not implemented | **MORE_TESTING_REQUIRED** | explicit spec gate currently unsatisfied |
| Major-market/derivatives/catalyst roles | current V2R3 evaluator behavior | proposal documents research roles | MORE_TESTING_REQUIRED | do not assume metadata equals wired behavior |
| Reason-code taxonomy | current free model reason codes | normalization explicitly required by proposal | MORE_TESTING_REQUIRED | not a reason to alter active V2R3 |
| Scanner cadence | ~10-minute target + event dispatch | local event-near discovery/recheck plus fallback | ADD | measure, do not infer superiority from heterogeneous samples |

## Important release finding

The current V2R4 proposal is **not purely a timing-only change**.

The timing/monitoring additions are the core hypothesis, but the proposed paper spec also changes paper sizing from V2R3's 50+50 EUR default to 75+75 EUR and describes larger adaptive tiers. The same spec says:

- `adaptive_sizing_contract_required_before_full_v2r4_series = true`
- `adaptive_sizing_runtime_status = NOT_YET_WIRED_USE_75_PLUS_75_FOR_E2E_SMOKE_ONLY`

Therefore a full V2R4 paper series cannot honestly be called release-ready until the sizing question is resolved explicitly.

No sizing decision is made by this document.

## Methodological guardrail for later activation review

Before V2R4 paper activation, choose and version exactly one of these approaches:

1. **Timing-isolation approach**  
   Keep V2R3 paper sizing unchanged for the first V2R4 timing/revalidation series, so timing/discovery effects are easier to attribute. Adaptive sizing becomes a later separately versioned experiment.

2. **Combined V2R4 approach**  
   Implement and test the adaptive sizing contract first, then accept that the V2R4-vs-V2R3 result combines timing/discovery and sizing changes and cannot isolate their causal contributions.

This is a release-design decision, not an infrastructure repair. It must be explicit in the final activation review rather than silently inferred.

## What can continue without that decision

- V2R3 clean evidence collection;
- V2R4 WS shadow/outcome collection;
- scanner-vs-shadow timing matching;
- health/watchdog hardening;
- PR #9 compile/unit/public-data validation;
- release-readiness documentation;
- reason-code and outcome analysis that does not change the active strategy.

## Activation boundary

This diff does not permit merge or activation.

The fail-closed Supabase view `public.v2r4_activation_readiness` remains authoritative for automated blocking only, and `automatic_activation_allowed=false` by design. A later release review still requires mature clean V2R3 evidence plus an explicit manual decision.
