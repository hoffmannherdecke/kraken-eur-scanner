"""Regression: eligible EXTENDED reentry must expose a full-review handoff, never a BUY."""
import unittest
from unittest.mock import patch
import json
import tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import tick_once
from tests.test_v3_paper_wait_observer_v1 import seed,SID,CID,START,DECISION,t
from tests.test_v3_paper_minipc_selective_tick_v1 import candidate,tick_capture
from paper_evaluator.v3_extended_reentry_review_v1 import extended_reentry_review
from paper_evaluator.v3_second_leg_policy_candidate_v1 import prepare_original_owner_reentry_child
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION

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


    def test_existing_single_owner_requires_prospectively_witnessed_1h_base(self):
        # Five independently timestamped Kraken-1m archive captures: four
        # closed consolidation bars and one later closed 15m reclaim. This is
        # a CI-only source stub; no historic MON claim or physical host ACK.
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        def record_chunk(when,outdir,breakout=False):
            base=(when-timedelta(minutes=15)).replace(second=0,microsecond=0)
            def loader(_):
                rows=[]
                for minute in range(15):
                    ts=int((base+timedelta(minutes=minute)).timestamp())
                    op,hi,lo,close=("2.09","2.17","2.04","2.15") if breakout else (
                        "2.08","2.12","2.04","2.09")
                    rows.append([ts,op,hi,lo,close,close,"10",1])
                return {"error":[],"result":{"ZROEUR":rows,"last":1}}
            return capture_public_1m(
                pair="ZRO/EUR",altname="ZROEUR",outdir=outdir,
                loader=loader,clock=lambda:when)
        def fetch(_,pair):
            return {"kind":"SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
                    "pair":pair,"status":"COMPLETE",
                    "observed_at_utc":t(at-timedelta(seconds=2)),
                    "known_at_utc":t(at-timedelta(seconds=1)),
                    "frames":{
                        "1":{"status":"VALID","interval_min":1,
                             "last_closed_bar_end_utc":t(at.replace(second=0)),
                             "closed_close_eur":2.15,"volume_ratio_prior_5":1.3},
                        "5":{"status":"VALID","interval_min":5,
                             "last_closed_bar_end_utc":t(at.replace(second=0)),
                             "closed_close_eur":2.15,"volume_ratio_prior_5":1.3},
                        "15":{"status":"VALID","interval_min":15,
                              "last_closed_bar_end_utc":t(at.replace(second=0)),
                              "closed_close_eur":2.15,"volume_ratio_prior_5":1.3,
                              "atr14_eur":0.1,"recent_8bar_low_eur":2.04}}}
        def quote(_):
            return {"pair":"ZRO/EUR","ask":2.155,"bid":2.153,
                    "observed_at_utc":t(at-timedelta(seconds=1))}
        original=candidate()
        original.update({"setup_lane":"EXTENDED","entry_origin":"SCANNER"})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";cap=root/"capture"
            journal.mkdir();cap.mkdir()
            seed(journal,model_setup_lane="EXTENDED")
            for n in range(4,0,-1):
                end_at=at.replace(second=7)-timedelta(minutes=n*15)
                record_chunk(end_at,cap)
            def witnessed_current(*,pair,altname,outdir):
                return record_chunk(at,outdir,breakout=True)
            first=tick_once(
                candidate=original,series_id=SID,journal=journal,
                capture_dir=cap,clock_now=lambda:t(at),
                capture=witnessed_current,fetch=fetch,ticker=quote)
            second=tick_once(
                candidate=original,series_id=SID,journal=journal,
                capture_dir=cap,clock_now=lambda:t(at),
                capture=witnessed_current,fetch=fetch,ticker=quote)
            self.assertTrue(first["extended_reentry"]["full_model_review_candidate"],
                            first["extended_reentry"])
            p1=first["extended_reentry"]
            self.assertEqual(p1["status"],
                "EXTENDED_CHILD_PREPARED_FOR_SEPARATE_GATED_MODEL_P4_NO_AUTH")
            self.assertEqual(p1["reentry_child_handoff"]["status"],
                "P1_CHILD_PREPARED_MODEL_AND_PAPER_STILL_GATED")
            self.assertEqual(p1["reentry_child_handoff"]["model_calls"],0)
            child=prepare_original_owner_reentry_child(
                journal=journal,series_id=SID,original_candidate=original,
                parent_event_key=p1["reentry_parent_event_key"],
                now_at_utc=t(at+timedelta(seconds=9)))
            self.assertEqual(child["status"],
                "P1_CHILD_PREPARED_MODEL_AND_PAPER_STILL_GATED")
            self.assertEqual(child["child_candidate"]["candidate_id"],
                             p1["reentry_episode_id"])
            self.assertEqual(child["child_candidate"]["event_time_utc"],
                             p1["reentry_episode_signal_at_utc"])
            self.assertNotEqual(child["child_candidate"]["event_time_utc"],
                                original["event_time_utc"])
            self.assertFalse(child["approval_to_call_model"])
            self.assertEqual(child["model_calls"],0)
            self.assertEqual(child["paper_fills"],0)
            with self.assertRaises(ValueError):
                prepare_original_owner_reentry_child(
                    journal=journal,series_id=SID,original_candidate=original,
                    parent_event_key=p1["reentry_parent_event_key"],
                    now_at_utc=t(at+timedelta(seconds=130)))
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
            self.assertEqual(route[0]["data"]["review_status"],
                             "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY")
            self.assertEqual(route[0]["data"]["review_family"],
                             "EXTENDED_PROSPECTIVE_15M_BASE_SECOND_LEG")
            episode=first["extended_reentry"]
            self.assertTrue(episode["reentry_episode_id"].startswith("V3RE-"))
            self.assertNotEqual(episode["reentry_episode_id"],original["candidate_id"])
            self.assertEqual(route[0]["data"]["reentry_parent_candidate_id"],
                             original["candidate_id"])
            self.assertEqual(route[0]["event_time_utc"],original["event_time_utc"])
            self.assertEqual(route[0]["data"]["reentry_closed_15m_end_utc"],
                             t(at.replace(second=0)).replace("+00:00","Z"))
            self.assertEqual(route[0]["data"]["reentry_episode_signal_at_utc"],
                             t(at).replace("+00:00","Z"))
            self.assertTrue(route[0]["data"]["reentry_will_use_separate_fill_time"])
            self.assertNotEqual(route[0]["event_time_utc"],
                                route[0]["data"]["reentry_episode_signal_at_utc"])
            self.assertFalse(any(r["phase"]=="PAPER_FILL" for r in receipts))
            self.assertEqual(len([r for r in receipts
                                  if r["phase"]=="MODEL_REQUEST"]),0)
            # Replaying the exact same closed bar into a child with any
            # existing immutable phase must never create another episode.
            childrec=make_receipt(
                series_id=SID,revision=REVISION,
                candidate_id=child["child_candidate"]["candidate_id"],
                pair=original["pair"],
                event_time_utc=child["child_candidate"]["event_time_utc"],
                known_at_utc=t(at+timedelta(seconds=2)),
                phase="MODEL_REQUEST",result="UNKNOWN",
                data={"phase_failure_stage":"TEST_NO_PAID_MODEL"})
            store_receipt_explicitly(journal,childrec)
            blocked=prepare_original_owner_reentry_child(
                journal=journal,series_id=SID,original_candidate=original,
                parent_event_key=p1["reentry_parent_event_key"],
                now_at_utc=t(at+timedelta(seconds=9)))
            self.assertEqual(blocked["status"],"P1_CHILD_ALREADY_JOURNALED_NO_REPLAY")
            self.assertEqual(blocked["model_calls"],0)

    def test_old_model_lane_cannot_be_invented_by_candidate_or_reason(self):
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        original=candidate()
        original.update({"setup_lane":"EXTENDED","entry_origin":"SCANNER"})
        with tempfile.TemporaryDirectory() as tmp:
            j=Path(tmp)/"journal";cap=Path(tmp)/"capture"
            j.mkdir();cap.mkdir()
            seed(j)  # No original model setup lane observed.
            result=tick_once(candidate=original,series_id=SID,
                journal=j,capture_dir=cap,clock_now=lambda:t(at),
                capture=tick_capture(at),
                fetch=lambda *_:self.fail("forged lane must not fetch"),
                ticker=lambda *_:self.fail("forged lane must not quote"))
            self.assertNotIn("extended_reentry",result)
            self.assertFalse(result["orders"])

    def test_missing_witnessed_1h_base_yields_unknown_not_false_buy(self):
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        original=candidate()
        with tempfile.TemporaryDirectory() as tmp:
            j=Path(tmp)/"journal";cap=Path(tmp)/"capture"
            j.mkdir();cap.mkdir()
            seed(j,model_setup_lane="EXTENDED")
            def coin(altname,pair):
                return {"kind":"SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
                        "pair":pair,"status":"COMPLETE",
                        "observed_at_utc":t(at-timedelta(seconds=2)),
                        "known_at_utc":t(at-timedelta(seconds=1)),
                        "frames":{
                            "1":{"status":"VALID","interval_min":1,
                                 "last_closed_bar_end_utc":t(at.replace(second=0)),
                                 "closed_close_eur":2.1,"volume_ratio_prior_5":1.3},
                            "5":{"status":"VALID","interval_min":5,
                                 "last_closed_bar_end_utc":t(at.replace(second=0)),
                                 "closed_close_eur":2.15,"volume_ratio_prior_5":1.3},
                            "15":{"status":"VALID","interval_min":15,
                                  "last_closed_bar_end_utc":t(at.replace(second=0)),
                                  "closed_close_eur":2.14,"volume_ratio_prior_5":1.3,
                                  "atr14_eur":.1,"recent_8bar_low_eur":2.04}}}
            out=tick_once(candidate=original,series_id=SID,
                journal=j,capture_dir=cap,clock_now=lambda:t(at),
                capture=tick_capture(at),fetch=coin,
                ticker=lambda _:{"pair":"ZRO/EUR","ask":2.155,"bid":2.153,
                                 "observed_at_utc":t(at-timedelta(seconds=1))})
            self.assertFalse(out["extended_reentry"]["full_model_review_candidate"])
            events=[json.loads(p.read_text()) for p in j.glob("*.json")]
            review=[x for x in events if x["phase"]=="FRESH_SECOND_LEG"]
            self.assertEqual(len(review),1)
            self.assertEqual(review[0]["result"],"UNKNOWN")
            self.assertIn(review[0]["data"]["review_status"],
                          ("MISSING_CLOSED_CONSOLIDATION_HISTORY",
                           "UNKNOWN_PROSPECTIVE_15M_BASE_SOURCE_INVALID"))
            self.assertFalse(out["orders"])

    def test_incomplete_later_source_journals_unknown_not_false_market_reject(self):
        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        original=candidate()
        original.update({"setup_lane":"EXTENDED","entry_origin":"SCANNER"})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";cap=root/"capture"
            journal.mkdir();cap.mkdir()
            seed(journal,model_setup_lane="EXTENDED")
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


class P1NativeModelWriterTests(unittest.TestCase):
    """Synthetic physically-isolated contract test, zero provider HTTP/Cloud writes."""

    SERIES="PAPER-V3-20261012T081500Z"
    REPO="a"*40
    BUNDLE="b"*64
    STRATEGY="c"*64

    def prepare(self,root):
        from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
            canonical_second_leg_episode,
        )
        from paper_evaluator.v3_full_entry_decision_candidate_v1 import SECOND_LEG_P1_CHECKS
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m
        from tests.test_v3_paper_minipc_one_candidate_v1 import valid_approval

        at=datetime(2026,10,12,8,45,7,tzinfo=timezone.utc)
        original=candidate()
        original.update(entry_origin="SCANNER")
        journal=root/"journal";capture=root/"capture";budget=root/"budget"
        for directory in (journal,capture,budget):directory.mkdir()
        def original_row(phase,status,when,data):
            receipt=make_receipt(
                series_id=self.SERIES,revision=REVISION,
                candidate_id=original["candidate_id"],pair=original["pair"],
                event_time_utc=original["event_time_utc"],
                known_at_utc=t(when),phase=phase,result=status,
                data=data)
            store_receipt_explicitly(journal,receipt)
        original_row("SCANNER_CAPTURE","SEEN",START,
                     {"candidate_origin":"SCANNER"})
        original_row("MODEL_RESPONSE","PASS",DECISION,
                     {"raw_setup_lane":"EXTENDED","raw_model_decision":"WAIT",
                      "model_response_at_utc":t(DECISION),
                      "model_response_id":"PARENT_TEST_REPLY"})
        original_row("P4_VALIDATION","WAIT",DECISION,
                     {"p4_decision":"WAIT","p4_status":"FULL_WAIT_VALIDATED_OFFLINE"})
        for n in range(4, -1, -1):
            when=at-timedelta(minutes=n*15)
            beginning=(when-timedelta(minutes=15)).replace(second=0,microsecond=0)
            breakout=n==0
            def loader(symbol,beginning=beginning,breakout=breakout):
                bars=[]
                for m in range(15):
                    ts=int((beginning+timedelta(minutes=m)).timestamp())
                    op,hi,lo,close=(
                        ("2.09","2.17","2.04","2.15") if breakout else
                        ("2.08","2.12","2.04","2.09"))
                    bars.append([ts,op,hi,lo,close,close,"10",1])
                return {"error":[],"result":{"ZROEUR":bars,"last":1}}
            capture_public_1m(pair="ZRO/EUR",altname="ZROEUR",
                              outdir=capture,loader=loader,clock=lambda when=when:when)
        episode=canonical_second_leg_episode(
            series_id=self.SERIES,original_candidate=original,
            closed_15m_end_utc=t(at.replace(second=0)),
            signal_known_at_utc=t(at))
        p1={"review_family":"EXTENDED_PROSPECTIVE_15M_BASE_SECOND_LEG",
            "review_status":"SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY",
            "review_checks":{"p1":{k:True for k in SECOND_LEG_P1_CHECKS}}}
        p1.update(episode)
        rec=make_receipt(
            series_id=self.SERIES,revision=REVISION,
            candidate_id=original["candidate_id"],pair=original["pair"],
            event_time_utc=original["event_time_utc"],
            known_at_utc=t(at),phase="FRESH_SECOND_LEG",
            result="PASS",event_key=episode["reentry_parent_event_key"],
            data=p1)
        store_receipt_explicitly(journal,rec)
        parent=prepare_original_owner_reentry_child(
            journal=journal,series_id=self.SERIES,
            original_candidate=original,
            parent_event_key=episode["reentry_parent_event_key"],
            now_at_utc=t(at+timedelta(seconds=1)))
        self.assertEqual(parent["status"],"P1_CHILD_PREPARED_MODEL_AND_PAPER_STILL_GATED")
        approval=dict(valid_approval(),series_id=self.SERIES,
                      unique_approval_id="P1-CHILD-UNIQUE-ONE-SHOT-CI-20261012")
        cloud={"series_id":self.SERIES,"status":"active","strategy_revision":REVISION,
               "observed_at_utc":t(at+timedelta(seconds=9)),
               "config":{
                   "series_id":self.SERIES,"strategy_revision":REVISION,
                   "release_repo_sha":self.REPO,
                   "runtime_bundle_fingerprint_sha256":self.BUNDLE,
                   "strategy_fingerprint_sha256":self.STRATEGY,
                   "paper_only":True,"real_money_actions_enabled":False,
                   "automatic_activation_allowed":False,
                   "physical_v2r4_writer_fence_verified":True,
                   "supervisor_old_intake_rearm_blocked":True,
                   "old_followup_owner_preserved":True,
                   "independent_six_e2e_proofs_verified":True}}
        coin={"kind":"SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
              "pair":"ZRO/EUR","status":"COMPLETE",
              "observed_at_utc":t(at+timedelta(seconds=1)),
              "known_at_utc":t(at+timedelta(seconds=2)),
              "frames":{
                  "1":{"interval_min":1,"status":"VALID",
                       "last_closed_bar_end_utc":t(at.replace(second=0)),
                       "closed_close_eur":2.15,"volume_ratio_prior_5":1.3},
                  "5":{"interval_min":5,"status":"VALID",
                       "last_closed_bar_end_utc":t(at.replace(second=0)),
                       "closed_close_eur":2.15,"volume_ratio_prior_5":1.3},
                  "15":{"interval_min":15,"status":"VALID",
                        "last_closed_bar_end_utc":t(at.replace(second=0)),
                        "closed_close_eur":2.15,"volume_ratio_prior_5":1.3,
                        "volume_ratio_prior_4":1.3,
                        "atr14_eur":0.1,"recent_8bar_low_eur":2.04}}}
        bid,ask=2.153,2.155
        quote={"pair":"ZRO/EUR","ask":ask,"bid":bid,
               "spread_pct":(ask-bid)/((ask+bid)/2)*100,
               "observed_at_utc":t(at+timedelta(seconds=3))}
        meta={"pair":"ZRO/EUR","status":"online","spot":True,
              "quote":"EUR","minimum_order_passed":True,
              "observed_at_utc":t(at+timedelta(seconds=4))}
        def model(prompt,_):
            self.assertIn("original_candidate_historical_only",prompt)
            return {"decision":"BUY_SCOUT","setup_lane":"EXTENDED",
                    "reason_codes":["FRESH_CLOSED_BASE_RECLAIM"],
                    "anti_chase_passed":True,
                    "stop_eur":2.04,"stage2_trigger_eur":2.27,
                    "stage2_ttl_minutes":30,"expected_remaining_move_pct":5.0}, {
                        "model":"CI-TEST-NO-PROVIDER","response_id":"CI-P1-ONE-RESPONSE"}
        return (at,original,parent["child_candidate"],approval,cloud,
                (coin,quote,meta),model)

    def call(self,root,prepared,*,model_client=None,acquire=None,clock_now=None,
             approval=None):
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            released_paper_reentry_child_model_once,
        )
        at,parent,child,approved,cloud,pit,model=prepared
        return released_paper_reentry_child_model_once(
            child=child,original_candidate=parent,series_id=self.SERIES,
            journal=root/"journal",capture_dir=root/"capture",
            model_reservations=root/"budget",
            expected_repo_sha=self.REPO,
            expected_bundle_sha256=self.BUNDLE,
            expected_strategy_sha256=self.STRATEGY,
            read_active_series=lambda _:cloud,
            approval=approved if approval is None else approval,
            model_key="CI-MODEL-STUB-FAKE-NO-REAL-KEY",
            clock_now=clock_now or (lambda:t(at+timedelta(seconds=9))),
            acquire=acquire or (lambda _:pit),
            model_client=model_client or model)

    def test_native_parent_child_model_p4_actual_paper_receipt_and_no_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.prepare(root)
            out=self.call(root,p)
            self.assertEqual(out["status"],"P1_CHILD_MODEL_P4_DURABLE_WAIT_FOR_FOLLOWUP")
            self.assertEqual(out["model_result"]["p4_decision"],"BUY_SCOUT")
            self.assertTrue(out["paper_entry_receipt_verified_local"])
            self.assertFalse(out["independent_cloud_paper_fill_ack"])
            child=p[2]
            records=[json.loads(x.read_text()) for x in (root/"journal").glob("*.json")]
            fills=[row for row in records if row["phase"]=="PAPER_FILL"]
            self.assertEqual(len(fills),1)
            fill=fills[0]
            self.assertEqual(fill["candidate_id"],child["candidate_id"])
            self.assertEqual(fill["event_time_utc"],child["event_time_utc"])
            self.assertNotEqual(fill["event_time_utc"],p[1]["event_time_utc"])
            self.assertGreater(datetime.fromisoformat(fill["known_at_utc"]),
                               datetime.fromisoformat(child["event_time_utc"]))
            self.assertEqual(fill["data"]["paper_entry_fee_eur"],0.3)
            self.assertFalse(any(x["phase"]=="SCANNER_CAPTURE" and
                                 x["candidate_id"]==child["candidate_id"]
                                 for x in records))
            self.assertEqual(len(list((root/"budget").glob("*.reserved.json"))),1)
            repeated=self.call(root,p,model_client=lambda *_:
                               self.fail("no retry after P1 model/P4/Fill"))
            self.assertEqual(repeated["status"],"P1_CHILD_ALREADY_JOURNALED_NO_MODEL_RETRY")
            self.assertFalse(repeated["orders"])

    def test_native_p1_full_model_reject_has_no_fill_and_no_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.prepare(root)
            def reject(prompt,key):
                obj,meta=p[6](prompt,key)
                obj["decision"]="REJECT"
                return obj,meta
            out=self.call(root,p,model_client=reject)
            self.assertEqual(out["model_result"]["p4_decision"],"REJECT")
            self.assertEqual(out["paper_entry_status"],"NO_BUY_NO_PAPER_FILL_AS_EXPECTED")
            self.assertFalse(any(json.loads(x.read_text())["phase"]=="PAPER_FILL"
                                 for x in (root/"journal").glob("*.json")))
            self.assertEqual(len(list((root/"budget").glob("*.reserved.json"))),1)

    def test_native_p1_missing_fill_or_bad_response_id_quarantines_without_spend_retry(self):
        from unittest.mock import patch
        from paper_evaluator import v3_paper_minipc_one_candidate_v1 as module
        for defect in ("NO_FILL_ON_DISK","MISSING_RESPONSE_ID"):
            with self.subTest(defect=defect):
                with tempfile.TemporaryDirectory() as td:
                    root=Path(td);p=self.prepare(root)
                    real=module.store_receipt_explicitly
                    def missing_fill(directory,receipt):
                        if receipt["phase"]=="PAPER_FILL":
                            return "SIMULATED_LOST_DISK_WRITE",Path(directory)/"missing.json"
                        return real(directory,receipt)
                    def no_response_id(prompt,key):
                        obj,meta=p[6](prompt,key)
                        return obj,dict(meta,response_id="")
                    kw=({"model_client":no_response_id}
                        if defect=="MISSING_RESPONSE_ID" else {})
                    with patch.object(module,"store_receipt_explicitly",
                                      side_effect=missing_fill if defect=="NO_FILL_ON_DISK" else real):
                        out=self.call(root,p,**kw)
                    self.assertEqual(out["status"],"P1_MODEL_OR_PAPER_LEDGER_INCOMPLETE_HOLD")
                    self.assertTrue(out["requires_original_owner_reconciliation"])
                    self.assertEqual(len(list((root/"budget").glob("*.reserved.json"))),1)
                    self.assertEqual(self.call(root,p,model_client=lambda *_:
                        self.fail("model must not retry"))["status"],
                                     "P1_CHILD_ALREADY_JOURNALED_NO_MODEL_RETRY")

    def test_native_p1_stale_source_and_unapproved_budget_do_not_spend(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.prepare(root)
            with self.assertRaises(ValueError):
                self.call(root,p,approval=dict(p[3],explicit_user_new_budget_approval=False),
                          acquire=lambda *_:self.fail("no Kraken before approval"))
            self.assertFalse(list((root/"budget").glob("*.reserved.json")))
            at,parent,child,approval,cloud,pit,model=p
            stale=dict(pit[0],known_at_utc=t(at-timedelta(minutes=5)))
            out=self.call(root,p,acquire=lambda _: (stale,pit[1],pit[2]))
            self.assertEqual(out["status"],"P1_NEW_MARKET_SOURCE_NOT_VERIFIED_NO_MODEL")
            self.assertFalse(list((root/"budget").glob("*.reserved.json")))
            self.assertFalse(out["orders"])


if __name__=="__main__": unittest.main()
