# Gate A: existing one-time release integration

Owner: #99. Source change only. Stage4 and issuer-inhibit are DONE and must
never be repeated. No STOP, restore, CAS, V3 writer or Paper authority here.

## Contract

`tools/v3-one-time-release.ps1 -Mode GateAAbort` runs interactively on the
independent Notebook, using the existing CurrentUser DPAPI issuer credential
and the existing issuer login (never postgres, SET ROLE or an administrative
replacement). `CLOUD_PREPARED_FENCE_ABORT` is a separate scope of the existing
15-minute detached-CMS release authorization and original #99 admission.
`computer_name=MINI-PC` in that authorization still identifies the protected
release target; this issuer operation itself rejects MINI-PC execution.

Bindings are exactly `epoch_id`, `source_sha256`, `fence_sha256`,
`caller_acl_sha256`, `receipt_sha256`, `reader_certificate_sha256`.
The release authority independently approves all six and the actual artifact
inventory. Existing runtime, strategy and predecessor identities are retained.
A source change needs a new commit-specific admission using the existing
procedure; an older admission must not be silently rebound.

`IssuerReceiptJson` / `IssuerReceiptCms` must be the original saved signed
`V3_CAS_ISSUER_COMMITTED_PRESTOP_READER_V1` receipt from the completed issuer
operation. This is the existing independently authenticated issuer readback,
not console output or a reconstructed JSON. SHA256 covers its exact original
UTF-8 bytes; no normalization, newline rewrite or JSON serialization occurs.
Its signature, reader identity, issuer, INHIBITED state and four epoch pins
must match the independently authorized digest. The historical receipt does
not grant freshness: `IssuerPrestopJson` / `IssuerPrestopCms` separately pass
the unchanged native 30-second verifier immediately before dispatch. SQL
expires at the earlier of that observation plus 30 seconds and approval expiry.

One transaction calls the existing five-argument
`v3_cas_audit.record_prepared_fence_abort_v1`. No schema installation. A
create-new durable local attempt latch precedes network dispatch; the existing
database UNIQUE constraints remain the cross-session duplicate barrier. A
failed/timeout/lost COMMIT result never triggers a retry or latch removal.

## Independent completion

Even psql exit zero reports only `V3_GATE_A_COMMIT_RETURNED_READER_REQUIRED_V1`.
Use the unchanged Notebook reader `-PreparedAbortSignedCurrent` to read the
original database and produce signed terminal JSON/CMS. Then use
`-Mode GateAReadback` with the same approved receipt, identities and terminal
files. The existing `Test-V3Pr515SignedPreparedAbortReadback` verifies the
90-second current signed terminal state and Cloud boundary. This wrapper also
requires exact receipt-SHA equality. It never calls the issuer transaction.
Its output supplies the original terminal file paths and SHA for the later,
separate `ORIGINALHOST_ABORT_RESTORE` authorization. Refreshing a reader
observation never means repeating an issuer COMMIT.

## Deployment and remaining physical evidence

After merge, update only the changed launcher and authorization module in an
isolated inactive release package; preserve the unchanged originalhost module,
reader, issuer enrollment, Cloud schema and runtime. Bind the resulting package
hash inventory to the merged commit through the existing independent admission
and authorization procedure. Do not replace the active V2R4 release directory.
No productive command is authorized by this document.

The productive original receipt file and its SHA are NOT claimed available in
this source workspace. On the Notebook read the already saved original
reader.json / reader.cms from the completed issuer operation, confirm the
signed original, and compute its actual SHA before preparing the independent
Gate-A decision. If those original bytes cannot be recovered, HOLD; no replacement
receipt, invented digest, repeated Stage4 or repeated inhibit operation.

## Verification

The existing authorization test executes actual detached-CMS checks, byte/pin
negatives, the actual attempt-latch function with transport failure, and blocks
a second network dispatch. The existing isolated PG17 suite executes the
actual SQL builder through an authenticated issuer connection, rejects wrong
source pins and duplicate calls, discards transaction output to require
separate reader resolution, and uses the existing signed abort integration.
Existing Windows CI also runs the shared PowerShell tests. Local Linux checks
cannot substitute for Windows/PG17 CI or physical release evidence.
