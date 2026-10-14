"""Offline exact-source deploy safety: preserve PR297 crash footer and match PR298 code."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

builder = load("last_eur_fix_builder", ROOT / "tools/minipc-ws-shadow-last-eur-fix-builder.py")
footer = load("crash_footer", ROOT / "tools/minipc-ws-shadow-crash-footer.py")
current = (ROOT / "paper_evaluator/v2r4_ws_shadow_watcher.py").read_bytes()

def create_pre_fix():
    text = current.decode("utf-8")
    for hunk_id, (before, after) in reversed(list(enumerate(builder.HUNKS))):
        if text.count(after) != 1:
            raise ValueError(f"production main does not match PR298 hunk {hunk_id}, occurrences={text.count(after)}")
        text = text.replace(after, before)
    return text.encode("utf-8")

class LastEURFixBuilderTests(unittest.TestCase):
    def test_exact_pr298_source_with_preserved_diagnostic_footer(self):
        original = create_pre_fix()
        installed = footer.instrument(original)
        patched = builder.patch(installed)
        expected = footer.instrument(current)
        self.assertEqual(patched, expected)
        self.assertIn(b"v2r4-ws-shadow-python-crash.log", patched)
        self.assertIn(b"invalid_price_pairs", patched)

    def test_fail_closed_without_installed_footer(self):
        with self.assertRaises(ValueError):
            builder.patch(create_pre_fix())

    def test_fail_closed_if_already_patched(self):
        with self.assertRaises(ValueError):
            builder.patch(footer.instrument(current))

    def test_original_instrumented_footer_retained_for_crlf(self):
        old = create_pre_fix().replace(b"\n", b"\r\n")
        installed = footer.instrument(old)
        patched = builder.patch(installed)
        self.assertEqual(patched, footer.instrument(current.replace(b"\n", b"\r\n")))
        self.assertNotIn(b"\n", patched.replace(b"\r\n", b""))

if __name__ == "__main__":
    unittest.main()
