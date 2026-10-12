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
             "source_id":"SOURCE-EVIDENCE-1",
             "observed_at_utc":dt(3),"known_at_utc":dt(5),
             "consensus_direction":"LONG","independent_wallet_count":3,
             "secret":"NOT_PERMITTED"}
        out=fuse_existing_sources({
            "smart_money_h10":yes,
            "polymarket_h11":dict(yes,known_at_utc=dt(50)),
            "market_phase_radar":dict(yes,regime="RECOVERY",breadth="MIXED"),
            "news_sentiment":dict(yes,headline_digest="Official statement")
        },decision_at_utc=dt(12))
        self.assertEqual(out["sources"]["smart_money_h10"]["state"],
                         "AVAILABLE_PIT_CONTEXT_ONLY")
        self.assertNotIn("secret",out["sources"]["smart_money_h10"]["values"])
        self.assertEqual(out["sources"]["polymarket_h11"]["state"],
                         "INVALID_FUTURE_OR_REVERSED_CLOCK")
        self.assertEqual(out["sources"]["market_phase_radar"]["values"]["regime"],"RECOVERY")
        self.assertTrue(out["optional_failure_never_hard_veto"])
        self.assertFalse(out["sources"]["polymarket_h11"]["hard_veto"])

if __name__=="__main__":
    unittest.main()
