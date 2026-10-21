#!/usr/bin/env python3
"""Bounded read-only identity check before scheduled PAPER completion notices.

No Supabase/Slack/HTTP imports or side effects. A name change in GitHub is not
a release; require exactly one cloud-active series with a matching readiness
view before a notification can be sent. Never prefer the first stale row.
"""
from __future__ import annotations


class PaperSeriesRoutingError(ValueError):
    pass


def select_current_readiness(active_rows: list, readiness_rows: list) -> dict:
    if not isinstance(active_rows, list) or len(active_rows) != 1:
        raise PaperSeriesRoutingError("PAPER_SERIES_ACTIVE_CARDINALITY_NOT_ONE")
    active = active_rows[0]
    if not isinstance(active, dict) or active.get("status") != "active":
        raise PaperSeriesRoutingError("PAPER_SERIES_WRONG_ACTIVE_STATUS")
    sid, revision = active.get("series_id"), active.get("strategy_revision")
    if not isinstance(sid, str) or not sid or not isinstance(revision, str):
        raise PaperSeriesRoutingError("PAPER_SERIES_MISSING_IDENTITY")
    if not (revision.startswith("V2R4-") or revision.startswith("V3-")):
        raise PaperSeriesRoutingError("PAPER_SERIES_UNAPPROVED_STRATEGY_REVISION")
    if not isinstance(readiness_rows, list):
        raise PaperSeriesRoutingError("PAPER_READINESS_NOT_A_LIST")
    match = [r for r in readiness_rows
             if isinstance(r, dict) and r.get("series_id") == sid]
    if len(match) != 1:
        raise PaperSeriesRoutingError("PAPER_READINESS_MISSING_OR_DUPLICATE_FOR_ACTIVE")
    row = match[0]
    if row.get("strategy_revision") != revision:
        raise PaperSeriesRoutingError("PAPER_READINESS_WRONG_ACTIVE_REVISION")
    if row.get("candidate_outcomes") is None:
        raise PaperSeriesRoutingError("PAPER_READINESS_MISSING_CANDIDATE_OUTCOMES")
    return row


def paper_completion_message_label(row: dict) -> str:
    revision = row.get("strategy_revision", "")
    if not (revision.startswith("V2R4-") or revision.startswith("V3-")):
        raise PaperSeriesRoutingError("PAPER_NOTICE_UNAPPROVED_REVISION")
    if not isinstance(row.get("series_id"), str) or not row["series_id"]:
        raise PaperSeriesRoutingError("PAPER_NOTICE_MISSING_SERIES")
    return "V3-Paper" if revision.startswith("V3-") else "V2R4-Paper"




def assess_v3_precas_original_pair(*, host: dict, cloud: dict,
                                   now_utc: "datetime") -> dict:
    """Pure correlation within EXISTING V3 proof #4, never CAS authority.

    A pair of plausible user-supplied dictionaries can still be forged.
    The independent physical release owner and separately credentialed Cloud
    CAS executor MUST re-read/verify their own originals, actual key roles,
    six E2E envelopes and live DB versions. Nothing here can issue permission.
    """
    from datetime import datetime, timezone
    import re

    result = {
        "kind": "V3_PRECAS_ORIGINAL_PAIR_REVIEW_V1",
        "disposition": "BLOCK_UNCORRELATED_OR_UNVERIFIED_PRECAS_ORIGINALS",
        "original_sources_authenticated": False,
        "six_e2e_proofs_credited": 0,
        "execution_or_cloud_cas_authorized": False,
        "may_rearm_v2r4": False,
        "may_start_v3": False,
        "may_retry_unknown_cas": False,
        "fresh_database_checkpoint_for_cas": False,
    }
    if not isinstance(host, dict) or not isinstance(cloud, dict):
        return result
    if (not isinstance(now_utc, datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() is None):
        return result

    def fresh(value: object) -> datetime | None:
        if not isinstance(value, str) or len(value) > 40 or not value.endswith("Z"):
            return None
        try:
            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return None
        if ts.tzinfo is None or ts.utcoffset() is None:
            return None
        return ts if 0 <= (now_utc - ts).total_seconds() <= 90 else None

    observed_host = fresh(host.get("observed_at_utc"))
    observed_cloud = fresh(cloud.get("observed_at_utc"))
    if (observed_host is None or observed_cloud is None
            or abs((observed_host-observed_cloud).total_seconds()) > 45):
        return result
    if (host.get("kind") != "V3_PRECAS_ORIGINALHOST_SNAPSHOT_V1"
            or host.get("source") != "EXTERNAL_MINIPC_PHYSICAL_OWNER"
            or cloud.get("kind") != "V3_PRECAS_CLOUD_ORIGINAL_SNAPSHOT_V1"
            or cloud.get("source") != "INDEPENDENT_PRODUCTION_SQL_QUERY"
            or host.get("phase") != "QUIESCED"
            or cloud.get("phase") != "CAS_NOT_ATTEMPTED"):
        return result

    patterns = {
        "predecessor_series_id": r"PAPER-V2R4-[0-9]{8}T[0-9]{6}Z",
        "successor_series_id": r"PAPER-V3-[0-9]{8}T[0-9]{6}Z",
        "reviewed_v3_repo_sha": r"[0-9a-f]{40}",
        "reviewed_v3_bundle_sha256": r"[0-9a-f]{64}",
        "reviewed_v3_strategy_sha256": r"[0-9a-f]{64}",
        "approved_six_proof_release_packet_sha256": r"[0-9a-f]{64}",
        "cutover_intent_id": r"[0-9a-f]{32}",
    }
    for field, pattern in patterns.items():
        value = host.get(field)
        if (not isinstance(value, str) or re.fullmatch(pattern, value) is None
                or cloud.get(field) != value):
            return result
    if host["predecessor_series_id"] == host["successor_series_id"]:
        return result

    expected_host = {
        "old_intake_tasks_disabled": True,
        "old_intake_workers_absent": True,
        "native_no_rearm_verified": True,
        "supervisor_no_rearm_verified": True,
        "old_lifecycle_and_cloudsync_running": True,
        "v3_writer_started": False,
        "cloud_cas_invoked": False,
        "real_money_actions": False,
    }
    expected_cloud = {
        "read_only": True,
        "cloud_mutations": False,
        "cloud_cas_invoked": False,
        "v3_successor_already_present": False,
    }
    for fields, original in ((expected_host, host), (expected_cloud, cloud)):
        if any(type(original.get(k)) is not bool or original[k] is not v
               for k, v in fields.items()):
            return result

    rows = cloud.get("active_series")
    if (not isinstance(rows, list) or len(rows) != 1
            or not isinstance(rows[0], dict)
            or rows[0].get("series_id") != host["predecessor_series_id"]
            or rows[0].get("status") != "active"):
        return result
    # The Cloud *readback* must be fresh, but a legitimate last-row update
    # can be hours/days old when no new outcomes/trades were written.
    # Never turn an old, stable V2R4 series into a failed release condition.
    def valid_db_version(value: object) -> bool:
        if not isinstance(value, str) or not value.endswith("Z") or len(value) > 40:
            return False
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return False
        return (stamp.tzinfo is not None and stamp.utcoffset() is not None
                and stamp <= observed_cloud)

    for count_key, updated_key in (
        ("original_candidate_count", "original_last_candidate_updated_at"),
        ("original_trade_count", "original_last_trade_updated_at")
    ):
        count, stamp = cloud.get(count_key), cloud.get(updated_key)
        if type(count) is not int or count < 0:
            return result
        if count == 0:
            if stamp is not None:
                return result
        else:
            if not valid_db_version(stamp):
                return result

    # These observations will be stale by the time a separate CAS is attempted.
    # PostgreSQL MUST lock/re-read original counts AND timestamps inside the
    # single atomic transaction. We never promote this review to a CAS permit.
    result["disposition"] = "CORRELATED_SOURCE_SHAPES_ONLY_NOT_CAS_AUTHORITY"
    return result

def assess_v3_cutover_recovery(
        *, phase: str, active_series: list[dict],
        expected_old: str, proposed_new: str,
        old_writer_fenced: bool = False,
        old_followups_preserved: bool = False,
        supervisor_old_intake_rearm_blocked: bool = False,
        successor_writer_healthy: bool = False) -> dict:
    """Pure V3 Paper cutover/rollback disposition; NEVER authorizes mutations.

    An indeterminate Cloud commit must never trigger an automatic retry,
    predecessor restoration or successor activation. The old and new writers
    stay fenced until independent current Cloud and Mini-PC evidence resolves
    the transaction. Pre-commit reversibility differs from post-commit.
    """
    result = {
        "kind": "V3_PAPER_CAS_RECOVERY_READONLY_DISPOSITION_V1",
        "phase": phase, "auto_restart_predecessor": False,
        "auto_start_successor": False, "auto_retry_cloud_cas": False,
        "mutation_authorized": False,
        "independent_current_host_cloud_ack_required": True,
        "disposition": "BLOCKED_UNVERIFIED_CUTOVER_SNAPSHOT",
    }
    # If the Cloud commit result is unknown, absent, unreachable, corrupt
    # or contradictory active-series rows must ALL lead to the same hard
    # quarantine. Never degrade UNKNOWN into a generic recoverable precommit.
    if phase == "CLOUD_COMMIT_OUTCOME_UNKNOWN":
        result["disposition"] = "CLOUD_AMBIGUOUS_QUARANTINE_BOTH_WRITERS"
        return result
    if (not isinstance(expected_old, str)
            or not expected_old.startswith("PAPER-V2R4-")
            or not isinstance(proposed_new, str)
            or not proposed_new.startswith("PAPER-V3-")
            or expected_old == proposed_new
            or not isinstance(active_series, list)
            or len(active_series) != 1
            or not isinstance(active_series[0], dict)
            or active_series[0].get("status") != "active"):
        return result
    current = active_series[0].get("series_id")
    if phase == "CLOUD_COMMIT_NOT_ATTEMPTED":
        if current == expected_old and not old_writer_fenced:
            result["disposition"] = "PRECOMMIT_DRYRUN_ONLY_NO_CLOUD_MUTATION"
        return result
    if phase == "CLOUD_REJECTED_BEFORE_COMMIT":
        if current == expected_old:
            result["disposition"] = "PRECOMMIT_RESTORE_REQUIRES_ORIGINAL_TASK_ACK"
        return result
    if phase == "CLOUD_COMMITTED":
        if current != proposed_new:
            result["disposition"] = "POSTCOMMIT_CLOUD_MISMATCH_QUARANTINE"
            return result
        if (old_writer_fenced is not True
                or old_followups_preserved is not True
                or supervisor_old_intake_rearm_blocked is not True):
            result["disposition"] = "POSTCOMMIT_OLD_WRITER_FENCE_UNVERIFIED"
            return result
        if successor_writer_healthy is not True:
            result["disposition"] = "POSTCOMMIT_KEEP_OLD_FENCED_STOP_NEW_FOR_REVIEW"
            return result
        result["disposition"] = "POSTCOMMIT_SOURCE_ACK_STILL_REQUIRED"
    return result
