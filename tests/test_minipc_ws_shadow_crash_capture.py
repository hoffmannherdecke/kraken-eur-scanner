"""Offline regression for bounded WSShadow Python crash trace diagnostic.

Only temp files, no Kraken endpoints, no original Mini-PC state, no task actions.
"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PATCHER = Path(__file__).resolve().parents[1] / "tools" / "minipc-ws-shadow-crash-footer.py"
SPEC = importlib.util.spec_from_file_location("ws_shadow_crash_footer", PATCHER)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)


def synthetic_source(body):
    return (
        "from pathlib import Path\n"
        "def main():\n"
        + body
        + '\nif __name__ == "__main__":\n'
        '    raise SystemExit(main())\n'
    ).encode("utf-8")


class CrashCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / "State"
        self.state.mkdir()
        self.heartbeat = self.state / "heartbeat.json"
        self.log = self.base / "Logs" / "v2r4-ws-shadow-python-crash.log"

    def run_patched(self, body):
        target = self.base / "modified.py"
        if target.exists():
            target.unlink()
        target.write_bytes(PATCH.instrument(synthetic_source(body)))
        return subprocess.run(
            [sys.executable, "-B", str(target), "--heartbeat", str(self.heartbeat)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_normal_exit_zero_and_no_log(self):
        result = self.run_patched("    return 0\n")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_python_exception_is_reraised_and_logged(self):
        result = self.run_patched("    raise RuntimeError('watcher synthetic JSON decode failure')\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("RuntimeError", result.stderr)
        self.assertIn("synthetic JSON decode failure", self.log.read_text(encoding="utf-8"))
        self.assertIn("WS-SHADOW PYTHON EXIT", self.log.read_text(encoding="utf-8"))

    def test_explicit_exit_one_is_preserved_and_logged(self):
        result = self.run_patched("    raise SystemExit(1)\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("SystemExit: 1", self.log.read_text(encoding="utf-8"))

    def test_log_rotation_keeps_last_48k(self):
        self.log.parent.mkdir()
        self.log.write_bytes(b"x" * (100 * 1024))
        result = self.run_patched("    raise ValueError('last_fatal_error')\n")
        self.assertEqual(result.returncode, 1)
        self.assertLessEqual(self.log.stat().st_size, 48 * 1024)
        self.assertIn("last_fatal_error", self.log.read_text(encoding="utf-8"))

    def test_missing_heartbeat_arg_does_not_mask_original_error(self):
        target = self.base / "modified.py"
        target.write_bytes(PATCH.instrument(synthetic_source("    raise ValueError('original')\n")))
        result = subprocess.run([sys.executable, str(target)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ValueError: original", result.stderr)
        self.assertFalse(self.log.exists())

    def test_missing_or_changed_footer_fails_closed(self):
        for source in (b"print('other watcher')\n", PATCH.instrument(synthetic_source("    return 0\n"))):
            with self.assertRaises(ValueError):
                PATCH.instrument(source)

    def test_crlf_variant_preserves_windows_line_endings(self):
        source = synthetic_source("    return 0\n").replace(b"\n", b"\r\n")
        output = PATCH.instrument(source)
        self.assertIn(b"\r\n", output)
        self.assertNotIn(b"\n", output.replace(b"\r\n", b""))
        

if __name__ == "__main__":
    unittest.main()
