import copy
import importlib.util
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
v=load("tools/validate-outage-resilience.py","validate_outage")

DOC=json.loads((ROOT/"research/global-outage-recovery-contract-v1.json").read_text("utf-8"))

class OutageResilienceTests(unittest.TestCase):
    def test_contract_protects_all_domains(self):
        self.assertEqual(v.validate(DOC),[])
        self.assertEqual(len(DOC["domains"]),17)
    def test_optional_feed_cannot_create_buy_veto(self):
        bad=copy.deepcopy(DOC)
        bad["missing_optional_inputs_can_reject_buy"]=True
        self.assertTrue(v.validate(bad))
    def test_cannot_fake_backfill(self):
        bad=copy.deepcopy(DOC)
        bad["failed_backfill_can_count_as_complete"]=True
        self.assertTrue(v.validate(bad))
    def test_unknown_provider_not_silently_unowned(self):
        bad=copy.deepcopy(DOC)
        bad["domains"]=bad["domains"][:-1]
        self.assertTrue(v.validate(bad))
    def test_supervisor_remembers_unverified_attempt(self):
        source=(ROOT/"tools/minipc-runtime-supervisor.ps1").read_text("utf-8")
        self.assertIn("last_attempt_at_utc",source)
        self.assertIn("consecutive_failures",source)
        self.assertIn("WAIT_FOR_UPSTREAM",source)
        self.assertIn("restart_attempt_history_persisted",source)
        self.assertIn("RESTART_UNVERIFIED",source)
        self.assertIn("restart_history_records_verified_recovery_only",source)
        self.assertIn("3600",source)
        self.assertIn("Stop-ScheduledTask",source)
        self.assertIn("Wait-TaskNotRunning",source)
    def test_current_paper_gap_is_registered_for_controlled_gate(self):
        text=(ROOT/"docs/project-wide-outage-recovery-v1.md").read_text("utf-8")
        self.assertIn("NOT_YET_DEPLOYED",text)
        self.assertIn("Prospective",text)
    def test_native_task_last_result_readback_is_observational_and_whitelisted(self):
        src=(ROOT/"tools/minipc-watchdog.ps1").read_text("utf-8")
        function=src.split("function Add-NativeTaskReadback {",1)[1].split(
            "# Disk: warn below 20 GB",1)[0]
        self.assertIn("Get-ScheduledTaskInfo -TaskName",function)
        self.assertIn("267009",function)  # Windows 0x41301 = running, not failure
        self.assertIn("RUNNING_CODE_AND_STATE_MATCH",function)
        self.assertIn("RUNNING_CODE_STATE_MISMATCH",function)
        self.assertIn("ZERO_RESULT_NOT_RUNTIME_PROOF",function)
        self.assertIn("OTHER_RESULT_REVIEW_REQUIRED",function)
        self.assertIn("UNAVAILABLE",function)
        self.assertNotIn("Start-ScheduledTask",function)
        self.assertNotIn("Stop-ScheduledTask",function)
        self.assertNotIn("Register-ScheduledTask",function)
        self.assertNotIn("Get-ScheduledTaskAction",function)
        self.assertNotIn("Get-FileHash",function)
        for key in (
            "v2r4_paper_candidates", "v2r4_paper_wait",
            "v2r4_paper_lifecycle", "v2r4_paper_cloud_sync",
        ):
            self.assertIn('check="'+key+'"',src)
        self.assertIn('Add-NativeTaskReadback -Key $spec.check -Task $task',src)
        for key in ("minipc_status_sync", "v3_canary_observation_28h"):
            self.assertIn('Add-NativeTaskReadback -Key "'+key+'"',src)
        self.assertIn('native_task_readback = [ordered]@{',src)
        self.assertIn('no_runtime_or_release_authority = $true',src)
        self.assertLess(src.index('native_task_readback = [ordered]@{'),
                        src.index('issues = $issues'))
        self.assertNotIn('task_path =',function)
        self.assertNotIn('task_action =',function)
        self.assertNotIn('arguments =',function)

    def test_native_task_readback_cannot_change_existing_health_decisions(self):
        src=(ROOT/"tools/minipc-watchdog.ps1").read_text("utf-8")
        function=src.split("function Add-NativeTaskReadback {",1)[1].split(
            "# Disk: warn below 20 GB",1)[0]
        for unsafe in ("Add-Check", "$issues.Add", "$status =", "$healthState =",
                       "Start-Process", "Restart-", "Invoke-WebRequest", "Invoke-RestMethod"):
            self.assertNotIn(unsafe,function)
        self.assertIn('Get-ScheduledTaskInfo',function)
        self.assertIn('try {',function)
        self.assertIn('} catch {',function)
        self.assertIn('# Native scheduler metadata is optional',function)
        self.assertIn('native_task_readback = [ordered]@{',src)
        self.assertIn('# V3 Canary 28h is observational only',src)

    def test_no_new_cron(self):
        contract=(ROOT/"docs/project-wide-outage-recovery-v1.md").read_text("utf-8")
        self.assertIn("keine neuen",contract.lower())
if __name__=="__main__":unittest.main()
