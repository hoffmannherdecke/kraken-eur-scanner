"""Ensure V3 decisions and source status cannot regress to closed old user tasks.

All checks are repository-state only. Never assume CI demonstrates actual
MINI-PC, Kraken model, source steward or Paper economic results.
"""
import json
import unittest
from pathlib import Path
from tools.v3_context_fusion_preflight import validate as validate_optional_context

ROOT=Path(__file__).resolve().parents[1]


def data(rel):
    return json.loads((ROOT/rel).read_text("utf-8"))


class V3IntegratedReadinessHandoffTests(unittest.TestCase):
    def test_true_current_action_replaces_20261011_second_run_pending_work(self):
        j=data("project-current-state.json")
        t=j["pending_strategy_transition"]
        self.assertEqual(t["status"],"BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING")
        self.assertEqual(t["user_decision"],
                         "APPROVED_GOAL_V3_PAPER_REPLACES_V2R4_NO_REAL_MONEY")
        h=t["current_handoff_action"]
        self.assertEqual(h["kind"],"V3_INTEGRATED_RESEARCH_NEXT_EVIDENCE_GATE_V1")
        self.assertIn("PROSPECTIVE",h["next_concrete_action"])
        self.assertFalse(h["full_model_consumer_e2e_verified"])
        self.assertFalse(h["five_real_pit_e2e_verified"])
        self.assertFalse(h["real_cost_validated_buy_verified"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        self.assertFalse(h["v3_paper_active"])
        self.assertTrue(h["no_new_scheduler"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        self.assertEqual(t["sequence"][1]["status"],
                         "V3B_SECOND_SHADOW5_CLOSED_NO_ELIGIBLE_AND_NO_ECONOMIC_PROOF")
        self.assertNotIn("READ_ONLY_PENDING",t["sequence"][1]["execution_state"])
        self.assertIn("V2R4",j["active_strategy"]["strategy_revision"])
        self.assertFalse(j["active_strategy"]["real_money_actions"])

    def test_integrated_plan_recognizes_existing_work_and_no_alpha(self):
        p=data("research/v3/v3-consolidated-strategy-integration-plan-20261011.json")
        work={x["id"]:x for x in p["package_order"]}
        for x in ("P0_LINEAGE_AND_DATA_READINESS","P1_V3_B_REAL_SECOND_LEG_ENTRY",
                  "P2_WAIT_EXPIRED_FRESH_RECHECK","P3_OTHER_ENTRY_SETUP_FAMILIES",
                  "P4_RISK_AND_EXECUTION_NOT_A_SHORTCUT",
                  "P5_CONTEXT_AND_ACTIVE_SOURCE_MANAGEMENT",
                  "P6_PROSPECTIVE_REGIME_LEARNING","P8_COMBINED_MATURE_V3"):
            self.assertIn(x,work)
        self.assertIn("INACTIVE",work["P2_WAIT_EXPIRED_FRESH_RECHECK"]["status"])
        self.assertIn("INACTIVE",work["P3_OTHER_ENTRY_SETUP_FAMILIES"]["status"])
        self.assertEqual(work["P8_COMBINED_MATURE_V3"]["status"],"NOT_READY")
        self.assertIn("P2",p["immediate_action"]["next"])
        self.assertNotIn("PR #159 pure review eligibility",p["immediate_action"]["next"])
        r=p["reconciliation_20261011"]
        self.assertIn("UNPROVEN",r["status"])
        self.assertIn("UNVERIFIED",r["source_steward_actual_e2e"])
        self.assertIn("MARKET_REGIME_EPISODE_V1",r["context_real_evidence"])
        reg=data("research/v3/v3-paper-experimental-ab-contract-20261011.json")
        self.assertIn("NOT_AUTHORIZED",reg["status"])
        self.assertIn("explicit",reg["prospective_measurement_once_separately_approved"]["approval_and_budget"].lower())

    def test_optional_source_management_never_promoted_as_buy_gate(self):
        r=validate_optional_context(ROOT)
        self.assertEqual(r["status"],
                         "PASSIVE_RESEARCH_ROUTES_VERIFIED_NO_STRATEGY_INTEGRATION")
        self.assertEqual(len(r["lanes"]),9)
        self.assertFalse(r["permission_to_trade"])
        self.assertFalse(r["added_schedules"])
        h=data("project-current-state.json")["pending_strategy_transition"]["current_handoff_action"]
        self.assertFalse(h["optional_source_management_unattended_e2e_verified"])
        self.assertFalse(h["regime_or_optional_source_buy_veto_enabled"])
        backlog=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn("erste tatsächlich unbeaufsichtigte vollständige Quellen-Steward-E2E fehlt noch",backlog)
        self.assertIn("P3-CONTINUITY-Review-Fassung",backlog)
        self.assertIn("bereits umgesetzt mit PR #181",backlog)


if __name__=="__main__":
    unittest.main()
