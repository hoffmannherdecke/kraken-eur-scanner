"""Safety proof that V3 Experimental remains one inactive paper-only hypothesis."""
import json
import unittest
from pathlib import Path
from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
    EXPERIMENTAL_FLOOR,
)
from paper_evaluator.v3_extended_reentry_review_v1 import (
    EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR,
)

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"research/v3/v3-paper-experimental-ab-contract-20261011.json"


class ExperimentalABInvariantTests(unittest.TestCase):
    def test_standard_vs_experimental_only_one_changed_policy_number(self):
        d=json.loads(CONTRACT.read_text("utf-8"))
        self.assertEqual(len(d["arms"]),2)
        self.assertEqual([x["id"] for x in d["arms"]],["STANDARD","EXPERIMENTAL"])
        self.assertEqual(d["arms"][0]["volume_review_floor"],EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR)
        self.assertEqual(d["arms"][1]["volume_review_floor"],EXPERIMENTAL_FLOOR)
        self.assertLess(EXPERIMENTAL_FLOOR,EXISTING_V2R4_VOLUME_RATIO_REVIEW_FLOOR)
        self.assertEqual(EXPERIMENTAL_FLOOR,1.0)
        self.assertEqual(d["arms"][1]["exclusive_band_upper"],1.2)

    def test_technical_and_real_money_gates_are_not_strategy_tunable(self):
        d=json.loads(CONTRACT.read_text("utf-8"))
        self.assertEqual(d["status"],
                         "IMPLEMENTED_OFFLINE_REVIEW_CANDIDATE_NOT_AUTHORIZED_TO_RUN_MODEL_OR_ACTIVATE_PAPER")
        g=d["frozen_shared_guards"]
        for item in ("kraken_online_spot_eur","primary_data_pit_must_pass",
                     "closed_15m_price_breakout","closed_5m_price_continuation",
                     "no_anti_chase_or_price_extension_override",
                     "structural_stop_below_entry_ask",
                     "stage2_above_ask_with_ttl",
                     "taker_each_side_pct"):
            self.assertIn(item,g)
        self.assertEqual(g["taker_each_side_pct"],.6)
        self.assertEqual((g["position_size_scout_eur"],g["position_size_stage2_eur"]),(50,50))
        for key in ("no_real_orders","no_live_paper_writer","no_standalone_shadow_or_cron",
                    "no_change_active_v2r4","model_decision_not_generated_from_eligibility",
                    "positive_net_expected_move_in_full_model",
                    "slippage_and_spread_accounted","h3_h6_remain_inactive"):
            self.assertIs(g[key],True,key)
        self.assertTrue(d["technical_robustness"]["no_http_or_model_calls_in_current_variant"])
        self.assertTrue(d["technical_robustness"]["no_file_or_cloud_writes_from_evaluator"])
        self.assertIn("explicit",d["prospective_measurement_once_separately_approved"]["approval_and_budget"].lower())

    def test_same_one_owner_and_inactive_provenance(self):
        routing=json.loads((ROOT/"research/context-before-action-routing-v1.json").read_text("utf-8"))
        for scope in ("strategy","research"):
            self.assertIn(str(CONTRACT.relative_to(ROOT)), [s["path"] for s in routing["scopes"][scope]])
        b=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn("V3 Experimental",b)
        self.assertIn("PRÜFVARIANTE",b)
        self.assertIn("keine Echtgeldorders",b)
        for file in ("paper_evaluator/evaluate.py",
                     "paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py",
                     "tools/v2r4-paper-local-runtime.py"):
            self.assertNotIn("v3_experimental_continuity_volume_review_v1",
                             (ROOT/file).read_text("utf-8"))


if __name__=="__main__":
    unittest.main()
