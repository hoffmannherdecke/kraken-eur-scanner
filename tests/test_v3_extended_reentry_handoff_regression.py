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


    def test_later_real_1_to_3h_base_can_request_review_only(self):
        # This is a synthetic contract regression, NEVER historical MON replay.
        candidate={"candidate_id":"FRESH-SECOND-LEG","pair":"MON/EUR",
                   "event_time_utc":"2026-10-18T10:00:00Z"}
        first={"setup_lane":"EXTENDED","decision":"REJECT",
               "known_at_utc":"2026-10-18T10:01:00Z"}
        evidence={"observed_at_utc":"2026-10-18T12:02:02Z",
                  "known_at_utc":"2026-10-18T12:02:03Z",
                  "frames":{
                      "5":{"closed_close_eur":10.2,"volume_ratio_prior_5":1.3,
                           "last_closed_bar_end_utc":"2026-10-18T12:00:00Z"},
                      "15":{"closed_close_eur":10.0,"atr14_eur":0.3,
                            "recent_8bar_low_eur":9.8}}}
        ticker={"ask":10.21,"bid":10.20,
                "observed_at_utc":"2026-10-18T12:02:04Z"}
        with patch("paper_evaluator.v3_extended_reentry_review_v1.attach_to_future_evaluator",
                   return_value={}):
            result=extended_reentry_review(
                candidate,first,evidence,ticker,
                decision_at_utc="2026-10-18T12:02:05Z")
        self.assertTrue(result["full_model_review_candidate"])
        self.assertTrue(result["new_prospective_second_leg_observed"])
        self.assertFalse(result["approval_to_call_model"])
        self.assertFalse(result["paper_trade"])
        self.assertEqual(result["decision"],"NO_DECISION_AUTHORITY")

        # A late original is not silently re-dated. Missing original P4,
        # old closed 5m bars, future snapshots, or >3h are UNKNOWN.
        for original,coin,quote,now in (
            ({**first,"known_at_utc":"2026-10-18T12:01:00Z"},
             evidence,ticker,"2026-10-18T12:02:05Z"),
            ({**first,"known_at_utc":None},
             evidence,ticker,"2026-10-18T12:02:05Z"),
            (first,{**evidence,"observed_at_utc":"2026-10-18T11:50:00Z"},
             ticker,"2026-10-18T12:02:05Z"),
            (first,evidence,
             {**ticker,"observed_at_utc":"2026-10-18T11:50:00Z"},
             "2026-10-18T12:02:05Z"),
            (first,evidence,ticker,"2026-10-18T13:05:00Z"),
        ):
            with patch("paper_evaluator.v3_extended_reentry_review_v1.attach_to_future_evaluator",
                       return_value={}):
                bad=extended_reentry_review(candidate,original,coin,quote,
                                           decision_at_utc=now)
            self.assertFalse(bad.get("full_model_review_candidate",False),
                             bad)
            self.assertFalse(bad["paper_trade"])

if __name__=="__main__": unittest.main()
