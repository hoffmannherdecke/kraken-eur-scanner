"""Offline tests for one-time V3 P3 Standard/Experimental HTTP10/6h gate."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator.v3_p3_ab_five_bounded_research import (
    APPROVAL, APPROVAL_LABEL, EXPECTED_SERIES, MAX_HTTP, MAX_MINUTES,
    MAX_SETUPS, BudgetExhausted, guarded_http, require_authority,
    verified_spot_metadata, run_one,
)


ROOT = Path(__file__).resolve().parents[1]


class V3P3ABFiveGuardTests(unittest.TestCase):
    def test_real_explicit_approval_is_exactly_bounded(self):
        a = require_authority(ROOT)
        self.assertEqual(a["approval_label"], APPROVAL_LABEL)
        self.assertEqual(a["max_qualified_setups"], 5)
        self.assertEqual(a["max_model_http_attempts_including_retries"], 10)
        self.assertEqual(a["max_observation_minutes"], 360)
        self.assertEqual(a["hard_guards"]["scout_eur"], 50)
        self.assertEqual(a["hard_guards"]["stage2_eur"], 50)
        self.assertEqual(a["hard_guards"]["fee_pct_each_side"], .6)

    def test_negative_approval_budget_paper_and_time_guards(self):
        original = json.loads((ROOT / APPROVAL).read_text("utf-8"))
        for edit in (
            lambda x: x.update(max_model_http_attempts_including_retries=11),
            lambda x: x.update(max_observation_minutes=361),
            lambda x: x.update(max_qualified_setups=6),
            lambda x: x["hard_guards"].update(no_paper_writer=False),
            lambda x: x["hard_guards"].update(no_real_money=False),
            lambda x: x["hard_guards"].update(fee_pct_each_side=0.1),
            lambda x: x.update(approval_label="REUSE_OLD_V3B_APPROVAL"),
        ):
            with tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                target = base / APPROVAL
                target.parent.mkdir(parents=True)
                changed = copy.deepcopy(original)
                edit(changed)
                target.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(ValueError):
                    require_authority(base)

    def test_http_budget_reservation_before_requests_and_retries(self):
        journal = {"model_http_attempts_reserved": 0}
        calls = []
        with patch("paper_evaluator.v3_p3_ab_five_bounded_research.checkpoint") as ck:
            for i in range(MAX_SETUPS):
                case = {"model_http_attempts_reserved": 0}
                def transport(url, method, headers, body, timeout):
                    calls.append(url)
                    return {"ok": True}
                gate = guarded_http(journal, Path("/tmp/report.json"), case, transport)
                for _ in range(2):
                    self.assertEqual(gate("https://api.openai.com/v1/responses", "POST"), {"ok": True})
                with self.assertRaises(BudgetExhausted):
                    gate("https://api.openai.com/v1/responses", "POST")
                self.assertEqual(case["model_http_attempts_reserved"], 2)
            self.assertEqual(journal["model_http_attempts_reserved"], MAX_HTTP)
            self.assertEqual(len(calls), MAX_HTTP)
            self.assertEqual(ck.call_count, MAX_HTTP)
            another = {"model_http_attempts_reserved": 0}
            with self.assertRaises(BudgetExhausted):
                guarded_http(journal, Path("/tmp/report.json"), another, transport)(
                    "https://api.openai.com/v1/responses", "POST")

    def test_assetpairs_requires_real_online_spot_eur_and_public_minimum(self):
        good = {"error": [], "result": {"key": {
            "wsname": "XBT/EUR", "quote": "ZEUR", "status": "online",
            "ordermin": "0.001", "costmin": "5"}}}
        ticker = {"ask": 10.24}
        with patch("paper_evaluator.v3_p3_ab_five_bounded_research.evaluate.http_json",
                   return_value=good):
            m = verified_spot_metadata("XBTEUR", "XBT/EUR", ticker)
            self.assertTrue(m["minimum_order_passed"])
            self.assertEqual(m["status"], "online")
            self.assertEqual(m["quote"], "EUR")
        for invalid in (
            {"wsname": "XBT/USD"}, {"quote": "ZUSD"},
            {"status": "cancel_only"}, {"costmin": "100"},
            {"ordermin": "100"},
        ):
            data = copy.deepcopy(good)
            data["result"]["key"].update(invalid)
            with patch("paper_evaluator.v3_p3_ab_five_bounded_research.evaluate.http_json",
                       return_value=data):
                with self.assertRaises(ValueError):
                    verified_spot_metadata("XBTEUR", "XBT/EUR", ticker)

    def test_runtime_diagnose_is_not_a_model_or_paper_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            trading = Path(directory)
            runtime = trading / "Runtime" / "fixed-stage"
            runtime.mkdir(parents=True)
            (runtime / "paper_strategy_spec.json").write_text("{}", encoding="utf-8")
            control = {"series_id": EXPECTED_SERIES}
            with patch("paper_evaluator.v3_p3_ab_five_bounded_research.discover_active_paper_runtime",
                       return_value=(runtime, control)):
                with patch("paper_evaluator.v3_p3_ab_five_bounded_research.freeze_runtime_provenance"):
                    with patch("paper_evaluator.v3_p3_ab_five_bounded_research.verify_frozen_strategy_spec"):
                        with patch("paper_evaluator.v3_p3_ab_five_bounded_research.evaluate.call_evaluator") as model:
                            out = run_one(trading, ROOT, minutes=0, dry_run=True)
            self.assertEqual(out["status"], "PREFLIGHT_PASS_NO_MODEL")
            self.assertEqual(out["model_http_attempts_reserved"], 0)
            self.assertFalse((trading / "Research").exists())
            model.assert_not_called()
        with self.assertRaises(ValueError):
            run_one(Path("/tmp"), ROOT, minutes=MAX_MINUTES + 1, dry_run=True)

    def test_active_runtime_does_not_import_bounded_research(self):
        for name in ("paper_evaluator/evaluate.py", "paper_evaluator/v2r4_local_recheck.py",
                     "paper_evaluator/v2r4_wait_runtime.py",
                     "tools/v2r4-paper-local-runtime.py"):
            self.assertNotIn("v3_p3_ab_five_bounded_research", (ROOT / name).read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
