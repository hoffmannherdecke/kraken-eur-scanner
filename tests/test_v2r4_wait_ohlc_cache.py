"""Offline regression tests for bounded public Kraken closed-OHLC reuse.

No network, disk cache, live task, model call or paper release is performed.
"""
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from paper_evaluator import v2r4_wait_watcher as watcher


def fake_kraken_response(url):
    if "/Ticker?" in url:
        return {
            "error": [],
            "result": {"XTZEUR": {"b": ["99"], "a": ["101"], "c": ["100"]}},
        }
    if "/OHLC?" in url:
        interval = int(parse_qs(urlparse(url).query)["interval"][0])
        seconds = interval * 60
        bucket = int(watcher.time.time() // seconds)
        return {
            "error": [],
            "result": {
                "XTZEUR": [
                    [(bucket - 1) * seconds, "1", "2", "1", str(100 + interval), "0", "10"],
                    [bucket * seconds, "1", "2", "1", str(200 + interval), "0", "11"],
                ],
                "last": 2000,
            },
        }
    raise AssertionError("unexpected endpoint")


class ClosedOhlcReuseTests(unittest.TestCase):
    def setUp(self):
        watcher._CLOSED_OHLC_CACHE.clear()

    def tearDown(self):
        watcher._CLOSED_OHLC_CACHE.clear()

    def test_every_wait_snapshot_has_fresh_ticker_and_all_original_metrics(self):
        t0 = 900 * 1000 + 10
        with patch.object(watcher.time, "time", return_value=t0), patch.object(
            watcher, "http_json", side_effect=fake_kraken_response
        ) as api:
            first = watcher.market_metrics("XTZEUR")
            second = watcher.market_metrics("XTZEUR")
        self.assertEqual(first, second)
        self.assertEqual(first["last_eur"], 100.0)
        for interval in ("1m", "5m", "15m"):
            self.assertIn("closed_" + interval + "_close_eur", first)
        urls = [c.args[0] for c in api.call_args_list]
        self.assertEqual(sum("/Ticker?" in u for u in urls), 2)
        self.assertEqual(sum("/OHLC?" in u for u in urls), 3)

    def test_exact_utc_boundaries_refresh_each_interval_only_when_due(self):
        base = 900 * 1000 + 10
        with patch.object(watcher.time, "time", return_value=base) as clock, patch.object(
            watcher, "http_json", side_effect=fake_kraken_response
        ) as api:
            watcher.market_metrics("XTZEUR")
            clock.return_value = base + 61
            watcher.market_metrics("XTZEUR")
            clock.return_value = base + 301
            watcher.market_metrics("XTZEUR")
            clock.return_value = base + 901
            watcher.market_metrics("XTZEUR")
        urls = [c.args[0] for c in api.call_args_list]
        self.assertEqual(sum("/Ticker?" in u for u in urls), 4)
        self.assertEqual(sum("interval=1" in u and "interval=15" not in u for u in urls), 4)
        self.assertEqual(sum("interval=5" in u for u in urls), 3)
        self.assertEqual(sum("interval=15" in u for u in urls), 2)

    def test_error_after_boundary_fails_closed_and_never_reuses_stale(self):
        with patch.object(watcher.time, "time", return_value=900010) as clock, patch.object(
            watcher, "http_json", side_effect=[
                fake_kraken_response("https://api.kraken.com/0/public/OHLC?pair=XTZEUR&interval=15"),
                {"error": ["EGeneral:Too many requests"], "result": {}},
                fake_kraken_response("https://api.kraken.com/0/public/OHLC?pair=XTZEUR&interval=15"),
            ]
        ) as api:
            first = watcher.closed_ohlc("XTZEUR", 15)
            self.assertTrue(first)
            clock.return_value = 900910
            with self.assertRaisesRegex(RuntimeError, "Too many requests"):
                watcher.closed_ohlc("XTZEUR", 15)
            self.assertEqual(len(watcher._CLOSED_OHLC_CACHE), 0)
            recovered = watcher.closed_ohlc("XTZEUR", 15)
        self.assertEqual(first, recovered)
        self.assertEqual(api.call_count, 3)

    def test_delayed_new_candle_is_not_pinned_for_whole_interval(self):
        now = 900010
        seconds = 15 * 60
        bucket = now // seconds
        # A cold Kraken response still carries the preceding (now closed)
        # bar as its last/current row, before the new live candle appears.
        stale = {
            "error": [],
            "result": {
                "XTZEUR": [
                    [(bucket - 2) * seconds, 1, 2, 1, 98, 0, 10],
                    [(bucket - 1) * seconds, 1, 2, 1, 99, 0, 11],
                ],
                "last": 0,
            },
        }
        with patch.object(watcher.time, "time", return_value=now), patch.object(
            watcher, "http_json", side_effect=[
                stale,
                fake_kraken_response("https://api.kraken.com/0/public/OHLC?pair=XTZEUR&interval=15"),
            ]
        ) as api:
            old_rows = watcher.closed_ohlc("XTZEUR", 15)
            self.assertEqual(len(watcher._CLOSED_OHLC_CACHE), 0)
            new_rows = watcher.closed_ohlc("XTZEUR", 15)
            self.assertNotEqual(old_rows[-1][0], new_rows[-1][0])
            self.assertEqual(api.call_count, 2)
            watcher.closed_ohlc("XTZEUR", 15)
            self.assertEqual(api.call_count, 2)

    def test_network_response_crossing_utc_boundary_is_not_cached(self):
        with patch.object(watcher.time, "time", return_value=900010) as clock:
            def delayed_response(url):
                clock.return_value = 900910
                return fake_kraken_response(url)
            with patch.object(watcher, "http_json", side_effect=delayed_response) as api:
                watcher.closed_ohlc("XTZEUR", 15)
                self.assertEqual(len(watcher._CLOSED_OHLC_CACHE), 0)
                watcher.closed_ohlc("XTZEUR", 15)
                self.assertEqual(api.call_count, 2)

    def test_missing_closed_candles_are_never_cached(self):
        empty = {"error": [], "result": {"XTZEUR": [[2000, 0, 0, 0, 0, 0, 0]], "last": 2000}}
        with patch.object(watcher.time, "time", return_value=900010), patch.object(
            watcher, "http_json", return_value=empty
        ) as api:
            self.assertEqual(watcher.closed_ohlc("XTZEUR", 5), [])
            self.assertEqual(watcher.closed_ohlc("XTZEUR", 5), [])
        self.assertEqual(api.call_count, 2)

    def test_cache_key_is_per_pair_and_interval_and_lru_is_bounded(self):
        with patch.object(watcher.time, "time", return_value=900010), patch.object(
            watcher, "http_json", side_effect=fake_kraken_response
        ) as api:
            watcher.closed_ohlc("XTZEUR", 1)
            watcher.closed_ohlc("XTZEUR", 5)
            for idx in range(watcher._CLOSED_OHLC_CACHE_MAX + 1):
                watcher.closed_ohlc("PAIR" + str(idx), 15)
        self.assertEqual(len(watcher._CLOSED_OHLC_CACHE), watcher._CLOSED_OHLC_CACHE_MAX)
        self.assertNotIn(("XTZEUR", 1), watcher._CLOSED_OHLC_CACHE)
        self.assertNotIn(("XTZEUR", 5), watcher._CLOSED_OHLC_CACHE)
        self.assertEqual(api.call_count, watcher._CLOSED_OHLC_CACHE_MAX + 3)

    def test_unsupported_interval_fails_before_http(self):
        with patch.object(watcher, "http_json") as api:
            with self.assertRaisesRegex(ValueError, "unsupported"):
                watcher.closed_ohlc("XTZEUR", 2)
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
