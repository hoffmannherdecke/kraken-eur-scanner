"""The 2nd immutable signed owner receipt never replaces the source UNKNOWN."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
from paper_evaluator.v3_paper_signed_source_journal_stage_v1 import (
    prepare_signed_owner_receipts,stage_signed_owner_receipts_explicitly,
)
from tests.test_v3_paper_existing_source_owner_to_single_writer_seam_v1 import (
    event,preflight,official,money,poly,movement,KEYS,
)

def samples():
    return [event("news_sentiment",official()),
            event("smart_money_h10",money()),
            event("polymarket_h11",poly(),movement())]

class SignedSourceStageTests(unittest.TestCase):
    def test_all_three_signed_origins_keep_first_unknown_and_append_auth_proof(self):
        for packet in samples():
            with self.subTest(source=packet["source_name"]),tempfile.TemporaryDirectory() as td:
                root=Path(td)
                plan=preflight(owner_events=[packet])
                self.assertEqual(plan["ingress"]["counts"]["selected"],1)
                first=stage_receipts_explicitly(preflight=plan,journal_directory=root)
                self.assertEqual(first["written"],1)
                self.assertFalse(first["source_owner_runtime_authenticated"])
                receipts_before=[json.loads(p.read_text()) for p in root.glob("*.json")]
                self.assertEqual(receipts_before[0]["phase"],"SOURCE_INPUT")
                self.assertEqual(receipts_before[0]["result"],"UNKNOWN")
                state=stage_signed_owner_receipts_explicitly(
                    preflight=plan,signed_owner_packets=[packet],
                    trusted_owner_hmac_keys=KEYS,journal_directory=root)
                self.assertEqual(state["immutable_new_auth_receipts"],1)
                self.assertFalse(state["model_http_authorized"])
                self.assertFalse(state["cloud_ack_verified"])
                self.assertFalse(state["v3_paper_activated"])
                rows=[json.loads(p.read_text()) for p in root.glob("*.json")]
                self.assertEqual({(r["phase"],r["event_key"],r["result"])
                                  for r in rows},
                                 {("SOURCE_INPUT","FIRST","UNKNOWN"),
                                  ("SOURCE_INPUT","OWNERAUTH","PASS")})
                auth=next(r for r in rows if r["event_key"]=="OWNERAUTH")
                self.assertEqual(auth["candidate_id"],receipts_before[0]["candidate_id"])
                self.assertEqual(auth["data"]["positive_source_event_id"],
                                 packet["snapshot"]["event_id"])
                self.assertEqual(auth["data"]["positive_source_owner"],
                                 packet["snapshot"]["source_owner"])
                self.assertFalse(any("owner_hmac_sha256" in str(r) for r in rows))
                self.assertFalse(any("proof_version" in str(r) for r in rows))
                self.assertNotIn("MODEL_REQUEST",[r["phase"] for r in rows])
                again=stage_signed_owner_receipts_explicitly(
                    preflight=plan,signed_owner_packets=[packet],
                    trusted_owner_hmac_keys=KEYS,journal_directory=root)
                self.assertEqual(again["idempotent_replays"],1)
                self.assertEqual(len(list(root.glob("*.json"))),2)

    def test_hmac_rechecked_again_not_preflight_bool_or_sha(self):
        packet=samples()[0]
        plan=preflight(owner_events=[packet])
        variants=[
            (lambda p:p["owner_integrity"].update(owner_hmac_sha256="0"*64)),
            (lambda p:p["snapshot"].update(sentiment="NEGATIVE")),
            (lambda p:p.update(pair="ETH/EUR")),
            (lambda p:p["owner_integrity"].pop("owner_hmac_sha256")),
            (lambda p:p.update(altname="ETHEUR")),
            (lambda p:p["owner_integrity"].update(
                authentication_checked_by_trusted_caller=True,
                owner_hmac_sha256="f"*64)),
        ]
        for change in variants:
            with self.subTest(change=change):
                invalid=copy.deepcopy(packet)
                change(invalid)
                with self.assertRaises(ValueError):
                    prepare_signed_owner_receipts(
                        preflight=plan,signed_owner_packets=[invalid],
                        trusted_owner_hmac_keys=KEYS)
        with self.assertRaises(ValueError):
            prepare_signed_owner_receipts(
                preflight=plan,signed_owner_packets=[packet],
                trusted_owner_hmac_keys=None)
        self.assertEqual(len(prepare_signed_owner_receipts(
            preflight=plan,signed_owner_packets=[packet],
            trusted_owner_hmac_keys=KEYS)),1)

    def test_no_original_unknown_or_mismatched_intake_no_write(self):
        packet=samples()[0]
        plan=preflight(owner_events=[packet])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with self.assertRaisesRegex(ValueError,"FIRST UNKNOWN"):
                stage_signed_owner_receipts_explicitly(
                    preflight=plan,signed_owner_packets=[packet],
                    trusted_owner_hmac_keys=KEYS,journal_directory=root)
            self.assertFalse(list(root.iterdir()))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            stage_receipts_explicitly(preflight=plan,journal_directory=root)
            tamper=copy.deepcopy(plan)
            tamper["selected_candidates"][0]["pair"]="ETH/EUR"
            with self.assertRaises(ValueError):
                prepare_signed_owner_receipts(
                    preflight=tamper,signed_owner_packets=[packet],
                    trusted_owner_hmac_keys=KEYS)
            with self.assertRaisesRegex(ValueError,"missing authenticated"):
                prepare_signed_owner_receipts(
                    preflight=plan,signed_owner_packets=[],
                    trusted_owner_hmac_keys=KEYS)
            with self.assertRaises(ValueError):
                prepare_signed_owner_receipts(
                    preflight=plan,signed_owner_packets=[packet,packet],
                    trusted_owner_hmac_keys=KEYS)
            self.assertEqual(len(list(root.glob("*.json"))),1)

    def test_non_source_scanner_unchanged_and_rejection_audit_not_promoted(self):
        packet=samples()[0]
        invalid=copy.deepcopy(packet)
        invalid["owner_integrity"]["owner_hmac_sha256"]="0"*64
        plan=preflight(owner_events=[invalid])
        self.assertEqual(len(plan["source_provenance"]["owner_source_events"]),0)
        self.assertEqual(plan["ingress"]["owner_pre_router_rejection_count"],1)
        receipts=prepare_signed_owner_receipts(
            preflight=plan,signed_owner_packets=[],
            trusted_owner_hmac_keys=KEYS)
        self.assertEqual(receipts,[])
        with self.assertRaises(ValueError):
            prepare_signed_owner_receipts(
                preflight=plan,signed_owner_packets=[packet],
                trusted_owner_hmac_keys=KEYS)
        self.assertFalse(plan["paper_buy_authorized"])

if __name__=="__main__":
    unittest.main()
