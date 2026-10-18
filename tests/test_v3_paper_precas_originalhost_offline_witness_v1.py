"""Offline tests of the one-shot originalhost PRE-CAS witness.

No cloud, Windows Task, real model, Kraken network, runtime, or actual release.
The physically deployed witness is separately read back on the Mini-PC.
"""
import json
from pathlib import Path
import tempfile
import unittest

from tools.v3_paper_precas_originalhost_offline_witness_v1 import (
    inspect, run_offline_cases,
)


class OfflineDualCaseWitnessTests(unittest.TestCase):
    def test_two_actual_p4_ledger_cases_share_one_lock_and_no_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "single-owner"
            target.mkdir()
            series = "PAPER-V3-CANARY-PRECAS-OFFLINE-LOCALCI"
            result = run_offline_cases(target, series)
            self.assertEqual(result["status"], "HOST_LOCAL_OFFLINE_MODEL_STUB_ONLY")
            self.assertTrue(result["native_owner_lock_used"])
            self.assertTrue(result["no_real_model_http"])
            self.assertTrue(result["simulated_model_approval_not_user_approval"])
            self.assertFalse(result["cloud_receipts_independently_verified"])
            self.assertFalse(result["physical_host_readback_independently_verified"])
            self.assertFalse(result["paper_release_authorized"])
            self.assertFalse(result["orders"])
            self.assertEqual(result["technical_release_proofs_credited"], 0)
            self.assertEqual(
                [(c["case"], c["p4_decision"], c["paper_fill_count"]) for c in result["cases"]],
                [("POSITIVE_BUY_SCOUT", "BUY_SCOUT", 1),
                 ("NEGATIVE_REJECT", "REJECT", 0)])
            journal_files = list((target / "journal").glob("*.json"))
            self.assertGreaterEqual(len(journal_files), 15)
            self.assertEqual(len(list((target / "model-stub-reservations").glob(
                "*.reserved.json"))), 2)
            no_buy = result["cases"][1]
            self.assertEqual(no_buy["paper_fill_result"], "NO_PAPER_FILL")
            self.assertFalse(any(x["phase"] == "PAPER_FILL" for x in no_buy["receipts"]))
            self.assertTrue(all(
                json.loads(f.read_text("utf-8"))["orders"] is False
                for f in journal_files))

    def test_preflight_never_treats_missing_staging_as_host_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"; src.mkdir()
            # Deliberately absent original paths must not create anything.
            with self.assertRaises(ValueError):
                inspect(source=src, stage=Path(tmp) / "missing",
                        stage_sha="a" * 40)
            self.assertEqual(list(src.iterdir()), [])

    def test_strict_canary_namespace_and_no_hidden_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "single-owner"
            target.mkdir()
            with self.assertRaisesRegex(ValueError, "synthetic CANARY"):
                run_offline_cases(target, "PAPER-V3-20261018T190000Z")
            self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
