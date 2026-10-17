"""Offline safety contracts for the admin-owned Mini-PC runner pre-job hook.

These tests must never start a Windows service or access the remote host.
"""
from pathlib import Path
import unittest

ROOT = Path("tools/minipc_runner_guard")
HOOK = ROOT / "pre_job.ps1"
INSTALL = ROOT / "install_guard.ps1"


class RunnerLocalGuardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = HOOK.read_text(encoding="utf-8")
        cls.installer = INSTALL.read_text(encoding="utf-8")

    def test_exact_private_repo_workflow_sha_is_required(self):
        hook = self.hook
        for value in (
            "GITHUB_REPOSITORY",
            "GITHUB_WORKFLOW_REF",
            "GITHUB_WORKFLOW_SHA",
            "GITHUB_WORKFLOW",
            "GITHUB_EVENT_NAME",
            "GITHUB_REF",
            "RUNNER_NAME",
            "approved-private-workflow-sha.txt",
            "hoffmannherdecke/kraken-readonly-bridge/.github/workflows/minipc-reviewed-project-task.yml@refs/heads/main",
        ):
            self.assertIn(value, hook)
        self.assertIn("GITHUB_WORKFLOW_SHA -ceq $pin", hook)
        self.assertIn("MINI-PC-CryptoSupport", hook)
        self.assertIn("CryptoSupportSvc", hook)
        self.assertIn("WindowsBuiltInRole]::Administrator", hook)
        self.assertIn("unapproved_workflow_revision", hook)

    def test_exact_connector_owner_and_ttl_are_required(self):
        hook = self.hook
        for value in (
            "GITHUB_EVENT_PATH",
            "ConvertFrom-Json",
            "$eventData.issue.number -eq 13",
            "$eventData.comment.user.login -ceq 'hoffmannherdecke'",
            "$eventData.comment.author_association -ceq 'OWNER'",
            "$eventData.comment.performed_via_github_app.slug -ceq 'chatgpt-codex-connector'",
            "MINIPC_TASK_V1",
            "created_at",
            "$age -ge -60 -and $age -le 600",
            "expired_request",
        ):
            self.assertIn(value, hook)
        self.assertIn("throw \"LOCAL_PREJOB_DENIED:", hook)
        self.assertIn("Write-Output 'LOCAL_PREJOB_V1_APPROVED", hook)
        self.assertNotIn("Invoke-Expression", hook)
        self.assertNotIn("Start-Process", hook)
        self.assertNotIn("git checkout", hook)
        self.assertNotIn("Start-Service", hook)
        self.assertNotIn("Set-Service", hook)
        self.assertNotIn("Set-Acl", hook)

    def test_admin_installer_does_not_enable_service_or_schedule(self):
        install = self.installer
        for required in (
            "INSTALL_BLOCK: run only in administrator PowerShell",
            "State -ne 'Stopped'",
            "StartMode -ne 'Disabled'",
            "StartName -ne '.\\CryptoSupportSvc'",
            "28bdddccd7d917151958c4b64461dc6289e71eca",
            "https://raw.githubusercontent.com/hoffmannherdecke/kraken-eur-scanner/",
            "ACTIONS_RUNNER_HOOK_JOB_STARTED",
            "Select-String",
            "/inheritance:r",
            "S-1-5-18",
            "S-1-5-32-544",
            ":(OI)(CI)(RX)",
            "SetEnvironmentVariable($varName,$hookPath,'Machine')",
            "RUNNER_STILL_STOPPED_DISABLED",
        ):
            self.assertIn(required, install)
        for forbidden in (
            "Start-Service", "Set-Service", "New-ScheduledTask",
            "Register-ScheduledTask", "Enable-ScheduledTask",
            "-StartupType Automatic", "Install-Module",
            "Trading\\Runtime", "Trading\\Secrets",
            "api.openai.com",
        ):
            self.assertNotIn(forbidden, install)

    def test_installer_checks_existing_config_and_can_roll_back(self):
        src = self.installer
        self.assertIn("INSTALL_BLOCK: guard directory exists; no overwrite", src)
        self.assertIn("INSTALL_BLOCK: other machine-level runner hook", src)
        self.assertIn("INSTALL_BLOCK: runner dotenv already overrides", src)
        self.assertIn("INSTALL_BLOCK: runner must be Stopped/Disabled", src)
        self.assertIn("UNINSTALL_BLOCK: other system hook configured", src)
        self.assertIn("LOCAL_PREJOB_GUARD_REMOVED; RUNNER_REMAINS_DISABLED", src)
        self.assertIn("Remove-Item -LiteralPath $guardDir -Recurse -Force", src)
        self.assertIn("SetEnvironmentVariable($varName,$null,'Machine')", src)

    def test_scope_stays_single_existing_runner(self):
        src = self.hook + self.installer
        self.assertNotIn("kraken-eur-scanner/.github/workflows", src)
        self.assertNotIn("workflow_dispatch", src)
        self.assertNotIn("ACTIONS_RUNNER_HOOK_JOB_COMPLETED", src)
        self.assertNotIn("Trading\\Staging", src)
        self.assertNotIn("Kraken_API", src)
        self.assertNotIn("C:\\Users\\ADMIN", src)


if __name__ == "__main__":
    unittest.main()
