"""Contract tests for the one-step DIRECT mode in the existing Mini-PC file bridge."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"tools/minipc_runner_tasks/file_access_bounded.ps1").read_text("utf-8")

class DirectFileHandoffContract(unittest.TestCase):
    def test_explicit_single_file_only(self):
        self.assertIn("(SEARCH|EXPORT|DIRECT)",SRC)
        self.assertIn("$mode -ceq 'DIRECT' -and ($expected",SRC)
        self.assertIn("if($mode -ceq 'DIRECT'){$expected=$hash}",SRC)
        self.assertIn("$mode -ceq 'EXPORT' -and $hash -cne $expected",SRC)
        self.assertIn("if($mode -ceq 'SEARCH')",SRC)
        self.assertIn("MINIPC_FILE_PROVENANCE_V1",SRC)
        self.assertIn("origin-sha256.json",SRC)
        self.assertIn("FILE_ACCESS_DENIED:RESERVED_NAME",SRC)
        self.assertIn("original_modified=$false",SRC)
    def test_non_sensitive_diagnostic_stages(self):
        for stage in ("ROOT_CHECK","PATH_DECODE","SOURCE_PATH","SOURCE_READ","CONTENT_SCREEN","TEMP_STAGE","PROVENANCE","COMPLETE"):
            self.assertIn(stage,SRC)
        self.assertIn("failure_stage =",SRC)
        self.assertNotIn("Exception.Message) | Write-Output",SRC)
    def test_original_guardrails_still_apply(self):
        for x in (
            "CryptoSupportSvc", "WindowsBuiltInRole]::Administrator",
            "Assert-Path $rel", "FILE_ACCESS_DENIED:SENSITIVE_NAME",
            "FILE_ACCESS_DENIED:SENSITIVE_CONTENT",
            "FILE_ACCESS_DENIED:ZIP_SENSITIVE_CONTENT", "FILE_ACCESS_DENIED:EXPORT_SIZE",
            "Get-FileHash", "FILE_HASH_MISMATCH", "RUNNER_TEMP",
            "new_permissions = $false", "trading_orders_permitted = $false"
        ):
            self.assertIn(x,SRC)
        for x in ("Set-Acl", "Start-Service", "Invoke-Expression", "Invoke-RestMethod"):
            self.assertNotIn(x,SRC)
if __name__=="__main__": unittest.main()
