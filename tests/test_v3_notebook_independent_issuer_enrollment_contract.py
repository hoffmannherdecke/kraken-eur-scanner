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

if __name__=="__main__":
    unittest.main()
