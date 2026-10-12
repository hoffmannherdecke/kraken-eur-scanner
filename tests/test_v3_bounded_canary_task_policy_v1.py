"""Static gate for a separately authorized, time-limited Windows V3 observer.

Do not run PowerShell in CI; parse AST separately. Source must remain isolated
from V2R4 tasks, MODEL HTTP and brokerage or Paper activation.
"""
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
INSTALL=ROOT/"tools"/"install-minipc-v3-bounded-canary-observer.ps1"
RUN=ROOT/"tools"/"minipc-v3-bounded-canary-observer-task.ps1"

class BoundedCanaryTaskPolicyTests(unittest.TestCase):
    def test_explicit_one_windows_task_one_lifetime_one_coin_cap(self):
        install=INSTALL.read_text("utf-8")
        for required in (
            "RUN_V3_CANARY_READONLY_28H",
            "if($Hours -ne 28)",
            "if(-not $Execute)",
            "New-ScheduledTaskTrigger -Once",
            "-RepetitionInterval (New-TimeSpan -Minutes 5)",
            "-RepetitionDuration (New-TimeSpan -Hours 28)",
            "-MultipleInstances IgnoreNew",
            "-User 'SYSTEM'",
            "model_http_calls_authorized=0",
            "max_original_canary_candidates=2",
            "v2r4_unchanged=$true",
            "if(Get-ScheduledTask -TaskName $taskName",
            "pinned_file_hashes",
            "[System.IO.FileMode]::CreateNew",
            "if($oldApps.Count -ne 1)",
        ):
            with self.subTest(required=required):
                self.assertIn(required,install)
        for forbidden in ("Start-ScheduledTask", "Remove-ScheduledTask",
                          "Stop-ScheduledTask","Invoke-RestMethod",
                          "OPENAI_API_KEY","-ForceRecovery"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,install)

    def test_single_task_mutex_no_retries_and_no_live_paper_transition(self):
        run=RUN.read_text("utf-8")
        for required in (
            "Global\\CryptoMiniPC_V3Canary28hOnce",
            "WaitOne(0)",
            "if($plan.kind -ne 'V3_LOCAL_READONLY_CANARY_28H_PLAN_V1'",
            "$plan.model_http_calls_authorized -ne 0",
            "$expires -le $now",
            "pinned_file_hashes",
            "Get-FileHash -LiteralPath $file -Algorithm SHA256",
            "-Execute -MaxCandidates 2",
            "v3-canary-observer-28h-heartbeat.json",
            "V3_PAPER_EXISTING_SUPERVISOR_SELECTIVE_TICK_V1",
            "CLOSED_KRAKEN_1M_SNAPSHOT_SAVED",
            "V3_RECEIPTS_CLOUD_ACK_VERIFIED",
            "NO_UNSYNCED_V3_RECEIPTS",
            "HEALTHY_NO_NEW_CLOUD_EVENTS",
            "HEALTHY_CLOUD_ACK",
            "model_attempts -ne 0",
            "new_schedules -ne 0",
        ):
            with self.subTest(required=required):
                self.assertIn(required,run)
        for forbidden in ("Start-ScheduledTask","Register-ScheduledTask",
                          "Stop-ScheduledTask","OPENAI_API_KEY",
                          "api.openai.com","OpenAI", "paper_series",
                          "v3_paper_active=$true"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,run)

    def test_repair_is_single_pinned_file_migration_not_reinstall_or_extension(self):
        repair=(ROOT/"tools"/"repair-minipc-v3-observer-28h-health-signal.ps1").read_text("utf-8")
        for required in (
            "if(-not $Execute)", "Get-ScheduledTask -TaskName $taskName",
            "$heartbeat.status -ne 'ERROR'",
            "No complete cloud ACK / observer completion marker",
            "NO_UNSYNCED_V3_RECEIPTS",
            "pinned_file_hashes",
            "$relative -ne $targetRelative",
            "Another protected program changed: NO AUTOMATIC REPIN",
            "RUN_V3_CANARY_READONLY_28H",
            "[System.IO.FileMode]::CreateNew",
            "unchanged_expires_at_utc=$manifest.until_utc",
            "duration_extended=$false",
            "Start-ScheduledTask -TaskName $taskName",
        ):
            with self.subTest(required=required):
                self.assertIn(required,repair)
        for forbidden in (
            "Register-ScheduledTask", "Unregister-ScheduledTask",
            "Stop-ScheduledTask", "New-ScheduledTaskTrigger",
            "model_http_calls_authorized=1",
            "Invoke-RestMethod", "OPENAI_API_KEY"
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,repair)

if __name__=="__main__":unittest.main()
