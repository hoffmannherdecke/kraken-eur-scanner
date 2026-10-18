"""Independent V3 Paper WAIT: fresh 5m PIT, idempotent, TTL and no API."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.v3_paper_wait_observer_v1 import observe_wait,finish_wait

SID="PAPER-V3-CANARY-20261011"
CID="20261012-064219-ZRO-EUR-r168479886848322"
START=datetime(2026,10,12,6,42,19,tzinfo=timezone.utc)
DECISION=datetime(2026,10,12,6,44,49,tzinfo=timezone.utc)
def t(x):return x.isoformat()
def seed(j:Path,conditions=None,*,model_setup_lane=None):
    rows=[
        ("SCANNER_CAPTURE","SEEN",START,{}),
        ("MODEL_RESPONSE","PASS",DECISION,{"model_response_at_utc":t(DECISION),
               "raw_model_decision":"WAIT"}),
        ("P4_VALIDATION","WAIT",DECISION,{"p4_status":"FULL_WAIT_VALIDATED_OFFLINE",
               "p4_decision":"WAIT"}),
        ("WAIT_WATCH","WAIT",DECISION+timedelta(seconds=2),{
            "raw_wait_ttl_minutes":30,
            "raw_watch_conditions":conditions if conditions is not None else [
                {"metric":"closed_5m_close_eur","op":">","value":2.111},
                {"metric":"closed_5m_volume_ratio_5","op":">=","value":1.2},
                {"metric":"ask_eur","op":"<=","value":2.12},
            ]})
    ]
    if model_setup_lane is not None:
        rows[1][3]["raw_setup_lane"]=model_setup_lane
    for phase,result,known,data in rows:
        record=make_receipt(series_id=SID,revision=REVISION,candidate_id=CID,
            pair="ZRO/EUR",event_time_utc=t(START),known_at_utc=t(known),
            phase=phase,result=result,data=data)
        store_receipt_explicitly(j,record)
def snap(at:datetime,*,close=2.114,volume=1.3,ask=2.110,pair="ZRO/EUR",bar=None):
    return {"pair":pair,"observed_at_utc":t(at-timedelta(seconds=2)),
        "known_at_utc":t(at),
        "closed_5m_end_utc":t(bar or datetime(2026,10,12,6,50,tzinfo=timezone.utc)),
        "values":{"closed_5m_close_eur":close,
                  "closed_5m_volume_ratio_5":volume,"ask_eur":ask}}
def logs(j):
    return [json.loads(p.read_text("utf-8")) for p in j.glob("*.json")]

class WaitTests(unittest.TestCase):
    def test_actual_within_ttl_5m_all_3_conditions_triggers_review_not_buy(self):
        with tempfile.TemporaryDirectory() as td:
            j=Path(td);seed(j)
            now=datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)
            out=observe_wait(journal=j,series_id=SID,candidate_id=CID,
                             snapshot=snap(now),now_at_utc=t(now))
            self.assertEqual(out["status"],"WAIT_CONDITIONS_MATCHED_REQUIRES_NEW_MODEL_P4_AUTH")
            self.assertFalse(out["authorized_buy"])
            self.assertEqual(out["model_calls"],0)
            evidence=[r for r in logs(j) if r["phase"]=="WAIT_RECHECK"]
            self.assertEqual(len(evidence),1)
            self.assertEqual(evidence[0]["result"],"PASS")
            self.assertEqual(evidence[0]["data"]["watch_evaluated_conditions"],3)
            # Cannot duplicate the same bar, or trigger a new paid call.
            self.assertEqual(observe_wait(journal=j,series_id=SID,candidate_id=CID,
                snapshot=snap(now),now_at_utc=t(now))["status"],
                "WAIT_TRIGGER_ALREADY_RECORDED_REQUIRES_NEW_MODEL_AUTH")
            finish=finish_wait(journal=j,series_id=SID,candidate_id=CID,
                now_at_utc=t(datetime(2026,10,12,7,15,tzinfo=timezone.utc)))
            self.assertTrue(finish["historical_trigger_proven"])
            self.assertFalse(finish["authorized_buy"])
            self.assertEqual(len([r for r in logs(j) if r["phase"]=="WAIT_EXPIRY"]),1)

    def test_wait_failed_step_and_same_bar_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as td:
            j=Path(td);seed(j)
            now=datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)
            a=observe_wait(journal=j,series_id=SID,candidate_id=CID,
                           snapshot=snap(now,close=2.10),now_at_utc=t(now))
            self.assertEqual(a["status"],"WAIT_VALID_5M_TICK_NOT_YET_MATCHED")
            self.assertEqual(observe_wait(journal=j,series_id=SID,candidate_id=CID,
                 snapshot=snap(now,close=2.115),now_at_utc=t(now))["status"],
                 "WAIT_SAME_CLOSED_5M_ALREADY_EVALUATED")
            self.assertEqual(len([r for r in logs(j) if r["phase"]=="WAIT_RECHECK"]),1)

    def test_future_late_wrong_coin_and_missing_volume_do_not_fabricate_buy(self):
        with tempfile.TemporaryDirectory() as td:
            j=Path(td);seed(j)
            now=datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)
            for altered in (
                snap(now,pair="ETH/EUR"),
                dict(snap(now),known_at_utc=t(now+timedelta(minutes=2))),
                snap(now,volume=0),
                snap(now,close=2.11),
            ):
                result=observe_wait(journal=j,series_id=SID,candidate_id=CID,
                    snapshot=altered,now_at_utc=t(now))
                self.assertFalse(result["authorized_buy"])
            self.assertFalse(any(r["phase"]=="PAPER_FILL" for r in logs(j)))

    def test_full_wait_grammar_with_less_than_spread_and_true_zero_volume(self):
        conditions=[
            {"metric":"last_eur","op":">","value":2.09},
            {"metric":"bid_eur","op":">=","value":2.0},
            {"metric":"spread_pct","op":"<","value":1.0},
            {"metric":"closed_1m_volume_ratio_5","op":">=","value":0.0},
            {"metric":"closed_15m_volume_ratio_4","op":"<=","value":0.5},
            {"metric":"closed_5m_close_eur","op":">","value":2.111},
        ]
        with tempfile.TemporaryDirectory() as td:
            j=Path(td);seed(j,conditions=conditions)
            now=datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)
            observation=snap(now)
            observation["values"].update({
                "last_eur":2.10,"bid_eur":2.09,"spread_pct":0.0,
                "closed_1m_volume_ratio_5":0.0,
                "closed_15m_volume_ratio_4":0.4,
            })
            result=observe_wait(journal=j,series_id=SID,candidate_id=CID,
                                snapshot=observation,now_at_utc=t(now))
            self.assertEqual(result["status"],"WAIT_CONDITIONS_MATCHED_REQUIRES_NEW_MODEL_P4_AUTH")
            self.assertEqual(result["condition_count"],6)
            self.assertFalse(result["authorized_buy"])
            self.assertEqual(result["model_calls"],0)

    def test_zro_window_without_real_time_captures_expires_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            j=Path(td);seed(j)
            late=t(datetime(2026,10,12,8,45,tzinfo=timezone.utc))
            out=observe_wait(journal=j,series_id=SID,candidate_id=CID,
                             snapshot=snap(datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)),
                             now_at_utc=late)
            self.assertEqual(out["status"],
               "WAIT_EXPIRED_UNKNOWN_WITH_UNPROVEN_MISSED_OPPORTUNITY")
            expiry=[r for r in logs(j) if r["phase"]=="WAIT_EXPIRY"]
            self.assertEqual(len(expiry),1)
            self.assertEqual(expiry[0]["result"],"UNKNOWN")
            self.assertTrue(expiry[0]["data"]["watch_did_not_prove_no_trigger"])
            self.assertEqual(finish_wait(journal=j,series_id=SID,candidate_id=CID,
                                        now_at_utc=late)["status"],"WAIT_EXPIRY_ALREADY_FINAL")

if __name__=="__main__":unittest.main()
