"""Real V3 P0 -> immutable original SOURCE_INPUT -> source-clocked 15m base.

All acquisition/model data are offline fixtures. These tests are NOT physical
Mini-PC, Cloud or real Paper entry proof.
"""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from paper_evaluator.v3_first_pit_presignal_15m_v1 import (
    KIND, capture_first_pit_base, read_first_pit_base,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
from tests.test_v3_experimental_paper_initial_review_v1 import fixture
from tests.test_v2r4_v3_entry_handoff_probe import dt

SID = "PAPER-V3-P0-PRESIGNAL-TEST"


def scenario():
    candidate, coin, ticker, meta = fixture()
    candidate = dict(candidate, entry_origin="SCANNER", altname="XBTEUR")
    # Original public OHLC P0 already has four CLOSED 15m candles.
    # Two of them fully precede the scanner's event_time at BASE-60sec.
    assert len(coin["initial_pit_closed_15m_ohlc"]) == 4
    return candidate, coin, ticker, meta


class OriginalFirstPIT15mTests(unittest.TestCase):
    def test_same_original_kraken_pit_base_persists_without_new_poll_or_model(self):
        candidate, coin, quote, meta = scenario()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            budgets = Path(tmp) / "budgets"
            journal.mkdir()
            budgets.mkdir()
            called = []
            result = one_candidate(
                candidate=candidate, series_id=SID,
                local_receipts=journal, model_reservations=budgets,
                acquire=lambda _: called.append("original_p0") or (
                    copy.deepcopy(coin), copy.deepcopy(quote), copy.deepcopy(meta)),
                clock=lambda: dt(12),
                model_client=lambda *_: self.fail("no paid model authorized"))
            self.assertEqual(result["status"],
                "V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            self.assertEqual(called, ["original_p0"])
            self.assertEqual(list(budgets.iterdir()), [])
            rows = [json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            source = next(r for r in rows if r["phase"] == "SOURCE_INPUT")
            actual = source["data"]["initial_pit_15m_base"]
            self.assertEqual(actual["kind"], KIND)
            self.assertEqual(actual["first_known_at_utc"], coin["known_at_utc"])
            self.assertTrue(actual["bar_closes_are_not_observation_times"])
            self.assertEqual(len(actual["bars"]), 2)
            self.assertTrue(all(
                b["start_utc"] + 900 <= int(datetime.fromisoformat(
                    candidate["event_time_utc"]).timestamp())
                for b in actual["bars"]))
            valid = read_first_pit_base(
                candidate, source, decision_at_utc=dt(60))
            self.assertEqual(valid["bars"], actual["bars"])
            self.assertEqual(source["data"]["input_known_at_utc"],
                             actual["first_known_at_utc"])
            self.assertFalse(any(r["phase"] == "PAPER_FILL" for r in rows))

    def test_first_pit_source_known_late_or_altered_does_not_become_presignal(self):
        candidate, coin, _, _ = scenario()
        original = capture_first_pit_base(candidate, coin, written_at_utc=dt(12))
        self.assertIsNotNone(original)
        for change in (
            lambda e: e.update(pair="ETH/EUR"),
            lambda e: e.update(known_at_utc=dt(900)),
            lambda e: e.update(observed_at_utc=dt(-90)),
            lambda e: e.update(initial_pit_closed_15m_ohlc=[]),
            lambda e: e["frames"]["15"].update(status="INVALID"),
            lambda e: e["initial_pit_closed_15m_ohlc"][-2].update(close=1000),
            lambda e: e["initial_pit_closed_15m_ohlc"][-2].update(start_utc=1791531000),
        ):
            trial = copy.deepcopy(coin)
            change(trial)
            with self.subTest(change=str(change)):
                self.assertIsNone(capture_first_pit_base(
                    candidate, trial, written_at_utc=dt(12)))
        self.assertIsNone(capture_first_pit_base(
            {**candidate, "entry_origin":"P1_REENTRY_EPISODE"},
            coin, written_at_utc=dt(12)))

    def test_receipt_replay_rejects_forged_source_and_clock(self):
        from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
        candidate, coin, _, _ = scenario()
        base = capture_first_pit_base(candidate, coin, written_at_utc=dt(12))
        self.assertIsNotNone(base)
        receipt = make_receipt(
            series_id=SID, revision=REVISION,
            candidate_id=candidate["candidate_id"], pair=candidate["pair"],
            event_time_utc=candidate["event_time_utc"],
            known_at_utc=dt(12), phase="SOURCE_INPUT", result="PASS",
            data={"input_known_at_utc": coin["known_at_utc"],
                  "source_status": "COMPLETE",
                  "initial_pit_15m_base": base})
        self.assertIsNotNone(read_first_pit_base(
            candidate, receipt, decision_at_utc=dt(30)))
        mutations = (
            lambda r:r["data"]["initial_pit_15m_base"].update(
                first_known_at_utc=dt(100)),
            lambda r:r["data"]["initial_pit_15m_base"].update(
                candidate_id="OTHER"),
            lambda r:r["data"]["initial_pit_15m_base"].update(
                bar_closes_are_not_observation_times=False),
            lambda r:r["data"].update(input_known_at_utc=dt(100)),
            lambda r:r.update(result="UNKNOWN"),
            lambda r:r["data"]["initial_pit_15m_base"]["bars"][-1].update(
                start_utc=r["data"]["initial_pit_15m_base"]["bars"][0]["start_utc"]),
        )
        for change in mutations:
            changed = copy.deepcopy(receipt)
            change(changed)
            with self.subTest(change=str(change)):
                self.assertIsNone(read_first_pit_base(
                    candidate, changed, decision_at_utc=dt(30)))
        self.assertIsNone(read_first_pit_base(
            candidate, receipt, decision_at_utc=dt(5)))


if __name__ == "__main__":
    unittest.main()
