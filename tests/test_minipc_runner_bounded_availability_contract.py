"""Offline source contract for ONE disabled local scheduler, existing protected runner.

Tests only read source. They must never alter Windows Scheduled Tasks or service state.
"""
from pathlib import Path
import unittest

BASE = Path("tools/minipc_runner_guard")
WINDOW = BASE / "bounded_window.ps1"
INSTALL = BASE / "install_bounded_window.ps1"


class BoundedRunnerAvailabilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = WINDOW.read_text(encoding="utf-8")
        cls.installer = INSTALL.read_text(encoding="utf-8")

    def test_window_verifies_exact_existing_runner_and_guard(self):
        s = self.window
        for required in (
            "CryptoSupportSvc",
            "S-1-5-18",
            "GetCimInstance" if False else "Get-CimInstance",
            "WINDOW_BLOCK:",
            "28bdddccd7d917151958c4b64461dc6289e71eca",
            "ACTIONS_RUNNER_HOOK_JOB_STARTED",
            "PSExecutionPolicyPreference=Bypass",
            "approved-private-workflow-sha.txt",
            "pre_job.ps1",
            "State -ceq 'Stopped'",
            "StartMode -ceq 'Disabled'",
            "$windowSeconds = 660",
            "$drainSeconds = 480",
        ):
            self.assertIn(required, s)
        self.assertNotIn("Invoke-WebRequest", s)
        self.assertNotIn("git pull", s)
        self.assertNotIn("supabase", s.lower())
        self.assertNotIn("Invoke-Expression", s)
        self.assertNotIn("Get-Content", s)
        self.assertNotIn("Get-ChildItem", s)

    def test_safe_pause_always_attempted_no_autostart(self):
        s = self.window
        self.assertIn("try {", s)
        self.assertIn("finally {", s)
        self.assertIn("Start-Service -Name $serviceName", s)
        self.assertIn("Stop-Service -Name $serviceName", s)
        self.assertIn("Set-Service -Name $serviceName -StartupType Disabled", s)
        self.assertIn("WINDOW_FINAL_CHECK_FAILED", s)
        self.assertIn("WINDOW_SAFE_PAUSE_ACK:", s)
        self.assertIn("Runner.Worker.exe", s)
        self.assertNotIn("-StartupType Automatic", s)
        self.assertNotIn("Restart-Service", s)
        self.assertNotIn("Register-ScheduledTask", s)
        self.assertNotIn("Set-Acl", s)
        self.assertNotIn("icacls", s)

    def test_installer_only_registers_exactly_one_disabled_system_task(self):
        s = self.installer
        for required in (
            "Get-ScheduledTask -TaskName $taskName",
            "CryptoSupport - Bounded Runner Window",
            "C:\\ProgramData\\CryptoSupportGuard",
            "INSTALL_BLOCK" if False else "WINDOW_INSTALL_BLOCK:",
            "Get-Acl -LiteralPath $root",
            "AreAccessRulesProtected",
            "ACTIONS_RUNNER_HOOK_JOB_STARTED",
            "PSExecutionPolicyPreference=Bypass",
            "ApprovedPublicMainSha",
            "Invoke-WebRequest -Uri $url",
            "New-ScheduledTaskAction",
            "New-ScheduledTaskTrigger -Once",
            "-RepetitionInterval (New-TimeSpan -Minutes 20)",
            "New-ScheduledTaskSettingsSet -Disable",
            "-MultipleInstances IgnoreNew",
            "-ExecutionTimeLimit (New-TimeSpan -Minutes 20)",
            "New-ScheduledTaskPrincipal -UserId 'SYSTEM'",
            "Register-ScheduledTask -TaskName $taskName",
            "WINDOW_TASK_INSTALLED_DISABLED",
            "NO_UNATTENDED_WINDOW_ENABLED_BEFORE_FINAL_APPROVAL",
        ):
            self.assertIn(required, s)
        self.assertEqual(s.count("Register-ScheduledTask -TaskName $taskName"), 1)
        for forbidden in (
            "Enable-ScheduledTask",
            "Start-ScheduledTask",
            "Start-Service -Name",
            "Set-Service -Name",
            "-StartupType Automatic",
            "Register-ScheduledTask -Force",
            "New-Service",
            "Install-Module",
            "Trading\\",
            "Kraken_API",
        ):
            self.assertNotIn(forbidden, s)

    def test_task_can_be_removed_only_when_disabled_and_runner_off(self):
        s = self.installer
        self.assertIn("if ($Remove)", s)
        self.assertIn("if ($currentTask.State -ne 'Disabled')", s)
        self.assertIn("Unregister-ScheduledTask", s)
        self.assertIn("WINDOW_REMOVE_BLOCK:", s)
        self.assertIn("runner must be Stopped/Disabled", s)
        self.assertIn("task already exists, never overwrite", s)
        self.assertIn("local window file exists, never overwrite", s)


if __name__ == "__main__":
    unittest.main()
