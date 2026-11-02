"""Narrow source guard for the existing private V3 CAS prepared-fence abort.
Not a replacement for disposable PostgreSQL 17 tests or physical issuer ACK.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "supabase" / "v3-cas-prepared-fence-abort-INACTIVE.sql"

class V3PreparedAbortSourcePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SOURCE.read_text(encoding="utf-8")
        cls.code = re.sub(r"(?m)^--[^\n]*", "", cls.sql)

    def test_first_effectful_statement_hardlocked(self):
        self.assertRegex(self.code, r"(?s)^\s*BEGIN;\s*DO \$locked\$\s*BEGIN\s*RAISE EXCEPTION")
        self.assertIn("V3_PREPARED_ABORT_SOURCE_INACTIVE_NO_PRODUCTION_INSTALL", self.sql)
        self.assertLess(self.code.index("RAISE EXCEPTION"), self.code.index("CREATE TABLE"))

    def test_no_parallel_cas_executor_or_public_permissions(self):
        self.assertEqual(len(re.findall(r"(?i)\bCREATE TABLE\b", self.code)), 1)
        self.assertEqual(len(re.findall(r"(?i)\bCREATE FUNCTION\b", self.code)), 2)
        self.assertNotRegex(self.code, r"(?i)\bCREATE (?:ROLE|SCHEMA|EXTENSION)\b")
        self.assertIn("FORCE ROW LEVEL SECURITY", self.code)
        self.assertIn("REVOKE ALL ON FUNCTION", self.code)
        self.assertIn("FROM PUBLIC,anon,authenticated,service_role", self.code)
        self.assertNotRegex(self.code, r"(?im)^\s*(?:UPDATE|DELETE|TRUNCATE)\s+v3_cas_audit\.prepared_fence_abort_v1")

    def test_aborted_epoch_blocks_future_intent_and_unknown(self):
        for v in (
            "reject_aborted_epoch_dispatch_v1",
            "v3_reject_aborted_intent_insert_v1",
            "v3_reject_aborted_attempt_insert_v1",
            "BEFORE INSERT ON v3_cas_audit.intent_v1",
            "BEFORE INSERT ON v3_cas_audit.attempt_v1",
            "FOR SHARE",
            "V3_ABORTED_EPOCH_CANNOT_APPEND_INTENT_OR_ATTEMPT",
        ):
            self.assertIn(v, self.code)
        self.assertEqual(len(re.findall(r"(?i)\bCREATE TRIGGER\b", self.code)), 2)

    def test_existing_force_rls_owner_read_is_exact_and_nologin(self):
        for value in (
            "v3_cas_epoch_owner_abort_read_v1",
            "v3_cas_epoch_owner_abort_update_v1",
            "v3_cas_intent_owner_abort_read_v1",
            "FOR SELECT TO v3_cas_audit_table_owner USING(true)",
            "FOR UPDATE TO v3_cas_audit_table_owner USING(true)",
        ):
            self.assertIn(value, self.code)
        self.assertEqual(self.code.count("FOR SELECT TO v3_cas_audit_table_owner"), 2)
        self.assertNotRegex(self.code, r"(?i)GRANT SELECT ON v3_cas_audit\\.(?:epoch_v1|intent_v1) TO (?:PUBLIC|service_role)")

    def test_receipt_is_not_release_or_auto_rearm(self):
        for token in [
            "session_user <> 'v3_cas_inhibit_issuer_actor'",
            "FOR UPDATE", "NOT e.sealed", "e.next_ordinal=1",
            "v3_cas_audit.intent_v1", "v3_cas_audit.attempt_v1",
            "i.state='INHIBITED'", "i.native_stop_at_utc IS NULL",
            "i.acknowledged_at_utc IS NULL",
            "rolname='v3_cas_executor_actor'", "rolname='v3_cas_executor'",
            "ABORT_RECORDED_NOT_RELEASED",
        ]:
            self.assertIn(token, self.code)
        self.assertNotRegex(self.code, r"(?im)^\s*(?:ALTER ROLE|CREATE USER|INSERT INTO public\.paper_series)")
        self.assertNotRegex(self.code, r"(?i)\b(?:Stop|Start|Enable|Disable)-ScheduledTask\b")

if __name__ == "__main__":
    unittest.main()
