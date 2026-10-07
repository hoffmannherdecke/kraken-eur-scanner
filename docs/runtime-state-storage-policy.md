# Runtime State / Evidence Storage Policy

Status: **CANONICAL / BINDING**  
Effective: 2026-10-05

## Goal

Keep source control small, reviewable and protectable while preserving complete runtime
and research evidence.

## Authoritative responsibilities

### GitHub `main`
GitHub contains only:
- source code;
- frozen strategy/config contracts;
- tests and workflow definitions;
- canonical architecture/runbooks;
- compact release/gate evidence and migration ledgers.

GitHub is **not** the durable runtime database for new strategy generations.

### Supabase
Supabase is the durable structured archive for:
- scanner detections / candidate handoffs;
- evaluator decisions and revalidations;
- paper trade results and follow-ups;
- V2R4/V3 shadow evidence;
- timing, health, gate and research state.

Runtime tables are backend-only. Direct `anon`/`authenticated` access is revoked and
RLS remains fail-closed.

### MINI-PC
The MINI-PC holds only operationally necessary local state:
- latest realtime snapshots;
- bounded trigger plans;
- short-lived queues/buffers;
- heartbeats;
- bounded logs;
- local backup/restore state.

Local operational files use bounded retention and are not a substitute for the durable
archive.

### GitHub Actions artifacts
Artifacts are for temporary diagnostics/smokes only and must use bounded retention. They are
not canonical strategy state.

## V2R3 compatibility exception

`PAPER-V2R3-CLEAN-20261001T0925Z` began before this storage policy and is intentionally
kept homogeneous. Therefore its already-established Git runtime persistence remains a
**temporary compatibility lane only** until its evidence-diversity collection/review gate
closes.

This exception is bounded:
1. At sample/temporal-diversity intake stop, scanner detection continues but **no new Git
   evaluator handoffs are admitted**.
2. Existing WAIT/revalidation/position/follow-up state may finish maturing.
3. A retention workflow verifies corresponding Supabase evidence before deleting any
   non-active/closed runtime files.
4. When V2R3 is completion-ready, final-review-allowed and integrity=HEALTHY, the active
   V2R3 Git runtime tree is retired after archive reconciliation.
5. No successor may copy this legacy Git-runtime pattern.

This is infrastructure-only and does not alter V2R3 strategy mechanics/fingerprints.

## V2R4 / V3 / future generations

All new runtime/shadow generations use:
`producer -> Supabase structured evidence -> analysis/release views`.

They must not commit high-frequency runtime observations to `main`.

Any new evidence stream must define before activation:
- table/schema and immutable identity key;
- idempotency/upsert semantics;
- timestamp/monotonicity rules;
- retention;
- RLS/grants;
- source/provenance fields;
- reconciliation check;
- bounded local fallback behavior.

## Branch protection target

The V2R3 compatibility lane retired on 2026-10-07 after the clean series reached
`closed_complete`, its 1005 candidate outcomes were verified in Supabase, and V2R4 PAPER
became the active MINI-PC/Supabase runtime.

Repository-side cutover requirements are now binding:
- no high-frequency runtime state is written to `main`;
- scanner and runtime automation use read-only repository access unless a future PR workflow
  explicitly needs a feature branch;
- compact code/config/release-evidence changes go through PR;
- no force-push/delete on `main`;
- required validation checks protect merges;
- automation has no normal bypass of `main`;
- emergency bypass is owner-only and explicit.

The code-side cutover is complete. The GitHub-hosted branch/ruleset setting is an external
repository-admin control and must be enabled after this cleanup PR is merged.
