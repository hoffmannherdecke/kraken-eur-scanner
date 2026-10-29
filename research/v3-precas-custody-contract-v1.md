# V3 PRE-CAS custody contract — research only

Status: **OFFLINE DESIGN / NOT AUTHORITY**. Fachowner: #99. No change to PR515 operator, originalhost tasks, CAS, database, runner or Notebook.

## Scope
This contract applies **only** to recovery of the existing V2R4 intake before any V3 CAS attempt. It does not authorize V3 release or recovery after CAS attempt, persisted intent, UNKNOWN or COMMIT. A historical assertion that CAS was *never* attempted is neither established nor implied by current empty tables.

## Necessary independent evidence (all mandatory)
1. An authenticated and independently pinned originalhost fence identity, scoped to the exact predecessor series, tasks, PR515 backup and original source hashes.
2. A continuously effective, independently attested **exclusive CAS-executor inhibit** covering the entire interval from before the first native STOP/ARMED transition until recovery has safely completed. Its issuer, start/end times, identity, fail-closed behavior and durability must be proven; a present-time missing RPC or NOLOGIN snapshot **alone** is not continuity.
3. Durable independent cloud readback of the single active predecessor, no new V3 series/rotation, and of **all relevant persisted CAS intents, attempts and UNKNOWNs**, with provenance, bounded freshness, and no visibility gaps. No untrusted caller booleans or log-tail counts can establish this.
4. Fresh native originalhost task XML/action/disabled state, independently checked process-family absence and supervisor no-rearm for both ARMED and QUIESCED, with validated PR515 recovery backup. Protected aftercare remains running.
5. One authoritative decision joining all evidence to the same fence/series/time interval, then a second freshness and no-new-intent check immediately before any native mutation. Any stale, missing, conflicting or unauthenticated evidence means HOLD.

## Negative test matrix (must all HOLD)
| Case | Expected |
| --- | --- |
| CAS dispatched between cloud snapshots | HOLD; no rearm |
| New persisted preinvoke intent after initial read | HOLD; no rearm |
| Local UNKNOWN latch or attempted/committed CAS | HOLD; no rearm |
| Missing, forged, mismatched or expired signed fence | HOLD |
| Executor NOLOGIN now but no proven continuous inhibit since STOP | HOLD |
| Executor identity or exclusive-call path changed | HOLD |
| Cloud snapshot not independently authenticated or not complete | HOLD |
| ARMED half-stopped / PID uncertainty / mixed native tasks | HOLD |
| QUIESCED XML drift, stale backup, or missing supervisor cycle | HOLD |
| No fresh second check before task mutation | HOLD |
| CURRENT epoch=0, intent=0, RPC=0 only | HOLD (not historical NEVER) |

## Review acceptance
This is a **candidate** for a narrower PRE-CAS recovery proof, not an approved change in release policy. Existing `V3_PR515_PRECOMMIT_RESTORE_SOURCE_UNCONDITIONALLY_LOCKED` and `V3_PRECOMMIT_INDEPENDENT_CLOUD_CAS_AUTHORITY_NOT_WIRED` remain in place. Before any implementation: identify an actually available independent continuous inhibit/custody issuer and authenticated history readback, review against #99, then add executable offline negative tests to existing test harness. If these cannot be proven, maintain HOLD and do not create an alternative CAS executor or widen privileges.
