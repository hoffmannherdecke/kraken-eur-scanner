import json
import unittest

from paper_evaluator.evaluate import apply_public_tradability_gate
from paper_evaluator.v2r4_local_recheck import make_paper_entry


class V2R4SpecRuntimeCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open("research/v2r4/paper_strategy_spec_v2r4_proposed.json","r",encoding="utf-8") as fh:
            cls.spec=json.load(fh)

    def test_executable_default_sizing_exists(self):
        self.assertEqual(self.spec["entry"]["scout_notional_eur"],75)
        self.assertEqual(self.spec["entry"]["stage2_notional_eur"],75)

    def test_public_tradability_gate_accepts_proposed_spec_shape(self):
        d={
            "decision":"BUY_SCOUT",
            "setup_lane":"IGNITION",
            "summary":"synthetic",
            "reason_codes":[],
            "missing_triggers":[],
            "watch_conditions":[],
            "stop_eur":0.9,
            "ttl_minutes":0,
            "expected_remaining_move_pct":5.0,
            "risk_reward_after_costs":2.0,
            "stage2_trigger_eur":1.1,
            "stage2_ttl_minutes":30,
        }
        out=apply_public_tradability_gate(
            d,
            {"ask":1.0},
            {"kraken_pair_metadata":{"available":True,"status":"online","ordermin":"1","costmin":"0.45"}},
            self.spec,
        )
        self.assertEqual(out["decision"],"BUY_SCOUT")

    def test_local_recheck_paper_entry_uses_proposed_spec(self):
        d={"stop_eur":0.9,"stage2_trigger_eur":1.1,"stage2_ttl_minutes":30}
        entry=make_paper_entry(
            d,
            {"ask":1.0,"spread_pct":0.1},
            self.spec,
            "2026-09-30T21:00:00Z",
        )
        self.assertEqual(entry["scout_notional_eur"],75)
        self.assertEqual(entry["stage2_plan"]["notional_eur"],75)
        self.assertTrue(entry["status"].startswith("SCOUT_FILLED_SIMULATED"))


if __name__=="__main__":
    unittest.main()
