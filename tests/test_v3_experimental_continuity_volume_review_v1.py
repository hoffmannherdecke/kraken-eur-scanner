"""V3 Standard vs Experimental CONTINUITY: one-change early-volume preview only.

No model calls; a "valid" mock BUY is only contract evidence, not P&L.
"""
import copy
import unittest
from pathlib import Path

from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
    propose_experimental_continuity_review as experiment,
    ELIGIBLE as EXP_ELIGIBLE, EXPERIMENTAL_FLOOR,
)
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    propose_continuity_fresh_review as standard,
    ELIGIBLE as STANDARD_ELIGIBLE,
)
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v3_continuity_fresh_review_candidate_v1 import fixture, dt
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as full_fixture


def scenario(ratio=1.1):
    xs=list(fixture())
    xs[2]["frames"]["5"]["volume_ratio_prior_5"]=ratio
    return xs


def compare(ratio=1.1, mutate=None):
    xs=scenario(ratio)
    if mutate:
        mutate(xs)
    frozen=copy.deepcopy(xs)
    a=standard(*xs,decision_at_utc=dt(13))
    b=experiment(*xs,decision_at_utc=dt(13))
    if xs != frozen:
        raise AssertionError("Preview modified shared input")
    return a,b,xs


class V3ExperimentalOneChangeTests(unittest.TestCase):
    def test_only_unchanged_standard_volume_floor_separates_matched_arms(self):
        a,b,_=compare(1.1)
        self.assertEqual(a["status"],"CONTINUITY_EARLY_CONFIRMATION_NOT_PROVEN")
        self.assertEqual(b["status"],EXP_ELIGIBLE)
        self.assertFalse(a["request_model_recheck_only"])
        self.assertTrue(b["request_model_recheck_only"])
        self.assertFalse(b["standard_review_permission"])
        self.assertEqual(b["standard_review_status"],a["status"])
        checks=b["standard_unmodified_checks"]
        self.assertEqual(checks,a["checks"])
        self.assertEqual([k for k,v in checks.items() if v is False],
                         ["unchanged_closed_5m_volume_floor"])
        self.assertEqual(b["standard_volume_floor"],1.2)
        self.assertEqual(EXPERIMENTAL_FLOOR,1.0)
        self.assertTrue(b["same_clock_baseline"])
        self.assertIn("|EXP_VOLUME_1_0",b["snapshot_recheck_key"])
        for k in ("approval_to_call_model","model_called","paper_trade",
                  "orders","real_money_actions","paper_state_changed",
                  "paper_writer_started","active_v2r4_changed",
                  "automatic_live_activation","economic_edge_proven",
                  "release_evidence"):
            self.assertIs(b[k],False,k)

    def test_standard_is_unmodified_and_not_charged_twice(self):
        a,b,_=compare(1.2)
        self.assertEqual(a["status"],STANDARD_ELIGIBLE)
        self.assertEqual(b["status"],"BASELINE_ALREADY_ELIGIBLE_NOT_INCREMENTAL")
        self.assertFalse(b["request_model_recheck_only"])
        self.assertFalse(b["model_called"])

    def test_less_than_1x_zero_missing_and_nan_do_not_relax(self):
        for v in (0.0,0.5,0.999):
            a,b,_=compare(v)
            self.assertFalse(b["request_model_recheck_only"])
            self.assertNotEqual(b["status"],EXP_ELIGIBLE)
        for v in (None,float("nan"),-1):
            _,b,_=compare(v)
            self.assertFalse(b["request_model_recheck_only"])
            self.assertFalse(b["orders"])

    def test_any_other_failed_standard_hard_gate_blocks_experiment(self):
        def spread(xs):xs[3]["bid"]=xs[3]["ask"]*.99
        def no_reclaim(xs):
            xs[4][-1]["close"]=10.1
            xs[2]["frames"]["15"]["closed_close_eur"]=10.1
        def ticker_old(xs):xs[3]["observed_at_utc"]=dt(-500)
        def stale_pit(xs):xs[2]["known_at_utc"]=dt(60)
        def wrong_pair(xs):xs[2]["pair"]="OTHER/EUR"
        def other_lane(xs):xs[1]["setup_lane"]="EXTENDED"
        for mutate in (spread,no_reclaim,ticker_old,stale_pit,wrong_pair,other_lane):
            _,b,_=compare(1.1,mutate)
            self.assertFalse(b["request_model_recheck_only"])
            self.assertNotEqual(b["status"],EXP_ELIGIBLE)
            self.assertFalse(b["orders"])

    def test_same_shared_p4_full_decision_contract_needs_independent_assessment(self):
        _,b,_=compare(1.1)
        payload=list(full_fixture())
        payload[0]=b
        payload[1]["candidate_id"]=b["source_candidate_id"]
        payload[5]["candidate_id"]=b["source_candidate_id"]
        payload[5]["decision_at_utc"]=dt(13)
        payload[2]["frames"]["5"]["volume_ratio_prior_5"]=1.1
        no_full=validate_full_entry_decision(*payload[:-1],None,
                                             decision_at_utc=dt(13),
                                             slippage_pct_each_side=.08)
        self.assertEqual(no_full["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")
        self.assertFalse(no_full["model_called"])
        # A mock illustrates the contract ONLY, not actual Alpha/BUY/paper fill.
        mock=validate_full_entry_decision(*payload,
                                          decision_at_utc=dt(13),
                                          slippage_pct_each_side=.08)
        self.assertEqual(mock["status"],"FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
        self.assertGreater(mock["total_round_trip_cost_pct"],1.2)
        self.assertFalse(mock["economic_edge_proven"])
        self.assertFalse(mock["orders"])
        self.assertFalse(mock["paper_writer_started"])
        self.assertLess(mock["stop_eur"],mock["execution_ask_eur"])
        self.assertGreater(mock["stage2_trigger_eur"],mock["execution_ask_eur"])

    def test_experiment_cannot_forge_volume_other_checks_or_full_assessment(self):
        _,base,_=compare(1.1)
        payload=list(full_fixture())
        payload[0]=base
        payload[1]["candidate_id"]=base["source_candidate_id"]
        payload[5]["candidate_id"]=base["source_candidate_id"]
        payload[5]["decision_at_utc"]=dt(13)
        payload[2]["frames"]["5"]["volume_ratio_prior_5"]=1.1
        for change in (
            lambda x:x[0].update(kind="UNREGISTERED"),
            lambda x:x[0].update(standard_review_status="CONTINUITY_ELIGIBLE"),
            lambda x:x[0].update(old_standard_volume_check_failed=False),
            lambda x:x[0]["standard_unmodified_checks"].update(fresh_eur_spread_guard=False),
            lambda x:x[0].update(new_snapshot_known_at_utc=dt(30)),
            lambda x:x[0].update(fresh_close_at_utc=dt(30)),
            lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=0.6),
            lambda x:x[5].update(stop_eur=10.35),
            lambda x:x[5].update(expected_remaining_move_pct=.2),
        ):
            candidate=copy.deepcopy(payload)
            change(candidate)
            r=validate_full_entry_decision(*candidate,decision_at_utc=dt(13),
                                           slippage_pct_each_side=.08)
            self.assertNotEqual(r["decision"],"BUY_SCOUT")

    def test_no_active_v2r4_module_imports_experimental_preview(self):
        repo=Path(__file__).resolve().parents[1]
        for path in ("paper_evaluator/evaluate.py",
                     "paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py",
                     "tools/v2r4-paper-local-runtime.py"):
            content=(repo/path).read_text("utf-8")
            self.assertNotIn("v3_experimental_continuity_volume_review_v1",content)


if __name__=="__main__":
    unittest.main()
