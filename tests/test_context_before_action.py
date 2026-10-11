"""Negative and positive regression tests for source-first context preflight."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.context_before_action import (
    ROOT, ContextGateError, build, routed_sources, verify_receipt,
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
