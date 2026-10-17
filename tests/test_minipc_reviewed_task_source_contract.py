"""Offline contract for the first restricted Mini-PC reviewed task."""
from pathlib import Path
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/host_safety_probe.ps1")
FOLDER = Path("tools/minipc_runner_tasks")

class MinipcReviewedTaskSourceTests(unittest.TestCase):
    def test_exactly_one_task_file(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual(list(FOLDER.glob("*.ps1")), [SCRIPT])
        self.assertFalse(SCRIPT.is_symlink())
        self.assertLess(SCRIPT.stat().st_size, 65536)

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
