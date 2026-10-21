"""Offline tests of the one-shot originalhost PRE-CAS witness.

No cloud, Windows Task, real model, Kraken network, runtime, or actual release.
The physically deployed witness is separately read back on the Mini-PC.
"""
import hashlib
import json
import subprocess
from pathlib import Path
import tempfile
import unittest

from tools.v3_paper_precas_originalhost_offline_witness_v1 import (
    inspect, run_offline_cases, _original_case_receipt, _case_economic_proof,
    inspect_existing_offline_originals,
)


class OfflineDualCaseWitnessTests(unittest.TestCase):
    def test_historical_stage_remains_verifiable_after_clean_source_checkout_advances(self):
        # An original 60-file stage is immutable. A newer clean HEAD must not
        # require checking out the old code or rerunning a synthetic writer.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "Source"
            trading = base / "Trading"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)],
                           check=True, capture_output=True)
            subprocess.run(["git", "-C", str(source), "config",
                            "user.name", "V3 Offline CI"], check=True)
            subprocess.run(["git", "-C", str(source), "config",
                            "user.email", "offline-ci@example.invalid"], check=True)
            must = [
                "paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
                "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
                "paper_evaluator/v3_experimental_paper_journal_v1.py",
                "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py",
                "paper_evaluator/v3_paper_minipc_native_launcher_v1.py",
                "tools/v3_experimental_paper_technical_gate.py",
                "tools/paper_series_transition_guard.py",
            ]
            files = must + [f"paper_evaluator/offline_{i:02d}.py"
                            for i in range(53)]
            rows = []
            for relative in files:
                src = source / relative
                src.parent.mkdir(parents=True, exist_ok=True)
                contents = ("# pinned original " + relative).encode() + bytes([10])
                src.write_bytes(contents)
                rows.append({"relative_path": relative,
                             "sha256": hashlib.sha256(contents).hexdigest()})
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm",
                            "historical V3 stage original"], check=True)
            stage_sha = subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "HEAD"],
                text=True).strip()
            stage = trading / "Staging" / ("V3Paper-INACTIVE-" + stage_sha[:12])
            stage.mkdir(parents=True)
            for relative in files:
                dst = stage / relative
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes((source / relative).read_bytes())
            manifest = {
                "kind": "V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1",
                "status": "STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED",
                "source_git_sha": stage_sha,
                "v3_paper_activated": False,
                "task_changes": False,
                "source_manifest": rows,
            }
            (stage / "v3-paper-inactive-source-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            (trading / "Research" / "V3Paper").mkdir(parents=True)
            # Simulate several merged PRs changing a pinned source file.
            updated = source / must[0]
            updated.write_text("# a later, valid code generation\\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(source), "add", "."], check=True)
            subprocess.run(["git", "-C", str(source), "commit", "-qm",
                            "new HEAD, old original still accessible"], check=True)
            result = inspect(source=source, stage=stage, stage_sha=stage_sha)
            self.assertEqual(result["verified_files"], 60)
            self.assertNotEqual(result["source_head"], stage_sha)
            self.assertEqual(result["stage_sha"], stage_sha)
            self.assertEqual(result["windows_crlf_checkout_files"], 0)
            self.assertTrue(result["source_manifest_sha256_checked_for_every_file"])
            # A Windows checkout with core.autocrlf produces CRLF source
            # worktree files. The original Stage copied precisely those
            # bytes and recorded their actual SHA256 in its immutable report.
            for row in rows:
                item = stage / row["relative_path"]
                original = item.read_bytes()
                self.assertIn(bytes([10]), original)
                self.assertNotIn(bytes([13, 10]), original)
                physical_windows = original.replace(bytes([10]), bytes([13, 10]))
                item.write_bytes(physical_windows)
                row["sha256"] = hashlib.sha256(physical_windows).hexdigest()
            (stage / "v3-paper-inactive-source-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            windows = inspect(source=source, stage=stage, stage_sha=stage_sha)
            self.assertEqual(windows["verified_files"], 60)
            self.assertEqual(windows["windows_crlf_checkout_files"], 60)
            self.assertTrue(windows["source_manifest_sha256_checked_for_every_file"])
            # Tampered stage without changed manifest: reject even though
            # CRLF normalization would otherwise be text-compatible.
            old = stage / must[0]
            pinned_original = old.read_bytes()
            old.write_bytes(pinned_original + bytes([13, 10]))
            with self.assertRaisesRegex(ValueError, "manifest SHA256 mismatch"):
                inspect(source=source, stage=stage, stage_sha=stage_sha)
            # Forged stage AND manifest with a meaningful content change
            # still cannot masquerade as benign Windows CRLF conversion.
            injected = pinned_original.replace(b"pinned", b"altered")
            old.write_bytes(injected)
            manifest["source_manifest"][0]["sha256"] = hashlib.sha256(
                injected).hexdigest()
            (stage / "v3-paper-inactive-source-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "historical Git bytes"):
                inspect(source=source, stage=stage, stage_sha=stage_sha)
            # A lone CR (not CRLF) or an extra LF is not an allowed
            # historical byte-for-byte text checkout conversion either.
            old.write_bytes(pinned_original + bytes([13]))
            manifest["source_manifest"][0]["sha256"] = hashlib.sha256(
                old.read_bytes()).hexdigest()
            (stage / "v3-paper-inactive-source-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "historical Git bytes"):
                inspect(source=source, stage=stage, stage_sha=stage_sha)
            # Forged new manifest SHA cannot authorize changed stage bytes:
            # the historical immutable Git blob is a third independent pin.
            old = stage / must[0]
            old.write_bytes(b"# forged newer local stage source")
            manifest["source_manifest"][0]["sha256"] = hashlib.sha256(
                old.read_bytes()).hexdigest()
            (stage / "v3-paper-inactive-source-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "historical Git bytes"):
                inspect(source=source, stage=stage, stage_sha=stage_sha)
            # A dirty worktree is never accepted, even if original blobs exist.
            (source / "local-mutation.txt").write_text("not committed")
            with self.assertRaisesRegex(ValueError, "source tree dirty"):
                inspect(source=source, stage=stage, stage_sha=stage_sha)

    def test_original_release_gate_must_be_manifest_verified(self):
        from tools import v3_paper_precas_originalhost_offline_witness_v1 as witness
        import inspect
        source = inspect.getsource(witness.inspect)
        self.assertIn(
            '"tools/v3_experimental_paper_technical_gate.py"',source)
        self.assertIn(
            '"paper_evaluator/v3_paper_minipc_native_launcher_v1.py"',source)
        self.assertIn('"tools/paper_series_transition_guard.py"',source)


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
            # The first real native disk file is evidence; a reviewer must
            # still independently attest host identity and Cloud originals.
            buy, rejected = result["cases"]
            self.assertEqual(buy["series_id"], series)
            self.assertEqual(buy["paper_scout_eur"], 50.0)
            self.assertEqual(buy["paper_entry_taker_fee_eur"], 0.30)
            self.assertEqual(buy["native_journal_record_sha256"],
                             buy["paper_fill_record_sha256"])
            self.assertEqual(buy["p4_record_sha256"],
                             next(x["content_sha256"] for x in buy["receipts"]
                                  if x["phase"] == "P4_VALIDATION"))
            self.assertLessEqual(buy["p4_known_at_utc"],
                                 buy["paper_fill_known_at_utc"])
            self.assertIsNone(rejected["paper_fill_known_at_utc"])
            self.assertIsNone(rejected["paper_scout_eur"])
            self.assertIsNone(rejected["paper_entry_taker_fee_eur"])
            self.assertEqual(rejected["native_journal_record_sha256"],
                             rejected["p4_record_sha256"])
            for case in (buy, rejected):
                self.assertFalse(case["physical_host_attested"])
                self.assertFalse(case["cloud_originals_independently_verified"])
                self.assertNotIn("execution_kind", case)
                self.assertNotIn("cloud_query_readback_verified",case)

    def test_disk_receipt_hash_change_blocks_original_economics(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp) / "writer" / "journal"
            root=journal.parent
            root.mkdir()
            series="PAPER-V3-CANARY-PRECAS-OFFLINE-HASHCI"
            report=run_offline_cases(root,series)
            buy=report["cases"][0]
            fill=next(x for x in buy["receipts"] if x["phase"]=="PAPER_FILL")
            path=journal / (fill["event_id"] + ".json")
            row=json.loads(path.read_text("utf-8"))
            row["data"]["paper_entry_fee_eur"]=0.99
            path.write_text(json.dumps(row),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"changed since journal indexing"):
                _original_case_receipt(journal,fill,series_id=series,
                                       candidate_id=buy["candidate_id"])
            # Even a forged re-indexing of the changed bytes cannot turn a
            # wrong-fee paper fill into valid economic evidence.
            bad=dict(fill,content_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            p4=next(x for x in buy["receipts"] if x["phase"]=="P4_VALIDATION")
            with self.assertRaisesRegex(ValueError,"economics|ask-stop-stage2-fee"):
                _case_economic_proof(journal,series,buy["candidate_id"],p4,bad)

    def test_no_forged_pre_p4_paper_fill_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp) / "writer"
            root.mkdir()
            series="PAPER-V3-CANARY-PRECAS-OFFLINE-CLOCKCI"
            report=run_offline_cases(root,series)
            buy=report["cases"][0]
            journal=root / "journal"
            fill=next(x for x in buy["receipts"] if x["phase"]=="PAPER_FILL")
            p4=next(x for x in buy["receipts"] if x["phase"]=="P4_VALIDATION")
            path=journal / (fill["event_id"]+".json")
            row=json.loads(path.read_text("utf-8"))
            row["known_at_utc"]="2026-10-08T00:00:00Z"
            path.write_text(json.dumps(row),encoding="utf-8")
            changed=dict(fill,content_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,"chronologically before original P4"):
                _case_economic_proof(journal,series,buy["candidate_id"],p4,changed)

    def _existing_original_16_receipts(self, tmp):
        from tools.v3_paper_precas_synthetic_cloud_sandbox_v1 import (
            SERIES, STAGE_SHA,
        )
        root = (Path(tmp) / "Research" / "V3Paper" /
                ("PRECAS-OFFLINE-ORIGINALHOST-" + STAGE_SHA[:12]))
        root.mkdir(parents=True)
        report = run_offline_cases(root, SERIES)
        report["stage_source_sha"] = STAGE_SHA
        (root / "offline-model-stub-witness.json").write_text(
            json.dumps(report, sort_keys=True), encoding="utf-8")
        return root, SERIES

    def test_existing_physical_dual_case_is_reread_without_second_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, series = self._existing_original_16_receipts(tmp)
            all_files = {
                str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(),
                                           p.stat().st_mtime_ns)
                for p in root.rglob("*") if p.is_file()
            }
            readback = inspect_existing_offline_originals(root, series)
            self.assertEqual(readback["status"],
                             "EXISTING_HOST_ORIGINALS_REANALYZED_READ_ONLY")
            self.assertEqual(readback["event_count"], 16)
            self.assertEqual(readback["technical_release_proofs_credited"], 0)
            self.assertFalse(readback["native_writer_reexecuted"])
            self.assertFalse(readback["fresh_independent_cloud_readback_performed"])
            self.assertFalse(readback["v3_paper_release_authorized"])
            self.assertFalse(readback["real_model_or_market_evidence"])
            self.assertFalse(readback["physical_host_attestation_automatically_granted"])
            self.assertEqual(readback["orders"], False)
            buy, rejected = readback["cases"]
            self.assertEqual((buy["case"], buy["paper_fill_count"]),
                             ("POSITIVE_BUY_SCOUT",1))
            self.assertEqual(buy["paper_scout_eur"],50.0)
            self.assertEqual(buy["paper_entry_taker_fee_eur"],0.30)
            self.assertLessEqual(buy["p4_known_at_utc"],
                                 buy["paper_fill_known_at_utc"])
            self.assertEqual((rejected["case"],rejected["paper_fill_count"]),
                             ("NEGATIVE_REJECT",0))
            self.assertIsNone(rejected["paper_fill_known_at_utc"])
            self.assertEqual(rejected["native_journal_record_sha256"],
                             rejected["p4_record_sha256"])
            self.assertEqual(all_files, {
                str(p.relative_to(root)): (hashlib.sha256(p.read_bytes()).hexdigest(),
                                           p.stat().st_mtime_ns)
                for p in root.rglob("*") if p.is_file()
            })

    def test_new_source_pinned_stage_journal_readback_never_repeats_writer(self):
        newsha = "16e27043c2f40f016d5b64f82383e40b0f89326d"
        with tempfile.TemporaryDirectory() as tmp:
            root = (Path(tmp) / "Research" / "V3Paper" /
                    ("PRECAS-OFFLINE-ORIGINALHOST-" + newsha[:12]))
            root.mkdir(parents=True)
            series = "PAPER-V3-CANARY-PRECAS-OFFLINE-" + newsha[:12].upper()
            witness = run_offline_cases(root, series)
            witness["stage_source_sha"] = newsha
            (root / "offline-model-stub-witness.json").write_text(
                json.dumps(witness, sort_keys=True), encoding="utf-8")
            original_files = {
                str(p.relative_to(root)):
                    (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in root.rglob("*") if p.is_file()
            }
            proof = inspect_existing_offline_originals(root, series,
                                                       stage_sha=newsha)
            self.assertEqual(proof["status"],
                             "EXISTING_HOST_ORIGINALS_REANALYZED_READ_ONLY")
            self.assertEqual(proof["event_count"], 16)
            self.assertFalse(proof["native_writer_reexecuted"])
            self.assertFalse(proof["v3_paper_release_authorized"])
            self.assertFalse(proof["fresh_independent_cloud_readback_performed"])
            self.assertEqual(
                [(x["case"], x["paper_fill_count"]) for x in proof["cases"]],
                [("POSITIVE_BUY_SCOUT", 1), ("NEGATIVE_REJECT", 0)])
            self.assertEqual(original_files, {
                str(p.relative_to(root)):
                    (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in root.rglob("*") if p.is_file()
            })
            with self.assertRaisesRegex(ValueError, "unknown originalhost synthetic"):
                inspect_existing_offline_originals(root, series)
            with self.assertRaisesRegex(ValueError, "unknown originalhost synthetic"):
                inspect_existing_offline_originals(root, series,
                                                   stage_sha="a" * 40)
            # Even matching staged identity cannot make a self-edited
            # decision/count or edited receipt acceptable.
            f = root / "offline-model-stub-witness.json"
            bad = json.loads(f.read_text(encoding="utf-8"))
            bad["cases"][0]["paper_fill_count"] = 0
            f.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_existing_offline_originals(root, series,
                                                   stage_sha=newsha)

    def test_old_independent_sandbox_reference_is_match_only_not_fresh_attestation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, series = self._existing_original_16_receipts(tmp)
            manifest = inspect_existing_offline_originals(root,series)
            verified = inspect_existing_offline_originals(
                root,series,manifest["event_digest_join_sha256"])
            self.assertTrue(verified["prior_independent_cloud_digest_reference_matched"])
            self.assertFalse(verified["fresh_independent_cloud_readback_performed"])
            with self.assertRaisesRegex(ValueError,"historical sandbox Cloud digest"):
                inspect_existing_offline_originals(root,series,"f"*64)
            with self.assertRaisesRegex(ValueError,"historical Cloud reference"):
                inspect_existing_offline_originals(root,series,"invalid")

    def test_existing_witness_tamper_or_other_series_fails_without_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, series = self._existing_original_16_receipts(tmp)
            with self.assertRaisesRegex(ValueError,"unknown originalhost synthetic"):
                inspect_existing_offline_originals(root,"PAPER-V3-CANARY-OTHER")
            w=root/"offline-model-stub-witness.json"
            original=json.loads(w.read_text("utf-8"))
            original["cases"][0]["paper_fill_count"]=0
            w.write_text(json.dumps(original),encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_existing_offline_originals(root,series)

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
