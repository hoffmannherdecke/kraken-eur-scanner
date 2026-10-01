# Storage / Retention Policy

Status: **ACTIVE GOVERNANCE / NO STRATEGY EFFECT**  
Date: 2026-10-01

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

GitHub cleanup implementation evidence:
- paper-artifact cleanup check on commit `eefb490c5d82f850bf9171179eaed47d690c0f99`: **SUCCESS**;
- workflow retains a daily schedule and self-tests on workflow changes.

MINI-PC baseline:
- `CryptoMiniPC-LogCleanup` is part of the installed baseline task set;
- `CryptoMiniPC-Backup` is part of the installed baseline task set;
- restore smoke verifies backup readability without modifying live state.

## Deliberately not auto-deleted

The following are provenance/evidence, not disposable cache:

- frozen V2R3/V2R4 Paper decisions, revalidations and outcome evidence;
- immutable historical Trial Ledger entries;
- frozen strategy/release manifests and rollback snapshots;
- normalized historical datasets still referenced by an active/reproducible research trial;
- verified raw source archive when it is the only provenance root for derived historical data.

Historical archive parts may be deleted only through a dedicated checksum-gated
cleanup after the joined source archive has been independently verified.
`tools/cleanup-verified-kraken-ohlcvt-parts.ps1` is fail-closed and plan-only by
default for that purpose.

## Raw-data rule

Raw/high-frequency data is not kept merely because it exists.

- live Kraken runtime keeps compact latest snapshots/heartbeats;
- V2R4 stores selective event/outcome evidence rather than endless tick history;
- GitHub/Supabase must not become secondary full raw-market archives;
- new raw datasets require an explicit question, provenance plan, retention rule,
  and storage-benefit gate before collection/download.

## Review rule

A new log, cache, artifact, raw dataset, or local work directory is not considered
production-ready until one of these is true:

1. it has an explicit bounded retention/cleanup path; or
2. it is explicitly classified as immutable provenance/evidence and documented as
   such.

Retention changes are infrastructure/governance changes only and must not alter
strategy rules, Paper decisions, release gates, private exchange access, orders,
or real-money behavior.
