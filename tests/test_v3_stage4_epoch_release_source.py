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

    def test_followup_prior_source_is_independent_and_new_epoch_preserved(self):
        sql = READ("supabase/v3-cas-audit-stage4-followup-release.sql")
        paper = READ("tools/v3-one-time-paper-release.ps1")
        # Positive: the old terminated epoch retains its historical source
        # even when the new CAS original changes in PR736.
        self.assertIn("e.source_sha256=current_setting('v3_followup.prior_source_sha256')", sql)
        self.assertIn("current_setting('v3_followup.source_sha256'),", sql)
        self.assertNotIn("e.source_sha256=current_setting('v3_followup.source_sha256')", sql)
        self.assertIn("'prior_source_sha256'", paper)
        self.assertIn("prior_source_sha256=''", paper)
        self.assertIn("v3_followup.prior_source_sha256", sql)
        # Missing/invalid pins are rejected before any temporary grant or
        # epoch insertion, not treated as the caller-supplied new hash.
        self.assertIn("V3_PAPER_FOLLOWUP_PRIOR_SOURCE_PIN_HOLD", sql)
        self.assertLess(sql.index("V3_PAPER_FOLLOWUP_PRIOR_SOURCE_PIN_HOLD"),
                        sql.index("GRANT v3_cas_audit_table_owner TO postgres"))
        self.assertIn("coalesce(current_setting('v3_followup.prior_source_sha256',true),'') !~ '^[a-f0-9]{64}
        # All old terminal, fence, ACL and no-effect guards remain.
        for clause in (
            "a.receipt_sha256=current_setting('v3_followup.prior_terminal_sha256')",
            "e.paper_release_commit=current_setting('v3_followup.prior_commit')",
            "e.approved_caller_acl_sha256=current_setting('v3_followup.caller_acl_sha256')",
            "a.source_sha256 IS DISTINCT FROM e.source_sha256",
            "a.prepared_fence_sha256 IS DISTINCT FROM e.original_fence_sha256",
            "a.caller_acl_sha256 IS DISTINCT FROM e.approved_caller_acl_sha256",
            "OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)",
            "OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)",
            "V3_PAPER_FOLLOWUP_SUPERSESSION_BINDING_HOLD",
            "V3_PAPER_FOLLOWUP_TERMINAL_HISTORY_HOLD",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, sql)

    def test_followup_different_historical_and_new_source_only_if_signed(self):
        sql = READ("supabase/v3-cas-audit-stage4-followup-release.sql")
        paper = READ("tools/v3-one-time-paper-release.ps1")
        # Simulate the two immutable hashes without a database mutation.
        old = "8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251"
        new = "989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043"
        self.assertNotEqual(old, new)
        settings = dict(prior_source_sha256=old, source_sha256=new)
        self.assertEqual(old, settings["prior_source_sha256"])
        self.assertEqual(new, settings["source_sha256"])
        self.assertNotEqual(settings["prior_source_sha256"], settings["source_sha256"])
        # The SQL uses prior_source exclusively for the old epoch and source
        # exclusively for INSERT of the new epoch.
        self.assertIn("e.source_sha256=current_setting('v3_followup.prior_source_sha256')", sql)
        self.assertIn("'public.rotate_v2r4_to_v3_experimental_paper',current_setting('v3_followup.source_sha256')", sql)
        self.assertIn("Get-V3PaperSupersessionSettings $plan", paper)
        self.assertIn("foreach($key in $supersession.Keys){$settings[$key]=$supersession[$key]}", paper)

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
        self.assertNotRegex(self.readback, r"(?im)^\s*(INSERT|UPDATE|DELETE|GRANT|REVOKE)\b")
        self.assertIn("V3_STAGE4_EPOCH_COMMITTED_READBACK_V1", self.launcher)


if __name__ == "__main__":
    unittest.main()
", sql)
        # All old terminal, fence, ACL and no-effect guards remain.
        for clause in (
            "a.receipt_sha256=current_setting('v3_followup.prior_terminal_sha256')",
            "e.paper_release_commit=current_setting('v3_followup.prior_commit')",
            "e.approved_caller_acl_sha256=current_setting('v3_followup.caller_acl_sha256')",
            "a.source_sha256 IS DISTINCT FROM e.source_sha256",
            "a.prepared_fence_sha256 IS DISTINCT FROM e.original_fence_sha256",
            "a.caller_acl_sha256 IS DISTINCT FROM e.approved_caller_acl_sha256",
            "OR EXISTS (SELECT FROM v3_cas_audit.intent_v1)",
            "OR EXISTS (SELECT FROM v3_cas_audit.attempt_v1)",
            "V3_PAPER_FOLLOWUP_SUPERSESSION_BINDING_HOLD",
            "V3_PAPER_FOLLOWUP_TERMINAL_HISTORY_HOLD",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, sql)

    def test_followup_different_historical_and_new_source_only_if_signed(self):
        sql = READ("supabase/v3-cas-audit-stage4-followup-release.sql")
        paper = READ("tools/v3-one-time-paper-release.ps1")
        # Simulate the two immutable hashes without a database mutation.
        old = "8b27c2392c2c8165660a40e15f5ab896c99da39befcd2201e43220acaa2e1251"
        new = "989e1657e03867774907f3a1ec9c9f4f84ee70c2d4b7a258cad9dc3e480f0043"
        self.assertNotEqual(old, new)
        settings = dict(prior_source_sha256=old, source_sha256=new)
        self.assertEqual(old, settings["prior_source_sha256"])
        self.assertEqual(new, settings["source_sha256"])
        self.assertNotEqual(settings["prior_source_sha256"], settings["source_sha256"])
        # The SQL uses prior_source exclusively for the old epoch and source
        # exclusively for INSERT of the new epoch.
        self.assertIn("e.source_sha256=current_setting('v3_followup.prior_source_sha256')", sql)
        self.assertIn("'public.rotate_v2r4_to_v3_experimental_paper',current_setting('v3_followup.source_sha256')", sql)
        self.assertIn("Get-V3PaperSupersessionSettings $plan", paper)
        self.assertIn("foreach($key in $supersession.Keys){$settings[$key]=$supersession[$key]}", paper)

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
        self.assertNotRegex(self.readback, r"(?im)^\s*(INSERT|UPDATE|DELETE|GRANT|REVOKE)\b")
        self.assertIn("V3_STAGE4_EPOCH_COMMITTED_READBACK_V1", self.launcher)


if __name__ == "__main__":
    unittest.main()
