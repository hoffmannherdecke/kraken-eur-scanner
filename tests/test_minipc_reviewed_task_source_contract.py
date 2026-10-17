"""Offline contract for the first restricted Mini-PC reviewed task."""
from pathlib import Path
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/host_safety_probe.ps1")
FOLDER = Path("tools/minipc_runner_tasks")

class MinipcReviewedTaskSourceTests(unittest.TestCase):
    def test_exactly_one_task_file(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual(
            sorted(FOLDER.glob("*.ps1")),
            [FOLDER / "access_boundary_probe.ps1", SCRIPT],
        )
        self.assertFalse(SCRIPT.is_symlink())
        self.assertLess(SCRIPT.stat().st_size, 65536)

    def test_readonly_boundary_probe_fails_closed_and_never_prints_file_names(self):
        script = FOLDER / "access_boundary_probe.ps1"
        self.assertTrue(script.is_file())
        self.assertFalse(script.is_symlink())
        source = script.read_text(encoding="utf-8")
        for required in (
            "# MINIPC_REVIEWED_TASK_V1",
            "CryptoSupportSvc",
            "WindowsBuiltInRole]::Administrator",
            "GetFileSystemEntries",
            "catch [System.UnauthorizedAccessException]",
            "HOST_ACCESS_BOUNDARY_FAIL:",
            "content_read_not_tested = $true",
            "protected_directory_listing_denied = $true",
            "task = 'access_boundary_probe'",
            "MINIPC_REVIEWED_TASK_ACK_V1",
            "mutation_scope = 'RESTRICTED'",
        ):
            self.assertIn(required, source)
        for disallowed in (
            "Get-Content", "Set-Content", "Copy-Item", "Move-Item",
            "Remove-Item", "Set-Acl", "icacls", "Start-Process",
            "Start-Service", "Set-Service", "Stop-Service",
            "Invoke-RestMethod", "Invoke-WebRequest",
            "ConvertTo-SecureString", "Start-ScheduledTask",
            "Get-ChildItem", "GetFileSystemEntries($restrictedRoot) |",
            "GetFileSystemEntries($restrictedRoot) | Out-String",
        ):
            self.assertNotIn(disallowed, source)
        self.assertEqual(source.count("ConvertTo-Json -Compress"), 1)

    def test_result_contract(self):
        s = SCRIPT.read_text(encoding="utf-8")
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        for key in ("MINIPC_REVIEWED_TASK_ACK_V1", "status = 'SUCCESS'",
                    "task = 'host_safety_probe'",
                    "mutation_scope = 'RESTRICTED'",
                    "CryptoSupportSvc", "WindowsBuiltInRole]::Administrator",
                    "MINI-PC-CryptoSupport", "Win32_OperatingSystem",
                    "Win32_LogicalDisk", "ConvertTo-Json -Compress"):
            self.assertIn(key, s)
        self.assertEqual(s.count("ConvertTo-Json -Compress"), 1)

    def test_no_mutating_or_secrets_commands(self):
        s = "\n".join(line for line in SCRIPT.read_text(encoding="utf-8").lower().splitlines() if not line.lstrip().startswith("#"))
        for forbidden in ("set-service", "start-service", "stop-service",
                          "start-scheduledtask", "register-scheduledtask",
                          "remove-item", "copy-item", "new-item", "set-content",
                          "add-content", "invoke-expression", "invoke-restmethod",
                          "invoke-webrequest", "get-content", "get-childitem",
                          "start-process", "icacls", "git pull",
                          "supabase", "kraken", "trading", ".env",
                          "c:\\users", "secrets.", "write-host"):
            self.assertNotIn(forbidden, s, forbidden)
        self.assertNotIn("$"+"{{", s)
        self.assertNotIn("$args", s)

if __name__ == "__main__":
    unittest.main()
