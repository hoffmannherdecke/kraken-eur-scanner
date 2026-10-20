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
    def test_native_source_import_closure_is_readonly_and_not_release(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        result=assess_v3_native_source_import_closure(ROOT)
        self.assertTrue(result["static_local_import_closure_complete"],
                        result["errors"])
        self.assertGreater(result["candidate_transitive_file_count"],20)
        self.assertEqual(len(result["candidate_transitive_source_sha256"]),64)
        self.assertFalse(result["actual_loaded_python_bytecode_independently_verified"])
        self.assertFalse(result["physical_mini_pc_or_cloud_release_proven"])
        self.assertFalse(result["paper_release_authorized"])
        self.assertFalse(result["real_money_actions"])
        included={r[0] for r in result["candidate_transitive_files"]}
        self.assertIn("paper_evaluator/v3_paper_minipc_native_launcher_v1.py",included)
        self.assertIn("tools/v3_experimental_paper_technical_gate.py",included)

    def test_native_source_import_closure_rejects_missing_and_linked_source(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        from unittest.mock import patch
        with patch("tools.v3_experimental_paper_technical_gate."
                   "assess_v3_experimental_source_inventory",
                   return_value={"source_inventory_complete":True,
                                 "candidate_source_files":[
                                  "paper_evaluator/not-installed.py"]}):
            report=assess_v3_native_source_import_closure(ROOT)
        self.assertFalse(report["static_local_import_closure_complete"])
        self.assertIn("INCOMPLETE",report["errors"][0])
        self.assertFalse(report["paper_release_authorized"])

    def test_native_source_import_closure_never_needs_runtime_or_network(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        from unittest.mock import patch
        with patch("subprocess.run",side_effect=AssertionError("no subprocess")), \
                patch("socket.create_connection",
                      side_effect=AssertionError("no network")):
            report=assess_v3_native_source_import_closure(ROOT)
        self.assertTrue(report["static_local_import_closure_complete"],report["errors"])


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
        self.assertTrue(a["no_new_model_budget_granted"])
        self.assertTrue(a["no_v2r4_runtime_strategy_modification"])
        self.assertTrue(a["no_shadow_or_paper_activation"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        self.assertFalse(h["v3_paper_active"])
        self.assertFalse(h["real_cost_validated_buy_verified"])
        report=(ROOT/a["source"]).read_text("utf-8")
        for x in ("153/164", "2.102", "0,202 %", "-1,882 %", "kein"):
            self.assertIn(x, report)
        self.assertIn(a["source"], (ROOT/"PROJECT_BACKLOG.md").read_text("utf-8"))
        self.assertIn("PROSPECTIVE",h["next_concrete_action"])

    def test_crash_rebound_archive_history_and_751_censored_horizons_not_converted_to_trades(self):
        j=data("project-current-state.json")
        h=j["pending_strategy_transition"]["current_handoff_action"]
        x=h["crash_rebound_historical_stress_review_20261011"]
        self.assertEqual(x["v2r3_clean"]["fully_mature_24h"],1005)
        self.assertEqual(x["v2r3_clean"]["completed_paper_trades"],1)
        self.assertEqual(x["v2r4_thursday"]["candidates"],554)
        self.assertEqual(x["v2r4_thursday"]["complete24"],214)
        self.assertEqual(x["v2r4_friday"]["candidates"],623)
        self.assertEqual(x["v2r4_friday"]["complete24"],212)
        self.assertEqual(x["v2r4_friday"]["mfe24_ge_plus12"],71)
        self.assertEqual(x["v2r4_friday"]["distinct_pairs_with_mfe24_plus12"],9)
        self.assertEqual(x["v2r4_technical_closed_followups"]["missing24"],751)
        self.assertEqual(x["v2r4_technical_closed_followups"]["of_which_complete12"],358)
        self.assertEqual(x["v2r4_technical_closed_followups"]["missing12_and_24"],393)
        self.assertEqual(x["v2r4_technical_closed_followups"]["cause_label"],
                         "HORIZON_CENSORED_ACROSS_FROZEN_TECHNICAL_ROTATION_NOT_LOSS_NOT_ZERO_RETURN")
        self.assertTrue(x["v2r4_technical_closed_followups"]["immutable_paper_segment_must_not_be_overwritten"])
        self.assertFalse(x["v2r4_technical_closed_followups"]["historical_recovery_verified"])
        self.assertFalse(x["numeric_new_model_http_cost_setup_caps_yet_fixed"])
        self.assertTrue(x["no_model_expenditure_or_physical_trial_started"])
        self.assertTrue(x["no_v2r4_or_paper_writer_change"])
        self.assertTrue(x["no_new_scheduler"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        self.assertFalse(h["v3_paper_active"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        audit=(ROOT/x["primary_source"]).read_text("utf-8")
        self.assertIn("**751 Kandidaten ohne 24h-Horizont**",audit)
        self.assertIn("1005",audit.replace(".",""))
        backlog=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn(x["primary_source"],backlog)
        self.assertIn("CENSORED_NOT_0_LOSS",backlog)

    def test_twelve_historical_cases_closed_as_learning_not_fake_trade_release(self):
        j=data("project-current-state.json")
        h=j["pending_strategy_transition"]["current_handoff_action"]
        d=h["historical_12_case_learning_closure_20261011"]
        self.assertEqual(d["source_decisions"],12)
        self.assertEqual(d["independent_original_handoffs_pass"],12)
        self.assertEqual(d["historic_coin_pit_at_first_model_time_proven"],0)
        self.assertEqual(d["favorable_outcome_selected"],6)
        self.assertEqual(d["adverse_outcome_selected"],6)
        self.assertFalse(d["economic_edge_proven"])
        self.assertFalse(d["successor_v3_paper_release_allowed"])
        self.assertFalse(d["model_or_shadow_started"])
        self.assertFalse(d["anti_chase_or_fee_rule_relaxed"])
        self.assertEqual(d["model_calls_for_historical_replay"],0)
        self.assertIn("WAIT_TRIGGER",d["v3_p4_wait_gate_fix"])
        self.assertFalse(h["new_model_shadow_or_paper_trial_authorized"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        g=data("research/strategy-learning-causal-gate-v1.json")
        x=g["v3_opportunity_first_research"]["historical_twelve_case_disposition_20261011"]
        self.assertEqual(x["known_originals"],12)
        self.assertEqual(x["historical_original_full_closed_coin_pit_proven"],0)
        self.assertFalse(x["shadow_or_paper_executed_by_this_work"])
        self.assertFalse(x["active_v2r4_modified"])
        backlog=(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8")
        self.assertIn("12er-Lernauftrag ABGESCHLOSSEN",backlog)
        self.assertIn("UNKNOWN_INVALID_WAIT_CONTRACT",backlog)

    def test_active_v2r4_and_early_p3_hypothesis_never_falsely_report_v3_paper_active(self):
        j=data("project-current-state.json")
        h=j["pending_strategy_transition"]["current_handoff_action"]
        d=h["v2r4_today_20261011_candidate_diagnosis"]
        x=h["v3_early_5m_paper_research_20261011"]
        cut=h["user_requested_v3_paper_cutover_20261011"]
        self.assertEqual(d["active_operational_series_id"],"PAPER-V2R4-20261009T110135Z")
        self.assertEqual(d["initial_candidates"],420)
        self.assertEqual(d["initial_wait"],238)
        self.assertEqual(d["initial_reject"],182)
        self.assertEqual(d["initial_buy"],0)
        self.assertEqual(d["real_triggered_rechecks"],40)
        self.assertEqual(d["rechecks_reclassified_extended"],38)
        self.assertEqual(d["initial_decisions_with_coin_entry_evidence"],0)
        self.assertEqual(d["initial_decisions_with_structural_stop"],0)
        self.assertEqual(x["same_5m_relative_volume_floor"],1.2)
        self.assertFalse(x["active_v2r4_changed"])
        self.assertTrue(x["no_paper_writer_or_shadow_started"])
        self.assertEqual(x["new_real_model_http_attempts"],0)
        self.assertTrue(cut["no_live_change_or_cutover_executed"])
        self.assertTrue(cut["user_paper_target_approval_retained"])
        self.assertEqual(cut["active_series"],d["active_operational_series_id"])
        self.assertIn("MODEL_VALIDATED_BUY_STOP_STAGE2_FEES",cut["missing_verified_gates"])
        self.assertIn("24H_FOLLOWUP_PRESERVATION_CROSS_TECHNICAL_ROTATION",cut["missing_verified_gates"])
        self.assertFalse(h["v3_paper_active"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        self.assertIn("PROSPECTIVE",h["next_concrete_action"])
        self.assertIn(d["source"],(ROOT/"PROJECT_BACKLOG.md").read_text("utf-8"))

    def test_all_day_v3_experiment_has_real_code_but_never_fake_runtime(self):
        b=data("research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json")
        self.assertEqual(b["strategy_revision"],
                         "V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001")
        self.assertEqual(len(b["entry_priority"]),7)
        self.assertEqual(b["entry_priority"][0]["id"],"SOURCE_CATALYST_INDEPENDENT")
        self.assertFalse(b["entry_priority"][0]["runtime_enabled"])
        self.assertTrue(all(x["paper_policy_selected"] for x in b["entry_priority"]))
        self.assertTrue(all(x["runtime_enabled"] is False for x in b["entry_priority"]))
        self.assertTrue(b["concurrency_requirements"]["dedupe_across_all_six_policy_families"])
        self.assertTrue(b["experiment_evaluation"]["missing_24h_is_censored_not_zero"])
        self.assertTrue(b["current_verified_state"]["pure_1m_stop_first_fee_stage2_pathwise_tests_present"])
        self.assertFalse(b["current_verified_state"]["physical_closed_1m_coin_path_to_cost_validator_verified"])
        self.assertFalse(b["current_verified_state"]["journal_automatically_connected_to_real_paper_writer"])
        self.assertFalse(b["current_verified_state"]["v3_paper_active"])
        self.assertTrue(b["release_requirements"]["physical_technical_proofs_required"])
        t=data("project-current-state.json")["pending_strategy_transition"]
        self.assertEqual(t["status"],"BLOCKED_RELEASE_EVIDENCE_NOT_V3_RUNNING")
        h=t["current_handoff_action"]
        self.assertFalse(h["v3_paper_active"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        self.assertFalse(h["v3_all_day_lessons_experimental_paper_20261011"]["physical_paper_writer_verified"])
        self.assertIn("PROSPECTIVE",h["next_concrete_action"])
        for x in ("v3_experimental_paper_initial_review_v1.py",
                  "v3_experimental_paper_model_prompt_v1.py",
                  "v3_experimental_paper_journal_v1.py",
                  "v3_experimental_paper_family_router_v1.py",
                  "v3_experimental_paper_pathwise_economics_v1.py"):
            self.assertTrue((ROOT/"paper_evaluator"/x).is_file())
        self.assertIn("V3 Experimental Paper",
                      (ROOT/"PROJECT_BACKLOG.md").read_text("utf-8"))

    def test_v3_cloud_deployed_is_not_fake_model_or_paper_release(self):
        x=data("research/v3/v3-paper-active-context-and-minipc-release-gates-20261011.json")
        d=x["cloud_deployment_20261011"]
        self.assertTrue(d["service_role_can_select"])
        self.assertTrue(d["service_role_can_insert"])
        self.assertFalse(d["service_role_can_update"])
        self.assertFalse(d["service_role_can_delete"])
        self.assertFalse(d["service_role_can_truncate"])
        self.assertTrue(d["credential_registered"])
        self.assertTrue(d["real_host_cloud_ack"])
        self.assertFalse(d["shared_v2r4_token_reuse"])
        self.assertTrue(d["v2r4_active_only"])
        self.assertFalse(d["real_money_actions"])
        j=data("project-current-state.json")
        h=j["pending_strategy_transition"]["current_handoff_action"]
        self.assertFalse(h["v3_paper_active"])
        self.assertTrue(h["v2r4_remains_only_active_paper"])
        state=h["v3_paper_runtime_stage_20261011"]
        self.assertTrue(state["cloud_schema_applied_verified"])
        self.assertTrue(state["edge_deployed_verified"])
        self.assertTrue(state["cloud_relay_secret_provisioned"])
        self.assertFalse(state["v3_paper_writer_single_process_continuous_verified"])
        budget=state.get("irreversible_model_spend") or h.get("one_model_prospective_canary_20261012")
        self.assertEqual(budget["max_http_attempts_including_retries"],1)
        self.assertTrue(budget["model_http_call_executed"])
        self.assertEqual(budget["remaining_model_http_authority"],0)
        self.assertEqual(budget["p4_decision"],"WAIT")
        watch=h["wait_paper_followup_observer_20261012"]
        self.assertEqual(watch["source_prospective_max_1m_capture_lag_minutes"],15)
        self.assertFalse(watch["runs_continuously_under_existing_windows_supervisor"])
        self.assertFalse(watch["real_new_cloud_wait_expiry_or_followup_ack_verified"])
        self.assertTrue(watch["original_model_budget_consumed"])
        self.assertFalse(watch["v3_paper_active"])
        self.assertTrue(watch["unknown_expired_not_false_negative"])
        observer=h["v3_bounded_live_observer_28h_20261012"]
        self.assertEqual(observer["latest_physical_heartbeat"],"HEALTHY_NO_NEW_CLOUD_EVENTS")
        self.assertEqual(observer["real_prospective_closed_1m_per_tracked_pair"],45)
        self.assertTrue(observer["task_healthy_verified"])
        self.assertFalse(observer["real_6h24h_mature_economic_cloud_outcomes_verified"])
        self.assertFalse(observer["task_window_reset"])
        self.assertEqual(observer["original_task_expiry_preserved"],"2026-10-13T12:00:12.2795431Z")
        self.assertFalse(observer["current_paper_series_independently_rechecked_this_turn"])
        self.assertFalse(budget["v3_paper_writer_active"])
        self.assertFalse(budget["old_pr186_budget_reused"])
        self.assertEqual(d["first_host_pair"],"EIGEN/EUR")
        self.assertEqual(d["first_host_receipts"],4)
        self.assertFalse(d["source_smart_money_connected"])
        self.assertFalse(state["physical_v3_paper_writer_running"])
        sql=(ROOT/"supabase/v3-paper-receipt-strict-service-privileges-20261011.sql").read_text("utf-8")
        self.assertIn("REVOKE UPDATE, DELETE, TRUNCATE",sql)
        wrapper=(ROOT/"tools/minipc-create-v3-paper-relay-token.ps1").read_text("utf-8")
        self.assertIn("sha256_for_cloud_registration",wrapper)
        self.assertIn("secret_itself_not_displayed=$true",wrapper)

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
