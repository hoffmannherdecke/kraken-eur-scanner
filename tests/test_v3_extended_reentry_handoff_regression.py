"""Regression: eligible EXTENDED reentry must expose a full-review handoff, never a BUY."""
import unittest
from unittest.mock import patch
import json
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import tick_once
from tests.test_v3_paper_wait_observer_v1 import seed,SID,CID,t
from tests.test_v3_paper_minipc_selective_tick_v1 import candidate,tick_capture
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


    def test_existing_single_owner_tick_journals_real_later_review_not_model_or_fill(self):
        # Exercise the EXISTING V3 owner, not a new shadow scheduler/HTTP.
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        def real_second_leg(altname,pair):
            return {"pair":pair,"status":"COMPLETE",
                    "observed_at_utc":t(at-timedelta(seconds=2)),
                    "known_at_utc":t(at-timedelta(seconds=1)),
                    "frames":{
                        "5":{"status":"VALID",
                             "last_closed_bar_end_utc":t(at.replace(second=0)),
                             "closed_close_eur":2.115,"volume_ratio_prior_5":1.3},
                        "15":{"status":"VALID","closed_close_eur":2.1,
                              "atr14_eur":0.1,"recent_8bar_low_eur":2.0}}}
        def quote(_):
            return {"ask":2.11,"bid":2.10,
                    "observed_at_utc":t(at-timedelta(seconds=1))}
        original=candidate()
        original.update({"setup_lane":"EXTENDED","entry_origin":"SCANNER"})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";cap=root/"capture"
            journal.mkdir();cap.mkdir()
            seed(journal)
            with patch("paper_evaluator.v3_extended_reentry_review_v1.attach_to_future_evaluator",
                       return_value={}):
                first=tick_once(
                    candidate=original,series_id=SID,journal=journal,
                    capture_dir=cap,clock_now=lambda:t(at),
                    capture=tick_capture(at),fetch=real_second_leg,ticker=quote)
                second=tick_once(
                    candidate=original,series_id=SID,journal=journal,
                    capture_dir=cap,clock_now=lambda:t(at),
                    capture=tick_capture(at),fetch=real_second_leg,ticker=quote)
            self.assertTrue(first["extended_reentry"]["full_model_review_candidate"])
            self.assertEqual(first["extended_reentry"]["model_calls"],0)
            self.assertEqual(first["extended_reentry"]["paper_fills"],0)
            self.assertEqual(second["extended_reentry"]["status"],
                             "EXTENDED_BAR_ALREADY_REVIEWED_NO_DUPLICATE")
            self.assertFalse(first["orders"])
            self.assertFalse(first["v2r4_changed"])
            receipts=[json.loads(p.read_text()) for p in journal.glob("*.json")]
            route=[r for r in receipts if r["phase"]=="FRESH_SECOND_LEG"]
            self.assertEqual(len(route),1)
            self.assertEqual(route[0]["result"],"PASS")
            self.assertEqual(route[0]["data"]["review_family"],
                             "EXTENDED_PROSPECTIVE_SECOND_LEG")
            self.assertFalse(any(r["phase"]=="PAPER_FILL" for r in receipts))
            self.assertEqual(len([r for r in receipts
                                  if r["phase"]=="MODEL_REQUEST"]),0)

    def test_incomplete_later_source_journals_unknown_not_false_market_reject(self):
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        original=candidate()
        original.update({"setup_lane":"EXTENDED","entry_origin":"SCANNER"})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";cap=root/"capture"
            journal.mkdir();cap.mkdir()
            seed(journal)
            out=tick_once(
                candidate=original,series_id=SID,journal=journal,
                capture_dir=cap,clock_now=lambda:t(at),
                capture=tick_capture(at),
                fetch=lambda *_: {"pair":"ZRO/EUR","status":"UNKNOWN_SOURCE_GAP"},
                ticker=lambda *_: {"ask":2.11,"bid":2.10})
            self.assertFalse(out["extended_reentry"]["full_model_review_candidate"])
            self.assertEqual(out["extended_reentry"]["model_calls"],0)
            receipts=[json.loads(p.read_text()) for p in journal.glob("*.json")]
            missing=[r for r in receipts if r["phase"]=="FRESH_SECOND_LEG"]
            self.assertEqual(len(missing),1)
            self.assertEqual(missing[0]["result"],"UNKNOWN")
            self.assertFalse(any(r["phase"]=="PAPER_FILL" for r in receipts))

if __name__=="__main__": unittest.main()
