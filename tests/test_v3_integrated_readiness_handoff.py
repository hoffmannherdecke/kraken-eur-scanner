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

    def test_finished_user_uploaded_original_p3_report_is_distinguished_from_economic_proof(self):
        h=data("project-current-state.json")["pending_strategy_transition"]["current_handoff_action"]
        p=h["bounded_p3_standard_experimental_test"]
        self.assertEqual(p["approval_status"],"APPROVAL_CONSUMED_SINGLE_RUN_FINISHED_2026_10_11")
        self.assertEqual(p["evidence_quality"],"VERIFIED_UPLOADED_JSON_NOT_INDEPENDENT_API_ATTESTATION")
        self.assertEqual(p["uploaded_json_bytes"],4730)
        self.assertEqual(p["uploaded_json_sha256"],
            "6a0fe8aeda0aab083d957edc27f85e190419a99588a936f1cde18568abbfc485")
        self.assertEqual(p["five_verified_coins"],
            ["EIGEN/EUR","XLM/EUR","RENDER/EUR","CC/EUR","MON/EUR"])
        self.assertEqual(p["verified_model_wait_and_p4_wait_count"],5)
        self.assertEqual(p["experimental_incremental_reviews_observed"],0)
        self.assertEqual(p["verified_5m_volume_weak_reason_code_count"],0)
        self.assertTrue(p["metadata_fail_count_not_incremented_in_runner"])
        self.assertTrue(p["true_model_response_at_and_wait_ttl_watch_not_persisted"])
        self.assertTrue(p["no_relaunch_and_no_automatic_model_budget_reset"])
        self.assertFalse(p["real_cost_validated_buy_proven"])
        self.assertFalse(p["incremental_ab_delta_tested"])
        self.assertFalse(h["full_model_consumer_e2e_verified"])
        self.assertFalse(h["real_cost_validated_buy_verified"])
        self.assertFalse(h["v3_paper_active"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        audit=(ROOT/"research/work-analysis/2026-10-11-v3-p3-ab-five-physical-result-screen-ack.md").read_text("utf-8")
        self.assertIn(p["uploaded_json_sha256"],audit)
        self.assertIn("kein einziges `5M_VOLUME_WEAK`",audit)
        self.assertIn("nicht hochgezählt",audit)
        backlog=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn("ORIGINAL-JSON GEPRÜFT",backlog)
        self.assertIn("V2R4 bleibt allein aktiv",backlog)

    def test_zero_buy_tradeability_analysis_preserves_causal_and_release_boundaries(self):
        state=data("project-current-state.json")
        h=state["pending_strategy_transition"]["current_handoff_action"]
        a=h["tradeability_backwards_causality_20261011"]
        self.assertEqual(a["v2r4_dynamic_snapshot_initial_decisions"],2102)
        self.assertEqual(a["v2r4_initial_wait"],1321)
        self.assertEqual(a["v2r4_initial_reject"],781)
        self.assertEqual(a["v2r4_initial_buy"],0)
        self.assertEqual(a["actual_v2r4_trigger_rechecks"],164)
        self.assertEqual(a["trigger_rechecks_as_extended"],153)
        self.assertEqual(a["trigger_rechecks_buy"],0)
        self.assertEqual(a["original_model_coin_1m5m15m_context_entries"],0)
        self.assertEqual(a["original_model_nonnull_structural_stop_prices"],0)
        self.assertEqual(a["v3_real_full_wait"],5)
        self.assertEqual(a["v3_real_buy"],0)
        self.assertFalse(a["no_new_model_budget_granted"] is False)
        self.assertTrue(a["no_v2r4_runtime_strategy_modification"])
        self.assertFalse(a["no_shadow_or_paper_activation"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        self.assertFalse(h["v3_paper_active"])
        self.assertFalse(h["real_cost_validated_buy_verified"])
        report=(ROOT/a["source"]).read_text("utf-8")
        for x in ("153/164", "2.102", "0,202 %", "-1,882 %", "kein"):
            self.assertIn(x, report)
        self.assertIn(a["source"], (ROOT/"PROJECT_BACKLOG.md").read_text("utf-8"))
        self.assertIn("PROSPECTIVE",h["next_concrete_action"])

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
