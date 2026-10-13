"""No-network tests for cross-process Kraken public REST request budget."""
from __future__ import annotations

import json
import io
import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from market_data import kraken_public_budget as gate


URL = "https://api.kraken.com/0/public/Ticker?pair=XTZEUR"
OHLC = "https://api.kraken.com/0/public/OHLC?pair=XTZEUR&interval=15"


def _worker(root: str, send, ready, start):
    os.environ["KRAKEN_PUBLIC_BUDGET_DIR"] = root
    ready.put(True)
    if not start.wait(6):
        send.put("UNEXPECTED")
        return
    try:
        gate.reserve_public_request(URL)
        send.put("ADMITTED")
    except gate.KrakenPublicBudgetDeferred:
        send.put("DEFERRED")
    except Exception:
        send.put("UNEXPECTED")


class PublicKrakenBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"KRAKEN_PUBLIC_BUDGET_DIR": self.temp.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_without_opt_in_does_not_create_any_state(self):
        with patch.dict(os.environ, {"KRAKEN_PUBLIC_BUDGET_DIR": ""}):
            self.assertFalse(gate.reserve_public_request(URL))
            self.assertFalse(gate.report_public_rate_limit({"error": ["EGeneral:Too many requests"]}))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_first_claim_admitted_second_immediately_deferred(self):
        self.assertTrue(gate.reserve_public_request(URL))
        with self.assertRaises(gate.KrakenPublicBudgetDeferred):
            gate.reserve_public_request(OHLC, max_wait_seconds=0)
        data = json.loads((Path(self.temp.name) / "budget-state.json").read_text())
        self.assertGreater(data["last_claim_at"], 0)

    def test_shared_between_distinct_processes(self):
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        ready = ctx.Queue()
        start = ctx.Event()
        a = ctx.Process(target=_worker, args=(self.temp.name, q, ready, start))
        b = ctx.Process(target=_worker, args=(self.temp.name, q, ready, start))
        a.start()
        b.start()
        ready.get(timeout=6)
        ready.get(timeout=6)
        start.set()
        a.join(timeout=8)
        b.join(timeout=8)
        self.assertEqual((a.exitcode, b.exitcode), (0, 0))
        self.assertEqual(sorted([q.get(timeout=1), q.get(timeout=1)]), ["ADMITTED", "DEFERRED"])

    def test_rate_limit_sets_bounded_host_wide_cooldown(self):
        self.assertTrue(gate.reserve_public_request(URL))
        self.assertTrue(gate.report_public_rate_limit({"error": ["EGeneral:Too many requests"]}))
        current = json.loads((Path(self.temp.name) / "budget-state.json").read_text())
        self.assertLessEqual(current["cooldown_until"] - time.time(), 21)
        self.assertGreater(current["cooldown_until"] - time.time(), 17)
        with self.assertRaises(gate.KrakenPublicBudgetDeferred):
            gate.reserve_public_request(URL)
        self.assertFalse(gate.report_public_rate_limit({"error": []}))

    def test_invalid_state_refuses_request_no_reset(self):
        path = Path(self.temp.name) / "budget-state.json"
        path.write_text("{not-json", "utf-8")
        with self.assertRaises(gate.KrakenPublicBudgetUnsafe):
            gate.reserve_public_request(URL)
        self.assertEqual(path.read_text("utf-8"), "{not-json")

    def test_http_429_is_cooldown_even_without_kraken_error_body(self):
        self.assertTrue(gate.report_public_rate_limit(http_status=429))
        with self.assertRaises(gate.KrakenPublicBudgetDeferred):
            gate.reserve_public_request(URL)

    def test_nonpublic_url_fails_closed_when_enrolled(self):
        for url in ("http://api.kraken.com/0/public/Ticker", "https://api.kraken.com/0/private/Balance", "https://example.net/0/public/Ticker"):
            with self.subTest(url=url):
                with self.assertRaises(gate.KrakenPublicBudgetUnsafe):
                    gate.reserve_public_request(url)

    def test_maximum_wait_bounded(self):
        gate.reserve_public_request(URL)
        before = time.monotonic()
        with self.assertRaises(gate.KrakenPublicBudgetDeferred):
            gate.reserve_public_request(URL, max_wait_seconds=0.1)
        self.assertLess(time.monotonic() - before, 0.5)

    def test_expired_slot_can_be_reclaimed_without_network_call(self):
        path = Path(self.temp.name) / "budget-state.json"
        path.write_text(json.dumps({"last_claim_at": time.time() - 5,
                                    "cooldown_until": 0.0}), encoding="utf-8")
        self.assertTrue(gate.reserve_public_request(URL))

    def test_wait_http_path_reserves_slot_before_opening_network(self):
        from paper_evaluator import v2r4_wait_watcher as watcher

        gate.reserve_public_request(URL)
        with patch.object(watcher.urllib.request, "urlopen") as network:
            with self.assertRaises(gate.KrakenPublicBudgetDeferred):
                watcher.http_json(URL)
        network.assert_not_called()

    def test_wait_rest_limit_sets_shared_cooldown(self):
        from paper_evaluator import v2r4_wait_watcher as watcher

        response = io.BytesIO(b'{"error":["EGeneral:Too many requests"],"result":{}}')
        with patch.object(watcher.urllib.request, "urlopen", return_value=response) as network:
            data = watcher.http_json(OHLC)
            self.assertEqual(data["error"], ["EGeneral:Too many requests"])
            network.assert_called_once()
        with self.assertRaises(gate.KrakenPublicBudgetDeferred):
            gate.reserve_public_request(URL)

    def test_relative_enrollment_path_is_forbidden(self):
        with patch.dict(os.environ, {"KRAKEN_PUBLIC_BUDGET_DIR": "State/relative"}):
            with self.assertRaises(gate.KrakenPublicBudgetUnsafe):
                gate.reserve_public_request(URL)


if __name__ == "__main__":
    unittest.main()
