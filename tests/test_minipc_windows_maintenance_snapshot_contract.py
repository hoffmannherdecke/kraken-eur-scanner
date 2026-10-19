"""Offline source safety contract for a bounded Windows maintenance readback."""
from pathlib import Path
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/windows_maintenance_snapshot.ps1")


class WindowsMaintenanceSnapshotSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.active = "\n".join(line.lower() for line in cls.source.splitlines()
                               if not line.lstrip().startswith("#"))

    def test_original_nonadmin_runner_and_fixed_read_paths(self):
        s = self.source
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        self.assertFalse(SCRIPT.is_symlink())
        self.assertLess(SCRIPT.stat().st_size, 65536)
        for required in (
            "CryptoSupportSvc", "WindowsBuiltInRole]::Administrator",
            "MINI-PC-CryptoSupport",
            "Get-ScheduledTask -TaskName 'CryptoSupport - Bounded Runner Window'",
            "Get-ScheduledTaskInfo -TaskName 'CryptoSupport - Bounded Runner Window'",
            "actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport",
            "Win32_Service", "Win32_OperatingSystem", "Win32_Processor",
            "Component Based Servicing\\RebootPending",
            "Auto Update\\RebootRequired", "PauseUpdatesExpiryTime",
        ):
            self.assertIn(required, s, required)

    def test_missing_information_never_becomes_successful_host_acceptance(self):
        s = self.source
        for required in (
            "'UNAVAILABLE'", "'ACCESS_DENIED'", "'PARTIAL_INFO_UNAVAILABLE'",
            "'VALUE_UNPARSEABLE'", "'PRESENT'", "'ABSENT'",
            "scheduled_window_safe_pause_proven=$false",
            "windows_update_ready_to_install_proven=$false",
            "cpu_replacement_physically_accepted=$false",
            "windows_restart_authorized=$false",
            "v2r4_or_v3_release_authorized=$false",
            "local_filesystem_writes=$false", "secrets_used=$false",
            "active_runtime_release=$false", "trading_orders_permitted=$false",
            "kind='MINIPC_REVIEWED_TASK_ACK_V1'",
            "task='windows_maintenance_snapshot'",
            "mutation_scope='RESTRICTED'",
        ):
            self.assertIn(required, s, required)

    def test_no_unreviewed_shell_or_mutation(self):
        for blocked in (
            "set-service", "start-service", "stop-service",
            "start-scheduledtask", "stop-scheduledtask",
            "register-scheduledtask", "unregister-scheduledtask",
            "enable-scheduledtask", "disable-scheduledtask",
            "restart-computer", "shutdown", "set-item",
            "set-itemproperty", "new-item", "remove-item", "copy-item",
            "move-item", "set-content", "add-content", "out-file",
            "get-content", "get-childitem", "invoke-expression",
            "invoke-webrequest", "invoke-restmethod", "invoke-command",
            "start-process", "invoke-cimmethod", "set-ciminstance",
            "set-acl", "icacls", "c:\\users", "api_key",
            "secrets", "write-host",
        ):
            self.assertNotIn(blocked, self.active, blocked)
        self.assertNotIn("$args", self.source)
        self.assertEqual(self.source.count("ConvertTo-Json -Depth 6 -Compress"), 1)


if __name__ == "__main__":
    unittest.main()
