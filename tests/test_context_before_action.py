"""Negative and positive regression tests for source-first context preflight."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.context_before_action import (
    ROOT, ContextGateError, build, routed_sources, verify_receipt, v3_decision_inheritance, read_json as original_read_json,
)


print('TEMP_CONTEXT_FINGERPRINTS_20261028', json.dumps({scope:build(ROOT,scope)['fingerprint'] for scope in ('architecture','operations','research','strategy')},sort_keys=True),flush=True)

class ContextBeforeActionTests(unittest.TestCase):

    def test_hardware_and_general_collaboration_never_inherit_v3_release(self):
        # Work domain selects the owner/gate family; knowledge scopes do not.
        for scope in ("operations", "architecture", "strategy", "research"):
            for domain in ("project_general", "infrastructure", "operations",
                           "research", "strategy_development"):
                with self.subTest(scope=scope, domain=domain):
                    packet = build(ROOT, scope, work_domain=domain)
                    bound = packet["work_domain_boundary"]
                    self.assertFalse(bound["requires_named_strategy_release_owner"])
                    self.assertFalse(bound["strategy_specific_release_gates_applicable"])
                    self.assertTrue(bound["scope_is_not_a_task_dependency"])
                    self.assertTrue(bound["project_rules_survive_v3_and_future_strategy_transitions"])
                    self.assertTrue(bound["only_existing_owner_and_task_specific_original_evidence_can_create_a_dependency"])
                    self.assertTrue(bound["not_a_runtime_or_release_authorization"])
                    selector = packet["next_action_selector"]
                    self.assertTrue(selector["no_automatic_v3_task_selection_for_project_or_infrastructure"])
                    v3 = next(x for x in selector["bounded_capabilities"]
                              if x["task"] == "v3_fixed_paths_readonly")
                    self.assertEqual(v3["applicable_to_current_work_domain"],
                                     False)
                    if domain == "infrastructure":
                        self.assertTrue(bound["hardware_change_is_not_a_strategy_milestone"])
                        self.assertFalse(v3["applicable_to_current_work_domain"])
                        self.assertTrue(bound["v3_specific_history_is_nonbinding_for_this_task"])

        v4 = build(ROOT, "strategy", work_domain="strategy_release")
        self.assertTrue(v4["work_domain_boundary"]["requires_named_strategy_release_owner"])
        self.assertTrue(v4["work_domain_boundary"]["strategy_specific_release_gates_applicable"])
        self.assertTrue(v4["work_domain_boundary"]["not_a_runtime_or_release_authorization"])
        self.assertEqual(v4["work_domain_boundary"]["owner_lane"],
                         "EXPLICIT_NAMED_STRATEGY_RELEASE_OWNER")
        # Even release routing does not hard-code V3 as the only future version.
        self.assertNotIn("V3", v4["work_domain_boundary"]["owner_lane"])
        self.assertEqual(v4["next_action_selector"]["work_domain"], "strategy_release")

    def test_priority_evidence_and_explicit_version_no_reopen_of_maintenance(self):
        from tools.context_before_action import compact_decision_brief
        generic = build(ROOT, "strategy")
        self.assertNotIn("strategy_learning_routes", generic)
        self.assertEqual(generic["current_reading_plan"]["strategy_version"], "UNSPECIFIED")
        self.assertTrue(generic["current_reading_plan"]["historical_plans_not_open_tasks"])
        self.assertTrue(generic["current_reading_plan"]["complete_source_index_preserved"])
        self.assertNotIn("docs/v3-controlled-paper-cutover-20261011.md",
                         generic["current_reading_plan"]["priority_source_paths"])
        release = build(ROOT, "strategy", work_domain="strategy_release", strategy_version="V3")
        self.assertIn("strategy_learning_routes", release)
        self.assertTrue(release["next_action_selector"]["bounded_capabilities"][2]["applicable_to_current_work_domain"])
        brief = compact_decision_brief(release)
        self.assertIn("--work-domain strategy_release --strategy-version V3",
                      brief["full_packet_command"])
        self.assertEqual(generic["fingerprint"], release["fingerprint"])
        v4 = build(ROOT, "strategy", work_domain="strategy_release", strategy_version="V4")
        self.assertNotIn("strategy_learning_routes", v4)
        self.assertFalse(v4["next_action_selector"]["bounded_capabilities"][2]["applicable_to_current_work_domain"])
        infra = build(ROOT, "operations", work_domain="infrastructure")
        self.assertTrue(infra["current_reading_plan"]["historical_plans_not_open_tasks"])
        self.assertFalse(infra["work_domain_boundary"]["requires_named_strategy_release_owner"])
        with self.assertRaises(ContextGateError):
            build(ROOT, "operations", strategy_version="../../V3")

    def test_work_domain_policy_fails_closed_on_missing_or_weakened_boundaries(self):
        from tools.context_before_action import project_work_domain_boundary
        config = original_read_json(ROOT / "research/context-before-action-routing-v1.json")
        import copy
        for mutate in (
            lambda p: p.pop("work_domain_policy"),
            lambda p: p["work_domain_policy"].update(
                hardware_upgrade_alone_never_creates_strategy_gate=False),
            lambda p: p["work_domain_policy"].update(
                future_strategy_versions_inherit_projectwide_collaboration_rules=False),
            lambda p: p["work_domain_policy"]["domains"]["infrastructure"].update(
                requires_strategy_release=True),
            lambda p: p["work_domain_policy"]["domains"].pop("strategy_release"),
        ):
            invalid = copy.deepcopy(config)
            mutate(invalid)
            with self.assertRaises(ContextGateError):
                project_work_domain_boundary(ROOT, invalid, "infrastructure")
        with self.assertRaises(ContextGateError):
            project_work_domain_boundary(ROOT, config, "unknown")

    def test_compact_brief_routes_real_owner_without_losing_full_context(self):
        from tools.context_before_action import compact_decision_brief
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                full = build(ROOT, scope)
                brief = compact_decision_brief(full)
                self.assertEqual(brief["kind"], "CONTEXT_BEFORE_ACTION_DECISION_BRIEF_V1")
                self.assertEqual(brief["fingerprint"], full["fingerprint"])
                self.assertEqual(brief["scope"], scope)
                self.assertLess(len(json.dumps(brief)), 3500)
                self.assertNotIn("source_index", brief)
                self.assertNotIn("strategy_learning_routes", brief)
                self.assertEqual(brief["routed_source_count"], len(full["source_index"]))
                self.assertTrue(brief["full_packet_required_before_material_change"])
                self.assertIn("AGENTS.md", brief["priority_sources_to_read"])
                self.assertEqual(brief["decision_order"][0],
                                 "USE_AVAILABLE_CONNECTED_GITHUB_OR_CLOUD_READBACK_FIRST")
                self.assertEqual(brief["decision_order"][-1],
                                 "ASK_USER_FOR_SMALLEST_SAFE_PHYSICAL_STEP_ONLY_IF_NEEDED")
                self.assertEqual(brief["connected_tools"], "MUST_CHECK_IN_CURRENT_CHAT")
                self.assertEqual(brief["live_host"], "NOT_CHECKED_BY_SOURCE_PACKET")
                self.assertTrue(brief["no_live_runtime_or_trading_authority"])
                self.assertTrue(brief["history_or_hash_is_not_live_proof"])

    def test_existing_minipc_task_sources_are_discoverable_not_implicitly_authorized(self):
        expected = sorted(p.stem for p in
                          (ROOT / "tools/minipc_runner_tasks").glob("*.ps1"))
        self.assertGreaterEqual(len(expected), 8)
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                selector = packet["next_action_selector"]
                self.assertEqual(selector["repository_task_source_names"], expected)
                self.assertTrue(selector["repository_inventory_is_not_host_approval"])
                from tools.context_before_action import compact_decision_brief
                brief = compact_decision_brief(packet)
                self.assertEqual(brief["repository_task_source_names"], expected)
                self.assertTrue(brief["repository_inventory_is_not_host_approval"])
                self.assertFalse(selector.get("host_online_now") == "ONLINE")

    def test_protected_main_has_one_unambiguous_required_validate_job(self):
        # GitHub ruleset requires "validate". Control-plane is path-selective:
        # it must not supply a competing identically named check.
        architecture = (ROOT / ".github/workflows/architecture-cleanup-validation.yml").read_text()
        control = (ROOT / ".github/workflows/project-control-plane-guard.yml").read_text()
        context = (ROOT / ".github/workflows/project-context-change-gate.yml").read_text()
        self.assertIn("  validate:\n", architecture)
        self.assertIn("  control-plane-validate:\n", control)
        self.assertNotIn("  validate:\n", control)
        self.assertIn("  source-and-review:\n", context)
        self.assertIn("  pull_request:\n", context)
        self.assertIn("  pull_request:\n", architecture)

    def test_compact_agents_preserves_full_rule_and_archival_boundary(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        archive = (ROOT / "docs/project-context-instruction-archive-20261019.md").read_text(encoding="utf-8")
        self.assertLess(len(agents), 18500)
        self.assertIn("Kontext", agents)
        self.assertIn("PROJECT_CONTEXT_REVIEW_V1", agents)
        self.assertIn("Keine Änderung aktiver Trading", agents)
        self.assertIn("ohne neue Nutzerantwort weiterarbeiten", agents)
        self.assertIn("MINIPC_TASK_V1", agents)
        self.assertIn("kein allgemeiner Befehlskanal", agents)
        self.assertIn("ARCHIV / NICHT AKTUELLE STATUS-AUTORITÄT", archive)
        self.assertIn("CryptoSupport - Bounded Runner Window", archive)
        self.assertIn("docs/project-context-instruction-archive-20261019.md", agents)

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

    def test_interactive_chat_goal_is_in_every_actual_context_packet(self):
        """Ordinary chat continuation is delivered directly; no Work-only source pointer."""
        import hashlib

        canonical = ROOT / "AGENTS.md"
        actual_hash = hashlib.sha256(canonical.read_bytes()).hexdigest()
        heading = "## Dialog-Arbeitsmodus: vereinbartes Ziel statt einzelner Arbeitsblock"
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                index = {row["path"]: row["sha256"] for row in packet["source_index"]}
                self.assertEqual(index["AGENTS.md"], actual_hash)
                x = packet["interactive_chat_goal"]
                self.assertEqual(x["kind"], "INTERACTIVE_CHAT_GOAL_CONTINUATION_HANDOFF_V1")
                self.assertEqual(x["canonical_source"], "AGENTS.md")
                self.assertEqual(x["source_sha256"], actual_hash)
                self.assertIn(heading, x["instruction_from_original"])
                self.assertIn("vereinbarte, tatsächlich prüfbare Zielzustand", x["instruction_from_original"])
                self.assertIn("ohne neue Nutzerantwort weiterarbeiten", x["instruction_from_original"])
                self.assertTrue(x["progress_note_is_not_a_stop"])
                self.assertTrue(x["finish_at_verified_goal_or_real_blocker"])
                self.assertTrue(x["new_chat_must_actively_load_context"])
                self.assertFalse(x["automatic_new_chat_bootstrap_guaranteed"])
                self.assertTrue(x["no_new_scheduler_or_execution_authority"])
                self.assertFalse(packet["has_runtime_side_effects"])
                self.assertFalse(packet["has_network_access"])

    def test_missing_or_incomplete_canonical_interactive_chat_rule_fails_closed(self):
        """A missing or weakened original section cannot appear as a successful handoff."""
        from tools.context_before_action import interactive_chat_goal_handoff
        source_index = [{"path": "AGENTS.md", "sha256": "example"}]
        original_reader = Path.read_text

        def altered_read(file, *args, **kwargs):
            text = original_reader(file, *args, **kwargs)
            if Path(file).name == "AGENTS.md":
                return text.replace("ohne neue Nutzerantwort weiterarbeiten", "await a new user message")
            return text

        with patch.object(Path, "read_text", autospec=True, side_effect=altered_read):
            with self.assertRaisesRegex(ContextGateError, "interactive chat rule incomplete"):
                interactive_chat_goal_handoff(ROOT, source_index)
        with self.assertRaisesRegex(ContextGateError, "interactive chat rule not indexed"):
            interactive_chat_goal_handoff(ROOT, [])

    def test_readonly_log_diagnostics_capability_routed_projectwide_without_host_claim(self):
        """New reviewed task must become discoverable for ALL project scopes."""
        config = json.loads((ROOT / "research/context-before-action-routing-v1.json").read_text())
        runner = config["existing_operational_evidence_handoff"]["projectwide_reviewed_runner"]
        diag = runner["reviewed_readonly_log_diagnostics"]
        script = "tools/minipc_runner_tasks/log_status_summary.ps1"
        self.assertEqual(diag["task_name"], "log_status_summary")
        self.assertEqual(diag["source_script"], script)
        self.assertEqual(diag["source_ci_status"], "MERGED_SOURCE_AND_REVIEW_PASS")
        self.assertEqual(diag["actual_windows_task_e2e"], "PENDING_ORIGINAL_HOST_ACK")
        self.assertEqual(diag["actual_source_file_acl"], "UNKNOWN_UNTIL_RUNNER_READBACK")
        self.assertTrue(diag["request_via_existing_workflow_only"])
        self.assertTrue(diag["no_windows_acl_changes"])
        self.assertTrue(diag["no_raw_log_lines_or_filenames"])
        self.assertTrue(diag["prefer_before_manual_powershell_for_applicable_tasks"])
        followthrough = json.loads((ROOT / "research/project-followthrough-routing-v1.json").read_text())
        deployment = next(x for x in followthrough["extra_project_areas"]
                          if x["id"] == "mini_pc_deployment")
        self.assertEqual(deployment["reviewed_readonly_log_diagnostics_source"], script)
        self.assertEqual(deployment["reviewed_readonly_log_diagnostics_owner_issue"], 353)
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                index = {x["path"]: x for x in packet["source_index"]}
                self.assertIn(script, index)
                self.assertEqual(len(index[script]["sha256"]), 64)
                handoff = packet["operational_evidence_handoff"]["projectwide_reviewed_runner"]
                available = handoff["reviewed_readonly_log_diagnostics"]
                self.assertEqual(available["source_script"], script)
                self.assertEqual(available["source_fingerprint"], index[script]["sha256"])
                self.assertTrue(available["prefer_before_manual_powershell"])
                self.assertEqual(available["actual_windows_task_e2e"], "PENDING_ORIGINAL_HOST_ACK")
                self.assertTrue(available["no_user_supplied_shellcode_or_acl_changes"])
                self.assertEqual(packet["declared_status"]["live_runtime_independently_checked"], False)

    def test_reuse_first_minipc_capability_policy_is_present_in_all_scopes(self):
        import hashlib
        policy_file = "docs/minipc-powershell-capability-reuse-v1.md"
        bundle = "tools/minipc_runner_tasks/operations_readonly_bundle.ps1"
        expected = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in (policy_file, bundle)
        }
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                sources = {x["path"]: x["sha256"] for x in packet["source_index"]}
                self.assertEqual(sources[policy_file], expected[policy_file])
                self.assertEqual(sources[bundle], expected[bundle])
                reuse = packet["operational_evidence_handoff"]["projectwide_reviewed_runner"]["capability_reuse_policy"]
                self.assertEqual(reuse["kind"], "MINIPC_REUSE_FIRST_POLICY_V1")
                self.assertEqual(reuse["policy_source_fingerprint"], expected[policy_file])
                self.assertEqual(reuse["bundle_source_fingerprint"], expected[bundle])
                self.assertEqual(reuse["source_task_name"], "operations_readonly_bundle")
                self.assertEqual(reuse["child_source_tasks"],
                                 ["host_safety_probe", "windows_maintenance_snapshot", "log_status_summary"])
                self.assertTrue(reuse["no_repeat_runner_e2e_without_changed_boundary"])
                self.assertTrue(reuse["existing_request_and_single_ack_only_for_previously_approved_tasks"])
                self.assertTrue(reuse["new_capabilities_one_review_and_targeted_test"])
                self.assertTrue(reuse["new_acl_or_write_rights_require_separate_permission"])
                self.assertTrue(reuse["no_new_workflow_scheduler_or_manager"])
                self.assertTrue(reuse["no_arbitrary_powershell_or_parameters"])
                self.assertTrue(reuse["runtime_evidence_not_established_by_context_packet"])
                self.assertTrue(reuse["original_host_receipt_must_be_independently_observed"])
                self.assertEqual(reuse["bundle_original_host_status"], "PASS_ONE_RESTRICTED_SOURCE_PINNED_WINDOWS_RUN")
                self.assertEqual(reuse["bundle_original_host_evidence"]["private_original_workflow_run_id"], 39269905027)
                self.assertEqual(reuse["bundle_original_host_evidence"]["overall_task_execution"], "COMPLETE")
                self.assertEqual(reuse["bundle_original_host_evidence"]["log_sources_readback"], "PARTIAL_OR_UNAVAILABLE")
                self.assertTrue(reuse["future_write_acl_currently_granted"])
                self.assertTrue(reuse["workspace_only"])
                self.assertEqual(reuse["next_permission_stage"],
                                 "SCOPED_WORKSPACE_HOST_PASS_NO_ADDITIONAL_PERMISSIONS")

    def test_reviewed_windows_snapshot_routed_in_every_scope_without_host_claim(self):
        import hashlib
        script = "tools/minipc_runner_tasks/windows_maintenance_snapshot.ps1"
        expected = hashlib.sha256((ROOT / script).read_bytes()).hexdigest()
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                sources = {x["path"]: x["sha256"] for x in packet["source_index"]}
                self.assertEqual(sources[script], expected)
                record = packet["operational_evidence_handoff"]["projectwide_reviewed_runner"]["reviewed_windows_maintenance_diagnostics"]
                self.assertEqual(record["task"], "windows_maintenance_snapshot")
                self.assertEqual(record["source_fingerprint"], expected)
                self.assertEqual(record["actual_windows_task_e2e"], "PASS_RESTRICTED_HOST_RUN_AND_SANITIZED_GITHUB_STATUS")
                self.assertEqual(record["original_host_evidence"]["original_workflow_run_id"], 39257496377)
                self.assertEqual(record["original_host_evidence"]["bounded_scheduler_task_metadata"], "READ_OK_RESTRICTED_ACCOUNT")
                self.assertEqual(record["original_host_evidence"]["task_read_method"], "CMDLET")
                self.assertEqual(record["original_host_evidence"]["task_readback"], "READ_OK")
                self.assertEqual(record["target_task_read_access_original_host"], "PASS_NATIVE_CMDLET_AFTER_SINGLE_TASK_READ_ACE")
                self.assertTrue(record["no_broad_or_admin_acl_grant"])
                self.assertFalse(record["post_window_safe_pause_original_ack_pending"])
                witness = record["first_window_host_evidence"]
                self.assertEqual(witness["safe_pause"], "PASS")
                self.assertEqual(witness["task_state"], "Ready")
                self.assertEqual(witness["task_last_result"], 0)
                self.assertEqual(witness["runner_service_state"], "Stopped")
                self.assertEqual(witness["runner_service_start_mode"], "Disabled")
                self.assertFalse(witness["future_windows_guaranteed"])
                self.assertTrue(witness["cpu_maintenance_requires_fresh_safe_pause"])
                self.assertTrue(record["no_acl_elevation_for_missing_scheduler_readback"])
                self.assertTrue(record["use_existing_runner_only"])
                self.assertTrue(record["no_arbitrary_shell_or_admin"])
                self.assertTrue(record["no_runtime_or_reboot_authority"])
                self.assertEqual(record["safe_github_job_log_marker"], "MINIPC_MAINTENANCE_SAFE_SUMMARY_V1")
                self.assertFalse(record["host_original_ack_still_required"])
                self.assertFalse(packet["declared_status"]["live_runtime_independently_checked"])

    def test_projectwide_reviewed_minipc_runner_is_routed_in_every_context_scope(self):
        """Same already-tested low-privilege capability must be visible without a second manager."""
        registry = json.loads((ROOT / "research/context-before-action-routing-v1.json").read_text())
        routing = registry["existing_operational_evidence_handoff"]["projectwide_reviewed_runner"]
        doc = "docs/minipc-runner-bounded-windows-v1.md"
        self.assertEqual(routing["canonical_runbook"], doc)
        self.assertEqual(routing["github_issue"], 353)
        self.assertEqual(routing["private_issue"], 13)
        self.assertEqual(routing["windows_task_name"], "CryptoSupport - Bounded Runner Window")
        self.assertTrue(routing["windows_task_schedule_enabled_host_confirmed"])
        self.assertTrue(routing["manual_one_off_e2e"]["passed"])
        self.assertEqual(routing["manual_one_off_e2e"]["last_task_result"], 0)
        self.assertEqual(
            routing["first_unattended_periodic_window_e2e"],
            "PASS_ONE_UNATTENDED_NATURAL_WINDOW_ORIGINAL_HOST_20261019",
        )
        self.assertFalse(routing["new_chat_auto_import_guaranteed"])
        self.assertTrue(routing["no_unreviewed_powershell_or_elevated_host_access"])
        self.assertTrue(routing["no_new_project_manager_or_schedule"])
        extra = json.loads(
            (ROOT / "research/project-followthrough-routing-v1.json").read_text()
        )["extra_project_areas"]
        deployment = next(x for x in extra if x["id"] == "mini_pc_deployment")
        self.assertEqual(deployment["owner"], "PROJECT_BACKLOG.md")
        self.assertEqual(deployment["execution_capability_source"], doc)
        self.assertIn("UNATTENDED_WINDOW_ORIGINAL_HOST_VERIFIED_20261019", deployment["gate"])
        self.assertEqual(
            set(routing["all_project_scopes"]),
            {"strategy", "architecture", "operations", "research"},
        )
        for scope in routing["all_project_scopes"]:
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                source_paths = {x["path"] for x in packet["source_index"]}
                self.assertIn(doc, source_paths)
                handoff = packet["operational_evidence_handoff"]["projectwide_reviewed_runner"]
                self.assertEqual(handoff["owner_issue"], 353)
                self.assertEqual(handoff["private_runner_issue"], 13)
                self.assertEqual(handoff["canonical_runbook"], doc)
                self.assertEqual(handoff["manual_one_off_task_result"], 0)
                self.assertTrue(handoff["windows_schedule_enabled_at_original_user_photo"])
                self.assertEqual(
                    handoff["status"],
                    "FIRST_NATURAL_SAFE_PAUSE_HOST_PASS_CPU_MAINTENANCE_REQUIRES_FRESH_GATE",
                )
                self.assertFalse(handoff["live_host_status_independently_verified_by_this_packet"])
                self.assertTrue(handoff["no_arbitrary_shell_or_trading_authority"])
                component = next(
                    x for x in packet["project_component_owners"]["components"]
                    if x["id"] == "mini_pc_deployment"
                )
                self.assertEqual(component["canonical_owner"], "PROJECT_BACKLOG.md")
                self.assertEqual(
                    packet["declared_status"]["live_runtime_independently_checked"], False
                )

    def test_real_original_host_capabilities_in_every_scope_and_manual_fallback(self):
        """Ensure the original host evidence reaches the actual packet consumer."""
        for scope in ("strategy", "architecture", "operations", "research"):
            with self.subTest(scope=scope):
                packet = build(ROOT, scope)
                sel = packet["next_action_selector"]
                self.assertEqual(sel["kind"], "PROJECT_NEXT_ACTION_SELECTOR_V1")
                self.assertEqual(sel["decision_order"][0], "USE_AVAILABLE_CONNECTED_GITHUB_OR_CLOUD_READBACK_FIRST")
                self.assertEqual(sel["decision_order"][-1], "ASK_USER_FOR_SMALLEST_SAFE_PHYSICAL_STEP_ONLY_IF_NEEDED")
                self.assertEqual(sel["connected_tool_availability"], "MUST_CHECK_IN_CURRENT_CHAT")
                self.assertEqual(sel["host_online_now"], "NOT_CHECKED_BY_SOURCE_PACKET")
                self.assertTrue(sel["historical_ack_not_live_proof"])
                self.assertTrue(sel["no_arbitrary_shell_or_admin_rights"])
                self.assertEqual([row["task"] for row in sel["bounded_capabilities"]],
                                 ["operations_readonly_bundle", "workspace_report", "v3_fixed_paths_readonly"])
                runner = packet["operational_evidence_handoff"]["projectwide_reviewed_runner"]
                ws = runner["scoped_workspace"]
                self.assertTrue(ws["source_review_pass"])
                self.assertEqual(ws["restricted_task_write_ack"], "PASS_ORIGINAL_JOB_39283677017")
                self.assertEqual(ws["original_host_evidence"]["write_read_delete_probe"], "PASS")
                self.assertFalse(ws["live_write_access_reverified_by_this_packet"])
                self.assertTrue(ws["no_unscoped_writes"])
                v3 = runner["reviewed_v3_fixed_paths"]
                self.assertEqual(v3["original_host_status"], "PASS_ORIGINAL_JOB_39313293207")
                self.assertEqual(v3["original_host_evidence"]["staging_nested_scan"], "TOO_MANY_CHILDREN")
                self.assertFalse(v3["live_v3_paths_reverified_by_this_packet"])
                self.assertTrue(v3["no_arbitrary_path_query"])

    def test_action_selector_fails_closed_on_stale_success_or_permissions(self):
        from tools.context_before_action import existing_operational_evidence_handoff
        data = original_read_json(ROOT / "research/context-before-action-routing-v1.json")
        index = build(ROOT, "operations")["source_index"]
        for mutate in (
            lambda runner: runner["scoped_workspace"].update(source_review_pass=False),
            lambda runner: runner["scoped_workspace"].update(restricted_task_write_ack="PENDING"),
            lambda runner: runner["reviewed_v3_fixed_paths"].update(original_host_status="PENDING"),
            lambda runner: runner["capability_reuse_policy"].update(future_write_acl_currently_granted=False),
        ):
            with self.subTest(mutation=mutate):
                altered = copy.deepcopy(data)
                mutate(altered["existing_operational_evidence_handoff"]["projectwide_reviewed_runner"])
                with self.assertRaises(ContextGateError):
                    existing_operational_evidence_handoff(altered, index)

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
        self.assertIn("keine siebte freigabe", sop.lower())

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
                    build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")

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
                    build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")

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
        packet = build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")
        self.assertIn("strategy_learning_routes", packet)
        plan = packet["strategy_learning_routes"]
        self.assertGreaterEqual(len(plan["prioritized_packages"]), 5)
        self.assertTrue(any(x["id"] == "H3" for x in plan["h_statuses"]))
        self.assertIn("project-current-state.json", {
            item["path"] for item in packet["source_index"]})
        self.assertIn("research/v3-migration-ledger.json", {
            item["path"] for item in packet["source_index"]})

    def test_pr161_all_19_lessons_p0_p9_h1_h11_and_eight_conflicts_in_packet(self):
        packet = build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")
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
        learning = build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")["strategy_learning_routes"]["paper_phase_learning"]
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
        packet = build(ROOT,"strategy",work_domain="strategy_development",strategy_version="V3")
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
        packet = build(ROOT, "strategy", work_domain="strategy_development", strategy_version="V3")
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



class LiveOwnerReadbackTests(unittest.TestCase):
    """Regression: a completed source never reopens from an older owner snapshot."""

    BASE = "https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner"

    def fake_fetch(self, url):
        if url.endswith("/commits/main"):
            return {"sha": "a" * 40}, ""
        for number in (99, 353):
            if url.endswith(f"/issues/{number}"):
                return {
                    "number": number, "state": "open",
                    "html_url": f"https://github.com/example/repo/issues/{number}",
                    "updated_at": "2026-10-28T12:00:00Z",
                    "body": "CURRENT owner: PR608 source and staging DONE; runtime still HOLD"
                }, ""
            first = self.BASE + f"/issues/{number}/comments?per_page=10"
            if url == first:
                return [{"body": "historical PR593 must not reopen source",
                         "html_url": "https://github.com/old-comment"}], (
                    f'<{first}&page=8>; rel="last"')
            if url == first + "&page=8":
                return [{"body": "CURRENT original ACK: PR608 STAGED PASS; "
                                 "real Writer/Notebook/CAS still pending",
                         "html_url": "https://github.com/current-comment",
                         "created_at": "2026-10-28T12:01:00Z"}], ""
        raise AssertionError("unexpected endpoint: " + url)

    def test_v3_live_owner_reads_both_managers_and_last_comment_page(self):
        from tools.context_before_action import live_owner_readback
        packet = live_owner_readback(
            "strategy_release", "V3",
            fetcher=self.fake_fetch, expected_main="a" * 40)
        self.assertEqual([x["issue"] for x in packet["owners"]], [353, 99])
        self.assertEqual(packet["main_sha"], "a" * 40)
        self.assertEqual(packet["status"],
                         "CURRENT_GITHUB_OWNER_READBACK_ONLY_NOT_HOST_OR_CLOUD_ACK")
        self.assertTrue(packet["source_and_staging_done_must_not_be_reopened_by_pending_runtime"])
        self.assertTrue(packet["no_new_development_without_specific_new_defect_evidence"])
        self.assertIn("CURRENT original ACK",
                      packet["owners"][1]["latest_comments"][-1]["excerpt"])
        self.assertNotIn("historical PR593",
                         packet["owners"][1]["latest_comments"][-1]["excerpt"])

    def test_current_owner_section_is_not_cut_before_operative_priority(self):
        from tools.context_before_action import live_owner_readback
        current = "Current decision " + ("reviewed evidence " * 270)
        self.assertGreater(len(current), 4500)
        current += "\n**Priorität nach Audit:** einzig bestehender Originalhost-Gate\n"
        body = current + "\n---\nARCHIVED PR593 is not a new task"
        def fetch(url):
            item, link = self.fake_fetch(url)
            if url.endswith("/issues/99"):
                item = dict(item, body=body)
            if url.endswith("/issues/353"):
                item = dict(item, body="CURRENT PROJECT RULE\n---\nARCHIVED OLD RULE")
            return item, link
        packet = live_owner_readback("strategy_release", "V3", fetcher=fetch)
        current_v3 = packet["owners"][1]
        self.assertIn("**Priorität nach Audit:**", current_v3["current_owner_header_excerpt"])
        self.assertNotIn("ARCHIVED PR593", current_v3["current_owner_header_excerpt"])
        self.assertFalse(current_v3["current_owner_header_truncated"])
        self.assertEqual(packet["owners"][0]["current_owner_header_excerpt"],
                         "CURRENT PROJECT RULE")

    def test_extreme_owner_header_exposes_truncation_instead_of_hiding_it(self):
        from tools.context_before_action import live_owner_readback
        def fetch(url):
            item, link = self.fake_fetch(url)
            if url.endswith("/issues/99"):
                item = dict(item, body="CURRENT " + "x"*9000)
            return item, link
        view = live_owner_readback("strategy_release", "V3", fetcher=fetch)["owners"][1]
        self.assertTrue(view["current_owner_header_truncated"])
        self.assertEqual(len(view["current_owner_header_excerpt"]), 8500)

    def test_general_and_hardware_do_not_import_v3_owner(self):
        from tools.context_before_action import live_owner_readback
        for domain in ("project_general", "infrastructure", "operations", "research",
                       "strategy_development"):
            with self.subTest(domain=domain):
                packet = live_owner_readback(domain, None, fetcher=self.fake_fetch)
                self.assertEqual([x["issue"] for x in packet["owners"]], [353])

    def test_stale_main_pin_fails_closed(self):
        from tools.context_before_action import live_owner_readback, ContextGateError
        with self.assertRaisesRegex(ContextGateError, "main moved"):
            live_owner_readback("strategy_release", "V3",
                                fetcher=self.fake_fetch, expected_main="b" * 40)

    def test_missing_owner_or_wrong_link_fails_closed(self):
        from tools.context_before_action import live_owner_readback, ContextGateError
        def missing(url):
            if url.endswith("/issues/99"):
                return {"number": 99, "state": "open"}, ""
            return self.fake_fetch(url)
        with self.assertRaisesRegex(ContextGateError, "owner unavailable"):
            live_owner_readback("strategy_release", "V3", fetcher=missing)
        def external_link(url):
            item, link = self.fake_fetch(url)
            if url.endswith("/issues/99/comments?per_page=10"):
                return item, '<https://example.com/unsafe>; rel="last"'
            return item, link
        with self.assertRaisesRegex(ContextGateError, "pagination link"):
            live_owner_readback("strategy_release", "V3", fetcher=external_link)

    def test_drift_during_owner_check_fails_closed(self):
        from tools.context_before_action import live_owner_readback, ContextGateError
        calls = [0]
        def moving(url):
            if url.endswith("/commits/main"):
                calls[0] += 1
                return {"sha": ("a" if calls[0] == 1 else "b") * 40}, ""
            return self.fake_fetch(url)
        with self.assertRaisesRegex(ContextGateError, "changed during"):
            live_owner_readback("strategy_release", "V3", fetcher=moving)

    def test_default_source_packet_remains_offline(self):
        from tools.context_before_action import build
        with patch("tools.context_before_action._github_api_read",
                   side_effect=AssertionError("offline packet made network request")):
            packet = build(ROOT, "architecture", work_domain="project_general")
        self.assertFalse(packet["has_network_access"])
        self.assertTrue(packet["current_reading_plan"]["historical_plans_not_open_tasks"])



class ExistingOwnerActionViewTests(unittest.TestCase):
    """The canonical owner view must prevent re-staging or skipping runtime gates."""

    def body(self):
        steps = [
            {"id": "PR607_CAS_SOURCE", "layer": "SOURCE", "state": "DONE",
             "evidence_class": "SOURCE_CI_ACK",
             "evidence_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6467674171"},
            {"id": "PR608_NOTEBOOK_STAGE", "layer": "PHYSICAL_STAGING", "state": "DONE",
             "evidence_class": "PHYSICAL_ACK",
             "evidence_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6468089267"},
            {"id": "ORIGINALHOST_NOREARM_CUTOVER", "layer": "REAL_RUNTIME", "state": "BLOCKED",
             "evidence_class": "OWNER_BLOCKER",
             "evidence_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6468388694"},
            {"id": "WRITER_REAL_COMMIT", "layer": "REAL_RUNTIME", "state": "BLOCKED",
             "evidence_class": "OWNER_BLOCKER",
             "evidence_url": "https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-6468388694"},
        ]
        obj = {"kind": "V3_EXISTING_RELEASE_OWNER_ACTION_VIEW_V1",
               "scope": "V3_PAPER", "owner_issue": 99,
               "as_of_utc": "2026-10-28T11:58:00Z",
               "last_owner_comment_id": 6468388694,
               "no_runtime_authority": True, "steps": steps}
        return obj

    def encode(self, obj):
        from tools.context_before_action import V3_GATE_START, V3_GATE_END
        obj = dict(obj)
        obj.setdefault("owner_header_sha256", hashlib.sha256(b"").hexdigest())
        return V3_GATE_START + "\n" + json.dumps(obj) + "\n" + V3_GATE_END

    def test_completed_source_and_staged_notebooks_block_rework(self):
        from tools.context_before_action import existing_owner_gate_decision
        body = self.encode(self.body())
        for candidate in ("PR607_CAS_SOURCE", "PR608_NOTEBOOK_STAGE"):
            with self.subTest(candidate=candidate):
                checked = existing_owner_gate_decision(body, candidate)
                self.assertEqual(checked["candidate_verdict"],
                                 "REWORK_BLOCKED_ALREADY_EVIDENCED_DONE")
                self.assertEqual(checked["rework_detected_this_query"], 1)
                self.assertFalse(checked["ready_to_execute"])
                self.assertEqual(checked["counts_from_declared_owner_view"]["REAL_RUNTIME"]["done"], 0)

    def test_next_runtime_gate_is_blocked_not_auto_executable(self):
        from tools.context_before_action import existing_owner_gate_decision
        answer = existing_owner_gate_decision(self.encode(self.body()), "ORIGINALHOST_NOREARM_CUTOVER")
        self.assertEqual(answer["next_open_gate"]["id"], "ORIGINALHOST_NOREARM_CUTOVER")
        self.assertEqual(answer["candidate_verdict"],
                         "NEXT_GATE_BLOCKED_PENDING_REAL_ACK_AND_APPROVAL")
        self.assertFalse(answer["runtime_verified_independently"])
        self.assertFalse(answer["ready_to_execute"])
        self.assertEqual(answer["past_duplicate_work_count"], "UNKNOWN_NOT_COLLECTED")

    def test_out_of_order_or_unregistered_work_is_not_next_action(self):
        from tools.context_before_action import existing_owner_gate_decision
        body = self.encode(self.body())
        self.assertEqual(existing_owner_gate_decision(
            body, "WRITER_REAL_COMMIT")["candidate_verdict"], "NOT_NEXT_OPEN_GATE_HOLD")
        self.assertEqual(existing_owner_gate_decision(
            body, "NEW_UNPROVEN_READER")["candidate_verdict"],
            "UNREGISTERED_WORK_HOLD_NEEDS_ORIGINAL_DEFECT_EVIDENCE")

    def test_runtime_done_cannot_be_claimed_from_source_ci(self):
        from tools.context_before_action import existing_owner_gate_decision, ContextGateError
        obj = self.body()
        obj["steps"][2]["state"] = "DONE"
        obj["steps"][2]["evidence_class"] = "SOURCE_CI_ACK"
        with self.assertRaisesRegex(ContextGateError, "original evidence class"):
            existing_owner_gate_decision(self.encode(obj))

    def test_no_marker_and_duplicate_ids_fail_closed(self):
        from tools.context_before_action import existing_owner_gate_decision, ContextGateError
        self.assertEqual(existing_owner_gate_decision(
            "old archived V3 summary", "PR608_NOTEBOOK_STAGE")["candidate_verdict"],
            "NO_ACTION_ALLOWED")
        obj = self.body()
        obj["steps"][1]["id"] = obj["steps"][0]["id"]
        with self.assertRaisesRegex(ContextGateError, "duplicate"):
            existing_owner_gate_decision(self.encode(obj))
        obj = self.body()
        obj["steps"][0]["state"] = "BLOCKED"
        obj["steps"][0]["evidence_class"] = "OWNER_BLOCKER"
        with self.assertRaisesRegex(ContextGateError, "out of order"):
            existing_owner_gate_decision(self.encode(obj))

    def test_owner_edited_during_live_readback_blocks_candidate(self):
        from tools.context_before_action import live_owner_readback, ContextGateError
        base = LiveOwnerReadbackTests()
        calls = [0]
        def fetch(url):
            item, link = base.fake_fetch(url)
            if url.endswith("/issues/99"):
                calls[0] += 1
                if calls[0] == 2:
                    item = dict(item, body=item["body"] + "\nnew evidence")
            return item, link
        with self.assertRaisesRegex(ContextGateError, "changed during"):
            live_owner_readback("strategy_release", "V3", fetcher=fetch)

    def test_freshness_fence_rejects_new_owner_comment(self):
        from tools.context_before_action import live_owner_readback
        base = LiveOwnerReadbackTests()
        owner_body = self.encode(self.body())
        def changed_comment(url):
            item, link = base.fake_fetch(url)
            if url.endswith("/issues/99"):
                item = dict(item, body=owner_body)
            if url.endswith("/issues/99/comments?per_page=10&page=8"):
                item = [dict(x, id=6468388695) for x in item]
            return item, link
        gate = live_owner_readback(
            "strategy_release", "V3", fetcher=changed_comment,
            candidate_id="PR608_NOTEBOOK_STAGE")["named_release_gate"]
        self.assertEqual(
            gate["status"],
            "OWNER_ACTION_VIEW_STALE_HOLD_NEEDS_LATEST_ACK_RECONCILIATION")
        self.assertEqual(gate["candidate_verdict"],
                         "STALE_OWNER_VIEW_HOLD_NO_REWORK")
        self.assertIsNone(gate["next_open_gate"])
        self.assertFalse(gate["ready_to_execute"])

    def test_new_issue_header_without_new_comment_invalidates_old_gate(self):
        from tools.context_before_action import live_owner_readback
        base = LiveOwnerReadbackTests()
        # The Issue 99 comment stays identical while a newer PR is inserted
        # in the owner DESCRIPTION, as actually happened with PR613.
        body = "PR613 new signed reader requires physical ACK\n" + self.encode(self.body())
        def changed_header(url):
            item, link = base.fake_fetch(url)
            if url.endswith("/issues/99"):
                item = dict(item, body=body)
            if url.endswith("/issues/99/comments?per_page=10&page=8"):
                item = [dict(x, id=6468388694) for x in item]
            return item, link
        gate = live_owner_readback(
            "strategy_release", "V3", fetcher=changed_header,
            candidate_id="ORIGINALHOST_NOREARM_CUTOVER")["named_release_gate"]
        self.assertEqual(
            gate["status"],
            "OWNER_ACTION_VIEW_STALE_HOLD_NEEDS_LATEST_ACK_RECONCILIATION")
        self.assertEqual(
            gate["staleness_reason"],
            "OWNER_HEADER_CHANGED_WITHOUT_VIEW_RECONCILIATION")
        self.assertIsNone(gate["next_open_gate"])
        self.assertEqual(gate["candidate_verdict"], "STALE_OWNER_VIEW_HOLD_NO_REWORK")
        self.assertFalse(gate["ready_to_execute"])

    def test_all_runtime_proofs_done_does_not_auto_release(self):
        from tools.context_before_action import existing_owner_gate_decision
        # Synthetic future owner receipts: structurally complete, never an
        # independent physical proof or a trading/release permission.
        obj = self.body()
        for step in obj["steps"]:
            if step["layer"] == "REAL_RUNTIME":
                step["state"] = "DONE"
                step["evidence_class"] = "ORIGINAL_RUNTIME_ACK"
        result = existing_owner_gate_decision(self.encode(obj))
        self.assertIsNone(result["next_open_gate"])
        self.assertFalse(result["ready_to_execute"])
        self.assertFalse(result["runtime_verified_independently"])
        self.assertEqual(result["counts_from_declared_owner_view"]["REAL_RUNTIME"]["open"], 0)
        self.assertEqual(result["counts_from_declared_owner_view"]["REAL_RUNTIME"]["done"], 2)

    def test_invalid_or_missing_header_digest_fails_closed(self):
        from tools.context_before_action import existing_owner_gate_decision, ContextGateError
        obj = self.body()
        obj["owner_header_sha256"] = "not-a-sha"
        with self.assertRaisesRegex(ContextGateError, "invalid release owner view"):
            existing_owner_gate_decision(self.encode(obj))
        obj = self.body()
        obj["owner_header_sha256"] = None
        with self.assertRaisesRegex(ContextGateError, "invalid release owner view"):
            existing_owner_gate_decision(self.encode(obj))

    def test_current_owner_comment_allows_classification_not_execution(self):
        from tools.context_before_action import live_owner_readback
        base = LiveOwnerReadbackTests()
        owner_body = self.encode(self.body())
        def current_comment(url):
            item, link = base.fake_fetch(url)
            if url.endswith("/issues/99"):
                item = dict(item, body=owner_body)
            if url.endswith("/issues/99/comments?per_page=10&page=8"):
                item = [dict(x, id=6468388694) for x in item]
            return item, link
        gate = live_owner_readback(
            "strategy_release", "V3", fetcher=current_comment,
            candidate_id="PR608_NOTEBOOK_STAGE")["named_release_gate"]
        self.assertEqual(gate["candidate_verdict"],
                         "REWORK_BLOCKED_ALREADY_EVIDENCED_DONE")
        self.assertFalse(gate["ready_to_execute"])

    def test_cannot_select_named_v3_gate_for_hardware(self):
        from tools.context_before_action import live_owner_readback, ContextGateError
        with self.assertRaisesRegex(ContextGateError, "only valid"):
            live_owner_readback("infrastructure", None, fetcher=lambda x: (None, ""),
                                candidate_id="PR608_NOTEBOOK_STAGE")


if __name__ == "__main__":
    unittest.main()
