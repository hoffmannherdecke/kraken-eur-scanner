#!/usr/bin/env python3
"""No-network tests of H10 original source archive read-after-write semantics."""
import copy
import unittest
from tools.v3_h10_selected_original_cloud_protocol_v1 import (
    prepare_source_only_insert, verify_persisted_readback,
    classify_existing_without_writing,
)
from tools.v3_h10_selected_original_receipt_v1 import OriginalEvidenceBlocked
from tests.test_v3_h10_selected_original_receipt_v1 import build, row


def persisted(candidate):
    stored = prepare_source_only_insert(candidate)
    stored["received_at_utc"] = "2026-10-12T12:36:01Z"
    return stored


class OriginalCloudProtocolTests(unittest.TestCase):
    def test_exact_storage_columns_and_server_timestamp_not_writable(self):
        c=build()
        prepared=prepare_source_only_insert(c)
        self.assertEqual(set(prepared), {
            "candidate_id","cohort_id","cohort_role","coin",
            "window_start_utc","evaluated_at_utc","content_sha256",
            "original_payload_canonical"
        })
        self.assertNotIn("received_at_utc",prepared)
        self.assertEqual(prepared["original_payload_canonical"][0],"{")
        self.assertEqual(verify_persisted_readback(c,persisted(c)),
                         "SOURCE_ONLY_READBACK_MATCH_NOT_A_LIVE_CLOUD_ACK")
        self.assertEqual(classify_existing_without_writing(c,persisted(c)),
                         "ALREADY_IDENTICAL_NO_UPDATE_NO_INSERT")

    def test_changed_content_cannot_overwrite_first_receipt(self):
        first=build()
        later=build(rows=[row(0), row(1), row(2,sz="2")])
        self.assertEqual(first["candidate_id"],later["candidate_id"])
        with self.assertRaisesRegex(OriginalEvidenceBlocked,
                                    "SOURCE_RECEIPT_READBACK_CONFLICT_CONTENT_SHA256"):
            classify_existing_without_writing(later,persisted(first))

    def test_server_received_at_fails_on_false_early_or_expired(self):
        c=build()
        r=persisted(c)
        r["received_at_utc"]="2026-10-12T12:30:00Z"
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"DATABASE_RECEIVED_BEFORE_EVALUATION"):
            verify_persisted_readback(c,r)
        r=persisted(c)
        r["received_at_utc"]="2026-10-14T12:30:00Z"
        with self.assertRaisesRegex(OriginalEvidenceBlocked,
                                    "DATABASE_RECEIVED_AFTER_EARLIEST_RAW_EXPIRY"):
            verify_persisted_readback(c,r)

    def test_forged_payload_or_role_or_first_seen_not_ack(self):
        c=build()
        for key,value in [
            ("original_payload_canonical","{}"),
            ("cohort_role","CONTROL"),
            ("coin","ETH"),
            ("candidate_id","0"*64),
            ("window_start_utc","2026-10-12T12:30:00Z")
        ]:
            with self.subTest(key=key):
                r=persisted(c)
                r[key]=value
                with self.assertRaises(OriginalEvidenceBlocked):
                    verify_persisted_readback(c,r)

    def test_stale_source_candidate_fails_even_with_plausible_receipt(self):
        c=build()
        forged=copy.deepcopy(c)
        forged["payload"]["evaluated_at_utc"]="2026-10-14T12:28:00.000000Z"
        with self.assertRaises(OriginalEvidenceBlocked):
            prepare_source_only_insert(forged)

    def test_not_a_source_authentication_or_trading_bridge(self):
        import inspect
        from tools import v3_h10_selected_original_cloud_protocol_v1 as mod
        source=inspect.getsource(mod)
        for forbidden in ("urllib", "requests.", "supabase.", "http_post_rows",
                          "model_api", "place_order", "insert()", "execute_sql",
                          "token=", "secret_key"):
            self.assertNotIn(forbidden,source)


if __name__=="__main__":
    unittest.main()
