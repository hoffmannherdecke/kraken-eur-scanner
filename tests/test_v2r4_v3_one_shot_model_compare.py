"""No-secret, no-network, no-order tests for a physical Mini-PC V3 one-shot comparison."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator.v3_one_shot_model_compare import (
    select_fresh_handoff,freeze_runtime_provenance,clean_decision,execute_one_shot,
    discover_active_paper_runtime,
)
from tests.test_v2r4_v3_entry_handoff_probe import evidence,dt,BASE


def candidate(ts=BASE):
    dtv=datetime.fromtimestamp(ts,timezone.utc)
    stamp=dtv.strftime("%Y%m%d-%H%M%S")
    return {"candidate_id":f"{stamp}-XBT-EUR-r0","queue_id":f"0:XBT-EUR:{ts}",
            "source_scanner_run_id":0,"event_time_utc":dtv.isoformat(),
            "event_ts":ts,"pair":"XBT/EUR","altname":"XBTEUR",
            "action":"REVIEW_ONLY_NOT_ORDER","scanner_candidate":{},
            "scanner_market_context":{}}


class V3OneShotModelCompareTests(unittest.TestCase):
    def test_recent_actual_canonical_handoff_selection(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/(candidate()["candidate_id"]+".json")
            path.write_text(json.dumps(candidate()))
            control={"series_started_at_utc":dt(-1800)}
            self.assertIsNotNone(select_fresh_handoff(
                Path(d),control,observed_now=datetime.fromtimestamp(BASE+130,timezone.utc)))
            self.assertIsNone(select_fresh_handoff(
                Path(d),control,observed_now=datetime.fromtimestamp(BASE+901,timezone.utc)))
            self.assertIsNone(select_fresh_handoff(
                Path(d),{"series_started_at_utc":dt(10)},
                observed_now=datetime.fromtimestamp(BASE+120,timezone.utc)))

    def test_runtime_provenance_rejects_code_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            live=root/"live";src=root/"src"
            for sub in (live,src):
                (sub/"paper_evaluator").mkdir(parents=True)
                (sub/"paper_context.py").write_text("exact")
                (sub/"paper_evaluator/evaluate.py").write_text("frozen")
            control={"enabled":True,"real_money_actions_enabled":False,
                     "strategy_revision":"V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"}
            self.assertEqual(len(freeze_runtime_provenance(live,src,control)),2)
            (src/"paper_context.py").write_text("modified")
            with self.assertRaisesRegex(ValueError,"differs"):
                freeze_runtime_provenance(live,src,control)

    def test_raw_paper_buy_never_creates_position(self):
        c={"decision":"BUY_SCOUT","setup_lane":"CONTINUITY","reason_codes":[],
           "missing_triggers":[],"stop_eur":9.2,"stage2_trigger_eur":11.0,
           "stage2_ttl_minutes":20,"ttl_minutes":0,"watch_conditions":[],
           "expected_remaining_move_pct":6.0,"risk_reward_after_costs":2.0}
        current={"ask":10.0,"bid":9.99,"spread_pct":.1}
        external={"kraken_pair_metadata":{"available":True,"status":"online",
                         "ordermin":".0001","costmin":".45"}}
        d=clean_decision(c,current,external,{"entry":{"scout_notional_eur":50,
                                     "stage2_notional_eur":50}})
        self.assertEqual(d["decision"],"BUY_SCOUT")
        self.assertTrue(d["valid_stop_below_ask"])
        self.assertTrue(d["valid_stage2_above_ask"])
        self.assertNotIn("paper_entry",d)

    def test_readonly_diagnostic_stops_before_secrets_and_models(self):
        # A genuine research candidate+public-input preparation is allowed.
        # No key file exists, and any model call is a hard test failure.
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            app=home/"Runtime/v2r4-paper-stage-d8b35a8ec2e6"
            app.mkdir(parents=True)
            ctrl={"enabled":True,"paper_only":True,"real_money_actions_enabled":False,
                  "strategy_revision":"V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
                  "series_id":"PAPER-V2R4-TEST-SERIES",
                  "series_started_at_utc":dt(-1800),
                  "release_repo_sha":"d8b35a8ec2e6"+"0"*28}
            (app/"paper_runtime_control.json").write_text(json.dumps(ctrl))
            (app/"paper_strategy_spec.json").write_text("{}")
            ticker={"ask":10,"bid":9.99,"last":10,"spread_pct":0.1}
            with patch("paper_evaluator.v3_one_shot_model_compare.freeze_runtime_provenance",return_value={"evaluate.py":"test"}), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.select_fresh_handoff",return_value=(Path("mock.json"),candidate())), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.evaluate.kraken_ticker",return_value=ticker), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.build_context",return_value={"kraken_execution_ticker":ticker}), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.fetch_public_entry_evidence",return_value=evidence()), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.now_utc",return_value=dt(14)), \\
                 patch("paper_evaluator.v3_one_shot_model_compare.evaluate.call_evaluator",side_effect=AssertionError("MODEL_MUST_NOT_BE_CALLED")):
                result=execute_one_shot(home,home,"PAPER-V2R4-TEST-SERIES",diagnose_only=True)
            self.assertEqual(result["status"],"INPUT_READY_NO_MODEL_CALLS_NOT_A_STRATEGY_PASS")
            self.assertEqual(result["model_calls"],0)
            self.assertFalse(result["secret_read"])
            self.assertFalse(result["orders"])
            self.assertFalse(result["active_v2r4_changed"])

    def test_safe_failure_stage_does_not_expose_raw_exception(self):
        from paper_evaluator.v3_one_shot_model_compare import checked, PreflightStageError
        def failed():
            raise ValueError("candidate entry evidence incomplete; secret=DO_NOT_PRINT")
        with self.assertRaises(PreflightStageError) as failure:
            checked("COIN_INPUT_ATTACH",failed)
        self.assertEqual(failure.exception.phase,"COIN_INPUT_ATTACH")
        self.assertEqual(failure.exception.safe_reason,"COIN_BARS_INCOMPLETE_OR_STALE")
        self.assertNotIn("DO_NOT_PRINT",str(failure.exception))


    def test_active_technical_stage_must_match_exact_series_and_release_hash(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            legacy=home/"Runtime/v2r4-paper-app"
            legacy.mkdir(parents=True)
            (legacy/"paper_runtime_control.json").write_text('{"series_id":"OLD-FROZEN-DO-NOT-SELECT"}')
            stage=home/"Runtime/v2r4-paper-stage-d8b35a8ec2e6"
            stage.mkdir()
            c={"series_id":"PAPER-V2R4-20261009T110135Z",
               "paper_only":True,"enabled":True,"real_money_actions_enabled":False,
               "release_repo_sha":"d8b35a8ec2e6"+"0"*28}
            (stage/"paper_runtime_control.json").write_text(json.dumps(c))
            path,pinned=discover_active_paper_runtime(home,"PAPER-V2R4-20261009T110135Z")
            self.assertEqual(path,stage)
            self.assertEqual(pinned["series_id"],c["series_id"])
            with self.assertRaises(ValueError):
                discover_active_paper_runtime(home,"PAPER-V2R4-20261007T184255Z")
            c["release_repo_sha"]="0"*40
            (stage/"paper_runtime_control.json").write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,"mismatch"):
                discover_active_paper_runtime(home,"PAPER-V2R4-20261009T110135Z")

    def test_stage_selection_rejects_multiple_active_stage_writers(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            s1=home/"Runtime/v2r4-paper-stage-d8b35a8ec2e6"
            s1.mkdir(parents=True)
            (s1/"paper_runtime_control.json").write_text(json.dumps({
                "series_id":"PAPER-V2R4-20261009T110135Z",
                "enabled":True,"paper_only":True,
                "real_money_actions_enabled":False,
                "release_repo_sha":"d8b35a8ec2e6"+"0"*28}))
            s2=home/"Runtime/v2r4-paper-stage-aaaaaaaaaaaa"
            s2.mkdir()
            (s2/"paper_runtime_control.json").write_text('{"series_id":"OTHER-ACTIVE"}')
            with self.assertRaisesRegex(ValueError,"exactly one"):
                discover_active_paper_runtime(home,"PAPER-V2R4-20261009T110135Z")

    def test_two_real_model_call_boundaries_offline_only(self):
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);app=home/"Runtime/v2r4-paper-stage-d8b35a8ec2e6";app.mkdir(parents=True)
            (home/"Secrets").mkdir()
            (home/"Secrets/openai-api-key.txt").write_text("MOCK_ONLY_NOT_A_REAL_TOKEN_12345")
            control={"enabled":True,"real_money_actions_enabled":False,
                     "strategy_revision":"V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
                     "paper_only":True,"release_repo_sha":"d8b35a8ec2e6"+"0"*28,
                     "series_started_at_utc":dt(-1800),"series_id":"PAPER-V2R4-TEST-SERIES"}
            (app/"paper_runtime_control.json").write_text(json.dumps(control))
            (app/"paper_strategy_spec.json").write_text(json.dumps(
                 {"entry":{"scout_notional_eur":50,"stage2_notional_eur":50}}))
            base={"kraken_pair_metadata":{"available":True,"status":"online",
                         "ordermin":".0001","costmin":".45"}}
            fake={"decision":"REJECT","setup_lane":"NONE","reason_codes":["MOCK"],
                  "missing_triggers":[],"stop_eur":None,"stage2_trigger_eur":None,
                  "stage2_ttl_minutes":0,"ttl_minutes":0,"watch_conditions":[],
                  "expected_remaining_move_pct":None,"risk_reward_after_costs":None}
            inputs=[]
            def ai(c,t,external,spec,control):
                inputs.append(external)
                return fake,{"response_id":"STUB_NO_API"}
            with patch("paper_evaluator.v3_one_shot_model_compare.freeze_runtime_provenance",return_value={"evaluator":"hash"}), \
                 patch("paper_evaluator.v3_one_shot_model_compare.select_fresh_handoff",return_value=(Path("mock.json"),candidate())), \
                 patch("paper_evaluator.v3_one_shot_model_compare.evaluate.kraken_ticker",return_value={"ask":10,"bid":9.99,"last":10,"spread_pct":.1}), \
                 patch("paper_evaluator.v3_one_shot_model_compare.build_context",return_value=base), \
                 patch("paper_evaluator.v3_one_shot_model_compare.fetch_public_entry_evidence",return_value=evidence()), \
                 patch("paper_evaluator.v3_one_shot_model_compare.now_utc",return_value=dt(14)), \
                 patch("paper_evaluator.v3_one_shot_model_compare.evaluate.call_evaluator",side_effect=ai):
                result=execute_one_shot(home,home,"PAPER-V2R4-TEST-SERIES")
            self.assertEqual(result["model_calls"],2)
            self.assertNotIn("candidate_entry_evidence",inputs[0])
            self.assertIn("candidate_entry_evidence",inputs[1])
            self.assertEqual(result["baseline"]["decision"],"REJECT")
            self.assertEqual(result["successor_with_coin_evidence"]["decision"],"REJECT")
            self.assertFalse(result["valid_paper_trade_proven"])
            self.assertFalse(result["economic_edge_proven"])
            self.assertFalse(result["active_v2r4_changed"])

if __name__=="__main__":unittest.main()
