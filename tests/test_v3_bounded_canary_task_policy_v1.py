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
            "V3 Paper observation cycle finished; NO MODEL, NO PAPER ACTIVATION, V2R4 unchanged",
        ):
            with self.subTest(required=required):
                self.assertIn(required,run)
        for forbidden in ("Start-ScheduledTask","Register-ScheduledTask",
                          "Stop-ScheduledTask","OPENAI_API_KEY",
                          "api.openai.com","OpenAI", "paper_series",
                          "v3_paper_active=$true"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,run)

if __name__=="__main__":unittest.main()
