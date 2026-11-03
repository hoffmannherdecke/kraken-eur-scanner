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

    def test_independent_reader_only_receipt_access(self):
        self.assertIn("CREATE POLICY v3_prepared_abort_reader_select_v1", self.code)
        self.assertIn("FOR SELECT TO v3_cas_audit_reader USING (true)", self.code)
        self.assertIn("GRANT SELECT ON v3_cas_audit.prepared_fence_abort_v1 TO v3_cas_audit_reader", self.code)
        self.assertIn("'INSERT,UPDATE,DELETE'", self.code)
        self.assertIn("'v3_cas_audit_reader'", self.code)
        self.assertNotRegex(
            self.code,
            r"(?i)GRANT (?:ALL|INSERT|UPDATE|DELETE) ON v3_cas_audit\.prepared_fence_abort_v1 TO v3_cas_audit_reader",
        )

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

    def test_stage5_rejects_missing_or_terminal_abort_ledger(self):
        stage5 = (ROOT / "supabase" / "v3-cas-audit-stage5-original-epoch-seal-INACTIVE.sql").read_text(encoding="utf-8")
        # The Stage5 template remains independently hardlocked. It must not
        # proceed when the abort ledger is absent or the current epoch was
        # terminally aborted, even if another path could surface an intent.
        self.assertIn("V3_STAGE5_EPOCH_SEAL_SOURCE_INACTIVE_APPROVAL_REQUIRED", stage5)
        self.assertIn("to_regclass('v3_cas_audit.prepared_fence_abort_v1') IS NULL", stage5)
        self.assertTrue(
            "OR EXISTS (SELECT 1 FROM v3_cas_audit.prepared_fence_abort_v1" in stage5
            and "WHERE epoch_id=v_id)" in stage5
        )
        self.assertLess(stage5.index("prepared_fence_abort_v1"), stage5.index("UPDATE v3_cas_audit.epoch_v1 SET sealed=true"))

    def test_originalhost_signed_abort_review_cannot_claim_release(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Test-V3Pr515SignedPreparedAbortReadback(")
        end = operator.index("# Scoped originalhost ARMED marker-only cancel (SOURCE ONLY; no release).", start)
        body = operator[start:end]
        self.assertIn("Test-V3IndependentOriginalHostCmsSignature", body)
        self.assertIn("SIGNED_TERMINAL_ABORT_FORMAT_AND_PINS_MATCH_NOT_RELEASE", body)
        for field in (
            "epoch_id", "source_sha256", "prepared_fence_sha256",
            "caller_acl_sha256", "receipt_sha256", "issuer_actor",
            "created_at_utc", "ABORT_RECORDED_NOT_RELEASED",
            "ABORT_WIRE_DUPLICATE", "ABORT_WIRE_SOURCE_OR_TIME_MISMATCH",
        ):
            self.assertIn(field, body)
        for denied in (
            "independent_reader_cloud_provenance_verified_here=$false",
            "complete_attempt_unknown_history_proven=$false",
            "marker_only_cancel_authorized=$false",
            "native_task_mutations_authorized=$false",
        ):
            self.assertIn(denied, body)
        for forbidden in (
            "Stop-ScheduledTask", "Start-ScheduledTask",
            "Disable-ScheduledTask", "Enable-ScheduledTask",
            "Remove-Item", "[IO.File]::Move(", "[IO.File]::Replace(",
        ):
            self.assertNotIn(forbidden, body)

    def test_originalhost_marker_only_cancel_remains_independently_locked(self):
        operator = (ROOT / "tools" / "minipc-v3-paper-cutover-operator-INACTIVE.ps1").read_text(encoding="utf-8")
        start = operator.index("function Invoke-V3Pr515ArmedMarkerOnlyCancelSOURCE_ONLY(")
        end = operator.index("# Current PR515 PRE-COMMIT manual recovery SOURCE ONLY.", start)
        body = operator[start:end]
        self.assertRegex(
            body,
            r"(?s)\) \{\s*throw 'V3_PR515_MARKER_ONLY_CANCEL_SOURCE_LOCKED_INDEPENDENT_ABORT_CUSTODY_NOT_WIRED'",
        )
        for required in (
            "V3_MARKER_CANCEL_BAD_HOST_OR_RELEASE_PINS",
            "V3_MARKER_CANCEL_FENCE_CHANGED",
            "V3_MARKER_CANCEL_NOT_EXACT_PRESTOP_ARMED",
            "V3_MARKER_CANCEL_SIGNED_CLOUD_ABORT_AND_ATOMIC_ARCHIVE_NOT_IMPLEMENTED",
            "Test-V3ScopedIntakeTaskSet",
            "proposed_v3_repo_sha",
            "proposed_v3_bundle_sha256",
            "proposed_v3_strategy_sha256",
        ):
            self.assertIn(required, body)
        for forbidden in (
            "Stop-ScheduledTask", "Start-ScheduledTask",
            "Disable-ScheduledTask", "Enable-ScheduledTask",
            "Remove-Item", "[IO.File]::Move(", "[IO.File]::Replace(",
        ):
            self.assertNotIn(forbidden, body)
        self.assertIn("if($Execute){", operator)
        self.assertIn("V3_CUTOVER_EXECUTION_LOCKED", operator)

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
