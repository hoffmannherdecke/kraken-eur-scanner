#!/usr/bin/env python3
"""Negative/positive invariants of the unified monitoring evidence contract."""
import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("monitor",ROOT/"tools/validate-monitoring-evidence-routing.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
TOPO=json.loads((ROOT/"research/monitoring-evidence-routing-v1.json").read_text())
STATE=json.loads((ROOT/"project-current-state.json").read_text())

class ContractTests(unittest.TestCase):
    def test_current_architecture_clean(self):
        self.assertEqual([],mod.validate(TOPO,STATE))
    def test_duplicate_fact_authority_fails(self):
        j=copy.deepcopy(TOPO)
        j["streams"][1]["fact_key"]=j["streams"][0]["fact_key"]
        self.assertTrue(any("two authorities" in e for e in mod.validate(j,STATE)))
    def test_optional_feed_must_fail_soft(self):
        j=copy.deepcopy(TOPO)
        next(s for s in j["streams"] if s["id"]=="global_market_crosscheck")["on_missing"]="BLOCK_BUY"
        self.assertTrue(any("veto" in e for e in mod.validate(j,STATE)))
    def test_rejected_h1_stays_rejected(self):
        j=copy.deepcopy(TOPO)
        next(s for s in j["streams"] if s["id"]=="h1_breadth_diagnostic")["authority"]="RESEARCH_ONLY"
        self.assertTrue(any("H1 standalone" in e for e in mod.validate(j,STATE)))
    def test_observation_cannot_open_work(self):
        j=copy.deepcopy(TOPO)
        j["work_gate_from_observation"]=True
        self.assertTrue(any("work_gate" in e for e in mod.validate(j,STATE)))
    def test_substantive_source_cannot_skip_release(self):
        j=copy.deepcopy(TOPO)
        next(s for s in j["streams"] if s["id"]=="news_event_context")["strategy_change_requires_release"]=False
        self.assertTrue(any("bypasses release" in e for e in mod.validate(j,STATE)))
    def test_recorded_market_regime_is_research_evidence_not_live_trading_approval(self):
        market=next(x for x in TOPO["streams"] if x["id"]=="market_regime")
        self.assertEqual(market["evidence_status"],
                         "PIT_KRAKEN_EUR_EPISODES_CAPTURED_FIRST_E2E_RECORDED_20261008")
        self.assertEqual(market["authority"],"RESEARCH_ONLY")
        self.assertEqual(market["on_missing"],"UNKNOWN_NO_VETO")
        self.assertTrue(market["strategy_change_requires_release"])
        self.assertGreaterEqual(len(market["evidence_refs"]),2)
        self.assertIn("PIT_24H_PAPER_OUTCOME_JOIN",market["next_gate"])
        self.assertIn("no proven strategy lift",market["evidence_scope"])
        news=next(x for x in TOPO["streams"] if x["id"]=="news_event_context")
        steward=next(x for x in TOPO["streams"] if x["id"]=="source_quality")
        self.assertEqual(news["evidence_status"],"UNATTENDED_E2E_UNVERIFIED")
        self.assertEqual(steward["evidence_status"],"UNATTENDED_E2E_UNVERIFIED")

    def test_source_autonomy_activation_waits_for_real_pilot_proof(self):
        q=next(x for x in TOPO["streams"] if x["id"]=="source_quality")
        gate=q["activation_followthrough"]
        self.assertEqual(gate["status"],
                         "OBSERVATION_TASK_ACTIVE_SOURCE_REVIEW_AND_REPLACE_E2E_UNVERIFIED")
        self.assertEqual(gate["id"], "AUTONOMOUS_ACTIVE_SOURCE_MANAGEMENT_E2E_GATE_V1")
        self.assertTrue(gate["active_management_not_limited_to_static_27_catalog"])
        self.assertIn("DISCOVER_UNKNOWN_SOURCE", gate["active_management_actions"])
        self.assertIn("REPLACE_WITH_BETTER_CHALLENGER", gate["active_management_actions"])
        self.assertIn("5_INDEPENDENT",gate["stage_2"])
        self.assertIn("ONE_CHANGE_ECONOMIC",gate["stage_4"])
        self.assertTrue(gate["no_new_work_run"])
        self.assertTrue(gate["no_trading_or_runtime_source_replacement"])

    def test_source_first_pilot_or_replacement_gate_cannot_be_dropped(self):
        j=copy.deepcopy(TOPO)
        next(x for x in j["streams"] if x["id"]=="source_quality").pop("activation_followthrough")
        self.assertTrue(any("source quality activation handoff" in x
                            for x in mod.validate(j,STATE)))

    def test_source_management_does_not_shrink_back_to_rotations(self):
        j=copy.deepcopy(TOPO)
        gate=next(x for x in j["streams"] if x["id"]=="source_quality")["activation_followthrough"]
        gate["active_management_actions"].remove("DISCOVER_UNKNOWN_SOURCE")
        self.assertTrue(any("source stewardship must cover autonomous discovery" in x
                            for x in mod.validate(j,STATE)))

    def test_static_27_source_whitelist_is_forbidden(self):
        j=copy.deepcopy(TOPO)
        gate=next(x for x in j["streams"] if x["id"]=="source_quality")["activation_followthrough"]
        gate["active_management_not_limited_to_static_27_catalog"]=False
        self.assertTrue(any("source quality activation cannot bypass safety" in x
                            for x in mod.validate(j,STATE)))

    def test_source_quality_never_modifies_active_trading_authority(self):
        j=copy.deepcopy(TOPO)
        gate=next(x for x in j["streams"] if x["id"]=="source_quality")["activation_followthrough"]
        gate["no_trading_or_runtime_source_replacement"]=False
        self.assertTrue(any("source quality activation cannot bypass safety" in x
                            for x in mod.validate(j,STATE)))

    def test_h3_h6_source_context_is_not_obsolete_pre_cutover_status(self):
        j=copy.deepcopy(TOPO)
        next(x for x in j["streams"] if x["id"]=="orderflow_h3")["evidence_status"]="ISOLATED_SHADOW_DECLARED"
        self.assertTrue(any("stale active H3" in x for x in mod.validate(j,STATE)))

    def test_no_second_active_shadow(self):
        state=copy.deepcopy(STATE)
        state["strategy_changing_shadow_wip"]["active"].extend([
            {"candidate_id":"V3-H3-SHADOW-001"},
            {"candidate_id":"V3-H6-SHADOW-002"},
        ])
        self.assertTrue(any("simultaneous decision shadows" in e for e in mod.validate(TOPO,state)))

if __name__=="__main__":
    unittest.main()
