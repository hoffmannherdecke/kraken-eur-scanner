"""Single-writer release intent: no V3 success claim without successor evidence and physical ACK."""
import copy
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from tools.strategy_successor_gate import ROOT, validate_learning_gate

STATE_FILE = ROOT / "project-current-state.json"
VALIDATOR = ROOT / "tools/validate-project-current-state.py"


def run_validator(state):
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

    def test_no_silent_extra_works_or_duplicate_shadow(self):
        j = copy.deepcopy(self.base)
        j["pending_strategy_transition"]["safety"]["max_strategy_changing_shadows"] = 2
        exit_code, out = run_validator(j)
        self.assertNotEqual(exit_code, 0)
        self.assertTrue(any("concurrent shadows" in x for x in out["errors"]))
