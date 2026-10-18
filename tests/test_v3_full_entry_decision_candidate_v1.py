"""Offline contract tests for inactive V3-B full entry decision path."""
import copy
import unittest

from paper_evaluator.v3_full_entry_decision_candidate_v1 import (
    validate_full_entry_decision,SECOND_LEG_P1_CHECKS,SECOND_LEG_ELIGIBLE_KIND,
)
from tests.test_v2r4_v3_entry_handoff_probe import evidence, dt


def fixture():
    ev = evidence()
    candidate = {"candidate_id":"V3-B-PIT-1", "pair":"XBT/EUR"}
    eligibility = {
        "kind":SECOND_LEG_ELIGIBLE_KIND,
        "status":"SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY",
        "request_model_recheck_only":True,
        "source_candidate_id":"V3-B-PIT-1",
        "pair":"XBT/EUR",
        "original_candidate_historical_only":True,
        "new_snapshot_known_at_utc":ev["known_at_utc"],
        "base_15m_bars":4,
        "approval_to_call_model":False,
        "checks":{name:True for name in SECOND_LEG_P1_CHECKS},
    }
    ticker = {"pair":"XBT/EUR", "bid":10.23, "ask":10.24,
              "spread_pct":(10.24-10.23)/((10.24+10.23)/2)*100,
              "observed_at_utc":dt(9)}
    metadata = {"pair":"XBT/EUR", "status":"online", "spot":True,
                "quote":"EUR", "minimum_order_passed":True,
                "observed_at_utc":dt(8)}
    assessment = {
        "candidate_id":"V3-B-PIT-1", "pair":"XBT/EUR", "decision_at_utc":dt(12),
        "decision":"BUY_SCOUT", "setup_lane":"CONTINUITY",
        "reason_codes":["FRESH_BASE_RECLAIM"], "anti_chase_passed":True,
        "stop_eur":9.90, "stage2_trigger_eur":10.55, "stage2_ttl_minutes":30,
        "expected_remaining_move_pct":5.0,
    }
    return eligibility, candidate, ev, ticker, metadata, assessment


def run(change=None, assessment=True):
    xs=list(fixture())
    if change:
        change(xs)
    return validate_full_entry_decision(*xs[:-1], xs[-1] if assessment else None,
                                        decision_at_utc=dt(12),
                                        slippage_pct_each_side=0.08)


class V3FullEntryDecisionCandidateTests(unittest.TestCase):
    def test_positive_mock_reaches_full_buy_contract_not_release(self):
        xs=fixture(); snap=copy.deepcopy(xs)
        result=validate_full_entry_decision(*xs, decision_at_utc=dt(12),
                                            slippage_pct_each_side=.08)
        self.assertEqual(result["decision"],"BUY_SCOUT")
        self.assertEqual(result["status"],"FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
        self.assertGreater(result["total_round_trip_cost_pct"],1.2)
        self.assertGreater(result["net_edge_pct_before_path_outcome"],0)
        self.assertLess(result["stop_eur"],result["execution_ask_eur"])
        self.assertGreater(result["stage2_trigger_eur"],result["execution_ask_eur"])
        for key in ("active_runtime_change","model_called","shadow_started",
                    "paper_writer_started","orders","real_money_actions",
                    "economic_edge_proven","release_evidence"):
            self.assertIs(result[key],False,key)
        self.assertEqual(xs,snap)

    def test_forged_five_minute_only_second_leg_cannot_make_p4_buy(self):
        for mutate in (
            lambda x:x[0].update(kind="HOMEMADE_P1"),
            lambda x:x[0].update(base_15m_bars=0),
            lambda x:x[0].update(original_candidate_historical_only=False),
            lambda x:x[0].update(approval_to_call_model=True),
            lambda x:x[0].update(new_snapshot_known_at_utc=dt(200)),
            lambda x:x[0]["checks"].update(base_1_to_3h_rebuilt=False),
            lambda x:x[0]["checks"].pop("closed_reclaim_above_prior_base_high"),
        ):
            with self.subTest(mutate=repr(mutate)):
                xs=list(fixture());mutate(xs)
                outcome=validate_full_entry_decision(
                    *xs,decision_at_utc=dt(12),
                    slippage_pct_each_side=.08)
                self.assertEqual(outcome["status"],"NO_FULL_REVIEW_ELIGIBILITY")
                self.assertEqual(outcome["decision"],"UNKNOWN")
                self.assertFalse(outcome["orders"])

    def test_eligibility_never_becomes_buy_without_full_assessment(self):
        result=run(assessment=False)
        self.assertEqual(result["decision"],"UNKNOWN")
        self.assertEqual(result["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")

    def test_identity_and_pit_clock_must_match(self):
        for change in (
            lambda x:x[2].update(pair="ETH/EUR"),
            lambda x:x[3].update(observed_at_utc=dt(20)),
            lambda x:x[4].update(status="cancel_only"),
            lambda x:x[4].update(observed_at_utc=dt(20)),  # future AssetPairs authority
            lambda x:x[2]["frames"]["1"].update(last_closed_bar_end_utc=dt(-200)),  # stale even if VALID
            lambda x:x[2]["frames"]["15"].update(last_closed_bar_end_utc=dt(50)),  # future bar
            lambda x:x[5].update(candidate_id="OTHER"),
        ):
            result=run(change)
            self.assertEqual(result["status"],"UNKNOWN_REQUIRED_PIT_OR_EXECUTION_EVIDENCE")
            self.assertEqual(result["decision"],"UNKNOWN")

    def test_missing_closed_frame_is_unknown_not_market_reject(self):
        result=run(lambda x:x[2]["frames"]["5"].update(status="MISSING"))
        self.assertEqual(result["status"],"UNKNOWN_REQUIRED_PIT_OR_EXECUTION_EVIDENCE")
        self.assertEqual(result["decision"],"UNKNOWN")

    def test_invalid_stop_stage2_or_cost_edge_fails_closed(self):
        changes=(
            lambda x:x[5].update(stop_eur=10.30),
            lambda x:x[5].update(stage2_trigger_eur=10.20),
            lambda x:x[5].update(anti_chase_passed=False),
            lambda x:x[5].update(expected_remaining_move_pct=.5),
        )
        for change in changes:
            result=run(change)
            self.assertEqual(result["status"],"FAIL_CLOSED_NONEXECUTABLE_BUY_AS_REJECT")
            self.assertEqual(result["decision"],"REJECT")

    def test_explicit_wait_and_reject_are_preserved(self):
        def wait(x):
            x[5].update(decision="WAIT",ttl_minutes=20,
                        watch_conditions=[{"metric":"last_eur","op":">=","value":10.5}])
        self.assertEqual(run(wait)["status"],"FULL_WAIT_VALIDATED_OFFLINE")
        self.assertEqual(run(lambda x:x[5].update(decision="REJECT"))["status"],
                         "FULL_REJECT_VALIDATED_OFFLINE")

    def test_full_wait_contract_rejects_unmonitorable_or_invalid_watch_conditions(self):
        def case(value):
            return run(lambda x:x[5].update(decision="WAIT", ttl_minutes=30,
                                              watch_conditions=value))
        good=[{"metric":"closed_5m_volume_ratio_5","op":">=","value":1.2}]
        self.assertEqual(case(good)["status"],"FULL_WAIT_VALIDATED_OFFLINE")
        bad=[
            [], [{"metric":"fake_model_name","op":">=","value":1}],
            [{"metric":"ask_eur","op":"EVAL","value":10}],
            [{"metric":"ask_eur","op":">","value":"nan"}],
            [{"metric":"ask_eur","op":">","value":True}],
            [{"metric":"closed_5m_volume_ratio_5","op":">","value":-1}],
            [{"metric":"ask_eur","op":">","value":10,"secret":"hidden"}],
            [None], good*7,
        ]
        for conds in bad:
            with self.subTest(conds=conds):
                self.assertEqual(case(conds)["status"],"UNKNOWN_INVALID_WAIT_CONTRACT")
                self.assertEqual(case(conds)["decision"],"UNKNOWN")

    def test_optional_sources_are_not_a_hidden_veto(self):
        base=run()
        changed=run(lambda x:x[2].update(optional_sources={"news":None,"h10":"MISSING"}))
        self.assertEqual(base["status"],changed["status"])


if __name__ == "__main__":
    unittest.main()
