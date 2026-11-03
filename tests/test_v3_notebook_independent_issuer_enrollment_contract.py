"""Offline contract for the one-shot independent Notebook issuer source; no secrets."""
from pathlib import Path
import unittest

SCRIPT=Path("tools/v3-notebook-independent-issuer-enroll-INACTIVE.ps1")

class NotebookIssuerEnrollmentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s=SCRIPT.read_text(encoding="utf-8")
        cls.active="\n".join(line for line in cls.s.splitlines() if not line.lstrip().startswith("#"))

    def test_default_inert_and_no_runtime(self):
        s=self.active
        self.assertIn("INACTIVE_PREVIEW",s)
        self.assertIn("cloud_changed=$false",s)
        for forbidden in ("Invoke-Expression","Invoke-RestMethod","Invoke-WebRequest",
                          "psql.exe","PGPASSWORD","KRAKEN_API_KEY",
                          "Register-ScheduledTask","Start-ScheduledTask",
                          "Invoke-Command","Start-Process","New-PSSession",
                          "GRANT v3_cas_executor","set role v3_cas_executor",
                          "create function","create role","drop role",
                          "service_role_key","reader.dpapi","writer.dpapi"):
            self.assertNotIn(forbidden.lower(),s.lower(),forbidden)

    def test_windows_dpapi_framework_loaded_before_local_mutation(self):
        s=self.active
        self.assertIn("Add-Type -AssemblyName System.Security -ErrorAction Stop",s)
        self.assertIn("V3_ISSUER_DPAPI_REAL_ROUNDTRIP_UNAVAILABLE",s)
        self.assertIn("[Security.Cryptography.ProtectedData]::Protect(",s)
        self.assertIn("[Security.Cryptography.ProtectedData]::Unprotect(",s)
        self.assertIn("V3_ISSUER_DPAPI_PROBE_MISMATCH_HOLD",s)
        self.assertNotIn("[type]::GetType(",s)
        self.assertLess(s.index("Add-Type -AssemblyName System.Security"),
                        s.index("[IO.Directory]::CreateDirectory($root"))
        self.assertLess(s.index("Add-Type -AssemblyName System.Security"),
                        s.index("ProtectedData]::Unprotect("))
        self.assertLess(s.index("Add-Type -AssemblyName System.Security"),
                        s.index("ProtectedData]::Protect("))

    def test_currentuser_only_and_nonoverwrite(self):
        s=self.active
        for marker in ("CryptoSupportSvc","GITHUB_ACTIONS","UserInteractive",
                       "DriveType]::Fixed","DriveFormat -ne 'NTFS'",
                       "SetAccessRuleProtection($true,$false)",
                       "AreAccessRulesProtected","ReparsePoint","CreateNew",
                       "FileShare]::None","WriteThrough","ProtectedData]::Protect(",
                       "ProtectedData]::Unprotect(","DataProtectionScope]::CurrentUser",
                       "V3CasIndependentIssuer","issuer-currentuser.dpapi",
                       "issuer-enroll-ONE-TIME.sql",
                       "V3_ISSUER_EXISTING_IDENTITY_HOLD"):
            self.assertIn(marker,s,marker)

    def test_local_scram_roundtrip_and_secrecy(self):
        s=self.active
        for marker in ("[switch]$VerifyLocal","LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS",
                       "V3_ISSUER_DPAPI_SCRAM_MISMATCH",
                       "RandomNumberGenerator]::Create()","Rfc2898DeriveBytes",
                       "HMACSHA256","Client Key","Server Key","SCRAM-SHA-256$4096:",
                       "manual_cloud_approval_still_required=$true",
                       "ONE_TIME_SQL_SCRUBBED"):
            self.assertIn(marker,s,marker)
        self.assertNotIn("Write-Host $password",s)
        self.assertNotIn("Write-Output $password",s)
        self.assertEqual(s.count("SCRAM-SHA-256$4096:"),1)

    def test_enrollment_sql_is_transactional_and_fail_closed(self):
        s=self.active.lower()
        for phrase in ("begin;\ndo $v3_issuer_enroll$",
                       "current_user <> 'postgres'",
                       "v3_issuer_role_prestaged_hold",
                       "not rolcanlogin and not rolinherit and rolconnlimit=0",
                       "v3_issuer_foreign_membership_hold",
                       "v3_issuer_schema_missing_hold",
                       "v3_issuer_acl_drift_hold",
                       "v3_issuer_cas_already_installed_hold",
                       "alter role v3_cas_inhibit_issuer_actor login connection limit 1 password %l",
                       "v3_issuer_enroll_rollback","$v3_issuer_enroll$;\ncommit;"):
            self.assertIn(phrase,s,phrase)
        self.assertNotIn("grant ",s)
        self.assertNotIn("alter role v3_cas_executor_actor",s)
        self.assertNotIn("insert into v3_cas_audit",s)


class ForwardT0NotebookReaderSourceContract(unittest.TestCase):
    """Same existing CI execution lane; never runs psql, signing or live CAS."""
    @classmethod
    def setUpClass(cls):
        cls.script=Path("tools/v3-notebook-cas-audit-original-readonly-witness-INACTIVE.ps1").read_text(encoding="utf-8")
        cls.sql=Path("supabase/v3-cas-t0-private-reader-witness-INACTIVE.sql").read_text(encoding="utf-8")

    def test_single_explicit_mode_and_genuine_reader_wire(self):
        s=self.script
        self.assertIn("[switch]$ForwardT0SignedCurrent",s)
        self.assertIn("V3_FORWARD_T0_SIGNER_EXPLICIT_PIN_REQUIRED",s)
        self.assertIn("$decisionReaderMode=($PrecommitCloudInventory -or $PostcommitDurableIntent -or $PrecommitRestoreCustody -or $ForwardT0SignedCurrent -or $PreparedAbortSignedCurrent)",s)
        self.assertEqual(s.count("SELECT v3_cas_audit.read_forward_t0_current_v1()::text;"),1)
        self.assertIn("BEGIN TRANSACTION READ ONLY;\nSELECT v3_cas_audit.read_forward_t0_current_v1()::text;\nCOMMIT;",s)
        self.assertIn("if($decisionReaderMode){'verify-full'}else{'require'}",s)
        self.assertEqual(s.count("Save-V3SignedNotebookReaderSnapshot -RawJson $wire -CertSha256 $ReviewedNotebookCertificateSha256"),2)
        self.assertLess(s.index("$row=$wire|ConvertFrom-Json"),s.index("Save-V3SignedNotebookReaderSnapshot -RawJson $wire"))

    def test_exact_cloud_schema_and_fail_closed_fields(self):
        s=self.script
        fields=("kind observed_at_utc actor requested_role active_series_count "
                "original_active_series_count epoch_count intent_count attempt_count "
                "dispatch_unknown_count inhibit_count cas_rpc_count executor_can_login "
                "history_never_proven complete_attempt_unknown_custody_authenticated "
                "t0_authenticated armed_marker_cancel_authorized native_stop_restore_authorized "
                "cas_or_v3_paper_authorized").split()
        block=s.split("if($ForwardT0SignedCurrent){\n $checks=",1)[1].split("} elseif($PrecommitRestoreCustody){",1)[0]
        for field in fields:
            self.assertIn("'"+field+"'",block)
            self.assertIn("'"+field+"'",self.sql)
        for flag in ("independent_signer_issuer_authorized", "originalhost_bound",
                     "complete_attempt_unknown_custody_proven","t0_authorized",
                     "native_stop_restore_authorized","armed_marker_cancel_authorized",
                     "cas_or_v3_paper_authorized"):
            self.assertIn(flag+"=$false",block)
            self.assertNotIn(flag+"=$true",block)
        for hold in ("V3_FORWARD_T0_FIELDS_INVALID","V3_FORWARD_T0_DUPLICATE_FIELD",
                     "V3_FORWARD_T0_ACTOR_OR_TIME_HOLD",
                     "V3_FORWARD_T0_NONZERO_OR_UNTYPED_HOLD",
                     "V3_FORWARD_T0_AUTHORITY_HOLD"):
            self.assertIn(hold,block)
        self.assertIn("$age -gt 60",block)
        self.assertIn("READER_FORWARD_T0_HOLD_CLASS=",s)

    def test_old_modes_not_replaced_and_no_new_executor(self):
        s=self.script
        for old in ("if($PrecommitCloudInventory){","if($PrecommitRestoreCustody){",
                    "if($PostcommitDurableIntent){","ExportSignedPrecommitCloudInventory"):
            self.assertIn(old,s)
        self.assertIn("SIGNED_CURRENT_ONLY_NOT_T0_AUTHORIZED",s)
        self.assertNotIn("Stop-ScheduledTask",s)
        self.assertNotIn("Invoke-RestMethod",s)
        self.assertNotIn("Start-ScheduledTask",s)


if __name__=="__main__":
    unittest.main()
