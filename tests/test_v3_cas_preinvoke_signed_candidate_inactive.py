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
    build_unsigned_cms_from_original_reader_export,
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
        "caller_acl_sha256": "e" * 64,
        "intent_sha256": intent.digest, "next_ordinal": 2,
        "ordered_intent_sha256": [intent.digest],
        "observed_at_utc": "2026-10-26T15:00:00Z",
    }
    return intent, readback


_UNSET = object()


class UnsignedPreinvokeCmsCandidateSourceTests(unittest.TestCase):
    def propose(self, intent=None, readback=_UNSET, review="2026-10-26T15:00:15Z"):
        good_intent, good_row = fixture()
        return build_unsigned_preinvoke_cms_proposal(
            good_intent if intent is None else intent,
            good_row if readback is _UNSET else readback,
            reviewed_at_utc=review,
            expected_caller_acl_sha256="e" * 64)

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
        self.assertEqual(decoded["caller_acl_sha256"], "e" * 64)
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
            ("caller_acl_sha256", "f" * 64),
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

    def test_unpinned_or_drifting_caller_acl_denied(self):
        intent, row = fixture()
        for pin in ("f" * 64, "G" * 64, "", None):
            with self.subTest(pin=pin), self.assertRaises(PreinvokeHold):
                build_unsigned_preinvoke_cms_proposal(
                    intent, row, reviewed_at_utc="2026-10-26T15:00:15Z",
                    expected_caller_acl_sha256=pin)
        with self.assertRaises(PreinvokeHold):
            self.propose(intent, {**row, "caller_acl_sha256": "f" * 64})

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


    def original_reader_export(self):
        intent, _ = fixture()
        row = {
            "kind": "V3_ORIGINAL_READER_DURABLE_PREINVOKE_INTENT_V1",
            "observed_at_utc": "2026-10-26T15:00:00.123456Z",
            "actor": "v3_cas_audit_reader_actor",
            "role": "v3_cas_audit_reader",
            "epoch_count": 1, "intent_count": 1,
            "epoch_id": intent.epoch_id, "intent_id": intent.intent_id,
            "predecessor_series_id": ORIGINAL_SERIES,
            "expected_rpc": RPC, "intent_rpc": RPC,
            "source_sha256": intent.source_sha256,
            "intent_source_sha256": intent.source_sha256,
            "fence_sha256": intent.fence_sha256,
            "intent_fence_sha256": intent.fence_sha256,
            "caller_acl_sha256": "e" * 64,
            "request_sha256": intent.request_sha256,
            "ordinal": 1, "next_ordinal": 2,
            "intent_state": "PREINVOKE_INTENT", "sealed": False,
            "opened_at_utc": "2026-10-26T14:59:00.000000Z",
            "intent_created_at_utc": "2026-10-26T14:59:59.000000Z",
        }
        report = {
            "kind": row["kind"],
            "status": "CURRENT_ONE_COMMITTED_PREINVOKE_INTENT_NOT_CAS_RELEASE",
            **{key: row[key] for key in (
                "observed_at_utc", "epoch_id", "intent_id",
                "source_sha256", "fence_sha256", "caller_acl_sha256",
                "request_sha256")},
            "original_reader_row_for_future_cms_proposal": row,
            "independent_tls_certificate_verified": False,
            "historical_cas_never_proven": False,
            "complete_cas_attempt_custody_proven": False,
            "originalhost_authenticated_here": False,
            "cloud_cas_authorized": False,
            "precommit_restore_authorized": False,
            "v3_paper_release_authorized": False,
        }
        return report

    def bridge(self, report):
        return build_unsigned_cms_from_original_reader_export(
            report,
            expected_source_sha256="c" * 64,
            expected_fence_sha256="d" * 64,
            expected_caller_acl_sha256="e" * 64,
            reviewed_at_utc="2026-10-26T15:00:15Z",
        )

    def test_original_postcommit_reader_export_canonical_bridge_only(self):
        report = self.original_reader_export()
        result = self.bridge(report)
        self.assertEqual(result["kind"], "V3_CAS_PREINVOKE_CMS_CANDIDATE_REVIEW_V2")
        payload = json.loads(result["unsigned_payload_utf8"])
        intent, original_row = fixture()
        self.assertEqual(payload["intent_sha256"], intent.digest)
        self.assertRegex(payload["readback_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(payload["source_sha256"], intent.source_sha256)
        self.assertEqual(payload["fence_sha256"], intent.fence_sha256)
        self.assertEqual(payload["caller_acl_sha256"], "e" * 64)
        self.assertEqual(payload["proof_status"], "UNTRUSTED_READER_PROPOSAL_NOT_AUTHENTICATED")
        self.assertFalse(result["cloud_reader_authenticated"])
        self.assertFalse(result["original_reader_export_source_claim_is_authenticated"])
        self.assertFalse(result["actual_original_writer_commit_independently_proven"])
        self.assertFalse(result["cas_attempt_coverage_proven"])
        self.assertFalse(result["cas_dispatch_authorized"])
        self.assertFalse(result["v3_paper_release_authorized"])

    def test_original_reader_export_negative_custody_and_drift(self):
        base = self.original_reader_export()
        variants = [
            lambda r: r.pop("original_reader_row_for_future_cms_proposal"),
            lambda r: r.update(cloud_cas_authorized=True),
            lambda r: r.update(independent_tls_certificate_verified=True),
            lambda r: r.update(status="CAS_RELEASE"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(actor="postgres"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(role="postgres"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(intent_count=2),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(ordinal=True),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(next_ordinal=3),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(sealed=True),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(intent_state="UNKNOWN"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(intent_source_sha256="f"*64),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(intent_fence_sha256="f"*64),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(caller_acl_sha256="f"*64),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(request_sha256="f"*64),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(extra_proof=True),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(
                observed_at_utc="2026-10-26T15:00:00Z"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(
                opened_at_utc="2026-10-26T15:00:01.000000Z"),
            lambda r: r["original_reader_row_for_future_cms_proposal"].update(
                intent_created_at_utc="2026-10-26T14:50:00.000000Z"),
        ]
        for mutation in variants:
            wrong = deepcopy(base)
            mutation(wrong)
            with self.subTest(variation=str(mutation)), self.assertRaises(PreinvokeHold):
                self.bridge(wrong)
        with self.assertRaises(PreinvokeHold):
            build_unsigned_cms_from_original_reader_export(
                base, expected_source_sha256="f" * 64,
                expected_fence_sha256="d" * 64,
                expected_caller_acl_sha256="e" * 64,
                reviewed_at_utc="2026-10-26T15:00:15Z")
        with self.assertRaises(PreinvokeHold):
            build_unsigned_cms_from_original_reader_export(
                base, expected_source_sha256="c" * 64,
                expected_fence_sha256="d" * 64,
                expected_caller_acl_sha256="e" * 64,
                reviewed_at_utc="2026-10-26T15:02:30Z")

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
