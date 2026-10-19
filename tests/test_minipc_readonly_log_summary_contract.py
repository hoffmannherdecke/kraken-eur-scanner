"""Offline contract for the one reusable restricted Windows log summarizer.

Never touch a real Windows file, runner, GitHub task, or Trading runtime.
"""
from pathlib import Path
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/log_status_summary.ps1")


class ReadonlyLogSummaryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_uses_existing_reviewed_minipc_runner_contract(self):
        s = self.text
        for token in (
            "# MINIPC_REVIEWED_TASK_V1",
            "MINIPC_REVIEWED_TASK_ACK_V1",
            "status = 'SUCCESS'",
            "task = 'log_status_summary'",
            "mutation_scope = 'RESTRICTED'",
            "CryptoSupportSvc",
            "WindowsBuiltInRole]::Administrator",
            "MINI-PC-CryptoSupport",
        ):
            self.assertIn(token, s)

    def test_reads_only_known_logs_with_existing_windows_permissions(self):
        s = self.text
        for token in (
            r"C:\Users\ADMIN\Trading\Logs",
            r"C:\CryptoSupport\Logs",
            "Get-ChildItem -LiteralPath $root.path -File -Filter '*.log'",
            "Get-Content -LiteralPath $file.FullName -Tail $maxTailLines",
            "ReparsePoint",
            "$maxFilesPerRoot = 5",
            "$maxTailLines = 4000",
            "$maxFileBytes = 16MB",
            "'ACCESS_DENIED'",
            "'ROOT_UNAVAILABLE'",
            "'ROOT_MISSING'",
            "'PARTIAL_ACCESS_DENIED'",
        ):
            self.assertIn(token, s)
        self.assertNotIn("Get-ChildItem -Recurse", s)

    def test_no_raw_output_or_user_supplied_command(self):
        s = self.text
        for token in (
            "total_files_read",
            "matched_status_events",
            "evidence_present",
            "source_readbacks",
            "status_counts",
            "raw_lines_exposed = $false",
            "filenames_exposed = $false",
            "local_filesystem_writes = $false",
            "secrets_used = $false",
            "trading_orders_permitted = $false",
            "active_runtime_release = $false",
        ):
            self.assertIn(token, s)
        for banned in (
            "Invoke-Expression", "iex ", "Invoke-WebRequest",
            "Invoke-RestMethod", "Start-Process", "Set-Acl",
            "icacls", "New-Item", "Set-Content", "Add-Content",
            "Out-File", "Remove-Item", "Set-Service", "Start-Service",
            "Stop-Service", "schtasks", "Invoke-Command", "Enter-PSSession",
            "Write-Host", "Write-Output $line", "ConvertTo-SecureString",
            "KRAKEN_API", "OPENAI_API_KEY", "SUPABASE_SERVICE_ROLE",
            "GITHUB_EVENT_PATH", "MINI_PC_TASK_REQUEST",
        ):
            self.assertNotIn(banned, s)

    def test_capped_window_and_status_only_parsing(self):
        s = self.text
        self.assertIn("UtcNow.AddHours(-24)", s)
        self.assertIn("DateTimeOffset]::TryParse", s)
        self.assertIn("status=(?<status>", s)
        self.assertIn("Sort-Object | Select-Object -First 40", s)
        self.assertIn("ConvertTo-Json -Depth 6 -Compress", s)


if __name__ == "__main__":
    unittest.main()
