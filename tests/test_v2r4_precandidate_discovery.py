import unittest

from paper_evaluator.v2r4_precandidate_discovery import (
    FRESH_PAPER_RECHECK_ONLY,
    MICROSTRUCTURE_EXCEPTION_SHADOW,
    STANDARD_EXECUTION_GATE,
    WATCH_ONLY,
    assess_discovery,
    classify_liquidity,
    discovery_reasons,
)


class V2R4PreCandidateDiscoveryTests(unittest.TestCase):
    def test_slow_staircase_is_seen_even_if_one_hour_is_not_extreme(self):
        reasons = discovery_reasons({
            "ret10m": 0.2,
            "ret30m": 0.5,
            "ret1h": 1.0,
            "ret3h": 2.8,
            "ret6h": 5.1,
            "ret12h": 9.0,
            "ret_day_open": 6.0,
        })
        self.assertIn("PERSISTENT_6H", reasons)
        self.assertIn("STAIRCASE_6H", reasons)

    def test_liquidity_does_not_suppress_recognition(self):
        result = assess_discovery(
            returns={"ret1h": 3.4},
            turnover24h_eur=20_000,
            spread_pct=1.2,
        )
        self.assertTrue(result.triggered)
        self.assertEqual(result.liquidity_class, WATCH_ONLY)
        self.assertEqual(result.next_action, "NONE")

    def test_existing_standard_execution_gate_is_preserved(self):
        self.assertEqual(
            classify_liquidity(
                turnover24h_eur=160_000,
                spread_pct=0.9,
                depth_1pct_eur=None,
            ),
            STANDARD_EXECUTION_GATE,
        )

    def test_microstructure_exception_is_shadow_only_and_requires_depth(self):
        self.assertEqual(
            classify_liquidity(
                turnover24h_eur=80_000,
                spread_pct=0.40,
                depth_1pct_eur=5_000,
                intended_notional_eur=150,
            ),
            MICROSTRUCTURE_EXCEPTION_SHADOW,
        )
        self.assertEqual(
            classify_liquidity(
                turnover24h_eur=80_000,
                spread_pct=0.40,
                depth_1pct_eur=1_000,
                intended_notional_eur=150,
            ),
            WATCH_ONLY,
        )

    def test_trigger_plus_eligible_liquidity_requests_recheck_not_order(self):
        result = assess_discovery(
            returns={"ret3h": 4.5},
            turnover24h_eur=200_000,
            spread_pct=0.25,
        )
        self.assertTrue(result.triggered)
        self.assertEqual(result.next_action, FRESH_PAPER_RECHECK_ONLY)


if __name__ == "__main__":
    unittest.main()
