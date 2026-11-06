"""Native existing-owner free P4 integration is no-model and non-replayable.

These are offline source/receipt tests, not physical Cloud/CAS authorizations.
"""
import json
import tempfile
import unittest
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


if __name__=="__main__":
    unittest.main()
