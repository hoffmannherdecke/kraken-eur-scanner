import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.project_followthrough_router import route, read_json as original_read_json

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


class ProjectFollowthroughRoutingTests(unittest.TestCase):
    def test_covers_all_registered_streams_and_project_areas_without_trading(self):
        result = route(ROOT, dt.datetime(2026, 10, 10, 8, 0, tzinfo=UTC))
        routing = json.loads((ROOT / "research/monitoring-evidence-routing-v1.json").read_text())
        self.assertEqual(result["stream_coverage_count"], len(routing["streams"]))
        self.assertGreaterEqual(result["crosscut_coverage_count"], 9)
        self.assertNotIn("V3-H3-ARCHIVE-DISPOSITION",
                         [x["id"] for x in result["ready_control_decisions"]])
        state = json.loads((ROOT / "project-current-state.json").read_text())
        h3 = next(x for x in state["closed_or_rejected_tracks"]
                  if x.get("id") == "V3-H3-SHADOW-001")
        self.assertEqual(h3.get("archive_disposition"), "DEFER_WITH_GATE")
        self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                      [x["id"] for x in result["gated_control_decisions"]])
        self.assertFalse(result["may_change_strategy"])
        self.assertFalse(result["may_execute_orders"])
        self.assertFalse(result["may_schedule_new_runs"])
        context = result["context_before_material_work"]
        self.assertTrue(context["required"])
        self.assertTrue(context["must_read_original_relevant_sources"])
        self.assertTrue(context["receipt_does_not_grant_release"])
        self.assertEqual(context["command"], "tools/context_before_action.py")

    def test_missing_context_handoff_blocks_substantive_work(self):
        manifest_path = "research/project-followthrough-routing-v1.json"
        original = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
        original.pop("context_preflight")
        def replaced(root, name):
            return original if name == manifest_path else original_read_json(root, name)
        with patch("tools.project_followthrough_router.read_json", side_effect=replaced):
            with self.assertRaisesRegex(ValueError, "context before material action"):
                route(ROOT, dt.datetime(2026, 10, 11, 8, 0, tzinfo=UTC))

    def test_due_gate_needs_real_report_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ("research/project-followthrough-routing-v1.json",
                         "research/monitoring-evidence-routing-v1.json",
                         "project-current-state.json", "research/work-analysis-state.json"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / path, target)
            for area in json.loads((root / "research/project-followthrough-routing-v1.json").read_text())["extra_project_areas"]:
                path = root / area["owner"]
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text("owner")
            late = dt.datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
            result = route(root, late)
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in result["ready_control_decisions"]])
            report = "research/work-analysis/v2r4-72h-decision.md"
            dst = root / report
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text("real review", encoding="utf-8")
            ackfile = root / "research/work-analysis-state.json"
            ack = json.loads(ackfile.read_text())
            ack.setdefault("acknowledgements", {}).setdefault("control_decision_reviews", {})[
                "V2R4_72H_STRATEGY_EPOCH_20261010"] = {
                    "status": "DECISION_PACKET_READY",
                    "completed_at_utc": "2026-10-11T07:00:00Z",
                    "report": report}
            ackfile.write_text(json.dumps(ack))
            result = route(root, late)
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW", result["previously_acknowledged"])
            ack["acknowledgements"]["control_decision_reviews"][
                "V2R4_72H_STRATEGY_EPOCH_20261010"]["completed_at_utc"] = "2099-10-11T07:00:00Z"
            ackfile.write_text(json.dumps(ack))
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in route(root, late)["ready_control_decisions"]])
            dst.unlink()
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in route(root, late)["ready_control_decisions"]])

    def test_missing_facets_or_unsafe_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ("research/project-followthrough-routing-v1.json",
                         "research/monitoring-evidence-routing-v1.json",
                         "project-current-state.json", "research/work-analysis-state.json"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / path, target)
            routing_path = root / "research/monitoring-evidence-routing-v1.json"
            routing = json.loads(routing_path.read_text())
            routing["streams"] = routing["streams"][:2]
            routing_path.write_text(json.dumps(routing))
            with self.assertRaisesRegex(ValueError, "missing/duplicate monitoring route"):
                route(root, dt.datetime.now(UTC))
            routing = json.loads((ROOT / "research/monitoring-evidence-routing-v1.json").read_text())
            routing["streams"][0]["id"] = "unregistered_replacement"
            routing_path.write_text(json.dumps(routing))
            with self.assertRaisesRegex(ValueError, "missing/duplicate monitoring route"):
                route(root, dt.datetime.now(UTC))


if __name__ == "__main__":
    unittest.main()
