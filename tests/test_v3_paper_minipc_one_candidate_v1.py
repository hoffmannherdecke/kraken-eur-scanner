"""Physical canary contract: real model boundary injectable; never spend in CI."""
import json
import tempfile
import unittest
from pathlib import Path
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import (
    one_candidate,REVISION,reserve_before_http,APPROVED_MODEL,
    MAX_PROMPT_UTF8_BYTES,MAX_OUTPUT_TOKENS,MAX_ESTIMATED_COST_USD,
)
from paper_evaluator.v3_paper_context_bridge_v1 import fuse_existing_sources
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
from tests.test_v3_experimental_paper_initial_review_v1 import fixture
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as full_fixture
from tests.test_v2r4_v3_entry_handoff_probe import dt

SID="PAPER-V3-ONE-CANARY-TEST"

def valid_approval():
    return {"kind":"V3_MINIPC_SINGLE_CANDIDATE_MODEL_HTTP_USER_APPROVAL_V1",
            "strategy_revision":REVISION,"series_id":SID,"paper_only":True,
            "real_money_actions":False,"max_model_http_attempts_including_retries":1,
            "max_candidates":1,"explicit_user_new_budget_approval":True,
            "consumed_pr186_budget":False,
            "model":APPROVED_MODEL,
            "max_input_utf8_bytes":MAX_PROMPT_UTF8_BYTES,
            "max_output_tokens":MAX_OUTPUT_TOKENS,
            "estimated_usd_ceiling":MAX_ESTIMATED_COST_USD,
            "expires_at_utc":"2099-01-01T00:00:00Z",
            "unique_approval_id":"PAPER-CANARY-FIXTURE-NOT-REAL"}

def fake_acquire(_):return tuple(fixture()[1:])
def fake_model(prompt,_):
    self_model=full_fixture()[-1]
    self_model.update(candidate_id="V3-INITIAL-EUR-1",
                      decision_at_utc=dt(12),setup_lane="IGNITION")
    return self_model,{"response_id":"test-model-response","model":"test-no-HTTP"}

def stage_scanner_original(journal,candidate):
    """Exactly the two immutable FIRST receipts from the separate intake stage."""
    root={
        "series_id":SID,"revision":REVISION,
        "candidate_id":candidate["candidate_id"],"pair":candidate["pair"],
        "event_time_utc":candidate["event_time_utc"],
        "known_at_utc":dt(12),"event_key":"FIRST",
    }
    store_receipt_explicitly(journal,make_receipt(
        **root,phase="SCANNER_CAPTURE",result="SEEN",
        data={"candidate_origin":"SCANNER",
              "source_status":"ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY",
              "raw_reason_codes":[]}))
    store_receipt_explicitly(journal,make_receipt(
        **root,phase="FULL_REVIEW_ELIGIBILITY",result="PASS",
        data={"candidate_origin":"SCANNER",
              "review_status":"INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY"}))

class V3MiniPCOneCandidateTests(unittest.TestCase):
    def test_source_only_public_preflight_records_three_phases_and_no_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            cand=fixture()[0]
            r=one_candidate(candidate=cand,series_id=SID,
                            local_receipts=journal,model_reservations=budgets,
                            acquire=fake_acquire,clock=lambda:dt(12))
            self.assertEqual(r["status"],"V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            self.assertEqual(len(list(journal.glob("*.json"))),4)
            self.assertFalse(list(budgets.glob("*.json")))
            again=one_candidate(candidate=cand,series_id=SID,
                            local_receipts=journal,model_reservations=budgets,
                            acquire=fake_acquire,clock=lambda:dt(12))
            self.assertEqual(again["status"],"V3_CANDIDATE_ALREADY_JOURNALED_NO_REPROCESS")
            self.assertEqual(len(list(journal.glob("*.json"))),4)

    def test_real_staged_original_can_expire_during_kraken_before_api_reservation(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); journal=root/"journal";budget=root/"budget"
            journal.mkdir();budget.mkdir()
            candidate=dict(fixture()[0],entry_origin="SCANNER")
            stage_scanner_original(journal,candidate)
            # Let genuine public evidence and eligibility succeed at the
            # original clock, then simulate a slow prompt construction
            # finishing after the 10-minute original is no longer fresh.
            from unittest.mock import patch
            from paper_evaluator import v3_paper_minipc_one_candidate_v1 as module
            current=[dt(12)]
            original_prompt=module.build_v3_paper_full_model_prompt
            def slow_prompt(**kwargs):
                prompt=original_prompt(**kwargs)
                current[0]=dt(900)
                return prompt
            with patch.object(module,"build_v3_paper_full_model_prompt",
                              side_effect=slow_prompt):
                result=one_candidate(
                    candidate=candidate,series_id=SID,
                    local_receipts=journal,model_reservations=budget,
                    approval=valid_approval(),model_key="sk-CI-NO-REAL-KEY-123456789012",
                    clock=lambda:current[0],acquire=fake_acquire,
                    model_client=lambda *_:self.fail("no model after original expires"),
                    allow_model=True,admit_staged_scanner_one_approved_model=True)
            self.assertEqual(result["status"],
                "ORIGINAL_EXPIRED_BEFORE_MODEL_HTTP_NO_SPEND")
            self.assertFalse(list(budget.glob("*.reserved.json")))
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertTrue(any(r["phase"]=="MODEL_REQUEST"
                and r["data"].get("phase_failure_stage")==
                    "ORIGINAL_EXPIRED_AFTER_KRAKEN_NO_API_SPEND" for r in rows))

    def test_explicit_staged_scanner_real_pit_recheck_only_once_without_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            cand=dict(fixture()[0],entry_origin="SCANNER")
            stage_scanner_original(journal,cand)
            result=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                acquire=fake_acquire,clock=lambda:dt(12),
                admit_staged_scanner_no_model=True)
            self.assertEqual(result["status"],
                             "V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual(len(rows),5)
            self.assertEqual(len([r for r in rows if r["phase"]=="SCANNER_CAPTURE"]),1)
            p0=[r for r in rows if r["phase"]=="FULL_REVIEW_ELIGIBILITY"]
            self.assertEqual({r["event_key"] for r in p0},{"FIRST","FRESHRECHECK"})
            self.assertEqual({r["phase"] for r in rows if r["event_key"]=="FRESHRECHECK"},
                             {"SOURCE_INPUT","FULL_REVIEW_ELIGIBILITY","MODEL_REQUEST"})
            self.assertFalse(list(budgets.glob("*.json")))
            called=[]
            def fail_if_called(_):
                called.append(True)
                raise AssertionError("duplicate public Kraken should be blocked")
            again=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                acquire=fail_if_called,clock=lambda:dt(12),
                admit_staged_scanner_no_model=True)
            self.assertEqual(again["status"],"NO_UNIQUE_UNPROCESSED_STAGED_SCANNER_NO_RECHECK")
            self.assertFalse(called)
            self.assertEqual(len(list(journal.glob("*.json"))),5)

    def test_previously_deferred_original_no_model_source_recheck_is_once_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            cand=dict(fixture()[0],entry_origin="SCANNER",deferred_recheck=True)
            first=dict(series_id=SID,revision=REVISION,
                candidate_id=cand["candidate_id"],pair=cand["pair"],
                event_time_utc=cand["event_time_utc"],known_at_utc=dt(12))
            for phase,key,result,status in (
                ("SCANNER_CAPTURE","FIRST","SKIP",
                 "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION"),
                ("SCANNER_CAPTURE","DEFERREDRECHECK","SEEN",
                 "ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY"),
                ("FULL_REVIEW_ELIGIBILITY","DEFERREDRECHECK","PASS",
                 "INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY"),
            ):
                payload={"candidate_origin":"SCANNER"}
                payload.update({"review_status":status} if phase=="FULL_REVIEW_ELIGIBILITY"
                               else {"source_status":status})
                r=make_receipt(**first,phase=phase,result=result,
                               data=payload,event_key=key)
                store_receipt_explicitly(journal,r)
            outcome=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                acquire=fake_acquire,clock=lambda:dt(12),
                admit_staged_scanner_no_model=True)
            self.assertEqual(outcome["status"],
                "V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            self.assertEqual(len(list(journal.glob("*.json"))),6)
            again=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                acquire=lambda _: (_ for _ in ()).throw(
                    AssertionError("no second network recheck")),
                clock=lambda:dt(12),admit_staged_scanner_no_model=True)
            self.assertEqual(again["status"],
                "NO_UNIQUE_UNPROCESSED_STAGED_SCANNER_NO_RECHECK")
            self.assertFalse(list(budgets.glob("*.json")))

    def test_staged_original_approved_one_model_call_preserves_first_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            candidate=dict(fixture()[0],entry_origin="SCANNER")
            stage_scanner_original(journal,candidate)
            frozen={p.name:p.read_bytes() for p in journal.glob("*.json")}
            calls=[]
            def one_stub(prompt,key):
                calls.append((prompt,key))
                return fake_model(prompt,key)
            result=one_candidate(candidate=candidate,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                approval=valid_approval(),model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=one_stub,clock=lambda:dt(12),
                allow_model=True,admit_staged_scanner_one_approved_model=True)
            self.assertEqual(result["status"],
                             "V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION")
            self.assertEqual(result["p4_decision"],"BUY_SCOUT")
            self.assertEqual(len(calls),1)
            self.assertEqual(len(list(budgets.glob("*.reserved.json"))),1)
            self.assertEqual({p.name:p.read_bytes() for p in journal.glob("*.json")
                              if p.name in frozen},frozen)
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual(len([r for r in rows if r["phase"]=="SCANNER_CAPTURE"]),1)
            self.assertEqual({r["event_key"] for r in rows
                              if r["phase"]=="MODEL_REQUEST"},{"FRESHRECHECK"})
            self.assertIn(("P4_VALIDATION","BUY_SCOUT"),
                          {(r["phase"],r["result"]) for r in rows})
            self.assertIn(("FOLLOWUP_24H","PENDING"),
                          {(r["phase"],r["result"]) for r in rows})
            replay=one_candidate(candidate=candidate,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                approval=valid_approval(),model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=lambda _: (_ for _ in ()).throw(
                    AssertionError("source replay forbidden")),
                model_client=lambda *_: (_ for _ in ()).throw(
                    AssertionError("second model forbidden")),
                clock=lambda:dt(12),allow_model=True,
                admit_staged_scanner_one_approved_model=True)
            self.assertEqual(replay["status"],
                             "NO_UNIQUE_UNPROCESSED_STAGED_SCANNER_NO_RECHECK")
            self.assertEqual(len(list(budgets.glob("*.reserved.json"))),1)
            self.assertEqual(len(calls),1)

    def test_staged_approved_model_fails_before_any_write_without_new_budget(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            candidate=dict(fixture()[0],entry_origin="SCANNER")
            stage_scanner_original(journal,candidate)
            originals={p.name:p.read_bytes() for p in journal.glob("*.json")}
            for kwargs in (
                {"allow_model":True,"approval":valid_approval(),"model_key":None},
                {"allow_model":False,"approval":valid_approval(),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":dict(valid_approval(),
                    max_model_http_attempts_including_retries=2),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":dict(valid_approval(),
                    unique_approval_id=None),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":dict(valid_approval(),
                    unique_approval_id="BAD"),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":dict(valid_approval(),
                    max_candidates=True),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":dict(valid_approval(),
                    max_model_http_attempts_including_retries=True),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"},
                {"allow_model":True,"approval":valid_approval(),
                 "model_key":"NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                 "admit_staged_scanner_no_model":True},
            ):
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                    one_candidate(candidate=candidate,series_id=SID,
                        local_receipts=journal,model_reservations=budgets,
                        acquire=lambda _: (_ for _ in ()).throw(
                            AssertionError("invalid budget must stop before Kraken")),
                        clock=lambda:dt(12),
                        admit_staged_scanner_one_approved_model=True,**kwargs)
            self.assertEqual({p.name:p.read_bytes() for p in journal.glob("*.json")},
                             originals)
            self.assertFalse(list(budgets.glob("*.reserved.json")))

    def test_staged_no_model_fence_invalid_source_and_old_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            cand=dict(fixture()[0],entry_origin="SCANNER")
            stage_scanner_original(journal,cand)
            for kwargs in (
                {"allow_model":True},
                {"approval":valid_approval()},
                {"model_key":"NON_REAL_STUB_KEY_DO_NOT_CALL"},
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    one_candidate(candidate=cand,series_id=SID,
                        local_receipts=journal,model_reservations=budgets,
                        admit_staged_scanner_no_model=True,
                        acquire=fake_acquire,clock=lambda:dt(12),**kwargs)
            with self.assertRaises(ValueError):
                one_candidate(candidate=dict(cand,entry_origin="VERIFIED_POSITIVE_SOURCE_CATALYST"),
                    series_id=SID,local_receipts=journal,model_reservations=budgets,
                    admit_staged_scanner_no_model=True,
                    acquire=fake_acquire,clock=lambda:dt(12))
            self.assertEqual(len(list(journal.glob("*.json"))),2)
            expired=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                admit_staged_scanner_no_model=True,
                acquire=lambda _: (_ for _ in ()).throw(AssertionError("no Kraken")),
                clock=lambda:dt(800))
            self.assertEqual(expired["status"],
                             "STAGED_ORIGINAL_EXPIRED_JOURNALED_NO_KRAKEN_NO_MODEL")
            rows=[json.loads(p.read_text()) for p in journal.glob("*.json")]
            expiry=next(r for r in rows if r["phase"]=="SOURCE_INPUT")
            self.assertEqual(expiry["result"],"UNKNOWN")
            self.assertNotIn("position_net_pnl_eur",expiry["data"])
            self.assertFalse(list(budgets.glob("*.json")))

    def test_real_model_path_with_explicit_injected_stub_uses_full_p4_and_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budgets=root/"budgets"
            journal.mkdir();budgets.mkdir()
            r=one_candidate(candidate=fixture()[0],series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                approval=valid_approval(),model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=fake_model,
                clock=lambda:dt(12),allow_model=True)
            self.assertEqual(r["status"],"V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION")
            self.assertEqual(r["p4_decision"],"BUY_SCOUT")
            self.assertEqual(r["model_http_attempts_reserved"],1)
            self.assertFalse(r["orders"])
            self.assertEqual(len(list(budgets.glob("*.reserved.json"))),1)
            records=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertIn(("PAPER_FILL","PAPER_FILLED"),
                          {(x["phase"],x["result"]) for x in records})
            self.assertIn(("FOLLOWUP_6H","PENDING"),
                          {(x["phase"],x["result"]) for x in records})
            self.assertIn(("FOLLOWUP_24H","PENDING"),
                          {(x["phase"],x["result"]) for x in records})
            self.assertIn(("FOLLOWUP_72H","PENDING"),
                          {(x["phase"],x["result"]) for x in records})

    def test_budget_spent_at_reservation_never_repeated_even_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);approval=valid_approval()
            p=reserve_before_http(root,approval,SID,"A",dt(12))
            self.assertTrue(p.is_file())
            with self.assertRaises(FileExistsError):
                reserve_before_http(root,approval,SID,"A",dt(12))
            wrong=dict(approval,max_model_http_attempts_including_retries=100)
            with self.assertRaises(ValueError):
                reserve_before_http(root,wrong,SID,"B",dt(13))

    def test_one_call_cannot_be_upgraded_in_model_tokens_or_cost(self):
        approval=valid_approval()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for mutate in (
                {"model":"gpt-6-astra"},
                {"max_input_utf8_bytes":500000},
                {"max_output_tokens":20000},
                {"estimated_usd_ceiling":5.0},
                {"max_model_http_attempts_including_retries":2},
                {"consumed_pr186_budget":True},
            ):
                with self.subTest(mutate=mutate):
                    wrong=dict(approval,**mutate)
                    with self.assertRaises(ValueError):
                        reserve_before_http(p,wrong,SID,"COIN",dt(12))
            self.assertFalse(list(p.glob("*.reserved.json")))

    def test_market_phase_smart_money_polymarket_are_known_at_or_missing_soft_context(self):
        yes={"source_verified":True,"source_owner":"H10_EXISTING",
             "pair":"XBT/EUR",
             "source_id":"SOURCE-EVIDENCE-1",
             "observed_at_utc":dt(3),"known_at_utc":dt(5),
             "consensus_direction":"LONG","independent_wallet_count":3,
             "secret":"NOT_PERMITTED"}
        out=fuse_existing_sources({
            "smart_money_h10":yes,
            "polymarket_h11":dict(yes,known_at_utc=dt(50)),
            "market_phase_radar":dict(yes,regime="RECOVERY",breadth="MIXED"),
            "news_sentiment":dict(yes,headline_digest="Official statement")
        },decision_at_utc=dt(12),pair="XBT/EUR")
        self.assertEqual(out["sources"]["smart_money_h10"]["state"],
                         "AVAILABLE_PIT_CONTEXT_ONLY")
        self.assertNotIn("secret",out["sources"]["smart_money_h10"]["values"])
        self.assertEqual(out["sources"]["polymarket_h11"]["state"],
                         "INVALID_FUTURE_OR_REVERSED_CLOCK")
        self.assertEqual(out["sources"]["market_phase_radar"]["values"]["regime"],"RECOVERY")
        self.assertTrue(out["optional_failure_never_hard_veto"])
        self.assertFalse(out["sources"]["polymarket_h11"]["hard_veto"])


    def test_pr251_optional_context_reaches_actual_worker_pre_model_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); journal=root/"journal"; budgets=root/"budgets"
            journal.mkdir(); budgets.mkdir()
            cand=fixture()[0]
            generic={"source_verified":True,"source_owner":"EXISTING_OWNER_TEST",
                     "source_id":"offline-pit-fixture",
                     "observed_at_utc":dt(3),"known_at_utc":dt(5)}
            context={
                "derivatives_h2":dict(generic,pair="XBT/EUR",funding_rate_pct=0.02),
                "macro_h5":dict(generic,event_id="calendar-no-catalyst"),
                "onchain_h8":dict(generic,pair="XBT/EUR",chain="bitcoin"),
                "global_market_crosscheck":dict(generic,btc_state="STABILIZING"),
                "smart_money_h10":dict(generic,pair="ETH/EUR",
                                      consensus_direction="LONG"),
            }
            result=one_candidate(candidate=cand,series_id=SID,
                local_receipts=journal,model_reservations=budgets,
                existing_context=context,acquire=fake_acquire,
                clock=lambda:dt(12),allow_model=False)
            self.assertEqual(result["status"],
                "V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            self.assertFalse(list(budgets.glob("*.json")))
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual(len(rows),4)
            reviewed=next(x["data"] for x in rows
                         if x["phase"]=="FULL_REVIEW_ELIGIBILITY")
            for key in ("derivatives_h2","macro_h5","onchain_h8",
                        "global_market_crosscheck"):
                self.assertEqual(reviewed["optional_context_states"][key],
                                 "AVAILABLE_PIT_CONTEXT_ONLY")
            self.assertNotIn("derivatives_h2_evidence",reviewed)
            self.assertEqual(reviewed["smart_money_evidence"]["state"],
                             "NOT_ASSOCIABLE_OTHER_PAIR")
            self.assertNotIn("values",reviewed["smart_money_evidence"])
            self.assertEqual(reviewed["optional_context_states"]["smart_money_h10"],
                             "NOT_ASSOCIABLE_OTHER_PAIR")
            self.assertFalse(any(r["phase"]=="MODEL_RESPONSE" for r in rows))

class V3ManualCliIdentityFenceTests(unittest.TestCase):
    """No network, model, budget, journal or task effects during source validation."""

    @staticmethod
    def canonical_scanner(*, action="REVIEW_ONLY_NOT_ORDER", origin=None):
        from datetime import datetime, timezone
        at="2026-10-15T09:30:00Z"
        ts=int(datetime.fromisoformat(at.replace("Z","+00:00")).timestamp())
        candidate={
            "kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
            "candidate_id":"20261015-093000-DASH-EUR-r42",
            "queue_id":f"42:DASH-EUR:{ts}",
            "source_scanner_run_id":42,"event_time_utc":at,
            "event_ts":ts,"pair":"DASH/EUR","altname":"DASHEUR",
            "action":action,"scanner_candidate":{},
            "scanner_market_context":{},
        }
        if origin is not None:
            candidate["entry_origin"]=origin
        return candidate

    def invoke_cli(self, candidate, *, filename=None, expected_error=None):
        from unittest.mock import patch
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import main
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);journal=root/"journal";budget=root/"budgets"
            journal.mkdir();budget.mkdir()
            file=root/(filename or candidate["candidate_id"]+".json")
            file.write_text(json.dumps(candidate),encoding="utf-8")
            argv=["v3_paper_minipc_one_candidate_v1.py","--candidate",str(file),
                  "--series",SID,"--journal",str(journal),
                  "--budget-directory",str(budget)]
            with patch("sys.argv",argv),patch(
                "paper_evaluator.v3_paper_minipc_one_candidate_v1.one_candidate",
                return_value={"status":"CLI_IDENTITY_TEST_NO_MODEL","orders":False}
            ) as worker:
                if expected_error:
                    with self.assertRaisesRegex(ValueError,expected_error):
                        main()
                    worker.assert_not_called()
                else:
                    self.assertEqual(main(),0)
                    worker.assert_called_once()
                    self.assertFalse(worker.call_args.kwargs["allow_model"])
            self.assertEqual(list(journal.iterdir()),[])
            self.assertEqual(list(budget.iterdir()),[])

    def test_original_scanner_identity_bound_to_filename_and_queue(self):
        self.invoke_cli(self.canonical_scanner())
        self.invoke_cli(self.canonical_scanner(),filename="forged.json",
                        expected_error="candidate identity mismatch")
        fake=self.canonical_scanner();fake["queue_id"]="not-original"
        self.invoke_cli(fake,expected_error="queue identity mismatch")

    def test_unauthorized_order_packet_never_reaches_model_worker(self):
        self.invoke_cli(self.canonical_scanner(action="BUY"),
                        expected_error="unsafe candidate action")
        fake=self.canonical_scanner();fake["kind"]="UNVERIFIED_CANDIDATE"
        self.invoke_cli(fake,expected_error="V3_CLI_ORIGINAL_SCANNER_HANDOFF_REQUIRED")

    def test_positive_source_label_without_hmac_cannot_use_model_cli(self):
        self.invoke_cli(self.canonical_scanner(
            origin="VERIFIED_POSITIVE_SOURCE_CATALYST"),
            expected_error="V3_CLI_SOURCE_OWNER_AUTH_NOT_PROVEN_NO_MODEL")
        self.invoke_cli(self.canonical_scanner(origin="UNKNOWN_BYPASS"),
            expected_error="V3_CLI_SOURCE_OWNER_AUTH_NOT_PROVEN_NO_MODEL")

if __name__=="__main__":
    unittest.main()
