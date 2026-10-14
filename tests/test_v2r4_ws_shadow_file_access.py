"""Bounded Windows access contention: no silent state reset or trading changes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v2r4_ws_shadow_watcher as ws


class BoundedFileAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_snapshot_read_recovers_from_two_temporary_permission_errors(self):
        p = self.root / "snapshot.json"
        p.write_text('{"test":12}', encoding="utf-8")
        actual = Path.read_text
        calls = []
        def flaky(obj, *args, **kwargs):
            calls.append(str(obj))
            if len(calls) <= 2:
                raise PermissionError(13, "Windows sharing access denied", str(obj))
            return actual(obj, *args, **kwargs)
        with patch.object(Path, "read_text", flaky), patch.object(ws.time, "sleep") as sleep:
            self.assertEqual(ws.load_json(p), {"test": 12})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_heartbeat_replace_recovers_without_partial_json(self):
        p = self.root / "heartbeat.json"
        p.write_text('{"old":true}', encoding="utf-8")
        actual = Path.replace
        calls = []
        def flaky(obj, target):
            calls.append(str(obj))
            if len(calls) <= 2:
                self.assertEqual(json.loads(p.read_text("utf-8")), {"old": True})
                raise PermissionError(13, "Windows target temporarily in use", str(target))
            return actual(obj, target)
        with patch.object(Path, "replace", flaky), patch.object(ws.time, "sleep") as sleep:
            ws.atomic_json(p, {"new": True})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(json.loads(p.read_text("utf-8")), {"new": True})

    def test_permanent_read_permission_error_raises_instead_of_resetting_state(self):
        p = self.root / "state.json"
        p.write_text('{"schema_version":1,"pairs":{"TEST/EUR":{}}}', encoding="utf-8")
        def inaccessible(obj, *args, **kwargs):
            raise PermissionError(13, "blocked by ACL", str(obj))
        with patch.object(Path, "read_text", inaccessible), patch.object(ws.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                ws.load_state(p)
        self.assertEqual(sleep.call_count, len(ws.WINDOWS_ACCESS_RETRY_DELAYS))

    def test_permanent_atomic_replace_does_not_claim_success(self):
        p = self.root / "heartbeat.json"
        p.write_text('{"old":true}', encoding="utf-8")
        def denied(obj, target):
            raise PermissionError(13, "persistent Windows lock", str(target))
        with patch.object(Path, "replace", denied), patch.object(ws.time, "sleep") as sleep:
            with self.assertRaises(PermissionError):
                ws.atomic_json(p, {"new": True})
        self.assertEqual(sleep.call_count, len(ws.WINDOWS_ACCESS_RETRY_DELAYS))
        self.assertEqual(json.loads(p.read_text("utf-8")), {"old": True})

    def test_json_corruption_is_not_misclassified_as_permission_error(self):
        p = self.root / "snapshot.json"
        p.write_text('{"bad":', encoding="utf-8")
        with patch.object(ws.time, "sleep") as sleep:
            with self.assertRaises(json.JSONDecodeError):
                ws.load_json(p)
        sleep.assert_not_called()

    def test_missing_snapshot_is_not_retried(self):
        p = self.root / "missing.json"
        with patch.object(ws.time, "sleep") as sleep:
            with self.assertRaises(FileNotFoundError):
                ws.load_json(p)
        sleep.assert_not_called()

    def test_single_retry_lifetime_bounded(self):
        self.assertLessEqual(sum(ws.WINDOWS_ACCESS_RETRY_DELAYS), 0.6)
        self.assertGreater(len(ws.WINDOWS_ACCESS_RETRY_DELAYS), 0)


if __name__ == "__main__":
    unittest.main()
