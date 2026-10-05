# V2R4 Sizing Release Decision Memo

Status: **DECIDED FOR FIRST FULL V2R4 PAPER SERIES / NO ACTIVATION**

Purpose: reduce the later V2R4 paper-release decision to one explicit choice instead of mixing timing/discovery and sizing changes at the release boundary.

## Current facts

V2R4's primary research hypothesis is a **timing/discovery/revalidation** hypothesis:

- detect early/persistent movers before current upstream filters hide them;
- reduce WAIT-to-trigger latency with deterministic local monitoring;
- always fresh-recheck before any paper BUY decision.

The current proposed V2R4 spec also contains sizing changes:

- V2R3 paper default: **50 EUR scout + 50 EUR stage 2**;
- V2R4 proposal carries **75 + 75 EUR** as an executable E2E-smoke default;
- larger adaptive tiers are described for A/A+ setups;
- the same proposal explicitly says the adaptive setup-quality mapper is **NOT YET WIRED** and requires a separate validated sizing contract before a full V2R4 series.

Therefore sizing is an independent release-design variable.

## Option A — timing-isolation series

For the first full V2R4 paper series:

- keep V2R3 paper sizing at **50 + 50 EUR**;
- change only the V2R4 timing/discovery/revalidation mechanics;
- compare V2R4 against frozen V2R3 on the predeclared timing, MFE/MAE, missed-move and net-return metrics;
- evaluate adaptive sizing later as a separate versioned experiment.

### Advantages

- strongest causal attribution to the actual V2R4 hypothesis;
- cleaner V2R3 ↔ V2R4 comparison;
- easier diagnosis if V2R4 produces more/fewer trades;
- avoids letting larger nominal paper PnL masquerade as better edge;
- does not require implementing a setup-quality sizing mapper before the first V2R4 series.

### Cost

- does not immediately test the user's later intended larger position tiers;
- EUR-PnL magnitude remains deliberately conservative during the first V2R4 paper comparison.

## Option B — combined timing + sizing series

Before first full V2R4 collection:

- implement a deterministic setup-quality tier mapper;
- freeze the exact tier mapping in the V2R4 spec;
- validate minimum-order, two-stage, max-size and no-chase constraints;
- accept that the resulting V2R3 ↔ V2R4 difference combines timing/discovery and sizing effects.

### Advantages

- tests the intended end-state paper behavior sooner;
- produces size-aware EUR-PnL evidence immediately.

### Costs

- materially weaker causal attribution;
- a changed outcome can no longer be cleanly assigned to faster detection/recheck versus notional size;
- additional implementation and test surface before release;
- higher risk of needing another version merely to disentangle sizing from timing.

## Binding first-series decision — 2026-10-05

**Option A is selected: timing isolation.**

Reason: V2R4 exists primarily to test whether earlier discovery and faster fresh rechecks fix the observed timing blind spots. Holding paper sizing constant is the cleanest way to answer that question.

Adaptive sizing should remain a separately versioned follow-up experiment after the first V2R4 timing series has enough evidence.

This decision does **not** change active V2R3 and does not activate V2R4. It resolves only the inactive V2R4 release design: the first full V2R4 Paper series must use **50 EUR scout + 50 EUR stage 2**. Adaptive sizing remains a separately versioned successor experiment and must not be mixed into that first series.

## Required release implementation

At the actual activation-review boundary:

1. copy the V2R4 proposed spec into a frozen release candidate;
2. override sizing only to the inherited V2R3 paper default **50 + 50 EUR**;
3. mark adaptive sizing disabled/deferred;
4. create a new V2R4 series/test ID;
5. rerun contract/unit/E2E release smokes;
6. start paper-only collection only after the normal release checklist passes.

## Later adaptive-sizing experiment

Do not activate the current proposal directly.

First:

1. implement deterministic setup-quality → size mapping;
2. add explicit contract tests for every tier;
3. freeze size caps and stage-2 rules;
4. version the resulting strategy separately;
5. rerun release validation before any paper collection.

## Safety boundary

Nothing in this memo authorizes:

- V2R4 activation;
- real-money sizing;
- Kraken private trading rights;
- orders;
- leverage;
- automatic capital scaling.
