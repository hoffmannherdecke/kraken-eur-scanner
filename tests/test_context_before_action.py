"""Negative and positive regression tests for source-first context preflight."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.context_before_action import (
    ROOT, ContextGateError, build, routed_sources, verify_receipt, v3_decision_inheritance, read_json as original_read_json,
)


class ContextBeforeActionTests(unittest.TestCase):

    def test_projectwide_ownership_is_not_limited_to_v3_or_runtime_guessing(self):
        required = json.loads(
            (ROOT / "research/project-followthrough-routing-v1.json").read_text()
        )["required_stream_ids"]
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                index = packet["project_component_owners"]
                self.assertEqual(index["kind"], "PROJECT_COMPONENT_OWNER_HANDOFF_V1")
                self.assertGreaterEqual(index["functional_stream_count"], 26)
                self.assertGreaterEqual(index["crosscut_project_area_count"], 9)
                components = {c["id"]: c for c in index["components"]}
                self.assertTrue(set(required).issubset(components))
                self.assertIn("mini_pc_deployment", components)
                self.assertIn("github_quota_and_cost", components)
                self.assertIn("security_permissions_and_rls", components)
                self.assertIn("source_quality", components)
                for c in components.values():
                    self.assertTrue(c["canonical_owner"])
                    self.assertTrue(c["next_gate"])
                    self.assertEqual(
                        c["actual_runtime_location"],
                        "REQUIRES_ORIGINAL_DEPLOYMENT_EVIDENCE")
                source_paths = {x["path"] for x in packet["source_index"]}
                self.assertIn("research/monitoring-evidence-routing-v1.json",
                              source_paths)
                self.assertIn("research/project-followthrough-routing-v1.json",
                              source_paths)
                self.assertFalse(packet["declared_status"]["live_runtime_independently_checked"])
        self.assertIn(
            "docs/v3-real-source-owner-topology-20261012.md",
            {x["path"] for x in build(ROOT, "operations")["source_index"]})

    def test_cpu_milestones_are_in_existing_architecture_and_operations_preflight(self):
        """Apply merged source milestones via the original context index, not a new manager."""
        import hashlib
        release_doc = "docs/v2r4-cpu-cache-versioned-technical-release-20261017.md"
        candidate = "tools/v2r4-paper-local-runtime.py"
        wait = "paper_evaluator/v2r4_wait_runtime.py"
        operations = build(ROOT, "operations")
        architecture = build(ROOT, "architecture")
        op_index = {item["path"]: item["sha256"] for item in operations["source_index"]}
        arch_index = {item["path"]: item["sha256"] for item in architecture["source_index"]}
        for path in (release_doc, candidate, wait):
            self.assertIn(path, op_index)
            self.assertEqual(op_index[path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
        self.assertIn(release_doc, arch_index)
        self.assertEqual(arch_index[release_doc], op_index[release_doc])
        self.assertFalse(operations["declared_status"]["live_runtime_independently_checked"])
        self.assertFalse(architecture["declared_status"]["live_runtime_independently_checked"])
        self.assertFalse(operations["has_runtime_side_effects"])
        self.assertIn("c2ff676196a08d89dbe2584144c70555149d49ca", (ROOT / release_doc).read_text("utf-8"))

    def test_v3_joint_cpu_golive_handoff_uses_same_release_owner(self):
        """V3 cutover must inherit CPU changes via same original source-index and owners."""
        import hashlib
        v3_path = "docs/v3-controlled-paper-cutover-20261011.md"
        cpu_path = "docs/v2r4-cpu-cache-versioned-technical-release-20261017.md"
        for scope in ("operations", "architecture"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                index = {x["path"]: x["sha256"] for x in packet["source_index"]}
                for path in (v3_path, cpu_path):
                    self.assertIn(path, index)
                    self.assertEqual(index[path], hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
                self.assertFalse(packet["declared_status"]["live_runtime_independently_checked"])
                self.assertFalse(packet["has_runtime_side_effects"])
        sop = (ROOT / v3_path).read_text("utf-8")
        self.assertIn("gemeinsamer Releasevorgang", sop)
        self.assertIn("PR326 WAIT", sop)
        self.assertIn("keine siebte Freigabe", sop.lower())

    def test_existing_operational_readback_route_is_available_for_all_scopes(self):
        """Every V3/ops/arch context can now locate the original existing reader."""
        import hashlib
        expected_paths = {
            "tools/minipc_cloud_evidence.py",
            "tools/minipc-watchdog.ps1",
            ".github/workflows/minipc-daily-status.yml",
        }
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                x = packet["operational_evidence_handoff"]
                self.assertEqual(x["kind"], "EXISTING_OPERATIONAL_EVIDENCE_HANDOFF_V1")
                self.assertEqual(x["status"], "SOURCE_ROUTES_REGISTERED_LIVE_DATA_NOT_QUERIED")
                self.assertEqual(set(x["source_paths"]), expected_paths)
                index = {v["path"]: v["sha256"] for v in packet["source_index"]}
                self.assertTrue(expected_paths.issubset(index))
                for path in expected_paths:
                    self.assertEqual(index[path], hashlib.sha256((ROOT / path).read_bytes()).hexdigest())
                    self.assertEqual(x["source_fingerprints"][path], index[path])
                self.assertEqual(x["original_cloud_sources"]["current"],
                                 "public.minipc_status_current")
                self.assertEqual(x["original_cloud_sources"]["alert"],
                                 "public.minipc_status_alert_state")
                self.assertEqual(x["original_cloud_sources"]["daily"],
                                 "public.minipc_daily_status")
                self.assertEqual(x["existing_fields"]["native_task_readback"],
                                 "payload.native_task_readback")
                self.assertEqual(x["existing_fields"]["daily_metric_provenance"],
                                 "payload.metric_provenance")
                self.assertEqual(x["github_original_watch_workflow_id"], 371909131)
                self.assertEqual(x["issue_number"], 353)
                for name in (
                    "live_windows_deployment_independently_verified",
                    "host_health_independently_verified",
                    "v3_model_decision_or_trade_verified",
                    "daily_scheduled_delivery_verified",
                    "slack_device_push_ack_verified",
                    "has_network_access",
                ):
                    self.assertIs(x[name], False)
                self.assertTrue(x["no_new_scheduler_or_status_authority"])
                self.assertTrue(x["no_trading_or_release_authority"])
                scan = x["scanner_artifact_handoff"]
                scanner_file = ".github/workflows/scan.yml"
                self.assertEqual(scan["kind"], "ORIGINAL_SCANNER_ARTIFACT_READBACK_ROUTE_V1")
                self.assertEqual(scan["source_workflow_file"], scanner_file)
                self.assertEqual(scan["source_fingerprint"], index[scanner_file])
                self.assertEqual(scan["source_fingerprint"], hashlib.sha256(
                    (ROOT / scanner_file).read_bytes()).hexdigest())
                self.assertEqual(scan["artifact_name_template"],
                                 "chat-handoff-{run_id}-{run_attempt}")
                self.assertEqual(scan["payload_file"], "candidates.jsonl")
                self.assertEqual(scan["retention_days"], 7)
                self.assertEqual(scan["action"], "REVIEW_ONLY_NOT_ORDER")
                self.assertIn("candidate_snapshot", scan["expected_event_kinds"])
                self.assertIn("market_context", scan["expected_event_kinds"])
                for flag in (
                    "actual_run_artifact_independently_verified",
                    "scan_candidate_sent_to_evaluator_verified",
                    "scan_candidate_written_to_cloud_verified",
                    "v3_model_decision_verified",
                    "trade_or_order_authorized",
                ):
                    self.assertIs(scan[flag], False)
                self.assertTrue(scan["no_new_scheduler_or_data_collector"])
                self.assertFalse(packet["has_network_access"])

    def test_original_operational_readback_wrong_source_fails_closed(self):
        route_path = ROOT / "research/context-before-action-routing-v1.json"
        original = original_read_json
        config = original(route_path)

        for change in (
            {"node_id": "SOME_OTHER_PC"},
            {"cloud_current_table": "public.random_fake_status"},
            {"github_original_watch_workflow_id": 12345},
            {"no_live_cloud_query_in_context_packet": False},
            {"no_paper_or_real_money_release": False},
            {"source_files": ["tools/minipc_cloud_evidence.py"]},
        ):
            tampered = copy.deepcopy(config)
            tampered["existing_operational_evidence_handoff"].update(change)

            def read_modified(path):
                if Path(path).resolve() == route_path.resolve():
                    return tampered
                return original(path)

            with self.subTest(change=change), patch(
                "tools.context_before_action.read_json", side_effect=read_modified
            ):
                with self.assertRaisesRegex(ContextGateError,
                                            "original MINI-PC"):
                    build(ROOT, "strategy")

    def test_original_scanner_artifact_handoff_rejects_fake_delivery_and_paths(self):
        route_path = ROOT / "research/context-before-action-routing-v1.json"
        original = original_read_json
        config = original(route_path)
        changes = (
            {"source_workflow_file": ".github/workflows/other.yml"},
            {"artifact_name_template": "chat-handoff-{run_id}"},
            {"artifact_retention_days": 90},
            {"review_action": "BUY_SCOUT"},
            {"no_implicit_delivery_to_scanner_detection_cloud": False},
            {"no_implicit_v2r4_v3_model_consumption": False},
            {"no_orders_or_strategy_release": False},
        )
        for mutation in changes:
            modified = copy.deepcopy(config)
            modified["existing_operational_evidence_handoff"]["scanner_handoff"].update(mutation)

            def read_modified(path):
                if Path(path).resolve() == route_path.resolve():
                    return modified
                return original(path)

            with self.subTest(mutation=mutation), patch(
                "tools.context_before_action.read_json", side_effect=read_modified
            ):
                with self.assertRaisesRegex(ContextGateError, "original scanner handoff"):
                    build(ROOT, "strategy")

    def test_component_owner_missing_is_not_assumed_healthy_or_locally_installed(self):
        from tools.context_before_action import project_component_owner_handoff
        routing_path = ROOT / "research/monitoring-evidence-routing-v1.json"
        j = json.loads(routing_path.read_text())
        j["streams"] = [x for x in j["streams"] if x["id"] != "smartmoney_h10"]
        original_read = original_read_json

        def omit_h10(path):
            if Path(path).resolve() == routing_path.resolve():
                return j
            return original_read(path)

        with patch("tools.context_before_action.read_json", side_effect=omit_h10):
            with self.assertRaisesRegex(ContextGateError, "stream owner coverage lost"):
                project_component_owner_handoff(ROOT)

    def test_every_scope_retrieves_versioned_canonical_sources(self):
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                self.assertEqual(packet["kind"], "CONTEXT_BEFORE_ACTION_PACKET_V1")
                self.assertGreater(len(packet["source_index"]), 5)
                self.assertEqual(packet["declared_status"]["live_runtime_independently_checked"], False)
                self.assertEqual(packet["has_runtime_side_effects"], False)
                self.assertEqual(packet["has_network_access"], False)
                self.assertEqual(len(packet["fingerprint"]), 64)

    def test_strategy_pack_carries_prior_decisions_and_component_status(self):
        packet = build(ROOT, "strategy")
        self.assertIn("strategy_learning_routes", packet)
        plan = packet["strategy_learning_routes"]
        self.assertGreaterEqual(len(plan["prioritized_packages"]), 5)
        self.assertTrue(any(x["id"] == "H3" for x in plan["h_statuses"]))
        self.assertIn("project-current-state.json", {
            item["path"] for item in packet["source_index"]})
        self.assertIn("research/v3-migration-ledger.json", {
            item["path"] for item in packet["source_index"]})

    def test_pr161_all_19_lessons_p0_p9_h1_h11_and_eight_conflicts_in_packet(self):
        packet = build(ROOT, "strategy")
        scope = packet["strategy_learning_routes"]
        self.assertEqual(len(scope["original_lessons"]), 19)
        self.assertEqual(len(scope["historical_conflict_resolutions"]), 8)
        self.assertEqual([x["order"] for x in scope["prioritized_packages"]],
                         list(range(10)))
        self.assertEqual({x["id"] for x in scope["h_statuses"]},
                         {f"H{x}" for x in range(1, 12)})
        self.assertIn("WAIT_TTL_NEVER_RECHECK",
                      {x["id"] for x in scope["original_lessons"]})
        self.assertEqual(scope["safety_gates"]["orders"], False)
        self.assertTrue(scope["not_a_runtime_or_economic_success_assertion"])
        for target in ("research/v3/v3-consolidated-strategy-integration-plan-20261011.json",
                       "research/v3/v3-buy-decision-lessons-implementation-matrix-20261011.json"):
            self.assertIn(target, {x["path"] for x in packet["source_index"]})
        self.assertIn("next", scope["next_action"])
        fusion = scope["optional_context_fusion"]
        self.assertTrue(fusion["optional_data_neutral"])
        self.assertTrue(fusion["not_a_trading_authorization"])
        self.assertEqual(len(fusion["source_lanes"]), 9)
        self.assertIn("smartmoney_h10", {x["stream_id"] for x in fusion["source_lanes"]})
        self.assertIn("prediction_h11", {x["stream_id"] for x in fusion["source_lanes"]})

    def test_all_17_paper_phase_insights_and_original_sources_in_v3_packet(self):
        learning = build(ROOT, "strategy")["strategy_learning_routes"]["paper_phase_learning"]
        self.assertEqual(learning["coverage_count"], 17)
        self.assertEqual(len(learning["findings"]), 17)
        self.assertEqual(len(learning["original_final_v2r3_strategic_dispositions"]), 12)
        self.assertEqual(learning["technical_only_exclusions"],
                         ["HYP-06", "REVALIDATION_DELAY"])
        self.assertTrue(learning["does_not_change_runtime_or_strategic_rules"])
        self.assertTrue(learning["does_not_claim_validated_net_positive_trades"])
        ids = {x["id"] for x in learning["findings"]}
        for required in (
            "V2R3_CONTINUITY_INITIAL_SMALL_SAMPLE_OPTIMISM",
            "V2R3_LATE_MATURING_LOSERS_NOT_SILENTLY_DROPPED",
            "V2R4_MATCHED_GOOD_AND_BAD_SETUP_FAMILIES",
            "V2R4_HIGH_UPSIDE_COINCIDES_WITH_BIG_DRAWDOWN",
        ):
            self.assertIn(required, ids)
        for x in learning["findings"]:
            self.assertTrue(x["source_paths"])
            self.assertTrue(x["v3_package_ids"])
            self.assertTrue(x["matrix_lesson_ids"])

    def test_all_20_old_cross_chat_promises_reach_v3_and_minipc_sources(self):
        packet = build(ROOT,"strategy")
        c = packet["strategy_learning_routes"]["prior_cross_chat_commitments"]
        self.assertEqual(c["coverage_count"],20)
        self.assertTrue(c["routed_not_all_operational"])
        self.assertTrue(c["no_new_scheduler_or_second_strategy"])
        ids={x["id"] for x in c["commitments"]}
        for required in (
            "MINIPC_ENTRY_PIT_OHLC","MINIPC_MISSED_MOVE_FUNNEL",
            "MINIPC_EXECUTION_COST_RESEARCH","MINIPC_BOUNDED_LOCAL_REPLAY",
            "MINIPC_OUTAGE_DELAY_DIAGNOSTICS","MINIPC_CAPACITY_GITHUB_OFFLOAD",
            "MINIPC_RAM_UPGRADE_GATE","MINIPC_OPTIONAL_AI_DIAGNOSTICS",
            "SEPARATE_AUTONOMOUS_AI_TRADING_PROJECT",
            "FULL_DYNAMIC_KRAKEN_SPOT_EUR",
            "MARKET_PHASES_AND_SENTIMENT","SOURCE_MANAGER_AUTONOMOUS_ACTIVE",
            "H2_H5_H8_H10_H11_OPTIONAL_CONTEXT",
            "H1_H3_H6_SHADOW_DISPOSITION",
            "JANSEN_HISTORICAL_WALKFORWARD_TRIAL_LEDGER",
            "RESILIENCE_AND_FUTURE_REAL_MONEY_INHERITANCE",
            "CONTINUOUS_PROJECT_AUTONOMY_AND_CONTEXT",
        ):
            self.assertIn(required,ids)
        for item in c["commitments"]:
            self.assertTrue((ROOT/item["source_path"]).is_file())
            self.assertTrue(item["next_gate"])
        for scope in ("strategy","research","architecture","operations"):
            sources={x["path"] for x in build(ROOT,scope)["source_index"]}
            self.assertIn("docs/minipc-analytics-rollout-v1.md",sources)
            self.assertIn("docs/minipc-support-block-plan-v1.md",sources)

    def test_past_mini_pc_commitment_cannot_be_silently_dropped(self):
        path="research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        def delete(j):
            j["prior_cross_chat_commitments"]["commitments"]=[
                x for x in j["prior_cross_chat_commitments"]["commitments"]
                if x["id"]!="MINIPC_ENTRY_PIT_OHLC"]
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(path,delete)):
            with self.assertRaisesRegex(ContextGateError,"cross-chat/Mini-PC user commitment"):
                v3_decision_inheritance(ROOT)
        def flip(j):
            j["prior_cross_chat_commitments"]["no_new_runner"]=False
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(path,flip)):
            with self.assertRaisesRegex(ContextGateError,"cross-chat work changed authority"):
                v3_decision_inheritance(ROOT)

    def test_missing_paper_finding_or_evidence_is_not_silently_lost(self):
        file = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        def drop(j):
            j["paper_phase_learning_crosswalk"]["findings"] = [
                x for x in j["paper_phase_learning_crosswalk"]["findings"]
                if x["id"] != "V2R4_MATCHED_GOOD_AND_BAD_SETUP_FAMILIES"]
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(file, drop)):
            with self.assertRaisesRegex(ContextGateError, "Paper learning ID lost"):
                v3_decision_inheritance(ROOT)
        def bogus(j):
            j["paper_phase_learning_crosswalk"]["findings"][0][
                "source_paths"] = ["research/work-analysis/not-real-report.md"]
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(file, bogus)):
            with self.assertRaisesRegex(ContextGateError, "original Paper source unavailable"):
                v3_decision_inheritance(ROOT)

    def test_paper_learning_cannot_be_detached_from_19_original_lessons(self):
        file = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        def bogus(j):
            j["paper_phase_learning_crosswalk"]["findings"][0][
                "matrix_lesson_ids"] = ["NEW_UNAPPROVED_BUY_RULE"]
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(file, bogus)):
            with self.assertRaisesRegex(ContextGateError, "unlinked to existing V3 owner"):
                v3_decision_inheritance(ROOT)

    def test_technical_only_v2r3_findings_cannot_pose_as_paper_strategy(self):
        file = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        def bogus(j):
            j["paper_phase_learning_crosswalk"]["excluded_nontrading_final_disposition_ids"] = []
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(file, bogus)):
            with self.assertRaisesRegex(ContextGateError, "technical-only exclusion missing"):
                v3_decision_inheritance(ROOT)

    def _mutate_v3_source(self, filename, mutate):
        original = copy.deepcopy(original_read_json(ROOT / filename))
        mutate(original)
        def substitute(path):
            return original if path.name == filename.split("/")[-1] else original_read_json(path)
        return substitute

    def test_deleted_historical_lesson_is_detected(self):
        file = "research/v3/v3-buy-decision-lessons-implementation-matrix-20261011.json"
        def removal(j):
            j["lessons"] = [x for x in j["lessons"] if x["id"] != "WAIT_TTL_NEVER_RECHECK"]
        with patch("tools.context_before_action.read_json",
                   side_effect=self._mutate_v3_source(file, removal)):
            with self.assertRaisesRegex(ContextGateError, "19 V3 findings"):
                v3_decision_inheritance(ROOT)

    def test_missing_package_or_h_component_is_detected(self):
        file = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        for key, item, expected in (("package_order", "P1_V3_B_REAL_SECOND_LEG_ENTRY", "P0-P9"),
                                    ("h_components", "H3", "H1-H11"),
                                    ("consistency_findings", "INPUT_ONLY_VS_NEW_POLICY",
                                     "eight explicit")):
            def remove(j):
                j[key] = [x for x in j[key] if x.get("id", x.get("key")) != item]
            with self.subTest(key=key):
                with patch("tools.context_before_action.read_json",
                           side_effect=self._mutate_v3_source(file, remove)):
                    with self.assertRaisesRegex(ContextGateError, expected):
                        v3_decision_inheritance(ROOT)

    def test_unapproved_trading_or_parallel_shadow_is_detected(self):
        file = "research/v3/v3-consolidated-strategy-integration-plan-20261011.json"
        for key, value, pattern in (("orders", True, "trading authority"),
                                    ("max_concurrent_strategy_changing_shadows", 2,
                                     "parallel strategy")):
            def unsafe(j):
                j["global_gates"][key] = value
            with self.subTest(key=key):
                with patch("tools.context_before_action.read_json",
                           side_effect=self._mutate_v3_source(file, unsafe)):
                    with self.assertRaisesRegex(ContextGateError, pattern):
                        v3_decision_inheritance(ROOT)

    def test_missing_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "research").mkdir()
            shutil.copyfile(ROOT / "research/context-before-action-routing-v1.json",
                            root / "research/context-before-action-routing-v1.json")
            with self.assertRaisesRegex(ContextGateError, "required source unavailable"):
                routed_sources(root, "strategy")

    def test_invalid_scope_fails_closed(self):
        with self.assertRaisesRegex(ContextGateError, "unsupported scope"):
            routed_sources(ROOT, "unknown")

    def _receipt(self, packet):
        return {
            "kind": "CONTEXT_REVIEW_RECEIPT_V1",
            "scope": packet["scope"],
            "fingerprint": packet["fingerprint"],
            "change_intent": "Ensure all canonical lessons are checked before architecture changes.",
            "planned_action": "Introduce a read-only preflight without adjusting any runtime behavior.",
            "superseded_or_rejected_alternatives": "Rejected adding another database, second backlog or duplicate scheduler.",
            "release_gate": "Existing CI and separate explicit strategic release approvals remain mandatory.",
            "canonical_followthrough_owner": "PROJECT_BACKLOG.md and the existing architecture governance contract.",
            "source_dispositions": [
                {
                    "path": item["path"],
                    "status": "APPLIED",
                    "reason": "Reviewed the relevant scope and retained the existing source precedence.",
                }
                for item in packet["source_index"]
            ],
        }

    def test_complete_receipt_is_structurally_valid_not_semantic_proof(self):
        packet = build(ROOT, "architecture")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            path.write_text(json.dumps(self._receipt(packet)), encoding="utf-8")
            result = verify_receipt(ROOT, packet, path)
            self.assertEqual(result["status"],
                             "RECEIPT_STRUCTURE_VERIFIED_NOT_SEMANTIC_PROOF")

    def test_missing_source_disposition_is_blocked(self):
        packet = build(ROOT, "architecture")
        receipt = self._receipt(packet)
        receipt["source_dispositions"].pop()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ContextGateError, "required source dispositions"):
                verify_receipt(ROOT, packet, path)

    def test_stale_receipt_is_blocked(self):
        packet = build(ROOT, "strategy")
        receipt = self._receipt(packet)
        receipt["fingerprint"] = "0" * 64
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ContextGateError, "stale"):
                verify_receipt(ROOT, packet, path)

    def test_empty_decision_rationale_is_blocked(self):
        packet = build(ROOT, "architecture")
        receipt = self._receipt(packet)
        receipt["source_dispositions"][0]["reason"] = "OK"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ContextGateError, "unsubstantiated"):
                verify_receipt(ROOT, packet, path)


if __name__ == "__main__":
    unittest.main()
