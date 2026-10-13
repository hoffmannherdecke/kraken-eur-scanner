"""V3 after-28h snapshot: no false tradeability, no artificial extensions."""
from __future__ import annotations
import hashlib
import json
import unittest
from datetime import datetime,timedelta,timezone

from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
from paper_evaluator.v3_paper_post_canary_evidence_verdict_v1 import (
    verdict,WATCH,SMOKE,ORIGINAL_ACTIVE,
)
END="2026-10-13T12:00:12.2795431Z"
SMOKE_AT="2026-10-12T10:32:40Z"
WATCH_AT="2026-10-12T05:27:31Z"
CHECKS={
    "fresh_original_candidate":True,
    "complete_real_closed_coin_frames":True,
    "positive_coin_atr":True,
    "structural_invalidating_low_below_ask":True,
    "current_online_kraken_spot_eur":True,
    "kraken_order_minimum_pass":True,
    "fresh_noninverted_ask_bid":True,
    "execution_spread_at_most_half_percent":True,
}
def event(series,phase,result,*,cid=None,pair=None,event_time=None,
          known=None,key="FIRST",data=None):
    if series==SMOKE:
        cid=cid or "20261012-103240-RENDER-EUR-r2405499019105"
        pair=pair or "RENDER/EUR"
        event_time=event_time or SMOKE_AT
    else:
        cid=cid or "WATCH-ORIGINAL-001"
        pair=pair or "ZRO/EUR"
        event_time=event_time or WATCH_AT
    known=known or event_time
    p=make_receipt(series_id=series,revision=REVISION,candidate_id=cid,
                   pair=pair,event_time_utc=event_time,known_at_utc=known,
                   phase=phase,result=result,data=data or {},event_key=key)
    eid=hashlib.sha256("|".join(str(p[k]) for k in
        ("series_id","candidate_id","phase","event_key")).encode()).hexdigest()
    raw=json.dumps(p,sort_keys=True,separators=(",",":")).encode()+b"\n"
    return {"series_id":series,"event_id":eid,
            "content_sha256":hashlib.sha256(raw).hexdigest(),"payload":p}

def smoke():
    return [
        event(SMOKE,"SCANNER_CAPTURE","SEEN",known="2026-10-12T10:33:28Z",
              data={"source_status":"ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY"}),
        event(SMOKE,"FULL_REVIEW_ELIGIBILITY","UNKNOWN",
              known="2026-10-12T10:33:28Z",
              data={"review_status":"UNKNOWN_NO_FRESH_COIN_KRAKEN_CONSUMER_INPUT"}),
        event(SMOKE,"SOURCE_INPUT","PASS",key="FRESHRECHECK",
              known="2026-10-12T10:33:29Z",data={"source_status":"COMPLETE"}),
        event(SMOKE,"FULL_REVIEW_ELIGIBILITY","PASS",key="FRESHRECHECK",
              known="2026-10-12T10:33:29Z",
              data={"review_status":"INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY",
                    "review_checks":CHECKS}),
        event(SMOKE,"MODEL_REQUEST","SKIP",key="FRESHRECHECK",
              known="2026-10-12T10:33:29Z",
              data={"source_status":"PREFLIGHT_NO_MODEL"}),
    ]
def watch():
    return [event(WATCH,"SCANNER_CAPTURE","SEEN")]
def run(rows=None,at="2026-10-12T14:00:00Z",active=None,host_ack=False):
    return verdict(cloud_rows=rows if rows is not None else watch()+smoke(),
                   as_of_utc=at,observer_deadline_utc=END,
                   active_paper_series=active if active is not None else
                     [ORIGINAL_ACTIVE],physical_observer_end_ack=host_ack)

class After28hVerdictTests(unittest.TestCase):
    def test_real_oneshot_means_only_one_technical_e2e_not_trade_or_economic(self):
        r=run()
        self.assertEqual(r["separate_series"][SMOKE]["cloud_rows"],5)
        self.assertTrue(r["separate_series"][SMOKE]["one_shot_real_p0_proof"])
        self.assertEqual(r["separate_series"][SMOKE]["p0_validations_passed"],8)
        self.assertEqual(r["separate_series"][WATCH]["unique_real_originals"],1)
        self.assertEqual(r["observation_window"],"AWAIT_FIXED_DEADLINE")
        self.assertEqual(r["watcher_followup_coverage"]["6"]["due_missing_or_pending"],1)
        self.assertEqual(r["watcher_followup_coverage"]["24"]["not_yet_due"],1)
        self.assertEqual(r["watcher_followup_coverage"]["72"]["not_yet_due"],1)
        self.assertEqual(r["watcher_24h_mature_cases"],0)
        self.assertEqual(r["watcher_mature_virtual_fee_adjusted_paper_net_count"],0)
        self.assertEqual(r["watcher_p4_model_backed_buy_count"],0)
        self.assertTrue(r["only_v2r4_active_as_reported"])
        self.assertFalse(r["strategy_v3_auto_activation_authorized"])
        self.assertFalse(r["automatic_model_api_authorized"])
        self.assertEqual(r["new_schedules"],0)

    def test_exact_due_clocks_and_recovery_do_not_fake_late_trades(self):
        x=run(at="2026-10-12T10:53:00Z")
        first=x["watcher_cases"][0]
        self.assertEqual(first["followup_due_at_utc"]["6"],
                         "2026-10-12T11:27:31+00:00")
        self.assertEqual(first["followup_due_at_utc"]["24"],
                         "2026-10-13T05:27:31+00:00")
        self.assertEqual(first["recovery_until_utc"]["6"],
                         "2026-10-12T12:27:31+00:00")
        self.assertEqual(x["watcher_next_unmatured_horizon"]["hours"],6)
        self.assertEqual(x["watcher_followup_coverage"]["6"]["not_yet_due"],1)
        self.assertEqual(x["watcher_due_missing_past_60m_recovery"],{})
        pending=run(at="2026-10-12T11:30:00Z")
        self.assertEqual(pending["watcher_followup_coverage"]["6"]["due_missing_or_pending"],1)
        self.assertEqual(pending["watcher_due_missing_past_60m_recovery"],{})
        overdue=run(at="2026-10-12T12:28:00Z")
        self.assertEqual(overdue["watcher_due_missing_past_60m_recovery"]["6"],1)
        self.assertEqual(overdue["watcher_mature_virtual_fee_adjusted_paper_net_count"],0)
        self.assertFalse(overdue["strategy_v3_auto_activation_authorized"])

    def test_original_cloud_timestamps_20261012_are_prospectively_due_not_now(self):
        eigen="2026-10-12T05:25:50.736889Z"
        zro="2026-10-12T06:42:19.705999Z"
        rows=smoke()+[
            event(WATCH,"SCANNER_CAPTURE","SEEN",
                  cid="EIGEN-REAL-001",pair="EIGEN/EUR",event_time=eigen,known=eigen),
            event(WATCH,"SCANNER_CAPTURE","SEEN",
                  cid="ZRO-REAL-001",pair="ZRO/EUR",event_time=zro,known=zro)]
        r=run(rows=rows,at="2026-10-12T10:53:00Z")
        self.assertEqual(r["watcher_followup_coverage"]["6"]["not_yet_due"],2)
        self.assertEqual(r["watcher_followup_coverage"]["24"]["not_yet_due"],2)
        self.assertEqual(r["watcher_next_unmatured_horizon"]["pair"],"EIGEN/EUR")
        self.assertEqual(r["watcher_next_unmatured_horizon"]["due_at_utc"],
                         "2026-10-12T11:25:50.736889+00:00")
        due={a["pair"]:a["followup_due_at_utc"] for a in r["watcher_cases"]}
        self.assertEqual(due["ZRO/EUR"]["24"],
                         "2026-10-13T06:42:19.705999+00:00")
        self.assertIn("BLOCKED",r["release"])

    def test_after_deadline_without_physical_stop_or_24h_is_not_pass(self):
        r=run(at="2026-10-13T12:01:00Z")
        self.assertEqual(r["observation_window"],
                         "ENDED_TIME_ONLY_PHYSICAL_STOP_NOT_VERIFIED")
        self.assertEqual(r["watcher_followup_coverage"]["24"]["due_missing_or_pending"],1)
        self.assertIn("REVIEW_MISSING_OR_CENSORED_24H_DATA",
                      r["next_research_disposition"])
        self.assertIn("BLOCKED",r["release"])
        ack=run(at="2026-10-13T12:01:00Z",host_ack=True)
        self.assertEqual(ack["observation_window"],"WINDOW_ENDED_HOST_STOP_ACK_SUPPLIED")
        self.assertFalse(ack["strategy_v3_auto_activation_authorized"])

    def test_prospectively_mature_no_buy_is_opportunity_only_never_net_pnl(self):
        rows=watch()+smoke()
        for h in (6,24):
            known=(datetime.fromisoformat(WATCH_AT.replace("Z","+00:00"))+
                   timedelta(hours=h,minutes=2)).isoformat()
            rows.append(event(WATCH,f"FOLLOWUP_{h}H","MATURE_COMPLETE",
                              known=known,key=f"NOBUY{h}H",
                              data={"followup_source":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                                    "path_contiguous_1m_verified":True,
                                    "source_status":"NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL",
                                    "mfe_pct":17.0,"mae_pct":-8.0,
                                    "position_net_pnl_eur":None,
                                    "position_net_return_pct":None}))
        r=run(rows,at="2026-10-13T12:03:00Z",host_ack=True)
        self.assertEqual(r["watcher_24h_mature_cases"],1)
        self.assertEqual(r["watcher_followup_coverage"]["6"]["mature_complete"],1)
        self.assertEqual(r["watcher_mature_virtual_fee_adjusted_paper_net_count"],0)
        self.assertEqual(r["watcher_followup_coverage"]["72"]["not_yet_due"],1)
        self.assertEqual(r["next_research_disposition"],
                         "REVIEW_FEE_ADJUSTED_DECISION_QUALITY_WITH_EXISTING_CONTROL_PLANE")
        self.assertFalse(r["strategy_v3_auto_activation_authorized"])

    def test_no_buy_with_forged_profit_or_premature_or_censored_gap(self):
        complete=event(WATCH,"FOLLOWUP_6H","MATURE_COMPLETE",
                       known="2026-10-12T11:29:00Z",key="NOBUY6H",
                       data={"followup_source":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                             "path_contiguous_1m_verified":True,
                             "position_net_pnl_eur":18.0})
        with self.assertRaisesRegex(ValueError,"non-buy"):
            run(watch()+smoke()+[complete])
        cens=event(WATCH,"FOLLOWUP_24H","CENSORED",
                  known="2026-10-13T06:30:00Z",key="NOBUY24H",
                  data={"followup_source":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                        "censor_reason":"CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH"})
        r=run(watch()+smoke()+[cens],at="2026-10-13T12:03:00Z")
        self.assertEqual(r["watcher_followup_coverage"]["24"]["censored"],1)
        self.assertEqual(r["watcher_24h_mature_cases"],0)
        self.assertEqual(r["watcher_mature_virtual_fee_adjusted_paper_net_count"],0)
        self.assertEqual(r["watcher_24h_censored_cases"],1)
        self.assertEqual(r["watcher_24h_not_yet_due_cases"],0)
        self.assertEqual(r["next_research_disposition"],
                         "REVIEW_MISSING_OR_CENSORED_24H_DATA_NO_FALSE_PNL")
        early=event(WATCH,"FOLLOWUP_24H","CENSORED",
                    known="2026-10-12T12:00:00Z",key="NOBUY24H",
                    data={"censor_reason":"FAKE"})
        with self.assertRaisesRegex(ValueError,"premature"):
            run(watch()+smoke()+[early])

    def test_late_genuine_original_is_pending_not_fake_24h_completion(self):
        rows=smoke()+[event(WATCH,"SCANNER_CAPTURE","SEEN",
                            cid="LATE-REAL-001",pair="EIGEN/EUR",
                            event_time="2026-10-13T09:00:00Z",
                            known="2026-10-13T09:00:00Z")]
        r=run(rows=rows,at="2026-10-13T12:04:00Z",host_ack=True)
        self.assertEqual(r["watcher_24h_not_yet_due_cases"],1)
        self.assertEqual(r["next_research_disposition"],
                         "REVIEW_24H_PENDING_NO_ARTIFICIAL_CANARY_EXTENSION")
        self.assertEqual(r["watcher_24h_mature_cases"],0)
        self.assertFalse(r["strategy_v3_auto_activation_authorized"])

    def test_no_originals_is_not_fee_adjusted_trade_evidence(self):
        r=run(rows=smoke(),at="2026-10-13T12:04:00Z",host_ack=True)
        self.assertEqual(r["watcher_24h_mature_cases"],0)
        self.assertEqual(r["next_research_disposition"],
                         "REVIEW_NO_MATURE_24H_RESULTS_NO_ECONOMIC_CLAIM")
        self.assertFalse(r["strategy_v3_auto_activation_authorized"])

    def test_cloud_receipt_event_ids_unique_and_original_metadata_consistent(self):
        x=watch()+smoke()
        with self.assertRaisesRegex(ValueError,"duplicate"):
            run(x+[x[0]])
        bad=json.loads(json.dumps(x))
        bad[0]["event_id"]="0"*64
        with self.assertRaisesRegex(ValueError,"tampered"):
            run(bad)
        wrong_digest=json.loads(json.dumps(x))
        wrong_digest[0]["content_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"content digest"):
            run(wrong_digest)
        altered_result=json.loads(json.dumps(x))
        altered_result[0]["payload"]["data"]["injected"]="false-trade-proof"
        with self.assertRaisesRegex(ValueError,"content digest"):
            run(altered_result)
        mixed=json.loads(json.dumps(x))
        mixed[0]["payload"]["pair"]="ETH/EUR"
        with self.assertRaises(ValueError):
            run(mixed+[event(WATCH,"SOURCE_INPUT","PASS")])
        incomplete=x[:-1]
        self.assertFalse(run(incomplete)["separate_series"][SMOKE]["one_shot_real_p0_proof"])

    def test_audit_sentinel_ignored_and_cannot_have_followups(self):
        cid="V3-INPUT-REJECT-"+"a"*32
        audit=event(WATCH,"SCANNER_CAPTURE","UNKNOWN",cid=cid,
                    pair="UNMAPPED/EUR",key="ROUTERREJECT")
        r=run(watch()+smoke()+[audit])
        self.assertEqual(r["separate_series"][WATCH]["unique_real_originals"],1)
        bad=event(WATCH,"FOLLOWUP_6H","PENDING",cid=cid,
                  pair="UNMAPPED/EUR",known="2026-10-12T11:28:00Z")
        with self.assertRaisesRegex(ValueError,"synthetic"):
            run(watch()+smoke()+[audit,bad])

if __name__=="__main__":
    unittest.main()
