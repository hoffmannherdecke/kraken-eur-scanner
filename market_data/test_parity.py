import copy
import unittest
from decimal import Decimal as D

from market_data.microstructure import Book, flow_metrics, wall_transitions
from market_data.parity import compare_assessment_paths, evaluation_basis
from market_data.runtime import (LIVE_EVALUATION_ENABLED, REAL_MONEY_ACTIONS_ENABLED,
                                 require_live_evaluation_disabled,
                                 require_real_money_actions_disabled)
from market_data.stream import subscription_payloads


def _book(bid=99.9, ask=100.1, bid_qty=10, ask_qty=10):
    result = Book()
    result.bids = {D(str(bid)): D(str(bid_qty))}
    result.asks = {D(str(ask)): D(str(ask_qty))}
    result.valid = True
    return result


def _fixture():
    events = [
        {"seq": 41, "exchange_at": "2026-09-26T06:00:00.100Z",
         "received_at": "2026-09-26T06:00:00.110Z", "channel": "book",
         "raw": '{"channel":"book","type":"snapshot","symbol":"RAY/EUR"}'},
        {"seq": 42, "exchange_at": "2026-09-26T06:00:00.200Z",
         "received_at": "2026-09-26T06:00:00.210Z", "channel": "trade",
         "raw": '{"channel":"trade","side":"buy","price":100.0,"qty":2}'},
    ]
    book = _book(bid_qty=12, ask_qty=10)
    trades = [{"monotonic_ns": 2_000_000_000, "side": "buy", "price": "100", "qty": "2"}]
    metrics = book.metrics()
    flow = {str(window) + "s": flow_metrics(trades, 2_000_000_000, window)
            for window in (15, 60, 300)}
    snapshot = {
        "symbol": "RAY/EUR", "exchange_at": "2026-09-26T06:00:00.200Z",
        "received_at": "2026-09-26T06:00:00.210Z", "seq": 43,
        "quality": "complete", "book": metrics, "flow": flow,
        "mid_return_60s_pct": 0.0, "wall_events": [],
    }
    return events, snapshot


class SharedMarketDataParityTests(unittest.TestCase):
    def test_recorded_tape_has_identical_shared_input_and_assessment(self):
        raw_events, snapshot = _fixture()
        report = compare_assessment_paths(raw_events, snapshot)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["raw_events"], raw_events)
        self.assertEqual(report["utc_timestamps_and_order"], [
            {"seq": event["seq"], "exchange_at": event["exchange_at"],
             "received_at": event["received_at"]} for event in raw_events])
        self.assertEqual(report["paper_input_sha256"], report["live_input_sha256"])
        self.assertEqual(report["paper_result"], report["live_path_result"])
        self.assertEqual(report["paper_result"]["microstructure_bias"], "supportive")
        self.assertIn("imbalance_top10", report["shared_input"]["book"])

    def test_report_records_assessment_divergence(self):
        raw_events, snapshot = _fixture()
        report = compare_assessment_paths(
            raw_events, snapshot,
            paper_assessor=lambda basis: {"result": "paper"},
            live_assessor=lambda basis: {"result": "live"})
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["deviations"], ["assessment_result"])
        self.assertEqual(report["paper_result"], {"result": "paper"})
        self.assertEqual(report["live_path_result"], {"result": "live"})

    def test_input_mutation_is_reported(self):
        raw_events, snapshot = _fixture()
        def mutating_assessor(basis):
            basis["book"]["bid"] = "changed"
            return {"ok": True}
        report = compare_assessment_paths(
            raw_events, snapshot, paper_assessor=mutating_assessor,
            live_assessor=lambda basis: {"ok": True})
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("paper_input_mutated", report["deviations"])
        self.assertEqual(report["live_path_result"], {"ok": True})

    def test_ambiguous_or_non_utc_order_is_rejected(self):
        raw_events, snapshot = _fixture()
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            compare_assessment_paths([raw_events[1], raw_events[0]], snapshot)
        bad = copy.deepcopy(snapshot)
        bad["exchange_at"] = "2026-09-26T08:00:00+02:00"
        with self.assertRaisesRegex(ValueError, "UTC"):
            evaluation_basis(bad)

    def test_runtime_gates_remain_off(self):
        self.assertFalse(LIVE_EVALUATION_ENABLED)
        self.assertFalse(REAL_MONEY_ACTIONS_ENABLED)
        require_live_evaluation_disabled()
        require_real_money_actions_disabled()

    def test_shared_book_wall_and_flow_functions_are_reusable(self):
        before = _book(99.9, 100.1, 10, 10).metrics()
        after = _book(99.9, 100.1, 15, 10).metrics()
        events = wall_transitions(before, after, 100.0, {}, 3_000_000_000)
        self.assertTrue(any(event["event"] == "build" for event in events))
        self.assertEqual(flow_metrics([
            {"monotonic_ns": 1_000_000_000, "side": "buy", "price": "100", "qty": "1"},
            {"monotonic_ns": 1_500_000_000, "side": "sell", "price": "100", "qty": "1"},
        ], 2_000_000_000, 15)["pressure"], 0.0)

    def test_shared_transport_builds_read_only_public_subscriptions(self):
        payloads = subscription_payloads(["RAY/EUR", "BTC/EUR", "RAY/EUR"])
        self.assertEqual([payload["params"]["channel"] for payload in payloads],
                         ["book", "trade"])
        self.assertEqual(payloads[0]["params"]["symbol"], ["BTC/EUR", "RAY/EUR"])
        self.assertEqual(payloads[0]["params"]["depth"], 25)
        self.assertTrue(all(payload["params"]["snapshot"] for payload in payloads))


if __name__ == "__main__":
    unittest.main()
