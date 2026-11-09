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
| `PaperActivate` | `V3_PAPER_ACTIVATE` | Signed Post-CAS Reader receipt and separately signed repeated operating lease | Verify both against the prepared disabled action, then start the existing task once and collect the host runtime readback |
| `PaperRuntimeBootstrap` | `V3_PAPER_RUNTIME_REPEATED` | Signed Post-CAS Reader receipt, operating lease and matching local activation attempt | Return the current lease to the SYSTEM launcher without requiring a running-task observation |
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
without the `p_` prefix. `runtime_bootstrap` binds local `approval_json`,
`approval_cms`, `admission_json`, `host_receipt`, `host_cms` paths. While the
task is disabled, Prepare can bind the destinations for the future operating
approval and Post-CAS witness under existing local directories. Activation
requires and verifies the original signed files at those exact paths. Task XML and
process data must be read from originals, not transcribed. A changed disabled
V3 action requires its resulting original XML to be bound in subsequent plans;
Prepare returns its exact XML digest. Original Candidates/WAIT XMLs permit only
the existing semantically validated Enabled change. Lifecycle and CloudSync
remain Running and unchanged.

For repeated Paper, the existing `host_receipt` and `host_cms` task arguments
refer to the original Notebook Post-CAS Reader pair. Use the same bytes for
activation. The independent operating lease pins that JSON as
`bindings.host_receipt_sha256` and signs the reviewed startup facts in
`bindings.start_authority`: `native_task_action_sha256`,
`native_task_launcher_file_sha256`, `runtime_release_packet_file_sha256`,
`approved_six_proof_release_packet_sha256` (the native canonical packet digest),
`six_external_original_e2e_proofs_approved`, `successor_series_assignment`,
the existing eight `maintenance_*` fields, `paper_only` and
`real_money_actions`. The task action hash is SHA-256 of its UTF-8 executable,
arguments and working directory separated by NUL bytes. The operating lease
does not attest any future Task state, PID, fence acknowledgement or heartbeat.
Activation checks the prepared Task XML and the complete bootstrap action, then
records the accepted operating lease and Cloud receipt digests before dispatch.
The lease cannot be swapped after that dispatch.

The SYSTEM launcher first verifies those original inputs and the committed
fence, then publishes a `STARTING` heartbeat under the existing lifetime
writer lock. This permits the host and supervisor to observe the process
independently. Actual Paper phases still require the live Task action, PID and
birth, no old intake workers, supervisor no-rearm acknowledgement and a fresh
locked Cloud read. The activation operator corroborates the later `HEALTHY`
heartbeat against the running Task, its CIM process and the existing supervisor.
Missing or mismatched readback is HOLD with the original activation attempt
preserved and no automatic second start. The local readback alone does not claim
the full operational cutover.

The native runtime spec has exactly these keys:
`kind` (`V3_NATIVE_RELEASE_RUNTIME_SPEC_V1`), `series_id`, `repo_sha`,
`bundle_sha256`, `strategy_sha256`, `phase`, `journal`, `capture_dir`,
`model_reservations`, `ack_file`, `release_root`, `release_packet`,
`candidate`, `preflight`, `paper_plan`. Candidate/preflight are existing JSON
paths or null as appropriate for the existing three phases. The signed
`V3_NATIVE_REPEATED_PAPER_RUNTIME_SPEC_V1` uses null for both fields. Its
existing V3 task reads original discovery events from the Mini-PC WS Shadow
directory, verifies a fresh Shadow heartbeat and builds the one-candidate
preflight with public Kraken data. Shadow's existing market-discovery triggers
define the input events. Its legacy liquidity class and recheck flag remain
source metadata and do not gate the V3 preflight. The V3 preflight and
Free-Rule P4 determine review eligibility and the Paper decision. It retains the admitted candidate in the
existing capture directory so follow-up can resume after a task restart.
No paid model key, model approval, callback, clock, alternative Cloud transport or arbitrary module
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

The existing six-proof packet explicitly selects `primary_decision_route:
FREE_RULE_P4` for that route. Its provider HTTP attempt limit is zero and the
packet grants no provider budget. The first proof retains its existing ID.
It must contain actual positive and negative Mini-PC rule/PIT/P4 journals,
including zero HTTP reservations and calls, and independent same-case
readbacks from the isolated Cloud evidence store. Production Cloud contributes
the separate read-only witness, with no fixture uploads or series changes.
Exact code and strategy pins, original receipt digests, owner lock, local
ledger and zero negative-case fills remain mandatory. The second proof checks
the route's fail-closed behavior, including rejecting provider inputs.
Legacy provider packets retain their original validation. Neither isolated
CI nor a locally generated packet is an independent release approval.

## Independent isolated aftercare cases in the sixth proof

For the first free-rule cutover, the existing
`V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN` envelope may declare
`cutover_witness_mode: V3_PRECAS_INDEPENDENT_ISOLATED_AFTERCARE_V1`. The
production `MINIPC_PHYSICAL` and `SUPABASE_CLOUD` originals still prove the
single active predecessor, exact successor fingerprints, disabled successor
writer, backup and original-host restore and no-rearm protections. The paired
production observations must be within 90 seconds of each other and inside
the existing ten-minute proposed-series window.

Complete and independently review the series-independent behavior first.
The real `MINIPC_ISOLATED` execution on the original Mini-PC supplies the
old owner and historical follow-up continuity cases. The real
`SUPABASE_SANDBOX` execution and independent readback supply stale CAS,
ambiguous outcome quarantine, postcommit no-restart, closed follow-up and
exit updates and rejection of new old-series intake. Both receipts share an
`ISOLATED-<32 lowercase hex>` run ID and the exact deployed relay, installed
CAS body and original Mini-PC sender digests. The `WORK` independent
readback pins both original receipt digests and must precede issuance of the
production series proposal. Keep the production and sandbox project identities
separate. A local fixture, CI result or mock remains supporting test evidence.
The external release owner still verifies provenance and signs the complete
packet. Existing STOP, CAS and activation approvals and the actual post-cutover
runtime readback remain separate.

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

### Pre-CAS free-rule originalhost receipts

Use the existing originalhost offline witness tool with `python -I -B`,
`--source`, `--stage`, `--expected-stage-sha`, `--free-rule-input` and
`--expected-input-sha256`. The source is the clean protected-commit checkout,
and the stage is its independently verified inactive copy on MINI-PC. A new
Research/V3Paper/PRECAS-FREE-RULE-<commit12> directory is created once.
Neither an active Cloud series nor a release approval is an input to this run.

The independently reviewed input is the original archived Scanner and PIT
bundle, kind `V3_PRECAS_PINNED_SCANNER_PIT_CASES_V1`, with the exact
`release_commit` and `cases` named `POSITIVE_BUY_SCOUT` and `NEGATIVE_REJECT`.
Each case contains `candidate`, its canonical one-candidate `preflight`,
the point-in-time `entry_evidence`, `ticker`, `pair_metadata` and the original
`decision_at_utc`. Retain the original source bytes and obtain the input
digest independently of the replay. Keep the actual historical clocks and
prices. Unit-test inputs do not qualify as original inputs. A different
observed outcome aborts the run and leaves its journal for inspection.

For the controlled technical BUY option, use input kind
`V3_PRECAS_CONTROLLED_BUY_REAL_REJECT_V1`. Supply only the previously captured
`NEGATIVE_REJECT` plus `negative_original` containing the original Scanner
handoff text, its SHA-256, and its capture commit. Bind the outer bundle to the
new release commit. The Mini-PC witness generates the pinned regression
scenario for the positive case under the reserved candidate ID
`V3-TECHNICAL-BUY-FIXTURE-V1`. The native worker only accepts that ID with the
isolated free-rule capability and an exact PRECAS-FREE CANARY series. No live
order or production-series journal may originate from this fixture.

Label the technical case `CONTROLLED_TECHNICAL_BUY_V1` and the real negative
case `ORIGINAL_SCANNER_PIT_V1` in both the host and independent sandbox case
records. The sandbox comparison first matches the original digest and exact
payload, including the reserved candidate ID. The release validator then
requires matching provenance across both independent sources. The fixture
only proves operation of the BUY path and its one virtual fill. Market-derived
BUY decisions, fills and economic outcomes are measured separately during
released Paper operation. The other evidence categories and release admission
remain mandatory.

The same free rule, P4 validation, native OS lock and append-only Paper
journal are used. This mode uses a commit-bound CANARY name, no network and
no provider authorization. It produces one virtual BUY fill and zero REJECT
fills only when the real rule arrives at those decisions. Its report records
the runtime fingerprints and claims zero release proofs.

Use the existing sandbox exporter from the clean source checkout with
`python -B -m tools.v3_paper_precas_synthetic_cloud_sandbox_v1 --witness-root ... --free-rule-commit ...`.
It exports only SOURCE_INPUT, MODEL_REQUEST/SKIP, P4 and the single BUY fill.
After independent host and input provenance checks, the same command with
`--prepare-sandbox-insert-sql` prepares one exact transaction. Execute it
only through the authenticated isolated Supabase project, during a valid
test window. It keeps the 16 old rows and their predicates, requires the
historical relay credential to stay disabled and permits exactly the seven
reviewed rows through an exception limited to their IDs and digests.

Independently query the entire exact CANARY series in a separate read-only
transaction for `series_id, event_id, content_sha256, payload`. Supply that
array using `--independent-sql-readback`. The checker compares every row and
rejects missing, extra, duplicate or altered rows. Keep the returned readback
and the original host witness for the existing technical gate and independent
owner. Neither the replay, export nor SQL comparison grants release authority.
