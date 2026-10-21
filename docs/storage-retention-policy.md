# Storage / Retention Policy

Status: **ACTIVE GOVERNANCE / NO STRATEGY EFFECT**  
Date: 2026-10-01

Canonical runtime/state placement policy: `docs/runtime-state-storage-policy.md`.

This document is the compact retention matrix for project-generated operational
data. It does not authorize deleting immutable strategy evidence, frozen trial
records, provenance roots, or historical source archives merely to save space.

## Automated retention

| Scope | Rule | Mechanism | Safety boundary |
|---|---|---|---|
| MINI-PC `Trading\Logs` | delete files older than **14 days** | `tools/minipc-log-cleanup.ps1`, scheduled daily 04:20 by `CryptoMiniPC-LogCleanup` | only local Logs directory |
| MINI-PC `Trading\Temp` | delete files older than **2 days** | same cleanup task | only local Temp directory |
| MINI-PC state backups | keep **14 days** | `tools/minipc-backup.ps1`, scheduled daily 04:00 by `CryptoMiniPC-Backup` | only `minipc-state-*.zip` under Trading\Backup; Secrets/Logs/Repo excluded |
| GitHub manual paper market tapes | delete stale `paper-market-tape-*` artifacts older than **36 h** | `.github/workflows/paper-artifact-cleanup.yml`, daily 03:15 UTC | fresh/manual diagnostics preserved |
| GitHub scanner caches | keep newest **12** `scanner-state-*` caches | same cleanup workflow | immutable rollback window retained |
| stale queued paper runtime jobs | keep newest active run, cancel older active queue entries | `.github/workflows/paper-runtime-queue-cleanup.yml` when invoked | runtime queue only; no evidence deletion |
| maintenance-triggered scanner runs | cancel only active scanner runs caused by maintenance pushes; start one clean run if needed | `.github/workflows/scanner-maintenance-cleanup.yml` when invoked | scheduled/normal scanner semantics preserved |
| H10 exact Hyperliquid fill events | keep **48 hours** | `tools/v3-h10-activity-capture.py` retention maintenance | short-lived exact source-timestamp/debug evidence only; long-term value first aggregated to 5-minute wallet/asset buckets |
| H10 compact wallet/asset 5m aggregates | keep **120 days** | same H10 capture retention maintenance | one row per wallet/asset/complete 5m bucket; upserted/deduplicated; sufficient for fixed-horizon/lead-time research |
| H10 wallet-state snapshots + capture batches/errors | keep **120 days** | same H10 capture retention maintenance; batch delete cascades state/error rows | frozen cohort/contracts remain immutable in GitHub |
| GitHub Paper runtime working tree | only the **active frozen series** may keep per-candidate working files; closed series are compacted after Supabase-ID verification | `tools/repository-runtime-compaction.py` + one bounded maintenance commit | pre-compaction archive ref + Git history retained; active series fail-closed excluded |
| V3/H1 and future shadow runtime evidence | **Supabase/local runtime, not per-event commits to main** | H1 closed-pilot archive + successor contracts | GitHub keeps code/contracts/compact status/release evidence only |
| V3/H3 MINI-PC sidecar evidence | hard local ceiling **200 candidate footprints**; synced pairs are compacted below the ceiling, unsynced data is never deleted | `tools/v3-h3-shadow-runtime.py` using frozen `local_retention_max_evidence_files` plus fail-closed intake backpressure | if sync/evaluation falls behind at the ceiling, only new H3 intake pauses until space is recovered; V2R4 remains unaffected |

GitHub cleanup implementation evidence:
- paper-artifact cleanup check on commit `eefb490c5d82f850bf9171179eaed47d690c0f99`: **SUCCESS**;
- workflow retains a daily schedule and self-tests on workflow changes.

MINI-PC baseline:
- `CryptoMiniPC-LogCleanup` is part of the installed baseline task set;
- `CryptoMiniPC-Backup` is part of the installed baseline task set;
- restore smoke verifies backup readability without modifying live state.

## Deliberately not auto-deleted

The following are provenance/evidence, not disposable cache. "Retained" does not require thousands
of individual files to remain in the default branch: once a backend archive is verified, Git
history plus a named archive ref may preserve provenance while the active working tree is compacted.

- frozen V2R3/V2R4 Paper decisions, revalidations and outcome evidence;
- immutable historical Trial Ledger entries;
- frozen strategy/release manifests and rollback snapshots;
- normalized historical datasets still referenced by an active/reproducible research trial;
- verified raw source archive when it is the only provenance root for derived historical data.

Historical archive parts may be deleted only through a dedicated checksum-gated
cleanup after the joined source archive has been independently verified.
`tools/cleanup-verified-kraken-ohlcvt-parts.ps1` is fail-closed and plan-only by
default for that purpose.

## Current storage posture snapshot — 2026-10-02

A read-only Supabase size audit after the first H10 capture showed the largest current relations are still small: `paper_candidate_outcomes` ~14 MB, `scanner_detection_evidence` ~8.6 MB, `v2r4_shadow_evidence` ~4.2 MB and the first H10 exact-fill table ~0.9 MB. The H10 fill table was nevertheless identified as the clearest future growth hotspot and is now explicitly compacted/TTL-bounded before scale.

Paper decisions/outcomes remain immutable because each research series is itself bounded by a completion/release gate. Scanner/shadow event evidence remains selective rather than raw tick/order-book data and is reviewed at the corresponding release gate before any later archival compaction.

## Raw-data rule

Raw/high-frequency data is not kept merely because it exists.

- live Kraken runtime keeps compact latest snapshots/heartbeats;
- V2R4 stores selective event/outcome evidence rather than endless tick history;
- GitHub/Supabase must not become secondary full raw-market archives;
- new raw datasets require an explicit question, provenance plan, retention rule,
  and storage-benefit gate before collection/download.

## 2026-10-21 — Supabase Disk-I/O warning: shared infrastructure, version-specific senders

**Source boundary:** The Supabase email reports depletion of burst I/O budget, **not** exhaustion of allocated database storage. The 24h dashboard screenshots show low snapshot IOPS/throughput and substantial disk capacity, but they do not independently establish remaining burst credits, nor can they prove that an alert has cleared. Live project status at the read-only review was `ACTIVE_HEALTHY`; neither a sustained outage nor a V3 production writer was established.

**Read-only evidence and attribution:** Historical `pg_stat_statements` totals since the end-of-September reset show substantial WAL and temporary-file work for `paper_candidate_outcomes` upserts. The deployed active V2R4 relay uses conflict-updates; its Mini-PC sender tracks content hashes but truncates the per-candidate successful-send map to 5,000 entries, while the active V2R4 series already exceeded 5,800 candidate records. PostgreSQL transaction-version samples confirm repeated writes of older V2R4 records in 200-row batches. This establishes wasteful repeated writes, **not** the precise current I/O-budget percentage or that all repeated requests are byte-identical. Older `scanner_detection_evidence` writes are also visible in cumulative statistics, but that table had not been recently updated at the time of the review. No deletion, `VACUUM FULL`, index removal, pricing change, or live writer change is authorized from these observations.

**Successor decision:** Do not migrate the V2R4 sender's 5,000-entry eviction rule, historical mutable-outcome upserts, or an emergency V2R4-specific retrofit into the planned V3 Paper writer. The existing V3 path is `paper_evaluator/v3_paper_cloud_receipt_sync_v1.py` -> `v3-paper-evidence-relay` -> `v3_paper_event_receipts`, with immutable event IDs and identical-replay verification. The V3 local acknowledgement list is **not capped at 5,000**; it must never silently forget Cloud-confirmed receipts. The source-level offline regression in `tests/test_v3_paper_mini_cloud_followup_v1.py` covers 5,001 previous acknowledgements, a newly confirmed event, unchanged replay and a failed-then-retried Cloud POST. That is **test evidence only**, not a real Mini-PC deployment or active V3 Cloud cutover.

**Project-wide operating rule:** Supabase remains the common structured evidence authority for current and future versions; event/provenance durability, unchanged replay, exact acknowledgement and post-failure recovery take priority over superficial reductions in write counts. At the V2R4 -> V3 transition, retain the original closed-series lifecycle, any open positions and genuinely due follow-ups under the existing release/aftercare owner. Do not stop or clean the original sender based on this warning alone. Use the existing `storage_and_cost` / `retention_supabase_state_and_cost_control` owner and the present health/reporting paths for real incidents; **no new schedule, manager, service, schema migration, table-index surgery, compute upgrade or additional V3 release gate**. If warnings persist after the verified V3 cutover, compare *new time-bounded* database-statistics deltas, the existing dashboard budget signal and real source/Cloud ACKs before proposing any further shared infrastructure change. Cumulative figures cannot establish a present-day V3 bottleneck.

### 21.10.2026 — Mini-PC/Supabase-Hybrid: deferred post-V3 placement review

**User decision, project-wide operations (not a V3 release gate):** Keep the existing split unchanged until the separately approved **actual V3 Paper go-live**. The current Mini-PC handles time-critical execution, calculation, bounded short-lived buffers and local recovery state; Supabase remains the central durable, protected, structured archive of original decisions, immutable receipts, follow-ups, missed opportunities, negative outcomes, health and research evidence. GitHub remains code/governance/release evidence, not a runtime write sink. This applies independently of V2R4/V3/V4 strategy lineage, with actual producer-specific protocols retained.

**Why defer relocation:** The present Disk-I/O alert is linked to the old V2R4 mutable candidate-upsert lane and does not prove future V3 load. V3 already uses append-only, exact-ACK replay-safe receipts; its higher observation/event coverage could still produce greater **total** Supabase I/O. Moving computation to a Mini-PC only reduces Supabase load if it changes measured database requests/bytes. A pre-go-live move would create new dual-write, recovery, durability, provenance and rollout risks without V3 workload evidence. Neither a blanket Supabase retirement nor a new local durable database is authorized.

**Conditional post-go-live assessment through the existing owner** `research/monitoring-evidence-routing-v1.json#storage_and_cost` → `retention_supabase_state_and_cost_control`:
1. **Baseline:** Reuse time-scoped last known Supabase I/O/burst-credit charts and where possible actual PostgreSQL counter deltas plus Mini-PC CPU/RAM/disk and existing archival ACK-health. Preserve the original collection windows, time zones and release/series boundaries; cumulative `pg_stat_statements` totals are not proof of V3 write rate.
2. **After real V3 Paper activation:** Review ~48–72 hours of actual operation and then a representative week **when data are available**, not by automatically delaying or blocking launch or inventing a scheduled follow-up. Check I/O budget/burst reserve, WAL/write volume, timeouts/latency, Supabase costs, local CPU/disk/queue growth and exact paper/negative/6h/24h/72h follow-up coverage/ACK gaps. Report unknown metrics as not verified.
3. **Only if persistent bottleneck or failure is evidenced:** Assess targeted additional MINI-PC-side ephemeral processing, batching, compression/coalescing of safely recomputable intermediate observations, or bounded buffering **without dropping any distinct immutable decisions or source provenance**. Evaluate expected reduction in actual Supabase calls/WAL against extra local CPU, disk, backup, recovery, source staleness and operational costs; a post-change observation/rollback gate belongs to the existing components, not a new scheduler.
4. **Early exception:** A genuine repeated Disk-I/O warning with evidenced degraded throughput, ACK failure, unbounded retry/queue growth or risk of missing evidence may trigger earlier review via existing `health_watchdog` / `storage_and_cost` owner. No silent changes to V2R4 or pending V3 writer, paper gates, database permissions, retention of immutable evidence, or paid compute are pre-authorized.

**Status:** `DEFERRED_UNTIL_VERIFIED_V3_LIVE_LOAD` / architecture decision archived only. This is an inherited future comparison criterion, not a new outstanding V3 task, calendar reminder, Work cadence, physical host ACK, strategy gate, or claim of completed migration. References: this document's Disk-I/O analysis above, `docs/runtime-state-storage-policy.md` and the existing project manager [Issue #353](https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353).

## Review rule

A new log, cache, artifact, raw dataset, or local work directory is not considered
production-ready until one of these is true:

1. it has an explicit bounded retention/cleanup path; or
2. it is explicitly classified as immutable provenance/evidence and documented as
   such.

Retention changes are infrastructure/governance changes only and must not alter
strategy rules, Paper decisions, release gates, private exchange access, orders,
or real-money behavior.


## Repository working-tree rule — 2026-10-05

Git is source/release control, not the primary runtime database.

- active frozen V2R3 is the last compatibility series allowed to persist per-event working files on `main`;
- closed/predecessor Paper series are removed from the current tree only after candidate-level Supabase verification;
- a named pre-compaction archive ref preserves an easy historical root in addition to ordinary Git history;
- V2R4 and later Paper/Shadow runtimes must persist event/outcome state in Supabase and/or bounded local state, not by creating a commit for every observation;
- GitHub may retain compact release snapshots, checksums, contracts and manifests;
- no cleanup may remove the currently active series or the only copy of evidence.

## Verified capacity baseline and low-cost escalation — 2026-10-13

**Actual read-only check (2026-10-13 ca. 05:16 UTC; snapshot, not live forever):**
Supabase `pg_database_size(current_database())` = **133,409,939 bytes** (about
127 MiB). Largest `pg_total_relation_size` results (including indexes and
TOAST) were `paper_candidate_outcomes` about **48 MiB**,
`v2r4_shadow_evidence` **40 MiB**, `v3_h10_wallet_states` **11 MiB**,
and `scanner_detection_evidence` **10 MiB**. The latest MINI-PC
`minipc_status_current.payload.checks.disk_space` showed
**C: 171 GB free / 237.4 GB**; backup status referenced a fresh 04:00 ZIP.
These observations do **not** establish D: free space, future growth or
that every local cleanup task actually ran.

**Implementation uses the existing capacity owner and Work cadence, no new
sensor, DB table, workflow or schedule.** On 2026-10-13 the **already enabled**
`GitHub- und Speicher-Kapazitätsfrühwarnung` task was updated, preserving
its existing monthly 10th/20th schedule: cheap read-only size and MINI-PC
heartbeat comparison, only if available, against the above dated baseline
and latest previously verified snapshot. Warning/review candidate when
database growth exceeds **50 MiB within 10 days** or **25% between comparable
snapshots**, or C: free space falls below **25 GB** or **15%**.
This is a review threshold, **not** permission to delete, alter retention,
execute VACUUM FULL or change physical task settings. Missing evidence is
`NOT_VERIFIED`, not a healthy status. The existing
`storage_and_cost` stream and `github_quota_and_cost` crosscut own
assessment and any actual cleanup/rights decision; only actionable new
problems are escalated to the existing 10:15 project owner/Backlog.

**Work-cost reduction already applied:** The same existing 2h market-regime/
source-steward Work task performs an inexpensive event/ACK delta check
first, and avoids broad repeated research or GitHub changes when the
material fingerprint is unchanged. It retains the 2h cadence and source
quality/market/strategy rules. The existing 10:15 project manager remains
the sole substantive cross-project followthrough. Work execution savings
must be measured later rather than claimed solely from prompt changes.

**GitHub CI de-duplication:** A same-PR superseded validation may be cancelled
by the existing `v2r4-pr-validation.yml` concurrency control (manual
dispatches stay independent), without removing the final/head safety tests
or reducing scanner/prod health monitoring. GitHub Actions run count alone
does not equal billable minutes; no cost-saving percentage is claimed.
