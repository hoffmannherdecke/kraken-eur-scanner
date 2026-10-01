# Historical Data Storage Lifecycle

Status: **ACTIVE POLICY / PLAN-ONLY CLEANUP**  
Date: 2026-10-01

Root on the MINI-PC remains:

`C:\Users\ADMIN\Trading\Historical\`

This policy is stricter than general log retention because historical market
data also carries reproducibility/provenance obligations.

## Storage classes

| Path class | Classification | Default action |
|---|---|---|
| `raw/**/archives/*.zip` | provenance root | KEEP |
| verified multipart pieces after joined archive exists | redundant transport parts | dedicated checksum-gated cleanup only |
| `staging/**` | temporary extraction/join workspace | delete candidate after age gate |
| `tmp/**` | disposable scratch | delete candidate after age gate |
| `normalized/**` | reproducible research derivative | KEEP while referenced / active |
| `derived/**` | reproducible features/labels | KEEP while referenced / active |
| `catalog/**` | source checksums/provenance/lifecycle metadata | KEEP |
| `trials/**` | immutable trial/search-accounting evidence | KEEP |
| `reports/**` | compact research evidence | KEEP |
| unknown path | unclassified | HOLD, never auto-delete |

## Hard deletion rules

1. A source archive is not deleted merely because normalized files exist.
2. Multipart download pieces may be deleted only after the joined archive checksum is independently verified; use the dedicated fail-closed cleanup tool for the known Kraken OHLCVT archive.
3. `staging/` and `tmp/` may be proposed for deletion only after an age gate.
4. Normalized/derived data is never age-deleted while referenced by an immutable Trial Ledger record or an active research branch.
5. Catalogs, trial ledgers, frozen specs/locks and compact reports are evidence, not cache.
6. Unknown files are never classified as disposable automatically.
7. Drive D remains excluded until its separate backup/FAT32 repair gate closes.
8. No historical cleanup may mutate V2R3/V2R4 runtime, Paper state, Supabase evidence, strategy files or exchange state.

## Plan-before-delete rule

`tools/plan-historical-storage-cleanup.py` is intentionally **read-only**.
It inventories the Historical tree and labels files as KEEP, DELETE_CANDIDATE,
REVIEW_REDUNDANT_PART or HOLD_UNKNOWN. It never deletes anything.

A later destructive cleanup must be a separate explicit action whose scope is limited to files already classified and whose prerequisites are revalidated at execution time.

## Initial age gates

- `staging/`: 24 hours;
- `tmp/`: 48 hours.

These are operational cleanup thresholds, not data-validity thresholds.

## Current Kraken OHLCVT state

The official joined OHLCVT archive remains the provenance root for the 648 normalized EUR/15m partitions. Redundant multipart download pieces may be removed only through `tools/cleanup-verified-kraken-ohlcvt-parts.ps1`, which verifies the joined archive SHA-256 and is plan-only unless explicitly confirmed.

## Future Kraken Time & Sales / Binance data

- Kraken Time & Sales remains not bulk-authorized.
- If later authorized, raw archive provenance receives the same KEEP semantics; extracted targeted windows may be compacted once the immutable trial records reference a reproducible source checksum.
- Binance public derivatives context should prefer compact point-in-time state records, not a second uncontrolled raw-history mirror.
