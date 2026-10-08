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
    def test_no_new_cron(self):
        contract=(ROOT/"docs/project-wide-outage-recovery-v1.md").read_text("utf-8")
        self.assertIn("keine neuen",contract.lower())
if __name__=="__main__":unittest.main()
