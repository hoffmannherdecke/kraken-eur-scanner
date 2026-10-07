import unittest

from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan


CANDIDATE = {
    "candidate_id": "20260929-060000-TEST-EUR-r1",
    "pair": "TEST/EUR",
    "altname": "TESTEUR",
}


class V2R4TriggerPlanTests(unittest.TestCase):
    def test_wait_builds_machine_readable_plan(self):
        decision = {
            "decision": "WAIT",
            "ttl_minutes": 30,
            "watch_conditions": [
                {"metric": "last_eur", "op": ">=", "value": 1.25},
                {"metric": "spread_pct", "op": "<=", "value": 0.35},
            ],
        }
        plan = build_wait_trigger_plan(CANDIDATE, decision, "2026-09-29T06:00:00Z")
        self.assertEqual(plan["on_match"], "FRESH_PAPER_RECHECK_ONLY")
        self.assertTrue(plan["paper_only"])
        self.assertEqual(plan["expires_at_utc"], "2026-09-29T06:30:00Z")

    def test_non_wait_has_no_plan(self):
        decision = {"decision": "REJECT", "ttl_minutes": 0}
        self.assertIsNone(
            build_wait_trigger_plan(CANDIDATE, decision, "2026-09-29T06:00:00Z")
        )

    def test_free_text_only_wait_fails_closed(self):
        decision = {
            "decision": "WAIT",
            "ttl_minutes": 30,
            "missing_triggers": ["price must break resistance"],
        }
        with self.assertRaises(ValueError):
            build_wait_trigger_plan(CANDIDATE, decision, "2026-09-29T06:00:00Z")


if __name__ == "__main__":
    unittest.main()
