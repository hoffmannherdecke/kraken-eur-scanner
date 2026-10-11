"""Fully offline future P3/P4 diagnostics contract; no run, model, Kraken, writer."""
import copy
import math
import unittest
from unittest.mock import patch

from paper_evaluator.v3_p3_future_diagnostics_offline_v1 import (
    KIND, phase_failure, review_diagnostic, full_review_receipt,
)
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    KIND as S_KIND, ELIGIBLE as S_ELIGIBLE,
)
from paper_evaluator.v3_experimental_continuity_volume_review_v1 import (
    KIND as E_KIND, ELIGIBLE as E_ELIGIBLE,
    EXPECTED_STANDARD_CHECKS,
)
from tests.test_v3_experimental_continuity_volume_review_v1 import compare


def receipt_args():
    return {
        "entry_known_at_utc": "2026-10-11T10:00:00Z",
        "execution_ticker_at_utc": "2026-10-11T10:00:10Z",
        "assetpairs_at_utc": "2026-10-11T10:00:11Z",
        "eligibility_at_utc": "2026-10-11T10:00:12Z",
        "model_request_at_utc": "2026-10-11T10:00:14Z",
        "model_response_at_utc": "2026-10-11T10:00:17Z",
        "p4_completed_at_utc": "2026-10-11T10:00:18Z",
        "model_response_id": "resp_test12345678",
        "model_decision": "WAIT",
        "p4_result": {
            "kind": "V3_B_INACTIVE_FULL_ENTRY_DECISION_V1",
            "status": "FULL_WAIT_VALIDATED_OFFLINE", "decision": "WAIT",
            "orders": False, "real_money_actions": False,
            "paper_writer_started": False, "release_evidence": False,
            "economic_edge_proven": False,
            "ttl_minutes": 20,
            "watch_conditions": [
                {"metric": "closed_5m_volume_ratio_5", "op": ">=", "value": 1.5},
                {"metric": "ask_eur", "op": "<=", "value": 12.5},
            ],
        },
    }


class V3P3FutureDiagnosticsOfflineTests(unittest.TestCase):
    def test_same_clock_standard_pass_proven_with_all_eight_gates(self):
        s,e,_=compare(1.2)
        out=review_diagnostic(s,e)
        self.assertEqual(out["kind"], KIND)
        self.assertEqual(out["status"], "STANDARD_REVIEW_ONLY")
        self.assertEqual(out["failed_standard_hard_check_names"],[])
        self.assertTrue(out["standard_hard_checks_present"])
        self.assertEqual(out["helper_model_calls"],0)
        self.assertFalse(out["new_model_permission"])

    def test_one_change_extra_is_separate_review_not_buy(self):
        s,e,_=compare(1.1)
        out=review_diagnostic(s,e)
        self.assertEqual(out["status"],"EXPERIMENTAL_INCREMENTAL_REVIEW_ONLY")
        self.assertEqual(out["failed_standard_hard_check_names"],
                         ["unchanged_closed_5m_volume_floor"])
        self.assertTrue(out["no_automatic_buy"])
        self.assertFalse(out["paper_changed"])

    def test_insufficient_volume_no_review_with_explicit_failed_check(self):
        s,e,_=compare(0.5)
        out=review_diagnostic(s,e)
        self.assertEqual(out["status"], "NO_REVIEW")
        self.assertIn("unchanged_closed_5m_volume_floor",
                      out["failed_standard_hard_check_names"])

    def test_missing_checks_not_a_pass_or_invented_market_reject(self):
        s,e,_=compare(1.2)
        broken=copy.deepcopy(s);broken["checks"]=None
        with self.assertRaises(ValueError):
            review_diagnostic(broken,e)
        s,e,_=compare(1.1)
        s["checks"]=None
        result=review_diagnostic(s,e)
        self.assertIsNone(result["failed_standard_hard_check_names"])

    def test_forged_extra_review_and_unknown_status_never_accepted(self):
        s,e,_=compare(1.1)
        e["old_standard_all_other_checks_passed"]=False
        with self.assertRaises(ValueError):
            review_diagnostic(s,e)
        s,e,_=compare(0.5)
        s["status"]="https://secret-token.invalid/?api=shhhh"
        out=review_diagnostic(s,e)
        self.assertEqual(out["standard_status"],"UNKNOWN_STATUS")
        self.assertEqual(out["status"],"UNKNOWN_REVIEW_OR_PERMISSION")
        self.assertNotIn("shhhh",str(out))

    def test_phase_classifies_assetpairs_and_hides_urls_and_secrets(self):
        failure=phase_failure("KRAKEN_ONLINE_SPOT_EUR_ASSETPAIRS",
                              RuntimeError("SECRET=sk-private https://host"))
        self.assertTrue(failure["assetpairs_phase_failed"])
        self.assertEqual(failure["exception_type"],"RuntimeError")
        self.assertNotIn("sk-private",str(failure))
        self.assertFalse(failure["new_model_permission"])
        self.assertEqual(phase_failure("UNKNOWN",Exception("bad"))["phase"],
                         "UNCLASSIFIED_PHASE")

    def test_model_p4_wait_receipt_orders_true_response_and_expiry(self):
        args=receipt_args()
        before=copy.deepcopy(args)
        x=full_review_receipt(**args)
        self.assertEqual(args,before)
        self.assertEqual(x["model_request_to_response_ms"],3000)
        self.assertEqual(x["wait_ttl_minutes"],20)
        self.assertEqual(x["wait_expires_at_utc"],"2026-10-11T10:20:18Z")
        self.assertEqual(len(x["watch_conditions"]),2)
        self.assertEqual(x["validated_decision"],"WAIT")
        self.assertFalse(x["economic_edge_proven"])
        self.assertEqual(x["orders"],0)
        self.assertIsNone(x["actual_pnl_eur"])

    def test_missing_or_inverted_model_response_time_never_pretends_pit_proof(self):
        changes=[
            {"model_request_at_utc":"2026-10-11T10:00:19Z"},
            {"model_response_at_utc":"2026-10-11T10:00:13Z"},
            {"p4_completed_at_utc":"2026-10-11T10:00:16Z"},
            {"entry_known_at_utc":"2026-10-11T10:01:00Z"},
            {"assetpairs_at_utc":"2026-10-11T10:01:00Z"},
            {"entry_known_at_utc":"2026-10-11T09:50:00Z"},
            {"eligibility_at_utc":"2026-10-11T10:00:12"},
            {"model_response_at_utc":None},
            {"model_response_id":"fake_resp_with_secret"},
            {"model_response_id":""},
        ]
        for change in changes:
            args=receipt_args();args.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                full_review_receipt(**args)

    def test_wait_requirements_fail_closed_missing_ttl_bad_watch(self):
        for mutation in (
            lambda p:p.pop("ttl_minutes"),
            lambda p:p.update(ttl_minutes=61),
            lambda p:p.update(watch_conditions=[]),
            lambda p:p.update(watch_conditions=[{"metric":"DELETE_EVERYTHING","op":">","value":1}]),
            lambda p:p.update(watch_conditions=[{"metric":"ask_eur","op":">","value":float("nan")}]),
            lambda p:p.update(watch_conditions=[{"metric":"ask_eur","op":">","value":True}]),
            lambda p:p.update(watch_conditions=[{"metric":"ask_eur","op":">","value":1,"secret":"xxx"}]),
        ):
            args=receipt_args();mutation(args["p4_result"])
            with self.assertRaises(ValueError):
                full_review_receipt(**args)

    def test_no_fake_filled_trade_or_wrong_p4_decision(self):
        for mutation in (
            lambda p:p.update(status="FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE"),
            lambda p:p.update(orders=True),
            lambda p:p.update(real_money_actions=True),
            lambda p:p.update(paper_writer_started=True),
            lambda p:p.update(release_evidence=True),
            lambda p:p.update(economic_edge_proven=True),
        ):
            args=receipt_args();mutation(args["p4_result"])
            with self.assertRaises(ValueError):
                full_review_receipt(**args)

    def test_helper_has_no_imports_into_active_paper_or_consumed_p3_runner(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        for p in ("paper_evaluator/evaluate.py",
                  "paper_evaluator/v2r4_local_recheck.py",
                  "paper_evaluator/v2r4_wait_runtime.py",
                  "paper_evaluator/v3_p3_ab_five_bounded_research.py",
                  "tools/v2r4-paper-local-runtime.py"):
            self.assertNotIn("v3_p3_future_diagnostics_offline_v1",
                             (root/p).read_text("utf-8"))


if __name__=="__main__":
    unittest.main()
