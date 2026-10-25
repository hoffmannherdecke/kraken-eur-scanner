"""Offline-only V3 CAS preinvoke audit source-contract tests.

sqlite is used to illustrate TRANSACTION boundaries, not to validate
PostgreSQL/Supabase privileges or certify original Cloud durability.
No network, no external CAS, no Mini-PC and no production DB writes.
"""
from __future__ import annotations

from dataclasses import asdict
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from uuid import uuid4

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from v3_cas_preinvoke_protocol_INACTIVE import (
    ORIGINAL_SERIES, RPC, PreinvokeHold, build_unsigned_intent,
    invoke_v3_paper_cas, review_untrusted_audit_readback,
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
        self.assertNotIn("grant insert on v3_cas_audit.intent_v1",executable.lower())
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


if __name__ == "__main__":
    unittest.main()
