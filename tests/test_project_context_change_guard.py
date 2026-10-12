"""Deterministic project-wide source handoff regression; no network or runtime."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path

from tools.context_before_action import build
from tools.project_context_change_guard import (
    ROOT, ChangeGateError, classify, check, git_paths, template, read_pr_review, START, END,
)


class ProjectContextChangeGuardTests(unittest.TestCase):
    def test_all_project_facets_cover_real_work(self):
        for path, expected in [
            ("paper_evaluator/v3_paper_x.py", {"strategy", "architecture"}),
            ("supabase/functions/worker/index.ts", {"architecture", "operations"}),
            ("research/market-source-candidates-v1.json", {"research"}),
            (".github/workflows/scan.yml", {"architecture", "operations", "strategy"}),
            ("tools/minipc-runtime-supervisor.ps1", {"architecture", "operations"}),
            ("project-current-state.json", {"strategy", "architecture", "operations", "research"}),
            ("unknown_new_system/file.xyz", {"architecture"}),
        ]:
            with self.subTest(path=path):
                self.assertTrue(expected.issubset(classify([path])))

    def good(self, paths):
        x = template(ROOT, paths)
        for field in ("prior_decisions", "reused_components", "no_duplicate_reason",
                      "change_and_evidence", "existing_owner", "approval_boundary",
                      "followthrough_and_ack", "remaining_unknowns"):
            x[field] = "Checked the original project decision and actual component before changing this."
        for item in x["scope_reviews"]:
            item["decision_applied"] = "Checked previous approvals and kept them unchanged for this review."
            item["existing_implementation"] = "The existing owner and source were reused, not duplicated here."
            item["conflicts_and_gates"] = "Any remaining runtime and financial permissions stay separately gated."
        return x

    def test_valid_review_scoped_sources_not_runtime_proof(self):
        paths = ["paper_evaluator/v3_paper_x.py", "tools/minipc-check.ps1",
                 "research/source-registry.json"]
        report = check(ROOT, paths, self.good(paths))
        self.assertEqual(set(report["scopes"]), classify(paths))
        self.assertFalse(report["runtime_or_trading_authorized"])
        self.assertFalse(report["model_understanding_proven"])

    def test_no_receipt_no_change_authority(self):
        with self.assertRaisesRegex(ChangeGateError, "wrong receipt kind"):
            check(ROOT, ["paper_evaluator/new.py"], {})

    def test_missing_facet_blocks(self):
        paths = ["project-current-state.json"]
        good = self.good(paths)
        good["scope_reviews"].pop()
        with self.assertRaisesRegex(ChangeGateError, "scope reviews"):
            check(ROOT, paths, good)

    def test_stale_packet_blocks(self):
        paths = ["paper_evaluator/test.py"]
        good = self.good(paths)
        good["scope_reviews"][0]["source_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ChangeGateError, "fingerprint stale"):
            check(ROOT, paths, good)

    def test_unknown_source_blocks(self):
        paths = ["paper_evaluator/test.py"]
        good = self.good(paths)
        good["scope_reviews"][0]["source_paths"].append("invented/never-existed.md")
        with self.assertRaisesRegex(ChangeGateError, "source references"):
            check(ROOT, paths, good)

    def test_placeholder_and_duplicate_scope_block(self):
        paths = ["paper_evaluator/test.py"]
        good = self.good(paths)
        good["reused_components"] = "not checked"
        with self.assertRaisesRegex(ChangeGateError, "reused_components"):
            check(ROOT, paths, good)
        good = self.good(paths)
        good["scope_reviews"].append(copy.deepcopy(good["scope_reviews"][0]))
        with self.assertRaisesRegex(ChangeGateError, "scope reviews"):
            check(ROOT, paths, good)

    def test_deletion_only_change_requires_actual_review(self):
        # A deletion-only PR previously disappeared under --diff-filter=ACMR.
        with patch("tools.project_context_change_guard.subprocess.run") as call:
            call.return_value.returncode = 0
            call.return_value.stdout = "docs/removed-component.md\\n"
            self.assertEqual(git_paths(ROOT, "HEAD^1", "HEAD"),
                             ["docs/removed-component.md"])
            self.assertIn("--diff-filter=ACMRD", call.call_args.args[0])
        with self.assertRaisesRegex(ChangeGateError, "no changed paths"):
            check(ROOT, [], self.good(["AGENTS.md"]))

    def test_unedited_review_template_is_not_a_valid_ack(self):
        paths = ["tools/project_context_change_guard.py"]
        draft = template(ROOT, paths)
        with self.assertRaisesRegex(ChangeGateError, "prior_decisions"):
            check(ROOT, paths, draft)
        reviewed = self.good(paths)
        reviewed["scope_reviews"][0]["decision_applied"] = (
            "REPLACE with previous decisions instead of reading anything"
        )
        with self.assertRaisesRegex(ChangeGateError, "decision_applied"):
            check(ROOT, paths, reviewed)

    def test_pr_body_must_contain_exactly_one_json(self):
        import json
        receipt = self.good(["AGENTS.md"])
        body = "Summary\n" + START + "\n" + json.dumps(receipt) + "\n" + END
        self.assertEqual(read_pr_review(body)["kind"], "PROJECT_CONTEXT_REVIEW_V1")
        with self.assertRaisesRegex(ChangeGateError, "needs one"):
            read_pr_review("ordinary prose no review")

    def test_canonical_packet_still_has_full_historical_strategy(self):
        for scope in ("strategy", "architecture", "operations", "research"):
            packet = build(ROOT, scope)
            self.assertEqual(packet["status"], "SOURCE_ROUTING_PASS_NEEDS_SUBSTANTIVE_REVIEW")
            self.assertTrue(packet["fingerprint"])


if __name__ == "__main__":
    unittest.main()
