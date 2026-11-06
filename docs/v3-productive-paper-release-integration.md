# V3 Paper release integration — #99

This is source integration, not a production activation receipt. Gate A/B and
PR677–679 Windows acceptance remain closed. The active V2R4 series must not be
changed merely because this source merges.

`tools/v3-one-time-release.ps1` now owns the productive modes below. Every
mode independently verifies the original #99 authority admission, exact release
commit, detached CMS, artifact inventory, signed plan hash and fresh independent
reader receipt. Existing authorization windows remain at most 15 minutes.
Expired authority holds; this is a bounded one-shot release, not an indefinite
unattended-operation authorization. No existing dormant SQL file is deployed
implicitly, no new credential is issued, and no paid model input is accepted
by the productive native bootstrap.

| Mode | Scope | Required independent state | Effect |
|---|---|---|---|
| `InstallPaperCas` | `V3_PAPER_CAS_INSTALL` | `INSTALL_APPROVED_OLD_ONLY_NO_ATTEMPTS` | Install the existing atomic CAS body and bind only the existing restricted executor actor; separate approval from rotation |
| `PaperPrepare` | `V3_PAPER_PREPARE` | `PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS` | Update the existing disabled task action; create the protected ARMED fence |
| `PaperStop` | `V3_PAPER_STOP` | `PRESTOP_INHIBITED_OLD_ONLY_NO_ATTEMPTS` | Disable/stop only Candidates and WAIT; require process absence before QUIESCED |
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
already satisfy their restricted properties. A missing/disabled actor or missing
original audit function is a concrete deployment prerequisite, not a reason to
use postgres/service_role for rotation. Installation and rotation use separate
SecureString credentials through the existing TLS-verifying stdin-only psql
transport. No raw caller SQL is executed.

## Exact inputs

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
