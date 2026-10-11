"""P3 early-CONTINUITY fresh review only: no model, orders, soft-veto removal."""
import copy
import unittest
from pathlib import Path
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import (
    propose_continuity_fresh_review, ELIGIBLE,
)
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v3_second_leg_policy_candidate_v1 import good,dt
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as full_fixture


def fixture():
    cand,base,e,ticker,bars=good()
    cand["event_time_utc"]=dt(-300)
    base.update(setup_lane="CONTINUITY",decision="WAIT",reason_codes=["MAJOR_MARKETS_WEAK","PRICE_VOLUME_CONFIRMATION_UNPROVEN"])
    ticker["observed_at_utc"]=dt(8)
    return cand,base,e,ticker,bars


def run(change=None,*,at=None,optional=None):
    xs=fixture()
    if change:
        change(xs)
    return propose_continuity_fresh_review(*xs,decision_at_utc=at or dt(13),
                                          optional_sources=optional)


class ContinuityFreshResearchOnlyTests(unittest.TestCase):
    def test_early_closed_continuity_allows_only_future_full_model_comparison(self):
        xs=fixture(); snap=copy.deepcopy(xs)
        r=propose_continuity_fresh_review(*xs,decision_at_utc=dt(13))
        self.assertEqual(xs,snap)
        self.assertEqual(r["status"],ELIGIBLE)
        self.assertTrue(r["request_model_recheck_only"])
        self.assertTrue(all(r["checks"].values()))
        self.assertEqual(r["decision"],"NO_DECISION_AUTHORITY")
        for f in ("approval_to_call_model","changes_v2r4","changes_wait_ttl",
                  "changes_stop_or_stage2_policy","changes_h3_h6",
                  "paper_state_changed","paper_trade","orders","real_money_actions",
                  "auto_buy","economic_edge_proven"):
            self.assertIs(r[f],False,f)
        self.assertGreater(r["fee_plus_spread_pct_before_slippage"],1.2)

    def test_not_extending_wait_expiry_or_extended_second_leg(self):
        for change in (
          lambda x:x[1].update(setup_lane="EXTENDED"),
          lambda x:x[1].update(setup_lane="IGNITION"),
          lambda x:x[1].update(decision="BUY_SCOUT"),
        ):
            self.assertEqual(run(change)["status"],"OUT_OF_SCOPE_NOT_EARLY_CONTINUITY_WAIT_OR_REJECT")
        self.assertEqual(run(lambda x:x[0].update(event_time_utc=dt(-1000)))["status"],
                         "NOT_A_FRESH_CONTINUITY_CANDIDATE")

    def test_prevent_lookahead_and_replayed_candles(self):
        self.assertEqual(run(lambda x:x[0].update(event_time_utc=dt(60)))["status"],
                         "NOT_A_FRESH_CONTINUITY_CANDIDATE")
        self.assertEqual(run(lambda x:x[0].update(event_time_utc=dt(0)))["status"],
                         "NO_NEW_CLOSED_CONTINUITY_BAR_AFTER_CANDIDATE")
        self.assertEqual(run(lambda x:x[4].clear())["status"],
                         "MISSING_CONTIGUOUS_CLOSED_15M_HISTORY")
        self.assertEqual(run(lambda x:x[4][-1].update(start_utc=x[4][-1]["start_utc"]+900))["status"],
                         "NONCONTIGUOUS_CLOSED_15M_HISTORY")
        self.assertEqual(run(lambda x:x[2].update(known_at_utc=dt(60)))["status"],
                         "UNKNOWN_REQUIRED_COIN_OR_CONTINUITY_PIT")

    def test_price_volume_stop_and_spread_negative_checks_remain_hard(self):
        r=run(lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=0.0))
        self.assertEqual(r["status"],"CONTINUITY_EARLY_CONFIRMATION_NOT_PROVEN")
        self.assertIs(r["checks"]["unchanged_closed_5m_volume_floor"],False)
        self.assertFalse(r["request_model_recheck_only"])
        r=run(lambda x:x[3].update(bid=10.1))
        self.assertFalse(r["checks"]["fresh_eur_spread_guard"])
        def no_reclaim(x):
            x[4][-1]["close"]=10.1
            x[2]["frames"]["15"]["closed_close_eur"]=10.1
        r=run(no_reclaim)
        self.assertFalse(r["checks"]["closed_new_15m_continuation_above_base"])

    def test_missing_required_source_fails_closed_optional_is_neutral(self):
        for change in (
          lambda x:x[2].update(pair="ETH/EUR"),
          lambda x:x[2]["frames"]["15"].update(atr14_eur=None),
          lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=None),
          lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=float("nan")),
          lambda x:x[3].update(observed_at_utc=dt(-600)),
          lambda x:x[3].update(ask=0),
        ):
            r=run(change)
            self.assertNotEqual(r["status"],ELIGIBLE)
            self.assertFalse(r["request_model_recheck_only"])
        self.assertEqual(run()["status"],run(optional={"h10":None,"macro":{"status":"MISSING"}})["status"])

    def test_explicit_full_model_and_cost_stop_stage2_validator_not_shortcut(self):
        hint=run()
        xs=list(full_fixture())
        xs[1]["candidate_id"]=hint["source_candidate_id"]
        xs[5]["candidate_id"]=hint["source_candidate_id"]
        xs[5]["decision_at_utc"]=dt(13)
        no_model=validate_full_entry_decision(hint,*xs[1:-1],None,
                                              decision_at_utc=dt(13),slippage_pct_each_side=.08)
        self.assertEqual(no_model["decision"],"UNKNOWN")
        self.assertEqual(no_model["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")
        # Only offline fabricated full assessments test the contract, not alpha.
        mocked=validate_full_entry_decision(hint,*xs[1:],decision_at_utc=dt(13),
                                             slippage_pct_each_side=.08)
        self.assertEqual(mocked["status"],"FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
        self.assertFalse(mocked["orders"])
        self.assertFalse(mocked["economic_edge_proven"])
        self.assertGreater(mocked["total_round_trip_cost_pct"],1.2)
        for change in (
            lambda h:h.update(kind="AD_HOC_UNREGISTERED"),
            lambda h:h.update(new_closed_15m_bar_after_candidate=False),
            lambda h:h.update(new_snapshot_known_at_utc=dt(24)),
            lambda h:h.update(fresh_close_at_utc=dt(24)),
        ):
            test=dict(hint);change(test)
            result=validate_full_entry_decision(test,*xs[1:],
                                                decision_at_utc=dt(13),slippage_pct_each_side=.08)
            self.assertNotEqual(result["decision"],"BUY_SCOUT")
        bad=list(copy.deepcopy(xs));bad[5]["stage2_trigger_eur"]=9.9
        failed=validate_full_entry_decision(hint,*bad[1:],decision_at_utc=dt(13),
                                            slippage_pct_each_side=.08)
        self.assertEqual(failed["status"],"FAIL_CLOSED_NONEXECUTABLE_BUY_AS_REJECT")

    def test_p3_full_validator_requires_eight_checks_and_matching_continuity_lane(self):
        hint=run()
        xs=list(full_fixture())
        xs[1]["candidate_id"]=hint["source_candidate_id"]
        xs[5]["candidate_id"]=hint["source_candidate_id"]
        xs[5]["decision_at_utc"]=dt(13)
        for corrupt in (
            lambda h:h.pop("checks"),
            lambda h:h["checks"].pop("fresh_eur_spread_guard"),
            lambda h:h["checks"].update(fresh_ask_not_chase=False),
            lambda h:h["checks"].update(fake_extra_gate=True),
        ):
            suspect=copy.deepcopy(hint)
            corrupt(suspect)
            result=validate_full_entry_decision(suspect,*xs[1:],
                                                decision_at_utc=dt(13),slippage_pct_each_side=.08)
            self.assertEqual(result["status"],"NO_FULL_REVIEW_ELIGIBILITY")
            self.assertNotEqual(result["decision"],"BUY_SCOUT")
        for lane in ("REVERSAL","IGNITION","EXTENDED","NONE"):
            case=copy.deepcopy(xs)
            case[5]["setup_lane"]=lane
            result=validate_full_entry_decision(hint,*case[1:],
                                                decision_at_utc=dt(13),slippage_pct_each_side=.08)
            self.assertEqual(result["status"],"UNKNOWN_REQUIRED_PIT_OR_EXECUTION_EVIDENCE")
            self.assertFalse(result["orders"])

    def test_live_v2r4_does_not_import_p3_or_full_model_contract(self):
        root=Path(__file__).resolve().parents[1]
        for path in ("paper_evaluator/evaluate.py","paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py","tools/v2r4-paper-local-runtime.py"):
            body=(root/path).read_text("utf-8")
            self.assertNotIn("v3_continuity_fresh_review_candidate_v1",body)
            self.assertNotIn("v3_full_entry_decision_candidate_v1",body)


if __name__=="__main__":
    unittest.main()
