"""Offline tests of the ACTUAL existing MINI-PC cloud alert script (not a copy).

Supabase, Slack and wall-clock sources are simulated. This does not change
alert policy or establish a real host/outage/recovery health proof.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import re
import textwrap
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / ".github/workflows/minipc-cloud-health-watch.yml"


def watch_source():
    match = re.search(
        r"(?ms)^\s*python - <<'PY'\s*\n(?P<code>.*?)^\s*PY\s*$",
        WATCH.read_text(encoding="utf-8"),
    )
    if not match:
        raise AssertionError("Original inline watch code missing: re-review required")
    return textwrap.dedent(match.group("code"))


class Response:
    status = 200

    def __init__(self, value):
        self.payload = b"" if value is None else json.dumps(value).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class CloudWatchContract(unittest.TestCase):
    @staticmethod
    def row(status="HEALTHY", minutes_ago=2):
        when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
        return {"node_id": "MINI-PC", "observed_at": when.isoformat(), "status": status}

    def execute_existing_code(self, row=None, previous="OK", last_alert=None):
        logs = io.StringIO()
        slack = []
        writes = []

        def network(request, timeout=None):
            url = request.full_url
            method = request.get_method()
            if method == "GET" and "minipc_status_current?" in url:
                return Response([] if row is None else [row])
            if method == "GET" and "minipc_status_alert_state?" in url:
                return Response([{
                    "node_id": "MINI-PC", "last_condition": previous,
                    "last_alert_at": last_alert, "last_recovery_at": None,
                }])
            if method == "POST" and "minipc_status_alert_state?" in url:
                writes.extend(json.loads(request.data))
                return Response(None)
            if method == "POST" and url == "https://slack.invalid/hook":
                slack.append(json.loads(request.data)["text"])
                return Response("ok")
            raise AssertionError("Unexpected network call: " + method)

        env = {
            "SUPABASE_URL": "https://db.invalid",
            "SUPABASE_SECRET_KEY": "test-only-no-real-credential",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SLACK_WEBHOOK_URL": "https://slack.invalid/hook",
            "SLACK_USER_ID": "FAKE_USER",
        }
        exit_code = None
        with patch.dict(os.environ, env), patch(
            "urllib.request.urlopen", side_effect=network
        ), contextlib.redirect_stdout(logs):
            try:
                exec(compile(watch_source(), str(WATCH), "exec"), {"__name__": "__main__"})
            except SystemExit as error:
                exit_code = error.code

        reports = [json.loads(s) for s in logs.getvalue().splitlines() if s.startswith("{")]
        return {"reports": reports, "log": logs.getvalue(), "slack": slack,
                "writes": writes, "exit": exit_code}

    def test_fresh_healthy_is_quiet(self):
        x = self.execute_existing_code(self.row())
        self.assertEqual(x["reports"][-1]["condition"], "OK")
        self.assertEqual(x["reports"][-1]["status"], "HEALTHY")
        self.assertEqual(x["slack"], [])
        self.assertEqual(x["writes"][-1]["last_condition"], "OK")

    def test_missing_source_does_not_claim_health(self):
        x = self.execute_existing_code()
        self.assertEqual(x["exit"], 0)
        self.assertIn("MINIPC_STATUS_NOT_ACTIVATED", x["log"])
        self.assertEqual(x["reports"], [])
        self.assertEqual(x["slack"], [])
        self.assertEqual(x["writes"], [])

    def test_stale_source_alerts(self):
        x = self.execute_existing_code(self.row(minutes_ago=25))
        self.assertEqual(x["reports"][-1]["condition"], "STALE")
        self.assertEqual(len(x["slack"]), 1)

    def test_critical_source_alerts(self):
        x = self.execute_existing_code(self.row(status="CRITICAL"))
        self.assertEqual(x["reports"][-1]["condition"], "CRITICAL")
        self.assertEqual(len(x["slack"]), 1)

    def test_repeated_critical_is_suppressed_for_two_hours(self):
        prev = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)).isoformat()
        x = self.execute_existing_code(self.row(status="CRITICAL"),
                                       previous="CRITICAL", last_alert=prev)
        self.assertEqual(x["reports"][-1]["condition"], "CRITICAL")
        self.assertEqual(x["slack"], [])

    def test_recovery_from_stale_after_healthy_status(self):
        x = self.execute_existing_code(self.row(), previous="STALE")
        self.assertEqual(x["reports"][-1]["condition"], "OK")
        self.assertEqual(len(x["slack"]), 1)
        self.assertIn("wieder erreichbar", x["slack"][0])
        self.assertIsNotNone(x["writes"][-1]["last_recovery_at"])

    def test_known_warning_gap_alert_ok_is_not_host_health(self):
        x = self.execute_existing_code(self.row(status="WARNING"))
        self.assertEqual(x["reports"][-1]["status"], "WARNING")
        self.assertEqual(x["reports"][-1]["condition"], "OK")
        self.assertEqual(x["slack"], [])
        # CHARACTERIZATION ONLY: never present this alert OK as HEALTHY.

    def test_known_future_timestamp_gap_alert_ok_is_not_host_health(self):
        x = self.execute_existing_code(self.row(minutes_ago=-3))
        self.assertLess(x["reports"][-1]["age_minutes"], -2)
        self.assertEqual(x["reports"][-1]["condition"], "OK")
        # CHARACTERIZATION ONLY: future proof remains invalid.

    def test_warning_recovery_is_only_reachability(self):
        x = self.execute_existing_code(self.row(status="WARNING"), previous="CRITICAL")
        self.assertEqual(len(x["slack"]), 1)
        self.assertIn("wieder erreichbar: WARNING", x["slack"][0])


if __name__ == "__main__":
    unittest.main()
