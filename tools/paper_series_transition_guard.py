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
