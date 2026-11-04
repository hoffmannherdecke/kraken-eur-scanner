"""Stage4 single-use epoch: source/authorization regression, no production execution."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READ = lambda p: (ROOT / p).read_text(encoding="utf-8")


class Stage4OneTimeEpochContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = READ("supabase/v3-cas-audit-stage4-original-epoch-open-INACTIVE.sql")
        cls.release = READ("supabase/v3-cas-audit-stage4-original-epoch-open-release.sql")
        cls.readback = READ("supabase/v3-cas-audit-stage4-original-epoch-open-readback.sql")
        cls.launcher = READ("tools/v3-one-time-release.ps1")
        cls.authority = READ("tools/v3-one-time-release-authorization.psm1")

    def test_original_source_production_lock_preserved(self):
        self.assertRegex(self.original, r"(?s)BEGIN;\s*DO \$v3_stage4_source_lock\$\s*BEGIN\s*RAISE EXCEPTION")
        self.assertIn("V3_STAGE4_EPOCH_OPEN_SOURCE_INACTIVE_NO_PRODUCTION_RELEASE", self.original)

    def test_only_one_reviewed_original_transaction(self):
        for sql in (self.original, self.release):
            self.assertEqual(sql.count("DO $v3_stage4_preflight$"), 1)
            self.assertEqual(sql.count("DO $v3_stage4_postflight$"), 1)
            self.assertEqual(sql.count("INSERT INTO v3_cas_audit.epoch_v1"), 1)
            self.assertEqual(len(re.findall(r"(?m)^COMMIT;", sql)), 1)
            self.assertEqual(sql.count("REVOKE INSERT ON v3_cas_audit.epoch_v1 FROM postgres;"), 1)
            self.assertIn("REVOKE v3_cas_audit_table_owner FROM postgres GRANTED BY postgres;", sql)
            self.assertIn("V3_STAGE4_TEMPORARY_PRIVILEGE_NOT_FULLY_RESTORED_HOLD", sql)

    def test_separate_sql_gate_requires_bound_release(self):
        self.assertIn("V3_STAGE4_EPOCH_SIGNED_ONE_TIME_SCOPE_HOLD", self.release)
        for key in ("scope", "release_commit", "approval_sha256", "runtime_release_commit",
                    "successor_series_id", "bundle_sha256", "strategy_sha256",
                    "epoch_id", "source_sha256", "fence_sha256",
                    "caller_acl_sha256", "expires_at"):
            self.assertIn("v3_stage4." + key, self.release)
        self.assertNotIn("'__EPOCH_ID__'", self.release)
        self.assertNotIn("'__SOURCE_SHA256__'", self.release)
        self.assertNotIn("'__CALLER_ACL_SHA256__'", self.release)

    def test_existing_authority_is_required_before_write(self):
        self.assertIn("'CLOUD_STAGE4_EPOCH_OPEN'", self.authority)
        self.assertIn("Assert-V3ReleaseAuthorityAdmission", self.launcher)
        self.assertIn("Assert-V3OneTimeReleaseAuthorization", self.launcher)
        self.assertIn("Assert-V3ReleaseCms", self.authority)
        self.assertIn("Get-V3OneTimeReleaseArtifactInventory", self.launcher)
        self.assertLess(self.launcher.index("Assert-V3OneTimeReleaseAuthorization"),
                        self.launcher.index("if($Mode -eq 'Stage4Epoch'){\n # Existing release authority"))
        self.assertLess(self.launcher.index("V3_STAGE4_EPOCH_INDEPENDENT_BINDINGS_HOLD"),
                        self.launcher.index("$null=Invoke-V3ReleasePg -Sql ($prefix+"))

    def test_scope_binds_originalhost_and_runtime_not_chat_generated(self):
        for v in ("36452e8fff4a9d7020eb39545dbd258fed880e00928a84a615c819e14b167e35",
                  "ebb39488530d9c032e082ca7ab4ae8d3e1f0a719",
                  "PAPER-V3-20261104T133710Z"):
            self.assertIn(v, self.release)
            self.assertIn(v, self.launcher)
        self.assertIn("'^V3CAS-AUDIT-[a-f0-9]{32}$'", self.launcher)
        self.assertIn("V3_STAGE4_EPOCH_COMMIT_READBACK_HOLD_NO_RETRY", self.launcher)

    def test_readback_requires_epoch_and_no_effects(self):
        for col in ("epoch_count", "epoch_id", "source_sha256", "original_fence_sha256",
                    "approved_caller_acl_sha256", "predecessor_series_id", "expected_rpc",
                    "next_ordinal", "sealed", "intent_count", "attempt_count",
                    "inhibit_count", "abort_count", "postgres_temp_insert",
                    "postgres_temp_set_owner", "predecessor_active"):
            self.assertIn(col, self.readback)
        self.assertNotRegex(self.readback, r"(?i)\b(INSERT|UPDATE|DELETE|GRANT|REVOKE)\b")
        self.assertIn("V3_STAGE4_EPOCH_COMMITTED_READBACK_V1", self.launcher)


if __name__ == "__main__":
    unittest.main()
