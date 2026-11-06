# V3 #99 one-time release integration

This is an **unapproved release candidate**, not a production authorization.
The two original SOURCE-ONLY files remain unchanged. The only public release
entry is `tools/v3-one-time-release.ps1`. Default mode only lists local hashes.

The generated originalhost module is the reviewed release derivative of the
same PR661 owner, not another scheduler, writer, CAS executor or recovery
implementation. `python tools/build_v3_one_time_release.py --check` reproduces
it from the exact original operator SHA and the explicit boundary fragment.
The generator fails on any unexpected seam or source change. CI reviews and
executes the committed result, not an unreviewed runtime text patch.

## Separate scopes

`CLOUD_ABORT_INSTALL` installs only the existing prepared-fence abort objects
and original owner policies, with temporary owner escrow restored in the same
transaction. It never opens an epoch, invokes CAS, starts a writer or changes
executor credentials. The existing table-absence condition plus transaction
advisory lock is the durable one-time latch. Any SQL failure rolls back DDL,
policies and escrow. Connection loss around COMMIT is UNKNOWN: use the separate
read-only readback, never replay the installer automatically. A successful
installation is retained; there is no destructive automatic uninstall.

`ORIGINALHOST_ABORT_RESTORE` is restricted to a **terminal pre-CAS abort
rehearsal**. The original epoch must already have a real committed inhibit,
then a real committed terminal abort *before the first native STOP*. The
existing terminal barrier rejects future intent and UNKNOWN appends. This is
not a claim of historical CAS NEVER and cannot authorize a later CAS attempt
on that aborted epoch. No V3 writer is enabled. A future Paper cutover retains
its separate existing Stage4/Stage5/CAS/Single-Writer gates.

The release consumes the existing separately authenticated and CMS-signed
Notebook terminal Reader output. It does not sign third-party
JSON, invent continuity assertions, grant Notebook paper-series privileges,
or create a replacement issuer. An absent, mismatched, expired or unadmitted
signer cannot enter production. The authority's scope covers the controlled
privileged operator window; as in PR661, kernel handles do not claim immunity
to forced handle closure or arbitrary administrator actions outside that
window. Such interference requires HOLD and independent reconciliation.

Gate B obtains fresh `PreparedAbortSignedCurrent` output from the unchanged
Notebook Reader. Pass those exact signed terminal bytes as `IssuerPrestopJson`
and `IssuerPrestopCms`, as well as the current local `TerminalAbortJson` and
`TerminalAbortCms`. The dedicated generated Gate-B adapter verifies the terminal
CMS and all existing epoch/source/fence/ACL and Cloud-boundary fields, then
enforces the existing maximum 30-second prestop age, rechecked after leases.
It does not serialize a replacement issuer receipt. The pre-abort issuer RPC
and its zero-abort guard remain unchanged for Gate A; that RPC cannot provide
a post-abort Gate-B observation. Preserve Gate A's archived original files;
refresh observations into separate Gate-B files immediately before use.

Read-only package file leases prevent replacement of verified runtime bytes during execution. STOP, restore and atomic archive recheck scoped authorization, package bytes,
fresh signed terminal proof, exact ARMED fence, protected task XML and V3
Disabled state. Both disabled task-definition handles are retained by the
same original PR661 session. A post-lease expired prestop signature now fails
before STOP. Partial failures retain Disabled tasks/ARMED fence where present;
there is no automatic rearm. In-process retry reuses the same real handles and
mutex. A process interruption cannot reconstruct handles from JSON. The
CreateNew durable attempt journal forbids an automatic new-process replay;
independent reconciliation under #99 is required. No cleanup deletes it.

## Independent authority admission and exact approval

The existing #99 authority must independently admit the public certificate,
its key custody and the exact release commit. This development does **not**
admit the existing candidate certificate or generate a production signature.
The operator re-reads the referenced original #99 comment over fixed GitHub HTTPS on admission and again before each native mutation. It checks the actual repository owner identity and exact commit/certificate/custody decision; a local file, digest or accepted flag alone cannot admit a key. The reviewer posts a plain JSON original decision with `kind`, `release_commit`, `certificate_sha256`, and `independent_key_custody_accepted` only. This implementation never posts that decision. Revocation, deletion or an unavailable original means HOLD.

The reviewed execution instruction must independently supply the SHA256 of
this exact external admission record (never calculate that trust input from
an untrusted downloaded admission file):

```json
{
  "kind": "V3_INDEPENDENT_RELEASE_AUTHORITY_ADMISSION_V1",
  "certificate_sha256": "<independently admitted DER SHA256>",
  "release_commit": "<reviewed release commit>",
  "independent_key_custody_accepted": true,
  "original_approval_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-<actual independent decision>"
}
```

That admitted authority signs the original UTF-8 approval bytes using one
SHA256 detached CMS signer. Mathematical signature validity alone is not
admission. Separate scopes require separate approval signatures. Required
approval fields:

| Field | Required binding |
|---|---|
| `kind` | `V3_ONE_TIME_RELEASE_AUTHORIZATION_V1` |
| `release_id` | `V3-ONETIME-` plus 32 lowercase hexadecimal characters |
| `scope` | Exactly one of the two scopes above |
| `base_commit` | `5b1789e349b157d06d3109c5f0ff10d95154bf81` |
| `release_commit` | Exact reviewed implementation commit, supplied independently |
| `not_before_utc`, `expires_at_utc` | `yyyy-MM-ddTHH:mm:ssZ`, at most 15 minutes |
| `project_ref` | `nlgzjmqgwueojlyqmoru` |
| `computer_name`, `trading_root` | `MINI-PC`, `C:\Users\ADMIN\Trading` |
| `artifacts` | Exact eight-path SHA256 inventory from the reviewed package |
| `bindings` | Scope-specific exact fields below |

Cloud bindings contain only `source_sha256`, equal to
`86dfebe688eda78ba14000a63f534e3295af63dcf19c48e07aab26d75e76fbd6`.
Host bindings are exactly `epoch_id`, `source_sha256`, `fence_sha256`,
`caller_acl_sha256`, `reader_certificate_sha256`, `reader_source_sha256`, `pr515_sha256`,
`backup_manifest_sha256`, `successor_series_id`, `bundle_sha256`,
`strategy_sha256`, `candidate_repo_sha`, `lifecycle_xml_sha256`,
`cloudsync_xml_sha256`, `v3_writer_xml_sha256`, `install_readback_sha256`,
`install_release_commit`, and `policy=TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1`.
These are exactly eighteen bindings. The Reader source pin is the already
staged original Reader SHA256 `c81dbdca986da4fb5143bc1a315cb3b7dd548e0b6f338a02f0992767b6af2ba5`.
The independent authority must accept the genuine Reader provenance and its
separate key custody before signing these bindings; signing supplied third-party
JSON is not such evidence. These are original observed bindings, not synthetic
development values.

The installation commit is the immutable commit recorded by the completed
Cloud installation, independently accepted in `install_release_commit`.
It is separate from the current host execution `release_commit`. For the
completed installation in #6627552137 it is
`b019448331dfeb1052d543486a077ac2404651e4`; do not repeat installation or edit
its record to make it match a later CLI. The exact original readback bytes are
independently pinned by `install_readback_sha256`. Before the attempt journal
and again at every STOP/restore/archive boundary the operator checks that digest,
the original installation kind, commit, release/approval identities and the
installed abort source hash against the reviewed package. A new host approval
must explicitly accept both identities; an earlier seventeen-binding approval
is rejected. Cloud DDL and its original catalog record remain unchanged.

## Authorized execution interface

No production command below is pre-authorized by this document. After review,
the actual #99 approval and all real hashes/paths must be inserted in a single
bounded block per necessary device window. Do not run placeholder commands.

- `-Mode Inventory`: local eight-file inventory, no credential or network use.
- `-Mode InstallCloud`: admitted authority record plus exact independently
  reviewed admission digest; exact release commit; original approval JSON and
  detached CMS. It prompts for the existing postgres password without saving
  it. Fixed PG17 client and original Session Pooler use TLS `verify-full`.
  No credentials are copied through Mistral_450. Output is the separate
  original-catalog readback, including exact function bodies, policies, ACLs
  and recorded approval/commit. Preserve the original output for independent
  checking and signing of the later scope.
- `-Mode ReadbackCloud`: bounded read-only reconciliation after UNKNOWN or
  failed output transfer. It cannot retry or install DDL, and needs no expired
  installation approval to read the original catalog.
- `-Mode OriginalhostAbortRestore`: separate live host approval and admission,
  existing backup directory, locally transferred prestop/terminal JSON+CMS,
  and independently accepted install readback. Transfer through Mistral_450;
  the terminal pair must be local direct children of the Trading root, as
  required by the original PR661 session. A stale proof fails closed; never
  reuse an old CMS to satisfy freshness. Refresh within the same held session.

Only files with changed bytes need staging. Existing original operator, source
SQL, readiness script, Reader, PG17, CA, DPAPI, native backups and accepted
infrastructure are reused. The new runtime package paths are the CLI, shared
authorization module, generated release module, installer SQL and readback
SQL; generator/boundary/test files are development inputs, not extra device
services. Versioned staging preserves original files. Actual rollout blocks
must be pinned to the final reviewed commit and admitted independent record;
this candidate intentionally contains no fabricated runnable production block.

## Interrupted Gate B: enabled-only reconciliation of the same attempt

`-Mode OriginalhostReconcile` extends this operator for the observed partial
state: both original intake definitions are disabled, each original instance
and its pre-window Python process family still runs, and the exact ARMED fence
and original attempt journal remain. It never calls STOP, Start, process kill,
SQL, Gate A, CAS or the V3 writer. This is cancellation/reconciliation of a
partial attempt, **not** proof that the intended STOP rehearsal succeeded.

The original `ORIGINALHOST_ABORT_RESTORE` authorization cannot admit this mode.
The existing independent #99 authority must admit the repaired release and sign
`ORIGINALHOST_ABORT_RECONCILE`, with the **same** `release_id`. Keep all 18
original bindings exactly; add only:

- `journal_sha256`: exact unchanged existing attempt journal;
- `original_approval_sha256`: original expired approval bytes;
- `evidence_sha256`: independently reviewed, unmodified originalhost JSON;
- `reconciliation_policy`: `ENABLED_ONLY_CONTINUING_ORIGINALS_NO_STOP_V1`.

The new approval pins the repaired eight-artifact inventory. The historical
approval/CMS is verified mathematically as original evidence, not renewed or
used as live execution authority. Its old release commit remains separate from
the repair release. `-ExistingApprovalJson`, `-ExistingApprovalCms` and
`-ReconciliationEvidenceJson` must be local original files. Admission still
requires the real independent GitHub decision for the exact repair commit.
No execution approval is granted by this document or a source merge.

Under the existing operator mutex, verify the journal, historical CMS, approved
state evidence, exact original backup, protected task hashes and signed fresh
terminal abort. Obtain real handles on the already disabled task definitions;
these are newly authorized reconciliation handles, **not** reconstructed old
STOP handles. Reread effective XML with the original disabled-only comparator,
Enabled and Running separately, one actual Scheduler instance per task, and
all matching Python PIDs/creation times/parents. Require IgnoreNew instance
policy (including its Scheduler default); reject Parallel/Queue/StopExisting.
Reject changed actions,
principals, triggers, other settings, process identities, or duplicate PIDs.
No XML is imported or overwritten. Before enabling either definition, persist
`<original-journal>.reconciliation-attempt.json` with CreateNew and Flush(true).
This is a durable extension of the same attempt, not another transaction ID.
No code deletes either latch. Release handles only at the authorized enable
boundary; use the same native Enable API owner as normal restore, without
starting another process. Check both definitions and original instances after
each enable. Any partial error is UNKNOWN, preserving the journal/latch and
ARMED fence; no automatic re-disable, rearm, STOP or retry is performed.

After both fresh HEALTHY intake heartbeats, recheck live authority, original
bytes, process identities, protected tasks and a fresh signed terminal abort
(maximum 90 seconds). Archive the exact fence using the existing exclusive
same-handle, non-overwriting NTFS rename primitive. The generic marker-only
hardlocks remain unchanged. Parent-directory/privileged-operator custody and
independent Reader provenance remain conditions of the supervised window;
these handles do not defeat an arbitrary malicious administrator.

Require fresh post-archive Supervisor HEALTHY/NONE, CloudSync HEALTHY/
ACTIVE_ORIGINAL for only the original series, continuing original processes,
and another independently signed Cloud Reader observation made **after** the
archive. Revalidate live authority and original bytes after waiting. Only then
CreateNew the original journal's `.completed.json`, with the distinct status
`TERMINAL_ABORT_PARTIAL_ATTEMPT_RECONCILED_AFTERCARE_CONFIRMED`, explicit
`successful_stop_claimed=false`, and no CAS/Paper permission. Do not translate
this receipt into `TERMINAL_ABORT_STOP_RESTORE_AFTERCARE_CONFIRMED`. A lost or
partial completion or expired authority never authorizes replay. The following
post-archive continuation is the only permitted restarted completion path.
Before archive, any interrupted Enable, heartbeat or rename without a proven
archive remains HOLD; no re-enable or recreated fence is permitted.

Minimal deployment: retain the original source stage and original evidence.
Create a separate inactive repaired stage; copy the five unchanged pinned
artifacts and download only the three changed runtime artifacts (launcher,
authorization module, generated native module) at the reviewed merge commit.
Validate all eight SHA256 values, then run Inventory only. Never overwrite an
active V2R4 release or the historical Gate-B source stage. Notebook needs only
the specific independent release admission/signature and its existing required
read-only Cloud Reader; no additional operational Notebook responsibilities.
Physical staging and reconciliation remain separate specifically authorized
steps after SOURCE/CI/MERGE_DONE.

Validation reuses existing CI: the release authorization suite includes the
reconciliation regressions (real historical/new CMS, changed originals,
Enabled=false/Running=true, semantic XML/action and PID drift, expiry,
partial Enable, repeated reconciliation, unknown health/rename/aftercare and
preserved latches). The existing disposable Windows native test checks the
shared Enable owner preserves a running instance. No production host action
occurs in either test.

### Post-archive continuation of the original transaction

After both definitions are enabled and the exact original processes and native
instances are confirmed, persist `.pre-archive.json` atomically before rename.
It retains the attempt-latch digest, original reconciliation approval/CMS and
instance identities. The journal, historical evidence and attempt marker are
never changed. After exact archive readback (source absent, archive hash exact)
create `.awaiting-post-archive-reader.json` in state
`AWAITING_POST_ARCHIVE_READER`. Failed/absent/stale CMS or expired authority
leaves this state intact. No Reader trigger, notebook service or scheduler is
introduced. Notebook use stays an occasional independent read/sign action.

If the process died after rename but before that receipt was persisted, the
same operator reconstructs it only from the unchanged pre-archive checkpoint,
signed original authorization, attempt latch, original task/process identities,
protected tasks, installed catalog evidence and exact archive. It records the
current verified archive-observation time as a conservative **upper bound** on
the rename time. NTFS modification/creation times are not proof of rename time.
The independently signed Reader observation must be later than that bound.
An interrupted operation still holding ARMED cannot use this reconstruction.

A later `OriginalhostReconcile` invocation takes the existing mutex, package
and original-evidence leases and goes directly to finalization. It never
acquires disabled-task mutation handles, enables a task, archives again, STOPs,
restores, or resets a latch. All original 22 reconciliation bindings remain
unchanged. The existing independent authority signs the same scope, release ID,
repair commit and artifacts, adding `post_archive_receipt_sha256`: exact SHA256
of `.awaiting-post-archive-reader.json`. This binds the stored time and its
checkpoint chain across process restarts. An old unpinned authorization cannot
finalize a restarted process, even if its clock window is still open. Expired
CMS needs a new valid specific window. A receipt reconstructed after a crash
must be independently reviewed and pinned before completion; a HOLD reports its
digest without performing a second reconciliation attempt.

Finalization revalidates admission, live authorization, package, original
journal/evidence, historical CMS, checkpoint chain, installed catalog,
protected tasks, exact archive, original intake definitions/processes/instances,
fresh Supervisor and CloudSync aftercare and fresh independent Reader CMS with
all unchanged Epoch/Source/Fence/ACL and Cloud/CAS guards. Persistent proof files
and the archive are held read-only during finalization. Completion is atomically
published without overwrite; a second call after completion is HOLD.

Physical sequence after a separately approved merge:

1. Preserve the historical Gate-B stage, journal, evidence, backup and all latches.
   Reuse the PR672 inactive stage as the verified source of the six unchanged
   inventory files; create one adjacent inactive repair stage and replace only
   authorization and generated-originalhost modules with exact merge bytes.
   Verify all eight inventory hashes and use the existing Inventory mode only.
2. Admit the new commit through the existing independent #99 decision. Prepare
   the existing `OriginalhostReconcile` argument set with unchanged original
   paths/bindings; issue a short-lived execution CMS only at its point of use.
   Production execution remains a separate specific gate.
3. Once the operator has durably reached AWAITING (or reconstructed it under a
   valid authority and returned HOLD), read its exact receipt SHA256. Use the
   existing Notebook Reader to produce fresh original JSON/CMS after the bound;
   sign the same transaction with the additional receipt digest and a live
   window. Transfer through the existing path. Invoke the same operator with
   the unchanged journal/evidence/backup and new exact Reader/CMS files.
   This invocation performs only finalization. Gate B remains PENDING until
   its original physical completion receipt and independent readback are proven.

Regression coverage runs through the existing authorization test entry on Linux
and disposable Windows: real timely/stale/pre-archive/wrong-Epoch/invalid/missing
Reader CMS, expired/new authority, interrupted Enable, unknown rename before or
after mutation, interruption before awaiting persistence, restarted process
context, exact receipt pin, release/Epoch/journal/task/process drift, duplicate
completion, unchanged original journal/checkpoint/latch and zero native mutation
on continuation. No production reconciliation is performed by CI.

## Gate-B process-filter correction (06 November 2026)

The PR673 `Read-V3ReleaseContinuingIntakes` filter assigned task arguments to
PowerShell's automatic `$args` variable. Inside the `Where-Object` scriptblock,
that variable is an empty argument array: `IndexOf` receives an empty string
and matches every Python command line. A shared CIM snapshot containing the
four original processes can therefore produce a per-task count drift even
when an independent check using the actual task arguments finds both original
launcher/worker pairs. This is a source defect, not a release parameter error
or evidence that CIM lost processes. The previous one-process/same-arguments
fixture concealed it.

The boundary fragment now captures `$taskArguments`; the generator reproduces
the release module. Query, snapshot timing, exact count, PID, parent PID,
creation time, task instance, XML, journal, fence, epoch and authorization
checks are unchanged. There is no second CIM query or automatic retry. A
transient incomplete snapshot remains HOLD; a later independent observation
cannot retroactively authorize the failed call. Any real additional matching
process or changed identity still fails closed.

Regression uses distinct Candidates/WAIT arguments, two original PIDs per task
and an unrelated Python process. It covers incomplete/transient snapshots,
extra processes, PID replacement/reuse, parent changes, absent command lines,
the real reader before Enable/archive, durable attempt preservation and replay
denial. The enhanced fixture fails with the original PR673 module.

Source/CI/merge and physical deployment remain separate. After merge, stage a
new pinned **inactive** package at the existing Mini-PC Staging location; do
not overwrite PR673, the frozen V2R4 runtime, original approvals/evidence,
journal, attempt sidecars or fence. Verify the new eight-file inventory against
the merged source. A source-stage PASS is not a reconciliation or completion
ACK. Existing PR673 admission and execution decisions are commit/artifact-bound
and cannot silently authorize changed release bytes. The existing #99 release
procedure must bind the repaired release before a future execution. No Notebook
CMS or reconciliation is part of this source repair. Since the latest failed
attempt's aftermath is not yet independently confirmed, preserve UNKNOWN for
that live state until the existing targeted originalhost readback establishes
which continuation branch, if any, is permitted. Never clear a latch or replay
because a source repair merged.
