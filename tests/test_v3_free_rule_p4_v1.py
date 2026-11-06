"""V3 zero-cost primary assessor meets same P4 contract as the model branch."""
import unittest
from unittest.mock import patch

from tests.test_rule_based_paper_decision_v1 import fixture, iso
from paper_evaluator.v3_full_entry_decision_candidate_v1 import (
    validate_free_rule_based_entry, SECOND_LEG_ELIGIBLE_KIND,
    SECOND_LEG_P1_CHECKS,
)


class V3FreeRuleP4Tests(unittest.TestCase):
    def test_closed_candle_continuation_p4_without_paid_model(self):
        candidate, quote, context, _spec, _control = fixture()
        evidence = context["candidate_entry_evidence"]
        pair = candidate["pair"]
        ticker = dict(quote, pair=pair, observed_at_utc=iso(-2))
        metadata = dict(context["kraken_pair_metadata"], pair=pair, spot=True,
                        quote="EUR", minimum_order_passed=True,
                        observed_at_utc=iso(-3))
        eligibility = {
            "kind": SECOND_LEG_ELIGIBLE_KIND,
            "status": "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY",
            "request_model_recheck_only": True,
            "source_candidate_id": candidate["candidate_id"], "pair": pair,
            "original_candidate_historical_only": True,
            "new_snapshot_known_at_utc": evidence["known_at_utc"],
            "base_15m_bars": 4, "approval_to_call_model": False,
            "checks": {key: True for key in SECOND_LEG_P1_CHECKS},
        }
        with patch("paper_evaluator.evaluate.http_json",
                   side_effect=AssertionError("model transport must remain unused")):
            result = validate_free_rule_based_entry(
                eligibility, candidate, evidence, ticker, metadata,
                decision_at_utc=iso(0))
        self.assertTrue(result["rule_based_primary"])
        self.assertEqual(result["model_http_requests"], 0)
        self.assertFalse(result["model_called"])
        self.assertFalse(result["paper_writer_started"])
        self.assertFalse(result["release_evidence"])
        self.assertEqual(result["decision"], "BUY_SCOUT")
        self.assertEqual(result["status"],
                         "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")

    def test_missing_or_forward_known_evidence_fails_closed(self):
        candidate, quote, context, _spec, _control = fixture()
        evidence = dict(context["candidate_entry_evidence"], known_at_utc=iso(10))
        eligibility = {"status": "INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY",
                       "request_model_recheck_only": True}
        ticker = dict(quote, pair=candidate["pair"], observed_at_utc=iso(-2))
        metadata = dict(context["kraken_pair_metadata"], pair=candidate["pair"],
                        status="online", spot=True, quote="EUR",
                        minimum_order_passed=True, observed_at_utc=iso(-3))
        r = validate_free_rule_based_entry(
            eligibility, candidate, evidence, ticker, metadata,
            decision_at_utc=iso(0))
        self.assertNotEqual(r["decision"], "BUY_SCOUT")
        self.assertEqual(r["model_http_requests"], 0)


if __name__ == "__main__":
    unittest.main()
