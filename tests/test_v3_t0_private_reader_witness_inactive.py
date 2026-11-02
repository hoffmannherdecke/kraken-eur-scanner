"""Source-only fail-closed regression for proposed V3 private T0 reader witness.

These checks are NOT PG17 execution, deployment, T0, independent CMS or a
substitute for role/RLS tests in the existing disposable PostgreSQL suite.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "supabase/v3-cas-t0-private-reader-witness-INACTIVE.sql"


class TestV3T0ReadOnlyWitness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SQL.read_text(encoding="utf-8")

    def test_first_effectful_statement_is_a_hard_lock(self):
        self.assertRegex(
            self.sql,
            r"(?is)DO \$v3_t0_witness_install_locked\$\s*BEGIN\s*"
            r"RAISE EXCEPTION 'V3_T0_READER_WITNESS_SOURCE_INACTIVE_APPROVAL_REQUIRED';",
        )

    def test_one_private_reader_entry_and_no_new_storage_or_owner(self):
        s = self.sql.lower()
        self.assertEqual(
            s.count("create function v3_cas_audit.read_forward_t0_current_v1()"),
            1,
        )
        for forbidden in (
            "create table", "create role", "create schema",
            "alter role", "alter table", "grant select on",
            "grant insert on", "grant update on", "grant delete on",
            "rotate_v2r4_to_v3_experimental_paper(", "drop function",
        ):
            self.assertNotIn(forbidden, s)

    def test_always_reports_hold_for_history_and_release(self):
        s = self.sql.lower()
        for flag in (
            "'history_never_proven',false",
            "'complete_attempt_unknown_custody_authenticated',false",
            "'t0_authenticated',false",
            "'armed_marker_cancel_authorized',false",
            "'native_stop_restore_authorized',false",
            "'cas_or_v3_paper_authorized',false",
        ):
            self.assertIn(flag, s)

    def test_no_direct_audit_select_and_role_pin(self):
        s = self.sql.lower()
        self.assertIn("session_user <> 'v3_cas_audit_reader_actor'", s)
        self.assertIn(
            "pg_catalog.current_setting('role',true) <> 'v3_cas_audit_reader'", s
        )
        for table in ("attempt_v1", "executor_inhibit_v1"):
            self.assertIn(
                f"'v3_cas_audit_reader','v3_cas_audit.{table}','select'", s
            )
        self.assertIn(
            "grant execute on function v3_cas_audit.read_forward_t0_current_v1()", s
        )
        self.assertIn("to v3_cas_audit_reader", s)
        self.assertIn("from public, anon, authenticated, service_role", s)


if __name__ == "__main__":
    unittest.main()
