"""Physical host readiness script must never mutate 28h observer/V2R4, spend, or sync."""
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/check-minipc-v3-physical-writer-readiness.ps1"

class PhysicalReadinessPolicyTests(unittest.TestCase):
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



if __name__=="__main__":
    unittest.main()
