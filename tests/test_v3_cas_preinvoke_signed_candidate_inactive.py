"""Pure source-only negative checks for original PREINVOKE unsigned CMS proposal.

No network, original Windows keys, Supabase, actor grants, role membership,
CAS invocation, runner, Paper writer or filesystem mutations.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from v3_cas_preinvoke_protocol_INACTIVE import (
    ORIGINAL_SERIES, RPC, PreinvokeHold, build_unsigned_intent,
    build_unsigned_preinvoke_cms_proposal,
)


def fixture():
    intent = build_unsigned_intent(
        epoch_id="V3CAS-AUDIT-" + "a" * 32,
        ordinal=1,
        intent_id="123e4567-e89b-42d3-a456-426614174000",
        predecessor_series_id=ORIGINAL_SERIES,
        rpc=RPC,
        request_sha256="b" * 64,
        source_sha256="c" * 64,
        fence_sha256="d" * 64,
    )
    readback = {
        "epoch_id": intent.epoch_id, "ordinal": intent.ordinal,
        "intent_id": intent.intent_id,
        "predecessor_series_id": intent.predecessor_series_id,
        "rpc": intent.rpc, "request_sha256": intent.request_sha256,
        "source_sha256": intent.source_sha256,
        "fence_sha256": intent.fence_sha256,
        "intent_sha256": intent.digest, "next_ordinal": 2,
        "ordered_intent_sha256": [intent.digest],
        "observed_at_utc": "2026-10-26T15:00:00Z",
    }
    return intent, readback


class UnsignedPreinvokeCmsCandidateSourceTests(unittest.TestCase):
    def propose(self, intent=None, readback=None, review="2026-10-26T15:00:15Z"):
        good_intent, good_row = fixture()
        return build_unsigned_preinvoke_cms_proposal(
            good_intent if intent is None else intent,
            good_row if readback is None else readback,
            reviewed_at_utc=review)

    def test_deterministic_nonsecret_bytes_never_release_authority(self):
        left = self.propose()
        right = self.propose()
        self.assertEqual(left, right)
        self.assertEqual(len(left["unsigned_payload_sha256"]), 64)
        decoded = json.loads(left["unsigned_payload_utf8"].decode("ascii"))
        self.assertEqual(decoded["proof_status"],
                         "UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED")
        self.assertEqual(decoded["ordinal"], 1)
        self.assertEqual(decoded["predecessor_series_id"], ORIGINAL_SERIES)
        self.assertEqual(decoded["rpc"], RPC)
        self.assertNotIn("password", left["unsigned_payload_utf8"].decode())
        self.assertLessEqual(len(left["unsigned_payload_utf8"]), 2048)
        for field in (
            "cloud_reader_authenticated", "cloud_commit_independently_proven",
            "originalhost_tpm_cms_signature_produced",
            "originalhost_tpm_acl_independent", "independent_offdb_custody_proven",
            "exclusive_cas_attempt_coverage_proven", "cas_dispatch_authorized",
            "old_writer_auto_rearm_allowed", "v3_paper_release_authorized",
        ):
            self.assertIs(left[field], False, field)

    def test_key_order_of_readback_does_not_change_canonical_digest(self):
        intent, row = fixture()
        a = self.propose(intent, row)
        b = self.propose(intent, dict(reversed(list(row.items()))))
        self.assertEqual(a["unsigned_payload_utf8"], b["unsigned_payload_utf8"])

    def test_missing_or_untrusted_arbitrary_status_fields_fail_closed(self):
        intent, row = fixture()
        for mutated in [
            None, {}, {**row, "cloud_verified": True},
            {k: v for k, v in row.items() if k != "next_ordinal"},
        ]:
            with self.subTest(mutated=mutated):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, mutated)

    def test_wrong_source_fence_rpc_epoch_and_request_denied(self):
        intent, row = fixture()
        for name, bad in [
            ("epoch_id", "V3CAS-AUDIT-" + "0" * 32),
            ("rpc", "public.any_other_rpc"),
            ("source_sha256", "e" * 64),
            ("fence_sha256", "e" * 64),
            ("request_sha256", "e" * 64),
            ("intent_id", "123e4567-e89b-42d3-a456-426614174001"),
            ("predecessor_series_id", "PAPER-V3-FOREIGN"),
            ("intent_sha256", "e" * 64),
        ]:
            modified = deepcopy(row)
            modified[name] = bad
            with self.subTest(name=name):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, modified)

    def test_first_attempt_only_and_reconstructed_digest(self):
        intent, row = fixture()
        for invalid in [replace(intent, digest="0" * 64),
                        replace(intent, ordinal=2),
                        replace(intent, rpc="public.fake")]:
            with self.assertRaises(PreinvokeHold):
                self.propose(invalid, row)

    def test_missing_gap_duplicate_and_out_of_order_intents(self):
        intent, row = fixture()
        for ordered in [[], ["f" * 64], [intent.digest, intent.digest],
                        ["e" * 64, intent.digest], "not-a-list"]:
            modified = deepcopy(row)
            modified["ordered_intent_sha256"] = ordered
            with self.subTest(ordered=ordered):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, modified)

    def test_non_boolean_or_invalid_ordinal_counter(self):
        intent, row = fixture()
        for value in [1, 3, True, "2", 0, -1]:
            modified = deepcopy(row)
            modified["next_ordinal"] = value
            with self.subTest(value=value):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, modified)
        modified = deepcopy(row)
        modified["ordinal"] = True
        with self.assertRaises(PreinvokeHold):
            self.propose(intent, modified)

    def test_stale_future_invalid_timestamps_hold(self):
        intent, row = fixture()
        for observed in ["2026-10-26T14:58:00Z",
                         "2026-10-26T15:01:00Z",
                         "2026-10-26T15:00:00+00:00",
                         "2026-02-30T15:00:00Z", None]:
            modified = deepcopy(row)
            modified["observed_at_utc"] = observed
            with self.subTest(observed=observed):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, modified)
        for reviewed in ["2026-10-26T15:03:00Z",
                         "2026-10-26T14:59:59Z",
                         "2026-10-26T15:00:15+00:00"]:
            with self.subTest(reviewed=reviewed):
                with self.assertRaises(PreinvokeHold):
                    self.propose(intent, row, reviewed)

    def test_entire_contract_stays_offline_and_cannot_become_cas_caller(self):
        source = (ROOT / "tools/v3_cas_preinvoke_protocol_INACTIVE.py").read_text("utf-8")
        self.assertIn("V3_CAS_PREINVOKE_PROTOCOL_SOURCE_UNCONDITIONALLY_LOCKED", source)
        self.assertNotIn("supabase.create_client", source)
        self.assertNotIn("PGPASSWORD", source)
        self.assertNotIn("Invoke-RestMethod", source)
        self.assertNotIn("CryptoSupportSvc", source)
        self.assertIn("cloud_reader_authenticated", source)
        self.assertIn("originalhost_tpm_acl_independent", source)


if __name__ == "__main__":
    unittest.main()
