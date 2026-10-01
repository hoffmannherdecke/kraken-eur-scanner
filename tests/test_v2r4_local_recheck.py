import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v2r4_local_recheck as bridge


class V2R4LocalRecheckTests(unittest.TestCase):
    def candidate(self, root: Path):
        p = root / "20260930-210000-BTC-EUR-r0.json"
        d = {
            "candidate_id": p.stem,
            "queue_id": "0:BTC-EUR:1790802000",
            "source_scanner_run_id": 0,
            "event_time_utc": "2026-09-30T21:00:00Z",
            "event_ts": 1790802000,
            "pair": "BTC/EUR",
            "altname": "XBTEUR",
            "action": "REVIEW_ONLY_NOT_ORDER",
            "scanner_candidate": {"price": 1.0},
            "scanner_market_context": {"sensor_price_eur": 1.0},
        }
        p.write_text(json.dumps(d), "utf-8")
        return p, d

    def receipt(self, root: Path, candidate: dict):
        p = root / "receipt.json"
        d = {
            "kind": "V2R4_PAPER_WAIT_TRIGGER_RECEIPT",
            "paper_only": True,
            "candidate_id": candidate["candidate_id"],
            "pair": candidate["pair"],
            "observed_at_utc": "2026-09-30T21:00:10Z",
            "matched": True,
            "expired": False,
            "reason": "MATCH_REQUIRES_FRESH_PAPER_RECHECK",
            "condition_results": [True],
            "metrics": {"spread_pct": 0.1},
            "next_action": "FRESH_PAPER_RECHECK_ONLY",
            "real_money_actions_enabled": False,
        }
        p.write_text(json.dumps(d), "utf-8")
        return p

    def spec_control(self, root: Path):
        spec = root / "spec.json"
        spec.write_text(json.dumps({
            "strategy_revision": "V2R4-TEST",
            "paper_only": True,
            "real_money_actions_enabled": False,
            "entry": {
                "scout_notional_eur": 75,
                "stage2_notional_eur": 75,
            },
        }), "utf-8")
        control = root / "control.json"
        control.write_text(json.dumps({
            "enabled": True,
            "test_id": "V2R4-TEST",
            "series_id": "PAPER-V2R4-TEST",
            "target_completed_paper_trades": 20,
            "real_money_actions_enabled": False,
        }), "utf-8")
        return spec, control

    def test_receipt_rejects_unsafe_next_action(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _, candidate = self.candidate(root)
            receipt = {
                "kind": "V2R4_PAPER_WAIT_TRIGGER_RECEIPT",
                "paper_only": True,
                "candidate_id": candidate["candidate_id"],
                "pair": candidate["pair"],
                "matched": True,
                "expired": False,
                "next_action": "BUY_NOW",
                "real_money_actions_enabled": False,
            }
            with self.assertRaises(ValueError):
                bridge.validate_trigger_receipt(receipt, candidate)

    def test_happy_path_writes_paper_only_recheck_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            candidate_path, candidate = self.candidate(root)
            receipt_path = self.receipt(root, candidate)
            spec_path, control_path = self.spec_control(root)
            out_dir = root / "out"

            raw = {
                "decision": "REJECT",
                "setup_lane": "NONE",
                "summary": "synthetic",
                "reason_codes": ["SYNTHETIC"],
                "missing_triggers": [],
                "watch_conditions": [],
                "stop_eur": None,
                "ttl_minutes": 0,
                "expected_remaining_move_pct": None,
                "risk_reward_after_costs": None,
                "stage2_trigger_eur": None,
                "stage2_ttl_minutes": 0,
            }
            ticker = {"bid": 1.0, "ask": 1.01, "last": 1.0, "spread_pct": 0.1}

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-abcdefghijklmnopqrstuvwxyz"}, clear=False):
                with patch.object(bridge, "kraken_ticker", return_value=ticker), \
                     patch.object(bridge, "build_context", return_value={"kraken_pair_metadata": {"available": True, "status": "online", "ordermin": "1", "costmin": "0.45"}}), \
                     patch.object(bridge, "enrich_derivatives_delta", side_effect=lambda x, *_: x), \
                     patch.object(bridge, "call_evaluator", return_value=(raw, {"response_id": "r1", "model": "test", "attempt": 1})):
                    target = bridge.run_recheck(
                        candidate_path=candidate_path,
                        receipt_path=receipt_path,
                        spec_path=spec_path,
                        control_path=control_path,
                        out_dir=out_dir,
                        api_key_file=None,
                    )

            record = json.loads(target.read_text("utf-8"))
            self.assertEqual(record["decision"]["decision"], "REJECT")
            self.assertTrue(record["paper_only"])
            self.assertFalse(record["real_money_actions_enabled"])
            self.assertFalse(record["order_api"])
            self.assertIsNone(record["paper_entry"])


if __name__ == "__main__":
    unittest.main()
