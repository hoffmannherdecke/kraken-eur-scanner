#!/usr/bin/env python3
"""Single pure contract for V2R4 strategy epoch across technical runtime rollovers.

Only the strategy-scoped first epoch is frozen; technical series may rotate
under exactly the same fingerprint. One immutable closed segment per cutover,
followed by one currently verified live segment. NO API calls, orders or writes.
The same contract is used by both the project-state validator and milestone
controller so they cannot silently disagree over candidate/trade counts.
"""
from __future__ import annotations

from typing import Any


def validate_epoch(active: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    series = active.get("series_id")
    revision = active.get("strategy_revision")
    technical = active.get("technical_rotation_runtime_last_verified") or {}
    closed = active.get("strategy_epoch_closed_segments")
    if active.get("strategy_epoch_closed_segments_rule") != (
        "APPEND_ONLY_EACH_AUTHORIZED_TECHNICAL_ROTATION_SUM_DISJOINT_CLOSED_SEGMENTS_PLUS_ONE_LIVE_SEGMENT_NEVER_RESET_OR_DOUBLE_COUNT"
    ):
        errors.append("strategy epoch closed-segment ledger is not append-only")
    if not isinstance(closed, list) or not closed:
        return errors + ["strategy epoch must retain a nonempty closed technical series list"]
    seen: set[str] = set()
    expected = series
    fp = technical.get("strategy_fingerprint_sha256")
    if not isinstance(fp, str) or len(fp) != 64:
        errors.append("missing shared original strategy fingerprint")
    for idx, segment in enumerate(closed):
        if not isinstance(segment, dict):
            return errors + ["invalid closed technical segment object"]
        sid = segment.get("series_id")
        successor = segment.get("successor_series_id")
        if not sid or sid in seen or sid != expected or successor in seen or successor == sid:
            errors.append("technical epoch segment lineage missing, duplicate or noncontiguous")
        seen.add(sid)
        expected = successor
        if (segment.get("status") != "technical_closed"
                or segment.get("immutable") is not True
                or segment.get("strategy_revision") != revision
                or segment.get("strategy_fingerprint_sha256") != fp
                or segment.get("followups_beyond_cutover") != "CENSORED_NOT_0_LOSS"):
            errors.append("technical closed series not immutable or wrongly classified")
        if not segment.get("cutover_at_utc") or not segment.get("observed_at_utc"):
            errors.append("undated technical epoch closure")
        fields = ("frozen_outcomes_at_cutover", "frozen_completed_trades_at_cutover",
                  "verified_complete_24h_at_cutover", "verified_eligible_24h_at_cutover")
        vals = [segment.get(k) for k in fields]
        if (any(not isinstance(v, int) or isinstance(v, bool) for v in vals)
                or not (0 <= vals[1] <= vals[0] and
                        0 <= vals[2] <= vals[3] <= vals[0] and vals[0] > 0)):
            errors.append("technical epoch source outcome/maturity counts invalid")
    if expected != technical.get("series_id") or expected in seen or expected == series:
        errors.append("strategy epoch closed chain does not end at current technical series")
    if technical.get("legacy_snapshot_mirrors_latest_closed_segment") is not True:
        errors.append("latest technical snapshot must mirror last immutable closed segment")
    last = closed[-1]
    if (technical.get("predecessor_outcomes_immutable_at_cutover") != last.get("frozen_outcomes_at_cutover")
            or technical.get("predecessor_trades_immutable_at_cutover") != last.get("frozen_completed_trades_at_cutover")
            or technical.get("predecessor_24h_complete_at_cutover") != last.get("verified_complete_24h_at_cutover")
            or technical.get("predecessor_24h_eligible_at_cutover") != last.get("verified_eligible_24h_at_cutover")):
        errors.append("latest technical snapshot and epoch closed ledger disagree")
    if (technical.get("original_strategy_epoch_series_id") != series
            or technical.get("relation") != "TECHNICAL_ROTATION_SAME_STRATEGY_FINGERPRINT_NOT_STRATEGY_RELEASE"
            or technical.get("productivity_clock_reset") is not False):
        errors.append("technical rotation may not change original strategy identity/clock")
    return errors


def summarize_epoch(active: dict[str, Any], paper: dict[str, Any]) -> dict[str, int | bool]:
    errors = validate_epoch(active)
    if errors:
        raise ValueError("FAIL_CLOSED: " + "; ".join(errors))
    technical = active["technical_rotation_runtime_last_verified"]
    if paper.get("series_id") != technical.get("series_id"):
        raise ValueError("FAIL_CLOSED: paper live series not exact latest technical successor")
    if paper.get("strategy_revision") != active.get("strategy_revision"):
        raise ValueError("FAIL_CLOSED: live paper revision drift")
    for key in ("candidate_outcomes", "completed_trades", "complete_24h"):
        if not isinstance(paper.get(key), int) or paper[key] < 0:
            raise ValueError("FAIL_CLOSED: live cohort metric unavailable or invalid: " + key)
    closed = active["strategy_epoch_closed_segments"]
    old_n = sum(x["frozen_outcomes_at_cutover"] for x in closed)
    old_t = sum(x["frozen_completed_trades_at_cutover"] for x in closed)
    old_m = sum(x["verified_complete_24h_at_cutover"] for x in closed)
    return {
        "epoch_minimum_candidate_outcomes": old_n + paper["candidate_outcomes"],
        "epoch_minimum_completed_trades": old_t + paper["completed_trades"],
        "epoch_minimum_complete_24h": old_m + paper["complete_24h"],
        "epoch_combines_verified_technical_segments": True,
        "technical_closed_segment_count": len(closed),
    }
