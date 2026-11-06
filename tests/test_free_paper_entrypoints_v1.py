"""Offline real entrypoint tests: Candidates and WAIT, no paid-model HTTP."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import evaluate, v2r4_local_recheck as bridge
from tests.test_rule_based_paper_decision_v1 import fixture, iso, NOW


def canonical(root):
    c,q,context,spec,control=fixture()
    c.update({
        "queue_id":f"12:BTC-EUR:{int(datetime.fromisoformat(iso(-120).replace('Z','+00:00')).timestamp())}",
        "source_scanner_run_id":12,
        "event_ts":int(datetime.fromisoformat(iso(-120).replace("Z","+00:00")).timestamp()),
        "scanner_candidate":{"source":"test"},
        "scanner_market_context":{"source":"test"},
    })
    p=root/(c["candidate_id"]+".json")
    p.write_text(json.dumps(c),"utf-8")
    spec.update(strategy_revision="V2R4-TEST",paper_only=True)
    control.update(enabled=True,test_id="V2R4-TEST",
                   series_started_at_utc=iso(-3600))
    return p,c,q,context,spec,control


class FullZeroCostEntrypoint(unittest.TestCase):
    def test_candidate_main_persists_real_rule_output_without_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            path,c,q,context,spec,control=canonical(root)
            out=root/"decisions"
            with patch.object(evaluate,"load_runtime",return_value=(control,spec,"test-fp")), \
                 patch.object(evaluate,"kraken_ticker",return_value=q), \
                 patch.object(evaluate,"build_context",return_value=context), \
                 patch.object(evaluate,"enrich_derivatives_delta",side_effect=lambda x,*_:x), \
                 patch.object(evaluate,"runtime_code_fingerprint",return_value="test-code"), \
                 patch.object(evaluate,"http_json",side_effect=AssertionError("paid network called")), \
                 patch("paper_evaluator.rule_based_paper_decision_v1.datetime") as dt, \
                 patch("paper_evaluator.evaluate.time.time",return_value=NOW.timestamp()), \
                 patch("sys.argv",["evaluate.py",str(path),"--out",str(out)]):
                dt.now.return_value=NOW
                dt.fromisoformat.side_effect=datetime.fromisoformat
                evaluate.main()
            record=json.loads((out/path.name).read_text("utf-8"))
            self.assertEqual(record["decision"]["decision"],"BUY_SCOUT")
            self.assertEqual(record["evaluator"]["attempt"],0)
            self.assertIsNone(record["evaluator"]["response_id"])
            self.assertIsNotNone(record["paper_entry"])
            self.assertIn("candidate_entry_evidence",record["decision_context"])

    def test_wait_recheck_executes_validated_trigger_without_model(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            path,c,q,context,spec,control=canonical(root)
            rp=root/"receipt.json";sp=root/"spec.json";cp=root/"control.json"
            receipt={
                "kind":"V2R4_PAPER_WAIT_TRIGGER_RECEIPT",
                "paper_only":True,"candidate_id":c["candidate_id"],"pair":c["pair"],
                "matched":True,"expired":False,
                "next_action":"FRESH_PAPER_RECHECK_ONLY",
                "observed_at_utc":iso(-10),
                "real_money_actions_enabled":False,
            }
            rp.write_text(json.dumps(receipt),"utf-8")
            sp.write_text(json.dumps(spec),"utf-8")
            cp.write_text(json.dumps(control),"utf-8")
            with patch.object(bridge,"kraken_ticker",return_value=q), \
                 patch.object(bridge,"build_context",return_value=context), \
                 patch.object(bridge,"enrich_derivatives_delta",side_effect=lambda x,*_:x), \
                 patch.object(evaluate,"http_json",side_effect=AssertionError("paid network called")), \
                 patch("paper_evaluator.rule_based_paper_decision_v1.datetime") as dt:
                dt.now.return_value=NOW
                dt.fromisoformat.side_effect=datetime.fromisoformat
                target=bridge.run_recheck(candidate_path=path,receipt_path=rp,
                    spec_path=sp,control_path=cp,out_dir=root/"out",
                    api_key_file=root/"unreadable-secret-never-used.txt")
            record=json.loads(target.read_text("utf-8"))
            self.assertTrue(record["paper_only"])
            self.assertFalse(record["order_api"])
            self.assertEqual(record["decision"]["decision"],"BUY_SCOUT")
            self.assertEqual(record["evaluator"]["attempt"],0)
            self.assertIsNone(record["evaluator"]["response_id"])


if __name__=="__main__":
    unittest.main()
