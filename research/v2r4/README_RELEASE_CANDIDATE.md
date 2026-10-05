# V2R4 release-candidate preparation

Status: **PREPARED / NOT ACTIVE / PAPER ONLY**

This directory describes the next paper strategy generation. The superseded PR #9
and its earlier proposed spec are historical research material only and are not
activation authority.

## Binding first-series contract

Canonical machine-readable contract:
`paper_strategy_spec_v2r4_release_candidate.json`.

The first full V2R4 Paper series isolates the timing/discovery/revalidation hypothesis
as far as practical while keeping explicit data-quality correctness repairs separate and visible:
- **50 EUR scout + 50 EUR stage 2**, inherited from V2R3;
- adaptive sizing is disabled and deferred to a separately versioned successor experiment;
- major-market, derivatives and catalyst decision-role semantics inherit the frozen V2R3 behavior for this first series; any relaxation is a later separately versioned experiment;
- live public Kraken Spot-EUR tradability replaces legacy static blocked-pair/account-private confounding as an explicit data-quality repair, not a hidden signal change;
- 24h follow-up is explicitly required for `EVIDENCE_DIVERSITY_FASTTRACK_V2` maturity;
- Kraken public data remains execution/condition truth;
- deterministic WAIT wakeups can request only `FRESH_PAPER_RECHECK_ONLY`;
- Altrady is an optional wake-up source, never sole condition truth;
- no private Kraken/order/real-money path;
- high-frequency runtime evidence belongs in Supabase or bounded MINI-PC state, not per-event Git commits.

## Activation order — binding

Technical smoke success is necessary but **never sufficient** to start V2R4.

V2R4 Paper may be activated only after all of the following:
1. V2R3 Evidence-Diversity Fast-Track collection gate is complete.
2. V2R3 clean-series integrity is `HEALTHY`.
3. `public.v2r3_release_review_snapshot.final_review_allowed = true`.
4. The final V2R3 causal review is completed.
5. Every material predecessor finding has a successor disposition in the canonical migration/release diff.
6. V2R4 shadow/transport evidence and MINI-PC health satisfy their release gates.
7. `public.v2r4_activation_readiness.activation_review_state = MANUAL_RELEASE_REVIEW_REQUIRED`.
8. The explicit release decision is `APPROVED_PAPER`.
9. A bounded final paper-only release smoke passes.
10. A new immutable V2R4 series/test ID is created.

`automatic_activation_allowed` remains false permanently.

## Storage architecture

- GitHub: code, frozen specs, tests, canonical docs and compact release evidence.
- Supabase: candidates/decisions/revalidations/follow-ups/shadow/timing/research evidence.
- MINI-PC: bounded realtime state, trigger plans, buffers, heartbeats and TTL logs.
- GitHub Actions artifacts: temporary diagnostics with explicit retention only.

No V2R4 or later runtime may reproduce the V2R3 legacy pattern of committing every
runtime observation to `main`.

## Safety

Nothing in this preparation authorizes V2R4 activation, real-money trading, leverage,
withdrawal rights or automatic capital scaling.
