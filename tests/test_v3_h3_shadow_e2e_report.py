#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
P = ROOT / "tools" / "v3-h3-shadow-e2e.py"
SPEC = importlib.util.spec_from_file_location("v3_h3_shadow_e2e_tested", P)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import H3 E2E")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class H3PhysicalReportValidationTests(unittest.TestCase):
    def test_zero_checksum_fail_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td)
            report = {
                "kind": "V3_H3_KRAKEN_SPOT_WS_BOOK_RECONCILIATION_SMOKE_V1",
                "status": "PASS",
                "totals": {"updates": 10, "checksum_pass": 12, "checksum_fail": 0},
                "interpretation": {"bounded_reconnect_resubscribe_proven": True},
            }
            p = logs / "v3-h3-ws-book-smoke-20261007-221153.json"
            p.write_text(json.dumps(report), "utf-8")
            selected, loaded = M.latest_physical_report(logs)
            self.assertEqual(selected, p)
            self.assertEqual(loaded["totals"]["checksum_fail"], 0)

    def test_missing_checksum_fail_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td)
            report = {
                "kind": "V3_H3_KRAKEN_SPOT_WS_BOOK_RECONCILIATION_SMOKE_V1",
                "status": "PASS",
                "totals": {"updates": 10, "checksum_pass": 12},
                "interpretation": {"bounded_reconnect_resubscribe_proven": True},
            }
            p = logs / "v3-h3-ws-book-smoke-20261007-221154.json"
            p.write_text(json.dumps(report), "utf-8")
            with self.assertRaises(RuntimeError):
                M.latest_physical_report(logs)


if __name__ == "__main__":
    unittest.main()
