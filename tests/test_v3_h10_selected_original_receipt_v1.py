#!/usr/bin/env python3
"""Offline, deterministic tests. No Supabase/HTTP/collector call."""
import copy
import datetime as dt
import hashlib
import json
import unittest
from pathlib import Path

from tools.v3_h10_selected_original_receipt_v1 import (
    OriginalEvidenceBlocked, build_selected_window_receipt, compare_replay
)

ROOT = Path(__file__).resolve().parents[1]
COHORT = json.loads((ROOT / "research/v3/h10-trader-cohort-v1.json").read_text(encoding="utf-8"))
START = "2026-10-12T12:00:00Z"
ASOF = "2026-10-12T12:36:00Z"
BATCH = {
    "batch_id": "h10-original", "cohort_id": "V3-H10-COHORT-001",
    "capture_path": "GITHUB_BOOTSTRAP_30M",
    "observed_at": "2026-10-12T12:35:00Z", "created_at": "2026-10-12T12:35:08Z",
    "wallet_count": 26, "success_count": 26, "error_count": 0
}


def row(index, *, role="PRIMARY", direction="Open Long", px="15000", sz="1"):
    addr = next(x["address"] for x in COHORT["traders"] if x["role"] == role and
                [y["address"] for y in COHORT["traders"] if y["role"] == role].index(x["address"]) == index)
    return {
        "event_id": hashlib.sha256(f"{role}:{index}".encode()).hexdigest(),
        "cohort_id": COHORT["cohort_id"], "cohort_role": role,
        "coin": "BTC", "address": addr,
        "fill_time": "2026-10-12T12:10:00Z",
        "first_seen_at": "2026-10-12T12:35:10Z",
        "first_seen_batch_id": "h10-original",
        "tx_hash": "0x" + "a" * 64, "oid": str(index), "tid": str(index),
        "direction": direction, "side": "B" if direction in ("Open Long", "Close Short") else "A",
        "px": px, "sz": sz,
    }


def build(rows=None, role="PRIMARY", **overrides):
    inputs = {
        "cohort": copy.deepcopy(COHORT), "batch_rows": [copy.deepcopy(BATCH)],
        "fill_rows": [row(0), row(1), row(2)] if rows is None else rows,
        "coin": "BTC", "role": role, "window_start_utc": START,
        "evaluated_at_utc": ASOF
    }
    inputs.update(overrides)
    return build_selected_window_receipt(**inputs)


class SelectedOriginalSourceReceiptTests(unittest.TestCase):
    def reject(self, reason, **kw):
        with self.assertRaisesRegex(OriginalEvidenceBlocked, reason):
            build(**kw)

    def test_three_wallet_positive_retains_individual_first_seen(self):
        p = build()
        self.assertEqual(p["status"], "SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED")
        self.assertEqual(p["payload"]["wallet_address_count"], 3)
        self.assertEqual(p["payload"]["positive_wallet_count"], 3)
        self.assertEqual(p["payload"]["source_event_count"], 3)
        self.assertTrue(p["payload"]["matches_pr230_descriptive_positive_raw_filter"])
        self.assertEqual(len(p["candidate_id"]), 64)
        self.assertEqual(len(p["content_sha256"]), 64)
        self.assertLessEqual(p["payload_bytes"], 65536)
        self.assertEqual(p["payload"]["original_events"][0]["original_batch_id"], "h10-original")
        self.assertEqual(p["payload"]["original_events"][0]["database_first_seen_at_utc"],
                         "2026-10-12T12:35:10.000000Z")
        self.assertIsNone(p["cloud_original_receipt_ack"])
        self.assertFalse(p["live_source_verified"])
        self.assertFalse(p["payload"]["self_dealing_excluded"])
        self.assertFalse(p["payload"]["source_owner_authenticated"])
        self.assertFalse(p["payload"]["kraken_eur_tradability_verified"])
        self.assertTrue(p["payload"]["no_buy_authority"])
        self.assertEqual(compare_replay(p, build(rows=[row(2), row(0), row(1)])),
                         "IDENTICAL_REPLAY_NO_WRITE")

    def test_preserve_counterexamples_not_only_positive(self):
        p = build(rows=[row(0), row(1, direction="Open Short"), row(2)])
        self.assertEqual(p["status"], "SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED")
        self.assertEqual(p["payload"]["positive_wallet_count"], 2)
        self.assertEqual(p["payload"]["negative_wallet_count"], 1)
        self.assertFalse(p["payload"]["matches_pr230_descriptive_positive_raw_filter"])

    def test_controls_preserved_separately(self):
        p = build(rows=[row(0, role="CONTROL"),row(1, role="CONTROL"),row(2, role="CONTROL")],
                  role="CONTROL")
        self.assertEqual(p["payload"]["cohort_role"], "CONTROL")
        self.assertEqual(p["payload"]["wallet_address_count"], 3)

    def test_not_selected_does_not_claim_receipt(self):
        p = build(rows=[row(0),row(1)])
        self.assertEqual(p["status"], "NOT_SELECTED_RESEARCH_ONLY")
        self.assertNotIn("content_sha256", p)

    def test_first_seen_batch_must_be_original(self):
        b = copy.deepcopy(BATCH)
        b["created_at"] = "2026-10-12T12:35:40Z"
        self.reject("ORIGINAL_BATCH_TIMESTAMP_REVERSED", batch_rows=[b])

    def test_source_clock_and_future_row_rejected(self):
        r = row(0)
        r["first_seen_at"] = "2026-10-12T12:05:00Z"
        self.reject("SOURCE_LOOKAHEAD_OR_CLOCK_REVERSAL", rows=[r,row(1),row(2)])
        r = row(0)
        r["first_seen_at"] = "2026-10-12T12:37:00Z"
        self.reject("SOURCE_LOOKAHEAD_OR_CLOCK_REVERSAL", rows=[r,row(1),row(2)])

    def test_fail_closed_capture_coverage(self):
        b = copy.deepcopy(BATCH)
        b["error_count"] = 1
        b["success_count"] = 25
        self.reject("NO_FULL_WINDOW_SUCCESSFUL_CAPTURE_COVERAGE",batch_rows=[b])
        b = copy.deepcopy(BATCH)
        b["observed_at"] = "2026-10-12T12:50:00Z"
        b["created_at"] = "2026-10-12T12:50:08Z"
        self.reject("BATCH_NOT_AVAILABLE_AT_EVALUATION",batch_rows=[b])

    def test_two_healthy_overlapping_cron_reads_cover_full_window(self):
        earlier = copy.deepcopy(BATCH)
        earlier["observed_at"] = "2026-10-12T12:17:00Z"
        earlier["created_at"] = "2026-10-12T12:17:08Z"
        later = copy.deepcopy(BATCH)
        later["batch_id"] = "h10-second"
        later["observed_at"] = "2026-10-12T12:47:00Z"
        later["created_at"] = "2026-10-12T12:47:08Z"
        p = build(batch_rows=[later, earlier], evaluated_at_utc="2026-10-12T12:48:00Z")
        self.assertEqual(p["status"], "SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED")
        self.assertEqual(p["payload"]["complete_window_capture_batch_ids"],
                         ["h10-original", "h10-second"])

    def test_healthy_capture_interval_gap_is_blocked(self):
        earlier = copy.deepcopy(BATCH)
        earlier["observed_at"] = "2026-10-12T12:14:00Z"
        earlier["created_at"] = "2026-10-12T12:14:08Z"
        later = copy.deepcopy(BATCH)
        later["batch_id"] = "h10-second"
        later["observed_at"] = "2026-10-12T13:00:00Z"
        later["created_at"] = "2026-10-12T13:00:08Z"
        self.reject("NO_FULL_WINDOW_SUCCESSFUL_CAPTURE_COVERAGE",
                    batch_rows=[later, earlier],
                    evaluated_at_utc="2026-10-12T13:01:00Z")

    def test_earliest_possible_fill_expiration_fails_closed(self):
        # The old end+48h calculation permitted 30 minutes of missing raw fills.
        self.reject("ORIGINAL_FILL_TTL_EXPIRED",
                    evaluated_at_utc="2026-10-14T11:55:00.000001Z")
        late = build(evaluated_at_utc="2026-10-14T11:55:00Z")
        self.assertEqual(late["status"], "SELECTED_INACTIVE_OFFLINE_NOT_PERSISTED")

    def test_no_false_historical_replay_when_raw_expired(self):
        self.reject("ORIGINAL_FILL_TTL_EXPIRED",
                    evaluated_at_utc="2026-10-15T13:00:00Z")

    def test_unregistered_wallet_and_cross_role(self):
        r = row(0)
        r["address"] = "0x" + "9" * 40
        self.reject("UNREGISTERED_OR_WRONG_ROLE_WALLET",rows=[r,row(1),row(2)])
        self.reject("UNREGISTERED_OR_WRONG_ROLE_WALLET",
                    rows=[row(0,role="CONTROL"),row(1),row(2)])

    def test_source_hash_direction_and_numerics(self):
        r = row(0); r["tx_hash"] = None
        self.reject("SOURCE_TX_HASH_REQUIRED",rows=[r,row(1),row(2)])
        r = row(0); r["side"] = "A"
        self.reject("SOURCE_SIDE_DIRECTION_CONFLICT",rows=[r,row(1),row(2)])
        r = row(0); r["px"] = float("nan")
        self.reject("INVALID_PRICE",rows=[r,row(1),row(2)])
        r = row(0); r["direction"] = "unknown"
        self.reject("UNKNOWN_SOURCE_DIRECTION",rows=[r,row(1),row(2)])

    def test_bad_event_conflict_and_input_cap_fail_closed(self):
        r = row(0); r["first_seen_batch_id"] = "other"
        self.reject("ORIGINAL_BATCH_JOIN_MISSING",rows=[r,row(1),row(2)])
        self.reject("DUPLICATE_EVENT_INPUT_NOT_DEDUPED",rows=[row(0),row(1),row(2),row(0)])
        self.reject("EVENT_CAP_NO_SILENT_TRUNCATION",rows=[row(0)]*129)

    def test_identical_receipt_only_no_upsert(self):
        previous = build()
        changed = build(rows=[row(0),row(1),row(2,sz="2")])
        self.assertEqual(previous["candidate_id"],changed["candidate_id"])
        self.assertNotEqual(previous["content_sha256"],changed["content_sha256"])
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"REPLAY_CONTENT_CONFLICT_KEEP_ORIGINAL"):
            compare_replay(previous, changed)

    def test_tampered_payload_cannot_use_old_content_digest(self):
        earlier = build()
        tampered = copy.deepcopy(earlier)
        tampered["payload"]["original_events"][0]["price_quote"] = "999999"
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"REPLAY_DIGEST_NOT_CANONICAL"):
            compare_replay(earlier, tampered)
        tampered = copy.deepcopy(earlier)
        tampered["candidate_id"] = "0" * 64
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"REPLAY_DIGEST_NOT_CANONICAL"):
            compare_replay(earlier, tampered)

    def test_alignment_cohort_role_and_missing_batch(self):
        self.reject("UNALIGNED_30M_WINDOW",window_start_utc="2026-10-12T12:15:00Z")
        self.reject("OPEN_WINDOW_LOOKAHEAD",evaluated_at_utc="2026-10-12T12:15:00Z")
        self.reject("INVALID_COHORT_ROLE",role="UNKNOWN")
        self.reject("NO_FULL_WINDOW_SUCCESSFUL_CAPTURE_COVERAGE",batch_rows=[])

    def test_no_io_or_routing_side_effects(self):
        import inspect
        from tools import v3_h10_selected_original_receipt_v1 as mod
        source = inspect.getsource(mod)
        for forbidden in ("urllib.request", "requests.", "supabase.", "subprocess.", "os.environ",
                          "http_post_rows", "INSERT INTO", "model_api", "place_order"):
            self.assertNotIn(forbidden,source)


if __name__ == "__main__":
    unittest.main()
