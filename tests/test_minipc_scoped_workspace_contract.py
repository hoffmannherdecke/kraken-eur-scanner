"""Source-only boundary for the fixed non-admin workspace report task.

This is not evidence of any existing Windows ACL or a successful write.
"""
from pathlib import Path
import unittest

TASK = Path("tools/minipc_runner_tasks/workspace_report.ps1")


class ScopedWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = TASK.read_text("utf-8")
        cls.active = "\n".join(line.lower() for line in cls.task.splitlines()
                               if not line.lstrip().startswith("#"))

    def test_only_fixed_nonadmin_workspace(self):
        s = self.task
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        self.assertFalse(TASK.is_symlink())
        self.assertLess(TASK.stat().st_size, 65536)
        for term in (
            "CryptoSupportSvc", "MINI-PC-CryptoSupport",
            "WindowsBuiltInRole]::Administrator",
            "C:\\CryptoSupport\\Workspace", "[IO.FileAttributes]::ReparsePoint",
            "[IO.Directory]::EnumerateFileSystemEntries($root)",
            "if ($seen -ge 20)", "[guid]::NewGuid()",
            "probe-", "report-", ".tmp", ".json",
            "[IO.FileMode]::CreateNew", "[IO.FileShare]::None",
            "[IO.File]::Delete($testPath)", "ConvertTo-Json -Compress",
            "MINIPC_WORKSPACE_SAFE_SUMMARY_V1", "MINIPC_REVIEWED_TASK_ACK_V1",
            "task = 'workspace_report'", "mutation_scope = 'RESTRICTED'",
            "local_filesystem_writes = $true", "writes_outside_workspace = $false",
            "trading_orders_permitted = $false", "[Text.UTF8Encoding]::new($false)"
        ):
            self.assertIn(term, s, term)

    def test_no_arbitrary_commands_paths_or_privileged_operations(self):
        for term in (
            "param(", "$args", "invoke-expression", "invoke-command",
            "invoke-webrequest", "invoke-restmethod", "start-process",
            "invoke-cimmethod", "set-service", "stop-service", "start-service",
            "start-scheduledtask", "set-acl", "icacls", "restart-computer",
            "get-credential", "git checkout", "git pull", "supabase ",
            ".env", "service_role_key", "api_key", "c:\\users",
            "get-childitem", "get-content", "new-item", "set-item",
            "remove-item", "write-host $content"
        ):
            self.assertNotIn(term, self.active, term)
        self.assertEqual(self.active.count("write-host ('minipc_workspace_safe_summary_v1 '"), 1)
        self.assertEqual(self.active.count("[io.filemode]::createnew"), 2)
        self.assertNotIn("Join-Path $env:", self.task)

    def test_reports_are_small_and_probe_is_cleaned_up(self):
        self.assertIn("if ($bytes.Length -gt 4096)", self.task)
        self.assertIn("if ([IO.File]::Exists($testPath)) { [IO.File]::Delete($testPath) }", self.task)
        self.assertIn("$probeDone = $true", self.task)
        self.assertIn("$writer.Dispose()", self.task)
        self.assertIn("MINIPC_WORKSPACE_REPORT_V1", self.task)
        self.assertIn("no_new_privileged_rights = $true", self.task)


if __name__ == "__main__":
    unittest.main()
