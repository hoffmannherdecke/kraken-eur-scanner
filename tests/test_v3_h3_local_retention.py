#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "tools" / "v3-h3-shadow-runtime.py"
SPEC = importlib.util.spec_from_file_location("v3_h3_shadow_runtime_retention_tested", P)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to import H3 runtime")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class H3LocalRetentionTests(unittest.TestCase):
    def _write_pair(self, evidence: Path, contexts: Path, cid: str, age: int) -> None:
        ep = evidence / f"{cid}.json"
        cp = contexts / f"{cid}.json"
        ep.write_text("{}", encoding="utf-8")
        cp.write_text("{}", encoding="utf-8")
        ts = time.time() - age
        os.utime(ep, (ts, ts))
        os.utime(cp, (ts, ts))

    def test_prunes_only_oldest_synced_pairs_beyond_cap(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / "evidence"
            contexts = root / "contexts"
            evidence.mkdir()
            contexts.mkdir()
            for idx in range(5):
                self._write_pair(evidence, contexts, f"c{idx}", 100 - idx)

            pruned = M.prune_synced_local_pair_files(
                evidence,
                contexts,
                {"c0", "c1", "c2", "c3", "c4"},
                3,
            )
            self.assertEqual(pruned, ["c0", "c1"])
            self.assertEqual(len(list(evidence.glob("*.json"))), 3)
            self.assertFalse((contexts / "c0.json").exists())
            self.assertFalse((contexts / "c1.json").exists())

    def test_never_deletes_unsynced_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = root / "evidence"
            contexts = root / "contexts"
            evidence.mkdir()
            contexts.mkdir()
            for idx in range(4):
                self._write_pair(evidence, contexts, f"c{idx}", 100 - idx)

            pruned = M.prune_synced_local_pair_files(
                evidence,
                contexts,
                {"c1", "c2", "c3"},
                2,
            )
            self.assertIn("c1", pruned)
            self.assertTrue((evidence / "c0.json").exists())
            self.assertTrue((contexts / "c0.json").exists())


if __name__ == "__main__":
    unittest.main()
