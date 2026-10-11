"""INACTIVE V3-P2 expired WAIT full-review-eligibility, not Paper/BUY activation."""
import copy
import unittest
from pathlib import Path

from paper_evaluator.v3_wait_fresh_review_candidate_v1 import (
    propose_wait_fresh_review, ELIGIBLE, EXPIRY_KIND,
)
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v3_second_leg_policy_candidate_v1 import good, dt
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as full_fixture


def fixture():
    cand, decision, ev, ticker, bars=good()
    decision["decision"]="WAIT"
    decision["setup_lane"]="CONTINUITY"
    expiry={
        "kind":EXPIRY_KIND,
        "candidate_id":cand["candidate_id"],
        "pair":cand["pair"],
        "decision":{"decision":"REJECT","reason_codes":["TTL_EXPIRED_NO_TRIGGER"]},
        "recheck_completed_at_utc":dt(-3*900),
        "evaluator":{"attempt":0},
    }
    ticker["observed_at_utc"]=dt(9)
    return cand,decision,expiry,ev,ticker,bars


def run(mutate=None,*,at=None,optional=None):
    xs=fixture()
    if mutate:
        mutate(xs)
    return propose_wait_fresh_review(*xs,decision_at_utc=at or dt(13),
                                     optional_sources=optional)


class WaitFreshReviewTests(unittest.TestCase):
    def test_recovered_new_closed_bar_only_requests_unprivileged_review(self):
        xs=fixture()
        baseline=copy.deepcopy(xs)
        r=propose_wait_fresh_review(*xs,decision_at_utc=dt(13))
        self.assertEqual(xs,baseline)
        self.assertEqual(r["status"],ELIGIBLE)
        self.assertEqual(r["decision"],"NO_DECISION_AUTHORITY")
        self.assertTrue(r["request_model_recheck_only"])
        self.assertTrue(r["original_wait_and_expiry_immutable"])
        self.assertTrue(r["fresh_bar_closed_after_expiry"])
        self.assertEqual(r["prior_wait_recheck_kind"],EXPIRY_KIND)
        self.assertEqual(r["snapshot_recheck_key"],
                         f"{xs[0]['candidate_id']}|{r['fresh_post_expiry_15m_close']}")
        self.assertTrue(all(r["checks"].values()))
        for field in ("approval_to_call_model","changes_v2r4","changes_wait_ttl",
                      "paper_state_changed","paper_trade","orders","real_money_actions",
                      "auto_buy","economic_edge_proven","changes_h3_h6"):
            self.assertIs(r[field],False,field)

    def test_expiry_not_proven_or_original_not_wait_is_out_of_scope(self):
        cases=[
          lambda x:x[1].update(decision="REJECT"),
          lambda x:x[1].update(decision="BUY_SCOUT"),
        ]
        for c in cases:
            self.assertEqual(run(c)["status"],"OUT_OF_SCOPE_ORIGINAL_NOT_WAIT")
        for c in (
          lambda x:x[2].update(kind="V2R4_LOCAL_TRIGGER_RECHECK_V1"),
          lambda x:x[2].update(candidate_id="OTHER"),
          lambda x:x[2].update(pair="ETH/EUR"),
          lambda x:x[2].update(decision={"decision":"WAIT"}),
          lambda x:x[2].update(decision="REJECT"),
        ):
            self.assertEqual(run(c)["status"],"EXPIRY_NOT_PROVEN_OR_ID_MISMATCH")

    def test_stale_expiry_original_or_future_clock_is_never_used(self):
        self.assertEqual(run(lambda x:x[2].update(recheck_completed_at_utc=dt(-6*3600)))["status"],
                         "INVALID_OR_NOT_PAST_WAIT_EXPIRY")
        self.assertEqual(run(lambda x:x[2].update(recheck_completed_at_utc=dt(30)))["status"],
                         "INVALID_OR_NOT_PAST_WAIT_EXPIRY")
        self.assertEqual(run(at=dt(4*3600+30))["status"],
                         "EXPIRED_ANCHOR_TOO_OLD_FOR_BOUNDED_RESEARCH")
        self.assertEqual(run(lambda x:x[2]["evaluator"].update(attempt=1))["status"],
                         "EXPIRY_HAS_UNEXPECTED_MODEL_RECHECK")
        self.assertEqual(run(lambda x:x[0].update(candidate_id=""))["status"],
                         "MISSING_CANONICAL_ORIGINAL_EUR_ID")

    def test_requires_genuinely_post_expiry_opened_and_fully_closed_bar(self):
        self.assertEqual(run(lambda x:x[2].update(recheck_completed_at_utc=dt(-300)))["status"],
                         "NO_INDEPENDENT_POST_EXPIRY_BAR")
        self.assertEqual(run(lambda x:x[5][-1].update(start_utc=x[5][-1]["start_utc"]+900))["status"],
                         "NONCONTIGUOUS_NEW_BAR_HISTORY")
        self.assertEqual(run(lambda x:x[5].pop())["status"],
                         "15M_PRICE_CLOCK_MISMATCH")
        self.assertEqual(run(lambda x:x[5].clear())["status"],
                         "MISSING_NEW_CLOSED_BAR_HISTORY")
        self.assertEqual(run(lambda x:x[3].update(observed_at_utc=dt(-1)))["status"],
                         "UNKNOWN_REQUIRED_NEW_PIT_OR_STRUCTURE_EVIDENCE")

    def test_new_market_structure_and_volume_are_real_not_posthoc_labels(self):
        self.assertEqual(run(lambda x:x[3]["frames"]["15"].update(closed_close_eur=10.01))["status"],
                         "15M_PRICE_EVIDENCE_MISMATCH")
        def no_reclaim(x):
            x[5][-1].update(close=10.11)
            x[3]["frames"]["15"]["closed_close_eur"]=10.11
        r=run(no_reclaim)
        self.assertEqual(r["status"],"FRESH_WAIT_CONDITIONS_NOT_CONFIRMED")
        self.assertFalse(r["checks"]["closed_post_expiry_reclaim"])

        r=run(lambda x:x[3]["frames"]["5"].update(volume_ratio_prior_5=0.0))
        self.assertEqual(r["status"],"FRESH_WAIT_CONDITIONS_NOT_CONFIRMED")
        self.assertFalse(r["checks"]["unchanged_v2r4_closed_5m_volume_confirmation"])
        self.assertFalse(r["request_model_recheck_only"])
        r=run(lambda x:x[4].update(bid=10.1))
        self.assertFalse(r["checks"]["fresh_eur_spread_guard"])

    def test_missing_stale_future_invalid_coin_or_ticker_evidence_fails_closed(self):
        for change in (
            lambda x:x[3].update(pair="ETH/EUR"),
            lambda x:x[3].update(known_at_utc=dt(18)),
            lambda x:x[3]["frames"]["15"].update(atr14_eur=None),
            lambda x:x[3]["frames"]["5"].update(volume_ratio_prior_5=None),
            lambda x:x[3]["frames"]["5"].update(volume_ratio_prior_5=float("nan")),
            lambda x:x[4].update(observed_at_utc=dt(-4*900)),
            lambda x:x[4].update(ask=0),
            lambda x:x[4].update(bid=11.0),
        ):
            r=run(change)
            self.assertFalse(r["request_model_recheck_only"])
            self.assertNotEqual(r["status"],ELIGIBLE)
            self.assertFalse(r["orders"])

    def test_optional_sources_do_not_independently_block_core_p2(self):
        self.assertEqual(run()["status"],
                         run(optional={"h10":None,"news":{"status":"MISSING"}})["status"])

    def test_p1_second_leg_and_p2_wait_share_only_identical_full_risk_contract(self):
        p2=run()
        xs=list(full_fixture())
        xs[1]["candidate_id"]=p2["source_candidate_id"]
        xs[5]["candidate_id"]=p2["source_candidate_id"]
        xs[5]["decision_at_utc"]=dt(13)
        validated=validate_full_entry_decision(p2,*xs[1:],
                                               decision_at_utc=dt(13),
                                               slippage_pct_each_side=.08)
        self.assertEqual(validated["status"],
            "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
        self.assertTrue(validated["eligibility_is_not_buy"])
        self.assertFalse(validated["paper_writer_started"])
        self.assertFalse(validated["model_called"])
        self.assertFalse(validated["orders"])
        self.assertFalse(validated["economic_edge_proven"])

        no_model=validate_full_entry_decision(p2,*xs[1:-1],None,
                                             decision_at_utc=dt(13),
                                             slippage_pct_each_side=.08)
        self.assertEqual(no_model["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")
        for tamper in (
            lambda r:r.update(kind="AD_HOC_SIGNAL"),
            lambda r:r.update(fresh_bar_closed_after_expiry=False),
            lambda r:r.update(prior_wait_recheck_kind="OTHER"),
            lambda r:r.update(expired_at_utc=dt(30)),
            lambda r:r.update(new_snapshot_known_at_utc=dt(20)),
        ):
            forged=dict(p2)
            tamper(forged)
            denial=validate_full_entry_decision(forged,*xs[1:],
                                               decision_at_utc=dt(13),
                                               slippage_pct_each_side=.08)
            self.assertNotEqual(denial["decision"],"BUY_SCOUT")

        no_cost=copy.deepcopy(xs)
        no_cost[5]["expected_remaining_move_pct"]=.2
        stopped=validate_full_entry_decision(p2,*no_cost[1:],
                                            decision_at_utc=dt(13),
                                            slippage_pct_each_side=.08)
        self.assertEqual(stopped["status"],"FAIL_CLOSED_NONEXECUTABLE_BUY_AS_REJECT")

    def test_live_v2r4_never_imports_inactive_p2_or_full_entry(self):
        root=Path(__file__).resolve().parents[1]
        for file in ("paper_evaluator/evaluate.py","paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py","tools/v2r4-paper-local-runtime.py"):
            src=(root/file).read_text("utf-8")
            self.assertNotIn("v3_wait_fresh_review_candidate_v1",src)
            self.assertNotIn("v3_full_entry_decision_candidate_v1",src)


if __name__=="__main__":
    unittest.main()
