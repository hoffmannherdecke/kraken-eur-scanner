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
