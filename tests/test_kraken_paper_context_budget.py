"""No-network proof that live PAPER evaluator/revalidator/context honor PR292.

The Kraken Spot public REST budget is opt-in and shared with WAIT, discovery
and Universe. Neither model calls nor non-Spot market context are rate-gated.
Nothing here starts Paper tasks or talks to Kraken/OpenAI.
"""
from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from market_data import kraken_public_budget as budget
from paper_evaluator import evaluate
import paper_context


TICKER = "https://api.kraken.com/0/public/Ticker?pair=XBTEUR"
OHLC = "https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=15"
ASSETPAIRS = "https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR"


class PaperSpotRestBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"KRAKEN_PUBLIC_BUDGET_DIR": self.temp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_evaluator_ticker_denied_before_network(self):
        self.assertTrue(budget.reserve_public_request(TICKER))
        with patch.object(evaluate.urllib.request, "urlopen") as network:
            with self.assertRaises(budget.KrakenPublicBudgetDeferred):
                evaluate.kraken_ticker("XBTEUR")
        network.assert_not_called()

    def test_revalidation_ohlc_reuses_evaluator_budget_path(self):
        # Production revalidate.py imports `http_json` from sibling evaluate.py.
        with patch.dict(sys.modules, {"evaluate": evaluate}):
            revalidate = importlib.import_module("paper_evaluator.revalidate")
        self.assertIs(revalidate.http_json, evaluate.http_json)
        self.assertTrue(budget.reserve_public_request(OHLC))
        with patch.object(evaluate.urllib.request, "urlopen") as network:
            with self.assertRaises(budget.KrakenPublicBudgetDeferred):
                revalidate.ohlc15("XBTEUR")
        network.assert_not_called()

    def test_context_ohlc_denied_before_network(self):
        self.assertTrue(budget.reserve_public_request(OHLC))
        with patch.object(paper_context.urllib.request, "urlopen") as network:
            with self.assertRaises(budget.KrakenPublicBudgetDeferred):
                paper_context._kraken_ohlc("XBTEUR")
        network.assert_not_called()

    def test_evaluator_ticker_blocks_context_assetpairs_same_ip_scope(self):
        self.assertTrue(budget.reserve_public_request(TICKER))
        with patch.object(paper_context.urllib.request, "urlopen") as network:
            with self.assertRaises(budget.KrakenPublicBudgetDeferred):
                paper_context._json(ASSETPAIRS)
        network.assert_not_called()

    def test_context_assetpairs_denial_remains_unavailable_not_fabricated(self):
        self.assertTrue(budget.reserve_public_request(TICKER))
        with patch.object(paper_context.urllib.request, "urlopen") as network:
            meta = paper_context.kraken_pair_metadata("XBTEUR")
        network.assert_not_called()
        self.assertIs(meta["available"], False)
        self.assertEqual(meta["error"], "KrakenPublicBudgetDeferred")

    def test_evaluator_http429_sets_shared_ip_cooldown(self):
        with patch.object(evaluate.urllib.request, "urlopen",
                          side_effect=urllib.error.HTTPError(TICKER, 429, "limit", {}, None)):
            with self.assertRaises(urllib.error.HTTPError):
                evaluate.http_json(TICKER)
        with self.assertRaises(budget.KrakenPublicBudgetDeferred):
            budget.reserve_public_request("https://api.kraken.com/0/public/AssetPairs")

    def test_context_payload_rate_error_sets_pair_cooldown(self):
        response = io.BytesIO(b'{"error":["EGeneral:Too many requests"],"result":{}}')
        with patch.object(paper_context.urllib.request, "urlopen", return_value=response):
            data = paper_context._json(OHLC)
        self.assertEqual(data["error"], ["EGeneral:Too many requests"])
        with self.assertRaises(budget.KrakenPublicBudgetDeferred):
            budget.reserve_public_request(OHLC)
        # Per-pair OHLC scope is independent from the ticker IP scope.
        self.assertTrue(budget.reserve_public_request(TICKER))

    def test_context_http429_sets_shared_pair_cooldown(self):
        with patch.object(paper_context.urllib.request, "urlopen",
                          side_effect=urllib.error.HTTPError(OHLC, 429, "limit", {}, None)):
            with self.assertRaises(urllib.error.HTTPError):
                paper_context._json(OHLC)
        with self.assertRaises(budget.KrakenPublicBudgetDeferred):
            budget.reserve_public_request(OHLC)

    def test_non_kraken_and_model_calls_never_consume_budget(self):
        self.assertTrue(budget.reserve_public_request(TICKER))
        response = b'{"ok":true}'
        futures = "https://futures.kraken.com/derivatives/api/v3/tickers"
        binance = "https://fapi.binance.com/fapi/v1/openInterest"
        openai = "https://api.openai.com/v1/responses"
        lookalike = "https://api.kraken.com.evil.example/0/public/Ticker"
        with patch.object(paper_context.urllib.request, "urlopen",
                          side_effect=lambda *a, **kw: io.BytesIO(response)) as network:
            self.assertTrue(paper_context._json(futures)["ok"])
            self.assertTrue(paper_context._json(binance)["ok"])
            self.assertTrue(evaluate.http_json(openai,method="POST",body=b"{}")["ok"])
            self.assertTrue(evaluate.http_json(lookalike)["ok"])
        self.assertEqual(network.call_count, 4)
        with self.assertRaises(budget.KrakenPublicBudgetDeferred):
            budget.reserve_public_request(TICKER)

    def test_rss_path_remains_outside_kraken_budget(self):
        self.assertTrue(budget.reserve_public_request(TICKER))
        with patch.object(paper_context.urllib.request, "urlopen",
                          return_value=io.BytesIO(b"<rss/>")):
            self.assertEqual(paper_context._text("https://www.sec.gov/feed"), "<rss/>")

    def test_unenrolled_evaluator_and_context_unchanged(self):
        with patch.dict(os.environ, {"KRAKEN_PUBLIC_BUDGET_DIR": ""}):
            with patch.object(paper_context.urllib.request, "urlopen",
                              side_effect=lambda *a, **kw: io.BytesIO(b'{"result":{}}')) as network:
                self.assertEqual(evaluate.http_json(TICKER), {"result": {}})
                self.assertEqual(paper_context._json(ASSETPAIRS), {"result": {}})
            self.assertEqual(network.call_count, 2)
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_corrupt_shared_state_is_hard_denial_without_network(self):
        (Path(self.temp.name) / "budget-state.json").write_text("not-json", encoding="utf-8")
        with patch.object(evaluate.urllib.request, "urlopen") as network:
            with self.assertRaises(budget.KrakenPublicBudgetUnsafe):
                evaluate.http_json(TICKER)
        network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
