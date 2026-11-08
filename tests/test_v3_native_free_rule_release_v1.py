"""Native existing-owner free P4 integration is no-model and non-replayable.

These are offline source/receipt tests, not physical Cloud/CAS authorizations.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import evaluate
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import (
    one_candidate, _RELEASED_MODEL_NATIVE_OWNER,
)
from paper_evaluator import v3_paper_minipc_selective_tick_v1 as native
from tests.test_v3_paper_minipc_one_candidate_v1 import (
    fixture, fake_acquire, stage_scanner_original, SID,
)
from tests.test_v2r4_v3_entry_handoff_probe import dt
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt, store_receipt_explicitly


class FreeRuleNativeTests(unittest.TestCase):
    def test_no_release_capability_blocks_staged_free_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            journal=root/"journal"; budget=root/"budget"
            journal.mkdir(); budget.mkdir()
            candidate=dict(fixture()[0],entry_origin="SCANNER",
                           action="REVIEW_ONLY_NOT_ORDER",altname="XBTEUR")
            stage_scanner_original(journal,candidate)
            with self.assertRaisesRegex(ValueError,"released OS owner"):
                one_candidate(
                    candidate=candidate,series_id=SID,local_receipts=journal,
                    model_reservations=budget,
                    admit_staged_scanner_one_free_rule=True,
                    acquire=lambda *_:self.fail("unreleased source fetch"),
                    clock=lambda:dt(12))
            self.assertFalse(list(budget.glob("*.reserved.json")))
            self.assertEqual(len(list(journal.glob("*.json"))),2)

    def test_original_locked_owner_writes_free_p4_and_never_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            journal=root/"journal"; capture=root/"capture";budget=root/"budget"
            journal.mkdir();capture.mkdir();budget.mkdir()
            candidate=dict(fixture()[0],kind="CANONICAL_CANDIDATE_HANDOFF_V1",
                           entry_origin="SCANNER",action="REVIEW_ONLY_NOT_ORDER",
                           altname="XBTEUR")
            preflight={
                "series_id":SID,"selected_candidates":[candidate],
                "ingress":{"capacity_deferred_originals":[]},
                "prospective_first_1m_capture_enrollment":[{"candidate_id":candidate["candidate_id"]}],
                "review_preflights":[{"candidate_id":candidate["candidate_id"],
                                      "eligible_for_full_model_review":True}],
                "paper_writer_active":False,"model_http_authorized":False,
            }
            def staged(**kwargs):
                stage_scanner_original(journal,candidate)
                return {"enrollment":[{"status":"FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY"}],
                        "source_capture_calls":1}
            with patch.object(native,"_require_released_paper_cloud") as gate, \
                 patch("paper_evaluator.v3_paper_intake_receipt_stage_v1.stage_and_witness_first_minute",
                       side_effect=staged), \
                 patch.object(evaluate,"http_json",side_effect=AssertionError("paid HTTP attempted")):
                result=native.released_paper_first_scanner_rule_once(
                    preflight=preflight,candidate=candidate,series_id=SID,
                    journal=journal,capture_dir=capture,model_reservations=budget,
                    expected_repo_sha="a"*40,
                    expected_bundle_sha256="b"*64,
                    expected_strategy_sha256="c"*64,
                    read_active_series=lambda *_:self.fail("patched release gate"),
                    acquire=fake_acquire,clock_now=lambda:dt(12))
            self.assertEqual(gate.call_count,1)
            self.assertEqual(result["model_http_calls"],0)
            self.assertEqual(result["model_http_attempts_reserved"],0)
            self.assertFalse(result["orders"])
            self.assertFalse(result["real_money_actions"])
            self.assertEqual(result["status"],"FIRST_SCANNER_FREE_RULE_P4_DURABLE_WAIT_FOR_FOLLOWUP")
            self.assertFalse(list(budget.glob("*.reserved.json")))
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual(len([x for x in rows if x["phase"]=="MODEL_RESPONSE"]),0)
            self.assertEqual(len([x for x in rows if x["phase"]=="P4_VALIDATION"]),1)
            self.assertEqual(len([x for x in rows if x["phase"]=="MODEL_REQUEST"]),1)
            with patch.object(native,"_require_released_paper_cloud"):
                again=native.released_paper_first_scanner_rule_once(
                    preflight=preflight,candidate=candidate,series_id=SID,
                    journal=journal,capture_dir=capture,model_reservations=budget,
                    expected_repo_sha="a"*40,
                    expected_bundle_sha256="b"*64,
                    expected_strategy_sha256="c"*64,
                    read_active_series=lambda *_:self.fail("patched release gate"),
                    acquire=lambda *_:self.fail("no second source fetch"),
                    clock_now=lambda:dt(12))
            self.assertEqual(again["status"],"FIRST_SCANNER_ALREADY_JOURNALED_NO_RULE_REPLAY")


    def test_released_rule_wait_continues_without_provider_receipts(self):
        series = "PAPER-V3-20261108T100000Z"
        start = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)
        candidate = dict(candidate_id="SCANNER-WAIT-ORIGINAL", pair="XBT/EUR",
                         altname="XBTEUR", entry_origin="SCANNER", event_time_utc=start.isoformat())
        with tempfile.TemporaryDirectory() as tmp:
            journal, capture, budget, ack = (Path(tmp, name) for name in ("journal", "capture", "budget", "ack"))
            for root in (journal, capture, budget, ack):
                root.mkdir()
            original = [
                ("SCANNER_CAPTURE", "SEEN", "FIRST", {"candidate_origin": "SCANNER"}),
                ("FULL_REVIEW_ELIGIBILITY", "PASS", "FIRST", {}),
                ("FULL_REVIEW_ELIGIBILITY", "PASS", "FRESHRECHECK", {}),
                ("MODEL_REQUEST", "SKIP", "FRESHRECHECK",
                 {"source_status": "FREE_RULE_V3_P4_NO_MODEL", "model_http_attempts_reserved": 0}),
                ("P4_VALIDATION", "WAIT", "FRESHRECHECK",
                 {"p4_decision": "WAIT", "p4_completed_at_utc": start.isoformat(),
                  "rule_based_primary": True, "model_http_requests": 0}),
                ("WAIT_WATCH", "WAIT", "FRESHRECHECK",
                 {"raw_wait_ttl_minutes": 30, "raw_watch_conditions":
                  [{"metric": "ask_eur", "op": "<=", "value": 100.0}]}),
            ]
            def store(phase, result, key, data):
                store_receipt_explicitly(journal, make_receipt(
                    series_id=series, revision=native.REVISION,
                    candidate_id=candidate["candidate_id"], pair=candidate["pair"],
                    event_time_utc=start.isoformat(), known_at_utc=start.isoformat(),
                    phase=phase, result=result, event_key=key, data=data))
            for row in original:
                store(*row)
            now = start + timedelta(minutes=5, seconds=10)
            def tick():
                return native.released_paper_followup_tick_once(
                    candidate=candidate, series_id=series, journal=journal, capture_dir=capture,
                    model_reservations=budget, ack_file=ack / "readback.json",
                    expected_repo_sha="a"*40, expected_bundle_sha256="b"*64,
                    expected_strategy_sha256="c"*64,
                    read_active_series=lambda *_: self.fail("patched release gate"),
                    clock_now=lambda: now.isoformat(),
                    capture=lambda **_: {"status": "CLOSED_KRAKEN_1M_SNAPSHOT_SAVED", "count": 0},
                    fetch=lambda *_: {"pair": "XBT/EUR", "observed_at_utc": now.isoformat(),
                                     "frames": {"5": {"status": "VALID",
                                                      "last_closed_bar_end_utc":
                                                      (start+timedelta(minutes=5)).isoformat()}}},
                    ticker=lambda *_: {"ask": 99.0})
            with patch.object(native, "_require_released_paper_cloud"), \
                 patch.object(evaluate, "http_json", side_effect=AssertionError("unexpected HTTP")):
                result = tick()
                self.assertIn("wait", result, result)
                self.assertEqual(result["wait"]["status"], "WAIT_CONDITIONS_MATCHED_REQUIRES_NEW_RULE_P4")
                self.assertFalse(result["wait"]["authorized_buy"])
                now = start + timedelta(hours=7, seconds=1)
                result = tick()
                self.assertFalse(result["orders"])
                store("MODEL_RESPONSE", "PASS", "FRESHRECHECK", {})
                mixed = tick()
                self.assertFalse(mixed["tick_called"])
                self.assertEqual(mixed["source_capture_calls"], 0)
            phases = [json.loads(p.read_text())["phase"] for p in journal.glob("*.json")]
            self.assertIn("WAIT_RECHECK", phases)
            self.assertIn("WAIT_EXPIRY", phases)
            self.assertIn("FOLLOWUP_6H", phases)
            self.assertNotIn("PAPER_FILL", phases)
            self.assertEqual(phases.count("MODEL_RESPONSE"), 1)  # Deliberately mixed test input.
            self.assertFalse(list(budget.iterdir()))


if __name__=="__main__":
    unittest.main()
