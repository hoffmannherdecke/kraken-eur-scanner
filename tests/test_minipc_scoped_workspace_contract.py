"""Fixed NTFS workspace change: source boundaries, never a substitute for Windows ACL evidence."""
from pathlib import Path
import unittest

TASK = Path("tools/minipc_runner_tasks/workspace_report.ps1")
SETUP = Path("tools/minipc_runner_guard/install_scoped_workspace.ps1")


class ScopedWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = TASK.read_text("utf-8")
        cls.setup = SETUP.read_text("utf-8")
        cls.active = "\n".join(line.lower() for line in cls.task.splitlines()
                               if not line.lstrip().startswith("#"))

    def test_one_fixed_lowprivilege_write_boundary(self):
        s = self.task
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        self.assertLess(TASK.stat().st_size, 65536)
        self.assertFalse(TASK.is_symlink())
        for required in (
            "CryptoSupportSvc", "MINI-PC-CryptoSupport",
            "WindowsBuiltInRole]::Administrator",
            "C:\\CryptoSupport\\Workspace",
            "[IO.FileAttributes]::ReparsePoint",
            "[IO.Directory]::EnumerateFileSystemEntries($root)",
            "if ($seen -ge 20)", "[guid]::NewGuid()",
            "probe-", "report-", ".tmp", ".json",
            "[IO.FileMode]::CreateNew", "[IO.FileShare]::None",
            "[IO.File]::Delete($testPath)",
            "ConvertTo-Json -Compress", "MINIPC_WORKSPACE_SAFE_SUMMARY_V1",
            "MINIPC_REVIEWED_TASK_ACK_V1", "task = 'workspace_report'",
            "mutation_scope = 'RESTRICTED'",
            "local_filesystem_writes = $true",
            "writes_outside_workspace = $false",
            "trading_orders_permitted = $false",
        ):
            self.assertIn(required, s, required)

    def test_never_execute_from_workspace_or_use_arbitrary_paths(self):
        for banned in (
            "param(", "$args", "invoke-expression", "invoke-command",
            "invoke-webrequest", "invoke-restmethod", "start-process",
            "invoke-cimmethod", "set-service", "stop-service", "start-service",
            "start-scheduledtask", "set-acl", "icacls", "restart-computer",
            "get-credential", "git checkout", "git pull", "supabase ",
            ".env", "service_role_key", "api_key", "c:\\users",
            "get-childitem", "get-content", "new-item", "set-item",
            "remove-item", "write-host $content",
        ):
            self.assertNotIn(banned, self.active, banned)
        self.assertEqual(self.active.count("write-host ('minipc_workspace_safe_summary_v1 '"), 1)
        self.assertEqual(self.active.count("[io.filemode]::createnew"), 2)
        self.assertNotIn("Join-Path $env:", self.task)

    def test_admin_setup_is_exactly_one_new_folder_only(self):
        s = self.setup
        self.assertTrue(s.startswith("# MINIPC_MANUAL_ADMIN_SETUP_ONLY"))
        self.assertNotIn("# MINIPC_REVIEWED_TASK_V1", s)
        self.assertFalse(SETUP.is_symlink())
        self.assertIn("WindowsBuiltInRole]::Administrator", s)
        self.assertIn("$target = 'C:\\CryptoSupport\\Workspace'", s)
        self.assertIn("$acl.SetAccessRuleProtection($true, $false)", s)
        self.assertIn("S-1-5-18", s)
        self.assertIn("S-1-5-32-544", s)
        self.assertIn("FileSystemRights]::Modify", s)
        self.assertIn("WORKSPACE_SETUP=PASS", s)
        self.assertIn("WORKSPACE_SETUP_BLOCK: workspace exists", s)
        self.assertIn("ROLLBACK=MANUAL_REVIEW_REQUIRED", s)
        for bad in (
            "Restart-Computer", "Set-Service", "Start-Service",
            "Stop-Service", "Register-ScheduledTask",
            "Set-ScheduledTask", "Invoke-Expression", "Invoke-WebRequest",
            "Invoke-RestMethod", "Set-ExecutionPolicy", "Get-ChildItem",
        ):
            self.assertNotIn(bad, s)


if __name__ == "__main__":
    unittest.main()
