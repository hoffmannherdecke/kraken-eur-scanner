#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "tools" / "v3-h3-shadow-runtime.py"
SPEC = importlib.util.spec_from_file_location("v3_h3_shadow_runtime_tested", P)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import H3 runtime")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

EXPECTED = "e533f05d31a5b80248076b4870addf4606dae3d8f0432a11ae66bea03db73ded"


class CanonicalConfigHashTests(unittest.TestCase):
    def test_repo_config_matches_frozen_hash(self):
        p = ROOT / "research" / "v3" / "shadow-candidates" / "v3-h3-shadow-001-config.json"
        self.assertEqual(M.sha256_file(p), EXPECTED)

    def test_crlf_and_lf_hash_identically(self):
        src = (ROOT / "research" / "v3" / "shadow-candidates" / "v3-h3-shadow-001-config.json").read_text("utf-8")
        canonical = src.replace("\r\n", "\n").replace("\r", "\n")
        with tempfile.TemporaryDirectory() as td:
            lf = Path(td) / "lf.json"
            crlf = Path(td) / "crlf.json"
            lf.write_bytes(canonical.encode("utf-8"))
            crlf.write_bytes(canonical.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(M.sha256_file(lf), EXPECTED)
            self.assertEqual(M.sha256_file(crlf), EXPECTED)


if __name__ == "__main__":
    unittest.main()
