"""Offline defensive contract for the existing MINI-PC watchdog cloud row."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from tools.minipc_cloud_evidence import classify_minipc_evidence, classify_minipc_alert_freshness

NOW = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)
REQUIRED = ("runtime_supervisor", "v2r4_paper_wait", "v2r4_paper_candidates")


def stamp(offset_seconds: int = -60) -> str:
    return (NOW + timedelta(seconds=offset_seconds)).isoformat()


def healthy_row(offset_seconds: int = -60):
    return {
        "node_id": "MINI-PC",
        "observed_at": stamp(offset_seconds),
        "status": "HEALTHY",
        "payload": {
            "checked_at_local": stamp(offset_seconds),
            "health_state": "OK",
            "issues": [],
            "checks": {name: {"ok": True, "detail": "PRIVATE DO NOT OUTPUT"}
                       for name in REQUIRED},
            "token": "NOT_TO_BE_EXPOSED",
        },
    }


class MiniPCReadbackContract(unittest.TestCase):
    def classify(self, row, **kw):
        return classify_minipc_evidence(row, now=NOW, required_checks=REQUIRED, **kw)

    def assert_code(self, row, code):
        result = self.classify(row)
        self.assertEqual(result["source_evidence_state"], code)
        self.assertEqual(result["host_reported_healthy"], code == "HEALTHY_REPORTED")
        self.assertTrue(result["alert_policy_unchanged"])
        self.assertFalse(result["runtime_pid_verified"])
        self.assertFalse(result["delivery_ack_verified"])
        raw = repr(result)
        self.assertNotIn("NOT_TO_BE_EXPOSED", raw)
        self.assertNotIn("PRIVATE DO NOT OUTPUT", raw)

    def test_healthy_report_is_not_independent_pid_proof(self):
        self.assert_code(healthy_row(), "HEALTHY_REPORTED")

    def test_missing_is_not_healthy(self):
        self.assert_code(None, "UNKNOWN_MISSING")
        self.assert_code({}, "INVALID_NODE")

    def test_wrong_node_is_not_healthy(self):
        row = healthy_row()
        row["node_id"] = "OTHER-NODE"
        self.assert_code(row, "INVALID_NODE")

    def test_unparseable_and_naive_time_are_invalid(self):
        for val in ("nope", "2026-10-17T08:59:00", None):
            row = healthy_row()
            row["observed_at"] = val
            with self.subTest(val=val):
                self.assert_code(row, "INVALID_TIMESTAMP")

    def test_stale_boundary(self):
        self.assert_code(healthy_row(-1200), "HEALTHY_REPORTED")
        self.assert_code(healthy_row(-1201), "STALE")

    def test_future_boundary(self):
        self.assert_code(healthy_row(120), "HEALTHY_REPORTED")
        self.assert_code(healthy_row(121), "INVALID_FUTURE")
        self.assert_code(healthy_row(180), "INVALID_FUTURE")

    def test_both_warning_and_critical_remain_not_healthy(self):
        for status in ("WARNING", "CRITICAL"):
            row = healthy_row()
            row["status"] = status
            with self.subTest(status=status):
                self.assert_code(row, "NOT_HEALTHY_" + status)

    def test_unknown_status_is_not_ok(self):
        row = healthy_row()
        row["status"] = "UNKNOWN"
        self.assert_code(row, "UNKNOWN_STATUS")

    def test_missing_payload(self):
        row = healthy_row()
        row["payload"] = None
        self.assert_code(row, "UNKNOWN_PAYLOAD")

    def test_source_clock_conflict(self):
        row = healthy_row()
        row["payload"]["checked_at_local"] = stamp(-50)
        self.assert_code(row, "INVALID_SOURCE_CLOCK")
        row["payload"]["checked_at_local"] = "not-a-clock"
        self.assert_code(row, "INVALID_SOURCE_CLOCK")

    def test_health_state_not_ok(self):
        row = healthy_row()
        row["payload"]["health_state"] = "DEGRADED"
        self.assert_code(row, "NOT_HEALTHY_STATE")

    def test_issues_must_be_explicit_empty_list(self):
        row = healthy_row()
        row["payload"].pop("issues")
        self.assert_code(row, "UNKNOWN_ISSUES")
        row["payload"]["issues"] = [{"check": "private", "detail": "DO NOT OUTPUT"}]
        self.assert_code(row, "NOT_HEALTHY_ISSUES")

    def test_missing_or_bad_required_check_is_not_verified(self):
        row = healthy_row()
        row["payload"]["checks"]["runtime_supervisor"]["ok"] = None
        self.assert_code(row, "FIELD_NOT_VERIFIED")
        row = healthy_row()
        row["payload"]["checks"].pop("runtime_supervisor")
        self.assert_code(row, "FIELD_NOT_VERIFIED")
        row = healthy_row()
        row["payload"]["checks"]["runtime_supervisor"]["ok"] = "true"
        self.assert_code(row, "FIELD_NOT_VERIFIED")

    def test_explicit_no_required_fields_means_host_report_only(self):
        row = healthy_row()
        row["payload"].pop("checks")
        result = classify_minipc_evidence(row, now=NOW)
        self.assertEqual(result["source_evidence_state"], "HEALTHY_REPORTED")
        self.assertEqual(result["required_check_count"], 0)

    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            classify_minipc_evidence(healthy_row(), now=datetime(2026, 10, 17))


class MiniPCExistingAlertUpsertFreshnessContract(unittest.TestCase):
    """Snapshot of the existing GitHub alert-state upsert; never a heartbeat."""

    @staticmethod
    def row(age_seconds=60, condition="OK"):
        return {
            "node_id": "MINI-PC",
            "updated_at": (NOW - timedelta(seconds=age_seconds)).isoformat(),
            "last_condition": condition,
            "last_alert_at": "secret-looking-data-must-not-leak",
            "last_recovery_at": "private-do-not-output",
        }

    def check(self, row, expected):
        out = classify_minipc_alert_freshness(row, now=NOW)
        self.assertEqual(out["alert_upsert_state"], expected)
        self.assertFalse(out["github_run_verified"])
        self.assertFalse(out["slack_delivery_verified"])
        self.assertFalse(out["recovery_verified"])
        self.assertFalse(out["host_reported_healthy"])
        self.assertFalse(out["writes_performed"])
        self.assertNotIn("secret-looking", repr(out))
        self.assertNotIn("private-do-not-output", repr(out))
        return out

    def test_recent_upsert_is_not_github_or_delivery_ack(self):
        out = self.check(self.row(), "RECENT")
        self.assertEqual(out["last_alert_condition"], "OK")
        self.assertEqual(out["nominal_cadence_seconds"], 900)

    def test_missing_and_wrong_node_fail_closed(self):
        self.check(None, "UNKNOWN_MISSING")
        self.check({}, "INVALID_NODE")
        data = self.row()
        data["node_id"] = "UNKNOWN"
        self.check(data, "INVALID_NODE")

    def test_pg_native_timestamp_with_space_timezone_is_accepted(self):
        data = self.row()
        data["updated_at"] = (NOW - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S.%f+00")
        self.check(data, "RECENT")

    def test_invalid_or_naive_timestamp_is_not_success(self):
        for value in ("", "garbage", None, "2026-10-17T08:59:00"):
            data = self.row()
            data["updated_at"] = value
            with self.subTest(value=value):
                self.check(data, "INVALID_TIMESTAMP")

    def test_future_clock_boundary(self):
        self.check(self.row(-120), "RECENT")
        self.check(self.row(-121), "INVALID_FUTURE")

    def test_delayed_and_stale_not_new_watcher(self):
        self.check(self.row(1800), "RECENT")
        self.check(self.row(1801), "DELAYED")
        self.check(self.row(2252), "DELAYED")
        self.check(self.row(2700), "DELAYED")
        self.check(self.row(2701), "STALE")

    def test_critical_upsert_does_not_prove_slack_ack(self):
        out = self.check(self.row(120, "CRITICAL"), "RECENT")
        self.assertEqual(out["last_alert_condition"], "CRITICAL")

    def test_missing_condition_remains_unknown_even_if_recent(self):
        self.check(self.row(1, None), "UNKNOWN_CONDITION")
        self.check(self.row(1, "WARNING"), "UNKNOWN_CONDITION")

    def test_naive_now_rejected(self):
        with self.assertRaises(ValueError):
            classify_minipc_alert_freshness(self.row(), now=NOW.replace(tzinfo=None))

    def test_no_global_runtime_or_secret_dependencies(self):
        data = self.row(3000)
        data["webhook"] = "do-not-export"
        out = self.check(data, "STALE")
        self.assertNotIn("webhook", out)
        self.assertNotIn("do-not-export", repr(out))


if __name__ == "__main__":
    unittest.main()
