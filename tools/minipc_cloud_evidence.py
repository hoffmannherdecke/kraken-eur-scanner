"""Pure, fail-closed MINI-PC cloud evidence classification for on-demand readbacks.

Consumes an ALREADY FETCHED minipc_status_current row (including its compact
watchdog payload). Never contacts Supabase, Windows, GitHub or Slack. This is
not the alert policy, an alert delivery ACK, a process PID proof, or a trading
release gate. Reuse from existing authorized readers; no new service/cron.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

MAX_AGE_SECONDS = 20 * 60
MAX_FUTURE_SECONDS = 120
MAX_CLOCK_SKEW_SECONDS = 2
NODE_ID = "MINI-PC"

# Output is intentionally a fixed small whitelist: no payload details, file
# paths, task arguments, secrets, private logs or raw issues are copied.
def classify_minipc_evidence(
    row: Mapping[str, Any] | None,
    *,
    now: datetime,
    required_checks: Sequence[str] = (),
) -> dict[str, Any]:
    """Classify host-*reported* evidence; never upgrade alert OK to host HEALTHY.

    A success requires an explicit current timestamp, matching host and relay
    source clocks, the watchdog's OK status and zero issues, plus all requested
    check flags. A caller must separately establish API/authenticity provenance.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    result: dict[str, Any] = {
        "kind": "MINIPC_CLOUD_EVIDENCE_CLASSIFICATION_V1",
        "node_id": NODE_ID,
        "source_evidence_state": "UNKNOWN_MISSING",
        "host_reported_healthy": False,
        "age_seconds": None,
        "required_check_count": len(required_checks),
        "alert_policy_unchanged": True,
        "runtime_pid_verified": False,
        "delivery_ack_verified": False,
    }

    def finish(code: str) -> dict[str, Any]:
        result["source_evidence_state"] = code
        result["host_reported_healthy"] = code == "HEALTHY_REPORTED"
        return result

    def read_timestamp(raw: Any) -> datetime | None:
        if not isinstance(raw, str) or "T" not in raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)

    if not isinstance(row, Mapping):
        return finish("UNKNOWN_MISSING")
    if row.get("node_id") != NODE_ID:
        return finish("INVALID_NODE")

    observed = read_timestamp(row.get("observed_at"))
    if observed is None:
        return finish("INVALID_TIMESTAMP")
    delta = (now.astimezone(timezone.utc) - observed).total_seconds()
    result["age_seconds"] = round(delta)
    if delta < -MAX_FUTURE_SECONDS:
        return finish("INVALID_FUTURE")
    if delta > MAX_AGE_SECONDS:
        return finish("STALE")

    status = row.get("status")
    if status == "CRITICAL":
        return finish("NOT_HEALTHY_CRITICAL")
    if status == "WARNING":
        return finish("NOT_HEALTHY_WARNING")
    if status != "HEALTHY":
        return finish("UNKNOWN_STATUS")

    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        return finish("UNKNOWN_PAYLOAD")
    checked_at = read_timestamp(payload.get("checked_at_local"))
    if checked_at is None or abs((checked_at - observed).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
        return finish("INVALID_SOURCE_CLOCK")
    if payload.get("health_state") != "OK":
        return finish("NOT_HEALTHY_STATE")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        return finish("UNKNOWN_ISSUES")
    if issues:
        return finish("NOT_HEALTHY_ISSUES")

    check_names = tuple(required_checks)
    if any(not isinstance(name, str) or not name or len(name) > 96 for name in check_names):
        return finish("INVALID_REQUIRED_CHECK")
    if check_names:
        checks = payload.get("checks")
        if not isinstance(checks, Mapping):
            return finish("FIELD_NOT_VERIFIED")
        if any(
            not isinstance(checks.get(name), Mapping)
            or checks[name].get("ok") is not True
            for name in check_names
        ):
            return finish("FIELD_NOT_VERIFIED")

    return finish("HEALTHY_REPORTED")


# The original GitHub MINI-PC cloud watch is scheduled for every 15 minutes,
# but GitHub Actions scheduling is best-effort, not an execution guarantee.
# Two missed nominal ticks merit an on-demand diagnostic, not a new pager.
ALERT_EXPECTED_CADENCE_SECONDS = 15 * 60
ALERT_DELAYED_SECONDS = 30 * 60
ALERT_STALE_SECONDS = 45 * 60

def classify_minipc_alert_freshness(
    alert_row: Mapping[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """Read-only freshness of the *existing* alert-state upsert.

    This is evidence only of the most recent state-row write; never a GitHub
    run-success, Slack delivery, recovery ACK or MINI-PC process proof.
    It must never trigger a workflow or modify an alert/heartbeat table.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")

    result: dict[str, Any] = {
        "kind": "MINIPC_ALERT_UPSERT_FRESHNESS_V1",
        "node_id": NODE_ID,
        "alert_upsert_state": "UNKNOWN_MISSING",
        "age_seconds": None,
        "nominal_cadence_seconds": ALERT_EXPECTED_CADENCE_SECONDS,
        "last_alert_condition": "UNKNOWN",
        "github_run_verified": False,
        "slack_delivery_verified": False,
        "recovery_verified": False,
        "host_reported_healthy": False,
        "writes_performed": False,
    }

    def finish(code: str) -> dict[str, Any]:
        result["alert_upsert_state"] = code
        return result

    if not isinstance(alert_row, Mapping):
        return finish("UNKNOWN_MISSING")
    if alert_row.get("node_id") != NODE_ID:
        return finish("INVALID_NODE")

    raw = alert_row.get("updated_at")
    if not isinstance(raw, str) or not raw.strip():
        return finish("INVALID_TIMESTAMP")
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            return finish("INVALID_TIMESTAMP")
    except ValueError:
        return finish("INVALID_TIMESTAMP")

    age = (now.astimezone(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
    result["age_seconds"] = round(age)
    # The presence of a timestamp from the future is not a successful run.
    if age < -MAX_FUTURE_SECONDS:
        return finish("INVALID_FUTURE")

    last_condition = alert_row.get("last_condition")
    if last_condition not in ("OK", "CRITICAL", "STALE"):
        return finish("UNKNOWN_CONDITION")
    result["last_alert_condition"] = last_condition

    if age > ALERT_STALE_SECONDS:
        return finish("STALE")
    if age > ALERT_DELAYED_SECONDS:
        return finish("DELAYED")
    return finish("RECENT")
