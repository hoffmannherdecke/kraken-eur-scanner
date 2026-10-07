#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "tools" / "v3_h3_shadow_common.py"
SPEC = importlib.util.spec_from_file_location("v3_h3_shadow_common_tested", P)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import common helper")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class H3ShadowCommonTests(unittest.TestCase):
    def test_routing_fail_closed_and_duplicate(self):
        self.assertEqual(M.route_shadow("XBT/EUR", "PASS", False), "EVALUATE_H3_SHADOW")
        self.assertEqual(
            M.route_shadow("AAVE/EUR", "PASS", False),
            "BASELINE_PASSTHROUGH_NONELIGIBLE_PAIR",
        )
        self.assertEqual(
            M.route_shadow("ETH/EUR", "MISSING_FAIL_CLOSED", False),
            "BASELINE_PASSTHROUGH_H3_CONTEXT_MISSING",
        )
        self.assertEqual(M.route_shadow("SOL/EUR", "PASS", True), "DUPLICATE_SKIPPED")

    def test_freshness_requires_point_in_time_order_and_2s_cap(self):
        t = datetime(2026, 10, 7, 20, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(
            M.context_is_fresh(
                source_exchange_at_utc=z(t),
                received_at_utc=z(t + timedelta(milliseconds=100)),
                evaluation_clock_utc=z(t + timedelta(milliseconds=500)),
            )
        )
        self.assertFalse(
            M.context_is_fresh(
                source_exchange_at_utc=z(t),
                received_at_utc=z(t + timedelta(milliseconds=100)),
                evaluation_clock_utc=z(t + timedelta(milliseconds=2100)),
            )
        )
        self.assertFalse(
            M.context_is_fresh(
                source_exchange_at_utc=z(t + timedelta(milliseconds=200)),
                received_at_utc=z(t + timedelta(milliseconds=100)),
                evaluation_clock_utc=z(t + timedelta(milliseconds=300)),
            )
        )

    def test_context_has_only_fixed_raw_features(self):
        c = M.compact_h3_context(
            pair="SOL/EUR",
            source_exchange_at_utc="2026-10-07T20:00:00Z",
            received_at_utc="2026-10-07T20:00:00.100000Z",
            spread_bps=1.2,
            bid_depth_quote_top10=10000,
            ask_depth_quote_top10=9000,
            depth_imbalance_top10=0.0526,
        )
        self.assertEqual(
            list(c["features"]),
            [
                "spread_bps",
                "bid_depth_quote_top10",
                "ask_depth_quote_top10",
                "depth_imbalance_top10",
            ],
        )
        self.assertTrue(c["checksum_valid"])
        self.assertEqual(c["depth"], 10)


if __name__ == "__main__":
    unittest.main()
