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
