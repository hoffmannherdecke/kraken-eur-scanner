"""Inactive single-change V3 early fresh 5m review and shared FULL P4 validation."""
import copy
import unittest
from pathlib import Path

from paper_evaluator.v3_p3_early_5m_continuity_research_v1 import (
    propose_early_5m_continuity_review, ELIGIBLE
)
from paper_evaluator.v3_continuity_fresh_review_candidate_v1 import propose_continuity_fresh_review
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v3_second_leg_policy_candidate_v1 import good, dt, BASE
from tests.test_v3_full_entry_decision_candidate_v1 import fixture as p4fixture


def fixture():
    c,b,e,t,bars=good()
    c["event_time_utc"]=dt(-180)
    b.update(setup_lane="CONTINUITY",decision="WAIT")
    t["observed_at_utc"]=dt(8)
    e["frames"]["15"]["last_closed_bar_end_utc"]=dt(-900)
    e["frames"]["15"]["closed_close_eur"]=10.09
    bars=bars[-4:-1]  # Same three closed 15m bars supplied to both arms
    return c,b,e,t,bars


def run(change=None):
    xs=fixture()
    if change: change(xs)
    return propose_early_5m_continuity_review(*xs,decision_at_utc=dt(13))


def full_inputs():
    c,b,e,t,bars=fixture()
    ticket=propose_early_5m_continuity_review(c,b,e,t,bars,decision_at_utc=dt(13))
    x=list(p4fixture())
    x[1]["candidate_id"]=c["candidate_id"]
    x[1]["event_time_utc"]=c["event_time_utc"]
    x[2]=e
    x[5]["candidate_id"]=c["candidate_id"]
    x[5]["decision_at_utc"]=dt(13)
    return ticket,x


class Early5mV3ResearchTests(unittest.TestCase):
    def test_early_5m_is_available_before_next_15m_but_is_not_buy(self):
        x=fixture();snap=copy.deepcopy(x)
        hint=propose_early_5m_continuity_review(*x,decision_at_utc=dt(13))
        self.assertEqual(hint["status"],ELIGIBLE)
        self.assertTrue(all(hint["checks"].values()))
        self.assertEqual(x,snap)
        self.assertEqual(hint["new_closed_5m_bar_after_candidate"],True)
        self.assertEqual(hint["fee_pct_each_side_unchanged"],0.6)
        self.assertEqual(hint["decision"],"NO_DECISION_AUTHORITY")
        self.assertFalse(hint["approval_to_call_model"])
        self.assertFalse(hint["orders"])
        self.assertFalse(hint["paper_writer_started"])
        self.assertFalse(hint["economic_edge_proven"])
        self.assertEqual(hint["fresh_close_at_utc"],dt(0))
        self.assertEqual(hint["prior_closed_15m_base_end_at_utc"],dt(-900))
        standard=propose_continuity_fresh_review(*x,decision_at_utc=dt(13))
        self.assertNotEqual(standard["status"],
                            "CONTINUITY_FRESH_STRUCTURE_SUPPORTS_NEW_FULL_REVIEW_ONLY")

    def test_p4_only_full_model_can_issue_mock_buy_no_orders(self):
        hint,x=full_inputs()
        no_model=validate_full_entry_decision(hint,*x[1:-1],None,
                                               decision_at_utc=dt(13),
                                               slippage_pct_each_side=.08)
        self.assertEqual(no_model["status"],"UNKNOWN_FULL_ASSESSMENT_NOT_PRODUCED")
        full=validate_full_entry_decision(hint,*x[1:],decision_at_utc=dt(13),
                                           slippage_pct_each_side=.08)
        self.assertEqual(full["status"],
                         "FULL_BUY_SCOUT_CONTRACT_VALIDATED_OFFLINE_NOT_RELEASE_EVIDENCE")
        self.assertFalse(full["orders"])
        self.assertFalse(full["paper_writer_started"])
        self.assertGreater(full["total_round_trip_cost_pct"],1.2)

    def test_verified_early5m_now_reaches_real_full_model_prompt_without_http(self):
        from paper_evaluator.v3_experimental_paper_model_prompt_v1 import (
            build_v3_paper_full_model_prompt,
        )
        hint,x=full_inputs()
        text=build_v3_paper_full_model_prompt(
            candidate=x[1],eligibility=hint,entry_evidence=x[2],
            ticker=x[3],pair_metadata=x[4],decision_at_utc=dt(13))
        self.assertIn("EARLY CLOSED-5M CONTINUITY",text)
        self.assertIn("EARLY_5M_CONTINUITY_SUPPORTS_NEW_FULL_REVIEW_ONLY",text)
        self.assertIn("EARLY_5M_P3",text)
        self.assertIn("snapshot_recheck_key",text)
        self.assertIn("NO model review",text)
        self.assertTrue(hint["request_model_recheck_only"])
        self.assertFalse(hint["approval_to_call_model"])
        self.assertFalse(hint["orders"])

    def test_early5m_prompt_rejects_foreign_base_clock_fake_checks_or_paid_authority(self):
        from paper_evaluator.v3_experimental_paper_model_prompt_v1 import (
            build_v3_paper_full_model_prompt,
        )
        hint,x=full_inputs()
        mutations=(
            lambda y:y.update(kind="FAKE_EARLY_5M"),
            lambda y:y.update(approval_to_call_model=True),
            lambda y:y["checks"].update(fresh_eur_spread_guard=False),
            lambda y:y.update(snapshot_recheck_key="FORGED"),
            lambda y:y.update(fresh_close_at_utc=dt(100)),
            lambda y:y.update(prior_closed_15m_base_end_at_utc=dt(100)),
            lambda y:y.update(new_snapshot_known_at_utc=dt(100)),
            lambda y:y.update(baseline_v2r4_decision_unchanged=False),
            lambda y:y.update(new_closed_5m_bar_after_candidate=False),
        )
        for change in mutations:
            forged=copy.deepcopy(hint)
            change(forged)
            with self.subTest(change=str(change)):
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    build_v3_paper_full_model_prompt(
                        candidate=x[1],eligibility=forged,
                        entry_evidence=x[2],ticker=x[3],
                        pair_metadata=x[4],decision_at_utc=dt(13))

    def test_falsified_eligibility_or_source_cannot_buy(self):
        hint,x=full_inputs()
        changes=(
            lambda h:h["checks"].update(unchanged_closed_5m_volume_floor=False),
            lambda h:h.update(new_closed_5m_bar_after_candidate=False),
            lambda h:h.update(original_candidate_fresh=False),
            lambda h:h.update(kind="FAKE_PAPER_READY"),
            lambda h:h.update(prior_closed_15m_base_end_at_utc=dt(12)),
            lambda h:h.update(fresh_close_at_utc=dt(5)),
            lambda h:h.update(new_snapshot_known_at_utc=dt(100)),
        )
        for mutation in changes:
            y=copy.deepcopy(hint);mutation(y)
            result=validate_full_entry_decision(y,*x[1:],decision_at_utc=dt(13),
                                                slippage_pct_each_side=.08)
            self.assertNotEqual(result["decision"],"BUY_SCOUT")

    def test_missing_fresh_closed_5m_and_bad_stop_guard_fail_closed(self):
        for change in (
            lambda a:a[0].update(event_time_utc=dt(1)),
            lambda a:a[0].update(event_time_utc=dt(-1000)),
            lambda a:a[2]["frames"]["5"].update(last_closed_bar_end_utc=dt(-240)),
            lambda a:a[2]["frames"]["5"].update(status="STALE"),
            lambda a:a[2]["frames"]["5"].update(status="UNKNOWN"),
            lambda a:a[2]["frames"]["5"].update(volume_ratio_prior_5=1.1),
            lambda a:a[2]["frames"]["5"].update(volume_ratio_prior_5=float("nan")),
            lambda a:a[2]["frames"]["15"].update(last_closed_bar_end_utc=dt(0)),
            lambda a:a[2]["frames"]["15"].update(closed_close_eur=10.5),
            lambda a:a[2]["frames"]["15"].update(atr14_eur=None),
            lambda a:a[2]["frames"]["15"].update(recent_8bar_low_eur=None),
            lambda a:a[3].update(ask=10.99),
            lambda a:a[3].update(bid=9.8),
            lambda a:a[4][1].update(start_utc=BASE-3600),
            lambda a:a[1].update(setup_lane="EXTENDED"),
        ):
            h=run(change)
            with self.subTest(status=h["status"]):
                self.assertNotEqual(h["status"],ELIGIBLE)
                self.assertFalse(h["request_model_recheck_only"])
        self.assertEqual(run()["status"],
                         run(lambda a:a[2].update(optional_sources={"unknown":"NO_DATA"}))["status"])

    def test_cannot_promote_active_paper_via_early_research_import(self):
        root=Path(__file__).resolve().parents[1]
        for path in (
            "paper_evaluator/evaluate.py",
            "paper_evaluator/v2r4_wait_runtime.py",
            "paper_evaluator/v2r4_local_recheck.py",
            "tools/v2r4-paper-local-runtime.py",
        ):
            self.assertNotIn("v3_p3_early_5m_continuity_research_v1",
                             (root/path).read_text("utf-8"))


if __name__=="__main__":
    unittest.main()
