"""Narrow source guard for the existing private V3 CAS prepared-fence abort.
Not a replacement for disposable PostgreSQL 17 tests or physical issuer ACK.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "supabase" / "v3-cas-prepared-fence-abort-INACTIVE.sql"

class V3PreparedAbortSourcePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SOURCE.read_text(encoding="utf-8")
        cls.code = re.sub(r"(?m)^--[^\n]*", "", cls.sql)

    def test_first_effectful_statement_hardlocked(self):
        self.assertRegex(self.code, r"(?s)^\s*BEGIN;\s*DO \$locked\$\s*BEGIN\s*RAISE EXCEPTION")
        self.assertIn("V3_PREPARED_ABORT_SOURCE_INACTIVE_NO_PRODUCTION_INSTALL", self.sql)
        self.assertLess(self.code.index("RAISE EXCEPTION"), self.code.index("CREATE TABLE"))

    def test_no_parallel_cas_executor_or_public_permissions(self):
        self.assertEqual(len(re.findall(r"(?i)\bCREATE TABLE\b", self.code)), 1)
        self.assertEqual(len(re.findall(r"(?i)\bCREATE FUNCTION\b", self.code)), 2)
        self.assertNotRegex(self.code, r"(?i)\bCREATE (?:ROLE|SCHEMA|EXTENSION)\b")
        self.assertIn("FORCE ROW LEVEL SECURITY", self.code)
        self.assertIn("REVOKE ALL ON FUNCTION", self.code)
        self.assertIn("FROM PUBLIC,anon,authenticated,service_role", self.code)
        self.assertNotRegex(self.code, r"(?im)^\s*(?:UPDATE|DELETE|TRUNCATE)\s+v3_cas_audit\.prepared_fence_abort_v1")

    def test_independent_reader_only_receipt_access(self):
        self.assertIn("CREATE POLICY v3_prepared_abort_reader_select_v1", self.code)
        self.assertIn("FOR SELECT TO v3_cas_audit_reader USING (true)", self.code)
        self.assertIn("GRANT SELECT ON v3_cas_audit.prepared_fence_abort_v1 TO v3_cas_audit_reader", self.code)
        self.assertIn("'INSERT,UPDATE,DELETE'", self.code)
        self.assertIn("'v3_cas_audit_reader'", self.code)
        self.assertNotRegex(
            self.code,
            r"(?i)GRANT (?:ALL|INSERT|UPDATE|DELETE) ON v3_cas_audit\.prepared_fence_abort_v1 TO v3_cas_audit_reader",
        )

    def test_aborted_epoch_blocks_future_intent_and_unknown(self):
        for v in (
            "reject_aborted_epoch_dispatch_v1",
            "v3_reject_aborted_intent_insert_v1",
            "v3_reject_aborted_attempt_insert_v1",
            "BEFORE INSERT ON v3_cas_audit.intent_v1",
            "BEFORE INSERT ON v3_cas_audit.attempt_v1",
            "FOR SHARE",
            "V3_ABORTED_EPOCH_CANNOT_APPEND_INTENT_OR_ATTEMPT",
        ):
            self.assertIn(v, self.code)
        self.assertEqual(len(re.findall(r"(?i)\bCREATE TRIGGER\b", self.code)), 2)

    def test_existing_force_rls_owner_read_is_exact_and_nologin(self):
        for value in (
            "v3_cas_epoch_owner_abort_read_v1",
            "v3_cas_epoch_owner_abort_update_v1",
            "v3_cas_intent_owner_abort_read_v1",
            "FOR SELECT TO v3_cas_audit_table_owner USING(true)",
            "FOR UPDATE TO v3_cas_audit_table_owner USING(true)",
        ):
            self.assertIn(value, self.code)
        self.assertEqual(self.code.count("FOR SELECT TO v3_cas_audit_table_owner"), 2)
        self.assertNotRegex(self.code, r"(?i)GRANT SELECT ON v3_cas_audit\\.(?:epoch_v1|intent_v1) TO (?:PUBLIC|service_role)")

    def test_stage5_rejects_missing_or_terminal_abort_ledger(self):
        stage5 = (ROOT / "supabase" / "v3-cas-audit-stage5-original-epoch-seal-INACTIVE.sql").read_text(encoding="utf-8")
        # The Stage5 template remains independently hardlocked. It must not
        # proceed when the abort ledger is absent or the current epoch was
        # terminally aborted, even if another path could surface an intent.
        self.assertIn("V3_STAGE5_EPOCH_SEAL_SOURCE_INACTIVE_APPROVAL_REQUIRED", stage5)
        self.assertIn("to_regclass('v3_cas_audit.prepared_fence_abort_v1') IS NULL", stage5)
        self.assertTrue(
            "OR EXISTS (SELECT 1 FROM v3_cas_audit.prepared_fence_abort_v1" in stage5
            and "WHERE epoch_id=v_id)" in stage5
        )
        self.assertLess(stage5.index("prepared_fence_abort_v1"), stage5.index("UPDATE v3_cas_audit.epoch_v1 SET sealed=true"))

    def test_existing_notebook_reader_signs_only_real_private_abort_row(self):
        reader = (ROOT / "tools" / "v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$PreparedAbortSignedCurrent", reader)
        self.assertIn("SET ROLE v3_cas_audit_reader;", reader)
        self.assertIn("BEGIN TRANSACTION READ ONLY;", reader)
        self.assertIn("FROM v3_cas_audit.prepared_fence_abort_v1 a", reader)
        self.assertIn("session_user='v3_cas_audit_reader_actor'", reader)
        self.assertIn("current_user='v3_cas_audit_reader'", reader)
        self.assertIn("count(*) FROM v3_cas_audit.intent_v1)=0", reader)
        self.assertIn("count(*) FROM v3_cas_audit.attempt_v1)=0", reader)
        self.assertIn("V3_PREPARED_ABORT_WIRE_DUPLICATE", reader)
        self.assertIn("V3_PREPARED_ABORT_INVALID_OR_STALE_ROW", reader)
        self.assertIn("Save-V3SignedNotebookReaderSnapshot -RawJson $wire", reader)
        self.assertIn("SIGNED_CURRENT_ABORT_ROW_NOT_RUNTIME_RELEASE", reader)
        self.assertIn("cloud_reader_provenance_independently_accepted_here=$false", reader)
        self.assertIn("marker_only_cancel_authorized=$false", reader)
        self.assertIn("native_task_change_authorized=$false", reader)

    def test_first_armed_pre_epoch_uses_existing_signed_no_cas_not_terminal_abort(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Test-V3Pr515PreEpochMarkerCancelCustodySOURCE_ONLY(")
        end = operator.index("# Scoped originalhost ARMED marker-only cancel (SOURCE ONLY; no release).", start)
        pre = operator[start:end]
        marker_start = operator.index("function Invoke-V3Pr515ArmedMarkerOnlyCancelSOURCE_ONLY(")
        marker_end = operator.index("# Current PR515 PRE-COMMIT manual recovery SOURCE ONLY.", marker_start)
        cancel = operator[marker_start:marker_end]
        self.assertIn("Test-V3Pr515SignedCurrentNoCasCustody", pre)
        self.assertIn("Get-V3Pr515SignedCasAndCloudSeriesReview", pre)
        self.assertIn("post_epoch_terminal_abort_required=$false", pre)
        for field in (
            "independent_cloud_provenance_authenticated_here=$false",
            "complete_attempt_unknown_history_authenticated_here=$false",
            "exclusive_native_pre_stop_task_and_pid_state_verified_here=$false",
            "atomic_marker_only_cancel_authorized=$false",
            "native_task_mutation_authorized=$false",
            "cas_or_paper_authorized=$false",
        ):
            self.assertIn(field, pre)
        self.assertNotIn("Test-V3Pr515SignedPreparedAbortReadback", pre)
        self.assertIn("[switch]$PreEpochOnly", cancel)
        self.assertIn("V3_MARKER_CANCEL_PRE_EPOCH_CANNOT_USE_POST_EPOCH_ABORT", cancel)
        self.assertIn("V3_MARKER_CANCEL_POST_EPOCH_CANNOT_USE_PRE_EPOCH_SNAPSHOT", cancel)
        self.assertIn("V3_MARKER_CANCEL_PRE_EPOCH_INDEPENDENT_CUSTODY_AND_ANTIRACE_HOLD", cancel)
        self.assertLess(
            cancel.index("if($PreEpochOnly){"),
            cancel.index("Test-V3Pr515SignedPreparedAbortReadback"),
        )
        self.assertRegex(
            cancel,
            r"(?s)\) \{\s*throw 'V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED'",
        )
        for forbidden in (
            "Remove-Item", "[IO.File]::Move(", "Stop-ScheduledTask",
            "Start-ScheduledTask", "Enable-ScheduledTask", "Disable-ScheduledTask",
        ):
            self.assertNotIn(forbidden, pre)

    def test_originalhost_signed_abort_review_cannot_claim_release(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Test-V3Pr515SignedPreparedAbortReadback(")
        end = operator.index("# Scoped originalhost ARMED marker-only cancel (SOURCE ONLY; no release).", start)
        body = operator[start:end]
        self.assertIn("Test-V3IndependentOriginalHostCmsSignature", body)
        self.assertIn("SIGNED_TERMINAL_ABORT_FORMAT_AND_PINS_MATCH_NOT_RELEASE", body)
        for field in (
            "epoch_id", "source_sha256", "prepared_fence_sha256",
            "caller_acl_sha256", "receipt_sha256", "issuer_actor",
            "created_at_utc", "ABORT_RECORDED_NOT_RELEASED",
            "ABORT_WIRE_DUPLICATE", "ABORT_WIRE_SOURCE_OR_TIME_MISMATCH",
        ):
            self.assertIn(field, body)
        for denied in (
            "independent_reader_cloud_provenance_verified_here=$false",
            "complete_attempt_unknown_history_proven=$false",
            "marker_only_cancel_authorized=$false",
            "native_task_mutations_authorized=$false",
        ):
            self.assertIn(denied, body)
        for forbidden in (
            "Stop-ScheduledTask", "Start-ScheduledTask",
            "Disable-ScheduledTask", "Enable-ScheduledTask",
            "Remove-Item", "[IO.File]::Move(", "[IO.File]::Replace(",
        ):
            self.assertNotIn(forbidden, body)

    def test_originalhost_marker_only_cancel_remains_independently_locked(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Invoke-V3Pr515ArmedMarkerOnlyCancelSOURCE_ONLY(")
        end = operator.index("# Current PR515 PRE-COMMIT manual recovery SOURCE ONLY.", start)
        body = operator[start:end]
        self.assertRegex(
            body,
            r"(?s)\) \{\s*throw 'V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED'",
        )
        for required in (
            "V3_MARKER_CANCEL_BAD_HOST_OR_RELEASE_PINS",
            "V3_MARKER_CANCEL_FENCE_CHANGED",
            "V3_MARKER_CANCEL_NOT_EXACT_PRESTOP_ARMED",
            "V3_MARKER_CANCEL_ATOMIC_RENAME_PHYSICAL_ANTIRACE_GATE_NOT_WIRED",
            "Test-V3ScopedIntakeTaskSet",
            "proposed_v3_repo_sha",
            "proposed_v3_bundle_sha256",
            "proposed_v3_strategy_sha256",
        ):
            self.assertIn(required, body)
        for forbidden in (
            "Stop-ScheduledTask", "Start-ScheduledTask",
            "Disable-ScheduledTask", "Enable-ScheduledTask",
            "Remove-Item", "[IO.File]::Replace(",
        ):
            self.assertNotIn(forbidden, body)
        self.assertIn("Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY -Source $fence -Archive $archive -ExpectedSha256 $ExpectedFenceSha256", body)
        self.assertLess(body.index("throw 'V3_MARKER_CANCEL_ATOMIC_RENAME_PHYSICAL_ANTIRACE_GATE_NOT_WIRED'"),
                        body.index("Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY -Source $fence"))
        self.assertIn("V3_MARKER_CANCEL_ARCHIVE_EXISTS_OR_FENCE_DRIFT", body)
        self.assertIn("V3_MARKER_CANCEL_POST_RENAME_READBACK_HOLD_PRESERVE_ARCHIVE", body)
        self.assertIn("V3_MARKER_CANCEL_V2R4_ORIGINAL_TASK_STATE_CHANGED", body)
        self.assertIn("v3-experimental-paper-old-intake-fence.aborted-", body)
        self.assertIn("CryptoMiniPC-V3PaperSingleWriter", body)
        self.assertNotIn("Copy-Item", body)
        self.assertIn("if($Execute){", operator)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED", operator)

    def test_native_rename_uses_same_exclusive_open_handle_and_never_self_releases(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY(")
        end = operator.index(" if([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT){", start)
        native = operator[start:end]
        for required in (
            "CreateFileW", "GENERIC_READ|DELETE_ACCESS,0",
            "FILE_FLAG_OPEN_REPARSE_POINT", "SetFileInformationByHandle",
            "sha.ComputeHash(bytes)", "FILE_RENAME_INFO_CLASS=3",
            "Marshal.WriteByte(memory,0,0)",
            "V3_EXCLUSIVE_ARCHIVE_PATH_SCOPE_HOLD",
            "V3_EXCLUSIVE_ARCHIVE_TARGET_EXISTS",
            "DemandAbsentTarget(target);",
            "archive-target-already-exists",
            "archive-target-unknown",
            "if(error!=2 && error!=3)",
            "V3_EXCLUSIVE_ARCHIVE_POSTRENAME_READBACK_HOLD",
            "independent_issuer_cas_custody_verified_here=$false",
            "cas_or_paper_authorized=$false",
        ):
            self.assertIn(required, native)
        self.assertNotIn("[IO.File]::Move(", native)
        self.assertNotIn("Stop-ScheduledTask", native)
        self.assertNotIn("Disable-ScheduledTask", native)
        self.assertIn("V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED", operator)
        self.assertLess(
            operator.index("throw 'V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED'"),
            operator.index("function Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY("),
        )
        self.assertIn("V3_MARKER_CANCEL_ATOMIC_RENAME_PHYSICAL_ANTIRACE_GATE_NOT_WIRED", operator)

    def test_pre_epoch_archive_identity_never_requires_nonexistent_epoch(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Invoke-V3Pr515ArmedMarkerOnlyCancelSOURCE_ONLY(")
        end = operator.index("# Current PR515 PRE-COMMIT manual recovery SOURCE ONLY.", start)
        body = operator[start:end]
        self.assertIn("$archiveId='pre-epoch-'+$ExpectedFenceSha256", body)
        self.assertIn("V3_MARKER_CANCEL_PRE_EPOCH_EPOCH_ID_FORBIDDEN", body)
        self.assertIn("V3_MARKER_CANCEL_POST_EPOCH_ID_INVALID", body)
        self.assertIn("$archiveId=$ExpectedEpochId", body)
        self.assertLess(body.index("if($PreEpochOnly){"), body.index("$archiveId='pre-epoch-'"))
        self.assertLess(body.index("throw 'V3_MARKER_CANCEL_ATOMIC_RENAME_PHYSICAL_ANTIRACE_GATE_NOT_WIRED'"), body.index("Invoke-V3Pr515NativeExclusiveFenceArchiveSOURCE_ONLY -Source $fence"))
        self.assertIn("V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED", body)

    def test_one_shot_native_observation_not_a_release_operator(self):
        path = ROOT / "tools" / "minipc-v3-pr515-pre-epoch-native-readonly-ack.ps1"
        reader = path.read_text(encoding="utf-8")
        for necessary in (
            "[Parameter(Mandatory=$true)][string]$ExpectedCandidateRepoSha",
            "Get-ScheduledTask", "Get-CimInstance Win32_Process",
            "Get-FileHash", "V3_MARKER_NOT_PRESTOP_ARMED",
            "exclusive_task_pid_antirace_proven=$false",
            "independently_authenticated_cloud_issuer_custody=$false",
            "complete_prospective_unknown_custody=$false",
            "marker_cancel_authorized=$false",
            "cas_or_paper_authorized=$false",
            "process_task_marker_cloud_writes=0",
        ):
            self.assertIn(necessary, reader)
        for forbidden in (
            "Stop-ScheduledTask", "Start-ScheduledTask", "Disable-ScheduledTask",
            "Enable-ScheduledTask", "Remove-Item", "[IO.File]::Move(",
            "Invoke-Sqlcmd", "Start-Process", "Set-Content", "New-Item",
        ):
            self.assertNotIn(forbidden, reader)

    def test_physical_reader_binds_existing_cms_t0_to_host_without_release(self):
        script = (ROOT / "tools" / "minipc-v3-pr515-pre-epoch-native-readonly-ack.ps1").read_text(encoding="utf-8")
        for required in (
            "$NotebookReaderJson", "$NotebookReaderCms",
            "$ReviewedNotebookCertificateSha256",
            "V3_T0_PAIR_MUST_USE_EXISTING_MISTRAL_SHARE",
            "[System.Security.Cryptography.Pkcs.SignedCms]",
            "2.16.840.1.101.3.4.2.1",
            "$signed.CheckSignature($true)",
            "V3_T0_DUPLICATE_FIELD",
            "V3_CAS_FORWARD_T0_CURRENT_CATALOG_READONLY_V1",
            "V3_T0_UNEXPECTED_CAS_ACTIVITY",
            "V3_T0_CLAIMED_FALSE_AUTHORITY",
            "V3_T0_NOT_CONTEMPORANEOUS_WITH_HOST",
            "signed_current_notebook_cloud_catalog_cryptographically_valid=$signedCurrentMatch",
            "signed_current_cloud_and_originalhost_within_30_seconds=$notebookCloudTimeMatched",
            "independent_notebook_issuer_authority_verified_here=$false",
            "exclusive_task_pid_antirace_proven=$false",
            "complete_prospective_unknown_custody=$false",
            "marker_cancel_authorized=$false",
            "process_task_marker_cloud_writes=0",
        ):
            self.assertIn(required, script)
        for effect in (
            "Stop-ScheduledTask", "Start-ScheduledTask",
            "Disable-ScheduledTask", "Enable-ScheduledTask",
            "[IO.File]::Move(", "Remove-Item", "Start-Process",
            "Invoke-Sqlcmd", "Set-Content", "New-Item",
        ):
            self.assertNotIn(effect, script)

    def test_native_double_snapshot_drift_cannot_promote_exclusive_lease(self):
        script = (ROOT / "tools" / "minipc-v3-pr515-pre-epoch-native-readonly-ack.ps1").read_text(encoding="utf-8")
        for required in (
            "Start-Sleep -Milliseconds 750",
            "$firstNative -ceq $secondNative",
            "$firstPids -ceq $secondPids",
            "$firstFenceHash -ceq $secondFenceHash",
            "two_native_observations_750ms_apart_stable=$shortNativeStable",
            "local_snapshot_not_an_exclusive_native_lock=$true",
            "exclusive_task_pid_antirace_proven=$false",
            "marker_cancel_authorized=$false",
            "cas_or_paper_authorized=$false",
        ):
            self.assertIn(required, script)
        self.assertEqual(script.count("Get-CimInstance Win32_Process"), 2)
        for forbidden in ("Stop-ScheduledTask", "Disable-ScheduledTask",
                          "Enable-ScheduledTask", "Start-ScheduledTask",
                          "[IO.File]::Move(", "Remove-Item", "Invoke-Sqlcmd"):
            self.assertNotIn(forbidden, script)

    def test_readonly_cross_source_digest_is_bound_but_never_release(self):
        script = (ROOT / "tools" / "minipc-v3-pr515-pre-epoch-native-readonly-ack.ps1").read_text(encoding="utf-8")
        for required in (
            "$notebookPayloadSha256=",
            "$notebookCmsSha256=",
            "$signedCurrentMatch -and $notebookCloudTimeMatched -and $shortNativeStable -and $pass",
            "$_.state -cne 'Running' -or $_.action_count -ne 1",
            "'V3_PR515_READONLY_CROSS_SOURCE_EVIDENCE_V1'",
            "$ExpectedCandidateRepoSha",
            "$firstNative",
            "$firstPids",
            "$firstFencePhase",
            "$firstFenceHash",
            "$ReviewedNotebookCertificateSha256",
            "$notebookPayloadSha256",
            "$notebookCmsSha256",
            "cross_source_readonly_evidence_sha256=$crossSourceEvidenceSha256",
            "cross_source_evidence_is_release_authority=$false",
            "independently_authenticated_cloud_issuer_custody=$false",
            "exclusive_task_pid_antirace_proven=$false",
            "marker_cancel_authorized=$false",
        ):
            self.assertIn(required, script)
        self.assertEqual(script.count("Get-CimInstance Win32_Process"), 2)
        for forbidden in ("Disable-ScheduledTask", "Stop-ScheduledTask",
                          "Set-Content", "Invoke-Sqlcmd", "Remove-Item"):
            self.assertNotIn(forbidden, script)

    def test_native_registered_task_xml_drift_is_detected_without_mutation(self):
        script = (ROOT / "tools" / "minipc-v3-pr515-pre-epoch-native-readonly-ack.ps1").read_text(encoding="utf-8")
        for required in (
            "function Get-V3Pr515NativeTaskXmlSha256",
            "Export-ScheduledTask -TaskName $TaskName -TaskPath",
            "registered_task_xml_sha256=(Get-V3Pr515NativeTaskXmlSha256 -TaskName $name)",
            "$firstV3XmlSha256=Get-V3Pr515NativeTaskXmlSha256",
            "$secondV3XmlSha256=Get-V3Pr515NativeTaskXmlSha256",
            "$firstV3XmlSha256 -ceq $secondV3XmlSha256",
            "v3_registered_task_xml_sha256=$firstV3XmlSha256",
            "$firstNative -ceq $secondNative",
            "$firstV3XmlSha256,",
            "local_snapshot_not_an_exclusive_native_lock=$true",
            "exclusive_task_pid_antirace_proven=$false",
        ):
            self.assertIn(required, script)
        self.assertEqual(
            script.count("registered_task_xml_sha256=(Get-V3Pr515NativeTaskXmlSha256 -TaskName $name)"), 2
        )
        for forbidden in (
            "Register-ScheduledTask", "Set-ScheduledTask", "Disable-ScheduledTask",
            "Stop-ScheduledTask", "Start-ScheduledTask", "Unregister-ScheduledTask"
        ):
            self.assertNotIn(forbidden, script)

    def test_single_originalhost_operator_wires_pinned_notebook_t0_native_readback(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        section = operator.split("if($ReviewSignedForwardT0NativeBridge){", 1)[1].split(
            "# Physically grounded, READONLY Phase-A cancellation review.", 1
        )[0]
        for token in (
            "[switch]$ReviewSignedForwardT0NativeBridge",
            "[string]$BridgeHelperFile",
            "[string]$ReviewedBridgeHelperGitBlob",
        ):
            self.assertIn(token, operator)
        for token in (
            "V3_NATIVE_T0_BRIDGE_ARGUMENTS_HOLD",
            "V3_NATIVE_T0_BRIDGE_WRONG_HOST",
            "V3_NATIVE_T0_BRIDGE_BLOB_MISMATCH",
            "git hash-object -- $pin.Path",
            "$ExpectedOriginalhostOperatorGitBlob",
            "$ReviewedBridgeHelperGitBlob",
            "$args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',$helper",
            "$wire=@(& powershell.exe @args)",
            "V3_NATIVE_T0_BRIDGE_CHILD_HOLD",
            "cross_source_readonly_evidence_sha256",
            "two_native_observations_750ms_apart_stable",
            "signed_current_cloud_and_originalhost_within_30_seconds",
            "independently_authenticated_cloud_issuer_custody -ne $false",
            "complete_prospective_unknown_custody -ne $false",
            "exclusive_task_pid_antirace_proven -ne $false",
            "marker_cancel_authorized -ne $false",
            "cas_or_paper_authorized -ne $false",
            "status='SIGNED_CURRENT_T0_NATIVE_JOIN_NOT_RELEASE'",
            "independent_issuer_and_unknown_custody_proven=$false",
            "exclusive_os_task_pid_lock_proven=$false",
            "marker_stop_cas_or_paper_authorized=$false",
        ):
            self.assertIn(token, section)
        for forbidden in ("Stop-ScheduledTask", "Disable-ScheduledTask",
                          "Enable-ScheduledTask", "Start-ScheduledTask",
                          "Invoke-Sqlcmd", "Remove-Item", "Set-Content"):
            self.assertNotIn(forbidden, section)
        self.assertIn("V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED", operator)
        self.assertIn("V3_PR515_NATIVE_STOP_EXTERNAL_STAGE4_ISSUER_NOT_WIRED", operator)

    def test_isolated_native_windows_smoke_cannot_touch_originalhost(self):
        path = ROOT / "tests" / "test_v3_pr515_native_exclusive_rename_smoke.ps1"
        smoke = path.read_text(encoding="utf-8")
        for required in (
            "V3_NATIVE_SMOKE_WINDOWS_ONLY",
            "V3_NATIVE_SMOKE_OPERATOR_NOT_EXACT_REVIEWED_BYTES",
            "V3_NATIVE_SMOKE_PARENT_HARDLOCK_MISSING",
            "V3-Pr515-NativeSmoke-",
            "GetTempPath()",
            "[V3Pr515NativeFenceRenameV1]::RenamePinned",
            "wrong_sha_denied=$wrongHashRejected",
            "overwrite_denied=$existingTargetRejected",
            "[Convert]::ToBase64String($targetBytes)",
            "[Convert]::ToBase64String($originalTargetBytes)",
            "sharing_conflict_denied=$shareConflictRejected",
            "originalhost_marker_or_tasks_mutated=$false",
            "operator_release_authorized=$false",
            "v3_paper_authorized=$false",
        ):
            self.assertIn(required, smoke)
        for forbidden in (
            "Stop-ScheduledTask -TaskName", "Enable-ScheduledTask -TaskName",
            "Disable-ScheduledTask -TaskName", "Start-ScheduledTask -TaskName",
            "Invoke-Sqlcmd", "Supabase", "Set-ScheduledTask",
        ):
            self.assertNotIn(forbidden, smoke)
        self.assertIn("[IO.Directory]::Delete($root,$true)", smoke)

    def test_receipt_is_not_release_or_auto_rearm(self):
        for token in [
            "session_user <> 'v3_cas_inhibit_issuer_actor'",
            "FOR UPDATE", "NOT e.sealed", "e.next_ordinal=1",
            "v3_cas_audit.intent_v1", "v3_cas_audit.attempt_v1",
            "i.state='INHIBITED'", "i.native_stop_at_utc IS NULL",
            "i.acknowledged_at_utc IS NULL",
            "rolname='v3_cas_executor_actor'", "rolname='v3_cas_executor'",
            "ABORT_RECORDED_NOT_RELEASED",
        ]:
            self.assertIn(token, self.code)
        self.assertNotRegex(self.code, r"(?im)^\s*(?:ALTER ROLE|CREATE USER|INSERT INTO public\.paper_series)")
        self.assertNotRegex(self.code, r"(?i)\b(?:Stop|Start|Enable|Disable)-ScheduledTask\b")

if __name__ == "__main__":
    unittest.main()
