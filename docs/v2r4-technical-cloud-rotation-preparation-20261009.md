# V2R4 technical cloud rotation — draft boundary (09.10.2026)

Status: **PREPARED IN SEPARATE GITHUB BRANCH — NOT APPLIED. DO NOT INVOKE THE DRAFT RPC.**

## Physical evidence (operator screenshots)
- Read-only local preflight returned `PREFLIGHT_PASS_NO_MUTATION`; all enumerated checks passed, empty `failed_checks`.
- The separately confirmed staging returned `STAGED_INERT_NO_ACTIVATION`. Source `927e8c8d4455c28bb0cb230e86eb1d83bc09576f`; directory `Runtime/v2r4-paper-stage-927e8c8d4455`. Manifest `current_app_unchanged=true`, `no_runtime_control_in_prepared_app=true`, `cloud_activation_performed=false`, `h3_rebinding_performed=false`.
- Preflight screenshot showed 606 local old-series decision files, 0 position files. These are a point-in-time count, **not** a final sync reconciliation.

## Read-only Supabase inventory (2026-10-09 ~00:10 CEST)
- Exactly one active series: `PAPER-V2R4-20261007T184255Z`. Old release pinned `3c6729a6c548d169f56a97f07f75892f37211636`.
- 607 old-series candidate outcomes at one sampled read; zero V2R4 trades previously recorded. Cloud counts remain moving until quiesced, so 606-local vs 607-cloud must not be treated as automatically matching.
- Partial unique index `paper_series_single_active_idx` exists.
- `v3_h3_shadow_status` baseline remains old series. At query, `v3_h3_shadow_evidence` has zero rows. H3-001 is not transferable to any new series.
- Last read `minipc_status_current` reported `WARNING / DEGRADED`, not `HEALTHY / OK`, because old frozen Paper candidate runtime still has the known symbol-alias defect.
- Live `v2r4-paper-evidence-relay` is v6. Its `activate` action is hard-pinned to **first-series** V2R3→V2R4 approval and cannot be reused; `sync_h3_shadow` is pinned to H3-001 / original series. Existing `sync` checks active-series status but must not be used to bypass rotation authorization.

## Proposed inactive database artifact
- `supabase/v2r4-technical-paper-rotation-20261009.sql` adds a **transaction-only** procedure and a service-role-only immutable predecessor/successor rotation record.
- It checks explicit predecessor and release fingerprint, successor series/config/strategy/sizing/paper-only constraints, final cloud evidence counters and latest update clock, and unchanged H3-001 original baseline.
- A PostgreSQL transaction closes the old status as `technical_closed`, inserts the new active series, and records the rotation. Any failure rolls back the entire transaction. An existing partial unique index prevents two active series.
- Exact idempotent retry returns only the prior accepted result. A conflicting retry raises an error. The RPC has no `anon` or `authenticated` grants.
- This artifact **has not been dry-run, deployed or independently reviewed**. Even after validation, it requires an independently authenticated cutover endpoint with **both existing narrow relay tokens**, exact approved successor manifest, and a physical stop/last-ACK checkpoint. Do not send direct service-role calls from the Mini-PC/operator shell.

## Outstanding before any production modification
1. Peer-review the SQL syntax, privilege posture, transaction behavior, partial index and idempotent replay; test in disposable DB/transaction rollback only. Never execute a migration just as a test against live production.
2. Implement and review a **separate** one-shot dual-token Edge cutover path (reuse existing authorized tokens; no new secrets). Enforce an explicit expiry-bound operator release manifest, exact predecessor and staged SHA/fingerprint, and verify scanner/market-source health separately from the **known old Paper candidate** degraded status. Do not weaken general health semantics.
3. Implement and review the bounded physical MINI-PC switch script: quiesce old PAPER tasks + H3-001 at UTC boundary; wait for all old cloud sync ACKs; take a hash-verified snapshot incl. all local evidence/WAIT/decisions/positions/cursors; compare local/cloud identities and counts. If mismatch or pending in-flight sync: BLOCKED, old remains intact.
4. Run the migration as a separate reviewed release only after validated CI and operator approval; prepare successor independent runtime (new control, new series ID, pinned hash, no inherited cursors/decisions/WAIT), with no orders. Design recovery for ambiguous RPC network timeouts via **read-only lookup first**, never create a second series.
5. At the physical cutover perform exactly one atomic RPC, then start only successor Paper tasks, verify fresh/single active, PAPER-only, no stale buys/duplicates, lifecycle/sync ACK, source freshness and candidate feedback. If inconsistent: fail closed, preserve both snapshots; no unreviewed rollback of cloud series.
6. Freeze H3-001 without rebinding. H3-002 requires a separately reviewed frozen baseline/relay and preregistered unchanged H3 gates; if absent leave H3 inactive while H10 observational collection continues.
7. Update `project-current-state.json` and Issue #89 in the **same** verified release sequence, not in this preparation-only PR. No new Work runs, schedules, secrets, runner, real money or strategy changes.

## Additional identified gap
The current old-series sync rejects non-active series. For old 6h/24h evidence that matures after cutover, an independently permissioned, **archive-only** evidence path is required to preserve explicit pending/MISSING; it must never create retroactive BUY/REJECT or alter completed original decisions. A generic upsert into a closed series is not an acceptable substitute.

The draft is intentionally kept outside main to prevent accidental deployment; leave the current production Paper/H3 unaffected until a proper cohesive runtime+cloud release is ready.

## Progress in draft PR #94 (not deployed; 09.10.2026)

- Added dedicated dual-token `v2r4-technical-cutover` Edge source in a new separate function; its `checkpoint` action returns an authenticated **read-only cloud candidate-ID SHA-256 digest**, count, last update and trade count. Its `cutover` action checks those exact identities against the physical manifest before calling the atomic SQL transaction. This is not the first-series `activate` path.
- Added a read-only MINI-PC `tools/minipc-v2r4-technical-cutover-readiness.ps1` inventory. Its explicit `-SuccessorReleaseSha` must be the **final reviewed successor Git SHA**; the 08.10 stage SHA was only a successful historical inert preparation, not necessarily the final eligible successor.
- New candidate/sync code accepts optional `--paper-state-dir` so the successor can use a separate per-release *cursor* directory, while existing shared heartbeat paths can still feed watchdog/supervisor. Legacy startup arguments default to the original shared state path. WAIT receives its own versioned `--state`; no copied WAIT, alert, candidate or sync cursors.
- Added targeted local-state-isolation regression, existing Windows parser/read-only failure test, disposable SQL rollback/idempotent/cross-series evidence isolation fixture and new Edge typecheck to **existing validation paths**. CI evidence must be checked on the **latest** PR head before any merge or production use.
- Because the successor runtime code changed to support isolated state, **rebuild inert staging once from the final reviewed/merged SHA**. Never overwrite the old `Runtime/v2r4-paper-app` and never reuse the 08.10 stage path with a falsely claimed newer fingerprint.
- `V2R4_TECHNICAL_RELEASE_SHA` in the isolated Edge function is a **nonsecret release pin**, required at final deployment. Missing or malformed pin must block the endpoint. It must exactly match the local staged manifest and successor config; no new API token is needed.
- The endpoint deliberately tolerates only the known old Paper candidate failure and bounded WARNING-level supervisor state with **no active restarted task**. It still requires fresh Kraken canary, universe, WS source and Shadow cloud sync, rejects any unexpected component fault, and permits deliberate PAPER/H3 task-quiescence only in the explicitly authenticated cutover path.

### Remaining exact operational blocker

The present supervisor auto-restarts missing/unhealthy named Paper/H3 tasks. A physical cutover script cannot just stop those tasks and then call the cloud RPC: the supervisor may restart the frozen old series during snapshot or while the new one is starting. The physical operator release must include an **audited and expiration-bounded maintenance/quiescence mechanism** (or equivalent securely reversible supervisor stop with a cloud health lease), followed by final cloud ACK and hash-verified snapshot, unique new Paper app and state paths, atomic Cloud RPC, task action switch, supervisor restore and one fresh E2E. A failure before cloud commit must restore exactly the original scheduled task configuration; a failure after commit must fail closed and preserve both snapshots, not create another active series.

No switch command is approved or runnable from this draft. In particular, do not invoke the historical `install-minipc-v2r4-paper-runtime.ps1 -Execute` which copies into the **old** immutable app.

### Remaining historical evidence policy

The current first-release relay refuses sync for non-active Paper series. Post-cutover 6h/24h old followups therefore require a **separate append-only evidence-only archive contract**, not another call to the active-series sync API. Completed original BUY/WAIT/REJECT decisions, price clocks and unique candidate IDs remain immutable; explicit `MISSING` is preferred to retrospective reevaluation.
