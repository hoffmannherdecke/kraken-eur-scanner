"""No-profit-before-paper is permitted ONLY with actual technical proofs."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.v3_experimental_paper_technical_gate import (
    PROOFS, validate_experimental_paper_packet,
)
from tools.strategy_successor_gate import ROOT, GATE_FILE, validate_learning_gate


def fixture(root:Path)->dict:
    items=[]
    for key in sorted(PROOFS):
        dest=root/"research"/("proof-"+key.lower()+".json")
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps({"real_e2e_fixture_only":True}),encoding="utf-8")
        items.append({"id":key,"status":"VERIFIED_PHYSICAL_OR_CLOUD_E2E",
                      "evidence_path":str(dest.relative_to(root)),
                      "sha256":hashlib.sha256(dest.read_bytes()).hexdigest()})
    return {"kind":"SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1",
            "strategy_revision":"V3-PAPER-EXPERIMENTAL-001",
            "paper_phase":"EXPERIMENTAL_PAPER_ONLY",
            "status":"READY_WITH_EXPLICIT_EXPERIMENTAL_PAPER_APPROVAL",
            "paper_only":True,"real_money_actions":False,
            "automatic_activation":False,
            "explicit_human_release_decision":"APPROVED_EXPERIMENTAL_PAPER",
            "code_fingerprint_sha256":"a"*64,
            "strategy_fingerprint_sha256":"b"*64,
            "economic_alpha_claimed":False,
            "post_experiment_promotion_requires_economic_gate":True,
            "physical_single_writer_cutover_dry_run_passed":True,
            "physical_single_writer_cutover_ack_obtained":False,
            "fixed_api_cost_limit_user_authorized":True,
            "bounded_research_scope":{
              "max_candidates":100,"max_model_http_attempts_including_retries":200,
              "max_observation_days":14,"deduplicate_pair_clock":True,
              "mandatory_real_6h_24h_and_censored_followups":True,
              "stop_when_budget_exhausted":True},
            "frozen_execution_risk":{
              "taker_pct_each_side":0.6,"scout_eur":50,"stage2_eur":50,
              "kraken_online_spot_eur":True,"true_pit_1m5m15m_atr_stop":True,
              "full_model_decision_before_any_paper_buy":True,
              "stop_stage2_spread_slippage_required":True,
              "no_real_orders":True,"no_h3_h6_auto_activation":True},
            "experimental_paper_technical_proofs":items,
            "prospective_feasibility":{"evaluated_candidates":0,"valid_buy_scouts":0}}


class ExperimentalV3PaperTechnicalReleaseTests(unittest.TestCase):
    def test_current_v2r4_unchanged_and_no_v3_evidence_is_blocked(self):
        self.assertEqual(validate_learning_gate(ROOT,
            active_revision="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"),[])
        x=validate_learning_gate(ROOT,active_revision="V3-PAPER-EXPERIMENTAL-001")
        self.assertTrue(any("NEW_STRATEGY_BLOCKED" in e for e in x))

    def test_experimental_paper_technical_release_not_alpha(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/GATE_FILE
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text((ROOT/GATE_FILE).read_text("utf-8"),encoding="utf-8")
            evidence=fixture(root)
            self.assertEqual(validate_learning_gate(root,"V3-PAPER-EXPERIMENTAL-001",
                                                    evidence),[])
            # NO requirement to invent a profitable BUY before a Paper experiment.
            self.assertEqual(evidence["prospective_feasibility"]["valid_buy_scouts"],0)
            self.assertFalse(evidence["economic_alpha_claimed"])
            self.assertFalse(evidence["physical_single_writer_cutover_ack_obtained"])
            # The later economic promotion path remains separate and strict.
            normal=copy.deepcopy(evidence)
            normal["paper_phase"]="ECONOMIC_PROMOTION"
            x=validate_learning_gate(root,"V3-PAPER-EXPERIMENTAL-001",normal)
            self.assertTrue(any("NEW_STRATEGY_BLOCKED" in e for e in x))

    def test_missing_one_real_proof_wrong_hash_budget_approval_always_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            base=fixture(root)
            mods=[
                lambda d:d["experimental_paper_technical_proofs"].pop(),
                lambda d:d["experimental_paper_technical_proofs"][0].update(status="MOCK_ONLY"),
                lambda d:d["experimental_paper_technical_proofs"][0].update(sha256="0"*64),
                lambda d:d["experimental_paper_technical_proofs"][0].update(evidence_path="../secret"),
                lambda d:d["experimental_paper_technical_proofs"].append(
                    copy.deepcopy(d["experimental_paper_technical_proofs"][0])),
                lambda d:d.update(fixed_api_cost_limit_user_authorized=False),
                lambda d:d.update(explicit_human_release_decision="SILENT_AUTO_APPROVED"),
                lambda d:d.update(physical_single_writer_cutover_dry_run_passed=False),
                lambda d:d.update(physical_single_writer_cutover_ack_obtained=True),
                lambda d:d.update(real_money_actions=True),
                lambda d:d.update(paper_only=False),
                lambda d:d.update(automatic_activation=True),
                lambda d:d.update(economic_alpha_claimed=True),
                lambda d:d.update(code_fingerprint_sha256="test-not-a-sha"),
                lambda d:d["bounded_research_scope"].update(max_candidates=0),
                lambda d:d["bounded_research_scope"].update(max_observation_days=999),
                lambda d:d["bounded_research_scope"].update(
                    max_model_http_attempts_including_retries=1001),
                lambda d:d["bounded_research_scope"].update(
                    mandatory_real_6h_24h_and_censored_followups=False),
                lambda d:d["frozen_execution_risk"].update(taker_pct_each_side=0),
                lambda d:d["frozen_execution_risk"].update(
                    full_model_decision_before_any_paper_buy=False),
                lambda d:d["frozen_execution_risk"].update(no_real_orders=False),
                lambda d:d.update(strategy_revision="OLD_V2R4"),
            ]
            for m in mods:
                d=copy.deepcopy(base);m(d)
                self.assertTrue(
                    validate_experimental_paper_packet(root,"V3-PAPER-EXPERIMENTAL-001",d),
                    m)

    def test_canonical_cutover_runbook_does_not_delay_first_paper_until_profit(self):
        # The release gate already distinguishes experimentation from promotion.
        # Keep the *operational* host runbook aligned so an old A+B sentence
        # cannot become an artificial second 28h/72h Shadow requirement.
        text=(ROOT/"docs/v3-controlled-paper-cutover-20261011.md").read_text("utf-8")
        self.assertIn("## 2. Reihenfolge der physischen Mini-PC-Übernahme, erst **nach** A + technischem",text)
        self.assertIn("B: Wirtschaftliche Nachfolger-Promotion",text)
        self.assertIn("KEINE Vorbedingung für den ersten `EXPERIMENTAL_PAPER_ONLY`-Start",text)
        self.assertIn("sechs **echte**",text)
        self.assertIn("ein profitabler Vorabkauf ist dabei nicht gefordert",text)
        self.assertNotIn("erst **nach** A+B",text)

    def test_current_runtime_does_not_depend_on_experimental_gate(self):
        for f in ("paper_evaluator/evaluate.py",
                  "paper_evaluator/v2r4_local_recheck.py",
                  "tools/v2r4-paper-local-runtime.py"):
            s=(ROOT/f).read_text("utf-8")
            self.assertNotIn("v3_experimental_paper_technical_gate",s)


if __name__=="__main__":
    unittest.main()
