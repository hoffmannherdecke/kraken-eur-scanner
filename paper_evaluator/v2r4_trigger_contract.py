#!/usr/bin/env python3
"""Deterministic V2R4 WAIT-trigger contract.

This module is intentionally paper-only. It validates and evaluates machine-readable
WAIT trigger plans so a local Mini-PC can watch cheap public Kraken data without
continuously calling an LLM. A trigger match NEVER places an order; it only requests
one fresh paper strategy recheck.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

ALLOWED_METRICS = {
    "last_eur",
    "bid_eur",
    "ask_eur",
    "spread_pct",
    "closed_1m_close_eur",
    "closed_1m_volume_ratio_5",
    "closed_5m_close_eur",
    "closed_5m_volume_ratio_5",
    "closed_15m_close_eur",
    "closed_15m_volume_ratio_4",
}
ALLOWED_OPS = {">", ">=", "<", "<="}
ALLOWED_ACTION = "FRESH_PAPER_RECHECK_ONLY"


@dataclass(frozen=True)
class TriggerResult:
    matched: bool
    expired: bool
    reason: str
    condition_results: tuple[bool, ...]


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc


def validate_plan(plan: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "candidate_id",
        "pair",
        "created_at_utc",
        "expires_at_utc",
        "logic",
        "conditions",
        "on_match",
        "paper_only",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise ValueError("missing trigger-plan fields: " + ",".join(missing))
    if int(plan["schema_version"]) != 1:
        raise ValueError("unsupported trigger-plan schema_version")
    if plan["paper_only"] is not True:
        raise ValueError("trigger plan must be paper-only")
    if plan["on_match"] != ALLOWED_ACTION:
        raise ValueError("trigger plan may only request a fresh paper recheck")
    if plan["logic"] != "ALL":
        raise ValueError("only ALL trigger logic is allowed in V2R4 prep")
    if not isinstance(plan["candidate_id"], str) or not plan["candidate_id"].strip():
        raise ValueError("candidate_id required")
    if not isinstance(plan["pair"], str) or "/EUR" not in plan["pair"]:
        raise ValueError("pair must be a Kraken EUR pair")

    created = _parse_utc(plan["created_at_utc"])
    expires = _parse_utc(plan["expires_at_utc"])
    if expires <= created:
        raise ValueError("expires_at_utc must be after created_at_utc")
    if (expires - created).total_seconds() > 60 * 60:
        raise ValueError("V2R4 WAIT trigger plan may not exceed 60 minutes")

    conditions = plan["conditions"]
    if not isinstance(conditions, list) or not conditions or len(conditions) > 6:
        raise ValueError("conditions must contain 1..6 entries")
    for idx, cond in enumerate(conditions):
        if set(cond) != {"metric", "op", "value"}:
            raise ValueError(f"condition {idx} keys must be metric/op/value")
        if cond["metric"] not in ALLOWED_METRICS:
            raise ValueError(f"condition {idx} uses unsupported metric")
        if cond["op"] not in ALLOWED_OPS:
            raise ValueError(f"condition {idx} uses unsupported operator")
        _number(cond["value"], f"condition {idx} value")


def _compare(actual: float, op: str, threshold: float) -> bool:
    if op == ">":
        return actual > threshold
    if op == ">=":
        return actual >= threshold
    if op == "<":
        return actual < threshold
    if op == "<=":
        return actual <= threshold
    raise ValueError("unsupported operator")


def evaluate_plan(
    plan: dict[str, Any],
    metrics: dict[str, Any],
    *,
    now: datetime | None = None,
) -> TriggerResult:
    validate_plan(plan)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    expires = _parse_utc(plan["expires_at_utc"])
    if now >= expires:
        return TriggerResult(False, True, "TTL_EXPIRED", tuple())

    results: list[bool] = []
    for idx, cond in enumerate(plan["conditions"]):
        metric = cond["metric"]
        if metric not in metrics or metrics[metric] is None:
            return TriggerResult(
                False,
                False,
                f"MISSING_METRIC:{metric}",
                tuple(results),
            )
        actual = _number(metrics[metric], f"metric {metric}")
        threshold = _number(cond["value"], f"condition {idx} value")
        results.append(_compare(actual, cond["op"], threshold))

    matched = all(results)
    return TriggerResult(
        matched,
        False,
        "MATCH_REQUIRES_FRESH_PAPER_RECHECK" if matched else "CONDITIONS_NOT_MET",
        tuple(results),
    )
