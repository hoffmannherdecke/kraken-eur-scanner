"""Regression contract for the existing Supabase paper model usage guard."""
from pathlib import Path
import unittest

SQL=(Path(__file__).resolve().parents[1] /
     "supabase/views/paper_model_usage_guard.sql").read_text()


class PaperModelUsageSinglePassContract(unittest.TestCase):
    def test_one_base_scan_preserves_invocation_semantics(self):
        self.assertEqual(SQL.count("from public.paper_candidate_outcomes p"), 1)
        self.assertIn("cross join lateral (values", SQL)
        self.assertIn("where v.phase = 'BASE' or v.response_id is not null", SQL)
        self.assertIn("count(distinct v.response_id)", SQL)
        self.assertIn("v.phase = 'INITIAL'", SQL)
        self.assertIn("v.phase = 'REVALIDATION'", SQL)
        self.assertIn("nullif(p.payload #>> '{decision,evaluator,response_id}', '')", SQL)
        self.assertIn("nullif(p.payload #>> '{revalidation,evaluator,response_id}', '')", SQL)

    def test_same_fail_closed_contract_and_no_write_or_budget_change(self):
        self.assertIn("with (security_invoker=true)", SQL)
        self.assertIn("'CALL_COUNT_ONLY_NO_TOKEN_OR_DOLLAR_DATA'", SQL)
        self.assertIn("false as automatic_budget_change_allowed", SQL)
        for condition in (
            "revalidation_without_initial_model > 0",
            "coalesce(max_attempt,0) > 2",
            "revalidation_model_calls > initial_wait_decisions",
            "logical_model_calls - distinct_response_ids > 0",
            "logical_model_calls > candidate_outcomes + initial_wait_decisions",
        ):
            self.assertIn(condition, SQL)
        self.assertEqual(SQL.count("then 'ANOMALY'"), 5)
        self.assertNotIn("security definer", SQL.lower())
        self.assertNotIn("update public.", SQL.lower())
        self.assertNotIn("delete from public.", SQL.lower())


if __name__ == "__main__":
    unittest.main()
