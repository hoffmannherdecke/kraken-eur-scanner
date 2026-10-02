# Test Strategy & Execution Runbook

Status: **CANONICAL TEST TRIAGE / EXECUTION RULES**  
Scope: project `Aktien & Krypto Chancen`  
Master to-do authority: `PROJECT_BACKLOG.md`

## Purpose

This runbook prevents two opposite failure modes:

1. skipping tests that protect evidence quality, runtime safety or release integrity;
2. endlessly adding low-value tests that delay the project without changing a real decision.

It is **not** a second backlog. Open/blocked work remains only in
`PROJECT_BACKLOG.md`. This document defines which kinds of tests are worth doing,
when they are required, who should execute them and when a previous PASS may be reused.

## 1. Test-value gate — every new test must justify itself

A proposed test is executed only if it answers at least one concrete question:

- **Evidence validity:** can the data / label / known-at / PIT semantics be trusted?
- **Strategy decision:** can this result change whether a component is kept, rejected or promoted?
- **Runtime safety:** can a realistic failure produce stale, duplicate, missing or corrupted decisions?
- **Execution safety:** can a later order path cause unintended size, duplicate orders, stale fills, unreconciled state or unrecoverable behavior?
- **Release integrity:** can the exact code/config/artifact being promoted be reproduced, rolled back and distinguished from prior versions?

A test should normally be rejected or deferred when it merely:
- repeats an already-proven property with no changed code/config/environment;
- measures a metric that cannot change a current or later decision;
- adds a second source that provides no unique information;
- increases sample count without a preregistered sample/reliability gate;
- explores extra thresholds/variants only because earlier results were weak;
- requires substantial user time while the same question can be answered in CI, public APIs, Supabase or existing evidence.

## 2. Autonomy-first execution rule

Default executor is ChatGPT through existing GitHub/Supabase/public read-only tooling.

### A — fully autonomous
ChatGPT should execute without asking the user:
- repository/static validation;
- unit/self-tests;
- GitHub Actions CI;
- public REST/WS/API response-shape and bounded source smokes;
- Supabase read-only evidence/readiness checks;
- point-in-time/known-at validation using already available data;
- report parsing and effect-size reviews from supplied/persisted artifacts;
- backlog/documentation/reconciliation updates;
- issue/release evidence updates;
- bounded reruns after a technical fix.

### B — user only when physically unavoidable
Ask the user only when the proof depends on:
- the physical MINI-PC/Windows environment or home network;
- BIOS/power-loss/device/storage hardware;
- an account UI/login/secret that ChatGPT cannot access;
- a real externally transported event that cannot be generated safely in cloud CI;
- an account-specific private Kraken state/fee tier;
- a deliberately human release/live-activation decision.

User actions should be **batched** into the smallest safe command/run possible.
Before asking for a long physical run, first perform the shortest cloud/static smoke
that can catch implementation errors.

## 3. No-repeat rule

A previous PASS remains valid unless at least one of these is true:

- relevant code or configuration changed;
- data/source schema or API semantics changed;
- hardware/OS/network/runtime environment materially changed;
- the test has an explicit freshness/expiry requirement;
- an incident contradicts the prior evidence;
- the later gate requires a different scope (for example cloud PASS -> physical MINI-PC PASS).

Therefore:
- do **not** repeat reboot, internet-loss, recovery, backup, WS transport or source-shape
  tests just to “be extra sure” when their relevant system has not changed;
- after a bug fix, rerun the **smallest regression test that covers the bug**, then the
  next required real environment gate;
- a technical failure is never counted as strategy evidence.

## 4. Smoke-before-duration rule

Order of work:

1. static/contract guard;
2. deterministic self-test;
3. shortest bounded real-source/cloud smoke;
4. shortest required physical smoke, only if environment-specific;
5. long prospective collection / shadow run;
6. effect-size/performance review only after the preregistered collection gate.

A failed step blocks only its dependent branch. Work should continue on independent
open items rather than waiting.

## 5. Required test families by project phase

### Phase A — before the first serious V3 shadow candidate

Required only for components that may enter the candidate:

- exact input/provenance and PIT/known-at semantics;
- frozen hypothesis/trial contract and search accounting;
- component-specific minimum data/sample gate;
- no-threshold/no-midrun-tuning guard where applicable;
- exact report/effect-size review;
- one-change candidate contract;
- same candidate stream / same market clock comparison;
- candidate materialization self-test + smallest E2E shadow smoke;
- frozen baseline/config/code fingerprints.

Current practical implication:
- finish the already-running H3 collection gate;
- import/review exact H1/H6 reports;
- do **not** force H2/H4/H7/H8/H9/H10/H11 to completion merely to start a first
  V3 shadow candidate unless one of those components is actually selected for it.

### Phase B — before V3 component promotion

Required:
- enough prospective/OOS evidence under the frozen contract;
- realistic cost treatment where the component affects entries/exits;
- no unresolved PIT/data leakage issue;
- no technical-invalid sessions mixed into strategy evidence;
- migration-ledger classification;
- explicit promotion gate and rollback target.

Not automatically required:
- every research hypothesis in the project;
- every possible sensor/source;
- every parameter variant.

### Phase C — before paper release / runtime activation

Required:
- exact release/config freeze;
- CI/static guards;
- smallest real E2E paper smoke;
- persistence/restart/reconciliation appropriate to the changed component;
- stale/duplicate fail-closed behavior where the changed path can affect decisions;
- rollback proof/reference.

Do not repeat unrelated infrastructure tests if the changed release cannot affect them.

### Phase D — before any later live/private execution

Required separately and much later:
- account-specific current Kraken fee tier/state verification;
- least-privilege private API permissions, no withdrawal rights;
- startup account reconciliation;
- stale-data rejection;
- duplicate-order / position / size / price-deviation gates;
- order lifecycle + fill/cancel race handling;
- deadline/cleanup-taker contract;
- explicit, testable queue/fill assumption before maker modelling;
- persistent kill switch;
- circuit breaker;
- restart / network-loss / recovery proof for the **actual execution path**;
- controlled E2E execution smoke before broader activation.

These are not blockers for present V3 research/shadow work.

## 6. Deferred/data-maturity tests

Some tests are valuable but cannot be made meaningful by spending more time today.

Examples:
- H4 stop/TTL regime work waits for mature MAE/MFE / trade evidence;
- H7 meta TAKE/NO-TAKE waits for frozen labels and enough clean outcomes;
- H8 on-chain association waits for additional prospective known-at depth;
- H9 fill-probability work waits for the execution-stage data/assumptions;
- H10 smart-money quality needs a frozen unbiased public-address selection rule and
  a meaningful prospective observation window;
- H11 prediction-market predictive value needs longer-horizon prospective capture
  and an event-relevance contract.

These should remain open/deferred in `PROJECT_BACKLOG.md`, not be accelerated by
arbitrary extra smokes.

## 7. Physical/user test budget

Before requesting user involvement, ChatGPT must answer:

1. Why can this not be proven autonomously?
2. What exact gate will the result close?
3. What is the shortest safe run?
4. Can multiple physical checks be combined?
5. What output/evidence must the user return?

Long physical tests should not be repeated after technical failures until a short
regression smoke has passed. H3 ASSOC-001 -> ASSOC-002 is the canonical example.

## 8. Evidence retention

For every meaningful test:
- store compact canonical evidence or a reference/hash to the local report;
- record PASS/FAIL/INVALID_TECHNICAL explicitly;
- never convert technical FAIL into strategy FAIL;
- keep immutable trial/search-accounting history;
- avoid raw-data duplication where compact evidence is sufficient;
- update the relevant backlog item immediately.

## 9. Stop conditions

Stop expanding a branch when:
- the preregistered gate is met;
- the result is sufficient to make the intended decision;
- the source/component shows no incremental value under the frozen test;
- data maturity blocks further valid inference;
- a later project phase, not the current phase, is the proper place for the test.

Do not keep testing merely because another test is possible.

## 10. Current execution principle

For the present project stage the priority is:

**finish already-started high-value gates -> review exact evidence -> build the smallest
valid V3 shadow candidate -> collect prospective shadow evidence -> only then expand
additional research branches if they can materially improve the next decision.**

The project should prefer forward progress with bounded, decision-relevant evidence
over exhaustive completion of every research idea.
