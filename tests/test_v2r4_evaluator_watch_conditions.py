import unittest

from paper_evaluator.evaluate import common_validate, fail_safe_normalize


class V2R4EvaluatorWatchConditionTests(unittest.TestCase):
    def base_wait(self):
        return {
            "decision": "WAIT",
            "setup_lane": "IGNITION",
            "summary": "synthetic",
            "reason_codes": ["TEST"],
            "missing_triggers": ["breakout confirmation"],
            "stop_eur": None,
            "ttl_minutes": 30,
            "expected_remaining_move_pct": None,
            "risk_reward_after_costs": None,
            "stage2_trigger_eur": None,
            "stage2_ttl_minutes": 0,
            "watch_conditions": [
                {"metric": "last_eur", "op": ">=", "value": 1.25},
                {"metric": "spread_pct", "op": "<=", "value": 0.35},
            ],
        }

    def test_wait_requires_machine_readable_conditions(self):
        d = self.base_wait()
        common_validate(d)

        d["watch_conditions"] = []
        with self.assertRaises(ValueError):
            common_validate(d)

    def test_wait_rejects_unsupported_metric(self):
        d = self.base_wait()
        d["watch_conditions"] = [{"metric": "free_text_news", "op": ">=", "value": 1}]
        with self.assertRaises(ValueError):
            common_validate(d)

    def test_non_wait_must_not_carry_watch_conditions(self):
        d = self.base_wait()
        d["decision"] = "REJECT"
        d["ttl_minutes"] = 0
        with self.assertRaises(ValueError):
            common_validate(d)

    def test_incomplete_buy_plan_fails_closed_to_reject(self):
        d = {
            "decision": "BUY_SCOUT",
            "setup_lane": "IGNITION",
            "summary": "synthetic",
            "reason_codes": [],
            "missing_triggers": [],
            "stop_eur": None,
            "ttl_minutes": 0,
            "expected_remaining_move_pct": 5.0,
            "risk_reward_after_costs": 2.0,
            "stage2_trigger_eur": None,
            "stage2_ttl_minutes": 0,
            "watch_conditions": [],
        }
        out = fail_safe_normalize(d, {"ask": 1.0})
        self.assertEqual(out["decision"], "REJECT")
        self.assertEqual(out["watch_conditions"], [])


if __name__ == "__main__":
    unittest.main()
