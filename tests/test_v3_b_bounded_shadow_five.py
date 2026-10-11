"""Adversarial bounded 5-case / 10 HTTP V3-B approval + Mini-PC bridge tests."""
import json
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v3_b_bounded_shadow_five as mod
from paper_evaluator import v3_bounded_four_candidate_compare as old


PROJECT=Path(__file__).resolve().parents[1]


class ApprovedV3BShadowTests(unittest.TestCase):
    def setUp(self):
        self.auth=mod.verified_authorization(PROJECT)
        self.assertEqual(self.auth["max_distinct_candidates"],5)
        self.assertEqual(self.auth["max_model_http_attempts_including_retries"],10)
        self.assertFalse(self.auth["no_orders"] is False)

    def fixture(self,folder,n=5):
        root=Path(folder)
        stage=root/"Runtime"/"v2r4-paper-stage-d8b35a8ec2e6"
        dec=stage/"paper_decisions"
        queue=stage/"handoff_queue"
        dec.mkdir(parents=True)
        queue.mkdir()
        (root/"Secrets").mkdir()
        (root/"Secrets"/"openai-api-key.txt").write_text("MOCK_ONLY_RESEARCH_API_TOKEN_NOT_REAL_1234")
        t=datetime(2026,10,11,12,tzinfo=timezone.utc)
        ctrl={"series_id":mod.EXPECTED_SERIES,"enabled":True,
              "paper_only":True,"real_money_actions_enabled":False,
              "series_started_at_utc":(t-timedelta(days=2)).isoformat(),
              "strategy_revision":old.REVISION}
        spec={"strategy_revision":old.REVISION,
              "entry":{"scout_notional_eur":50,"stage2_notional_eur":50},
              "fees":{"taker_pct_per_side":0.6}}
        (stage/"paper_strategy_spec.json").write_text(json.dumps(spec))
        for k,coin in enumerate(("XBT","ETH","SOL","ADA","AVAX")[:n]):
            stamp=t-timedelta(minutes=85,seconds=k)
            event_ts=int(stamp.timestamp())
            run=121000+k
            cid=f"{stamp:%Y%m%d-%H%M%S}-{coin}-EUR-r{run}"
            c={"candidate_id":cid,"queue_id":f"{run}:{coin}-EUR:{event_ts}",
               "source_scanner_run_id":run,"event_ts":event_ts,
               "event_time_utc":stamp.isoformat(),"pair":coin+"/EUR",
               "altname":coin+"EUR","action":"REVIEW_ONLY_NOT_ORDER",
               "scanner_candidate":{},"scanner_market_context":{}}
            row={"candidate_id":cid,"pair":c["pair"],"series_id":mod.EXPECTED_SERIES,
                 "candidate_event_time_utc":stamp.isoformat(),
                 "decision":{"decision":"REJECT","setup_lane":"EXTENDED"}}
            (queue/(cid+".json")).write_text(json.dumps(c))
            (dec/(cid+".json")).write_text(json.dumps(row))
        return root,stage,ctrl,t

    def mocks(self,stage,ctrl,t):
        ticker={"ask":10.0,"bid":9.99,"last":9.995,"spread_pct":0.1}
        coin={"kind":"SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
              "known_at_utc":t.isoformat(),"status":"COMPLETE"}
        hint={"status":mod.ELIGIBLE,"request_model_recheck_only":True,
              "checks":{"fresh_reclaim":True}}
        def fake_assessment(*xs):
            mod.evaluate.http_json("https://api.openai.com/v1/responses","POST")
            return {"decision":"REJECT","setup_lane":"EXTENDED",
                    "reason_codes":[],"missing_triggers":[],"ttl_minutes":0,
                    "stage2_ttl_minutes":0,"watch_conditions":[]},{}
        return (
            patch.object(mod,"discover_active_paper_runtime",return_value=(stage,ctrl)),
            patch.object(mod,"freeze_runtime_provenance",return_value={}),
            patch.object(mod.evaluate,"kraken_ticker",return_value=ticker),
            patch.object(mod,"build_context",return_value={"kraken_pair_metadata":{
                "available":True,"status":"online","ordermin":"0.001","costmin":"0.5"}}),
            patch.object(mod,"fetch_public_entry_evidence",return_value=coin),
            patch.object(mod,"closed_15m_history",return_value=[]),
            patch.object(mod,"propose_second_leg_review",return_value=hint),
            patch.object(mod,"attach_to_future_evaluator",
                         side_effect=lambda c,ctx,ev,at:{**ctx,"candidate_entry_evidence":ev}),
            patch.object(mod.evaluate,"call_evaluator",side_effect=fake_assessment),
            patch.object(mod.evaluate,"http_json",return_value={"id":"MOCK"}),
        )

    def test_true_5_case_10_request_ceiling_and_one_policy_delta(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d)
            report=root/"budget.json"
            contexts=[]
            def evaluator(candidate,ticker,context,spec,control):
                contexts.append((candidate["candidate_id"],dict(context)))
                mod.evaluate.http_json("https://api.openai.com/v1/responses","POST")
                return {"decision":"REJECT","setup_lane":"EXTENDED","reason_codes":[],
                        "missing_triggers":[],"ttl_minutes":0,"stage2_ttl_minutes":0,
                        "watch_conditions":[]},{}
            with ExitStack() as s:
                for x in self.mocks(stage,ctrl,t):s.enter_context(x)
                s.enter_context(patch.object(mod.evaluate,"call_evaluator",side_effect=evaluator))
                result=mod.main_run(root,PROJECT,report,0,now_fn=lambda:t)
            self.assertEqual(len(result["cases"]),5)
            self.assertEqual(result["completed_matched_reviews"],5)
            self.assertEqual(result["model_http_attempts_reserved"],10)
            self.assertEqual(len(contexts),10)
            self.assertTrue(all(contexts[i][0]==contexts[i+1][0] for i in range(0,10,2)))
            self.assertTrue(all(
                "v3_b_new_independent_second_leg_review_only" not in contexts[i][1]
                and "v3_b_new_independent_second_leg_review_only" in contexts[i+1][1]
                for i in range(0,10,2)))
            self.assertEqual(result["orders"],0)
            self.assertFalse(result["active_v2r4_changed"])
            self.assertFalse(result["v3_paper_writer_started"])
            self.assertEqual(json.loads(report.read_text())["model_http_attempts_reserved"],10)
            with self.assertRaisesRegex(ValueError,"EXISTING_REPORT_NO_RETRY"):
                mod.main_run(root,PROJECT,report,0,now_fn=lambda:t)

    def test_readonly_diagnose_never_creates_journal_or_calls_model(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=1)
            report=root/"budget.json"
            with ExitStack() as s:
                for x in self.mocks(stage,ctrl,t):s.enter_context(x)
                result=mod.main_run(root,PROJECT,report,0,
                                    diagnose_only=True,now_fn=lambda:t)
            self.assertEqual(result["original_extended_candidate_count"],1)
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertFalse(report.exists())

    def test_ineligible_new_base_never_uses_http_model_budget(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=1)
            report=root/"budget.json"
            with ExitStack() as s:
                for x in self.mocks(stage,ctrl,t):s.enter_context(x)
                s.enter_context(patch.object(mod,"propose_second_leg_review",return_value={
                    "status":"SECOND_LEG_CONDITIONS_NOT_CONFIRMED",
                    "request_model_recheck_only":False}))
                result=mod.main_run(root,PROJECT,report,0,now_fn=lambda:t)
            self.assertEqual(result["completed_matched_reviews"],0)
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertEqual(result["cases"][0]["status"],"ELIGIBILITY_CHECKED_NO_BUY")

    def test_retries_cannot_exceed_2_requests_per_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=2)
            report=root/"budget.json"
            def two_requests_then_more(*args):
                # Simulate the frozen evaluator's own retry before the 2nd arm.
                mod.evaluate.http_json("https://api.openai.com/v1/responses","POST")
                mod.evaluate.http_json("https://api.openai.com/v1/responses","POST")
                return {"decision":"REJECT","setup_lane":"EXTENDED",
                        "reason_codes":[],"missing_triggers":[],"ttl_minutes":0,
                        "stage2_ttl_minutes":0,"watch_conditions":[]},{}
            with ExitStack() as s:
                for x in self.mocks(stage,ctrl,t):s.enter_context(x)
                s.enter_context(patch.object(mod.evaluate,"call_evaluator",side_effect=two_requests_then_more))
                result=mod.main_run(root,PROJECT,report,0,now_fn=lambda:t)
            self.assertEqual(result["model_http_attempts_reserved"],2)
            self.assertEqual(len(result["cases"]),1)
            self.assertEqual(result["status"],"STOPPED_BUDGET_CAP_NO_AUTO_RETRY")
            self.assertEqual(result["orders"],0)

    def test_no_unapproved_series_or_stale_double_or_wrong_lanes(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=1)
            decisions=stage/"paper_decisions"
            queue=stage/"handoff_queue"
            cases=mod.select_original_extended(decisions,queue,ctrl,t,set())
            self.assertEqual(len(cases),1)
            self.assertEqual(mod.select_original_extended(
                decisions,queue,ctrl,t,{cases[0][0]["candidate_id"]}),[])
            rowpath=next(decisions.glob("*.json"))
            row=json.loads(rowpath.read_text())
            row["decision"]["setup_lane"]="IGNITION"
            rowpath.write_text(json.dumps(row))
            self.assertEqual(mod.select_original_extended(decisions,queue,ctrl,t,set()),[])
            row["decision"]["setup_lane"]="EXTENDED"
            row["series_id"]="PAPER-V2R4-FOREIGN"
            rowpath.write_text(json.dumps(row))
            self.assertEqual(mod.select_original_extended(decisions,queue,ctrl,t,set()),[])


if __name__=="__main__":
    unittest.main()
