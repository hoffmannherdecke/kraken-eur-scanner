# MINI-PC analytics read-only reuse preflight v1

Status: **PREPARED_INACTIVE — PHYSICAL E2E UNVERIFIED**  
Gate fingerprint: `191504e22a3280b1aec5`  
Scope: approved preparation only; no runtime, scheduler, strategy, database or trading mutation.

## Decision

No new collector, Cron, model call, database writer or strategy adapter is warranted. The required preparation can reuse three existing components:

| Need | Existing owner | What is already proven |
|---|---|---|
| Candidate → first decision → WAIT/recheck funnel | `tools/v2r4-readonly-decision-funnel.py` | One-shot local read; deduplicates initial candidate IDs, separates recheck events from candidates, reports TTL gaps and missing structured entry provenance; no network/model/write path |
| Closed 1m/5m/15m, volume and ATR input | `paper_evaluator/successor_coin_entry_evidence_v1.py` | Inactive public Kraken-EUR adapter; closed-bar/PIT rules, `observed_at_utc`/`known_at_utc`, stale/incomplete/missing fail-closed states, no BUY authority |
| Same-snapshot comparison envelope | `tools/run-minipc-v3-entry-model-compare.ps1` | Plan-only by default; temporary detached worktree, pinned technical series and PAPER/real-money guards |

The model-compare wrapper is **not** part of this cost-free preflight execution: `-Execute` may make two model calls and therefore remains gated. The public Kraken loader is likewise not invoked here. Its pure transformation and fixture tests are sufficient for preparation.

## Exact safe local checks

Run only against the already pinned PAPER technical app. These commands do not start services, schedules or writes:

```powershell
python tools/v2r4-readonly-decision-funnel.py --app "$env:USERPROFILE\Trading\Runtime\v2r4-paper-stage-d8b35a8ec2e6" --series "PAPER-V2R4-20261009T110135Z"
python -m unittest tests.test_v2r4_readonly_decision_funnel -v
python -m unittest tests.test_successor_coin_entry_evidence_v1 -v
pwsh -NoProfile -File tools/run-minipc-v3-entry-model-compare.ps1
```

The last command must remain plan-only. Do not pass `-Execute` under this preflight.

## Required join and evidence semantics

A later authorized physical one-shot must keep these fields on the same candidate clock:

- stable `candidate_id`, pair, original event time and first decision time;
- recheck event identity separate from the unique candidate;
- entry evidence `observed_at_utc`, `known_at_utc` and `available_for_decision_no_earlier_than_utc`;
- closed-bar status for 1m/5m/15m, volume ratio and 15m ATR/recent low;
- bid/ask spread, fee assumption 0.60% per side, slippage assumption and TTL at the decision/recheck;
- later MFE/MAE and missed-move/valid-risk-avoidance outcome joined only after its horizon matures;
- missing/stale/incomplete data as `UNKNOWN` or censored, never zero loss or a bearish vote.

Candidate IDs are the join key. Rechecks are events, not extra candidates or trades. A later same coin retrigger is distinct only when it has a new canonical candidate ID.

## Smallest remaining physical gate

No additional offline wrapper is justified before the V2R4 productivity review because the existing funnel and entry-evidence adapter already cover the read-only mechanics, while actual candidate-specific integration would cross the frozen-series boundary.

After the V2R4 72h report is genuinely complete and acknowledged:

1. run the funnel once on the then-authoritative technical PAPER app;
2. verify one real candidate can be mapped to closed-bar entry evidence without backdating;
3. persist only a report/evidence artifact through the approved research path;
4. compare baseline versus input-only evidence with evaluator/WAIT unchanged only after the separate release gate;
5. stop on any series mismatch, missing provenance, stale bar, unverified fee/spread/MAE join or absent physical E2E.

## Completion and blockers

Preparation is complete. Physical MINI-PC E2E is intentionally **PENDING** until the V2R4 economic review and the normal explicit research/release gate. This document proves reuse selection and the bounded command path only. It does not prove a runtime run, strategy benefit, BUY conversion, paper fill, or release readiness.

Permanent guards: PAPER only; real-money actions false; no private Kraken endpoints; no secrets access; no Supabase writes; no service/task/scheduler changes; no V2R4/H3/H6 mutation; no threshold, entry, stop or sizing changes.
