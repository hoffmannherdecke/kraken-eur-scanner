"""Regression: V2R4's normal Candidates and WAIT model adapter is zero-cost."""
import os
import unittest
from unittest.mock import patch

from paper_evaluator import evaluate


class V2R4NoPaidAPIRegression(unittest.TestCase):
    def test_default_never_uses_openai_even_with_key_present(self):
        for env in ({}, {"OPENAI_API_KEY": "sk-test-not-real",
                         "OPENAI_MODEL": "gpt-6-luna",
                         "OPENAI_PAID_MODEL_ENABLED": "true"}):
            with self.subTest(env=bool(env)):
                with patch.dict(os.environ, env, clear=True):
                    with patch.object(evaluate, "http_json",
                                      side_effect=AssertionError("paid network attempted")):
                        decision, meta = evaluate.call_evaluator(
                            {"pair": "BTC/EUR"}, {"ask": 50000},
                            {}, {"strategy_revision": "V2R4"},
                            {"series_id": "PAPER-V2R4-test"})
                self.assertEqual(decision["decision"], "REJECT")
                self.assertEqual(decision["watch_conditions"], [])
                self.assertIsNone(decision["stop_eur"])
                self.assertIsNone(decision["stage2_trigger_eur"])
                self.assertIn("PAID_MODEL_DISABLED", decision["reason_codes"][0])
                self.assertIsNone(meta["response_id"])
                self.assertEqual(meta["attempt"], 0)

    def test_historical_paid_evaluator_is_not_an_escape_hatch(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-not-real"}):
            with patch.object(evaluate, "http_json",
                              side_effect=AssertionError("paid network attempted")):
                with self.assertRaisesRegex(RuntimeError, "PAID_MODEL_RETIRED"):
                    evaluate._retired_paid_model_evaluator({}, {}, {}, {}, {})


if __name__ == "__main__":
    unittest.main()
