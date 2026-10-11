"""No-trade V3-A historical learning decision is a CLOSED diagnosis, not P&L."""
import copy
import json
import unittest
from pathlib import Path

from paper_evaluator.v3_a_historical_learning_closure_v1 import classify

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"research/v3/v3-a-retro-12-case-matched-no-buy-20261010.json"


def panel():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


class V3AHistoricalLearningClosureTests(unittest.TestCase):
    def test_original_twelve_case_decision_is_closed_without_inventing_trades(self):
        m=panel()
        before=copy.deepcopy(m)
        d=classify(m)
        self.assertEqual(m,before)
        self.assertEqual(d["sample_size"],12)
        self.assertEqual(d["favorable_selected"],6)
        self.assertEqual(d["adverse_controls"],6)
        self.assertEqual(d["historical_coin_PIT_v3_replay_eligible"],0)
        self.assertEqual(d["verified_economic_buy_paths"],0)
        self.assertIsNone(d["net_pnl_sum_eur"])
        self.assertFalse(d["net_expected_value_proven"])
        self.assertTrue(d["retrospective_outcomes_are_only_labels"])
        self.assertEqual(d["fee_pct_per_side"],0.6)
        self.assertEqual(d["status"],
                         "HISTORICAL_DIAGNOSTIC_LEARNING_CLOSED_ECONOMIC_RELEASE_NOT_PROVEN")
        self.assertEqual(d["model_calls"],0)
        self.assertFalse(d["shadow_started"])
        self.assertFalse(d["paper_writer_started"])
        self.assertFalse(d["v2r4_changed"])
        self.assertFalse(d["orders"])
        self.assertFalse(d["real_money_actions"])
        self.assertFalse(d["learning_decision"]["strategy_rule_cutover_authorized"])
        self.assertFalse(d["learning_decision"]["model_budget_authorized_by_this_decision"])
        self.assertEqual(len(d["cases"]),12)
        self.assertEqual(len(set(c["candidate_id"] for c in d["cases"])),12)
        self.assertEqual({c["pair"] for c in d["cases"]},
                         {"STRK/EUR","OP/EUR","BAT/EUR","W/EUR","JUP/EUR","DRV/EUR",
                          "WLD/EUR","GRT/EUR","ORCA/EUR","ALGO/EUR","ADA/EUR","SYN/EUR"})
        for c in d["cases"]:
            self.assertFalse(c["valid_historical_v3_replay"])
            self.assertFalse(c["source_model_context_closed_coin_PIT_proven"])
            self.assertIsNone(c["realized_net_pnl_eur"])
            self.assertIn("ORDER_FILL_STOP_FIRST_6H24H_PATH_NET",c["missing_evidence"])

    def test_frozen_case_selection_and_future_label_leakage_not_allowed(self):
        mutations=[
            lambda m:m.update(status="MODEL_REPLAY_COMPLETE"),
            lambda m:m["cases"].pop(),
            lambda m:m["cases"][0].update(pair="ETH/EUR"),
            lambda m:m["cases"][0].update(candidate_id=m["cases"][1]["candidate_id"]),
            lambda m:m["cases"][0].update(initial_decision="BUY_SCOUT"),
            lambda m:m["cases"][0].update(final_decision="BUY_SCOUT"),
            lambda m:m["cases"][0].update(validated_v3_buy=True),
            lambda m:m["cases"][0].update(at_time_closed_coin_1m_5m_15m_complete_evidence="COMPLETE"),
            lambda m:m["cases"][0].update(at_time_h10_5m_records_in_prior_3h=10),
            lambda m:m["cases"][0].update(mfe24_pct=float("nan")),
            lambda m:m["cases"][0].update(mae24_pct=80),
            lambda m:m["cases"][0].update(initial_spread_pct=-1),
            lambda m:m["cases"][0].update(outcome_stratum="OPPORTUNITY") if
                m["cases"][0]["outcome_stratum"]=="ADVERSE_CONTROL" else
                m["cases"][0].update(outcome_stratum="ADVERSE_CONTROL"),
            lambda m:m["point_in_time_source_inventory"].update(
                coin_specific_1m_5m_15m_ohlc_volume_atr="CLAIMED_PRESENT"),
        ]
        for mutate in mutations:
            m=panel();mutate(m)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                classify(m)

    def test_no_active_consumer_imports_historical_future_labels(self):
        for name in ("paper_evaluator/evaluate.py",
                     "paper_evaluator/v3_p3_ab_five_bounded_research.py",
                     "paper_evaluator/v3_full_entry_decision_candidate_v1.py",
                     "paper_evaluator/v2r4_local_recheck.py"):
            s=(ROOT/name).read_text("utf-8")
            self.assertNotIn("v3_a_historical_learning_closure_v1",s)

if __name__=="__main__":
    unittest.main()
