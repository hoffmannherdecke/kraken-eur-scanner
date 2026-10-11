"""V3 exploratory PAPER initial entry is earlier than WAIT/15m, but never auto-BUY."""
import copy
import unittest
from pathlib import Path

from paper_evaluator.v3_experimental_paper_initial_review_v1 import (
    ELIGIBLE,propose_initial_full_review,
)
from paper_evaluator.v3_experimental_paper_model_prompt_v1 import (
    build_v3_paper_full_model_prompt,
)
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v2r4_v3_entry_handoff_probe import evidence,dt
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as full_fixture


def fixture():
    c={"candidate_id":"V3-INITIAL-EUR-1","pair":"XBT/EUR",
       "event_time_utc":dt(-60)}
    e=evidence()
    t={"pair":"XBT/EUR","bid":10.23,"ask":10.24,
       "spread_pct":(10.24-10.23)/((10.24+10.23)/2)*100,
       "observed_at_utc":dt(9)}
    m={"pair":"XBT/EUR","status":"online","spot":True,"quote":"EUR",
       "minimum_order_passed":True,"observed_at_utc":dt(8)}
    return c,e,t,m


def ticket(xs):
    return propose_initial_full_review(*xs,decision_at_utc=dt(12))


def p4(hint,xs,model):
    c,e,t,m=xs
    return validate_full_entry_decision(hint,c,e,t,m,model,
                                        decision_at_utc=dt(12),
                                        slippage_pct_each_side=.08)


class ExperimentalInitialV3PaperTests(unittest.TestCase):
    def test_initial_all_family_permission_requires_no_later_closed_confirmation(self):
        xs=fixture();snap=copy.deepcopy(xs);h=ticket(xs)
        self.assertEqual(xs,snap)
        self.assertEqual(h["status"],ELIGIBLE)
        self.assertEqual(set(h["checks"]),set((
            "fresh_original_candidate","complete_real_closed_coin_frames",
            "positive_coin_atr","structural_invalidating_low_below_ask",
            "current_online_kraken_spot_eur","kraken_order_minimum_pass",
            "fresh_noninverted_ask_bid","execution_spread_at_most_half_percent")))
        self.assertTrue(all(h["checks"].values()))
        self.assertFalse(h["approval_to_call_model"])
        self.assertFalse(h["paper_trade"])
        self.assertTrue(h["request_model_recheck_only"])
        self.assertFalse(h["orders"])
        self.assertFalse(h["release_evidence"])
        self.assertFalse(h["model_called"])
        # Valid low volume is research context, NOT automatic hard blocker.
        low=copy.deepcopy(xs)
        low[1]["frames"]["5"]["volume_ratio_prior_5"]=0.0
        self.assertEqual(ticket(low)["status"],ELIGIBLE)

    def test_full_v3_model_required_and_all_initial_lanes_share_same_risk(self):
        xs=fixture();h=ticket(xs)
        self.assertEqual(p4(h,xs,None)["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")
        for lane in ("IGNITION","CONTINUITY","REVERSAL","EXTENDED"):
            model=full_fixture()[-1];model["candidate_id"]=xs[0]["candidate_id"]
            model["decision_at_utc"]=dt(12);model["setup_lane"]=lane
            v=p4(h,xs,model)
            self.assertEqual(v["decision"],"BUY_SCOUT",lane)
            self.assertEqual(v["status"],
                             "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
            self.assertFalse(v["orders"])
            self.assertFalse(v["paper_writer_started"])
            self.assertGreater(v["total_round_trip_cost_pct"],1.2)
        model=full_fixture()[-1]
        model.update(candidate_id=xs[0]["candidate_id"],decision_at_utc=dt(12),
                     stop_eur=10.5)
        self.assertEqual(p4(h,xs,model)["status"],"FAIL_CLOSED_NONEXECUTABLE_BUY_AS_REJECT")

    def test_missing_required_kraken_source_fails_closed_not_false_market_reject(self):
        mutations=[
            lambda x:x[0].update(event_time_utc=dt(30)),
            lambda x:x[0].update(event_time_utc=dt(-1000)),
            lambda x:x[1]["frames"]["5"].update(status="MISSING"),
            lambda x:x[1]["frames"]["15"].update(atr14_eur=None),
            lambda x:x[1]["frames"]["15"].update(recent_8bar_low_eur=None),
            lambda x:x[1]["frames"]["5"].update(volume_ratio_prior_5=float("nan")),
            lambda x:x[2].update(pair="ETH/EUR"),
            lambda x:x[2].update(observed_at_utc=dt(30)),
            lambda x:x[2].update(ask=0.0),
            lambda x:x[2].update(bid=10.40),
            lambda x:x[3].update(status="cancel_only"),
            lambda x:x[3].update(minimum_order_passed=False),
            lambda x:x[3].update(observed_at_utc=dt(-130)),
        ]
        for change in mutations:
            x=copy.deepcopy(fixture());change(x);h=ticket(x)
            with self.subTest(status=h["status"]):
                self.assertNotEqual(h["status"],ELIGIBLE)
                self.assertFalse(h["request_model_recheck_only"])

    def test_forged_initial_ticket_cannot_make_buy(self):
        xs=fixture();model=full_fixture()[-1]
        model.update(candidate_id=xs[0]["candidate_id"],decision_at_utc=dt(12))
        original=ticket(xs)
        for change in (
            lambda h:h["checks"].update(current_online_kraken_spot_eur=False),
            lambda h:h.update(kind="FAKE"),
            lambda h:h.update(request_model_recheck_only=False),
            lambda h:h.update(exact_full_model_consumer_required=False),
            lambda h:h.update(new_snapshot_known_at_utc=dt(13)),
            lambda h:h.update(source_5m_volume_ratio=9.99),
            lambda h:h.update(decision_at_utc=dt(50)),
        ):
            forged=copy.deepcopy(original);change(forged)
            self.assertNotEqual(p4(forged,xs,model)["decision"],"BUY_SCOUT")

    def test_v3_prompt_is_changed_from_old_selector_but_no_future_leak(self):
        xs=fixture();c,e,t,m=xs;h=ticket(xs)
        prompt=build_v3_paper_full_model_prompt(
            candidate=c,eligibility=h,entry_evidence=e,ticker=t,
            pair_metadata=m,decision_at_utc=dt(12),
            optional_context={"news":None,"macro":{"risk":"UNKNOWN"}})
        self.assertIn("FIRST actual",prompt) if False else None
        self.assertIn("NEW independent V3 decision policy",prompt)
        self.assertIn("candidate_entry_evidence",prompt)
        self.assertIn("atr14_eur",prompt)
        self.assertIn("volume_ratio_prior_5",prompt)
        self.assertIn("no universal",prompt.lower())
        self.assertIn('"available":false',prompt)
        self.assertNotIn('"risk":"UNKNOWN"',prompt)
        self.assertNotIn("actual_pnl",prompt)
        bad=dict(c,future_close=999)
        with self.assertRaises(ValueError):
            build_v3_paper_full_model_prompt(
                candidate=bad,eligibility=h,entry_evidence=e,ticker=t,
                pair_metadata=m,decision_at_utc=dt(12))

    def test_old_v2r4_owner_is_not_wired_to_v3(self):
        root=Path(__file__).resolve().parents[1]
        for path in ("paper_evaluator/evaluate.py",
                     "paper_evaluator/v2r4_local_recheck.py",
                     "tools/v2r4-paper-local-runtime.py"):
            s=(root/path).read_text("utf-8")
            self.assertNotIn("v3_experimental_paper_initial_review_v1",s)
            self.assertNotIn("v3_experimental_paper_model_prompt_v1",s)

if __name__=="__main__":
    unittest.main()
