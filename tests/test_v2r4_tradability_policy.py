import inspect
import unittest

from paper_evaluator import evaluate


class V2R4TradabilityPolicyTests(unittest.TestCase):
    def test_no_static_pair_blacklist_remains(self):
        self.assertFalse(hasattr(evaluate, "BLOCKED"))
        source = inspect.getsource(evaluate.call_evaluator)
        self.assertNotIn("QNT/EUR", source)
        self.assertNotIn("DUSK/EUR", source)
        self.assertNotIn("TION/EUR", source)
        self.assertIn("Do not use any static pair blacklist", source)

    def test_public_online_pair_can_pass_without_private_account_tradability(self):
        decision = {
            "decision": "BUY_SCOUT",
            "setup_lane": "IGNITION",
            "summary": "synthetic",
            "reason_codes": [],
            "missing_triggers": [],
            "stop_eur": 0.9,
            "ttl_minutes": 0,
            "expected_remaining_move_pct": 5.0,
            "risk_reward_after_costs": 2.0,
            "stage2_trigger_eur": 1.1,
            "stage2_ttl_minutes": 30,
        }
        current = {"ask": 1.0}
        external = {
            "account_specific_tradability": {
                "available": False,
                "reason": "paper runtime has no private Kraken credential",
            },
            "kraken_pair_metadata": {
                "available": True,
                "status": "online",
                "ordermin": "1",
                "costmin": "0.45",
            },
        }
        spec = {
            "entry": {
                "scout_notional_eur": 75,
                "stage2_notional_eur": 75,
            }
        }
        out = evaluate.apply_public_tradability_gate(decision, current, external, spec)
        self.assertEqual(out["decision"], "BUY_SCOUT")


if __name__ == "__main__":
    unittest.main()
