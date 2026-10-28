"""Offline-only V3 CAS preinvoke audit source-contract tests.

sqlite is used to illustrate TRANSACTION boundaries, not to validate
PostgreSQL/Supabase privileges or certify original Cloud durability.
No network, no external CAS, no Mini-PC and no production DB writes.
"""
from __future__ import annotations

# Reuse the existing native Architecture CI entrypoint for the new negative
# contract; never start another workflow or test service.
from tests.test_v3_cas_preinvoke_signed_candidate_inactive import (
    UnsignedPreinvokeCmsCandidateSourceTests,
)
from tests.test_v3_cas_actor_custody_gate_inactive import (
    V3CasActorCustodyReadOnlySourceTests,
)

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

    def test_stage1_actor_shell_sql_never_grants_access(self):
        src = (ROOT / "supabase/v3-cas-actor-stage1-disabled-20261026.sql").read_text("utf-8")
        executable = "\n".join(line for line in src.splitlines()
                                 if not line.lstrip().startswith("--"))
        self.assertTrue(executable.lstrip().startswith(
            "DO $v3_actor_stage1_disabled$"))
        self.assertTrue(executable.rstrip().endswith("$v3_actor_stage1_disabled$;"))
        for identity in ("v3_cas_audit_writer_actor", "v3_cas_audit_reader_actor",
                         "v3_cas_executor_actor"):
            self.assertIn("CREATE ROLE "+identity+"\n", executable)
        self.assertEqual(executable.count(
            "NOREPLICATION CONNECTION LIMIT 0 PASSWORD NULL VALID UNTIL '2000-01-01'"),3)
        for denial in (
            "V3_STAGE1_UNEXPECTED_OWNER_OR_DATABASE_HOLD",
            "V3_STAGE1_STAGE0_OR_CAS_GUARD_HOLD",
            "V3_STAGE1_QUARANTINE_TABLES_NOT_EMPTY_LOCKED_HOLD",
            "V3_STAGE1_SCHEMA_OWNER_DRIFT_HOLD",
            "V3_STAGE1_ORIGINAL_V2R4_ONLY_HOLD",
            "V3_STAGE1_ACTOR_NAME_ALREADY_PRESENT_NO_REPAIR",
            "V3_STAGE1_ORIGINAL_ACTOR_GROUP_GRAPH_DRIFT_HOLD",
            "V3_STAGE1_ORIGINAL_QUARANTINE_ACCESS_DRIFT_HOLD",
            "V3_STAGE1_NEW_ACTOR_FAILCLOSED_ATTRS_HOLD",
            "V3_STAGE1_UNEXPECTED_ACTOR_MEMBERSHIP_HOLD",
            "V3_STAGE1_UNEXPECTED_ACTOR_AUDIT_PRIVILEGE_HOLD",
        ):
            self.assertIn(denial,executable)
        for denied in ("GRANT ","CREATE FUNCTION","ALTER ROLE",
                       "LOGIN PASSWORD","SECURITY DEFINER",
                       "CREATE POLICY","UPDATE public.paper_series",
                       "ALTER DEFAULT PRIVILEGES","PGPASSWORD","CREATE EXTENSION"):
            self.assertNotIn(denied,executable.upper())
        script = (ROOT / "tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        self.assertIn('cat "$stage0_sql"',script)
        self.assertIn('cat "$stage1_sql"',script)
        self.assertIn("V3_PG17_STAGE1_DISABLED_ACTOR_SHELLS_ROLLBACK_PASS",script)
        self.assertIn("V3_PG17_STAGE1_ABSENT_STAGE0_FAILCLOSED_PASS",script)
        self.assertIn("ROLLBACK;",script)
        readback=(ROOT/"supabase/v3-cas-actor-stage1-readonly-check-20261026.sql").read_text("utf-8")
        self.assertIn("three_actor_shells_disabled",readback)
        self.assertIn("'cas_dispatch_authorized',false",readback)
        self.assertIn("'v3_paper_release_authorized',false",readback)


    def test_new_stage0_private_schema_source_has_no_runtime_grants_or_dispatch(self):
        src = (ROOT / "supabase/v3-cas-audit-stage0-private-quarantine-SOURCE-20261026.sql").read_text("utf-8")
        executable = "\n".join(x for x in src.splitlines()
                                if not x.lstrip().startswith("--"))
        self.assertEqual(executable.count("DO $v3_stage0_private$"), 1)
        self.assertTrue(executable.rstrip().endswith("$v3_stage0_private$;"))
        for marker in (
            "V3_STAGE0_ROLE_GRAPH_DRIFT_ABORT",
            "V3_STAGE0_ORIGINAL_V2R4_NOT_SOLE_ACTIVE_ABORT",
            "V3_STAGE0_CAS_ALREADY_INSTALLED_ABORT",
            "V3_STAGE0_ALREADY_PRESENT_ABORT_WITHOUT_REPAIR",
            "V3_STAGE0_ANY_RUNTIME_ACCESS_ABORT",
            "V3_STAGE0_UNEXPECTED_POLICY_ABORT",
            "ALTER TABLE v3_cas_audit.epoch_v1 FORCE ROW LEVEL SECURITY",
            "ALTER TABLE v3_cas_audit.intent_v1 FORCE ROW LEVEL SECURITY",
            "REVOKE ALL ON ALL TABLES IN SCHEMA v3_cas_audit",
        ):
            self.assertIn(marker, executable)
        # No append function, automatic schema-access policy, executable CAS
        # RPC, credential/LOGIN or privileged user membership provisioning.
        for dangerous in (
            "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION",
            "GRANT EXECUTE", "GRANT v3_cas_", "PASSWORD ",
            "CREATE ROLE", "ALTER ROLE",
            "CREATE POLICY", "SECURITY DEFINER", "INSERT INTO",
            "UPDATE public.paper_series", "set role", "pg_authid"
        ):
            self.assertNotIn(dangerous.upper(), executable.upper())
        test_script = (ROOT / "tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        self.assertIn("V3_PG17_STAGE0_PRIVATE_SCHEMA_QUARANTINE_AND_ROLLBACK_PASS", test_script)
        self.assertIn("V3_PG17_STAGE0_ROLE_DRIFT_ABORT_PASS", test_script)
        self.assertIn("cat \"$stage0_sql\"", test_script)
        self.assertIn("ROLLBACK;", test_script)


    def test_source_always_first_statement_blocked_even_if_run_accidentally(self):
        sql = (ROOT / "supabase/v3-cas-preinvoke-ledger-INACTIVE.sql").read_text("utf-8")
        executable = "\n".join(x for x in sql.splitlines() if not x.lstrip().startswith("--"))
        self.assertTrue(executable.lstrip().lower().startswith(
            "do $v3_cas_ledger_inactive$\nbegin\n  raise exception 'v3_cas_audit_ledger_source_inactive_approval_required';"
        ))
        self.assertEqual(executable.lower().count("do $v3_cas_ledger_inactive$"), 1)
        self.assertTrue(executable.rstrip().endswith("$v3_cas_ledger_inactive$;"))
        for phrase in (
            "V3_CAS_STAGE0_EXISTING_QUARANTINE_REQUIRED",
            "V3_CAS_STAGE0_QUARANTINE_DRIFT_HOLD",
            "V3_CAS_STAGE0_COLUMN_SHAPE_DRIFT_HOLD",
            "pg_catalog.to_regclass('v3_cas_audit.epoch_v1')",
            "pg_catalog.to_regclass('v3_cas_audit.intent_v1')",
            "revoke all on schema v3_cas_audit",
            "pg_catalog.pg_get_userbyid(c.relowner)='postgres'",
            "exists(select 1 from v3_cas_audit.epoch_v1)",
            "exists(select 1 from v3_cas_audit.intent_v1)",
            "pg_catalog.pg_policy",
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
            "grant create on schema v3_cas_audit to v3_cas_audit_table_owner",
            "revoke create on schema v3_cas_audit from v3_cas_audit_table_owner",
            "grant create on schema v3_cas_audit to v3_cas_audit_append_definer",
            "revoke create on schema v3_cas_audit from v3_cas_audit_append_definer",
        ):
            self.assertIn(source, executable.lower())
        self.assertNotIn("rotate_v2r4_technical_paper(", executable.lower())
        self.assertNotIn("create table v3_cas_audit.epoch_v1", executable.lower())
        self.assertNotIn("create table v3_cas_audit.intent_v1", executable.lower())
        self.assertNotIn("create schema if not exists v3_cas_audit", executable.lower())
        self.assertLess(executable.index("V3_CAS_STAGE0_EXISTING_QUARANTINE_REQUIRED"),
                        executable.index("alter table v3_cas_audit.epoch_v1 owner"))
        self.assertLess(executable.index("grant v3_cas_audit_table_owner to postgres"),
                        executable.index("alter table v3_cas_audit.epoch_v1 owner"))
        # Restricted PG17 postgres loses table-owner powers immediately on
        # ALTER OWNER. Grants and policies must be created BEFORE that.
        self.assertLess(executable.index("create policy v3_cas_epoch_writer_read_v1"),
                        executable.index("alter table v3_cas_audit.epoch_v1 owner"))
        self.assertLess(executable.index("grant select(epoch_id,next_ordinal,sealed,source_sha256"),
                        executable.index("alter table v3_cas_audit.epoch_v1 owner"))
        self.assertLess(executable.index("alter table v3_cas_audit.intent_v1 owner"),
                        executable.index("revoke v3_cas_audit_table_owner from postgres"))


    def test_stage3_offline_two_actor_source_hardlocked_and_scoped(self):
        sql=(ROOT/"supabase/v3-cas-audit-stage3-actors-enrollment-INACTIVE.sql").read_text("utf-8")
        ps=(ROOT/"tools/v3-notebook-cas-stage3-two-actor-scram-INACTIVE.ps1").read_text("utf-8")
        effective="\n".join(x for x in sql.splitlines() if not x.lstrip().startswith("--"))
        self.assertTrue(effective.lstrip().lower().startswith(
          "do $v3_cas_stage3_audit_actors$\ndeclare"))
        self.assertLess(sql.index("RAISE EXCEPTION 'V3_STAGE3_LOCAL_ENROLLMENT_TEMPLATE_INACTIVE'"),
                        sql.index("GRANT v3_cas_audit_writer TO v3_cas_audit_writer_actor"))
        for word in ("__WRITER_SCRAM_SHA256_VERIFIER__",
                     "__READER_SCRAM_SHA256_VERIFIER__",
                     "GRANT v3_cas_audit_writer TO v3_cas_audit_writer_actor",
                     "GRANT v3_cas_audit_reader TO v3_cas_audit_reader_actor",
                     "WITH ADMIN FALSE, INHERIT FALSE, SET TRUE;",
                     "V3_STAGE3_TWO_DISTINCT_SCRAM_VERIFIERS_REQUIRED",
                     "V3_STAGE3_STAGE2_PRIVATE_ACL_DRIFT_HOLD",
                     "V3_STAGE3_ACTOR_OR_GROUP_ROLE_DRIFT_HOLD",
                     "V3_STAGE3_POST_ENROLLMENT_DRIFT_ROLLBACK"):
            with self.subTest(required=word): self.assertIn(word,sql)
        for forbidden in ("CREATE ROLE", "CREATE TABLE", "CREATE FUNCTION",
                          "GRANT v3_cas_executor", "ALTER ROLE v3_cas_executor_actor LOGIN",
                          "UPDATE public.paper_series", "INSERT INTO v3_cas_audit.",
                          "DELETE FROM", "DROP ", "service_role TO"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden.upper(),effective.upper())
        self.assertIn("[switch]$Stage",ps)
        self.assertIn("[switch]$RemoveEnrollmentSql",ps)
        self.assertIn("INACTIVE_PREVIEW",ps)
        self.assertIn("DataProtectionScope]::CurrentUser",ps)
        self.assertIn("Rfc2898DeriveBytes",ps)
        self.assertIn("V3_STAGE3_HOLD_EXISTING_LOCAL_IDENTITY_NO_OVERWRITE",ps)
        self.assertIn("plaintext_password_displayed=$false",ps)
        self.assertIn("network_used=$false; cloud_mutation=$false",ps)
        self.assertNotIn("Invoke-WebRequest",ps)
        self.assertNotIn("Start-Process",ps)
        script=(ROOT/"tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        self.assertIn("V3_PG17_STAGE3_DISTINCT_WRITER_READER_ACTORS_SOURCE_TEST_PASS_CAS_OFF",script)
        self.assertIn("stage3_sql=\"supabase/v3-cas-audit-stage3-actors-enrollment-INACTIVE.sql\"",script)

    def test_approved_stage2_artifact_exactly_matches_locked_canonical_source(self):
        """The only reviewed install SQL differs by a header + one hardlock,
        not by altered permission statements or hidden CAS functionality.
        """
        original=(ROOT/"supabase/v3-cas-preinvoke-ledger-INACTIVE.sql").read_text("utf-8")
        installed=(ROOT/"supabase/v3-cas-audit-stage2-install-APPROVED-20261027.sql").read_text("utf-8")
        locked="  raise exception 'V3_CAS_AUDIT_LEDGER_SOURCE_INACTIVE_APPROVAL_REQUIRED';"
        self.assertEqual(original.count(locked),1)
        self.assertTrue(original.startswith("-- SOURCE ONLY / NEVER MIGRATE"))
        self.assertTrue(installed.startswith("-- V3 Paper controlled production Stage-2 AUDIT INSTALLATION ONLY."))
        self.assertNotIn(locked,installed)
        self.assertNotIn("create table v3_cas_audit.",installed.lower())
        self.assertNotIn("rotate_v2r4_to_v3_experimental_paper(",installed.lower())
        old_body=original.split("do $v3_cas_ledger_inactive$",1)[1]
        approved_body=installed.split("do $v3_cas_stage2_approved$",1)[1]
        expected=old_body.replace(
            locked,
            "  -- Stage-2 installation specifically approved; original source remains locked.",
            1
        ).replace("$v3_cas_ledger_inactive$;","$v3_cas_stage2_approved$;")
        self.assertEqual(approved_body,expected)
        self.assertEqual(approved_body.count("create function v3_cas_audit.append_intent_v1("),1)

    def test_pg17_distinct_scram_reader_observes_only_committed_intent(self):
        # Native disposable PG17 test uses two actual SCRAM LOGINs instead
        # of a postgres superuser impersonating both actors via SET ROLE.
        # Credentials are public CI FIXTURES, never real Cloud credentials.
        script = (ROOT / "tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        for token in (
            "--network none",
            "CREATE ROLE v3_ci_writer_login LOGIN NOINHERIT NOBYPASSRLS",
            "CREATE ROLE v3_ci_reader_login LOGIN NOINHERIT NOBYPASSRLS",
            "GRANT v3_cas_audit_writer TO v3_ci_writer_login",
            "GRANT v3_cas_audit_reader TO v3_ci_reader_login",
            "-h 127.0.0.1",
            "auth_method='scram-sha-256'",
            'sed -i "1i host postgres v3_ci_reader_login 127.0.0.1/32 scram-sha-256"',
            'sed -i "1i host postgres v3_ci_writer_login 127.0.0.1/32 scram-sha-256"',
            "SELECT pg_reload_conf();",
            "FAIL_CI_DISTINCT_READER_DID_NOT_REQUIRE_SCRAM",
            "session_user||':'||current_user",
            "FAIL_SCRAM_SEPARATE_SESSION_IDENTITIES",
            "FAIL_SCRAM_WRITER_ALLOWED_READBACK",
            "FAIL_SCRAM_READER_ALLOWED_APPEND",
            "FAIL_SCRAM_INDEPENDENT_READER_SAW_UNCOMMITTED_INTENT",
            "FAIL_SCRAM_INDEPENDENT_READER_AFTER_COMMIT_CONTENT_MISMATCH",
            "FAIL_SCRAM_READER_AND_WRITER_BACKEND_SEPARATION",
            "FAIL_SCRAM_READER_FALSE_ROLLBACK_ACK",
            "V3_PG17_DISTINCT_SCRAM_READER_AFTER_COMMIT_PASS_NO_RELEASE",
        ):
            with self.subTest(token=token):
                self.assertIn(token, script)
        self.assertLess(
            script.index("reader_precommit =") if "reader_precommit =" in script
            else script.index("reader_precommit="),
            script.index('wait "$scram_writer_pid"'))
        self.assertLess(
            script.index('wait "$scram_writer_pid"'),
            script.index("reader_postcommit="))
        # No executable production CAS or user-approved independent Cloud
        # reader is created by either test, nor a new runner/scheduler.
        self.assertNotIn("supabase.co", script)
        self.assertNotIn("pg -f supabase/v3-experimental-paper-atomic-cas", script)

    def test_preprovisioned_pg17_safe_audit_roles_are_reused_but_always_inactive(self):
        sql = (ROOT / "supabase/v3-cas-preinvoke-ledger-INACTIVE.sql").read_text("utf-8")
        for role in (
            "v3_cas_executor",
            "v3_cas_audit_writer",
            "v3_cas_audit_reader",
        ):
            self.assertIn(f"to_regrole('{role}') is null", sql)
            self.assertIn(f"create role {role} nologin noinherit nobypassrls", sql)
        for token in (
            "V3_CAS_PREPROVISIONED_NOLOGIN_ROLES_UNSAFE",
            "a.rolname='postgres'",
            "m.admin_option and not m.set_option",
            "not m.inherit_option",
            "pg_catalog.pg_auth_members",
            "not r.rolcanlogin",
            "not r.rolbypassrls",
            "not r.rolsuper",
        ):
            self.assertIn(token, sql, token)
        self.assertEqual(sql.count(
            "V3_CAS_AUDIT_LEDGER_SOURCE_INACTIVE_APPROVAL_REQUIRED"), 1)
        self.assertNotIn("create role v3_cas_executor login",sql.lower())

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


# This tests actual file creation, flush, readback and hostile filesystem states
# in a disposable CI directory. NOT a physical Mini-PC deployment or CAS.
from v3_cas_local_spool_INACTIVE import (
    LocalWitnessHold, append_local_witness_candidate,
    review_local_witness_candidate, ZERO_DIGEST,
)


class V3CasMiniPcLocalSpoolInactiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "v3cas-audit-witness"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def intent(self, ordinal=1, epoch=None):
        proposal = original_proposal()
        proposal["ordinal"] = ordinal
        if epoch is not None:
            proposal["epoch_id"] = epoch
        return build_unsigned_intent(**proposal)

    def test_real_disk_append_two_records_survives_reader_restart_without_authority(self):
        empty = review_local_witness_candidate(self.root)
        self.assertEqual(empty["local_records_checked"], 0)
        self.assertFalse(empty["historical_cas_never_invoked_proven"])
        self.assertFalse(empty["cloud_cas_authorized"])
        one = self.intent()
        first = append_local_witness_candidate(self.root, one)
        self.assertEqual(first["local_records_checked"], 1)
        self.assertNotEqual(first["last_entry_sha256"], ZERO_DIGEST)
        two = self.intent(ordinal=2)
        second = append_local_witness_candidate(self.root, two)
        self.assertEqual(second["local_records_checked"], 2)
        raw1 = json.loads((self.root / "000001.json").read_text("ascii"))
        raw2 = json.loads((self.root / "000002.json").read_text("ascii"))
        self.assertEqual(raw2["previous_entry_sha256"], raw1["entry_sha256"])
        reread = review_local_witness_candidate(self.root)
        self.assertEqual(reread["last_entry_sha256"], second["last_entry_sha256"])
        for flag in (
            "originalhost_identity_authenticated",
            "independent_offdb_durable_storage_proven",
            "exclusive_cas_attempt_coverage_proven",
            "historical_cas_never_invoked_proven", "cloud_cas_authorized",
            "old_writer_auto_rearm_allowed", "native_restore_authorized",
            "v3_paper_release_authorized",
        ):
            self.assertFalse(reread[flag], flag)

    def test_real_disk_duplicate_wrong_order_and_foreign_epoch_hold(self):
        first = self.intent()
        append_local_witness_candidate(self.root, first)
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, first)
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, self.intent(ordinal=3))
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, self.intent(
                ordinal=2, epoch="V3CAS-AUDIT-" + "9" * 32))
        self.assertEqual(review_local_witness_candidate(self.root)["local_records_checked"], 1)

    def test_real_disk_corrupted_or_injected_record_cannot_be_silently_repaired(self):
        append_local_witness_candidate(self.root, self.intent())
        record = self.root / "000001.json"
        original = record.read_bytes()
        record.write_bytes(original.replace(b'"entry_sha256":"', b'"entry_sha256":"f', 1))
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, self.intent(ordinal=2))
        # A canonical-looking record with a self-authorization field is still rejected.
        record.write_bytes(original)
        hostile = json.loads(original)
        hostile["v3_paper_release_authorized"] = True
        record.write_text(json.dumps(hostile, sort_keys=True, separators=(",", ":")), "ascii")
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)

    def test_partial_crash_entry_blocks_retry_and_no_auto_recovery(self):
        (self.root / "000001.json").write_bytes(b'{"kind":')
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, self.intent())
        self.assertEqual((self.root / "000001.json").read_bytes(), b'{"kind":')

    def test_gap_extra_file_and_symlink_are_not_accepted(self):
        (self.root / "000003.json").write_text("{}", "ascii")
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)
        (self.root / "000003.json").unlink()
        (self.root / "unexpected.log").write_bytes(b"")
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)
        (self.root / "unexpected.log").unlink()
        import os
        external = pathlib.Path(self.tmp.name) / "outside"
        external.write_text("secret", "ascii")
        try:
            os.symlink(external, self.root / "000001.json")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"test platform does not allow symlink: {type(exc).__name__}")
        with self.assertRaises(LocalWitnessHold):
            review_local_witness_candidate(self.root)

    def test_invalid_dataclass_digest_cannot_be_committed(self):
        from dataclasses import replace
        tampered = replace(self.intent(), digest="a" * 64)
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(self.root, tampered)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_or_linked_directory_cannot_be_created_implicitly(self):
        missing = self.root / "not-created"
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(missing, self.intent())
        import os
        link = pathlib.Path(self.tmp.name) / "linked"
        try:
            os.symlink(self.root, link, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"test platform does not allow symlink: {type(exc).__name__}")
        with self.assertRaises(LocalWitnessHold):
            append_local_witness_candidate(link, self.intent())



class V3CasPublicSigstoreProviderSourceTests(unittest.TestCase):
    """Source-only negative policy. Real Sigstore provider verified on protected PUSH."""

    def test_public_subject_does_not_claim_real_host_or_release(self):
        p = ROOT / "research/v3/v3_cas_sigstore_provider_probe_v1.json"
        raw = p.read_bytes()
        self.assertLess(len(raw), 1024)
        subject = json.loads(raw)
        expected = {
            "kind": "V3_CAS_PUBLIC_SIGSTORE_PROVIDER_PROBE_V1",
            "schema_version": 1,
            "data_classification": "PUBLIC_SYNTHETIC_ONLY",
            "proof_scope": "GITHUB_PROVENANCE_NOT_ORIGINALHOST_OR_CAS",
            "original_host_audit_intents": 0,
            "originalhost_signer_authenticated": False,
            "independent_cas_attempt_coverage_proven": False,
            "external_originalhost_worm_custody_proven": False,
            "cloud_cas_authorized": False,
            "v3_paper_activated": False,
            "source_note": (
                "Public no-secret canary. Real Windows CAS audit has no published receipt."
            ),
        }
        if "private_runner_generated_synthetic_sha256" in subject:
            import re
            source_hash = subject["private_runner_generated_synthetic_sha256"]
            self.assertIs(type(source_hash), str)
            self.assertRegex(source_hash, r"^[a-f0-9]{64}$")
            expected["proof_scope"] = (
                "PRIVATE_RUNNER_SYNTHETIC_HASH_BRIDGE_NOT_HOST_SIGNATURE"
            )
            expected["private_runner_generated_synthetic_sha256"] = source_hash
            expected["reported_hash_origin"] = (
                "PRIVATE_REVIEWED_MINIPC_TASK_NOT_INDEPENDENT_SIGNER"
            )
        self.assertEqual(subject, expected)
        self.assertEqual(raw, (json.dumps(subject, indent=2) + "\n").encode("ascii"))

    def test_exact_existing_protected_public_repo_push_with_no_scheduler(self):
        workflow = (ROOT / ".github/workflows/v3-cas-sigstore-public-witness.yml").read_text()
        for text in (
            "branches: [main]",
            "research/v3/v3_cas_sigstore_provider_probe_v1.json",
            "push:",
            "runs-on: ubuntu-latest",
            "id-token: write",
            "attestations: write",
            "artifact-metadata: write",
            "actions/attest@v4",
            "gh attestation verify",
            "--signer-workflow",
            "--source-ref refs/heads/main",
            "--deny-self-hosted-runners",
            "tlogEntries",
            "private_runner_generated_synthetic_sha256",
            "V3_PUBLIC_SIGSTORE_PRIVATE_HOST_HASH_TRANSPORT_ONLY_NOT_SIGNER",
            "V3_REAL_SIGSTORE_PUBLIC_GOOD_GITHUB_ORIGIN_AND_DIGEST_PASS",
            "V3_PHYSICAL_ORIGINALHOST_SIGSTORE_OR_CAS_RELEASE_PROOF=FALSE",
        ):
            self.assertIn(text, workflow, text)
        for unsafe in (
            "workflow_dispatch:", "schedule:", "cron:",
            "pull_request:", "runs-on: [self-hosted",
            "secrets.", "SUPABASE_SERVICE_ROLE_KEY", "KRAKEN_API_SECRET",
            "actions/upload-artifact", "aws ", "curl ",
        ):
            self.assertNotIn(unsafe, workflow, unsafe)
        self.assertEqual(workflow.count("actions/attest@v4"), 1)
        self.assertEqual(workflow.count("gh attestation verify"), 1)
        self.assertTrue(workflow.startswith("name: V3 CAS public Sigstore provider"))


class V3Stage3OriginalNotebookAuditReadOnlyWitnessTests(unittest.TestCase):
    """New original-credential reader proof is strictly one-shot and non-mutating."""

    def test_existing_stage3_dpapi_reader_writer_readonly_source(self):
        src = (ROOT / "tools/v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1").read_text("utf-8")
        self.assertIn("Add-Type -AssemblyName System.Security -ErrorAction Stop", src)
        # Original two-actor default + two mutually exclusive opt-in
        # Reader-only snapshots (current empty and future committed intent);
        # still the SAME two actors, no third credentials or CAS authority.
        self.assertEqual(src.count("BEGIN TRANSACTION READ ONLY;"), 4)
        self.assertEqual(src.count("COMMIT;"), 4)
        self.assertIn("[switch]$PrecommitCloudInventory", src)
        self.assertIn("[switch]$PostcommitDurableIntent", src)
        self.assertIn("if($PrecommitCloudInventory -and $PostcommitDurableIntent)", src)
        self.assertIn("V3_READER_MODE_CONFLICT", src)
        self.assertIn("WHERE (SELECT count(*) FROM v3_cas_audit.epoch_v1)=1", src)
        self.assertIn("CURRENT_ONE_COMMITTED_PREINVOKE_INTENT_NOT_CAS_RELEASE", src)
        self.assertIn("if($PrecommitCloudInventory)", src)
        self.assertIn("if ($passed -eq 2)", src)
        self.assertIn("writer.dpapi", src)
        self.assertIn("reader.dpapi", src)
        self.assertIn("DataProtectionScope]::CurrentUser", src)
        self.assertIn("aws-1-eu-west-1.pooler.supabase.com", src)
        # Legacy Stage3 inventory stays unchanged. Both decision-grade
        # PRE- and POST-COMMIT Reader modes enforce CA + hostname.
        self.assertIn("sslmode=require", src)
        self.assertIn("$tlsMode=if($decisionReaderMode){'verify-full'}else{'require'}", src)
        self.assertIn("$decisionReaderMode=($PrecommitCloudInventory -or $PostcommitDurableIntent)", src)
        self.assertIn("$postcommitTlsRoot='system'", src)
        self.assertIn("[string]$CaFile=''", src)
        self.assertIn("V3_READER_CA_FILE_DECISION_MODE_ONLY", src)
        self.assertIn("V3_POSTCOMMIT_READER_CA_FILE_INVALID", src)
        self.assertIn("$env:PGSSLROOTCERT=$postcommitTlsRoot", src)
        self.assertIn("if($decisionReaderMode){Remove-Item Env:\\PGSSLROOTCERT", src)
        self.assertIn("independent_tls_certificate_verified=$false", src)
        self.assertNotIn("independent_tls_certificate_verified=$true", src)
        self.assertIn("v3_cas_audit_writer_actor", src)
        self.assertIn("v3_cas_audit_reader_actor", src)
        self.assertIn("pg_catalog.pg_has_role(session_user", src)
        self.assertIn("v3_cas_audit.epoch_v1", src)
        self.assertIn("v3_cas_audit.intent_v1", src)
        # Preserve database UTC literal before ConvertFrom-Json auto-DateTime
        # conversion; original 90s freshness remains enforced, not bypassed.
        self.assertEqual(src.count("function Read-V3ReaderUtcLiteral("), 1)
        self.assertIn("V3_READER_UTC_MISSING_OR_DUPLICATE", src)
        self.assertIn("V3_READER_UTC_FORMAT_INVALID", src)
        self.assertIn("CURRENT_UTC_FORMAT", src)
        # PostgreSQL emits a canonical UTC literal without relying on nested
        # double quotes surviving Windows PowerShell 5.1 native -c arguments.
        # Same one clock_timestamp per row, no split timestamp at midnight.
        self.assertEqual(src.count("pg_catalog.replace(pg_catalog.to_char("), 4)
        self.assertIn("'YYYY-MM-DD HH24:MI:SS.US'),' ','T') || 'Z'", src)
        self.assertNotIn('YYYY-MM-DD"T"HH24:MI:SS.US"Z"', src)
        self.assertIn("([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -gt 90", src)
        self.assertIn("([datetimeoffset]::UtcNow-$at.utc).TotalSeconds -lt -5", src)
        self.assertIn("created.utc -lt $opened.utc", src)
        self.assertNotIn("[string]$row.observed_at_utc -cnotmatch 'Z$'", src)
        self.assertIn("V3_STAGE3_READONLY_AUDIT_HOLD", src)
        self.assertIn("V3_STAGE3_TWO_ORIGINAL_READONLY_AUDIT_SESSIONS_PASS_NO_CAS", src)
        for prohibited in (
            "INSERT INTO", "DELETE FROM", "UPDATE v3_cas_audit.",
            "CREATE POLICY", "CREATE ROLE", "ALTER ROLE", "DROP TABLE",
            "SET ROLE v3_cas_executor", "rotate_v2r4_to_v3_experimental_paper(",
            "Set-Clipboard", "Start-Process", "Invoke-WebRequest",
            "Get-Credential", "new-item", "Set-Content",
            "Write-Host $secret", "Write-Output $secret",
        ):
            self.assertNotIn(prohibited, src, prohibited)
        self.assertIn("Remove-Item Env:\\PGPASSWORD", src)
        self.assertNotIn("Write-Output $_.Exception.Message", src)
        self.assertIn("if ($passed -eq 2)", src)


class V3Stage4OriginalEpochPrivilegeEscrowSourceTests(unittest.TestCase):
    """No false Stage4 activation; test original privileges only offline."""

    def test_stage4_locked_and_atomic_scoped_owner_escalation(self):
        sql = (ROOT / "supabase/v3-cas-audit-stage4-original-epoch-open-INACTIVE.sql").read_text("utf-8")
        self.assertTrue(sql.startswith("-- V3 Paper Issue #99"))
        body = "\n".join(x for x in sql.splitlines() if not x.lstrip().startswith("--"))
        self.assertTrue(body.lstrip().startswith("BEGIN;\nDO $v3_stage4_source_lock$"))
        self.assertIn("RAISE EXCEPTION 'V3_STAGE4_EPOCH_OPEN_SOURCE_INACTIVE_NO_PRODUCTION_RELEASE'", body)
        self.assertTrue(body.rstrip().endswith("COMMIT;"))
        self.assertEqual(body.count("INSERT INTO v3_cas_audit.epoch_v1"), 1)
        self.assertIn("GRANT v3_cas_audit_table_owner TO postgres WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;", body)
        self.assertIn("GRANT INSERT ON v3_cas_audit.epoch_v1 TO postgres;", body)
        self.assertIn("REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;", body)
        self.assertIn("REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;", body)
        self.assertEqual(body.count("SET ROLE v3_cas_audit_table_owner;"), 2)
        self.assertEqual(body.count("RESET ROLE;"), 2)
        self.assertIn("V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD", body)
        self.assertIn("V3_STAGE4_ORIGINAL_FINGERPRINTS_MISSING_HOLD", body)
        self.assertIn("V3_STAGE4_WRONG_ACTIVE_ORIGINAL_PAPER_HOLD", body)
        self.assertIn("V3_STAGE4_EXISTING_AUDIT_EPOCH_OR_INTENT_HOLD", body)
        self.assertIn("V3_STAGE4_CAS_ALREADY_EXISTS_HOLD", body)
        self.assertIn("V3_STAGE4_ACTOR_STATE_DRIFT_HOLD", body)
        for token in ("__EPOCH_ID__", "__SOURCE_SHA256__", "__FENCE_SHA256__", "__CALLER_ACL_SHA256__"):
            self.assertGreaterEqual(body.count(token), 2, token)
        for forbidden in (
            "INSERT INTO v3_cas_audit.intent_v1",
            "UPDATE public.paper_series",
            "CREATE ROLE", "CREATE POLICY",
            "ALTER ROLE", "CREATE FUNCTION",
            "GRANT EXECUTE", "DROP TABLE",
            "GRANT UPDATE ON v3_cas_audit.epoch_v1",
            "PERFORM v3_cas_audit.append_intent_v1",
        ):
            self.assertNotIn(forbidden, body, forbidden)
        ci=(ROOT / "tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        self.assertIn("V3_PG17_STAGE4_ORIGINAL_EPOCH_PRIVILEGE_ESCROW_ROLLBACK_PASS", ci)
        self.assertIn("stage4_sql=\"supabase/v3-cas-audit-stage4-original-epoch-open-INACTIVE.sql\"", ci)
        self.assertIn('src=src.replace("COMMIT;\\n-- Even an actual","ROLLBACK;\\n-- Even an actual",1)', ci)


class V3Stage5OriginalEpochSealSourceTests(unittest.TestCase):
    """Independent Stage5 seal is inert and cannot authorize a real CAS."""

    def test_locked_original_seal_requires_exact_single_committed_intent(self):
        source = (ROOT / "supabase/v3-cas-audit-stage5-original-epoch-seal-INACTIVE.sql").read_text("utf-8")
        self.assertIn("V3_STAGE5_EPOCH_SEAL_SOURCE_INACTIVE_APPROVAL_REQUIRED", source)
        self.assertEqual(source.count("BEGIN;"), 1)
        self.assertEqual(source.count("COMMIT;"), 1)
        self.assertIn("GRANT v3_cas_audit_table_owner TO postgres", source)
        self.assertIn("REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres", source)
        self.assertIn("GRANT UPDATE (sealed)", source)
        self.assertIn("REVOKE UPDATE (sealed)", source)
        self.assertIn("SET ROLE v3_cas_audit_table_owner", source)
        self.assertIn("V3_STAGE5_SEAL_DURABLE_EXACT_INTENT_NOT_VISIBLE_HOLD", source)
        self.assertIn("V3_STAGE5_SEAL_POSTFLIGHT_RIGHTS_REMAIN_HOLD", source)
        self.assertIn("i.ordinal=1 AND i.intent_id=v_intent", source)
        self.assertIn("i.request_sha256=v_request", source)
        self.assertIn("i.created_at_utc>pg_catalog.clock_timestamp()-interval '5 minutes'", source)
        self.assertIn("v3_cas_executor_actor", source)
        self.assertIn("UPDATE v3_cas_audit.epoch_v1 SET sealed=true", source)
        for forbidden in ("CREATE ROLE", "CREATE FUNCTION", "CREATE POLICY", "INSERT INTO", "UPDATE public.paper_series", "DROP TABLE", "GRANT EXECUTE", "SET ROLE v3_cas_executor;"):
            self.assertNotIn(forbidden, source)
        contract = (ROOT / "tests/v3_cas_postgres_ephemeral_contract.sh").read_text("utf-8")
        self.assertIn("V3_PG17_STAGE5_REAL_SYNTHETIC_SEAL_RESTORE_PASS", contract)
        self.assertIn("FAIL_STAGE5_SEAL_LOCK_EXECUTED", contract)
        self.assertIn("FAIL_STAGE5_SEAL_REPLAY_ACCEPTED", contract)
        self.assertIn("pg_root_db -f - <<'SQL'", contract)

if __name__ == "__main__":
    unittest.main()
