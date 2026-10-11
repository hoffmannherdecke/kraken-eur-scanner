"""V3 immutable per-event Paper evidence, censoring, and no-trade analysis."""
import copy
import tempfile
import unittest
from pathlib import Path

from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt,store_receipt_explicitly,funnel_summary,
)
from tests.test_v2r4_v3_entry_handoff_probe import dt


def event(phase="SCANNER_CAPTURE",result="SEEN",when=None,data=None,**extra):
    return make_receipt(
        series_id="PAPER-V3-EXPERIMENTAL-TEST",
        revision="V3-EXPERIMENTAL-PAPER-TEST",
        candidate_id="CAND-1",pair="XBT/EUR",
        event_time_utc=dt(0),known_at_utc=when or dt(15),
        phase=phase,result=result,data=data,**extra)


class ExperimentalV3JournalTests(unittest.TestCase):
    def test_pre_model_skip_writes_immutable_duplicate_checked_receipt(self):
        e=event("SOURCE_INPUT","UNKNOWN",data={
            "phase_failure_class":"ValueError",
            "phase_failure_stage":"COIN_1M_5M_15M_PIT",
            "source_status":"PARTIAL"})
        snap=copy.deepcopy(e)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            a,p=store_receipt_explicitly(root,e)
            self.assertEqual(a,"IMMUTABLE_NEW_RECEIPT")
            self.assertTrue(p.is_file())
            b,q=store_receipt_explicitly(root,e)
            self.assertEqual((b,q),("IDEMPOTENT_IDENTICAL",p))
            altered=copy.deepcopy(e);altered["data"]["source_status"]="COMPLETE"
            with self.assertRaisesRegex(ValueError,"conflicting event"):
                store_receipt_explicitly(root,altered)
            self.assertEqual(e,snap)
            self.assertEqual(len(list(root.glob("*.json"))),1)

    def test_no_hidden_reject_and_reason_mentions_are_not_unique_vetoes(self):
        x=[
            event(),
            event("SOURCE_INPUT","UNKNOWN",event_key="COIN",
                  data={"source_status":"PARTIAL","phase_failure_stage":"COIN_1M_5M_15M_PIT"}),
            event("FULL_REVIEW_ELIGIBILITY","SKIP",event_key="P3",
                  data={"failed_hard_checks":["NO_15M_CLOSE"]}),
            event("MODEL_RESPONSE","REJECT",event_key="LATER",
                  data={"raw_reason_codes":["EXTENDED_MOVE","EXTENDED_MOVE",
                                            "NO_VOLUME_CONFIRMATION"]}),
            event("FOLLOWUP_24H","CENSORED",when=dt(90000),
                  data={"censor_reason":"TECHNICAL_SERIES_ROTATION"}),
        ]
        y=funnel_summary(x)
        self.assertEqual(y["unique_series_candidate_count"],1)
        self.assertEqual(y["technical_missing_unknown_or_censored_events"],3)
        self.assertEqual(y["reason_mentions_not_exclusive_causes"]["EXTENDED_MOVE"],1)
        self.assertEqual(y["horizon_maturity"]["FOLLOWUP_24H:CENSORED"],1)
        self.assertIsNone(y["realized_net_pnl_sum_eur"])
        with self.assertRaises(ValueError):
            funnel_summary(x+x[:1])

    def test_followups_must_have_contiguous_real_path_and_maturity(self):
        with self.assertRaises(ValueError):
            event("FOLLOWUP_24H","MATURE_COMPLETE",when=dt(3599),
                  data={"followup_source":"KRAKEN_CLOSED_1M",
                        "path_contiguous_1m_verified":True})
        with self.assertRaises(ValueError):
            event("FOLLOWUP_6H","MATURE_COMPLETE",when=dt(22000),
                  data={"followup_source":"KRAKEN_CLOSED_1M",
                        "path_contiguous_1m_verified":False})
        with self.assertRaises(ValueError):
            event("FOLLOWUP_24H","CENSORED",when=dt(90000))
        v=event("FOLLOWUP_24H","MATURE_COMPLETE",when=dt(86400),
                data={"followup_source":"KRAKEN_CLOSED_1M",
                      "path_contiguous_1m_verified":True,
                      "mfe_pct":14.0,"mae_pct":-9.0,
                      "stop_before_profit_ordering":"AMBIGUOUS_ADVERSE_FIRST"})
        self.assertEqual(v["result"],"MATURE_COMPLETE")
        self.assertFalse(v["orders"])
        self.assertTrue(v["mfe_is_not_net_profit"])

    def test_unsafe_buy_contract_does_not_bypass_stop_stage2_fees(self):
        good={"p4_decision":"BUY_SCOUT",
              "p4_status":"FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE",
              "ask_eur":10.25,"validated_stop_eur":9.8,
              "validated_stage2_eur":10.6,"total_cost_pct":1.45}
        e=event("P4_VALIDATION","BUY_SCOUT",data=good)
        self.assertEqual(e["result"],"BUY_SCOUT")
        bad=(dict(good,validated_stop_eur=10.3),
             dict(good,total_cost_pct=0.2),
             dict(good,p4_status="HOMEMADE_FAKE_BUY"))
        for payload in bad:
            with self.assertRaises(ValueError):
                event("P4_VALIDATION","BUY_SCOUT",data=payload)

    def test_no_nan_secrets_or_outcome_relabels(self):
        for data in (
            {"openai_api_key":"would_leak"},
            {"ask_eur":float("nan")},
            {"raw_reason_codes":[object()]},
        ):
            with self.assertRaises(ValueError):
                event("SOURCE_INPUT","UNKNOWN",data=data)
        with self.assertRaises(ValueError):
            event("SOURCE_INPUT","SEEN",when=dt(-1))
        with self.assertRaises(ValueError):
            event("SOURCE_INPUT","PASS",event_key="../ESCAPE")
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                store_receipt_explicitly(Path(temp)/"NOT_PREPARED",event())

if __name__=="__main__":
    unittest.main()
