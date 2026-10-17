"""Offline defensive contract for the existing MINI-PC watchdog cloud row."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from tools.minipc_cloud_evidence import (
    DAILY_NATIVE_TASKS, DAILY_REQUIRED_CHECKS,
    classify_minipc_evidence, classify_minipc_alert_freshness,
    classify_minipc_daily_diagnostics, classify_minipc_github_watch_runs,
    parse_postgrest_exact_count,
)

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


class MiniPCDailyReadbackHandoffContract(unittest.TestCase):
    def row(self):
        data = healthy_row()
        for key in DAILY_REQUIRED_CHECKS:
            data["payload"]["checks"][key] = {"ok": True, "detail": "DO NOT LEAK"}
        data["payload"]["native_task_readback"] = {
            "kind": "MINIPC_NATIVE_TASK_READBACK_V1",
            "no_runtime_or_release_authority": True,
            "observations": {
                k: {
                    "task_state": "Ready" if k == "v3_canary_observation_28h" else "Running",
                    "last_result_code": 0 if k == "v3_canary_observation_28h" else 267009,
                    "last_result_meaning": (
                        "ZERO_RESULT_NOT_RUNTIME_PROOF" if k == "v3_canary_observation_28h"
                        else "RUNNING_CODE_AND_STATE_MATCH"
                    ),
                    "arguments": "LEAKING_SENSITIVE_COMMAND_ARGUMENTS",
                }
                for k in DAILY_NATIVE_TASKS
            },
            "secret": "LEAKING_PRIVATE_SECRET",
        }
        return data

    def check(self, row, state, health="HEALTHY_REPORTED"):
        out = classify_minipc_daily_diagnostics(row, now=NOW)
        self.assertEqual(out["native_task_readback_state"], state)
        self.assertEqual(out["cloud_evidence_state"], health)
        self.assertTrue(out["reporting_only"])
        for blocked in (
            "LEAKING_PRIVATE_SECRET", "LEAKING_SENSITIVE_COMMAND_ARGUMENTS",
            "NOT_TO_BE_EXPOSED", "DO NOT LEAK",
        ):
            self.assertNotIn(blocked, repr(out))
        self.assertFalse(out["slack_delivery_verified"])
        self.assertFalse(out["native_task_liveness_independently_verified"])
        self.assertFalse(out["paper_or_real_money_authorized"])
        return out

    def test_actual_reported_six_tasks_without_promoting_canary_zero(self):
        out = self.check(self.row(), "COMPLETE_REPORTED")
        self.assertEqual(out["native_observation_count"], 6)
        self.assertEqual(
            out["native_task_observations"]["v3_canary_observation_28h"]["last_result_meaning"],
            "ZERO_RESULT_NOT_RUNTIME_PROOF",
        )

    def test_legacy_report_without_native_data_fails_closed(self):
        out = self.check(healthy_row(), "UNKNOWN_MISSING", "FIELD_NOT_VERIFIED")
        self.assertEqual(out["native_observation_count"], 0)

    def test_stale_original_report_does_not_confirm_native_tasks(self):
        row = self.row()
        row["observed_at"] = stamp(-1201)
        row["payload"]["checked_at_local"] = stamp(-1201)
        out = self.check(row, "SOURCE_UNVERIFIED", "STALE")
        self.assertEqual(out["native_observation_count"], 0)

    def test_warning_is_not_silently_upgraded_to_healthy(self):
        row = self.row()
        row["status"] = "WARNING"
        out = self.check(row, "COMPLETE_REPORTED", "NOT_HEALTHY_WARNING")
        self.assertFalse(out["host_reported_healthy"])

    def test_native_missing_one_is_incomplete(self):
        row = self.row()
        row["payload"]["native_task_readback"]["observations"].pop("v2r4_paper_wait")
        out = self.check(row, "INCOMPLETE")
        self.assertEqual(out["native_observation_count"], 5)

    def test_native_contract_mismatch_rejected(self):
        row = self.row()
        row["payload"]["native_task_readback"]["no_runtime_or_release_authority"] = False
        self.check(row, "INVALID_CONTRACT")

    def test_native_running_code_state_mismatch_must_be_reviewed(self):
        row = self.row()
        item = row["payload"]["native_task_readback"]["observations"]["v2r4_paper_wait"]
        item["task_state"] = "Ready"
        item["last_result_meaning"] = "RUNNING_CODE_STATE_MISMATCH"
        self.check(row, "REVIEW_REQUIRED")

    def test_unavailable_scheduler_data_fails_closed(self):
        row = self.row()
        item = row["payload"]["native_task_readback"]["observations"]["v2r4_paper_wait"]
        item["last_result_code"] = None
        item["last_result_meaning"] = "UNAVAILABLE"
        self.check(row, "INCOMPLETE")

    def test_unexpected_codes_and_forged_bool_are_rejected(self):
        for code in (True, -1, 2 ** 50, "267009"):
            row = self.row()
            row["payload"]["native_task_readback"]["observations"]["v2r4_paper_wait"]["last_result_code"] = code
            with self.subTest(code=code):
                self.check(row, "REVIEW_REQUIRED")

    def test_malformed_native_fields_fail_closed_without_exceptions(self):
        for bad in ([], {}, None, False):
            row = self.row()
            row["payload"]["native_task_readback"]["observations"]["v2r4_paper_wait"]["task_state"] = bad
            with self.subTest(bad=repr(bad)):
                self.check(row, "REVIEW_REQUIRED")

    def test_bad_native_label_is_never_accepted(self):
        row = self.row()
        row["payload"]["native_task_readback"]["observations"]["v2r4_paper_wait"]["last_result_meaning"] = "UNKNOWN_NEW_CODE"
        self.check(row, "REVIEW_REQUIRED")

    def test_daily_report_reuses_existing_schedule_and_slack_route(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        original = (root / ".github/workflows/minipc-daily-status.yml").read_text("utf-8")
        self.assertIn("cron: '0 8,9 * * *'", original)
        self.assertIn("native_diagnostics=classify_minipc_daily_diagnostics(row,now=now_utc)", original)
        self.assertIn('"native_task_diagnostics":native_diagnostics', original)
        # Historical all-series totals must not be confused with the
        # current technical rotation, open trades or actual V3 model buys.
        self.assertIn('"metric_provenance":metric_provenance', original)
        self.assertIn('"kind":"MINIPC_DAILY_METRIC_PROVENANCE_V1"', original)
        self.assertIn('"source_report_observed_at":row["observed_at"]', original)
        self.assertIn('"series_id_at_report":current_series_id', original)
        self.assertIn('"strategy_revision_at_report":current_revision', original)
        self.assertIn('"ALL_V2R4_SHADOW_EVIDENCE_HISTORY"', original)
        self.assertIn('"HOST_REPORTED_V2R4_WATCHDOG_DETAIL_NOT_TRADE_TOTAL"', original)
        self.assertIn('"DETECTION_LAST_24H_AT_GENERATED_AT"', original)
        self.assertIn('"current_v3_model_or_buy_decision_verified":False', original)
        self.assertIn('"historical_counts_prove_live_strategy_profitability":False', original)
        self.assertIn('historisch alle Serien: Events {shadow_events}', original)
        self.assertIn('aktuell laut Watchdog aktiv {active_outcomes}', original)
        self.assertIn('dry_run=event_name!="schedule"', original)
        self.assertIn('if dry_run:\n              raise SystemExit(0)', original)
        self.assertEqual(original.count('"/rest/v1/minipc_status_current?'), 1)
        self.assertEqual(original.count('"POST",\n              "/rest/v1/minipc_daily_status'), 1)



class MiniPCOriginalGithubRunCadenceContract(unittest.TestCase):
    """Only already-read original GitHub Actions schedule metadata, no APIs."""

    WATCH_ID = 371909131

    @staticmethod
    def scheduled_run(age_seconds: int, run_id: int = 1068):
        return {
            "workflow_id": MiniPCOriginalGithubRunCadenceContract.WATCH_ID,
            "event": "schedule",
            "id": run_id,
            "created_at": (NOW - timedelta(seconds=age_seconds)).isoformat(),
            "status": "completed",
            "conclusion": "success",
            "html_url": "PRIVATE_NEVER_EXPORT",
            "actor": {"token": "SECRET_DO_NOT_COPY"},
        }

    def classify(self, rows, expected):
        answer = classify_minipc_github_watch_runs(
            {"workflow_runs": rows}, now=NOW,
        )
        self.assertEqual(answer["run_evidence_state"], expected)
        for key in (
            "all_expected_triggers_verified",
            "schedule_delay_or_drop_cause_verified",
            "job_logs_verified",
            "alert_upsert_ack_verified",
            "slack_delivery_verified",
            "host_reported_healthy",
            "writes_performed",
        ):
            self.assertIs(answer[key], False)
        self.assertNotIn("PRIVATE_NEVER_EXPORT", repr(answer))
        self.assertNotIn("SECRET_DO_NOT_COPY", repr(answer))
        return answer

    def test_realistic_39_minute_gap_not_automatically_github_outage(self):
        rows = [
            self.scheduled_run(300, 1068),
            self.scheduled_run(300 + 2373, 1067),
        ]
        out = self.classify(rows, "RECENT_SUCCESS_WITH_RECORDED_GAP")
        self.assertEqual(out["observed_inter_run_gap_seconds"], 2373)
        self.assertEqual(out["matched_schedule_run_count_in_sample"], 2)
        self.assertEqual(out["latest_run_id"], 1068)
        self.assertEqual(out["nominal_cadence_seconds"], 900)

    def test_regular_two_runs(self):
        self.classify([
            self.scheduled_run(60, 11),
            self.scheduled_run(960, 10),
        ], "RECENT_SUCCESS")

    def test_best_effort_delay_vs_stale_distinct(self):
        self.classify([self.scheduled_run(1800)], "RECENT_SUCCESS")
        self.classify([self.scheduled_run(1801)], "LAST_RECORDED_RUN_DELAYED")
        self.classify([self.scheduled_run(2700)], "LAST_RECORDED_RUN_DELAYED")
        self.classify([self.scheduled_run(2701)], "LAST_RECORDED_RUN_STALE")

    def test_actual_failure_not_hidden_by_older_success(self):
        latest = self.scheduled_run(100, 100)
        latest["conclusion"] = "failure"
        self.classify([self.scheduled_run(1000, 99), latest],
                      "LATEST_RUN_NOT_SUCCESSFUL")

    def test_pending_run_not_claimed_success(self):
        x = self.scheduled_run(40)
        x["status"] = "in_progress"
        x["conclusion"] = None
        self.classify([x], "LATEST_RUN_NOT_COMPLETED")

    def test_ignores_different_workflow_and_manual_dispatches(self):
        other = self.scheduled_run(3, 200)
        other["workflow_id"] = 99999
        manual = self.scheduled_run(5, 201)
        manual["event"] = "workflow_dispatch"
        out = self.classify(
            [other, manual, self.scheduled_run(120, 202)],
            "RECENT_SUCCESS",
        )
        self.assertEqual(out["matched_schedule_run_count_in_sample"], 1)

    def test_no_matching_runs_is_not_failed_run(self):
        self.classify([], "NO_WATCH_SCHEDULE_RUNS_IN_SAMPLE")
        self.assertEqual(classify_minipc_github_watch_runs(None, now=NOW)[
            "run_evidence_state"], "UNKNOWN_MISSING")
        self.assertEqual(classify_minipc_github_watch_runs({
            "workflow_runs": "not an array"}, now=NOW)[
            "run_evidence_state"], "UNKNOWN_RUN_COLLECTION")

    def test_future_timestamp_fails_closed(self):
        self.classify([self.scheduled_run(-130)], "INVALID_FUTURE")

    def test_invalid_or_duplicate_metadata_fails_closed(self):
        duplicate = self.scheduled_run(60, 55)
        self.classify([duplicate, self.scheduled_run(200, 55)],
                      "INVALID_RUN_METADATA")
        for raw in ("not-a-time", "2026-10-17T09:00:00", None):
            row = self.scheduled_run(60)
            row["created_at"] = raw
            with self.subTest(raw=raw):
                self.classify([row], "INVALID_RUN_METADATA")
        invalid = self.scheduled_run(60)
        invalid["status"] = "UNKNOWN"
        self.classify([invalid], "INVALID_RUN_METADATA")

    def test_results_are_order_insensitive_and_no_job_ack(self):
        old = self.scheduled_run(1200, 1)
        new = self.scheduled_run(100, 2)
        out = self.classify([old, new], "RECENT_SUCCESS")
        self.assertEqual(out["latest_run_id"], 2)
        self.assertEqual(out["observed_inter_run_gap_seconds"], 1100)

    def test_untrusted_response_cannot_expand_github_scope(self):
        row = self.scheduled_run(10)
        row["workflow_id"] = 999
        self.classify([row], "NO_WATCH_SCHEDULE_RUNS_IN_SAMPLE")



class MiniPCDailyExactCountContract(unittest.TestCase):
    """Prevent the previously real Supabase 1000-row response truncation."""

    def test_original_real_bigger_than_1000_totals_are_not_capped(self):
        # PostgREST can use a header-only */N or a 0-M/N page range.
        # Only the denominator is the exact total; M is NOT the count.
        for header, expected in (
            ("0-0/24460", 24460), ("*/24460", 24460),
            ("0-999/24460", 24460), ("0-0/24014", 24014),
            ("*/24014", 24014), ("0-999/24014", 24014),
            ("0-0/1001", 1001), ("0-0/1", 1),
        ):
            with self.subTest(header=header):
                self.assertEqual(parse_postgrest_exact_count(header), expected)

    def test_genuine_empty_result_has_explicit_zero(self):
        self.assertEqual(parse_postgrest_exact_count("*/0"), 0)
        self.assertEqual(parse_postgrest_exact_count(" */0 "), 0)

    def test_unverifiable_or_invalid_range_never_silently_becomes_zero(self):
        for value in (
            None, "", "*/", "0-0/*", "0-0/0", "0-1000/1000",
            "1-1/24014", "0-24014/24014", "0-0/-1", "0-0/1.2",
            "0-0/abc", "0-0/1\nContent-Type: secret",
            1000, {}, "0-0/9223372036854775808",
        ):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    parse_postgrest_exact_count(value)

    def test_existing_daily_original_count_queries_are_head_only(self):
        from pathlib import Path
        script=(Path(__file__).resolve().parents[1] /
                ".github/workflows/minipc-daily-status.yml").read_text("utf-8")
        self.assertIn('def request_count(path):', script)
        self.assertIn('method="HEAD"', script)
        self.assertIn('"Prefer":"count=exact"', script)
        self.assertIn('"Range":"0-0"', script)
        self.assertIn('resp.headers.get("Content-Range")', script)
        self.assertEqual(script.count("=request_count("), 3)
        for old in (
            "len(shadow_count_rows or [])",
            "len(completed_rows or [])",
            "len(scanner_rows or [])",
        ):
            self.assertNotIn(old, script)
        for table in (
            "v2r4_shadow_evidence?select=event_id",
            "v2r4_shadow_evidence?select=event_id&outcome_payload=not.is.null",
            "scanner_detection_evidence?select=handoff_id&detected_at=gte.",
        ):
            self.assertIn(table, script)
        self.assertIn("cron: '0 8,9 * * *'", script)
        self.assertIn("      - 'tools/minipc_cloud_evidence.py'", script)
        self.assertIn('dry_run=event_name!="schedule"', script)
        self.assertIn('if dry_run:\n              raise SystemExit(0)', script)
        self.assertEqual(script.count("Slack response:"), 1)
        self.assertEqual(script.count('"/rest/v1/minipc_daily_status?'), 1)


if __name__ == "__main__":
    unittest.main()
