#!/usr/bin/env python3
"""Build a validated V2R4 paper WAIT trigger plan from a structured decision."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

try:\n    from .v2r4_trigger_contract import validate_plan\nexcept ImportError:  # direct script execution\n    from v2r4_trigger_contract import validate_plan


def _dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_wait_trigger_plan(
    candidate: dict[str, Any],
    decision: dict[str, Any],
    created_at: str | datetime,
) -> dict[str, Any] | None:
    """Return a fail-closed machine-readable plan for WAIT, else None.

    V2R4 evaluators must provide watch_conditions directly in the decision.
    Free-text missing_triggers are never parsed into executable conditions.
    """
    if decision.get("decision") != "WAIT":
        return None

    ttl = int(decision.get("ttl_minutes") or 0)
    if ttl < 1 or ttl > 60:
        raise ValueError("WAIT ttl_minutes must be 1..60")

    conditions = decision.get("watch_conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("V2R4 WAIT requires structured watch_conditions")

    created = _dt(created_at)
    plan = {
        "schema_version": 1,
        "candidate_id": candidate["candidate_id"],
        "pair": candidate["pair"],
        "altname": candidate["altname"],
        "created_at_utc": _iso(created),
        "expires_at_utc": _iso(created + timedelta(minutes=ttl)),
        "logic": "ALL",
        "conditions": conditions,
        "on_match": "FRESH_PAPER_RECHECK_ONLY",
        "paper_only": True,
    }
    validate_plan(plan)
    return plan
