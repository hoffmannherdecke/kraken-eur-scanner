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
        x["commitment_intake"]={
            "disposition":"REGISTERED_OR_REUSED",
            "commitment_ids":["V3_EXPERIMENTAL_PAPER_SIX_PROOFS"],
            "rationale":"The existing V3 Paper cutover six proof obligation remains open even after this code review.",
            "next_owner_and_gate":"The existing Paper release owner validates six original physical and Cloud proofs.",
            "no_claim_of_execution_without_evidence":True}
        x["architecture_integrity"] = {
            "change_mode": "EXTEND",
            "affected_stream_ids": ["scanner_detection", "realtime_timing"],
            "affected_area_ids": ["architecture_dependencies"],
            "reviewed_overlap_ids": ["realtime_timing", "price_volume_h6",
                                     "scanner_detection"],
            "affected_consumer_roles": ["GATED_STRATEGY_REVIEW"],
            "runtime_change_authorized": False,
            "original_component_and_owner": "The existing scanner and timing owners are the original accountable implementation locations.",
            "systemwide_integration_path": "Upstream existing scanner events flow downstream to the gated review without a second capture mechanism.",
            "reuse_or_retirement_decision": "Extend the present reviewer rather than inventing another running project manager or redundant registry.",
            "compatibility_and_failure_effects": "Existing scanner and timing interfaces remain stable while missing live evidence stays explicitly unverified.",
            "complexity_cost_and_maintenance": "One local reviewer extension has no new scheduler, persistent database, model budget or runtime overhead.",
            "validation_rollback_and_ack": "Existing CI negative tests and the original Work review gate are reused with reversible Git changes.",
        }
        for item in x["scope_reviews"]:
            item["decision_applied"] = "Checked previous approvals and kept them unchanged for this review."
            item["existing_implementation"] = "The existing owner and source were reused, not duplicated here."
            item["conflicts_and_gates"] = "Any remaining runtime and financial permissions stay separately gated."
        return x


    def test_future_followthrough_must_be_registered_or_explicitly_disposed(self):
        paths=["tools/source-inspector.py"]
        base=self.good(paths)
        for bad in (
          lambda x: x.pop("commitment_intake"),
          lambda x: x["commitment_intake"].update(commitment_ids=["FUTURE_INVISIBLE_999"]),
          lambda x: x["commitment_intake"].update(
              disposition="NO_NEW_FOLLOWUP",commitment_ids=["V3_EXPERIMENTAL_PAPER_SIX_PROOFS"]),
          lambda x: x["commitment_intake"].update(
              no_claim_of_execution_without_evidence=False),
        ):
            candidate=copy.deepcopy(base)
            bad(candidate)
            with self.assertRaises(ChangeGateError):
                check(ROOT,paths,candidate)
        claimed=copy.deepcopy(base)
        claimed["commitment_intake"].update(
            disposition="NO_NEW_FOLLOWUP",commitment_ids=[],
            rationale="This isolated regression merely confirms the existing receipt validator without scheduling new work.",
            next_owner_and_gate="The original project guard remains the sole owner and requires existing green CI evidence.")
        self.assertEqual(check(ROOT,paths,claimed)["commitment_intake_disposition"],
                         "NO_NEW_FOLLOWUP")

    def test_valid_review_scoped_sources_not_runtime_proof(self):
        paths = ["paper_evaluator/v3_paper_x.py", "tools/minipc-check.ps1",
                 "research/source-registry.json"]
        report = check(ROOT, paths, self.good(paths))
        self.assertEqual(set(report["scopes"]), classify(paths))
        self.assertFalse(report["runtime_or_trading_authorized"])
        self.assertFalse(report["model_understanding_proven"])


    def test_architecture_integrity_rejects_hidden_overlaps(self):
        paths = ["paper_evaluator/review.py"]
        good = self.good(paths)
        good["architecture_integrity"]["reviewed_overlap_ids"].pop()
        with self.assertRaisesRegex(ChangeGateError, "overlapping components omitted"):
            check(ROOT, paths, good)

    def test_architecture_integrity_rejects_fake_owner_or_downstream(self):
        paths = ["tools/new-source.py"]
        good = self.good(paths)
        good["architecture_integrity"]["affected_stream_ids"] = ["invented_poller"]
        with self.assertRaisesRegex(ChangeGateError, "architecture reference"):
            check(ROOT, paths, good)
        good = self.good(paths)
        good["architecture_integrity"]["affected_consumer_roles"] = []
        with self.assertRaisesRegex(ChangeGateError, "downstream consumers"):
            check(ROOT, paths, good)

    def test_architecture_integrity_no_doc_only_for_code_or_config(self):
        for path in ["tools/new-manager.py", "project-current-state.json",
                     ".github/workflows/new.yml"]:
            good = self.good([path])
            good["architecture_integrity"]["change_mode"] = "DOCUMENT_ONLY"
            with self.subTest(path=path):
                with self.assertRaisesRegex(ChangeGateError, "cannot claim DOCUMENT_ONLY"):
                    check(ROOT, [path], good)

    def test_architecture_integrity_no_implicit_runtime_approval(self):
        paths = ["paper_evaluator/new-worker.py"]
        good = self.good(paths)
        good["architecture_integrity"]["runtime_change_authorized"] = True
        with self.assertRaisesRegex(ChangeGateError, "cannot grant active runtime"):
            check(ROOT, paths, good)

    def test_architecture_integrity_rejects_missing_analysis(self):
        paths = ["tools/patch.py"]
        good = self.good(paths)
        good.pop("architecture_integrity")
        with self.assertRaisesRegex(ChangeGateError, "missing project-wide architecture"):
            check(ROOT, paths, good)
        good = self.good(paths)
        good["architecture_integrity"]["reuse_or_retirement_decision"] = "NOT CHECKED"
        with self.assertRaisesRegex(ChangeGateError, "reuse_or_retirement_decision"):
            check(ROOT, paths, good)

    def test_architecture_integrity_accepts_document_only_with_original_owner(self):
        paths = ["docs/architecture-review.md"]
        good = self.good(paths)
        good["architecture_integrity"]["change_mode"] = "DOCUMENT_ONLY"
        self.assertEqual(check(ROOT, paths, good)["architecture_integrity"]["impact_mode"],
                         "DOCUMENT_ONLY")

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

    def test_review_placeholder_guard_allows_ordinary_semantic_reuse_prose(self):
        from tools.project_context_change_guard import meaningful
        for natural in (
            "Do not replace GitHub rules; keep existing branch protection unchanged.",
            "We can replace the inaccurate description without creating a new owner.",
            "Replacing an obsolete name is different from removing authorization gates.",
        ):
            with self.subTest(natural=natural):
                self.assertTrue(meaningful(natural))
        for placeholder in (
            "REPLACE with current integration information from original code.",
            "TODO fill the original implementation after checking the registry.",
            "TBD check this before changing any actual deployment source.",
            "PLACEHOLDER source information will be supplied in the future.",
        ):
            with self.subTest(placeholder=placeholder):
                self.assertFalse(meaningful(placeholder))

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
            call.return_value.stdout = "docs/removed-component.md\n"
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
