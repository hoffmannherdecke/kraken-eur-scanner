"""Static mutual contract gate for the inactive technical PAPER release.
No credentials, network, task access, migrations, or runtime side effects.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class TechnicalCutoverMutualContract(unittest.TestCase):
    def test_edge_physical_proofs_are_all_supplied_by_operator(self):
        edge = source("supabase/functions/v2r4-technical-cutover/index.ts")
        operator = source("tools/minipc-v2r4-technical-cutover-operator.ps1")
        required = set(re.findall(r"proof\?\.([a-z][a-z0-9_]+)", edge))
        self.assertGreaterEqual(len(required), 8)
        self.assertIn("old_candidate_ids_sha256", required)
        self.assertIn("staged_manifest_sha256", required)
        for key in sorted(required):
            self.assertRegex(operator, re.escape(key) + r"\s*=",
                             msg=f"missing physical proof field: {key}")

    def test_frozen_inert_stage_has_complete_file_bytes_inventory(self):
        staging = source("tools/minipc-v2r4-technical-rollover-stage.ps1")
        readiness = source("tools/minipc-v2r4-technical-cutover-readiness.ps1")
        self.assertIn("prepared_file_hashes", staging)
        self.assertIn("prepared_file_hashes", readiness)
        self.assertIn("all_staged_files_immutable", readiness)
        self.assertIn("staged_code_hash_matches_manifest", readiness)
        self.assertIn("paper_runtime_control.json", staging)

    def test_one_active_and_fail_closed_after_commit(self):
        operator = source("tools/minipc-v2r4-technical-cutover-operator.ps1")
        sql = source("supabase/v2r4-technical-paper-rotation-20261009.sql")
        self.assertIn("MAINTENANCE_LEASE_EXPIRED_BEFORE_RPC", operator)
        self.assertIn("POST_COMMIT_FAIL_CLOSED_SUCCESSOR_STOPPED", operator)
        self.assertIn("CLOUD_OUTCOME_UNKNOWN", operator)
        self.assertIn("technical_closed", sql)
        self.assertIn("paper_series_single_active_idx", sql)
        self.assertIn("predecessor_outcomes", sql)

    def test_failed_precommit_restores_only_originally_running_tasks(self):
        operator = source("tools/minipc-v2r4-technical-cutover-operator.ps1")
        self.assertIn("original-task-states.json", operator)
        self.assertIn("if($saved.enabled -eq $true -and $saved.running -eq $true)", operator)
        self.assertIn("POST_COMMIT_FAIL_CLOSED_SUCCESSOR_STOPPED", operator)
        self.assertIn("CLOUD_OUTCOME_UNKNOWN", operator)
        self.assertIn("$matches.Count -eq 1 -and $closed.Count -eq 1", operator)
        self.assertIn("Need-No-Old-Writers", operator)
        self.assertIn("Win32_Process", operator)
        self.assertIn("PRE_COMMIT_TASKS_UNTOUCHED", operator)
        self.assertIn("$taskStopStarted=$true", operator)

    def test_successor_health_verifies_identity_and_task_actions(self):
        operator = source("tools/minipc-v2r4-technical-cutover-operator.ps1")
        self.assertIn("$hb.series_id -cne $newId", operator)
        self.assertIn("Task action not pinned to successor app", operator)
        self.assertIn("Successor scheduled task exited", operator)
        self.assertIn("$hb.real_money_actions -ne $false", operator)

    def test_h3_001_baseline_cannot_be_rebound(self):
        operator = source("tools/minipc-v2r4-technical-cutover-operator.ps1")
        sql = source("supabase/v2r4-technical-paper-rotation-20261009.sql")
        self.assertIn("V3-H3-SHADOW-001", sql)
        self.assertIn("FROZEN_TECHNICAL_CUTOVER", sql)
        self.assertIn("guard_frozen_h3_001_status", sql)
        self.assertIn("v3_h3_001_frozen_status_guard", sql)
        self.assertIn("guard_h3_001_evidence_after_close", sql)
        self.assertIn("v3_h3_001_evidence_after_close_guard", sql)
        self.assertIn("h3_001_retired", operator)


if __name__ == "__main__":
    unittest.main()
