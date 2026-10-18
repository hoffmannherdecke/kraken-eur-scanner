"""Pure offline V3 second-leg candidate: one review-eligibility difference, NO orders."""
import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_evaluator.v3_second_leg_policy_candidate_v1 import (
    propose_second_leg_review,witnessed_15m_from_existing_1m_path,
)
from tests.test_v2r4_v3_entry_handoff_probe import evidence, BASE


def dt(offset=0):
    return datetime.fromtimestamp(BASE + offset, timezone.utc).isoformat()


def good():
    e = evidence()
    e["frames"]["15"]["closed_close_eur"] = 10.28
    e["frames"]["15"]["atr14_eur"] = 0.25
    e["frames"]["15"]["recent_8bar_low_eur"] = 9.96
    e["frames"]["5"]["closed_close_eur"] = 10.26
    e["frames"]["5"]["volume_ratio_prior_5"] = 1.35
    bars = []
    # Last five complete contiguous 15-minute bars; four consolidation,
    # fifth new close above the historical base.
    for n in range(5):
        v = {"start_utc": BASE - 5*900 + n*900,
             "open": 10.08, "close": 10.09,
             "high": 10.12, "low": 10.00, "volume": 100.0}
        if n == 4:
            v.update(open=10.09, close=10.28, high=10.32, low=10.04)
        bars.append(v)
    cand = {"candidate_id":"OLD-EXTENDED-EUR-1", "pair":"XBT/EUR",
            "event_time_utc":dt(-5*900)}
    decision = {"decision":"REJECT", "setup_lane":"EXTENDED",
                "reason_codes":["ALREADY_RUN","LATE_CHASE"]}
    ticker = {"ask":10.30, "bid":10.29}
    return cand, decision, e, ticker, bars


def run(variation=None, *, base_bars=4, at=None, optional=None):
    xs = good()
    if variation:
        variation(xs)
    c, d, e, t, bars = xs
    return propose_second_leg_review(c, d, e, t, bars,
                                     decision_at_utc=at or dt(13),
                                     base_bars=base_bars,
                                     optional_sources=optional)


class SecondLegPolicyCandidateTests(unittest.TestCase):
    def test_new_real_base_reclaim_enables_only_future_full_review(self):
        state = good()
        snap = copy.deepcopy(state)
        r = propose_second_leg_review(*state,decision_at_utc=dt(13),
                                      optional_sources={"onchain":{"status":"MISSING"},
                                                        "headlines":None})
        self.assertEqual(r["status"],"SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY")
        self.assertEqual(r["next_action"],"ONLY_IF_SEPARATELY_APPROVED_FRESH_FULL_MODEL_REVIEW")
        self.assertTrue(r["request_model_recheck_only"])
        self.assertTrue(all(r["checks"].values()))
        self.assertEqual(state,snap)
        for flag in ("paper_trade","orders","real_money_actions","auto_buy",
                     "changes_v2r4","changes_wait_ttl","economic_edge_proven",
                     "changes_h3_h6","changes_stop_or_stage2_policy",
                     "approval_to_call_model"):
            self.assertIs(r[flag],False,flag)
        self.assertEqual(r["decision"],"NO_DECISION_AUTHORITY")
        self.assertEqual(r["fee_pct_each_side_unchanged"],.6)
        self.assertEqual(r["scout_eur_unchanged"],50)
        self.assertEqual(r["stage2_eur_unchanged"],50)
        self.assertGreater(r["fee_plus_spread_pct_before_slippage"],1.2)

    def test_exact_minute_archive_is_required_for_closed_second_leg_base(self):
        # Pure unit fixture: in production assemble() independently authenticates
        # the original capture files and lag. No historical/reconstructed MFE.
        first=BASE-75*60
        minute_rows=[]
        for n in range(75):
            is_breakout=n>=60
            op,hi,lo,close=(
                (10.09,10.32,10.04,10.28) if is_breakout
                else (10.08,10.12,10.00,10.09))
            minute_rows.append({
                "start_at_utc":datetime.fromtimestamp(first+60*n,timezone.utc).isoformat(),
                "open":op,"high":hi,"low":lo,"close":close})
        path={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
              "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":"XBT/EUR",
              "captured_at_utc":dt(7),
              "closed_bars":minute_rows,
              "source_snapshots_with_conflicts":False,
              "no_future_backfill":True,
              "max_original_snapshot_lag_minutes":15,
              "historical_late_backfill_excluded":True}
        bars=witnessed_15m_from_existing_1m_path(
            path,pair="XBT/EUR",observed_at_utc=dt(13))
        self.assertEqual(len(bars),5)
        self.assertEqual(bars[-1]["close"],10.28)
        self.assertEqual(bars[-1]["start_utc"],BASE-900)
        c,d,e,t,_=good()
        self.assertEqual(propose_second_leg_review(
            c,d,e,t,bars,decision_at_utc=dt(13))["status"],
            "SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY")
        gap=copy.deepcopy(path);gap["closed_bars"].pop(12)
        incomplete=witnessed_15m_from_existing_1m_path(
            gap,pair="XBT/EUR",observed_at_utc=dt(13))
        self.assertEqual(len(incomplete),4)
        self.assertEqual(propose_second_leg_review(
            c,d,e,t,incomplete,decision_at_utc=dt(13))["status"],
            "MISSING_CLOSED_CONSOLIDATION_HISTORY")
        forged=dict(path,no_future_backfill=False)
        with self.assertRaises(ValueError):
            witnessed_15m_from_existing_1m_path(
                forged,pair="XBT/EUR",observed_at_utc=dt(13))
        future=dict(path,captured_at_utc=dt(45))
        with self.assertRaises(ValueError):
            witnessed_15m_from_existing_1m_path(
                future,pair="XBT/EUR",observed_at_utc=dt(13))

    def test_missing_optional_source_is_neutral_not_hidden_veto(self):
        base = run()
        absent = run(optional={"news":None, "smart_money":{"status":"UNAVAILABLE"}})
        self.assertEqual(base["status"],absent["status"])
        self.assertTrue(absent["optional_sources_are_context_only"])

    def test_non_extended_or_already_bought_never_enters(self):
        self.assertEqual(run(lambda x:x[1].update(setup_lane="CONTINUITY"))["status"],
                         "OUT_OF_SCOPE_NOT_PRIOR_EXTENDED_WAIT_OR_REJECT")
        self.assertEqual(run(lambda x:x[1].update(decision="BUY_SCOUT"))["status"],
                         "OUT_OF_SCOPE_NOT_PRIOR_EXTENDED_WAIT_OR_REJECT")

    def test_original_candidates_can_be_older_than_fifteen_minutes(self):
        self.assertGreater((datetime.fromisoformat(dt(13))-
                            datetime.fromisoformat(good()[0]["event_time_utc"])).total_seconds(),900)
        self.assertTrue(run()["request_model_recheck_only"])

    def test_cannot_reuse_old_bars_or_make_up_a_base(self):
        self.assertEqual(run(lambda x:x[4].pop())["status"],
                         "MISSING_CLOSED_CONSOLIDATION_HISTORY")
        self.assertEqual(run(lambda x:x[4][1].update(start_utc=x[4][1]["start_utc"]+60))["status"],
                         "NONCONTIGUOUS_BASE_HISTORY")
        self.assertEqual(run(lambda x:x[4][0].update(start_utc=x[4][0]["start_utc"]-900))["status"],
                         "NONCONTIGUOUS_BASE_HISTORY")

    def test_old_base_cannot_be_recreated_from_future_knowledge(self):
        self.assertEqual(run(at=dt(-30))["status"],
                         "OUTSIDE_FRESH_SECOND_LEG_OBSERVATION_WINDOW")
        self.assertEqual(run(lambda x:x[4][-1].update(start_utc=BASE+900))["status"],
                         "NONCONTIGUOUS_BASE_HISTORY")
        self.assertEqual(run(lambda x:x[2].update(known_at_utc=dt(80)))["status"],
                         "UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")

    def test_reclaim_requires_real_fresh_closed_15_minute_candle(self):
        self.assertEqual(run(lambda x:x[4][-1].update(close=10.10))["status"],
                         "CANDLE_EVIDENCE_PRICE_MISMATCH")
        def no_reclaim(xs):
            xs[4][-1]["close"] = 10.11
            xs[2]["frames"]["15"]["closed_close_eur"] = 10.11
        r = run(no_reclaim)
        self.assertEqual(r["status"],"SECOND_LEG_CONDITIONS_NOT_CONFIRMED")
        self.assertFalse(r["checks"]["closed_reclaim_above_prior_base_high"])

    def test_overextended_stays_protected_no_chase(self):
        def chase(xs):
            xs[4][-1].update(close=10.45,high=10.50)
            xs[2]["frames"]["15"]["closed_close_eur"] = 10.45
            xs[3]["ask"] = 10.46
        r = run(chase)
        self.assertEqual(r["status"],"SECOND_LEG_CONDITIONS_NOT_CONFIRMED")
        self.assertFalse(r["checks"]["reclaim_not_late_chase"])

    def test_weak_volume_and_costly_spread_block_review_only(self):
        r=run(lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=1.1))
        self.assertFalse(r["checks"]["existing_v2r4_volume_confirmed"])
        self.assertFalse(r["request_model_recheck_only"])
        r=run(lambda x:x[3].update(bid=10.10))
        self.assertFalse(r["checks"]["liquid_eur_spread"])

    def test_valid_5m_zero_volume_ratio_is_negative_not_missing_pit(self):
        # OHLC canonical frame may be VALID with legitimate last volume=0;
        # the original _finite_positive(0) turned it into unexplained UNKNOWN
        # despite all required 1/5/15m candle statuses being VALID.
        def zero_valid_5m(xs):
            xs[2]["frames"]["5"]["status"]="VALID"
            xs[2]["frames"]["5"]["volume_ratio_prior_5"]=0.0
            xs[2]["frames"]["5"]["volume_ratio_status"]="VALID"
        r=run(zero_valid_5m)
        self.assertEqual(r["status"],"SECOND_LEG_CONDITIONS_NOT_CONFIRMED")
        self.assertIs(r["checks"]["existing_v2r4_volume_confirmed"],False)
        self.assertFalse(r["request_model_recheck_only"])
        self.assertEqual(r["decision"],"NO_DECISION_AUTHORITY")
        self.assertFalse(r["paper_trade"])
        self.assertFalse(r["orders"])

    def test_missing_or_invalid_5m_ratio_still_unknown_without_buy(self):
        for val in (None,float("nan"),-0.1):
            r=run(lambda x:x[2]["frames"]["5"].update(volume_ratio_prior_5=val))
            self.assertEqual(r["status"],"UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
            self.assertEqual(r.get("validation_stage"),"CORE_PIT_SOURCE")
            self.assertFalse(r["request_model_recheck_only"])

    def test_unknown_result_has_safe_stage_not_sensitive_error_detail(self):
        r=run(lambda x:x[2].update(status="PARTIAL_OR_MISSING"))
        self.assertEqual(r["status"],"UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
        self.assertEqual(r["validation_stage"],"CORE_PIT_SOURCE")
        self.assertNotIn("raw_error",r)
        self.assertNotIn("exception",r)

    def test_invalid_core_stop_context_and_missing_source_are_unknown(self):
        self.assertEqual(run(lambda x:x[2]["frames"]["15"].update(atr14_eur=None))["status"],
                         "UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
        self.assertEqual(run(lambda x:x[2].update(status="PARTIAL_OR_MISSING"))["status"],
                         "UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
        self.assertEqual(run(lambda x:x[3].update(ask=0))["status"],
                         "UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")
        self.assertEqual(run(lambda x:x[2].update(pair="ETH/EUR"))["status"],
                         "UNKNOWN_REQUIRED_PIT_OR_STRUCTURE_EVIDENCE")

    def test_three_hour_base_uses_twelve_closed_bars_without_changing_risk(self):
        def provide_3h(xs):
            # Prefix 8 earlier closed bars so 12 are consolidation, last is
            # the same timestamped reclaim. Original extended alert precedes it.
            old = xs[4]
            prefix=[]
            for i in range(8):
                v=dict(old[0])
                v["start_utc"] = BASE - 13*900 + i*900
                prefix.append(v)
            xs[4][:] = prefix+old
            xs[0]["event_time_utc"] = dt(-13*900)
        r=run(provide_3h,base_bars=12)
        self.assertEqual(r["status"],"SECOND_LEG_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY")
        self.assertEqual(r["base_15m_bars"],12)
        self.assertFalse(r["auto_buy"])

    def test_unapproved_variants_cannot_hide_strategy_optimization(self):
        self.assertEqual(run(base_bars=3)["status"],"INVALID_RESEARCH_BASE_WINDOW")
        self.assertEqual(run(base_bars=13)["status"],"INVALID_RESEARCH_BASE_WINDOW")
        self.assertEqual(run(base_bars=True)["status"],"INVALID_RESEARCH_BASE_WINDOW")

    def test_no_live_v2r4_modules_import_standalone_v3_policy(self):
        root=Path(__file__).resolve().parents[1]
        for name in ("paper_evaluator/evaluate.py",
                     "paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py",
                     "tools/v2r4-paper-local-runtime.py"):
            self.assertNotIn("v3_second_leg_policy_candidate_v1",
                             (root/name).read_text("utf-8"))

if __name__ == "__main__":
    unittest.main()
