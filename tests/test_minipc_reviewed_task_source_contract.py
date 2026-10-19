"""Offline contract for the first restricted Mini-PC reviewed task."""
from pathlib import Path
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/host_safety_probe.ps1")
FOLDER = Path("tools/minipc_runner_tasks")

class MinipcReviewedTaskSourceTests(unittest.TestCase):
    def test_only_reviewed_task_files(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual(
            sorted(FOLDER.glob("*.ps1")),
            [FOLDER / "access_boundary_probe.ps1", SCRIPT,
             FOLDER / "log_status_summary.ps1",
             FOLDER / "operations_readonly_bundle.ps1",
             FOLDER / "v3_fixed_paths_readonly.ps1",
             FOLDER / "v3_paper_offline_probe.ps1",
             FOLDER / "windows_maintenance_snapshot.ps1",
             FOLDER / "workspace_report.ps1"],
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

    def test_v3_offline_probe_is_only_existing_restricted_runner_stub(self):
        task = FOLDER / "v3_paper_offline_probe.ps1"
        self.assertTrue(task.is_file())
        self.assertFalse(task.is_symlink())
        self.assertLess(task.stat().st_size, 65536)
        src = task.read_text("utf-8")
        self.assertTrue(src.startswith("# MINIPC_REVIEWED_TASK_V1"))
        for required in (
            "CryptoSupportSvc", "MINI-PC-CryptoSupport",
            "WindowsBuiltInRole]::Administrator",
            "MINIPC_TASK_SANDBOX", "_protected_main",
            "P1NativeModelWriterTests", "WaitForExit(90000)",
            "Ran 8 tests in", "PYTHONDONTWRITEBYTECODE",
            "SUPABASE_SERVICE_ROLE_KEY", "V3_PAPER_MODEL_KEY",
            "test_native_parent_child_model_p4_actual_paper_receipt_and_no_retry",
            "test_native_p1_full_model_reject_has_no_fill_and_no_retry",
            "test_native_p1_missing_fill_or_bad_response_id_quarantines_without_spend_retry",
            "test_p1_restart_follows_new_fill_clock_not_old_scanner",
            "test_native_p1_child_paper_cloud_forwarding_uses_same_relay_once",
            "test_native_p1_reject_missed_opportunity_tracks_child_not_parent",
            "test_native_p1_child_wait_watches_fresh_child_ttl_not_old_parent",
            "test_native_p1_stale_source_and_unapproved_budget_do_not_spend",
            "MINIPC_REVIEWED_TASK_ACK_V1",
            "task = 'v3_paper_offline_probe'",
            "mutation_scope = 'RESTRICTED'",
            "live_paper_writer_physically_witnessed = $false",
            "independent_cloud_receipt_verified = $false",
            "model_api_spend = $false",
            "v3_paper_activated = $false",
            "v2r4_runtime_touched = $false",
            "technical_release_proofs_credited = 0",
        ):
            self.assertIn(required, src, required)
        self.assertEqual(src.count("ConvertTo-Json -Compress"), 1)
        # The original host incident showed python.exe absent from the
        # CryptoSupportSvc PATH. Permit only preinstalled system-wide
        # Python or the standard py.exe launcher; never an admin profile.
        for required in (
            "Get-Command -Name $name -CommandType Application",
            "'python.exe', 'py.exe'",
            "'Python314','Python313','Python312','Python311','Python310'",
            "$env:ProgramFiles, $env:SystemDrive",
            "no Python executable visible to restricted Windows owner",
            "$useLauncher", "'-3 '",
        ):
            self.assertIn(required, src, required)
        active = "\n".join(line.lower() for line in src.splitlines()
                           if not line.lstrip().startswith("#"))
        for prohibited in (
            "start-service", "set-service", "stop-service",
            "register-scheduledtask", "start-scheduledtask",
            "enable-scheduledtask", "stop-scheduledtask",
            "invoke-expression", "invoke-webrequest", "invoke-restmethod",
            "start-process", "git checkout", "git pull",
            "supabase db", "supabase functions deploy",
            "c:\\users", "get-content", "set-content",
            "remove-item", "new-item", "copy-item",
            "set-acl", "icacls", "write-host",
        ):
            self.assertNotIn(prohibited, active, prohibited)
        self.assertNotIn("$" + "{{", src)

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
