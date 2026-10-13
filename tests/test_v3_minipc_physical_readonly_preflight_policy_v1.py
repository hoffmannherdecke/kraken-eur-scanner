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

if __name__=="__main__":
    unittest.main()
