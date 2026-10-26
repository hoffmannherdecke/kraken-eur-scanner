"""One original interactive Windows owner credential stage, no runtime CAS."""
from pathlib import Path
import re
import unittest

SCRIPT = Path("tools/minipc-v3-cas-operator-login-INACTIVE.ps1")


class V3CasOperatorLoginSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = SCRIPT.read_text(encoding="utf-8")
        cls.active = "\n".join(line for line in cls.s.splitlines()
                               if not line.lstrip().startswith("#"))

    def test_default_inert_no_cloud_calls_or_bypass(self):
        s = self.active
        self.assertLess(s.index("if (-not $Stage -and -not $VerifyLocal -and -not $RemoveEnrollmentSql)"),
                        s.index("if ($Stage -and $RemoveEnrollmentSql)"))
        for marker in (
            "INACTIVE_PREVIEW", "cloud_login_created = $false",
            "cas_role_membership_granted = $false",
            "v3_paper_activated = $false",
            "remote_database_contacted = $false",
            "supabase_ddl_executed_by_this_script = $false",
        ):
            self.assertIn(marker, s)
        for forbidden in (
            "Invoke-RestMethod", "Invoke-WebRequest", "Start-Process",
            "Invoke-Expression", "Get-Credential", "psql.exe",
            "PGPASSWORD", "SUPABASE_SERVICE_ROLE_KEY", "KRAKEN_API_KEY",
            "Invoke-Command", "Register-ScheduledTask", "Start-ScheduledTask",
            "Set-Acl", "icacls", "GRANT v3_cas_executor",
            "grant execute on function", "create function",
            "drop role", "set role v3_cas_executor", "alter default privileges",
        ):
            self.assertNotIn(forbidden.lower(), s.lower(), forbidden)

    def test_local_currentuser_dpapi_and_no_runner_secret_issuance(self):
        s = self.active
        for marker in (
            "[Security.Principal.WindowsIdentity]::GetCurrent()",
            "CryptoSupportSvc",
            "$env:GITHUB_ACTIONS -eq 'true'",
            "-not [Environment]::UserInteractive",
            "$env:LOCALAPPDATA",
            "V3CasOperator-INACTIVE",
            "operator-login-currentuser.dpapi",
            "operator-login-enroll-ONE-TIME.sql",
            "ProtectedData]::Protect(",
            "ProtectedData]::Unprotect(",
            "DataProtectionScope]::CurrentUser",
            "RandomNumberGenerator]::Create()",
            "CreateNew",
            "SetAccessRuleProtection($true,$false)",
            "FileShare]::None",
            "FileOptions]::WriteThrough",
            "AreAccessRulesProtected",
            "GetAccessRules",
            "ReparsePoint",
            "DriveType]::Fixed",
            "DriveFormat -cne 'NTFS'",
            "V3_CAS_OPERATOR_HOLD: local NTFS owner profile unavailable",
            "S-1-5-18",
            "S-1-5-32-544",
        ):
            self.assertIn(marker, s, marker)

    def test_local_dpapi_and_scram_verifier_roundtrip_is_read_only(self):
        s = self.active
        for marker in (
            "[switch]$VerifyLocal",
            "if ($VerifyLocal) {",
            "LOCAL_DPAPI_SCRAM_ROUNDTRIP_PASS",
            "ProtectedData]::Unprotect(",
            "GetAccessRules",
            "Assert-LocalScope $secretPath $false",
            "Assert-LocalScope $sqlPath $false",
            "Rfc2898DeriveBytes",
            "GetBytes(32)",
            "HMACSHA256",
            "Client Key",
            "Server Key",
            "SHA256]::Create()",
            "expectedStored",
            "expectedServer",
            "V3_CAS_OPERATOR_HOLD: DPAPI and SCRAM verifier mismatch",
            "sql_still_local_only = $true",
            "remote_database_contacted = $false",
            "cas_role_membership_granted = $false",
        ):
            self.assertIn(marker, s, marker)
        self.assertEqual(s.count("if ($VerifyLocal) {"), 1)
        self.assertLess(s.index("if ($VerifyLocal) {"),
                        s.index("if ($RemoveEnrollmentSql) {"))
        self.assertLess(s.index("if ($VerifyLocal) {"),
                        s.index("if ([IO.File]::Exists($sqlPath) -or"))
        self.assertIn("$VerifyLocal -or $RemoveEnrollmentSql", s)
        self.assertIn("localSecret = $null", s)
        self.assertIn("sqlText = $null", s)
        # A physical owner must finish the encrypted-secret/SCRAM check
        # before copying any one-time verifier SQL into Supabase.
        result = s.split("if ($VerifyLocal) {", 1)[1].split(
            "if ($RemoveEnrollmentSql) {", 1)[0]
        self.assertNotIn("New-ProtectedByteFile", result)
        self.assertNotIn("[IO.File]::WriteAll", result)
        self.assertNotIn("execute format(", result)
        self.assertNotIn("secret_file =", result)
        self.assertNotIn("verifier =", result)
        self.assertNotIn("Get-Content", result)

    def test_strong_scram_verifier_and_secret_not_in_result(self):
        s = self.active
        for marker in (
            "New-Object byte[] 32",
            "New-Object byte[] 16",
            "Rfc2898DeriveBytes",
            "HashAlgorithmName]::SHA256",
            "GetBytes(32)",
            "HMACSHA256",
            "Client Key", "Server Key",
            "SCRAM-SHA-256$4096:",
            "operator-login-enroll-ONE-TIME.sql",
            "[Array]::Clear",
            "sql_contains_only_scram_verifier_not_password = $true",
            "supabase_sql_editor_execution_required = $true",
        ):
            self.assertIn(marker, s, marker)
        self.assertIn("rolconnlimit=1", s)
        self.assertNotRegex(s, r"(?im)^\s*(?:write-(?:host|output)|echo)\s+\$secret\b")
        self.assertEqual(s.count("SCRAM-SHA-256$4096:"), 1)

    def test_exact_credential_only_sql_guards(self):
        s = self.active.lower()
        for phrase in (
            "begin;\ndo $v3_cas_local_login$",
            "if current_user <> 'postgres'",
            "v3_cas_operator_login",
            "not r.rolcanlogin",
            "not r.rolbypassrls",
            "not r.rolcreaterole",
            "not r.rolcreatedb",
            "not r.rolreplication",
            "v3_cas_login_unexpected_membership",
            "v3_cas_login_runtime_already_present",
            "v3_cas_login_public_function_execute_drift",
            "alter role v3_cas_operator_login login password %l",
            "v3_cas_login_atomic_enroll_check_failed",
            "pg_catalog.aclexplode",
            "v3_cas_executor",
            "v3_cas_audit_writer",
            "v3_cas_audit_reader",
            "$v3_cas_local_login$;\ncommit;",
        ):
            self.assertIn(phrase, s, phrase)
        self.assertNotIn("create role v3_cas_operator_login", s)
        self.assertNotIn("grant v3_cas_executor to v3_cas_operator_login", s)


if __name__ == "__main__":
    unittest.main()
