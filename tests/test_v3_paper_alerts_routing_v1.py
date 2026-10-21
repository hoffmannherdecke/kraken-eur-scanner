"""No-network V3 alert routing against original durable Paper model/P4/fill."""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location(
    "existing_paper_alert_relay", ROOT/"tools/v2r4-paper-alerts.py")
ALERT=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ALERT)
SID="PAPER-V3-20261019T100000Z"
CID="20261019-100001-TIA-EUR-r123456789"
PAIR="TIA/EUR"
EID="a"*64
STAMP="2026-10-19T10:04:30+00:00"


def row(phase, result, data, event=EID, event_key="FIRST"):
    return {"event_id":event,"series_id":SID,"candidate_id":CID,"pair":PAIR,
            "phase":phase,"result":result,"source_known_at":STAMP,
            "content_sha256":"b"*64,
            "payload":{"kind":"V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1",
                       "event_id":event,"series_id":SID,"candidate_id":CID,
                       "event_key":event_key,
                       "pair":PAIR,"phase":phase,"result":result,
                       "orders":False,"real_money_actions":False,
                       "data":data}}


def original_sources():
    return {
      "fill":row("PAPER_FILL","PAPER_FILLED",{
        "paper_entry_ask_eur":2.0,"paper_entry_qty":25.0,
        "paper_entry_fee_eur":0.30,"validated_stop_eur":1.9,
        "validated_stage2_eur":2.2}),
      "p4":row("P4_VALIDATION","BUY_SCOUT",{
        "p4_decision":"BUY_SCOUT","ask_eur":2.0,
        "validated_stop_eur":1.9,"validated_stage2_eur":2.2}),
      "model":row("MODEL_RESPONSE","PASS",{"raw_model_decision":"BUY_SCOUT"}),
    }


class AlertRouterTests(unittest.TestCase):
    def setUp(self):
        self.series={"series_id":SID,"status":"active","strategy_revision":"V3-PAPER-001",
                     "config":{"paper_only":True,"real_money_actions_enabled":False}}
        self.src=original_sources()
        self.p4_history=[self.src["p4"]]
        self.model_history=[self.src["model"]]
        self.fills=[]
        self.sent=[]
        self.receipts=[]
        self.request_paths=[]
        self.env_patch=mock.patch.object(ALERT,"env",return_value=("cloud","key","hook","user"))
        self.get_patch=mock.patch.object(ALERT,"get",side_effect=self.get)
        self.slack_patch=mock.patch.object(ALERT,"post_slack",side_effect=self.post_slack)
        self.receipt_patch=mock.patch.object(ALERT,"insert_receipt",side_effect=self.insert)
        for p in (self.env_patch,self.get_patch,self.slack_patch,self.receipt_patch):p.start()

    def tearDown(self):
        for p in (self.receipt_patch,self.slack_patch,self.get_patch,self.env_patch):p.stop()

    def get(self,url,key,path):
        self.request_paths.append(path)
        if path.startswith("paper_series?"):return [self.series] if self.series else []
        if path.startswith("v2r4_paper_alert_receipts?"):return list(self.receipts)
        if path.startswith("v3_paper_event_receipts?"):
            if "phase=eq.PAPER_FILL" in path:
                return self.fills
            if "phase=eq.P4_VALIDATION" in path or "phase=eq.MODEL_RESPONSE" in path:
                # The true PostgREST JSON-field filter must be present for
                # each exact candidate episode, not just candidate+phase.
                self.assertIn("payload->>event_key=eq.",path)
                event_key=path.split("payload->>event_key=eq.",1)[1].split("&",1)[0]
                history=(self.p4_history if "phase=eq.P4_VALIDATION" in path
                         else self.model_history)
                return [x for x in history
                        if x["payload"].get("event_key")==event_key][:2]
            raise AssertionError("unapproved V3 query: "+path)
        if path.startswith("paper_candidate_outcomes?"):return []
        if path.startswith("paper_trade_results?"):return []
        raise AssertionError("unexpected query "+path)

    def post_slack(self,webhook,text):
        self.sent.append(text)
        return STAMP

    def insert(self,url,key,item):
        self.receipts.append({"event_key":item["event_key"]})
        self.last_receipt=item

    def run_relay(self):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            ALERT.main()
        return json.loads(buf.getvalue())

    def test_only_current_v2r4_original_is_unchanged(self):
        self.series={"series_id":"PAPER-V2R4-20261009T110135Z",
                     "status":"active","strategy_revision":"V2R4-FROZEN"}
        result=self.run_relay()
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(self.sent,[])
        self.assertEqual(self.receipts,[])
        self.assertFalse(any("v3_paper_event_receipts?" in p for p in self.request_paths))

    def test_wait_or_p4_without_actual_paper_fill_sends_nothing(self):
        r=self.run_relay()
        self.assertEqual(r["status"],"PASS_V3_ORIGINAL_FILLS_ONLY")
        self.assertEqual(r["delivered"],0)
        self.assertEqual(self.sent,[])
        self.assertFalse(any("phase=eq.P4_VALIDATION" in p for p in self.request_paths))

    def test_verified_model_p4_durable_paper_fill_one_alert_and_dedupe(self):
        self.fills=[self.src["fill"]]
        r=self.run_relay()
        self.assertEqual(r["delivered"],1)
        self.assertEqual(len(self.sent),1)
        self.assertIn("V3 PAPER BUY_SCOUT",self.sent[0])
        self.assertIn("keine Echtgeldorder",self.sent[0])
        self.assertEqual(self.last_receipt["series_id"],SID)
        self.assertEqual(self.last_receipt["payload"]["source"],"V3_ORIGINAL_PAPER_FILL")
        self.assertEqual(self.run_relay()["delivered"],0)
        self.assertEqual(len(self.sent),1)

    def test_p4_without_buy_or_missing_model_fails_before_slack(self):
        self.fills=[self.src["fill"]]
        self.src["p4"]["result"]="WAIT"
        self.src["p4"]["payload"]["result"]="WAIT"
        with self.assertRaisesRegex(RuntimeError,"IDENTITY_MISMATCH"):
            self.run_relay()
        self.assertEqual(self.sent,[])
        self.assertEqual(self.receipts,[])

    def test_mismatched_fill_economics_fails_closed(self):
        self.fills=[self.src["fill"]]
        self.src["fill"]["payload"]["data"]["paper_entry_qty"]=29.0
        with self.assertRaisesRegex(RuntimeError,"ECONOMICS_MISMATCH"):
            self.run_relay()
        self.assertEqual(self.sent,[])

    def test_non_paper_or_money_enabled_v3_blocks_all(self):
        self.series["config"]["real_money_actions_enabled"]=True
        with self.assertRaisesRegex(RuntimeError,"NO_PAPER_ONLY"):
            self.run_relay()
        self.assertEqual(self.sent,[])

    def test_foreign_unknown_active_revision_fails_closed(self):
        self.series["strategy_revision"]="V4-PAPER-UNKNOWN"
        with self.assertRaisesRegex(RuntimeError,"UNSUPPORTED_ACTIVE"):
            self.run_relay()

    def test_duplicate_active_series_is_rejected(self):
        self.series={"series_id":SID,"status":"active","strategy_revision":"V3-PAPER-001",
                     "config":{"paper_only":True,"real_money_actions_enabled":False}}
        orig=self.get
        def two(url,key,path):
            if path.startswith("paper_series?"):return [self.series,self.series]
            return orig(url,key,path)
        with mock.patch.object(ALERT,"get",side_effect=two):
            with self.assertRaisesRegex(RuntimeError,"CARDINALITY"):
                self.run_relay()
        self.assertEqual(self.sent,[])

    def test_duplicate_same_episode_fills_block_before_partial_slack_delivery(self):
        self.fills=[self.src["fill"],dict(self.src["fill"],event_id="c"*64)]
        with self.assertRaisesRegex(RuntimeError,"DUPLICATE_FILL_EPISODE"):
            self.run_relay()
        self.assertEqual(self.sent,[])
        self.assertEqual(self.receipts,[])

    def test_wait_first_then_fresh_recheck_buy_alert_delivered_once(self):
        # Same original candidate had an earlier real WAIT. The next
        # valid BUY model/P4/fill must join ONLY its FRESHRECHECK episode.
        first_model=row("MODEL_RESPONSE","PASS",{"raw_model_decision":"WAIT"},
                        event="1"*64)
        first_p4=row("P4_VALIDATION","WAIT",{"p4_decision":"WAIT"},
                     event="2"*64)
        for part in ("model","p4","fill"):
            self.src[part]["payload"]["event_key"]="FRESHRECHECK"
        self.p4_history=[first_p4,self.src["p4"]]
        self.model_history=[first_model,self.src["model"]]
        self.fills=[self.src["fill"]]
        result=self.run_relay()
        self.assertEqual(result["delivered"],1)
        self.assertEqual(len(self.sent),1)
        self.assertTrue(any("phase=eq.MODEL_RESPONSE" in x
                            and "payload->>event_key=eq.FRESHRECHECK" in x
                            for x in self.request_paths))
        self.assertEqual(self.run_relay()["delivered"],0)

    def test_foreign_earlier_model_cannot_support_later_p4_fill(self):
        self.src["p4"]["payload"]["event_key"]="FRESHRECHECK"
        self.src["fill"]["payload"]["event_key"]="FRESHRECHECK"
        self.fills=[self.src["fill"]]
        # Only the FIRST model exists. No cross-episode BUY inference.
        with self.assertRaisesRegex(RuntimeError,"MISSING_UNIQUE_MODEL_RESPONSE"):
            self.run_relay()
        self.assertEqual(self.sent,[])

    def test_missing_fill_episode_blocks_before_any_delivery(self):
        self.fills=[self.src["fill"]]
        del self.src["fill"]["payload"]["event_key"]
        with self.assertRaisesRegex(RuntimeError,"MISSING_OR_INVALID_EPISODE"):
            self.run_relay()
        self.assertEqual(self.sent,[])

    def test_source_chronology_model_p4_fill_must_be_ordered(self):
        self.fills=[self.src["fill"]]
        self.src["model"]["source_known_at"]="2026-10-19T10:04:31+00:00"
        with self.assertRaisesRegex(RuntimeError,"SOURCE_CLOCK_INVALID"):
            self.run_relay()
        self.assertEqual(self.sent,[])
        self.src["model"]["source_known_at"]="2026-10-19T10:04:30"
        with self.assertRaisesRegex(RuntimeError,"SOURCE_CLOCK_INVALID"):
            self.run_relay()
        self.assertEqual(self.receipts,[])


if __name__=="__main__":
    unittest.main()
