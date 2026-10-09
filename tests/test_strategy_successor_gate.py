"""Release-chain regression: historical V2R4 allowed, unproven future strategy blocked."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.strategy_successor_gate import ROOT, GATE_FILE, SUCCESS, validate_learning_gate


class SuccessorLearningGateTests(unittest.TestCase):
    def test_current_frozen_v2r4_does_not_retroactively_block(self):
        self.assertEqual(validate_learning_gate(ROOT,
          active_revision="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"), [])

    def test_future_strategy_without_e2e_is_blocked(self):
        errors=validate_learning_gate(ROOT, active_revision="V3-PAPER-NEW")
        self.assertTrue(any("NEW_STRATEGY_BLOCKED" in x for x in errors), errors)

    def test_fake_approval_with_zero_buys_still_blocked(self):
        missing={
          "kind":"SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1",
          "strategy_revision":"V3-PAPER-NEW",
          "status":"READY_WITH_EXPLICIT_PAPER_APPROVAL",
          "real_money_actions":False,
          "code_fingerprint_sha256":"a",
          "strategy_fingerprint_sha256":"b",
          "requirement_proofs":[],
          "prospective_feasibility":{
            "evaluated_candidates":1000,
            "valid_buy_scouts":0,
            "matched_baseline_and_successor_clock":True,
            "pair_time_clustered":True,
            "risk_and_net_cost_review_complete":True},
          "explicit_human_release_decision":"APPROVED_PAPER"
        }
        errors=validate_learning_gate(ROOT,"V3-PAPER-NEW",release_evidence=missing)
        self.assertTrue(any("no evidence any viable BUY_SCOUT" in x for x in errors))
        self.assertTrue(any("not verified in canonical gate" in x for x in errors))

    def test_contract_can_close_only_with_individual_artifact_proofs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=json.loads((ROOT/GATE_FILE).read_text("utf-8"))
            requirements=source["checks_before_any_successor_paper_release"]
            for req in requirements:
                req["current_status"]=SUCCESS
            out=root/GATE_FILE
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(source),encoding="utf-8")
            proofs=[]
            for req in requirements:
                p=f"research/gate-proof-{req['id'].lower()}.json"
                fp=root/p
                fp.write_text('{"verified":"fixture_only"}',encoding="utf-8")
                proofs.append({"id":req["id"],"status":SUCCESS,"evidence_path":p})
            claim={
              "kind":"SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1",
              "strategy_revision":"V3-PAPER-NEW",
              "status":"READY_WITH_EXPLICIT_PAPER_APPROVAL",
              "real_money_actions":False,"code_fingerprint_sha256":"code_fixture",
              "strategy_fingerprint_sha256":"strategy_fixture",
              "requirement_proofs":proofs,
              "prospective_feasibility":{"evaluated_candidates":100,
                  "valid_buy_scouts":1,"matched_baseline_and_successor_clock":True,
                  "pair_time_clustered":True,"risk_and_net_cost_review_complete":True},
              "explicit_human_release_decision":"APPROVED_PAPER"}
            self.assertEqual(validate_learning_gate(root,"V3-PAPER-NEW",claim),[])
            proofs[0]["evidence_path"]="research/no-proof.json"
            self.assertTrue(any("artifact absent" in e for e in validate_learning_gate(root,"V3-PAPER-NEW",claim)))

if __name__=="__main__":
    unittest.main()
