"""One-shot read-only CLI: usable from existing Work/controller, no new jobs."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tests.test_v3_paper_post_canary_evidence_verdict_v1 import watch, smoke
from paper_evaluator.v3_paper_post_canary_evidence_verdict_v1 import ORIGINAL_ACTIVE,SMOKE,WATCH

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/v3-post-canary-evidence-readonly-report.py"

def envelope(**changes):
    x={
       "kind":"V3_READONLY_SUPABASE_RECEIPTS_FOR_VERDICT_V1",
       "mode":"READ_ONLY_NO_ACTIVATION",
       "cloud_source_verified_by_caller":True,
       "new_model_budget":False,
       "as_of_utc":"2026-10-12T10:53:00Z",
       "active_paper_series":[ORIGINAL_ACTIVE],
       "physical_observer_end_ack":False,
       "cloud_rows":watch()+smoke()
    }
    x.update(changes)
    return x

def run(doc):
    return subprocess.run(
        [sys.executable,str(SCRIPT)],cwd=ROOT,
        input=json.dumps(doc).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        timeout=10)

class V3ReadOnlyReportTests(unittest.TestCase):
    def test_render_smoke_separate_watch_and_true_not_due(self):
        result=run(envelope())
        self.assertEqual(result.returncode,0,result.stderr.decode())
        report=json.loads(result.stdout)
        self.assertTrue(report["separate_series"][SMOKE]["one_shot_real_p0_proof"])
        self.assertEqual(report["separate_series"][WATCH]["unique_real_originals"],1)
        self.assertEqual(report["watcher_followup_coverage"]["6"]["not_yet_due"],1)
        self.assertEqual(report["watcher_next_unmatured_horizon"]["hours"],6)
        self.assertEqual(report["release"].startswith("BLOCKED"),True)
        self.assertFalse(report["automatic_model_api_authorized"])
        self.assertFalse(report["strategy_v3_auto_activation_authorized"])
        self.assertTrue(report["cli_does_not_contact_supabase"])
        self.assertEqual(report["new_schedules"],0)

    def test_fail_closed_on_missing_source_provenance_or_model_budget(self):
        for change in (
            {"cloud_source_verified_by_caller":False},
            {"new_model_budget":True},
            {"mode":"RUN_PAPER"},
            {"kind":"FAKE"},
            {"active_paper_series":None},
            {"cloud_rows":None},
            {"as_of_utc":"2025-10-12T10:53:00Z"}
        ):
            with self.subTest(change=change):
                process=run(envelope(**change))
                self.assertNotEqual(process.returncode,0)
                self.assertFalse(process.stdout.strip())

    def test_after_deadline_is_not_physical_stop_or_trade_permission(self):
        process=run(envelope(as_of_utc="2026-10-13T12:01:00Z"))
        self.assertEqual(process.returncode,0,process.stderr.decode())
        output=json.loads(process.stdout)
        self.assertEqual(output["observation_window"],
                         "ENDED_TIME_ONLY_PHYSICAL_STOP_NOT_VERIFIED")
        self.assertIn("BLOCKED",output["release"])
        self.assertEqual(output["watcher_followup_coverage"]["24"]["due_missing_or_pending"],1)
        self.assertFalse(output["strategy_v3_auto_activation_authorized"])

if __name__=="__main__":
    unittest.main()
