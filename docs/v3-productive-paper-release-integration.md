# V3 Paper release integration — #99

This is source integration, not a production activation receipt. Gate A/B and
PR677–679 Windows acceptance remain closed. The active V2R4 series must not be
changed merely because this source merges.

`tools/v3-one-time-release.ps1` now owns the productive modes below. Every
mode independently verifies the original #99 authority admission, exact release
commit, detached CMS, artifact inventory, signed plan hash and, except for the Stage4 epoch opening itself, a fresh independent
reader receipt. Existing authorization windows remain at most 15 minutes.
Expired authority holds; this is a bounded one-shot release, not an indefinite
unattended-operation authorization. No existing dormant SQL file is deployed
implicitly, no new credential is issued, and no paid model input is accepted
by the productive native bootstrap.

| Mode | Scope | Required independent state | Effect |
|---|---|---|---|
| `PaperOpenEpoch` | `CLOUD_STAGE4_EPOCH_OPEN` | Original old-only Cloud, one historical terminal abort, zero intents and attempts | Open one source-bound follow-up epoch and install its read-only Notebook query in one transaction |
| `InstallPaperCas` | `V3_PAPER_CAS_INSTALL` | `INSTALL_APPROVED_OLD_ONLY_NO_ATTEMPTS` | Install the existing atomic CAS body and bind only the existing restricted executor actor; separate approval from rotation |
| `PaperPrepare` | `V3_PAPER_PREPARE` | `PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS` | Update the existing disabled task action; create the protected ARMED fence |
| `PaperStop` | `V3_PAPER_STOP` | `PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS` | Disable/stop only Candidates and WAIT; require process absence before QUIESCED |
| `PaperSealEpoch` | `CLOUD_STAGE5_EPOCH_SEAL` | `STOP_CONFIRMED_INTENT_COMMITTED` | Seal only the new epoch, with exact original STOP receipt and independent Writer/Issuer commits |
| `PaperCas` | `V3_PAPER_CAS` | `SEALED_INTENT_INHIBIT_STOP_CONFIRMED` | Commit UNKNOWN through the existing executor, then call the existing 16-parameter rotation in a second transaction |
| `PaperActivate` | `V3_PAPER_ACTIVATE` | `CAS_COMMITTED_EXACT_SUCCESSOR_SINGLE_ACTIVE` | Hold both disabled intake definitions, set CLOUD_COMMITTED, enable/start the existing V3 task once |
| `PaperHostReadback` | `V3_PAPER_RUNTIME` | Signed original release evidence | Authenticate release evidence and independently observe actual Windows task/Python PID/birth, process absence, fence and supervisor before the locked native phase |
| `PaperResume` | `V3_PAPER_RESUME` | Fresh independent current result | Read-only resolution; never redispatch CAS or activation |
| `PaperRollback` | `V3_PAPER_ROLLBACK` | `PRECAS_ABORT_SEALED_OLD_ONLY_ZERO_ATTEMPTS` before CAS | Restore only original intake definitions after independent terminal abort. After possible CAS: request V3 safe HOLD, never rearm old intake |

The original CAS source retains its unconditional inactive exception. The
release builder in `Get-V3PaperCasInstallSql` replaces only that installation
seam after INSTALL admission, within one transaction. The atomic function body,
private audit relations, full PostgreSQL request digest, issuer inhibit,
old-series locks and single-active index remain unchanged. Existing roles must
already satisfy their restricted properties. The existing executor actor must be NOLOGIN, at connection limit zero, with no session or membership before installation. The installation binds only SET membership and keeps login disabled. An executable, separately authorized actor credential is needed at rotation. Installation and rotation use separate
SecureString credentials through the existing TLS-verifying stdin-only psql
transport. No raw caller SQL is executed.

### Follow-up after terminal Gate A

1. With the reviewed original Windows task definitions and signed plan, run
   `PaperOpenEpoch` under the existing Stage4 scope. The previous Stage4 and
   abort paths keep their historical semantics. The follow-up SQL preserves the
   historical rows and dispatch triggers, restores the existing role escrow,
   and refuses replay or any unexpected epoch, intent, attempt, or active series.
2. Before installing the RPC, the existing independent issuer calls
   `begin_executor_inhibit_v1` using the new epoch's four original bindings.
   The Notebook runs the existing Reader script with `-PaperReleaseSignedCurrent`,
   `-PaperPlanJson`, `-PaperReleaseId` and its existing reviewed certificate pin.
   It queries the exact new epoch over the authenticated read-only connection
   and signs the pre-install result with the plan digest.
3. Run `InstallPaperCas` with the corresponding scoped approval and Reader
   receipt. The SQL rechecks the new epoch and its genuine inhibit in the
   transaction. Re-run the Reader in the same mode for independent installation
   readback. It validates the exact installed RPC and limited executor membership,
   still requiring no executor login or sessions before STOP.
4. Use fresh signed Pre-STOP receipts for `PaperPrepare` and `PaperStop` under
   their own scopes. After preparation the plan must pin its returned exact
   disabled task XML. STOP checks the prepared fence bytes against the same
   Cloud epoch. After STOP, the existing Writer commits the exact request intent
   using `append_intent_v1`. The independent issuer confirms STOP with
   `confirm_executor_inhibit_v1` using the completion timestamp and SHA256 of
   the returned Originalhost STOP receipt. Obtain a fresh Reader result, then
   run `PaperSealEpoch` on the Originalhost under its separate scope. The Reader
   can attest the sealed epoch with the executor still inhibited. Enroll/enable
   the existing executor only for the separately authorized CAS window, then
   obtain the fresh pre-CAS Reader result.

If the release must stop before any CAS attempt, disable the executor actor and
verify zero sessions. Under the separate abort approval the existing issuer
calls `record_paper_release_abort_v1` for the exact release, epoch, source,
fence, ACL and independently reviewed receipt hash. The same Notebook Reader
can then attest the terminal state even with the guarded RPC installed. Only
a separately authorized Originalhost `PaperRollback` may rearm V2R4.

### Expired binding before STOP

Preserve the installed CAS and both previous epoch and receipt bytes. The existing
independent issuer records the terminal receipt for the unstarted binding. If
Prepare already armed the fence, a separately signed PaperRollback may archive
the exact marker with both original intakes still running and the V3 task
disabled. After a STOP attempt use the existing quiesced recovery contract.

Only in the coordinated execution window, issue a fresh UTC series ID and
corresponding fence. Under the existing Stage4 scope the new plan includes
`supersession` with `prior_epoch_id`, `prior_commit`, `prior_terminal_sha256`,
`installed_cas_sha256`, `installed_issuer_sha256`, and `installed_reader_sha256`.
The definition hashes are SHA-256 of the exact UTF-8 `pg_get_functiondef`
results observed before signing. The transaction preserves the installed CAS,
opens the successor only over terminal history, and updates the existing
restricted issuer and Reader in place. The Notebook then independently issues
the new inhibit. A fresh reader receipt permits Prepare without reinstalling CAS.

Stage code, admission, credentials and offline proofs before selecting the
timestamp. Start the independent approvals only inside the coordinated window.
An expired plan before dispatch leaves no latch. An ambiguous dispatch must be
resolved by independent readback before signing a new epoch. A committed but
unused epoch needs a fresh terminal receipt before another can open. Prepare and
STOP reject expired series before their first mutation. After STOP, preserve
QUIESCED and follow the existing recovery path if the window expires.

The signed plan includes `cas_epoch` with `epoch_id`, `source_sha256`,
`fence_sha256` and `caller_acl_sha256`. The source hash is the reviewed CAS
artifact hash. The fence hash is SHA256 of the UTF-8 no-BOM compact JSON bytes
that `Write-V3PaperReceipt` will write for the existing
`New-V3Pr515PreparedArmedMarker` (using the plan's exact release, series, bundle
and strategy). The ACL hash comes from the reviewed original ACL evidence.
These pins remain fixed across later plan revisions for the same epoch.

## Exact inputs

`-Mode PaperInventory` returns the complete fourteen-file artifact inventory
from original bytes, without Windows actions or Cloud contact. Use this
inventory for the new scopes; the historical default Inventory remains
unchanged for its older scopes.

Common operator inputs are `PackageRoot`, `ExpectedReleaseCommit`,
`AuthorityAdmissionJson`, `ExpectedAuthorityAdmissionSha256`, `ApprovalJson`,
`ApprovalCms`, `PaperPlanJson`, `HostReceiptJson` and `HostReceiptCms`.
`RuntimeSpecJson` is additionally used for preparation/activation/runtime.
The package root is the exact existing
`C:\Users\ADMIN\Trading\Staging\V3Paper-INACTIVE-<commit12>` directory.
The existing staging script now includes the productive operator, shared
CMS verifier, original native owner and original SQL in its byte manifest.

Approval `bindings` contain `plan_sha256`, `reader_certificate_sha256` and,
for runtime/preparation/activation, `runtime_spec_sha256`. Hash original bytes;
do not reserialize signed evidence. Reader receipts bind `release_id`,
`release_commit`, `plan_sha256`, `observed_at_utc` and the state above. CAS
receipts must also match all six original `preinvoke_*` epoch/intent/request/
source/fence/inhibit identifiers in the planned CAS request. Activation receipts
bind exact successor, repository, compiled bundle and strategy identities.
Six-proof, maintenance, issuance and independent Cloud-CAS assertions come from
the admitted original signer, never from locally invented success flags.

The plan has kind `V3_ONE_TIME_PAPER_RELEASE_PLAN_V1`, `repo_sha`, `series_id`,
`bundle_sha256`, `strategy_sha256`, five `tasks` (`name`, `xml_path`,
`xml_sha256`), and exact `intake_processes` (`pid`, `started_at_utc`,
`command_sha256`). `cas_request` uses the original sixteen `p_` argument names
without the `p_` prefix. `runtime_bootstrap` contains existing `approval_json`,
`approval_cms`, `admission_json`, `host_receipt`, `host_cms` paths. Task XML and
process data must be read from originals, not transcribed. A changed disabled
V3 action requires its resulting original XML to be bound in subsequent plans;
Prepare returns its exact XML digest. Original Candidates/WAIT XMLs permit only
the existing semantically validated Enabled change. Lifecycle and CloudSync
remain Running and unchanged.

The native runtime spec has exactly these keys:
`kind` (`V3_NATIVE_RELEASE_RUNTIME_SPEC_V1`), `series_id`, `repo_sha`,
`bundle_sha256`, `strategy_sha256`, `phase`, `journal`, `capture_dir`,
`model_reservations`, `ack_file`, `release_root`, `release_packet`,
`candidate`, `preflight`, `paper_plan`. Candidate/preflight are existing JSON
paths or null as appropriate for the existing three phases. No paid model key,
model approval, callback, clock, alternative Cloud transport or arbitrary module
is accepted. The existing dedicated relay credential stays at its fixed local
secret path and never enters task arguments or output.

`PaperPrepare` configures the original task to run the existing launcher with
`-I -B --released-one-shot`. Before any project imports the launcher verifies
and compiles its retained stage snapshot. The authenticated provider independently
observes the invoking Python process after startup, so an independent signer is
not asked to predict a future PID. Python correlates that separate observation
with its own OS PID/birth, exact task/source fingerprints, compiled identities,
original six-proof packet and a fresh authenticated Cloud read inside the
existing native single-writer lock. The first-scanner default remains the
free BUY_SCOUT/WAIT/REJECT rule route from PR677–679.

## Fault handling and evidence

Create-new, flushed attempt receipts precede every effectful dispatch. Timeouts,
partial STOP, lost CAS results and interrupted activation preserve their latches
and fences. Resume can inspect and select the next separately admitted phase;
it cannot remove a latch or replay an UNKNOWN rotation. A pre-CAS failure may
use the independently admitted terminal-abort restore. After a possible CAS,
reverse rotation and old-intake restart are forbidden. A requested safe HOLD
is not proof that all V3 workers have exited.

Offline verification covers real ephemeral CMS verification, wrong/stale/future/
tampered evidence, typed SQL escaping/nulls, original CAS-body parity, durable
latches, successful STOP/CAS/activation sequencing, duplicate dispatch, UNKNOWN
resume and post-CAS rollback. Existing CI also runs the disposable PG17 atomic
CAS fixture when this integration changes. These are not production host,
independent Cloud-commit, loaded-code, six-E2E or operational no-paid-HTTP
receipts. The latter remain part of the separately admitted physical release.
