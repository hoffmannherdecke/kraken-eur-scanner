import json
import os
import unittest
from unittest.mock import patch

from paper_evaluator import evaluate


def base_wait():
    return {
        "decision": "WAIT",
        "setup_lane": "IGNITION",
        "summary": "synthetic",
        "reason_codes": ["SYNTHETIC"],
        "missing_triggers": ["break and hold"],
        "watch_conditions": [
            {"metric": "last_eur", "op": ">=", "value": 1.01},
            {"metric": "spread_pct", "op": "<=", "value": 0.35},
        ],
        "stop_eur": None,
        "ttl_minutes": 30,
        "expected_remaining_move_pct": None,
        "risk_reward_after_costs": None,
        "stage2_trigger_eur": None,
        "stage2_ttl_minutes": 0,
    }


class V2R4EvaluatorContractTests(unittest.TestCase):
    def test_structured_wait_is_accepted(self):
        d = base_wait()
        evaluate.common_validate(d)

    def test_free_text_only_wait_is_rejected(self):
        d = base_wait()
        d["watch_conditions"] = []
        with self.assertRaises(ValueError):
            evaluate.common_validate(d)

    def test_non_wait_cannot_carry_watch_conditions(self):
        d = base_wait()
        d["decision"] = "REJECT"
        d["ttl_minutes"] = 0
        with self.assertRaises(ValueError):
            evaluate.common_validate(d)

    def test_prompt_renders_structured_watch_condition_schema(self):
        fake_decision = {
            "decision": "REJECT",
            "setup_lane": "NONE",
            "summary": "synthetic",
            "reason_codes": ["SYNTHETIC"],
            "missing_triggers": [],
            "watch_conditions": [],
            "stop_eur": None,
            "ttl_minutes": 0,
            "expected_remaining_move_pct": None,
            "risk_reward_after_costs": None,
            "stage2_trigger_eur": None,
            "stage2_ttl_minutes": 0,
        }
        response = {
            "id": "resp_test",
            "model": "test-model",
            "output": [{"content": [{"type": "output_text", "text": json.dumps(fake_decision)}]}],
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            with patch("paper_evaluator.evaluate.http_json", return_value=response):
                out, meta = evaluate.call_evaluator(
                    {"pair": "BTC/EUR", "altname": "XBTEUR"},
                    {"bid": 1.0, "ask": 1.01, "last": 1.0, "spread_pct": 0.1},
                    {},
                    {"strategy_revision": "V2R4-TEST"},
                    {"series_id": "PAPER-V2R4-TEST"},
                )
        self.assertEqual(out["decision"], "REJECT")
        self.assertEqual(meta["response_id"], "resp_test")

    def test_fail_safe_buy_with_invalid_stage2_is_rejected_not_wait(self):
        d = {
            "decision": "BUY_SCOUT",
            "setup_lane": "IGNITION",
            "summary": "synthetic",
            "reason_codes": [],
            "missing_triggers": [],
            "watch_conditions": [],
            "stop_eur": 0.99,
            "ttl_minutes": 0,
            "expected_remaining_move_pct": 5.0,
            "risk_reward_after_costs": 2.0,
            "stage2_trigger_eur": None,
            "stage2_ttl_minutes": 0,
        }
        out = evaluate.fail_safe_normalize(d, {"ask": 1.0, "spread_pct": 0.1})
        self.assertEqual(out["decision"], "REJECT")
        self.assertEqual(out["watch_conditions"], [])
        self.assertIn("INVALID_OR_MISSING_TWO_STAGE_PLAN", out["reason_codes"])


if __name__ == "__main__":
    unittest.main()
