"""Offline V3 complete entry-input handoff proof: source -> guarded context -> evaluator prompt.

Never run real model or orders. Mocked BUY is contract-only, NOT an observed trade.
"""
import copy
import json
import os
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch

from paper_evaluator.v3_entry_handoff_probe import attach_to_future_evaluator
from paper_evaluator.successor_coin_entry_evidence_v1 import build_entry_evidence
from paper_evaluator import evaluate

BASE=1791550800

def candles(interval,n=24):
    span=interval*60
    out=[]
    for i in range(n):
        ts=BASE - n*span + i*span
        p=10 + 0.01*i
        out.append([ts,str(p),str(p+.08),str(p-.08),str(p+.005),str(p+.005),"100","9"])
    out.append([BASE,"999","1000","998","999","999","999999","1"])
    return out

def evidence():
    return build_entry_evidence("XBT/EUR",{k:candles(k) for k in (1,5,15)},
      observed_at_utc=datetime.fromtimestamp(BASE,timezone.utc).isoformat(),
      known_at_utc=datetime.fromtimestamp(BASE+7,timezone.utc).isoformat())

def dt(seconds):
    return datetime.fromtimestamp(BASE+seconds,timezone.utc).isoformat()

class V3EntryInputHandoffTests(unittest.TestCase):
    def test_real_evaluator_prompt_receives_candidate_specific_closed_features(self):
        e=evidence()
        self.assertEqual(e["status"],"COMPLETE")
        base={"major_market_regime":{"available_assets":3},"derivatives":{"available":False}}
        candidate={"pair":"XBT/EUR","altname":"XBTEUR"}
        external=attach_to_future_evaluator(candidate,base,e,dt(12))
        self.assertEqual(base,{"major_market_regime":{"available_assets":3},"derivatives":{"available":False}})
        self.assertIs(external["candidate_entry_evidence"],e)
        assert external["candidate_entry_evidence"]["frames"]["15"]["atr14_eur"] > 0
        canned={"decision":"REJECT","setup_lane":"NONE","summary":"offline model-stub demonstration",
          "reason_codes":["MODEL_STUB_ONLY"],"missing_triggers":[],"stop_eur":None,"ttl_minutes":0,
          "expected_remaining_move_pct":None,"risk_reward_after_costs":None,
          "stage2_trigger_eur":None,"stage2_ttl_minutes":0,"watch_conditions":[]}
        captured=[]
        def transport(url,method,headers,body,timeout):
            request=json.loads(body.decode("utf-8"))
            captured.append(request)
            return {"id":"OFFLINE_TEST_NO_REAL_MODEL","model":"mock",
              "output":[{"content":[{"type":"output_text","text":json.dumps(canned)}]}]}
        with patch.dict(os.environ,{"OPENAI_API_KEY":"OFFLINE_STUB_NOT_SECRET"}):
            with patch("paper_evaluator.evaluate.http_json",side_effect=transport):
                decision,info=evaluate.call_evaluator(
                    candidate,{"ask":10.24,"bid":10.23,"last":10.24,"spread_pct":0.1},
                    external,{"strategy_revision":"INACTIVE-V3-INPUT-PROBE"},
                    {"series_id":"INACTIVE-MOCK-SERIES"})
        self.assertEqual(decision["decision"],"REJECT")
        self.assertEqual(info["response_id"],"OFFLINE_TEST_NO_REAL_MODEL")
        self.assertEqual(len(captured),1)
        prompt=captured[0]["input"]
        self.assertIn("candidate_entry_evidence",prompt)
        self.assertIn("atr14_eur",prompt)
        self.assertIn("known_at_utc",prompt)
        self.assertIn("volume_ratio_prior_5",prompt)
        self.assertIn("major_market_regime",prompt)
        self.assertNotIn("BUY_SCOUT_ONLY",prompt)

    def test_mock_buy_plan_is_contract_only_not_promotion_evidence(self):
        # Validated raw format is a capability smoke, not model prediction.
        fake={"decision":"BUY_SCOUT","setup_lane":"CONTINUITY","summary":"canned stub",
              "reason_codes":[],"missing_triggers":[],"stop_eur":9.8,
              "ttl_minutes":0,"expected_remaining_move_pct":6.0,
              "risk_reward_after_costs":2.0,"stage2_trigger_eur":10.8,
              "stage2_ttl_minutes":20,"watch_conditions":[]}
        normalized=evaluate.fail_safe_normalize(fake,{"ask":10.2,"spread_pct":0.1})
        self.assertEqual(normalized["decision"],"BUY_SCOUT")
        self.assertEqual(normalized["stage2_trigger_eur"],10.8)
        self.assertFalse(any("promot" in k for k in evidence()))

    def test_partial_source_is_not_misclassified_as_certain_reject(self):
        e=evidence();e["status"]="PARTIAL_OR_MISSING";e["frames"]["5"]["status"]="MISSING"
        with self.assertRaisesRegex(ValueError,"incomplete"):
            attach_to_future_evaluator({"pair":"XBT/EUR"},{},e,dt(14))

    def test_pair_duplicate_and_future_data_guard(self):
        e=evidence()
        with self.assertRaisesRegex(ValueError,"pair mismatch"):
            attach_to_future_evaluator({"pair":"ETH/EUR"},{},e,dt(14))
        with self.assertRaisesRegex(ValueError,"duplicate"):
            attach_to_future_evaluator({"pair":"XBT/EUR"},{"candidate_entry_evidence":{}},e,dt(14))
        with self.assertRaisesRegex(ValueError,"future-known"):
            attach_to_future_evaluator({"pair":"XBT/EUR"},{},e,dt(3))
        with self.assertRaisesRegex(ValueError,"stale"):
            attach_to_future_evaluator({"pair":"XBT/EUR"},{},e,dt(150))

    def test_invalid_volume_atr_or_candle_age_cannot_be_considered_full_evidence(self):
        for field,interval,value in [("volume_ratio_prior_5","1",None),
                                     ("atr14_eur","15",None),
                                     ("last_closed_bar_end_utc","1",dt(13))]:
            e=evidence()
            e["frames"][interval][field]=value
            with self.assertRaises(ValueError):
                attach_to_future_evaluator({"pair":"XBT/EUR"},{},e,dt(15))

    def test_existing_v2r4_evaluator_does_not_import_future_adapter(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        active=(root/"paper_evaluator/evaluate.py").read_text("utf-8")
        local=(root/"paper_evaluator/v2r4_local_recheck.py").read_text("utf-8")
        self.assertNotIn("v3_entry_handoff_probe",active)
        self.assertNotIn("v3_entry_handoff_probe",local)
        self.assertNotIn("successor_coin_entry_evidence_v1",active)
        self.assertNotIn("successor_coin_entry_evidence_v1",local)

if __name__ == "__main__":
    unittest.main()
