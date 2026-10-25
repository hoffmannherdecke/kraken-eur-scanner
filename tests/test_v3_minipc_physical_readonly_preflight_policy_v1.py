"""Physical host readiness script must never mutate 28h observer/V2R4, spend, or sync."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/check-minipc-v3-physical-writer-readiness.ps1"

class PhysicalReadinessPolicyTests(unittest.TestCase):
    def assert_locked_pr515_native_stop_only(self, source):
        """Exactly two dormant Task cmdlet sites, and no reachable release entry."""
        name="function Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY("
        boundary="# Native TaskScheduler disable may change exactly one XML field:"
        self.assertEqual(source.count(name),1)
        pre, remainder=source.split(name,1)
        locked, post=remainder.split(boundary,1)
        dormant=name+locked
        outside=pre+boundary+post
        self.assertEqual(len(re.findall(r"(?m)^\s*Disable-ScheduledTask\b",dormant)),1)
        self.assertEqual(len(re.findall(r"(?m)^\s*Stop-ScheduledTask\b",dormant)),1)
        self.assertNotRegex(outside,r"(?m)^\s*(?:Disable|Stop|Start|Enable|Register)-ScheduledTask\b")
        self.assertNotRegex(dormant,r"(?m)^\s*(?:Start|Enable|Register)-ScheduledTask\b")
        self.assertIn("V3_PR515_NATIVE_STOP_SOURCE_UNCONDITIONALLY_LOCKED",dormant)
        self.assertRegex(dormant,r"(?s)\) \{\s*# Independent second hard-lock:.*?throw 'V3_PR515_NATIVE_STOP_SOURCE_UNCONDITIONALLY_LOCKED'")
        self.assertIn("V3_PRECAS_ARMED_NOT_ACKED_LEAVE_FENCE",dormant)
        self.assertLess(dormant.index("V3_PRECAS_ARMED_NOT_ACKED_LEAVE_FENCE"),
                        dormant.index("Disable-ScheduledTask"))
        self.assertIn("if($Execute){",outside)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",outside)
        self.assertNotRegex(outside,r"(?m)^\s*Invoke-V3Pr515ScopedNativeStopSOURCE_ONLY\b")


    def test_no_side_effect_commands_or_runtime_invocation(self):
        s=SCRIPT.read_text(encoding="utf-8")
        effective="\n".join(line for line in s.splitlines()
                            if not line.lstrip().startswith("#"))
        banned=(
            r"(?i)\b(?:Set-Content|Add-Content|Out-File|Tee-Object|"
            r"New-Item|Remove-Item|Move-Item|Copy-Item|Start-Process|"
            r"Start-ScheduledTask|Stop-ScheduledTask|Disable-ScheduledTask|"
            r"Set-ScheduledTask|Register-ScheduledTask|Unregister-ScheduledTask|"
            r"Invoke-RestMethod|Invoke-WebRequest|Invoke-Expression|"
            r"Invoke-Command|Enter-PSSession|Restart-Computer|"
            r"Set-ItemProperty|Set-Item|WriteAllText|"
            r"git\s+pull|git\s+fetch|git\s+checkout|"
            r"curl|wget|python\.exe|pip\.exe)\b"
        )
        self.assertIsNone(re.search(banned,effective))
        for marker in (
            "Get-ScheduledTask","Get-FileHash","Get-Content",
            "v3-canary-observer-28h-plan.json","v3-canary-observer-28h-heartbeat.json",
            "PAPER-V2R4-20261009T110135Z",
            "v3_paper_intake_receipt_stage_v1.py",
            "v3_paper_minipc_one_candidate_v1.py",
            "model_http_calls=0","filesystem_writes=$false",
            "new_v3_writer_started=$false","v2r4_changed=$false",
            "canary_manifest_valid_and_pinned=$canarySafe",
        ):
            self.assertIn(marker,s)
    def test_physical_task_evidence_never_mislabels_config_as_single_writer_proof(self):
        s=SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "CryptoMiniPC-V2R4PaperCandidates",
            "CryptoMiniPC-V2R4PaperWait",
            "CryptoMiniPC-V2R4PaperLifecycle",
            "CryptoMiniPC-V2R4PaperCloudSync",
            "Get-ScheduledTaskInfo",
            "active_v2r4_host_runtime_count_is_config_files_not_processes=$true",
            "physical_v2r4_paper_task_readback=$v2r4PaperTasks",
            "physical_single_writer_cutover_dry_run_passed=$false",
            "physical_v2r4_intake_stop_ack_proven=$false",
            "physical_v3_writer_start_ack_proven=$false",
            "cloud_expected_predecessor_cas_verified=$false",
            "physical_task_name_scan_cannot_prove_absence_of_other_writers=$true",
        ):
            self.assertIn(marker,s)
        # No read-only Windows task query can return a physical or CAS
        # release token; this script only inventories original evidence.
        self.assertNotIn("physical_single_writer_cutover_dry_run_passed=$true",s)

    def test_fixed_28h_task_end_requires_real_schedule_and_cannot_claim_release(self):
        s=SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "Get-ScheduledTaskInfo",
            "[System.Xml.XmlConvert]::ToTimeSpan",
            "[timespan]::FromHours(28)",
            "$taskActionMatchesPinnedObserver",
            "$taskState -in @('Ready','Disabled')",
            "$pinChecked -eq 9",
            "$pinMismatches.Count -eq 0",
            "canary_original_schedule_readback_status=$taskScheduleReadbackStatus",
            "canary_scheduler_end_candidate_for_independent_review=$canarySchedulerEndCandidate",
            "canary_physical_observer_end_ack_from_this_single_readback=$false",
            "canary_after_deadline_requires_independent_host_cloud_ack=$true",
        ):
            self.assertIn(marker,s)
        self.assertNotIn("canary_physical_observer_end_ack_from_this_single_readback=$true",s)
        self.assertNotIn("Start-ScheduledTask", "\n".join(
            line for line in s.splitlines() if not line.lstrip().startswith("#")))

    def test_script_has_no_secret_exfiltration_or_unbounded_scan(self):
        s=SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("Get-Content -LiteralPath $secret",s)
        self.assertNotIn("Secrets\\",s)
        self.assertIn("Select-Object -First 100",s)
        self.assertNotIn("Invoke-WebRequest",s)
        self.assertNotIn("Start-Job",s)
        self.assertIn("ConvertTo-Json -Depth 8",s)
        self.assertIn("new_cloud_sync_performed=$false",s)

    def test_four_real_tasks_expose_only_bounded_readonly_owner_evidence(self):
        s=SCRIPT.read_text(encoding="utf-8")
        # No new Task, process, secret, Cloud or runtime mutation pathways.
        for marker in (
            "'CryptoMiniPC-V2R4PaperCandidates'=@{script='v2r4-paper-local-runtime.py'",
            "'CryptoMiniPC-V2R4PaperWait'=@{script='wait_launcher.py'",
            "'CryptoMiniPC-V2R4PaperLifecycle'=@{script='v2r4-paper-local-runtime.py'",
            "'CryptoMiniPC-V2R4PaperCloudSync'=@{script='v2r4-paper-cloud-sync.py'",
            "action_count=$null",
            "$actions=@($oldTask.Actions)",
            "if($actions.Count -eq 1)",
            "documented_script_basename_hint_matches=$false",
            "$scriptTokens.Count -eq 1",
            "$oldTask.Principal.UserId",
            "$oldTask.Settings.RestartCount",
            "$oldTask.Settings.RestartInterval",
            "$oldTask.Settings.MultipleInstances",
            "$record.action_sha256=",
            "$role.heartbeat",
            "$role.max_age",
            "$age -ge -30",
            "physical_task_action_sha256_has_no_raw_arguments=$true",
            "physical_pr291_wait_launcher_basename_only_not_loaded_module_sha_proof=$true",
            "physical_supervisor_and_windows_rearm_fence_proven=$false",
            "physical_closed_old_series_followup_exit_relay_proven=$false",
        ):
            self.assertIn(marker,s)
        # SHA256 summarizes the command; raw args are not included in output.
        self.assertNotRegex(s,r"(?m)^\s*(?:args|arguments|raw_task_arguments)\s*=")
        self.assertNotIn("physical_supervisor_and_windows_rearm_fence_proven=$true",s)
        self.assertNotIn("physical_closed_old_series_followup_exit_relay_proven=$true",s)
        self.assertIn("evidence='PARTIAL_TASK_ACTION_AND_HEARTBEAT_READBACK_NOT_LIVE_SOURCE_OR_REARM_PROOF'",s)


    def test_v3_inactive_cutover_reads_current_pr326_wait_stage_only(self):
        script=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        self.assertIn("Staging\\v2r4-wait-pr326-isolated-c660ebb87a39",script)
        self.assertNotIn("Runtime\\v2r4-paper-stage-d8b35a8ec2e6",script)
        self.assertIn("OriginalStage=$cmd.Contains($oldStage)",script)
        self.assertIn("wait_closed_descendants_snapshot_only_no_stop_authority=$true",script)
        self.assertIn("v3_live_release_authorized=$false",script)
        self.assertIn("if($Execute){",script)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",script)


    def test_precas_originalhost_xml_backup_is_explicit_and_preserves_live_writers(self):
        """A real recovery backup is useful; it must never be mistaken for a cutover."""
        s=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$BackupOriginalIntake",s)
        self.assertIn("V3_PRECAS_NATIVE_XML_BACKUP_ONLY",s)
        self.assertIn("original Windows host required for recovery artifact",s)
        self.assertIn("original local administrator confirmation required",s)
        self.assertIn("Test-V3CutoverPreparationPolicy -Report $Report",s)
        self.assertIn("original independent snapshot/native task SHA mismatch",s)
        self.assertIn("original V2R4 fence or maintenance marker appeared",s)
        self.assertIn("OriginalIntakeXmlOnly",s)
        self.assertIn("CreateDirectory($folder,$secure)",s)
        self.assertIn("SetAccessRuleProtection($true,$false)",s)
        self.assertIn("[IO.FileMode]::CreateNew",s)
        self.assertIn("$handle.Flush($true)",s)
        self.assertIn("original native task changed during XML backup",s)
        self.assertIn("ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED",s)
        for fail_closed in (
            "v3_release_or_six_proofs_credited=0",
            "new_v3_writer_started=$false",
            "cloud_cas_invoked=$false",
            "scheduler_task_mutations=$false",
            "original_v2r4_changed=$false",
            "original_cloud_series_independently_checked=$false",
            "imported_or_loaded_v3_code_attested=$false",
        ):
            self.assertIn(fail_closed,s)
        self.assertLess(s.index("if($Execute){"),s.index("if($BackupOriginalIntake) {"))
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",s)
        self.assert_locked_pr515_native_stop_only(s)
        self.assertNotIn("Invoke-RestMethod",s)
        self.assertNotIn("Invoke-WebRequest",s)

    def test_future_paper_release_sources_are_explicitly_hashed_without_claiming_pins(self):
        s=SCRIPT.read_text(encoding="utf-8")
        required=(
            "v3_paper_shared_candidate_intake_plan_v1.py",
            "v3_paper_existing_owner_source_bridge_v1.py",
            "v3_paper_intake_receipt_stage_v1.py",
            "v3_paper_signed_source_journal_stage_v1.py",
            "v3_paper_minipc_one_candidate_v1.py",
            "v3_paper_minipc_selective_tick_v1.py",
            "v3_paper_minipc_closed_1m_capture_v1.py",
            "v3_paper_wait_observer_v1.py",
            "v3_paper_minipc_followup_v1.py",
            "v3_paper_cloud_receipt_sync_v1.py",
            "minipc-runtime-supervisor.ps1",
            "v3-paper-evidence-relay",
        )
        for name in required:
            self.assertIn(name,s)
        self.assertIn("$v3ReleaseSourcePaths=@(",s)
        self.assertIn("Get-FileHash -LiteralPath $file -Algorithm SHA256",s)
        self.assertIn("future_v3_release_source_fingerprint_inventory=@($v3ReleaseSourceHashes)",s)
        self.assertIn("future_v3_release_source_files_all_readable=$v3ReleaseSourceHashComplete",s)
        self.assertIn("future_v3_release_source_hashes_compared_to_approved_release=$false",s)
        self.assertIn("future_v3_paper_writer_installed_by_this_check=$false",s)
        self.assertIn("future_v3_paper_single_writer_proven_by_this_check=$false",s)

    def test_bounded_next_writer_hash_inventory_never_touches_secrets_or_live_release(self):
        s=SCRIPT.read_text(encoding="utf-8")
        chunk=s.split("$v3ReleaseSourcePaths=@(",1)[1].split("\n)",1)[0]
        # Exactly twelve source files; none in Secrets/State or private runtime.
        self.assertEqual(chunk.count(".py'")+chunk.count(".ps1'")+chunk.count(".ts'"),12)
        for forbidden in ("Secrets", ".env", "Runtime", "State",
                          "paper_runtime_control.json","service_role"):
            self.assertNotIn(forbidden,chunk)
        self.assertNotIn("future_v3_release_source_hashes_compared_to_approved_release=$true",s)
        self.assertNotIn("future_v3_paper_writer_installed_by_this_check=$true",s)


    def test_original_v3_task_action_and_stage_sha_only_no_loaded_release_proof(self):
        s=SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "native_task_action_sha256=$null",
            "native_task_launcher_file_sha256=$null",
            "native_task_python_executable_hint=$false",
            "native_task_stage_path_shape_match=$false",
            "native_task_loaded_module_independently_verified=$false",
            "Get-FileHash -LiteralPath $launchFile -Algorithm SHA256",
            "[BitConverter]::ToString($hasher.ComputeHash($data))",
            "v3_paper_minipc_native_launcher_v1.py",
        ):
            self.assertIn(marker,s)
        self.assertNotIn("native_task_loaded_module_independently_verified=$true",s)
        self.assertNotIn("native_task_launcher_file_sha256=$true",s)

    def test_native_task_python_parent_observation_remains_readonly_untrusted_hint(self):
        source=SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "native_python_parent_process_observed=$false",
            "native_python_parent_matches_task_action_hint=$false",
            "native_powershell_process_token_is_system=$false",
            "native_runtime_identity_independently_verified=$false",
            'Get-CimInstance Win32_Process -Filter "ProcessId=$PID"',
            'Get-CimInstance Win32_Process -Filter "ProcessId=$parentId"',
            "WindowsIdentity]::GetCurrent().User.Value",
            '$parentArgs.Contains($argsText)',
        ):
            self.assertIn(marker,source)
        self.assertNotIn("native_runtime_identity_independently_verified=$true",source)
        self.assertNotIn("native_task_loaded_module_independently_verified=$true",source)
        self.assertNotRegex(source,r"(?m)^\s*(?:native_raw_commandline|parent_args_raw)\s*=")

    def test_postcas_inventory_reuses_existing_supervisor_without_release_authority(self):
        s=SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "V3_NATIVE_POSTCAS_LOCAL_INSPECTION_ONLY_V1",
            "Get-ScheduledTask -TaskName 'CryptoMiniPC-V3PaperSingleWriter'",
            "v3_paper_successor_readonly",
            "V3_PAPER_SUCCESSOR_SUPERVISOR_READONLY_OBSERVATION_V1",
            "original_supervisor_observation=[string]$peek.status",
            "physical_v3_postcas_local_inventory=$v3PostCas",
            "native_task_uses_old_readonly_launcher=$true",
            "old_intake_tasks_disabled=$false",
            "protected_old_aftercare_running=$false",
            "exact_loaded_source_sha_verified=$false",
            "old_python_process_tree_absent_verified=$false",
            "independent_cloud_cas_verified=$false",
            "six_external_e2e_proofs_verified=$false",
            "live_paper_activation_authorized=$false",
            "model_calls=0","cloud_writes=0","tasks_changed=0",
        ):
            self.assertIn(marker,s)
        self.assertNotIn("live_paper_activation_authorized=$true",s)
        self.assertNotIn("independent_cloud_cas_verified=$true",s)
        self.assertNotIn("six_external_e2e_proofs_verified=$true",s)
        self.assertNotIn("Start-ScheduledTask",s)
        self.assertNotIn("Enable-ScheduledTask",s)
        # The unchanged current pre-cutover source remains the authority.
        self.assertIn("new_v3_writer_started=$false",s)
        self.assertIn("v2r4_changed=$false",s)



    def test_pr515_precommit_recovery_needs_current_backup_and_independent_ack(self):
        """A legacy synthetic recovery proposal alone cannot green-light restore."""
        s=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        recovery=s.split("function Resolve-V3ScopedCutoverRecovery",1)[1].split(
            "# Exact adapter for the *actual*",1)[0]
        shared=s.split("function Test-V3Pr515FreshRecoveryIdentity",1)[1].split(
            "# A pure decision matrix.",1)[0]
        preview=s.split("function Read-V3Pr515FreshRecoveryPreview",1)[1].split(
            "if($Execute){",1)[0]
        for required in (
            "current_pr515_readonly_preview",
            "V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1",
            "COMPATIBLE_READONLY_NOT_RELEASED",
            "pr515_sha_pin_separately_verified -eq $true",
            "fresh_current_xml_after_quiesce_independently_checked -eq $true",
            "independent_cloud_precommit_cas_never_invoked_ack -eq $true",
            "independent_cloud_old_only_after_quiesce_ack -eq $true",
            "HOLD_CURRENT_PR515_BACKUP_OR_INDEPENDENT_CLOUD_ACK",
            "current_backup_and_external_cloud_proof_required=$true",
            "source_only_pr515_recovery_readback_not_authority=$true",
            "automatic_old_writer_rearm_allowed=$false",
            "operator_stop_disable_implemented=$false",
            "host_rollback_implemented=$false",
            "cloud_cas_executed=$false",
        ):
            self.assertIn(required,recovery+shared)
        self.assertIn("Test-V3Pr515FreshRecoveryIdentity -Preview $current",recovery)
        for required in (
            "current_backup_directory_leaf=$name",
            "pr515_source_sha256=$ExpectedCloudSha",
            "current_native_task_xml_sha256=@(",
            "current_backup_valid_while_intakes_running_only=$true",
            "preview_is_not_poststop_or_independent_cloud_ack=$true",
            "external_sha_pin_independently_authenticated=$false",
        ):
            self.assertIn(required,preview)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",s)
        self.assertNotIn("Invoke-RestMethod",s)

    def test_pr515_no_rearm_phase_contract_reuses_one_fresh_source_identity(self):
        """Stop/recovery planning stays offline, fail-closed and PR515 specific."""
        s=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        shared=s.split("function Test-V3Pr515FreshRecoveryIdentity",1)[1].split(
            "# A pure decision matrix.",1)[0]
        phase=s.split("function Get-V3SingleWriterFenceDryRunPlan",1)[1].split(
            "# Pure, externally signed",1)[0]
        for required in (
            "current_native_task_xml_sha256",
            "current_backup_valid_while_intakes_running_only -eq $true",
            "preview_is_not_poststop_or_independent_cloud_ack -eq $true",
            "pr515_source_sha256",
            "current_backup_directory_leaf",
            "external_sha_pin_independently_authenticated -eq $false",
        ):
            self.assertIn(required,shared)
        for required in (
            "Test-V3Pr515FreshRecoveryIdentity -Preview $Receipt.current_pr515_readonly_preview",
            "pr515_sha_pin_separately_verified -ne $true",
            "current_backup_original_xml_prestop_verified -ne $true",
            "CURRENT_PR515_ORIGINAL_BACKUP_IDENTITY_UNVERIFIED",
            "two_distinct_quiesced_supervisor_cycles_readback -ne $true",
            "pr515_cloudsync_precommit_no_network_hold_readback -ne $true",
            "current_backup_xml_after_quiesce_readback -ne $true",
            "independent_old_only_cloud_readback_after_quiesce -ne $true",
            "independent_cas_never_invoked_readback_after_quiesce -ne $true",
            "HOLD_PR515_QUIESCED_OR_CLOUD_ACK_INCOMPLETE",
            "REQUIRE_EFFECTIVE_PR515_CLOUDSYNC_SHA_AND_TWO_FRESH_BACKUP_XML_HASHES",
            "REQUIRE_TWO_DISTINCT_QUIESCED_SUPERVISOR_CYCLES_AND_PR515_CLOUDSYNC_PRECOMMIT_HOLD",
            "REQUIRE_FRESH_POSTSTOP_TASK_XML_AND_INDEPENDENT_CLOUD_CAS_NEVER_READBACK",
            "pre_cas_recovery_only_if_cas_never_attempted=$true",
            "step_implementation_present=$false",
            "cloud_cas_invoke_permitted=$false",
        ):
            self.assertIn(required,phase)
        self.assertIn("if($Execute){",s)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",s)
        self.assert_locked_pr515_native_stop_only(s)
        self.assertNotIn("Invoke-RestMethod",s)

    def test_pr515_quiesced_readback_is_separate_and_cannot_rearm(self):
        """The original scoped operator reads disabled Task XML without mutation."""
        s=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        for required in (
            "[switch]$PreviewPr515Quiesced",
            "[switch]$ExpectedQuiesced",
            "Test-V3Pr515DisabledOnlyXmlDifference",
            "Test-V3Pr515QuiescedLocalHold",
            "V3_PRECAS_PR515_QUIESCED_READONLY_COMPATIBILITY_V1",
            "QUIESCED_NATIVE_SOURCE_MATCH_NOT_RELEASED",
            "Native disabled Task changed beyond Enabled configuration",
            "Invalid or historical drill-only QUIESCED marker",
            "Native Supervisor or PR515 precommit no-network hold mismatch",
            "after_disable_enabled_only_native_xml_comparison=$ExpectedQuiesced.IsPresent",
            "two_distinct_supervisor_cycles_verified=$false",
            "old_intake_pid_family_absence_independently_verified=$false",
            "independent_cloud_cas_never_invoked_verified=$false",
            "if($PreviewPr515Quiesced) {",
            "-ExpectedQuiesced",
        ):
            self.assertIn(required,s)
        self.assertLess(s.index("if($Execute){"),s.index("if($PreviewPr515Quiesced) {"))
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",s)
        self.assert_locked_pr515_native_stop_only(s)
        self.assertNotIn("Invoke-RestMethod",s)
        self.assertNotIn("Invoke-WebRequest",s)
        self.assertNotIn("drill_only=$false",s)

    def test_pr515_fresh_native_backup_preview_fail_closed_and_never_cutover(self):
        """New PR515 preview compares current native XML and disk bytes only."""
        s=(ROOT/"tools/minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        for required in (
            "[switch]$PreviewPr515PreCas",
            "OriginalBackupDirectory",
            "ExpectedPr515SourceSha256",
            "V3Paper-PreCAS-Backup-[a-f0-9]{32}",
            "V3_PRECAS_NATIVE_XML_BACKUP_ORIGINALHOST_V1",
            "ORIGINAL_TASK_XML_BACKUP_ONLY_NOT_RELEASED",
            "backup-manifest.json",
            "Get-Acl -LiteralPath $folder",
            "AreAccessRulesProtected",
            "S-1-5-18", "S-1-5-32-544",
            "original_v2r4_changed -ne $false",
            "cloud_cas_invoked -ne $false",
            "Get-V3OriginalNativeActionSha $task.Actions[0]",
            "Export-ScheduledTask -TaskName $role.name",
            "Test-V3FreshBackupFileBytes",
            "PR515-CloudSync-INACTIVE-20261022",
            "Get-FileHash -LiteralPath $cloudFile -Algorithm SHA256",
            "V3_PRECAS_PR515_FRESH_BACKUP_READONLY_COMPATIBILITY_V1",
            "COMPATIBLE_READONLY_NOT_RELEASED",
            "external_sha_pin_independently_authenticated=$false",
            "single_writer_pid_and_lock_proven=$false",
            "physical_task_restore_tested=$false",
            "scheduler_task_mutations=$false",
            "technical_release_proofs_credited=0",
        ):
            self.assertIn(required,s)
        # Reject any attempt to use this read-only report as old-intake stop,
        # a complete paper release or a substitute for the six proofs.
        self.assertIn("if($Execute){",s)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED",s)
        self.assertIn("if($PreviewPr515PreCas) {",s)
        self.assertIn("if($BackupOriginalIntake) {",s)
        self.assertIn("$BackupOriginalIntake -or $Confirm -or",s)
        self.assertLess(s.index("if($Execute){"),s.index("if($PreviewPr515PreCas) {"))
        self.assert_locked_pr515_native_stop_only(s)
        self.assertNotIn("Invoke-RestMethod",s)
        self.assertNotIn("Invoke-WebRequest",s)
        self.assertNotIn("PR332-CloudSync-Vorher-",s)
        self.assertNotIn("drill_only=$false",s)



if __name__=="__main__":
    unittest.main()
