"""Realistic loss/control fixtures for V3 CLOSED 1m pathwise Paper estimates."""
import copy
import unittest
from datetime import datetime,timezone,timedelta

from paper_evaluator.v3_experimental_paper_pathwise_economics_v1 import (
    estimate_closed_1m_paper_path,
)

BASE=datetime(2026,10,11,20,0,tzinfo=timezone.utc)
def stamp(t):return t.isoformat()


def bars(n=360,price=10.25):
    return [{"start_at_utc":stamp(BASE+timedelta(minutes=i)),
             "open":price,"high":price+0.02,"low":price-0.02,
             "close":price} for i in range(n)]


def run(data,**updates):
    kwargs={
        "candidate_id":"TEST","pair":"BAT/EUR",
        "entry_at_utc":stamp(BASE),
        "observed_at_utc":stamp(BASE+timedelta(hours=6)),
        "entry_ask_eur":10.25,"stop_eur":9.5,
        "stage2_trigger_eur":11.0,"stage2_ttl_minutes":30,
        "horizon_minutes":360,"closed_1m_bars":data,
        "scout_eur":50,"stage2_eur":50,
        "taker_fee_pct_each_side":0.6,"spread_assumption_pct":0.2,
        "slippage_pct_each_side":0.08,
    }
    kwargs.update(updates)
    return estimate_closed_1m_paper_path(**kwargs)


class V3PathwiseEconomicsTests(unittest.TestCase):
    def test_flat_market_net_loss_from_fees_not_fake_positive_mfe(self):
        a=bars();snap=copy.deepcopy(a)
        x=run(a)
        self.assertEqual(a,snap)
        self.assertEqual(x["status"],"MATURE_ESTIMATED_PAPER_NET_NOT_VERIFIED_FILL")
        self.assertEqual(x["exit_reason"],"HORIZON")
        self.assertFalse(x["stage2_modelled_filled"])
        self.assertLess(x["net_pnl_eur"],0)
        self.assertLess(x["net_return_pct"],0)
        self.assertEqual(x["fee_pct_each_side"],0.6)
        self.assertTrue(x["path_is_estimate_not_exchange_trade"])
        self.assertFalse(x["economic_edge_or_fill_real_world_proven"])
        self.assertFalse(x["orders"])

    def test_qualified_later_stage2_filled_only_when_trigger_crossed(self):
        b=bars()
        for i in range(3,len(b)):
            b[i].update(open=11.2,high=11.32,low=11.05,close=11.2)
        b[2].update(open=10.4,high=11.1,low=10.3,close=11.01)
        x=run(b)
        self.assertEqual(x["status"],"MATURE_ESTIMATED_PAPER_NET_NOT_VERIFIED_FILL")
        self.assertTrue(x["stage2_modelled_filled"])
        self.assertGreater(x["total_invested_including_buy_fees_eur"],100)
        self.assertGreater(x["net_pnl_eur"],0)
        self.assertFalse(x["actual_economic_edge_proven"])

    def test_ambiguous_stop_and_stage2_same_bar_is_stop_first(self):
        b=bars()
        b[0].update(open=10.25,high=11.5,low=9.2,close=10.1)
        x=run(b)
        self.assertEqual(x["exit_reason"],"STOP")
        self.assertTrue(x["stop_first_when_bar_ambiguous"])
        self.assertFalse(x["stage2_modelled_filled"])
        self.assertLess(x["net_pnl_eur"],0)
        self.assertEqual(x["closed_1m_bars_processed"],360)

    def test_gap_down_exit_more_conservative_than_nominal_stop(self):
        b=bars()
        b[0].update(open=9.0,high=9.1,low=8.9,close=9.0)
        x=run(b)
        self.assertEqual(x["exit_reason"],"STOP")
        self.assertLess(x["exit_synthetic_bid_eur"],9.0)
        self.assertLess(x["net_return_pct"],-5)

    def test_maturity_and_gaps_fail_closed_without_zero_return(self):
        missing=run(bars(40))
        self.assertEqual(missing["status"],"CENSORED_INCOMPLETE_HORIZON_PRICE_PATH")
        self.assertIsNone(missing["net_pnl_eur"])
        immature=run(bars(),observed_at_utc=stamp(BASE+timedelta(hours=5)))
        self.assertEqual(immature["status"],"CENSORED_HORIZON_NOT_YET_MATURE")
        cut=bars();cut.pop(10)
        broken=run(cut)
        self.assertEqual(broken["status"],"CENSORED_NONCONTIGUOUS_ONE_MINUTE_PATH")
        self.assertIsNone(broken["net_return_pct"])
        no=run([])
        self.assertEqual(no["status"],"CENSORED_NO_CLOSED_ONE_MINUTE_PATH")

    def test_invalid_sources_and_safety_limits_never_fake_profit(self):
        b=bars()
        for opts in (
            {"entry_ask_eur":-10},
            {"stop_eur":11},
            {"stage2_trigger_eur":10.2},
            {"taker_fee_pct_each_side":float("nan")},
            {"slippage_pct_each_side":-0.1},
            {"pair":"BAT/USD"},
            {"stage2_ttl_minutes":0},
        ):
            x=run(b,**opts)
            self.assertTrue(x["status"].startswith("UNKNOWN_"))
            self.assertIsNone(x["net_pnl_eur"])
        damaged=bars()
        damaged[9]["high"]=9.0
        x=run(damaged)
        self.assertEqual(x["status"],"UNKNOWN_INVALID_PRICE_RISK_OR_CLOCK_PROVENANCE")
        pre=bars()
        pre.insert(0,{"start_at_utc":stamp(BASE-timedelta(minutes=1)),
                      "open":10,"high":10.1,"low":9.9,"close":10})
        self.assertEqual(run(pre)["status"],"UNKNOWN_INVALID_PRICE_RISK_OR_CLOCK_PROVENANCE")

if __name__=="__main__":
    unittest.main()
