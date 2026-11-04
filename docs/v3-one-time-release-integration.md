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
Notebook prestop and terminal Reader outputs. It does not sign third-party
JSON, invent continuity assertions, grant Notebook paper-series privileges,
or create a replacement issuer. An absent, mismatched, expired or unadmitted
signer cannot enter production. The authority's scope covers the controlled
privileged operator window; as in PR661, kernel handles do not claim immunity
to forced handle closure or arbitrary administrator actions outside that
window. Such interference requires HOLD and independent reconciliation.

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
`caller_acl_sha256`, `reader_certificate_sha256`, `pr515_sha256`,
`backup_manifest_sha256`, `successor_series_id`, `bundle_sha256`,
`strategy_sha256`, `candidate_repo_sha`, `lifecycle_xml_sha256`,
`cloudsync_xml_sha256`, `v3_writer_xml_sha256`, `install_readback_sha256`,
and `policy=TERMINAL_ABORT_BEFORE_STOP_NO_CAS_V1`. These are original observed
bindings, not synthetic development values. The host also requires the
installation readback's recorded release commit to match this exact release.

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
