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
            self.assertEqual(result["cases"][0]["status"],"ELIGIBILITY_PENDING_NEXT_CLOSED_BAR_NO_BUY")

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


    def test_not_yet_mature_original_does_not_consume_one_of_five_slots(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=1)
            cohort=mod.select_original_extended(stage/"paper_decisions",stage/"handoff_queue",
                                                ctrl,t-timedelta(minutes=72),set())
            # Candidate is only 13m old; 1-3h closed base cannot exist.
            self.assertEqual(mod.select_due_second_leg(cohort,[],t-timedelta(minutes=72)),None)
            report=root/"budget.json"
            with ExitStack() as s:
                for x in self.mocks(stage,ctrl,t): s.enter_context(x)
                s.enter_context(patch.object(mod,"select_original_extended",return_value=cohort))
                result=mod.main_run(root,PROJECT,report,0,now_fn=lambda:t-timedelta(minutes=72))
            self.assertEqual(len(result["cases"]),0)
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertEqual(result["status"],"COMPLETED_NO_ELIGIBLE_SECOND_LEG_MODEL_EVIDENCE")

    def test_same_original_candidate_rechecked_only_after_new_closed_15m_bar(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=1)
            cohort=mod.select_original_extended(stage/"paper_decisions",
                                                stage/"handoff_queue",ctrl,t,set())
            candidate,original,fresh=mod.select_due_second_leg(cohort,[],t)
            self.assertIsNone(fresh)
            cid=candidate["candidate_id"]
            sample={"source_candidate_id":cid, "status":"ELIGIBILITY_PENDING_NEXT_CLOSED_BAR_NO_BUY",
                    "last_eligibility_checked_at_utc":t.isoformat(),
                    "eligibility_checks":1}
            self.assertIsNone(mod.select_due_second_leg(cohort,[sample],t+timedelta(minutes=5)))
            chosen=mod.select_due_second_leg(cohort,[sample],t+timedelta(minutes=15))
            self.assertEqual(chosen[0]["candidate_id"],cid)
            self.assertIs(chosen[2],sample)
            sample["status"]="MATCHED_RESEARCH_COMPLETE_NOT_PAPER_BUY"
            self.assertIsNone(mod.select_due_second_leg(cohort,[sample],t+timedelta(minutes=15)))
            sample["status"]="ELIGIBILITY_PENDING_NEXT_CLOSED_BAR_NO_BUY"
            self.assertIsNone(mod.select_due_second_leg(cohort,[sample],t+timedelta(hours=4)))

    def test_five_slot_capacity_is_still_frozen_during_ineligible_rechecks(self):
        with tempfile.TemporaryDirectory() as d:
            root,stage,ctrl,t=self.fixture(d,n=5)
            cohort=mod.select_original_extended(stage/"paper_decisions",
                                                stage/"handoff_queue",ctrl,t,set())
            five=[{"source_candidate_id":c["candidate_id"],"status":"ELIGIBILITY_PENDING_NEXT_CLOSED_BAR_NO_BUY",
                    "last_eligibility_checked_at_utc":t.isoformat(),"eligibility_checks":1}
                  for c,_ in cohort]
            self.assertEqual(len(five),5)
            self.assertIsNone(mod.select_due_second_leg(cohort,five,t+timedelta(minutes=2)))
            chosen=mod.select_due_second_leg(cohort,five,t+timedelta(minutes=15))
            self.assertIsNotNone(chosen)
            self.assertEqual(chosen[0]["candidate_id"],five[0]["source_candidate_id"])


    def test_eligibility_reason_diagnostics_are_bounded_boolean_and_not_raw_kraken(self):
        coin={"status":"COMPLETE","observed_at_utc":"2026-10-11T10:15:00Z",
              "known_at_utc":"2026-10-11T10:15:07Z",
              "frames":{
                  "1":{"status":"VALID","closed_close_eur":100},
                  "5":{"status":"VALID","volume_ratio_status":"VALID",
                       "closed_close_eur":101},
                  "15":{"status":"VALID","atr_status":"VALID","atr14_eur":2,
                        "closed_close_eur":102},
              }}
        hint={"status":"SECOND_LEG_CONDITIONS_NOT_CONFIRMED",
              "checks":{"base_1_to_3h_rebuilt":True,
                        "closed_reclaim_above_prior_base_high":False,
                        "liquid_eur_spread":True,
                        "accidental_raw_private_key":"UNTRUSTED_NOT_STORED"}}
        data=mod.compact_gate_evidence(hint,coin,[{"start_utc":"2026-10-11T10:00:00Z",
                                                  "close":102,"high":103}])
        self.assertIs(data["checks"]["closed_reclaim_above_prior_base_high"],False)
        self.assertIsNone(data["checks"]["existing_v2r4_volume_confirmed"])
        self.assertEqual(data["required_coin_frames"]["15"]["atr_status"],"VALID")
        self.assertEqual(data["closed_15m_bar_count"],1)
        self.assertEqual(data["latest_closed_15m_start_utc"],"2026-10-11T10:00:00Z")
        serialized=json.dumps(data)
        self.assertNotIn("UNTRUSTED_NOT_STORED",serialized)
        self.assertNotIn("accidental_raw_private_key",serialized)
        self.assertNotIn("atr14_eur",serialized)
        self.assertNotIn("closed_close_eur",serialized)

    def test_missing_pit_remains_unknown_with_source_status_not_market_reject(self):
        coin={"status":"PARTIAL_OR_MISSING","frames":{
                "1":{"status":"STALE","reason":"LAST_CLOSED_BAR_TOO_OLD"},
                "5":{"status":"INCOMPLETE","reason":"INSUFFICIENT_CONTIGUOUS_BARS"},
                "15":{"status":"MISSING","reason":"NO_CLOSED_BARS"}}}
        hint={"status":"UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE"}
        data=mod.compact_gate_evidence(hint,coin,[])
        self.assertEqual(data["second_leg_status"],"UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
        self.assertIsNone(data["checks"]["closed_reclaim_above_prior_base_high"])
        self.assertEqual(data["required_coin_frames"]["15"]["reason"],"NO_CLOSED_BARS")
        self.assertIsNone(data["latest_closed_15m_start_utc"])


class SecondOneShotAuthorizationRegressionTests(unittest.TestCase):
    def test_user_second_consent_is_narrow_and_distinct_from_first(self):
        first=mod.verified_authorization(PROJECT,"FIRST")
        second=mod.verified_authorization(PROJECT,"SECOND")
        self.assertNotEqual(first["approval_label"],second["approval_label"])
        self.assertEqual(second["trial_id"],"SECOND")
        self.assertEqual(second["max_distinct_candidates"],5)
        self.assertEqual(second["max_model_http_attempts_including_retries"],10)
        self.assertEqual(second["max_wait_minutes"],90)
        self.assertTrue(second["immutable_previous_report"])
        with self.assertRaisesRegex(ValueError,"UNKNOWN_OR_UNAPPROVED"):
            mod.verified_authorization(PROJECT,"THIRD")

    def first_report(self,root, *, status="WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED",
                     calls=0, cases=5):
        research=root/"Research"
        research.mkdir(exist_ok=True)
        path=research/mod.FIRST_REPORT_NAME
        prior={"kind":"V3_B_MANUAL_SHADOW5_HTTP10_V1","status":status,
               "model_http_attempts_reserved":calls,
               "completed_matched_reviews":0,
               "cases":[{"status":"ELIGIBILITY_CHECKED_NO_BUY",
                          "source_candidate_id":f"FIRST-ORIGINAL-{i}"}
                        for i in range(cases)],
               "orders":0,"active_v2r4_changed":False,"v3_paper_writer_started":False}
        path.write_text(json.dumps(prior),encoding="utf-8")
        return path

    def test_second_is_blocked_if_first_trial_not_closed_or_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(ValueError,"FIRST_V3B"):
                mod.verify_first_trial_closed(root)
            first=self.first_report(root,status="RUNNING")
            with self.assertRaisesRegex(ValueError,"NOT_CLOSED"):
                mod.verify_first_trial_closed(root)
            prior=json.loads(first.read_text())
            prior["status"]="WINDOW_ELAPSED_OR_FIVE_ORIGINAL_CASES_REVIEWED"
            prior["model_http_attempts_reserved"]=3
            first.write_text(json.dumps(prior))
            with self.assertRaisesRegex(ValueError,"NOT_CLOSED"):
                mod.verify_first_trial_closed(root)
            prior["model_http_attempts_reserved"]=0
            first.write_text(json.dumps(prior))
            mod.verify_first_trial_closed(root)

    def test_second_live_diagnose_zero_budget_does_not_touch_old_journal(self):
        setup=ApprovedV3BShadowTests()
        with tempfile.TemporaryDirectory() as folder:
            root,stage,ctrl,t=setup.fixture(folder,n=1)
            first=self.first_report(root)
            before=first.read_bytes()
            report=root/"Research"/mod.SECOND_REPORT_NAME
            with ExitStack() as stack:
                for scope in setup.mocks(stage,ctrl,t):
                    stack.enter_context(scope)
                result=mod.main_run(root,PROJECT,report,0,trial_id="SECOND",
                                    diagnose_only=True,now_fn=lambda:t)
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertFalse(report.exists())
            self.assertEqual(first.read_bytes(),before)

    def test_second_one_shot_zero_model_never_reuses_old_journal(self):
        setup=ApprovedV3BShadowTests()
        with tempfile.TemporaryDirectory() as folder:
            root,stage,ctrl,t=setup.fixture(folder,n=1)
            first=self.first_report(root)
            before=first.read_bytes()
            report=root/"Research"/mod.SECOND_REPORT_NAME
            with ExitStack() as stack:
                for scope in setup.mocks(stage,ctrl,t):
                    stack.enter_context(scope)
                stack.enter_context(patch.object(mod,"propose_second_leg_review",return_value={
                    "status":"SECOND_LEG_CONDITIONS_NOT_CONFIRMED",
                    "request_model_recheck_only":False}))
                result=mod.main_run(root,PROJECT,report,0,trial_id="SECOND",now_fn=lambda:t)
            self.assertEqual(result["trial_id"],"SECOND")
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertEqual(result["status"],"COMPLETED_NO_ELIGIBLE_SECOND_LEG_MODEL_EVIDENCE")
            self.assertEqual(first.read_bytes(),before)
            self.assertNotEqual(report.read_bytes(),before)
            with self.assertRaisesRegex(ValueError,"EXISTING_REPORT_NO_RETRY"):
                mod.main_run(root,PROJECT,report,0,trial_id="SECOND",now_fn=lambda:t)

    def test_second_excludes_all_first_trial_original_candidate_ids(self):
        setup=ApprovedV3BShadowTests()
        with tempfile.TemporaryDirectory() as folder:
            root,stage,ctrl,t=setup.fixture(folder,n=5)
            candidates=mod.select_original_extended(stage/"paper_decisions",
                stage/"handoff_queue",ctrl,t,set())
            self.assertEqual(len(candidates),5)
            first=self.first_report(root)
            data=json.loads(first.read_text())
            for old_case,(candidate,_) in zip(data["cases"],candidates):
                old_case["source_candidate_id"]=candidate["candidate_id"]
            first.write_text(json.dumps(data))
            excluded=mod.verify_first_trial_closed(root)
            self.assertEqual(len(excluded),5)
            self.assertEqual(mod.select_original_extended(stage/"paper_decisions",
                stage/"handoff_queue",ctrl,t,excluded),[])
            report=root/"Research"/mod.SECOND_REPORT_NAME
            with ExitStack() as stack:
                for patcher in setup.mocks(stage,ctrl,t):
                    stack.enter_context(patcher)
                output=mod.main_run(root,PROJECT,report,0,trial_id="SECOND",
                                    diagnose_only=True,now_fn=lambda:t)
            self.assertEqual(output["original_extended_candidate_count"],0)
            self.assertFalse(report.exists())

    def test_missing_unique_first_ids_blocks_second_not_recycles(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            first=self.first_report(root)
            original=json.loads(first.read_text())
            original["cases"][4].pop("source_candidate_id")
            first.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError,"MISSING_SOURCE_IDS"):
                mod.verify_first_trial_closed(root)
            original["cases"][4]["source_candidate_id"]=original["cases"][0]["source_candidate_id"]
            first.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_UNKNOWN"):
                mod.verify_first_trial_closed(root)

    def test_second_wrong_path_cannot_alias_first_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.first_report(root)
            with self.assertRaisesRegex(ValueError,"WRONG_REPORT_NAME"):
                mod.main_run(root,PROJECT,root/"Research"/mod.FIRST_REPORT_NAME,0,
                             trial_id="SECOND",diagnose_only=True)



if __name__=="__main__":
    unittest.main()
