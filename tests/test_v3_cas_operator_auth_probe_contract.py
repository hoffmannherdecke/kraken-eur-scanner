"""Inactive originalhost V3 CAS user SSL-auth probe: offline security regression."""
import re
import unittest
from pathlib import Path

P = Path("tools/minipc-v3-cas-operator-auth-probe-INACTIVE.ps1")


class OriginalhostCasAuthProbeContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = P.read_text(encoding="utf-8")
        cls.active = "\n".join(
            x for x in cls.source.splitlines() if not x.lstrip().startswith("#")
        )

    def test_preview_does_not_access_credential_or_network(self):
        s = self.active
        self.assertIn("[switch]$Probe", s)
        self.assertIn("if (-not $Probe)", s)
        self.assertIn("state = 'INACTIVE_PREVIEW'", s)
        self.assertLess(s.index("if (-not $Probe)"), s.index("WindowsIdentity]::GetCurrent()"))
        self.assertIn("secret_read = $false", s)
        self.assertIn("remote_contacted = $false", s)
        self.assertIn("database_modified = $false", s)
        for bad in (
            "Invoke-Expression", "Invoke-RestMethod", "Invoke-Command",
            "Start-ScheduledTask", "Register-ScheduledTask", "Start-Process",
            "CreateNew", "WriteAllText", "WriteAllBytes", "KRAKEN_API_KEY",
            "SUPABASE_SERVICE_ROLE_KEY", "ALTER ROLE", "CREATE ROLE",
            "GRANT ", "-Stage",
        ):
            self.assertNotIn(bad.lower(), s.lower(), bad)

    def test_same_owner_local_dpapi_only(self):
        s = self.active
        for marker in (
            "WindowsIdentity]::GetCurrent()", "CryptoSupportSvc",
            "$env:GITHUB_ACTIONS -eq 'true'", "[Environment]::UserInteractive",
            "operator-login-currentuser.dpapi", "DataProtectionScope]::CurrentUser",
            "ProtectedData]::Unprotect(", "AreAccessRulesProtected",
            "ReparsePoint", "DriveType]::Fixed", "DriveFormat -cne 'NTFS'",
            "S-1-5-18", "S-1-5-32-544", "do not regenerate",
        ):
            self.assertIn(marker, s, marker)
        self.assertNotIn("operator-login-enroll-ONE-TIME.sql", s)
        self.assertNotIn("ProtectedData]::Protect(", s)

    def test_winps51_explicit_system_security_load_before_sealed_secret(self):
        s = self.active
        load = "Add-Type -AssemblyName System.Security -ErrorAction Stop"
        credential_read = "[IO.File]::ReadAllBytes($secretFile)"
        decrypt = "[Security.Cryptography.ProtectedData]::Unprotect("
        self.assertIn(load, s)
        self.assertIn("Windows system cryptography unavailable; no credential read", s)
        self.assertLess(s.index("if (-not $Probe)"), s.index(load))
        self.assertLess(s.index(load), s.index(credential_read))
        self.assertLess(s.index(load), s.index(decrypt))
        self.assertEqual(s.count(load), 1)

    def test_tls_verify_full_postgresql_role_real_server_read_only(self):
        s = self.active
        for marker in (
            "'Direct','SessionPooler'", "'PGSSLMODE'] = 'verify-full'",
            "'PGSSLROOTCERT'] = $caTrust", "'PGPASSWORD'] = $password",
            "'PGCONNECT_TIMEOUT'] = '8'", "'PGDATABASE'] = 'postgres'",
            "'PGPORT'] = '5432'", "'PGHOST'] = $targetHost",
            "'PGUSER'] = $dbLogin", "'PGHOSTADDR'] = ''",
            "'PGOPTIONS'] = '-c default_transaction_read_only=on -c statement_timeout=10000'",
            "'-X -w -A -t -q -v ON_ERROR_STOP=1 -c",
            "current_user,session_user,(select ssl from pg_catalog.pg_stat_ssl",
            "pg_backend_pid()", "ORIGINALHOST_POSTGRES_SSL_AUTH_PASS",
            "$result.code -ne 0 -or $result.output -cne",
            "finally { $password = $null }",
            "never echo raw server/client error", "WaitForExit(20000)",
        ):
            self.assertIn(marker, self.source, marker)
        self.assertIn("pooler\\.supabase\\.com$", self.source)
        self.assertNotIn("sslmode=require", s.lower())
        self.assertNotIn("sslmode=prefer", s.lower())
        self.assertEqual(len(re.findall(r"\bselect current_user,session_user", s, re.I)), 1)


if __name__ == "__main__":
    unittest.main()
