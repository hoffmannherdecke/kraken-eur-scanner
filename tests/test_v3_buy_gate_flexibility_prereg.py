"""Guard the cross-version no-BUY findings against accidental live-rule promotion.

The registered variants are hypotheses, not new Paper/BUY/Model permissions.
"""
import json
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"research/v3/v3-buy-gate-flexibility-prereg-20261011.json"


class V3RuleFlexibilityResearchGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e=json.loads(DATA.read_text("utf-8"))

    def test_frozen_original_cohort_arithmetic_and_distinct_maturity_denominators(self):
        b=self.e["baseline_snapshot"]
        self.assertEqual(b["unique_candidate_rows"],1864)
        self.assertEqual(b["initial_wait"]+b["initial_reject"],1864)
        self.assertEqual(b["wait_ttl_expiry"]+b["true_trigger_rechecks"]
                         +b["pending_or_other_initial_wait"],b["initial_wait"])
        self.assertGreater(b["fully_mature_24h"],0)
        self.assertLess(b["fully_mature_24h"],b["unique_candidate_rows"])
        self.assertEqual(b["initial_buy"],0)
        self.assertEqual(b["final_buy"],0)
        self.assertEqual(b["valid_trade_fills"],0)
        self.assertLess(b["trigger_mature_n"],b["true_trigger_rechecks"])
        self.assertLess(b["expired_mature_n"],b["wait_ttl_expiry"])
        self.assertTrue(b["disclaimer"])

    def test_single_sequential_inactive_one_change_variants(self):
        e=self.e
        self.assertEqual(e["status"],
                         "PRE_REGISTERED_INACTIVE_RESEARCH_ONLY_NO_STRATEGY_OR_PAPER_CHANGE")
        self.assertTrue(e["no_activation"])
        self.assertTrue(e["no_buy_authority"])
        self.assertTrue(e["no_new_automation"])
        vs=e["variants"]
        self.assertEqual([x["priority"] for x in vs],[1,2,3])
        self.assertEqual(len(set(x["changes_only"] for x in vs)),3)
        self.assertEqual(vs[0]["id"],"P2_WAIT_FRESH_REVIEW_ONLY_V1")
        self.assertTrue(vs[0]["original_v2r4_wait_expiry_remains_recorded"])
        self.assertTrue(vs[0]["success_not_implied_by_more_reviews"])
        self.assertIn("BUY",vs[1]["rule"])
        self.assertEqual(vs[2]["status"],"DEFERRED_NO_AUTOMATIC_THIRD_SHADOW")

    def test_all_true_core_hard_gates_and_safe_approval_boundary(self):
        e=self.e
        flags=e["nonnegotiable_guards"]
        for key in ["kraken_online_spot_eur_only","fees_plus_spread_slippage_costs",
                    "valid_stop_below_fresh_ask","stage2_above_fresh_ask",
                    "liquidity_and_minimums","missing_required_PIT_fail_closed",
                    "no_score_only_buy","no_new_v3_paper_writer",
                    "no_real_money","no_live_v2r4_change",
                    "no_new_shadow_or_model_budget","no_extra_jobs"]:
            self.assertIs(flags[key],True,key)
        self.assertEqual(flags["taker_fee_each_side_pct"],.6)
        self.assertEqual((flags["scout_eur"],flags["stage2_eur"]),(50,50))
        self.assertIn("REQUIRE_SEPARATE_GATES",e["approval_boundary"])
        self.assertGreaterEqual(len(e["causal_evidence_needed"]),6)
        self.assertTrue((ROOT/e["primary_evidence"]).is_file())
        self.assertTrue((ROOT/e["prior_independent_source"]).is_file())

    def test_new_knowledge_routes_back_to_single_strategy_scope(self):
        routing=json.loads((ROOT/"research/context-before-action-routing-v1.json").read_text("utf-8"))
        for scope in ("strategy","research"):
            p=[s["path"] for s in routing["scopes"][scope]]
            self.assertIn("research/v3/v3-buy-gate-flexibility-prereg-20261011.json",p)
        b=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn("P2 → P3 / V3 wirtschaftliche BUY-Konversion",b)
        self.assertIn("P2_WAIT_FRESH_REVIEW_ONLY_V1",b)


if __name__=="__main__":
    unittest.main()
