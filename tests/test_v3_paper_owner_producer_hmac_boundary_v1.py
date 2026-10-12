"""True outbound H5/H10/H11 qualified-event packet format matches writer MAC."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from paper_evaluator.v3_paper_source_owner_hmac_v1 import (
    sign_qualified_owner_event_explicitly,verify_owner_packet,
)
from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
from paper_evaluator.v3_paper_signed_source_journal_stage_v1 import (
    stage_signed_owner_receipts_explicitly,
)
from tests.test_v3_paper_existing_source_owner_to_single_writer_seam_v1 import (
    bridge,preflight,KEYS,H10,H11,H5,
)
from tests.test_v3_paper_positive_source_entry_v1 import (
    official,money,poly,movement,
)
from tests.test_v2r4_v3_entry_handoff_probe import dt

def sign(name,snapshot,move=None,*,secret=None,pair="XBT/EUR",altname="XBTEUR",
         owner=None,at=None):
    owner=owner or snapshot.get("source_owner")
    secret=secret if secret is not None else KEYS[name][owner]
    return sign_qualified_owner_event_explicitly(
        source_name=name,pair=pair,kraken_altname=altname,snapshot=snapshot,
        signed_at_utc=at or dt(12),owner_id=owner,owner_hmac_key=secret,
        market_move=move)

class V3OwnerProducerTests(unittest.TestCase):
    def test_each_true_qualified_owner_to_preflight_to_signed_immutable_receipt(self):
        for name,snapshot,move in (
            ("news_sentiment",official(),None),
            ("smart_money_h10",money(),None),
            ("polymarket_h11",poly(),movement()),
        ):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as td:
                source_packet=sign(name,snapshot,move)
                self.assertEqual(
                    verify_owner_packet(packet=source_packet,
                      trusted_keys=KEYS,decision_at_utc=dt(12)),
                    "VERIFIED_OWNER_HMAC_PACKET_ONLY")
                outcome=bridge([source_packet])
                self.assertEqual(len(outcome["owner_source_events"]),1)
                future=preflight(owner_events=[source_packet])
                self.assertEqual(future["ingress"]["counts"]["selected"],1)
                folder=Path(td)
                first=stage_receipts_explicitly(
                    preflight=future,journal_directory=folder)
                self.assertEqual(first["written"],1)
                proof=stage_signed_owner_receipts_explicitly(
                    preflight=future,signed_owner_packets=[source_packet],
                    trusted_owner_hmac_keys=KEYS,journal_directory=folder)
                self.assertEqual(proof["immutable_new_auth_receipts"],1)
                saved=json.dumps([json.loads(p.read_text())
                                  for p in folder.glob("*.json")],sort_keys=True)
                self.assertNotIn("owner_hmac_sha256",saved)
                self.assertNotIn("proof_version",saved)
                self.assertNotIn("H"*32,saved)
                self.assertNotIn("P"*32,saved)
                self.assertNotIn("N"*32,saved)
                self.assertIn("OWNERAUTH",saved)
                self.assertIn("UNKNOWN",saved)
                self.assertNotIn("PAPER_FILL",saved)
                self.assertFalse(proof["cloud_ack_verified"])
                self.assertFalse(proof["model_http_authorized"])

    def test_raw_h5_h10_h11_context_cannot_be_signed_to_positive_source(self):
        for name,snap in (
            ("news_sentiment",H5),("smart_money_h10",H10),
            ("polymarket_h11",H11),
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    sign(name,snap,owner=list(KEYS[name])[0])

    def test_signer_key_owner_pair_and_clock_must_be_exact(self):
        s=official()
        for changes in (
            {"secret":b"short"},
            {"secret":"not-a-bytes-key"},
            {"owner":"UNAUTHORIZED_SOURCE_OWNER","secret":b"N"*32},
            {"pair":"ETH/EUR"},
            {"altname":"X/BTEUR"},
            {"at":dt(-100)},
        ):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                sign("news_sentiment",s,**changes)
        good=sign("news_sentiment",s)
        changed=copy.deepcopy(good)
        changed["snapshot"]["sentiment"]="NEGATIVE"
        self.assertNotEqual(
            verify_owner_packet(packet=changed,trusted_keys=KEYS,
                                decision_at_utc=dt(12)),
            "VERIFIED_OWNER_HMAC_PACKET_ONLY")

    def test_packet_is_deterministic_and_not_mutated_after_signing(self):
        original=official()
        packet=sign("news_sentiment",original)
        self.assertEqual(packet,sign("news_sentiment",original))
        original["news_category"]="NEGATIVE_FAKE_AFTER_THE_FACT"
        self.assertNotEqual(packet["snapshot"]["news_category"],
                            original["news_category"])
        self.assertEqual(verify_owner_packet(
            packet=packet,trusted_keys=KEYS,decision_at_utc=dt(12)),
                         "VERIFIED_OWNER_HMAC_PACKET_ONLY")

if __name__=="__main__":
    unittest.main()
