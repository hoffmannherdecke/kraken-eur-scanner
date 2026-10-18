"""Regression: eligible EXTENDED reentry must expose a full-review handoff, never a BUY."""
import unittest
from unittest.mock import patch
from paper_evaluator.v3_extended_reentry_review_v1 import extended_reentry_review

class ExtendedReentryHandoffTests(unittest.TestCase):
    def test_eligible_routes_to_full_review_without_trade_authority(self):
        candidate={"candidate_id":"MON-PIT","pair":"MON/EUR","event_time_utc":"2026-10-01T11:20:00Z"}
        original={"setup_lane":"EXTENDED","decision":"REJECT"}
        evidence={"frames":{"5":{"closed_close_eur":10.2,"volume_ratio_prior_5":1.3},
                            "15":{"closed_close_eur":10.0,"atr14_eur":0.3,"recent_8bar_low_eur":9.8}}}
        ticker={"ask":10.21,"bid":10.20}
        with patch("paper_evaluator.v3_extended_reentry_review_v1.attach_to_future_evaluator",return_value={}):
            r=extended_reentry_review(candidate,original,evidence,ticker,decision_at_utc="2026-10-01T11:21:00Z")
        self.assertEqual(r["state"],"STRUCTURE_AND_VOLUME_SUPPORT_FRESH_REVIEW_NOT_BUY")
        self.assertTrue(r["full_model_review_candidate"])
        self.assertEqual(r["next_action"],"REQUEST_SEPARATELY_AUTHORIZED_FULL_V3_MODEL_AND_P4_REVIEW")
        self.assertFalse(r["approval_to_call_model"])
        self.assertFalse(r["paper_trade"])
        self.assertFalse(r["orders"])
        with patch("paper_evaluator.v3_extended_reentry_review_v1.attach_to_future_evaluator",return_value={}):
            evidence["frames"]["5"]["volume_ratio_prior_5"]=1.0
            r=extended_reentry_review(candidate,original,evidence,ticker,decision_at_utc="2026-10-01T11:21:00Z")
        self.assertFalse(r["full_model_review_candidate"])
        self.assertEqual(r["next_action"],"WAIT_FOR_FRESH_CLOSED_CONFIRMATION")

if __name__=="__main__": unittest.main()
