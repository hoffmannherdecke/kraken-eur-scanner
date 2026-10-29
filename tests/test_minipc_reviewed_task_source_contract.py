"""Offline contract for the first restricted Mini-PC reviewed task."""
from pathlib import Path
import re
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/host_safety_probe.ps1")
FOLDER = Path("tools/minipc_runner_tasks")

# Common fail-closed floor for *all* source-reviewed tasks, including later ones.
# Per-task tests below remain the authority for narrower read/write boundaries.
# This file runs on every PR as part of the already required source-and-review check.
BASE_DENIED_COMMANDS = (
    "invoke-expression", "invoke-command", "invoke-webrequest",
    "invoke-restmethod", "new-pssession", "enter-pssession",
    "start-process", "set-acl", "icacls", "start-service",
    "stop-service", "set-service", "restart-service",
    "register-scheduledtask", "unregister-scheduledtask",
    "enable-scheduledtask", "disable-scheduledtask",
    "start-scheduledtask", "restart-computer", "stop-computer",
    "-encodedcommand", "-startupType automatic", "get-credential",
    "supabase functions deploy",
)


def reviewed_task_violations(name: str, source: str) -> list[str]:
    """Static minimum safety floor; never claim this proves Windows behavior."""
    errors = []
    if not source.startswith("# MINIPC_REVIEWED_TASK_V1"):
        errors.append("reviewed task source header missing")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", name):
        errors.append("unsafe task basename")
    for marker in ("CryptoSupportSvc", "MINI-PC-CryptoSupport",
                   "WindowsBuiltInRole]::Administrator",
                   "MINIPC_REVIEWED_TASK_ACK_V1"):
        if marker not in source:
            errors.append("missing original restricted runner contract: " + marker)
    if not re.search(r"\btask\s*=\s*['\"]" + re.escape(name) + r"['\"]", source):
        errors.append("missing exact result task identity")
    if not re.search(r"\bmutation_scope\s*=\s*['\"]RESTRICTED['\"]", source):
        errors.append("missing restricted mutation scope")
    active = "\n".join(line for line in source.splitlines()
                       if not line.lstrip().startswith("#")).lower()
    for forbidden in BASE_DENIED_COMMANDS:
        if forbidden.lower() in active:
            errors.append("forbidden source token: " + forbidden)
    if re.search(r"\bparam\s*\(", active) or "$args" in active:
        errors.append("parameterized or free-form PowerShell")
    if "${{" in source:
        errors.append("workflow expression embedded in task source")
    return errors


class MinipcReviewedTaskSourceTests(unittest.TestCase):
    def test_only_reviewed_task_files(self):
        self.assertTrue(SCRIPT.is_file())
        self.assertEqual(
            sorted(FOLDER.glob("*.ps1")),
            [FOLDER / "access_boundary_probe.ps1", SCRIPT,
             FOLDER / "log_status_summary.ps1",
             FOLDER / "operations_readonly_bundle.ps1",
             FOLDER / "v3_cas_log_readonly_triage.ps1",
             FOLDER / "v3_cas_witness_archive_stage.ps1",
             FOLDER / "v3_fixed_paths_readonly.ps1",
             FOLDER / "v3_paper_offline_probe.ps1",
             FOLDER / "windows_maintenance_snapshot.ps1",
             FOLDER / "workspace_report.ps1"],
        )
        self.assertFalse(SCRIPT.is_symlink())
        self.assertLess(SCRIPT.stat().st_size, 65536)

    def test_every_reviewed_task_has_minimum_nonadmin_execution_contract(self):
        for file in sorted(FOLDER.glob("*.ps1")):
            with self.subTest(task=file.name):
                self.assertFalse(file.is_symlink(), file)
                self.assertLess(file.stat().st_size, 65536, file)
                self.assertEqual(reviewed_task_violations(
                    file.stem, file.read_text(encoding="utf-8")), [], file.name)

    def test_minimum_execution_contract_rejects_new_unsafe_commands(self):
        good = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(reviewed_task_violations("host_safety_probe", good), [])
        for malicious in (
            "Invoke-Expression $payload",
            "Set-Acl -Path $root -AclObject $acl",
            "Register-ScheduledTask -TaskName 'Unreviewed'",
            "Invoke-RestMethod -Uri $remote",
            "Start-Service -Name $otherRunner",
            "param($userCommand)",
            "$args | Out-String",
        ):
            with self.subTest(malicious=malicious):
                self.assertTrue(reviewed_task_violations(
                    "host_safety_probe", good + "\n" + malicious),
                    malicious)
        self.assertTrue(reviewed_task_violations(
            "other_task", good), "task identity substitution must fail")

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

    def test_v3_cas_log_triage_is_bounded_and_never_authorizes_release(self):
        task = FOLDER / "v3_cas_log_readonly_triage.ps1"
        source = task.read_text("utf-8")
        self.assertEqual(reviewed_task_violations(task.stem, source), [])
        for required in (
            r"C:\Users\ADMIN\Trading\Logs",
            r"C:\CryptoSupport\Logs",
            "$limitFiles = 5", "$limitLines = 4000", "$limitBytes = 16MB",
            "historical_coverage='INCOMPLETE'",
            "historical_cas_never_invoked_proven=$false",
            "independent_cloud_provenance_verified=$false",
            "cas_dispatch_authorized=$false",
            "v3_paper_release_authorized=$false",
            "disposition='HOLD_REQUIRES_INDEPENDENT_HISTORICAL_CUSTODY'",
            "raw_log_lines_exposed=$false",
            "local_filesystem_writes=$false",
        ):
            self.assertIn(required, source)
        for forbidden in ("Write-Host", "Set-Content", "Invoke-RestMethod"):
            self.assertNotIn(forbidden, source)

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

    def test_witness_archive_stage_has_one_fixed_approved_ntfs_scope(self):
        task = FOLDER / "v3_cas_witness_archive_stage.ps1"
        src = task.read_text("utf-8")
        self.assertEqual(reviewed_task_violations(task.stem, src), [])
        for item in (
            "C:\\CryptoSupport\\Workspace",
            "V3CasWitness-INACTIVE",
            "Assert-ExistingWorkspaceOwnerWrite",
            "SetAccessRuleProtection($true, $false)",
            "[IO.Directory]::CreateDirectory($archive, $isolatedAcl)",
            "archive_explicit_protected_three_principals_acl = $true",
            "AreAccessRulesProtected",
            "GetAccessRules",
            "S-1-5-18",
            "S-1-5-32-544",
            "CryptoSupportSvc",
            "WindowsBuiltInRole]::Administrator",
            "_protected_main",
            "v3_cas_local_spool_INACTIVE.py",
            "v3_cas_originalhost_spool_probe_INACTIVE.py",
            "MINIPC_TASK_SANDBOX",
            "PYTHONDONTWRITEBYTECODE",
            "SUPABASE_SERVICE_ROLE_KEY",
            "KRAKEN_API_SECRET",
            "V3_LOCAL_WITNESS_REAL_ORIGINALHOST_SANDBOX_PROBE_PASS",
            "[IO.Directory]::CreateDirectory($probe)",
            "000001.json", "000002.json",
            "[IO.File]::Delete($file)",
            "[IO.Directory]::Delete($probe, $false)",
            "no_paid_service_or_network_api = $true",
            "backup_and_powerloss_durability_proven = $false",
            "external_worm_custody_proven = $false",
            "cloud_cas_authorized = $false",
            "old_writer_auto_rearm_allowed = $false",
            "technical_v3_e2e_release_proofs_credited = 0",
            "task = 'v3_cas_witness_archive_stage'",
            "mutation_scope = 'RESTRICTED'",
        ):
            self.assertIn(item, src, item)
        active = "\n".join(
            line.lower() for line in src.splitlines()
            if not line.lstrip().startswith("#")
        )
        for forbidden in (
            "invoke-expression", "invoke-command", "invoke-restmethod",
            "invoke-webrequest", "start-process", "set-acl", "icacls",
            "start-service", "set-service", "register-scheduledtask",
            "remove-item", "del /", "rd /s", "trading\\runtime",
            "set-executionpolicy", "git pull", "supabase functions deploy",
            "upload-artifact", "aws ", "sigstore upload",
        ):
            self.assertNotIn(forbidden, active, forbidden)
        self.assertEqual(src.count("ConvertTo-Json -Compress"), 1)
        self.assertIn("$matched = [regex]::Match", src)
        self.assertIn("synthetic_filechain_hash_only_reported = $true", src)
        self.assertIn("originalhost_hash_report_is_independent_signature = $false", src)
        marker = "Write-Host ('V3_MINIPC_CAS_SYNTHETIC_HASH_PUBLIC_CANDIDATE_V1 '"
        self.assertIn(marker, src)
        self.assertGreater(src.index(marker), src.index("[IO.Directory]::Delete($probe, $false)"))
        self.assertEqual(src.count(marker), 1)

    def test_originalhost_spool_probe_is_synthetic_and_no_cas(self):
        source = Path("tools/v3_cas_originalhost_spool_probe_INACTIVE.py").read_text("utf-8")
        self.assertIn('Path(r"C:\\CryptoSupport\\Workspace\\V3CasWitness-INACTIVE")', source)
        self.assertIn('if os.name != "nt"', source)
        self.assertIn("directory.parent != BASE", source)
        self.assertIn("tuple(directory.iterdir())", source)
        self.assertIn("build_unsigned_intent(", source)
        self.assertIn("append_local_witness_candidate(", source)
        self.assertIn("review_local_witness_candidate(", source)
        self.assertIn("cloud_cas_authorized", source)
        self.assertIn("V3_LOCAL_WITNESS_REAL_ORIGINALHOST_SANDBOX_PROBE_PASS", source)
        self.assertIn('print(MARKER + " " + verified["last_entry_sha256"])', source)
        for forbidden in ("invoke_v3_paper_cas(", "requests.", "subprocess.",
                          "urllib.", "boto3", "http.client", "os.remove(",
                          "unlink(", "rmdir(", "shutil.rmtree("):
            self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
