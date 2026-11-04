"""Focused source and (when available) PowerShell fail-closed regression checks for PR #667.

Never executes the authorized mutation mode. Does not change a host task or series.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/minipc-v2r4-pr666-inert-code-stage.ps1"
SOURCE = SCRIPT.read_text(encoding="utf-8")


class Pr666ScopedReleaseTests(unittest.TestCase):
    def test_exact_component_scope_and_commit(self):
        self.assertIn("b4c751fbe9df468360a7683961aaf46228c3b944", SOURCE)
        self.assertIn("PAPER-V2R4-20261009T110135Z", SOURCE)
        self.assertIn("8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0", SOURCE)
        assignment = re.search(r"\$names=@\((.*?)\)", SOURCE, re.S)
        self.assertIsNotNone(assignment)
        self.assertIn("CryptoMiniPC-V2R4PaperCandidates", assignment.group(1))
        self.assertIn("CryptoMiniPC-V2R4PaperLifecycle", assignment.group(1))
        self.assertNotIn("CryptoMiniPC-V2R4PaperWait", assignment.group(1))
        self.assertNotIn("CryptoMiniPC-V2R4PaperCloudSync", assignment.group(1))

    def test_inert_byte_inventory_and_rollback_guards(self):
        for predicate in (
            "function Verify-Stage", "function ActiveChildren", "function Quiet",
            "function Backup-Tasks", "function Restore-Tasks",
            "PR666_INERT_STAGE_INCOMPLETE_NO_LIVE_MUTATION",
            "ROLLBACK_APPROVED_PR666_PAPER_ONLY",
            "EXECUTE_APPROVED_PR666_CANDIDATES_LIFECYCLE_ONLY",
            "SEPARATE", "TASKS_REBOUND_OLD_CHILDREN_QUIESCED",
            "FAIL_CLOSED_MANUAL_RECOVERY_REQUIRED",
            "NEW_CODE_HEALTHY_ORIGINAL_BACKUP_RETAINED",
            "paper_runtime_control.json", "checked_at_utc",
            "CreationDate", "xml_sha256", "merge-base --is-ancestor",
            "diff --quiet $pin HEAD",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, SOURCE)
        self.assertNotIn("Invoke-RestMethod", SOURCE)
        self.assertNotIn("Invoke-Sqlcmd", SOURCE)
        self.assertNotIn("v2r4-technical-cutover'", SOURCE)

    @unittest.skipUnless(shutil.which("pwsh") or shutil.which("powershell"),
                         "PowerShell not available on this runner")
    def test_powershell_parser_and_unauthorized_modes_fail_closed(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        quoted = str(SCRIPT).replace("'", "''")
        parse = (
            "$tokens=$null;$errors=$null;"
            f"[System.Management.Automation.Language.Parser]::ParseFile('{quoted}',"
            "[ref]$tokens,[ref]$errors)|Out-Null;"
            "if($errors.Count){$errors|ForEach-Object{Write-Error $_};exit 5}"
        )
        result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", parse],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory() as directory:
            # Explicit no-host location: no existing tasks, runtime or release.
            for mode in (["-Execute"], ["-Rollback"], ["-Stage"],
                         ["-Execute", "-Rollback"]):
                with self.subTest(mode=mode):
                    ran = subprocess.run(
                        [shell, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT),
                         "-TradingRoot", directory, *mode],
                        capture_output=True, text=True, timeout=30,
                    )
                    self.assertNotEqual(ran.returncode, 0)
                    self.assertFalse(list(pathlib.Path(directory).rglob("*.xml")))
                    self.assertFalse(list(pathlib.Path(directory).rglob("*.json")))


if __name__ == "__main__":
    unittest.main()
