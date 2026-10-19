"""Bounded read-only original-runner path discovery contract."""
from pathlib import Path
import unittest

TASK = Path("tools/minipc_runner_tasks/v3_fixed_paths_readonly.ps1")

class V3FixedPathReadbackContract(unittest.TestCase):
    def test_reviewed_scope(self):
        s = TASK.read_text("utf-8")
        self.assertTrue(s.startswith("# MINIPC_REVIEWED_TASK_V1"))
        self.assertIn("CryptoSupportSvc", s)
        self.assertIn("WindowsBuiltInRole]::Administrator", s)
        self.assertIn("MINI-PC-CryptoSupport", s)
        self.assertIn("MINIPC_V3_PATHS_SAFE_SUMMARY_V1", s)
        self.assertIn("task='v3_fixed_paths_readonly'", s)
        self.assertIn("local_filesystem_writes=$false", s)
        self.assertEqual(s.count("root_key=$root.key"), 1)
        self.assertLess(TASK.stat().st_size, 8192)
        self.assertFalse(TASK.is_symlink())
        for name in ("TRADING", "STAGING", "V3STAGE"):
            self.assertIn(name, s)
    def test_no_mutations_or_arbitrary_execution(self):
        s = "\n".join(line.lower() for line in TASK.read_text("utf-8").splitlines()
                      if not line.lstrip().startswith("#"))
        for forbidden in ("get-childitem", "get-content", "set-content", "remove-item",
                          "copy-item", "move-item", "new-item", "start-process",
                          "invoke-expression", "invoke-webrequest", "invoke-restmethod",
                          "git pull", "git checkout", "set-acl", "icacls",
                          "start-service", "stop-service", "start-scheduledtask",
                          "register-scheduledtask", "$args", "param("):
            self.assertNotIn(forbidden, s)
        self.assertNotIn("get-childitem -recurse", s)

if __name__ == "__main__":
    unittest.main()
