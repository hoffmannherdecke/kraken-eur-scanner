"""REGRESSION: EXTENDED reentry overlay is only a bounded fresh model-review hint."""
import copy
import unittest
from pathlib import Path

from paper_evaluator.v3_extended_reentry_review_v1 import extended_reentry_review
from tests.test_v2r4_v3_entry_handoff_probe import evidence,dt


def case():
    e = evidence()
    assert e["status"]=="COMPLETE"
    e["frames"]["5"]["closed_close_eur"]=10.40
    e["frames"]["15"]["closed_close_eur"]=10.30
    e["frames"]["5"]["volume_ratio_prior_5"]=1.4
    e["frames"]["15"]["atr14_eur"]=0.22
    e["frames"]["15"]["recent_8bar_low_eur"]=10.0
    return e


def run(e=None,original=None,ticker=None,at=None,candidate=None):
    c=candidate if candidate is not None else {"pair":"XBT/EUR","event_time_utc":dt(0),"candidate_id":"FROZEN"}
    d=original if original is not None else {"decision":"REJECT","setup_lane":"EXTENDED","reason_codes":["LATE_CHASE"]}
    t=ticker if ticker is not None else {"ask":10.40,"bid":10.39}
    return extended_reentry_review(c,d,e if e is not None else case(),t,decision_at_utc=at or dt(13))


class ExtendedReentryReviewContract(unittest.TestCase):
    def test_positive_structure_volume_only_proposes_model_review_not_buy(self):
        source=case()
        untouched=copy.deepcopy(source)
        result=run(source)
        self.assertEqual(result["state"],"STRUCTURE_AND_VOLUME_SUPPORT_FRESH_REVIEW_NOT_BUY")
        self.assertTrue(result["request_model_recheck_only"])
        self.assertGreater(result["stop_distance_pct_descriptive_only"],0)
        self.assertGreater(result["conservative_minimum_cost_hurdle_pct_excluding_slippage"],1.2)
        for key in ("paper_trade","orders","real_money_actions","automatic_promotion",
                    "independent_trade_signal","duplicates_h6_volume_vote",
                    "creates_h4_stop_policy","changes_existing_v2r4_wait"):
            self.assertIs(result[key],False,key)
        self.assertEqual(result["decision"],"NO_DECISION_AUTHORITY")
        self.assertEqual(source,untouched)

    def test_missing_volume_confirmation_does_not_trigger_model_review(self):
        e=case();e["frames"]["5"]["volume_ratio_prior_5"]=1.1
        res=run(e)
        self.assertEqual(res["state"],"PROSPECTIVE_CONFIRMATION_INCOMPLETE")
        self.assertFalse(res["checks"]["closed_5m_volume_ratio_at_least_existing_v2r4_1_2"])
        self.assertFalse(res["request_model_recheck_only"])

    def test_below_reference_price_does_not_trigger_model_review(self):
        e=case();e["frames"]["5"]["closed_close_eur"]=9.9
        res=run(e)
        self.assertEqual(res["state"],"PROSPECTIVE_CONFIRMATION_INCOMPLETE")

    def test_foreign_lane_and_buy_do_not_create_duplicate_signal(self):
        self.assertEqual(run(original={"decision":"REJECT","setup_lane":"REVERSAL"})["state"],
                         "OUT_OF_SCOPE_EXISTING_LANE_RETAINED")
        self.assertEqual(run(original={"decision":"BUY_SCOUT","setup_lane":"EXTENDED"})["state"],
                         "OUT_OF_SCOPE_NOT_A_MISSED_EXTENDED_ENTRY")

    def test_missing_stale_future_and_wrong_pair_fail_closed(self):
        e=case();e["status"]="PARTIAL_OR_MISSING"
        self.assertEqual(run(e)["state"],"UNKNOWN_INSUFFICIENT_PROSPECTIVE_EVIDENCE")
        self.assertEqual(run(at=dt(1050))["state"],"UNKNOWN_STALE_OR_FUTURE_CANDIDATE")
        self.assertEqual(run(at=dt(1))["state"],"UNKNOWN_INSUFFICIENT_PROSPECTIVE_EVIDENCE")
        self.assertEqual(run(candidate={"pair":"W/EUR","event_time_utc":dt(0)})["state"],
                         "UNKNOWN_INSUFFICIENT_PROSPECTIVE_EVIDENCE")

    def test_no_structural_stop_reference_is_not_tradeable(self):
        e=case();e["frames"]["15"]["recent_8bar_low_eur"]=13.
        e["frames"]["15"]["closed_close_eur"]=12.0
        e["frames"]["15"]["atr14_eur"]=.3
        self.assertEqual(run(e)["state"],"STRUCTURAL_REFERENCE_NOT_VALID")

    def test_wide_spread_is_not_exempt_from_cost_checks(self):
        r=run(ticker={"ask":10.45,"bid":10.25})
        self.assertEqual(r["state"],"PROSPECTIVE_CONFIRMATION_INCOMPLETE")
        self.assertFalse(r["checks"]["spread_at_most_half_percent"])

    def test_active_v2r4_decision_consumer_never_imports_research_overlay(self):
        root=Path(__file__).resolve().parents[1]
        for p in ("paper_evaluator/evaluate.py","paper_evaluator/v2r4_local_recheck.py",
                  "paper_evaluator/v2r4_wait_runtime.py","tools/v2r4-paper-local-runtime.py"):
            content=(root/p).read_text("utf-8")
            self.assertNotIn("v3_extended_reentry_review_v1",content)

if __name__=="__main__":
    unittest.main()
