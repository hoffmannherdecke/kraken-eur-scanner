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

    def test_one_sanitized_log_line_without_changing_json_ack_contract(self):
        s = self.source
        self.assertEqual(self.active.count("write-host"), 1)
        self.assertIn("Write-Host ('MINIPC_MAINTENANCE_SAFE_SUMMARY_V1 ' + $safeLine)", s)
        self.assertIn("$safeLine = $safeSummary | ConvertTo-Json -Compress -Depth 4", s)
        for required in ("$safeCpu = 'OTHER_OR_NOT_READABLE'",
                         "'i5-8500T|i7-8700T'",
                         "post_window_safe_pause_proven = $false",
                         "restart_or_update_authorized = $false",
                         "reboot_markers = @($markers)",
                         "task_readback = $task.readback"):
            if required == "'i5-8500T|i7-8700T'":
                self.assertIn("i5-8500T|i7-8700T", s)
            else:
                self.assertIn(required, s)
        self.assertEqual(s.count("Write-Host ('MINIPC_MAINTENANCE_SAFE_SUMMARY_V1 ' + $safeLine)"), 1)

    def test_exact_task_native_com_fallback_and_finite_failure_classes(self):
        s = self.source
        for needle in (
            "SchedulerReadErrorClass",
            "CMDLET_NOT_AVAILABLE",
            "OTHER_ERROR",
            "PermissionDenied",
            "New-Object -ComObject 'Schedule.Service' -ErrorAction Stop",
            "$scheduler.Connect()",
            "$scheduler.GetFolder('\\')",
            "$rootFolder.GetTask('CryptoSupport - Bounded Runner Window')",
            "SCHEDULE_SERVICE_COM",
            "task_read_method = $task.method",
            "task_cmdlet_probe = $task.cmdlet_probe",
            "task_com_probe = $task.com_probe",
            "task.readback = 'READ_OK'",
        ):
            self.assertIn(needle, s, needle)
        for prohibited in (
            "GetTasks(", "GetFolders(", "RegisterTask", "RegisterTaskDefinition",
            "SetSecurityDescriptor(", "$comTask.Run(", "$comTask.Stop(",
            "$comTask.Enabled =", "$rootFolder.DeleteTask(",
            "$scheduler.GetFolder($", "$_.Exception.Message",
            "FullyQualifiedErrorId", "script_block",
        ):
            self.assertNotIn(prohibited.lower(), self.active, prohibited)
        self.assertEqual(self.active.count("gettask('cryptosupport - bounded runner window')"), 1)

    def test_prior_window_history_is_bounded_read_only_and_never_a_false_final_ack(self):
        s = self.source
        for token in (
            "$previousWindow",
            "scope = 'PRIOR_WINDOW_ONLY'",
            "Get-WinEvent -FilterHashtable",
            "LogName = 'System'",
            "ProviderName = 'Service Control Manager'",
            "Id = 7036",
            "LogName = 'Microsoft-Windows-TaskScheduler/Operational'",
            "Id = 201",
            "-MaxEvents 220",
            "-MaxEvents 120",
            "AddMinutes(-75)",
            "AddSeconds(-1)",
            "$serviceLabel -ceq [string]$svc.DisplayName",
            "$taskNameField[0].InnerText -ceq '\\CryptoSupport - Bounded Runner Window'",
            "$resultCodeField[0].InnerText -ceq '0'",
            "previous_window_history = $previousWindow",
            "previous_window_history=$previousWindow",
            "post_window_stopped_disabled_independently_proven = $false",
        ):
            self.assertIn(token, s, token)
        self.assertEqual(s.count("Get-WinEvent -FilterHashtable"), 2)
        self.assertNotIn("Get-WinEvent -ListLog", s)
        self.assertNotIn("Write-Host $event", s)
        self.assertNotIn("$entry.Message", s)
        self.assertNotIn("Get-WinEvent -ComputerName", s)
        self.assertNotIn("Get-WinEvent -MaxEvents", s)
        self.assertLess(s.count("Get-WinEvent -FilterHashtable"), 3)

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
            "trading\\secrets",
        ):
            self.assertNotIn(blocked, self.active, blocked)
        self.assertNotIn("$args", self.source)
        self.assertEqual(self.source.count("ConvertTo-Json -Depth 6 -Compress"), 1)


if __name__ == "__main__":
    unittest.main()
