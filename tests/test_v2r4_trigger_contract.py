import unittest
from datetime import datetime, timezone

from paper_evaluator.v2r4_trigger_contract import evaluate_plan, validate_plan


def base_plan():
    return {
        "schema_version": 1,
        "candidate_id": "20260928-183801-CRV-EUR-r36466362150",
        "pair": "CRV/EUR",
        "altname": "CRVEUR",
        "created_at_utc": "2026-09-29T06:00:00Z",
        "expires_at_utc": "2026-09-29T06:45:00Z",
        "logic": "ALL",
        "conditions": [
            {"metric": "closed_1m_close_eur", "op": ">=", "value": 0.32281},
            {"metric": "spread_pct", "op": "<=", "value": 0.35},
        ],
        "on_match": "FRESH_PAPER_RECHECK_ONLY",
        "paper_only": True,
    }


class V2R4TriggerContractTests(unittest.TestCase):
    def test_match_requests_recheck_not_order(self):
        plan = base_plan()
        result = evaluate_plan(
            plan,
            {"closed_1m_close_eur": 0.3231, "spread_pct": 0.12},
            now=datetime(2026, 9, 29, 6, 10, tzinfo=timezone.utc),
        )
        self.assertTrue(result.matched)
        self.assertFalse(result.expired)
        self.assertEqual(result.reason, "MATCH_REQUIRES_FRESH_PAPER_RECHECK")

    def test_missing_metric_fails_closed(self):
        plan = base_plan()
        result = evaluate_plan(
            plan,
            {"spread_pct": 0.12},
            now=datetime(2026, 9, 29, 6, 10, tzinfo=timezone.utc),
        )
        self.assertFalse(result.matched)
        self.assertEqual(result.reason, "MISSING_METRIC:closed_1m_close_eur")

    def test_expired_never_matches(self):
        plan = base_plan()
        result = evaluate_plan(
            plan,
            {"closed_1m_close_eur": 0.33, "spread_pct": 0.1},
            now=datetime(2026, 9, 29, 6, 46, tzinfo=timezone.utc),
        )
        self.assertFalse(result.matched)
        self.assertTrue(result.expired)

    def test_non_paper_action_rejected(self):
        plan = base_plan()
        plan["paper_only"] = False
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_ttl_over_one_hour_rejected(self):
        plan = base_plan()
        plan["expires_at_utc"] = "2026-09-29T07:01:00Z"
        with self.assertRaises(ValueError):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
