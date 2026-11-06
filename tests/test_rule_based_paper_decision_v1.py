"""Closed-candle free-paper rule regressions; never touch OpenAI or Kraken."""
import copy
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from paper_evaluator import evaluate
from paper_evaluator.rule_based_paper_decision_v1 import assess

NOW = datetime(2026,11,6,20,0,0,tzinfo=timezone.utc)


def iso(seconds):
    return (NOW+timedelta(seconds=seconds)).isoformat().replace("+00:00","Z")


def fixture(*,volume=1.5,c1=100.0,c5=99.9,c15=99.4,atr=2.0):
    candidate = {
        "candidate_id": "20261106-195800-BTC-EUR-r12",
        "event_time_utc": iso(-120), "action": "REVIEW_ONLY_NOT_ORDER",
        "pair": "BTC/EUR", "altname": "XBTEUR"
    }
    quote = {"ask":100.0,"bid":99.9,"last":99.9,"spread_pct":0.1}
    def frame(interval, close, age, **extra):
        return dict(status="VALID",interval_min=interval,
                    closed_close_eur=close,last_closed_bar_end_utc=iso(-age),
                    volume_ratio_prior_5=volume,**extra)
    evidence = {
        "kind": "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
        "pair": "BTC/EUR", "status": "COMPLETE",
        "observed_at_utc": iso(-12), "known_at_utc": iso(-5),
        "frames": {
            "1": frame(1,c1,60),
            "5": frame(5,c5,300,closed_high_eur=100.0),
            "15": frame(15,c15,900,atr14_eur=atr,recent_8bar_low_eur=97.0)
        }
    }
    context = {"kraken_pair_metadata":{"available":True,"status":"online",
                "ordermin":"0.01","costmin":"0.45"},
               "candidate_entry_evidence":evidence}
    spec = {"real_money_actions_enabled":False,
            "entry":{"scout_notional_eur":50,"stage2_notional_eur":50}}
    control = {"real_money_actions_enabled":False,"series_id":"PAPER-V2R4-test",
               "target_completed_paper_trades":20}
    return candidate,quote,context,spec,control


class FreeRuleTests(unittest.TestCase):
    def test_realistic_closed_continuation_can_buy_paper(self):
        args=fixture()
        decision=assess(*args,decision_at_utc=iso(0))
        self.assertEqual(decision["decision"],"BUY_SCOUT")
        self.assertGreater(decision["stage2_trigger_eur"],args[1]["ask"])
        self.assertLess(decision["stop_eur"],args[1]["ask"])
        self.assertGreater(decision["risk_reward_after_costs"],1.5)
        evaluate.common_validate(decision)
        self.assertEqual(evaluate.fail_safe_normalize(decision,args[1])["decision"],"BUY_SCOUT")
        self.assertEqual(evaluate.apply_public_tradability_gate(decision,args[1],args[2],args[3])["decision"],"BUY_SCOUT")

    def test_structured_wait_and_no_immediate_buy(self):
        args=fixture(volume=0.9,c1=99.4)
        d=assess(*args,decision_at_utc=iso(0))
        self.assertEqual(d["decision"],"WAIT")
        self.assertEqual(len(d["watch_conditions"]),2)
        self.assertEqual(d["ttl_minutes"],30)
        evaluate.common_validate(d)
        from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan
        plan=build_wait_trigger_plan(args[0],d,iso(0))
        self.assertEqual(plan["on_match"],"FRESH_PAPER_RECHECK_ONLY")

    def test_missing_stale_and_bad_guard_sources_cannot_buy(self):
        for kind in ("missing","stale","future","bad_pair","volume","spread","stop","no_authority"):
            args=list(fixture())
            args[2]=copy.deepcopy(args[2])
            args[0]=dict(args[0])
            args[1]=dict(args[1])
            if kind=="missing": args[2].pop("candidate_entry_evidence")
            if kind=="stale": args[2]["candidate_entry_evidence"]["known_at_utc"]=iso(-200)
            if kind=="future": args[2]["candidate_entry_evidence"]["known_at_utc"]=iso(10)
            if kind=="bad_pair": args[2]["candidate_entry_evidence"]["pair"]="ETH/EUR"
            if kind=="volume": args[2]["candidate_entry_evidence"]["frames"]["5"]["volume_ratio_prior_5"]=None
            if kind=="spread": args[1]["spread_pct"]=1.0
            if kind=="stop": args[2]["candidate_entry_evidence"]["frames"]["15"]["recent_8bar_low_eur"]=101
            if kind=="no_authority": args[3]["real_money_actions_enabled"]=True
            with self.subTest(kind=kind):
                d=assess(*args,decision_at_utc=iso(0))
                self.assertEqual(d["decision"],"REJECT")
                self.assertIsNone(d["stop_eur"])

    def test_wait_recheck_requires_fresh_matching_receipt(self):
        args=list(fixture())
        args[0]=dict(args[0], candidate_id="20261106-193000-BTC-EUR-r12",
                     event_time_utc=iso(-1800))
        receipt={
            "kind":"V2R4_PAPER_WAIT_TRIGGER_RECEIPT",
            "candidate_id":args[0]["candidate_id"],"pair":"BTC/EUR",
            "paper_only":True,"matched":True,"expired":False,
            "real_money_actions_enabled":False,
            "next_action":"FRESH_PAPER_RECHECK_ONLY",
            "observed_at_utc":iso(-10),
        }
        args[0]["v2r4_fresh_recheck_context"]={
            "kind":"V2R4_TRIGGERED_FRESH_PAPER_RECHECK",
            "trigger_receipt":receipt}
        d=assess(*args,decision_at_utc=iso(0))
        self.assertEqual(d["decision"],"BUY_SCOUT")
        bad=copy.deepcopy(args)
        bad[0]["v2r4_fresh_recheck_context"]["trigger_receipt"]["observed_at_utc"]=iso(-500)
        self.assertEqual(assess(*bad,decision_at_utc=iso(0))["decision"],"REJECT")

    def test_normal_entrypoint_cannot_send_paid_api(self):
        args=list(fixture())
        # The production evaluator accepts evidence already validated by the
        # original closed-candle adapter; no network is needed in this case.
        with patch.object(evaluate,"http_json",side_effect=AssertionError("HTTP invoked")):
            with patch("paper_evaluator.rule_based_paper_decision_v1.datetime") as dt:
                dt.now.return_value=NOW
                dt.fromisoformat.side_effect=datetime.fromisoformat
                dt.timezone=timezone
                d,m=evaluate.call_evaluator(*args)
        self.assertEqual(d["decision"],"BUY_SCOUT")
        self.assertIsNone(m["response_id"])
        self.assertEqual(m["attempt"],0)
        self.assertIsNone(m["model"])


if __name__=="__main__":
    unittest.main()
