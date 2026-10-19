"""One small source-only check for the reuse-first reviewed Mini-PC bundle.

Never treat this static contract as an original Windows host acknowledgement.
"""
from pathlib import Path
import re
import unittest

SCRIPT = Path("tools/minipc_runner_tasks/operations_readonly_bundle.ps1")


class ReviewedOperationsBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.active = "\n".join(line.lower() for line in cls.source.splitlines()
                               if not line.lstrip().startswith("#"))

    def test_one_runner_one_result_and_only_existing_child_tasks(self):
        s = self.source
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        self.assertFalse(SCRIPT.is_symlink())
        self.assertLess(SCRIPT.stat().st_size, 65536)
        for name in ("host_safety_probe", "windows_maintenance_snapshot",
                     "log_status_summary"):
            self.assertIn("'" + name + "'", s)
        self.assertEqual(s.count("Join-Path $PSScriptRoot ($name + '.ps1')"), 1)
        self.assertIn("CryptoSupportSvc", s)
        self.assertIn("WindowsBuiltInRole]::Administrator", s)
        self.assertIn("MINI-PC-CryptoSupport", s)
        self.assertIn("MINIPC_REVIEWED_TASK_ACK_V1", s)
        self.assertIn("task = 'operations_readonly_bundle'", s)
        self.assertIn("mutation_scope = 'RESTRICTED'", s)
        self.assertIn("MINIPC_OPERATIONS_BATCH_SAFE_SUMMARY_V1", s)
        self.assertIn("overall_readback = $overall", s)

    def test_no_user_parameters_or_raw_sensitive_values(self):
        s = self.active
        for forbidden in (
            "param(", "$args", "invoke-expression", "invoke-command",
            "invoke-restmethod", "invoke-webrequest", "start-process",
            "get-content", "get-childitem", "set-content", "out-file",
            "new-item", "remove-item", "copy-item", "move-item",
            "start-service", "stop-service", "set-service",
            "register-scheduledtask", "start-scheduledtask",
            "enable-scheduledtask", "disable-scheduledtask",
            "restart-computer", "set-acl", "icacls", "get-credential",
            ".environment", "api_key", "scriptblock", "invoke-cimmethod",
        ):
            self.assertNotIn(forbidden, s)
        self.assertIn("local_filesystem_writes = $false", s)
        self.assertIn("service_or_task_mutations = $false", s)
        self.assertIn("new_permissions = $false", s)
        self.assertIn("trading_orders_permitted = $false", s)
        self.assertIn("active_runtime_release = $false", s)
        self.assertEqual(s.count("write-host ('minipc_operations_batch_safe_summary_v1 '"), 1)

    def test_honest_partial_readback_without_raw_child_output(self):
        for token in (
            "'UNAVAILABLE'", "'COMPLETE'", "'PARTIAL'",
            "ConvertFrom-Json -ErrorAction Stop",
            "if ($ack.kind -cne 'MINIPC_REVIEWED_TASK_ACK_V1'",
            "$ack.task -cne $name",
            "$ack.mutation_scope -cne 'RESTRICTED'",
            "([string]$rawResult[0]).Length -gt 16384",
            "$safe | ConvertTo-Json",
            "local_filesystem_writes = $false",
        ):
            self.assertIn(token, self.source)
        self.assertNotIn("Write-Host $rawResult", self.source)
        self.assertNotIn("Write-Host $ack", self.source)
        self.assertNotIn("Write-Output $rawResult", self.source)


if __name__ == "__main__":
    unittest.main()
