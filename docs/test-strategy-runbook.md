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

## 11. Fast-track strategy iteration — adopted 2026-10-03

Purpose: shorten calendar time to a decision without weakening evidence quality, safety,
or release integrity.

Binding rules:

- **Parallelize independent work.** While a frozen prospective series is collecting,
  successor implementation, inactive shadow preparation, component research and release
  plumbing may proceed in parallel, provided none of those changes mutate the active
  series or contaminate its evidence.
- **Do not serialize V2R4 and V3 unnecessarily.** After the V2R3 completion/release
  review, V2R4 paper evaluation and the smallest valid V3 shadow candidate may collect
  evidence concurrently because they answer different questions.
- **Use the smallest valid V3 candidate.** The first serious V3 shadow candidate does
  not wait for every H-component. Only components actually selected for that candidate
  must have their own required gate closed.
- **24h sanity gate:** verify mechanics, persistence, duplicate/stale behavior and obvious
  decision-path defects. This is not a performance-promotion gate.
- **72h early productivity gate:** review trade/candidate frequency, WAIT/REJECT structure,
  obvious pathological selectivity and technical validity. A clearly unproductive branch
  may be stopped early; no threshold is changed inside the running frozen version.
- **~7-day decision gate:** unless a preregistered component-specific gate requires more
  maturity, decide whether the candidate has earned continued collection, should be
  rejected, or should be replaced by a separately versioned successor.
- **No automatic long extension for low trade count.** If hundreds of valid candidate
  decisions again produce essentially no trades, low trade frequency is a strategy result,
  not a reason to keep the same version running indefinitely.
- **No mid-run tuning.** Any material strategy change creates a new version/series. Existing
  evidence remains attached to the old frozen version.
- **Reuse prior PASS evidence.** Infrastructure/source/recovery tests are not rerun merely
  because a strategy version changes when the tested path itself did not change.
- **Stop dead branches early.** Once a preregistered gate is sufficient to conclude that a
  component/branch lacks decision-relevant incremental value, stop expanding it and route
  effort to the next highest-value hypothesis.
- **Quality remains primary.** Fast-track means reducing idle/duplicate calendar time, not
  loosening cost, liquidity, stale-data, execution-safety or release-integrity controls.

Current calendar intent, subject to evidence maturity rather than date alone:

1. 2026-10-03 through V2R3 completion: keep V2R3 frozen while finalizing V2R4 readiness
   and preparing the smallest valid V3 shadow candidate in parallel.
2. At the V2R3 completion gate: perform the final evidence classification immediately;
   do not add an arbitrary extra waiting period.
3. After review: start the new homogeneous V2R4 paper series and the eligible V3 shadow
   candidate concurrently.
4. Apply the 24h / 72h / ~7-day decision cadence to new strategy candidates.
5. Live/private execution remains a later, separate gate and is not accelerated by this rule.

This section complements, and does not override, the smoke-before-duration, no-repeat,
freeze, holdout, and explicit release rules above.

## 12. Mandatory analysis-to-action loop — adopted 2026-10-04

Every **substantive** targeted interim or final analysis is incomplete until its
decision-relevant consequences have been processed. The report itself is not the end
product.

After an analysis gate opens and real analysis is performed, execute this sequence
automatically within the existing autonomy/safety boundaries:

1. **Extract learnings.** Separate evidence-backed findings from speculation, outliers and
   unresolved confounders. Explicitly distinguish strategy/filter issues, timing/runtime
   issues, data/provenance issues, cost/execution issues and genuine no-change findings.
2. **Deduplicate against current design.** Check whether each learning is already covered
   by V2R4/V3, an existing hypothesis, research contract, backlog item or guardrail. If so,
   strengthen/link the existing item rather than creating duplicate machinery.
3. **Convert to consequences.** For each material learning choose the smallest appropriate
   downstream action:
   - update/create a versioned hypothesis/evidence/disposition artifact;
   - route the point to V2R4, V3 or the migration ledger;
   - update backlog/master status when materially changed;
   - prepare a bounded preregistered test/research contract or read-only analysis step when
     this is already within the approved project scope;
   - record explicitly that no action is warranted when evidence does not justify one.
4. **Execute safe follow-through immediately.** Documentation, deduplication, read-only
   checks, report linking, Ack-state updates, inactive research/test preparation and other
   reversible/documentable actions are performed without waiting for a separate user
   prompt when they are clearly inside the already approved scope.
5. **Preserve release boundaries.** Never turn an analysis result directly into a silent
   strategy/runtime/release change. No automatic threshold, entry, stop, sizing, scanner,
   frozen-series, V2R4 activation, V3 promotion or real-money/account/order change.
   Those remain subject to the existing version/freeze/release/user gates.
6. **Persist processing state.** Record which analysis/report was processed, what
   downstream artifacts/items were updated, and whether anything remains
   decision-gated. This prevents the same learning from consuming Work again.
7. **Notify only when useful.** Routine successful consequence-processing stays silent.
   Notify the user only for a material strategic conclusion, a meaningful closed gate,
   a required user/release decision, a manual MINI-PC action or a non-self-healable blocker.

A substantive analysis that merely writes a report but leaves obvious approved
consequence-processing for a later chat is therefore considered **incomplete**.

This rule applies equally to V2R3 intermediate/final reviews and later V2R4/V3
Work-level synthesis. It complements the fast-track rules and never weakens freeze,
holdout, no-midrun-tuning, cost, safety or release controls.

### 12.1 Gated-change escalation — mandatory user decision packet

If consequence-processing concludes that a currently gated change is **materially warranted**
(for example a strategy/threshold/entry/stop/sizing/scanner rule change, V2R4 activation,
V3 promotion, or another release-boundary change), the system must not merely leave it as
a passive note.

It must create a compact **DECISION REQUIRED** packet and notify the user at the next
meaningful analysis/gate completion. The packet must contain:

- **What should change** — exact component/rule/version.
- **Why now** — evidence and sample/gate that justify the change.
- **Expected benefit** — what problem the change is intended to solve.
- **Main risk / downside** — including overfitting, trade-frequency, cost or runtime risk.
- **Exact proposed implementation** — bounded diff/variant; no vague “optimize further”.
- **Validation plan** — which paper/shadow gate proves or rejects it.
- **Rollback** — explicit previous version / revert path.
- **Recommendation** — `APPROVE`, `REJECT`, or `MORE_TESTING` with a clear preferred choice.

The user notification must be action-oriented and clearly labeled **ENTSCHEIDUNG ERFORDERLICH**.
Routine findings that do not justify a gated change remain silent.

After user approval, execute the already-defined safe release/change workflow automatically
as far as possible, including versioning, tests, documentation, and rollback preparation.
Only stop again if a further genuine human/release gate is reached.

No gated change may be activated without the required explicit approval.

### 12.2 Mandatory V2R3 → V2R4 inheritance disposition

Every material V2R3 strategy learning produced by an interim or final analysis must receive
an explicit V2R4 inheritance disposition before V2R4 paper activation can be approved.
Allowed dispositions:

- `ALREADY_COVERED_V2R4` — the prepared V2R4 candidate already implements the intended behavior; link exact component/evidence.
- `PROPOSE_V2R4_CHANGE` — evidence supports a concrete change to the inactive V2R4 candidate; prepare the exact bounded diff and validation/rollback plan, then raise `ENTSCHEIDUNG ERFORDERLICH` before modifying strategy mechanics.
- `MORE_TESTING_BEFORE_V2R4` — potentially relevant but evidence is not mature enough; define the smallest required test/gate.
- `V3_ONLY` — structural/experimental change is deliberately not part of V2R4; route to V3 with rationale.
- `NO_V2R4_CHANGE` — evidence supports retaining current V2R4 behavior or no actionable change.
- `REJECTED` — hypothesis is contradicted or economically/operationally unjustified.

No material V2R3 finding may remain without one of these dispositions at the V2R3 final review.
The V2R4 release review must reconcile the complete disposition set against the exact
V2R4 behavior diff/spec. Any `PROPOSE_V2R4_CHANGE` without explicit user approval or any
unresolved material disposition blocks V2R4 activation.

After explicit approval of a proposed V2R4 change, implementation into the inactive V2R4
candidate, versioning, tests, documentation and rollback preparation should proceed
automatically as far as existing gates allow. Activation remains a separate explicit release gate.
