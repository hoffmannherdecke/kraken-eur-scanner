"""Offline-only V3 CAS preinvoke audit source-contract tests.

sqlite is used to illustrate TRANSACTION boundaries, not to validate
PostgreSQL/Supabase privileges or certify original Cloud durability.
No network, no external CAS, no Mini-PC and no production DB writes.
"""
from __future__ import annotations

from dataclasses import asdict
import pathlib
import sqlite3
import hmac
import hashlib
import json
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from v3_cas_preinvoke_protocol_INACTIVE import (
    ORIGINAL_SERIES, RPC, PreinvokeHold, build_unsigned_intent,
    invoke_v3_paper_cas, review_untrusted_audit_readback,
    review_offdb_witness_hmac_packet, WITNESS_KIND, WITNESS_DOMAIN, WITNESS_KEYS,
)


def original_proposal():
    return {
        "epoch_id": "V3CAS-AUDIT-" + "a" * 32,
        "ordinal": 1,
        "intent_id": str(uuid4()),
        "predecessor_series_id": ORIGINAL_SERIES,
        "rpc": RPC,
        "request_sha256": "b" * 64,
        "source_sha256": "c" * 64,
        "fence_sha256": "d" * 64,
    }


class V3CasAuditInactiveTests(unittest.TestCase):
    def test_source_always_first_statement_blocked_even_if_run_accidentally(self):
        sql = (ROOT / "supabase/v3-cas-preinvoke-ledger-INACTIVE.sql").read_text("utf-8")
        executable = "\n".join(x for x in sql.splitlines() if not x.lstrip().startswith("--"))
        self.assertTrue(executable.lstrip().lower().startswith(
            "do $v3_cas_ledger_inactive$\nbegin\n  raise exception 'v3_cas_audit_ledger_source_inactive_approval_required';"
        ))
        self.assertEqual(executable.lower().count("do $v3_cas_ledger_inactive$"), 1)
        self.assertTrue(executable.rstrip().endswith("$v3_cas_ledger_inactive$;"))
        for phrase in (
            "create schema if not exists v3_cas_audit",
            "revoke all on schema v3_cas_audit",
            "create table v3_cas_audit.epoch_v1",
            "create table v3_cas_audit.intent_v1",
            "primary key(epoch_id,ordinal)",
            "intent_id uuid not null unique",
            "next_ordinal bigint not null",
            "state = 'PREINVOKE_INTENT'",
            "enable row level security",
            "force row level security",
            "from public, anon, authenticated, service_role",
        ):
            self.assertIn(phrase, sql)
        # The future SECURITY DEFINER is still behind the original
        # unconditional DO-first-RAISE. Never grant executable CAS RPC or
        # expose append to PUBLIC/anon/authenticated/shared service_role.
        self.assertEqual(executable.lower().count("security definer"),1)
        self.assertIn("set search_path = pg_catalog, v3_cas_audit",executable)
        self.assertIn("for update",executable)
        self.assertIn("set next_ordinal = next_ordinal + 1",executable)
        self.assertIn("grant execute on function v3_cas_audit.append_intent_v1",executable)
        self.assertIn("to v3_cas_audit_writer;",executable)
        self.assertIn("from public, anon, authenticated, service_role,",executable)
        self.assertNotIn("grant execute on function public.",executable.lower())
        self.assertNotIn("grant update(next_ordinal)",executable.lower())
        self.assertNotIn(
            "grant insert on v3_cas_audit.intent_v1\n    to v3_cas_audit_writer;",
            executable.lower()
        )
        for source in (
            "create role v3_cas_audit_table_owner nologin noinherit nobypassrls",
            "create role v3_cas_audit_append_definer nologin noinherit nobypassrls",
            "alter table v3_cas_audit.epoch_v1 owner to v3_cas_audit_table_owner",
            "alter table v3_cas_audit.intent_v1 owner to v3_cas_audit_table_owner",
            "create policy v3_cas_epoch_definer_update_v1",
            "create policy v3_cas_intent_definer_insert_v1",
            "owner to v3_cas_audit_append_definer",
        ):
            self.assertIn(source, executable.lower())
        self.assertNotIn("rotate_v2r4_technical_paper(", executable.lower())

    def test_candidate_canonical_digest_is_stable_and_no_secrets(self):
        inputs = original_proposal()
        one = build_unsigned_intent(**inputs)
        two = build_unsigned_intent(**inputs)
        self.assertEqual(one.digest, two.digest)
        self.assertEqual(len(one.digest), 64)
        self.assertNotIn("service_role", repr(asdict(one)))
        self.assertEqual(one.epoch_id, inputs["epoch_id"])

    def test_scope_rejections_fail_closed(self):
        cases = (
            {"epoch_id": "old"},
            {"ordinal": 0},
            {"ordinal": True},
            {"intent_id": "not-a-uuid"},
            {"predecessor_series_id": "PAPER-V3-UNAUTHORISED"},
            {"rpc": "public.rotate_v2r4_technical_paper"},
            {"request_sha256": "F" * 64},
            {"source_sha256": "bad"},
            {"fence_sha256": ""},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(PreinvokeHold):
                build_unsigned_intent(**(original_proposal() | changes))

    def test_every_untrusted_ack_is_always_hold(self):
        intent = build_unsigned_intent(**original_proposal())
        row = {
            "epoch_id": intent.epoch_id, "ordinal": intent.ordinal,
            "intent_id": intent.intent_id,
            "predecessor_series_id": intent.predecessor_series_id,
            "requested_rpc": intent.rpc,
            "request_sha256": intent.request_sha256,
            "source_sha256": intent.source_sha256,
            "fence_sha256": intent.fence_sha256,
        }
        for testrow, expected in (
            (None, "HOLD_NO_INDEPENDENT_DURABLE_ACK"),
            ({}, "HOLD_AUDIT_ACK_MISMATCH_OR_REPLAY"),
            (row | {"ordinal": True}, "HOLD_AUDIT_ACK_MISMATCH_OR_REPLAY"),
            (row | {"source_sha256": "f" * 64}, "HOLD_AUDIT_ACK_MISMATCH_OR_REPLAY"),
            (row, "HOLD_PERSISTED_INTENT_OR_UNKNOWN_DISPATCH"),
        ):
            result = review_untrusted_audit_readback(intent, testrow)
            self.assertEqual(result["disposition"], expected)
            self.assertTrue(all(result[k] is False for k in (
                "caller_supplied_row_authenticated",
                "ack_durably_committed_independently_verified",
                "preinvoke_audit_epoch_complete",
                "historical_cas_never_invoked_proven",
                "cas_dispatch_authorized",
                "native_restore_authorized",
                "old_writer_auto_rearm_allowed",
                "v3_paper_release_authorized",
            )))

    def test_cas_function_never_invokes_any_caller_callback(self):
        count = []
        with self.assertRaisesRegex(PreinvokeHold, "SOURCE_UNCONDITIONALLY_LOCKED"):
            invoke_v3_paper_cas(callback=lambda: count.append("CALLED"))
        self.assertEqual(count, [])

    def test_precommit_durability_vs_same_transaction_rollback_simulation(self):
        # Two actual sqlite connections only, NOT real Postgres evidence.
        # The first audit is committed BEFORE a separate failed transaction.
        with tempfile.TemporaryDirectory() as tmp:
            dbpath = pathlib.Path(tmp) / "audit-simulation.db"
            auditor = sqlite3.connect(str(dbpath), isolation_level=None)
            caller = sqlite3.connect(str(dbpath), isolation_level=None)
            try:
                auditor.execute("create table intent (id text primary key, ordinal integer unique)")
                auditor.execute("BEGIN IMMEDIATE")
                auditor.execute("insert into intent values ('committed-before-rpc', 1)")
                auditor.execute("COMMIT")
                self.assertEqual(caller.execute("select count(*) from intent").fetchone()[0], 1)
                caller.execute("BEGIN")
                caller.execute("ROLLBACK")  # Simulated CAS failure cannot erase first commit.
                self.assertEqual(auditor.execute("select count(*) from intent").fetchone()[0], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    auditor.execute("insert into intent values ('committed-before-rpc', 2)")
                auditor.execute("BEGIN IMMEDIATE")
                auditor.execute("insert into intent values ('rolled-back-with-rpc', 2)")
                auditor.execute("ROLLBACK")
                self.assertEqual(caller.execute("select count(*) from intent").fetchone()[0], 1)
            finally:
                caller.close()
                auditor.close()



    @staticmethod
    def _signed_witness_fixture(intent):
        """Only a synthetic test key and fictional external digest."""
        receipt = {
            "kind": WITNESS_KIND,
            "witness_id": "synthetic-external-witness",
            "epoch_id": intent.epoch_id,
            "last_ordinal": 1,
            "ordered_intent_sha256": [intent.digest],
            "external_commit_sha256": "a" * 64,
            "signed_at_utc": "2026-10-25T19:00:00Z",
        }
        V3CasAuditInactiveTests._resign_fixture(receipt)
        return receipt

    @staticmethod
    def _resign_fixture(receipt):
        data = {k: receipt[k] for k in WITNESS_KEYS}
        payload = WITNESS_DOMAIN + json.dumps(
            data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        receipt["hmac_sha256"] = hmac.new(b"x" * 32, payload, hashlib.sha256).hexdigest()

    @staticmethod
    def _review_fixture(intent, receipt, **changes):
        opts = {
            "expected_witness_id": "synthetic-external-witness",
            "verification_key": b"x" * 32,
            "reviewed_at_utc": "2026-10-25T19:01:00Z",
        }
        opts.update(changes)
        return review_offdb_witness_hmac_packet(intent, receipt, **opts)

    def test_signed_witness_valid_mac_still_never_authorizes_release(self):
        intent = build_unsigned_intent(**original_proposal())
        result = self._review_fixture(intent, self._signed_witness_fixture(intent))
        self.assertEqual(result["disposition"], "REVIEW_ONLY_MAC_MATCH_CUSTODY_UNPROVEN")
        self.assertTrue(result["mac_matches_supplied_key"])
        for key, value in result.items():
            if key.endswith("_authorized") or key.endswith("_proven") or key.endswith("_allowed"):
                self.assertFalse(value, key)

    def test_signed_witness_forgery_missing_stale_gap_unauthorized(self):
        intent = build_unsigned_intent(**original_proposal())
        valid = self._signed_witness_fixture(intent)
        altered = [
            None,
            dict(valid, hmac_sha256="0" * 64),
            dict(valid, witness_id="different-witness"),
            dict(valid, epoch_id="V3CAS-AUDIT-" + "c" * 32),
            dict(valid, external_commit_sha256="b" * 64),
            dict(valid, last_ordinal=2),
            dict(valid, last_ordinal=True),
            dict(valid, ordered_intent_sha256=[]),
            dict(valid, ordered_intent_sha256=["f" * 64]),
            dict(valid, signed_at_utc="2026-10-25T18:50:00Z"),
            dict(valid, signed_at_utc="2026-10-25T19:05:00Z"),
            dict(valid, v3_paper_release_authorized=True),
        ]
        for receipt in altered:
            with self.subTest(receipt=receipt):
                result = self._review_fixture(intent, receipt)
                self.assertTrue(result["disposition"].startswith("HOLD_"))
                self.assertFalse(result["mac_matches_supplied_key"])
                self.assertFalse(result["cas_dispatch_authorized"])
                self.assertFalse(result["old_writer_auto_rearm_allowed"])
        for changes in [
            {"verification_key": b"y" * 32},
            {"verification_key": b"too-short"},
            {"expected_witness_id": "wrong-witness"},
            {"reviewed_at_utc": "2026-10-25T18:59:00Z"},
            {"reviewed_at_utc": "2026-10-25 19:01:00"},
        ]:
            with self.subTest(changes=changes):
                result = self._review_fixture(intent, valid, **changes)
                self.assertTrue(result["disposition"].startswith("HOLD_"))

    def test_signed_witness_fabricated_external_storage_still_not_proof(self):
        intent = build_unsigned_intent(**original_proposal())
        receipt = self._signed_witness_fixture(intent)
        receipt["external_commit_sha256"] = "f" * 64
        self._resign_fixture(receipt)
        result = self._review_fixture(intent, receipt)
        self.assertTrue(result["mac_matches_supplied_key"])
        self.assertFalse(result["independent_offdb_durable_storage_proven"])
        self.assertFalse(result["real_witness_issuer_authenticated"])
        self.assertFalse(result["historical_cas_never_invoked_proven"])


if __name__ == "__main__":
    unittest.main()
