"""Single-writer release intent: no V3 success claim without successor evidence and physical ACK."""
import copy
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tools.strategy_successor_gate import ROOT, validate_learning_gate

STATE_FILE = ROOT / "project-current-state.json"
VALIDATOR = ROOT / "tools/validate-project-current-state.py"


def run_validator(state):
    tool_dir = str(ROOT / "tools")
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)
    spec = importlib.util.spec_from_file_location("v3_transition_state_validator", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    orig = module.load
    module.load = lambda path: copy.deepcopy(state) if path == STATE_FILE else orig(path)
    with redirect_stdout(io.StringIO()) as out:
        result = module.main()
    return result, json.loads(out.getvalue())


class V3TransitionContractTests(TestCase):
    def setUp(self):
        self.base = json.loads(STATE_FILE.read_text(encoding="utf-8"))

    def test_user_v3_goal_does_not_modify_current_v2r4_paper(self):
        t = self.base["pending_strategy_transition"]
        self.assertEqual(t["status"], "BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING")
        self.assertFalse(t["safety"]["real_money_actions"])
        self.assertTrue(t["safety"]["v2r4_runtime_still_active_until_physical_ack"])
        self.assertTrue(t["last_observed_supabase_read_only"]["snapshot_not_current_runtime_truth"])
        self.assertIn("V2R4", self.base["active_strategy"]["strategy_revision"])
        self.assertEqual(t["last_observed_supabase_read_only"]["active_series_count"], 1)
        self.assertEqual(t["last_observed_supabase_read_only"]["v2r4_completed_paper_trades"], 0)
        self.assertEqual(t["sequence"][-1]["status"], "BLOCKED")
        self.assertEqual(validate_learning_gate(ROOT, "V3-PAPER-20261011") != [], True)

    def test_valid_declared_cutover_intent_passes_existing_release_controls(self):
        exit_code, out = run_validator(self.base)
        self.assertEqual(exit_code, 0, out["errors"])

    def test_wrong_early_v3_runtime_label_fails(self):
        j = copy.deepcopy(self.base)
        j["active_strategy"]["strategy_revision"] = "V3-PAPER-20261011"
        exit_code, out = run_validator(j)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(any("NEW_STRATEGY_BLOCKED" in s for s in out["errors"]))
        self.assertTrue(any("before release/physical ACK" in s for s in out["errors"]))

    def test_phantom_v3_active_ack_fails(self):
        j = copy.deepcopy(self.base)
        j["pending_strategy_transition"]["status"] = "V3_PAPER_ACTIVE_VERIFIED"
        exit_code, out = run_validator(j)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(any("real physical/cloud ACK" in s for s in out["errors"]))

    def test_cannot_lose_historical_followups_or_disable_risk_controls(self):
        for flag in ("holdovers_followups_and_existing_paper_ledger_preserved",
                     "v3_release_requires_complete_prospective_evidence",
                     "h3_h6_remain_inactive"):
            j = copy.deepcopy(self.base)
            j["pending_strategy_transition"]["safety"][flag] = False
            exit_code, out = run_validator(j)
            self.assertNotEqual(exit_code, 0)
            self.assertTrue(any(flag in x for x in out["errors"]))

    def test_v3_cas_recovery_is_never_an_automatic_retry_or_rollback(self):
        from tools.paper_series_transition_guard import assess_v3_cutover_recovery as check
        old="PAPER-V2R4-20261009T110135Z"
        new="PAPER-V3-EXPERIMENTAL-20261013"
        oldrows=[{"series_id":old,"status":"active"}]
        newrows=[{"series_id":new,"status":"active"}]
        scenarios=[
            ("CLOUD_COMMIT_NOT_ATTEMPTED",oldrows,{},
             "PRECOMMIT_DRYRUN_ONLY_NO_CLOUD_MUTATION"),
            ("CLOUD_REJECTED_BEFORE_COMMIT",oldrows,{},
             "PRECOMMIT_RESTORE_REQUIRES_ORIGINAL_TASK_ACK"),
            ("CLOUD_COMMIT_OUTCOME_UNKNOWN",oldrows,{},
             "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"),
            ("CLOUD_COMMIT_OUTCOME_UNKNOWN",[],{},
             "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"),
            ("CLOUD_COMMIT_OUTCOME_UNKNOWN",oldrows+newrows,{},
             "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"),
            ("CLOUD_COMMIT_OUTCOME_UNKNOWN",None,{},
             "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"),
            ("CLOUD_COMMIT_OUTCOME_UNKNOWN",newrows,{},
             "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"),
            ("CLOUD_COMMITTED",oldrows,{},
             "POSTCOMMIT_CLOUD_MISMATCH_QUARANTINE"),
            ("CLOUD_COMMITTED",newrows,{},
             "POSTCOMMIT_OLD_WRITER_FENCE_UNVERIFIED"),
            ("CLOUD_COMMITTED",newrows,{
                "old_writer_fenced":True,"old_followups_preserved":True,
                "supervisor_old_intake_rearm_blocked":True},
             "POSTCOMMIT_KEEP_OLD_FENCED_STOP_NEW_FOR_REVIEW"),
            ("CLOUD_COMMITTED",newrows,{
                "old_writer_fenced":True,"old_followups_preserved":True,
                "supervisor_old_intake_rearm_blocked":True,
                "successor_writer_healthy":True},
             "POSTCOMMIT_SOURCE_ACK_STILL_REQUIRED"),
            ("CLOUD_COMMITTED",oldrows+[{"series_id":new,"status":"active"}],{},
             "BLOCKED_UNVERIFIED_CUTOVER_SNAPSHOT"),
        ]
        for phase,rows,flags,expected in scenarios:
            with self.subTest(phase=phase,expected=expected):
                verdict=check(phase=phase,active_series=rows,
                    expected_old=old,proposed_new=new,**flags)
                self.assertEqual(verdict["disposition"],expected)
                self.assertFalse(verdict["auto_restart_predecessor"])
                self.assertFalse(verdict["auto_start_successor"])
                self.assertFalse(verdict["auto_retry_cloud_cas"])
                self.assertFalse(verdict["mutation_authorized"])
                self.assertTrue(verdict["independent_current_host_cloud_ack_required"])

    def test_no_silent_extra_works_or_duplicate_shadow(self):
        j = copy.deepcopy(self.base)
        j["pending_strategy_transition"]["safety"]["max_strategy_changing_shadows"] = 2
        exit_code, out = run_validator(j)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(any("concurrent shadows" in x for x in out["errors"]))
