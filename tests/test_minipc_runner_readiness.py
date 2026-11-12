"""Offline tests for the existing CryptoSupport GitHub runner-state classifier."""
import unittest
from unittest.mock import patch
from tools.minipc_runner_guard.runner_readiness import (
    RUNNER_NAME, classify_runner_payload, query_runner_status,
)


class StatusTests(unittest.TestCase):
    def payload(self, status, busy):
        return {"runners": [{"name": RUNNER_NAME, "status": status, "busy": busy}]}

    def test_idle(self):
        self.assertEqual(classify_runner_payload(self.payload("online", False))["state"], "IDLE")

    def test_busy(self):
        self.assertEqual(classify_runner_payload(self.payload("online", True))["state"], "BUSY")

    def test_offline(self):
        self.assertEqual(classify_runner_payload(self.payload("offline", False))["state"], "OFFLINE")

    def test_offline_takes_precedence_even_if_busy_stale(self):
        self.assertEqual(classify_runner_payload(self.payload("offline", True))["state"], "OFFLINE")

    def test_never_guess_from_unavailable(self):
        for value in ({}, {"runners": []}, {"runners": [{"name": RUNNER_NAME, "status": "online", "busy": "false"}]},
                      {"runners": [{"name": RUNNER_NAME, "status": "online", "busy": False}] * 2}):
            self.assertEqual(classify_runner_payload(value)["state"], "UNAVAILABLE")

    def test_absent_auth_fails_closed_and_no_external_api_call(self):
        with patch("urllib.request.urlopen") as fetch:
            self.assertEqual(query_runner_status("")["state"], "UNAVAILABLE")
            fetch.assert_not_called()

    def test_no_token_in_failure_output(self):
        with patch("urllib.request.urlopen", side_effect=OSError("private auth error")):
            self.assertEqual(query_runner_status("fake-valid-looking-token"), {
                "state": "UNAVAILABLE", "online": None, "busy": None, "reason": "API_UNAVAILABLE"
            })


if __name__ == "__main__":
    unittest.main()
