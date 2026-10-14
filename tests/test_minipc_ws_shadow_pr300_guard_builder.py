"""Original-hash-only physical PR300 builder regression and PR297/299 preservation."""
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = load("ws_pr300_guard", ROOT / "tools/minipc-ws-shadow-pr300-io-guard-builder.py")
footer = load("ws_pr297_footer", ROOT / "tools/minipc-ws-shadow-crash-footer.py")
pr300_source = (ROOT / "paper_evaluator/v2r4_ws_shadow_watcher.py").read_bytes().replace(b"\r\n", b"\n")


def pre_pr300_source():
    source = pr300_source.decode("utf-8")
    for i, (before, after) in reversed(list(enumerate(builder.HUNKS))):
        if source.count(after) != 1:
            raise ValueError(f"PR300 hunk {i} mismatch, count={source.count(after)}")
        source = source.replace(after, before)
    return source.encode("utf-8")


class PR300GuardedDeploymentTests(unittest.TestCase):
    def test_exact_byte_equivalence_and_both_previous_guards_retained(self):
        instrumented_pr299 = footer.instrument(pre_pr300_source())
        patched = builder.patch(instrumented_pr299)
        self.assertEqual(patched, footer.instrument(pr300_source))
        self.assertIn(b"v2r4-ws-shadow-python-crash.log", patched)
        self.assertIn(b"invalid_price_pairs", patched)
        self.assertIn(b"WINDOWS_ACCESS_RETRY_DELAYS", patched)

    def test_crlf_pinned_installed_source_remains_identical_except_guard(self):
        source = pre_pr300_source().replace(b"\n", b"\r\n")
        patched = builder.patch(footer.instrument(source))
        self.assertEqual(patched, footer.instrument(pr300_source.replace(b"\n", b"\r\n")))
        self.assertNotIn(b"\n", patched.replace(b"\r\n", b""))

    def test_uninstrumented_pr299_source_is_rejected(self):
        with self.assertRaises(ValueError):
            builder.patch(pre_pr300_source())

    def test_already_guarded_pr300_is_rejected(self):
        with self.assertRaises(ValueError):
            builder.patch(footer.instrument(pr300_source))

    def test_missing_pr299_price_guard_is_rejected(self):
        altered = pre_pr300_source().replace(b"invalid_price_pairs", b"invalid_price_count")
        with self.assertRaises(ValueError):
            builder.patch(footer.instrument(altered))

    def test_original_footer_does_not_change_with_new_source(self):
        original = footer.instrument(pre_pr300_source()).decode()
        updated = builder.patch(original.encode()).decode()
        marker = 'if __name__ == "__main__":\n    try:\n'
        self.assertEqual(original[original.index(marker):], updated[updated.index(marker):])


if __name__ == "__main__":
    unittest.main()
