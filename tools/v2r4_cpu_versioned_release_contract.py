"""Issue #353: offline-only decision model for a separately VERSIONED V2R4 CPU release.

Pure functions over synthetic/evidence-shaped dictionaries.  NEVER reads host tasks,
contacts Supabase, changes an active series, copies source, or performs a restart.
A successful simulated trace is NOT a physical cutover acknowledgement.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

KIND = "ISSUE353_CPU_VERSIONED_RELEASE_OFFLINE_CONTRACT_V1"
OLD_SERIES = "PAPER-V2R4-20261009T110135Z"
OLD_RELEASE = "d8b35a8ec2e6f392f219b1c36cad95f3ad629b64"
OLD_BUNDLE = "604d5d460f17c4548b2d69db8ceb2f5368e702a6d51860ce8916e2e7fbba5b30"
OLD_STRATEGY = "55c15f6c0735e524409594ece173ab30e4d84eecafefa18b57f8dc9c48cca32c"
BACKUP_ID = "ISSUE353-CPU-VORHER-20261017-091646-93265fff"
PR360_SOURCE = "c8f37da865314ac91d36c786b66d107aad4a28d1"
HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
NEW_SERIES = re.compile(r"^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$")

# These are offline DESIGN requirements. An existing Oct07 rotation RPC is NOT
# suitable for the 09Oct predecessor and may not be used to commit a successor.
PHASES = (
    "SUPERVISOR_HELD",
    "OLD_WORKERS_QUIESCED",
    "OLD_EVIDENCE_CHECKPOINTED",
    "VERSIONED_CLOUD_CAS_ACK",
    "SUCCESSOR_STARTED",
    "POSTSTART_ACK",
)

def _is_true(data: Mapping[str, Any], key: str) -> bool:
    return data.get(key) is True


def _is_false(data: Mapping[str, Any], key: str) -> bool:
    return data.get(key) is False


def _text(data: Mapping[str, Any], key: str) -> str:
    v = data.get(key)
    return v if isinstance(v, str) else ""


def _same_hash(value: str, expected: str) -> bool:
    return value == expected and HEX64.fullmatch(value) is not None


def _error(code: str, phase: str) -> dict[str, Any]:
    return {
        "kind": KIND,
        "status": "OFFLINE_CONTRACT_BLOCKED",
        "blocked_phase": phase,
        "reason": code,
        "simulation_only": True,
        "production_release_authorized": False,
        "mutations_performed": False,
        "automatic_rollback_allowed": False,
    }


def assess_manifest(p: Mapping[str, Any]) -> dict[str, Any]:
    """Reject attempts to re-label the Oct09 runtime bytes as a new release."""
    if not isinstance(p, Mapping):
        return _error("MANIFEST_NOT_OBJECT", "MANIFEST")
    expected = {
        "predecessor_series_id": OLD_SERIES,
        "predecessor_release_sha": OLD_RELEASE,
        "predecessor_bundle_sha256": OLD_BUNDLE,
        "strategy_sha256": OLD_STRATEGY,
        "source_pr360_sha": PR360_SOURCE,
        "original_backup_id": BACKUP_ID,
    }
    for name, value in expected.items():
        if _text(p, name) != value:
            return _error("PIN_MISMATCH_" + name.upper(), "MANIFEST")
    new_id = _text(p, "successor_series_id")
    new_release = _text(p, "successor_release_sha")
    new_bundle = _text(p, "successor_bundle_sha256")
    if not NEW_SERIES.fullmatch(new_id) or new_id <= OLD_SERIES:
        return _error("SUCCESSOR_ID_INVALID_OR_NOT_NEW", "MANIFEST")
    if not HEX40.fullmatch(new_release) or new_release == OLD_RELEASE:
        return _error("SUCCESSOR_RELEASE_ID_INVALID_OR_REUSED", "MANIFEST")
    if not HEX64.fullmatch(new_bundle) or new_bundle == OLD_BUNDLE:
        return _error("SUCCESSOR_BUNDLE_ID_INVALID_OR_REUSED", "MANIFEST")
    if not _same_hash(_text(p, "successor_strategy_sha256"), OLD_STRATEGY):
        return _error("STRATEGY_NOT_IDENTICAL", "MANIFEST")
    if any(not _is_true(p, key) for key in (
        "source_gate_physical_pass", "backup_gate_physical_pass",
        "original_pr326_hashes_pinned", "staged_pr360_hashes_pinned",
        "original_series_active_only", "paper_only",
    )):
        return _error("REQUIRED_ORIGINALHOST_EVIDENCE_MISSING", "MANIFEST")
    if not _is_false(p, "real_money_actions_enabled"):
        return _error("REAL_MONEY_NOT_EXPLICITLY_DISABLED", "MANIFEST")
    if (
        type(p.get("scout_notional_eur")) is not int
        or type(p.get("stage2_notional_eur")) is not int
        or p["scout_notional_eur"] != 50
        or p["stage2_notional_eur"] != 50
    ):
        return _error("PAPER_SIZING_MISMATCH", "MANIFEST")
    if _text(p, "series_rotation_endpoint") in (
        "v2r4-technical-cutover", "v3-experimental-paper-cutover",
    ):
        return _error("LEGACY_OR_V3_CAS_REUSE_FORBIDDEN", "MANIFEST")
    if not _is_true(p, "new_endpoint_fenced_inactive"):
        return _error("NEW_VERSIONED_CAS_NOT_PROVEN_INACTIVE", "MANIFEST")
    if not _is_true(p, "old_followups_preserved"):
        return _error("UNRESOLVED_OLD_FOLLOWUP_OWNER", "MANIFEST")
    # Existing closed-original aftercare in the V2R4 relay is V3-specific;
    # it cannot automatically be reused for V2R4 -> V2R4.
    if not _is_true(p, "v2r4_to_v2r4_aftercare_contract_reviewed"):
        return _error("V2R4_SUCCESSOR_OLD_AFTERCARE_NOT_PROVEN", "MANIFEST")
    if not _is_true(p, "new_series_routing_and_milestones_reviewed"):
        return _error("SUCCESSOR_METRICS_ROUTING_NOT_PROVEN", "MANIFEST")
    return {
        "kind": KIND,
        "status": "OFFLINE_MANIFEST_CONTRACT_PASS_RUNTIME_BLOCKED",
        "next_gate": "INDEPENDENT_ORIGINALHOST_QUIESCENCE_AND_TRANSACTION_REVIEW",
        "simulation_only": True,
        "production_release_authorized": False,
        "mutations_performed": False,
    }


def assess_trace(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Model fail-closed task/recovery boundaries; never execute these steps.

    Every event is synthetic unless separately authenticated by an independent
    operator. No trace outcome here can authorize a physical Mini-PC or Cloud
    mutation.
    """
    if not isinstance(events, (list, tuple)) or not events:
        return _error("EMPTY_OR_INVALID_TRACE", "TRACE")
    phase = 0
    cas_done = False
    for e in events:
        if not isinstance(e, Mapping):
            return _error("EVENT_NOT_OBJECT", "TRACE")
        name = _text(e, "phase")
        if name == "ROLLBACK_PRECAS":
            if cas_done:
                return _error("BLIND_ROLLBACK_AFTER_CAS_FORBIDDEN", name)
            needed = (
                "backup_sha_rechecked", "original_workers_single_owner",
                "original_series_still_active_only", "original_heartbeats_advanced_twice",
                "old_followup_owner_healthy", "supervisor_rearmed_after_workers",
                "temporary_fences_removed",
            )
            if any(not _is_true(e, key) for key in needed):
                return _error("PRECAS_ROLLBACK_UNVERIFIED_HOLD", name)
            return {
                "kind": KIND,
                "status": "SYNTHETIC_PRECAS_ROLLBACK_PASS_RUNTIME_BLOCKED",
                "simulation_only": True, "production_release_authorized": False,
                "mutations_performed": False, "automatic_rollback_allowed": False,
            }
        if name == "FAILURE":
            return _error("POST_CAS_HOLD_FOR_MANUAL_RECONCILIATION" if cas_done else "PRECAS_HOLD_OR_VERIFIED_RESTORE_ONLY", name)
        if phase >= len(PHASES) or name != PHASES[phase]:
            return _error("PHASE_ORDER_OR_DUPLICATE", name or "TRACE")
        if name == "SUPERVISOR_HELD":
            valid = all(_is_true(e, key) for key in (
                "supervisor_task_disabled", "supervisor_process_fully_exited",
                "no_other_rearm_owner", "native_state_confirmed",
            ))
        elif name == "OLD_WORKERS_QUIESCED":
            valid = all(_is_true(e, key) for key in (
                "candidate_disabled", "wait_disabled", "lifecycle_disabled",
                "cloudsync_quiesced_or_fenced", "no_python_descendants",
                "no_out_of_band_workers", "task_native_states_confirmed",
            )) and type(e.get("matching_process_count")) is int and e["matching_process_count"] == 0
        elif name == "OLD_EVIDENCE_CHECKPOINTED":
            valid = all(_is_true(e, key) for key in (
                "final_cloud_ack", "candidate_id_digest_matches",
                "paper_open_positions_reconciled", "ttl_and_recheck_reconciled",
                "old_followup_owner_handoff_ready", "writer_quiescence_still_held",
            ))
        elif name == "VERSIONED_CLOUD_CAS_ACK":
            # The old Oct07 RPC has fixed predecessor identity and must never
            # produce this ACK. A reviewed NEW transaction is obligatory.
            valid = all(_is_true(e, key) for key in (
                "independent_new_cas_approved", "new_transaction_pin_verified",
                "old_closed_technically", "exactly_one_new_active_series",
                "old_followups_mutable_with_old_id",
                "v2r4_successor_aftercare_relay_ack",
                "old_intake_fenced", "new_runtime_bundle_fingerprint_verified",
            )) and _text(e, "cas_endpoint") == "VERSIONED_CPU_ONLY_NEW_REVIEWED"
        elif name == "SUCCESSOR_STARTED":
            valid = all(_is_true(e, key) for key in (
                "new_candidate_single_writer", "new_wait_single_writer",
                "new_lifecycle_single_writer", "original_followup_owner_retained",
                "old_followup_recheck_receipts_route_to_old_series",
                "no_old_candidate_intake", "no_real_money_actions",
                "task_args_pinned_new_bundle", "supervisor_owner_fence_verified",
            ))
        else:  # POSTSTART_ACK
            valid = all(_is_true(e, key) for key in (
                "two_distinct_fresh_host_cloud_acks", "heartbeat_timestamps_advanced",
                "new_paper_decision_e2e", "old_pending_followups_progress",
                "post_restart_no_duplicate_workers",
                "cpu_workload_comparable", "supervisor_healthy_rearmed",
                "independent_owner_verified",
            ))
        if not valid:
            return _error("PHASE_EVIDENCE_INCOMPLETE", name)
        if name == "VERSIONED_CLOUD_CAS_ACK":
            cas_done = True
        phase += 1
    if phase != len(PHASES):
        return _error("TRACE_INCOMPLETE", PHASES[phase])
    return {
        "kind": KIND,
        "status": "SYNTHETIC_SEQUENCE_PASS_NOT_PHYSICAL_RELEASE_ACK",
        "simulation_only": True,
        "production_release_authorized": False,
        "mutations_performed": False,
        "automatic_rollback_allowed": False,
        "next_gate": "LIVE_HOST_AND_CLOUD_INDEPENDENT_EVIDENCE_AND_MANUAL_GO_NO_GO",
    }
