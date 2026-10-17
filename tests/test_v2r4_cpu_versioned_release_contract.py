"""Synthetic, deliberately adversarial CPU-only release safety tests.

No service actions, no Cloud changes, no original Mini-PC dependency.
"""
import copy
import unittest

from tools.v2r4_cpu_versioned_release_contract import (
    BACKUP_ID, OLD_BUNDLE, OLD_RELEASE, OLD_SERIES, OLD_STRATEGY,
    PHASES, PR360_SOURCE, assess_manifest, assess_trace,
)


def manifest():
    return {
        "predecessor_series_id": OLD_SERIES,
        "predecessor_release_sha": OLD_RELEASE,
        "predecessor_bundle_sha256": OLD_BUNDLE,
        "strategy_sha256": OLD_STRATEGY,
        "source_pr360_sha": PR360_SOURCE,
        "original_backup_id": BACKUP_ID,
        "successor_series_id": "PAPER-V2R4-20261017T120000Z",
        "successor_release_sha": "a" * 40,
        "successor_bundle_sha256": "b" * 64,
        "successor_strategy_sha256": OLD_STRATEGY,
        "source_gate_physical_pass": True,
        "backup_gate_physical_pass": True,
        "original_pr326_hashes_pinned": True,
        "staged_pr360_hashes_pinned": True,
        "original_series_active_only": True,
        "paper_only": True,
        "real_money_actions_enabled": False,
        "scout_notional_eur": 50,
        "stage2_notional_eur": 50,
        "series_rotation_endpoint": "new-cpu-versioned-review-pending",
        "new_endpoint_fenced_inactive": True,
        "old_followups_preserved": True,
        "v2r4_to_v2r4_aftercare_contract_reviewed": True,
        "new_series_routing_and_milestones_reviewed": True,
    }


def events():
    return [
        {
            "phase": PHASES[0],
            "supervisor_task_disabled": True,
            "supervisor_process_fully_exited": True,
            "no_other_rearm_owner": True,
            "native_state_confirmed": True,
        },
        {
            "phase": PHASES[1],
            "candidate_disabled": True,
            "wait_disabled": True,
            "lifecycle_disabled": True,
            "cloudsync_quiesced_or_fenced": True,
            "no_python_descendants": True,
            "no_out_of_band_workers": True,
            "task_native_states_confirmed": True,
            "matching_process_count": 0,
        },
        {
            "phase": PHASES[2],
            "final_cloud_ack": True,
            "candidate_id_digest_matches": True,
            "paper_open_positions_reconciled": True,
            "ttl_and_recheck_reconciled": True,
            "old_followup_owner_handoff_ready": True,
            "writer_quiescence_still_held": True,
        },
        {
            "phase": PHASES[3],
            "independent_new_cas_approved": True,
            "new_transaction_pin_verified": True,
            "old_closed_technically": True,
            "exactly_one_new_active_series": True,
            "old_followups_mutable_with_old_id": True,
            "v2r4_successor_aftercare_relay_ack": True,
            "old_intake_fenced": True,
            "new_runtime_bundle_fingerprint_verified": True,
            "cas_endpoint": "VERSIONED_CPU_ONLY_NEW_REVIEWED",
        },
        {
            "phase": PHASES[4],
            "new_candidate_single_writer": True,
            "new_wait_single_writer": True,
            "new_lifecycle_single_writer": True,
            "original_followup_owner_retained": True,
            "old_followup_recheck_receipts_route_to_old_series": True,
            "no_old_candidate_intake": True,
            "no_real_money_actions": True,
            "task_args_pinned_new_bundle": True,
            "supervisor_owner_fence_verified": True,
        },
        {
            "phase": PHASES[5],
            "two_distinct_fresh_host_cloud_acks": True,
            "heartbeat_timestamps_advanced": True,
            "new_paper_decision_e2e": True,
            "old_pending_followups_progress": True,
            "post_restart_no_duplicate_workers": True,
            "cpu_workload_comparable": True,
            "supervisor_healthy_rearmed": True,
            "independent_owner_verified": True,
        },
    ]


class VersionedCpuReleaseContractTests(unittest.TestCase):
    def assert_blocked(self, result, reason=None):
        self.assertEqual(result["status"], "OFFLINE_CONTRACT_BLOCKED")
        self.assertFalse(result["production_release_authorized"])
        self.assertFalse(result["mutations_performed"])
        self.assertFalse(result["automatic_rollback_allowed"])
        if reason:
            self.assertEqual(result["reason"], reason)

    def test_exact_versioned_paper_manifest_offline_only(self):
        x = assess_manifest(manifest())
        self.assertEqual(x["status"], "OFFLINE_MANIFEST_CONTRACT_PASS_RUNTIME_BLOCKED")
        self.assertTrue(x["simulation_only"])
        self.assertFalse(x["production_release_authorized"])

    def test_bad_original_or_backup_pins_fail_closed(self):
        for key in (
            "predecessor_series_id", "predecessor_release_sha",
            "predecessor_bundle_sha256", "strategy_sha256",
            "source_pr360_sha", "original_backup_id",
        ):
            with self.subTest(key=key):
                p = manifest()
                p[key] = "bad"
                self.assert_blocked(assess_manifest(p))

    def test_no_same_series_or_same_bundle_provenance(self):
        for key, value in (
            ("successor_series_id", OLD_SERIES),
            ("successor_bundle_sha256", OLD_BUNDLE),
            ("successor_release_sha", OLD_RELEASE),
            ("successor_strategy_sha256", "f" * 64),
        ):
            with self.subTest(key=key):
                p = manifest()
                p[key] = value
                self.assert_blocked(assess_manifest(p))

    def test_no_live_real_money_or_incorrect_paper_sizing(self):
        for key, value in (
            ("paper_only", False),
            ("real_money_actions_enabled", True),
            ("real_money_actions_enabled", None),
            ("stage2_notional_eur", 75),
            ("scout_notional_eur", True),
            ("old_followups_preserved", False),
            ("backup_gate_physical_pass", False),
        ):
            with self.subTest(key=key, value=value):
                p = manifest()
                p[key] = value
                self.assert_blocked(assess_manifest(p))

    def test_aftercare_must_be_specific_to_v2r4_successor(self):
        for key, reason in (
            ("v2r4_to_v2r4_aftercare_contract_reviewed",
             "V2R4_SUCCESSOR_OLD_AFTERCARE_NOT_PROVEN"),
            ("new_series_routing_and_milestones_reviewed",
             "SUCCESSOR_METRICS_ROUTING_NOT_PROVEN"),
        ):
            with self.subTest(key=key):
                p = manifest()
                p[key] = False
                self.assert_blocked(assess_manifest(p), reason)

    def test_aftercare_relay_and_old_receipt_ownership_post_cas(self):
        t = events()
        t[3]["v2r4_successor_aftercare_relay_ack"] = False
        self.assert_blocked(assess_trace(t), "PHASE_EVIDENCE_INCOMPLETE")
        t = events()
        t[4]["old_followup_recheck_receipts_route_to_old_series"] = False
        self.assert_blocked(assess_trace(t), "PHASE_EVIDENCE_INCOMPLETE")

    def test_no_reuse_of_oct07_or_v3_transaction(self):
        for endpoint in ("v2r4-technical-cutover", "v3-experimental-paper-cutover"):
            p = manifest()
            p["series_rotation_endpoint"] = endpoint
            self.assert_blocked(
                assess_manifest(p), "LEGACY_OR_V3_CAS_REUSE_FORBIDDEN"
            )
        p = manifest()
        p["new_endpoint_fenced_inactive"] = False
        self.assert_blocked(assess_manifest(p))

    def test_complete_synthetic_success_never_grants_live_rights(self):
        x = assess_trace(events())
        self.assertEqual(x["status"], "SYNTHETIC_SEQUENCE_PASS_NOT_PHYSICAL_RELEASE_ACK")
        self.assertFalse(x["production_release_authorized"])
        self.assertFalse(x["mutations_performed"])
        self.assertFalse(x["automatic_rollback_allowed"])

    def test_each_phase_must_be_complete(self):
        base = events()
        for index, phase in enumerate(base):
            for key, value in phase.items():
                if key == "phase":
                    continue
                with self.subTest(index=index, key=key):
                    x = copy.deepcopy(base)
                    x[index][key] = False if value is True else 1
                    self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")

    def test_stopped_task_but_orphan_worker_is_not_quiesced(self):
        x = events()
        x[1]["matching_process_count"] = 1
        self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")
        x[1]["matching_process_count"] = 0
        x[1]["no_out_of_band_workers"] = False
        self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")

    def test_delayed_ack_and_stale_supervisor_never_pass(self):
        x = events()
        x[-1]["two_distinct_fresh_host_cloud_acks"] = False
        self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")
        x = events()
        x[0]["supervisor_process_fully_exited"] = False
        self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")

    def test_duplicate_phase_or_out_of_order_rejected(self):
        x = events()
        x.insert(1, copy.deepcopy(x[0]))
        self.assert_blocked(assess_trace(x), "PHASE_ORDER_OR_DUPLICATE")
        self.assert_blocked(assess_trace(events()[1:]), "PHASE_ORDER_OR_DUPLICATE")
        self.assert_blocked(assess_trace(events()[:3]), "TRACE_INCOMPLETE")

    def test_pre_cas_failure_does_not_auto_restart(self):
        x = assess_trace(events()[:2] + [{"phase": "FAILURE"}])
        self.assert_blocked(x, "PRECAS_HOLD_OR_VERIFIED_RESTORE_ONLY")

    def test_pre_cas_rollback_requires_heartbeats_and_all_owners(self):
        ack = {
            "phase": "ROLLBACK_PRECAS",
            "backup_sha_rechecked": True,
            "original_workers_single_owner": True,
            "original_series_still_active_only": True,
            "original_heartbeats_advanced_twice": True,
            "old_followup_owner_healthy": True,
            "supervisor_rearmed_after_workers": True,
            "temporary_fences_removed": True,
        }
        for key in list(ack)[1:]:
            with self.subTest(key=key):
                failed = dict(ack)
                failed[key] = False
                self.assert_blocked(
                    assess_trace(events()[:2] + [failed]),
                    "PRECAS_ROLLBACK_UNVERIFIED_HOLD",
                )
        result = assess_trace(events()[:2] + [ack])
        self.assertEqual(result["status"], "SYNTHETIC_PRECAS_ROLLBACK_PASS_RUNTIME_BLOCKED")

    def test_after_cas_failure_requires_manual_reconciliation(self):
        self.assert_blocked(
            assess_trace(events()[:4] + [{"phase": "FAILURE"}]),
            "POST_CAS_HOLD_FOR_MANUAL_RECONCILIATION",
        )
        self.assert_blocked(
            assess_trace(events()[:4] + [{"phase": "ROLLBACK_PRECAS"}]),
            "BLIND_ROLLBACK_AFTER_CAS_FORBIDDEN",
        )

    def test_no_old_oct07_cas_ack_in_synthetic_trace(self):
        x = events()
        x[3]["cas_endpoint"] = "v2r4-technical-cutover"
        self.assert_blocked(assess_trace(x), "PHASE_EVIDENCE_INCOMPLETE")

    def test_no_implicit_release_from_empty_or_malformed_trace(self):
        self.assert_blocked(assess_trace([]), "EMPTY_OR_INVALID_TRACE")
        self.assert_blocked(assess_trace([None]), "EVENT_NOT_OBJECT")


if __name__ == "__main__":
    unittest.main()
