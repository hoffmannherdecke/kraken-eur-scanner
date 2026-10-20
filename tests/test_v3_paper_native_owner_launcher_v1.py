"""Original V3 Paper one native-owner launcher: offline only, never Cloud/model."""

import contextlib
import io
import json
from datetime import datetime, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v3_paper_minipc_native_launcher_v1 as launcher


class SingleNativeOwnerLauncherTests(unittest.TestCase):
    SID = "PAPER-V3-20261017T170000Z"

    def setUp(self):
        # Pin the actual-wall-clock provider only in offline unit tests.
        clock = patch.object(
            launcher, "_originalhost_wall_clock_utc",
            return_value=datetime(2026, 10, 19, 14, 0, 25, tzinfo=timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
    REPO = "a" * 40
    BUNDLE = "b" * 64
    STRATEGY = "c" * 64

    def roots(self, root):
        r = Path(root)
        journal = r / "journal"
        capture = r / "capture"
        budget = r / "budget"
        ackdir = r / "ack"
        for p in (journal, capture, budget, ackdir):
            p.mkdir()
        return journal, capture, budget, ackdir / "v3.json"

    def common(self, root):
        journal, capture, budget, ack = self.roots(root)
        return dict(
            series_id=self.SID, repo_sha=self.REPO,
            bundle_sha256=self.BUNDLE, strategy_sha256=self.STRATEGY,
            journal=journal, capture_dir=capture,
            model_reservations=budget, ack_file=ack,
            read_active_series=lambda _: self.fail(
                "Offline dispatcher must not query Cloud before locked worker"))

    def test_read_only_cli_discloses_gaps_without_start_or_cloud(self):
        buf = io.StringIO()
        with patch("sys.argv", ["launcher", "--read-only"]):
            with contextlib.redirect_stdout(buf):
                self.assertEqual(launcher.main(), 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["status"], "SOURCE_DISPATCH_READY_RUNTIME_NOT_AUTHORIZED")
        self.assertEqual(out["phases"], list(launcher.PHASES))
        for key in ("native_windows_task_installed",
                    "originalhost_source_pins_verified",
                    "independent_six_e2e_proofs_verified",
                    "cloud_cas_performed", "v3_paper_activated",
                    "task_changes", "orders", "real_money_actions"):
            self.assertFalse(out[key])
        self.assertEqual(out["model_http_calls"], 0)
        for args in (["launcher"], ["launcher", "--execute"],
                     ["launcher", "--activate"]):
            with self.subTest(args=args):
                with patch("sys.argv", args), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as err:
                        launcher.main()
                    self.assertEqual(err.exception.code, 2)

    def test_originalhost_readonly_report_never_claims_release(self):
        fixed = {
            "kind": "V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1",
            "checked_at_utc": "2026-10-20T08:00:00Z",
            "filesystem_writes": False,
            "v2r4_changed": False,
            "new_v3_writer_started": False,
            "experimental_paper_release_authorized_by_this_check": False,
            "physical_v3_postcas_local_inventory": {
                "kind": "V3_NATIVE_POSTCAS_LOCAL_INSPECTION_ONLY_V1",
                "status": "NOT_INDEPENDENT_RELEASE_EVIDENCE",
                "native_task_state": "Disabled",
                "native_task_uses_old_readonly_launcher": True,
                "old_intake_tasks_disabled": False,
                "protected_old_aftercare_running": True,
                "live_paper_activation_authorized": False,
                "tasks_changed": 0, "cloud_writes": 0, "model_calls": 0,
            },
        }
        summary = launcher.summarize_originalhost_readonly(fixed)
        self.assertEqual(summary["status"], "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE")
        self.assertTrue(summary["native_task_uses_old_readonly_launcher"])
        self.assertFalse(summary["runtime_bootstrap_executable"])
        self.assertFalse(summary["paper_activated"])
        self.assertFalse(summary["six_original_e2e_proofs_verified"])
        for edits in ({"new_v3_writer_started": True},
                      {"filesystem_writes": True},
                      {"experimental_paper_release_authorized_by_this_check": True}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                launcher.summarize_originalhost_readonly(dict(fixed, **edits))
        local = fixed["physical_v3_postcas_local_inventory"]
        for edits in ({"status": "VERIFIED_PHYSICAL_OR_CLOUD_E2E"},
                      {"live_paper_activation_authorized": True},
                      {"tasks_changed": 1}, {"native_task_state": "FOREIGN"}):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                launcher.summarize_originalhost_readonly(dict(
                    fixed, physical_v3_postcas_local_inventory=dict(local, **edits)))

    def test_originalhost_cli_offline_reuses_one_readonly_script_not_worker(self):
        with patch.object(launcher, "read_originalhost_readonly",
                          return_value={"status": "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE"}) as host, \\
                patch.object(launcher, "dispatch_one_owned_paper_phase") as worker:
            out = io.StringIO()
            with patch("sys.argv", ["launcher", "--originalhost-readonly"]), \\
                    contextlib.redirect_stdout(out):
                self.assertEqual(launcher.main(), 0)
            self.assertEqual(json.loads(out.getvalue())["status"],
                             "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE")
            host.assert_called_once()
            worker.assert_not_called()

    def test_originalhost_physical_probe_unavailable_off_windows(self):
        with patch.object(launcher.sys, "platform", "linux"):
            with self.assertRaisesRegex(ValueError, "physical Windows host"):
                launcher.read_originalhost_readonly()

    def test_first_scanner_dispatches_exact_original_p4_once_without_cloud_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = self.common(tmp)
            candidate = {"entry_origin": "SCANNER", "candidate_id": "ACTUAL_HANDED_OFF"}
            preflight = {"kind": "EXISTING_SOURCE_PREFLIGHT"}
            approval = {"explicit_user_new_budget_approval": True}
            called = []
            with patch.object(launcher, "released_paper_first_scanner_model_once",
                              side_effect=lambda **kw: called.append(kw) or
                              {"status": "OFFLINE_ORIGINAL_DELEGATE"}) as first, patch.object(
                              launcher, "released_paper_followup_tick_once") as follow, patch.object(
                              launcher, "released_paper_cloud_ack_once") as ack:
                out = launcher.dispatch_one_owned_paper_phase(
                    phase="FIRST_SCANNER_MODEL_P4", **common,
                    candidate=candidate, preflight=preflight, approval=approval,
                    model_key="ONLY_A_FAKE_OFFLINE_TEST_API_KEY",
                    source_capture=lambda **_: None,
                    source_acquire=lambda *_: None,
                    model_client=lambda *_: None)
                self.assertEqual(out["status"], "OFFLINE_ORIGINAL_DELEGATE")
                first.assert_called_once()
                follow.assert_not_called()
                ack.assert_not_called()
            self.assertEqual(called[0]["series_id"], self.SID)
            self.assertEqual(called[0]["expected_repo_sha"], self.REPO)
            self.assertIs(called[0]["preflight"], preflight)
            self.assertIs(called[0]["candidate"], candidate)

    def test_followup_dispatches_original_locked_worker_and_forbids_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = self.common(tmp)
            candidate = {"candidate_id": "EXISTING_ORIGINAL"}
            with patch.object(launcher, "released_paper_followup_tick_once",
                              return_value={"status": "SOURCE_ONLY_STUB"}) as follow, patch.object(
                              launcher, "released_paper_first_scanner_model_once") as model, patch.object(
                              launcher, "released_paper_cloud_ack_once") as ack:
                out = launcher.dispatch_one_owned_paper_phase(
                    phase="FOLLOWUP_6H24H72H", candidate=candidate, **common)
                self.assertEqual(out["status"], "SOURCE_ONLY_STUB")
                follow.assert_called_once()
                self.assertIs(follow.call_args.kwargs["candidate"], candidate)
                self.assertIs(follow.call_args.kwargs["ack_file"], common["ack_file"])
                model.assert_not_called()
                ack.assert_not_called()
            with self.assertRaises(ValueError):
                launcher.dispatch_one_owned_paper_phase(
                    phase="FOLLOWUP_6H24H72H", candidate=candidate,
                    model_key="SHOULD_NEVER_SPEND", **common)

    def test_cloud_ack_dispatches_existing_native_lock_and_no_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = self.common(tmp)
            with patch.object(launcher, "released_paper_cloud_ack_once",
                              return_value={"status": "ORIGINAL_ACK_STUB"}) as ack, patch.object(
                              launcher, "released_paper_first_scanner_model_once") as first, patch.object(
                              launcher, "released_paper_followup_tick_once") as follow:
                out = launcher.dispatch_one_owned_paper_phase(
                    phase="CLOUD_RECEIPT_ACK", **common,
                    relay_token="NON_REAL_TOKEN_123456789_TEST_ONLY",
                    cloud_post=lambda *_: None)
                self.assertEqual(out["status"], "ORIGINAL_ACK_STUB")
                ack.assert_called_once()
                self.assertEqual(ack.call_args.kwargs["token"],
                                 "NON_REAL_TOKEN_123456789_TEST_ONLY")
                self.assertEqual(ack.call_args.kwargs["expected_bundle_sha256"],
                                 self.BUNDLE)
                first.assert_not_called()
                follow.assert_not_called()
            with self.assertRaises(ValueError):
                launcher.dispatch_one_owned_paper_phase(
                    phase="CLOUD_RECEIPT_ACK", **common,
                    relay_token="NON_REAL_TOKEN_123456789_TEST_ONLY",
                    candidate={})
            with self.assertRaises(ValueError):
                launcher.dispatch_one_owned_paper_phase(
                    phase="CLOUD_RECEIPT_ACK", **common, relay_token="SHORT")

    def test_foreign_identity_and_unsafe_dirs_fail_before_any_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = self.common(tmp)
            cases = (
                dict(series_id="PAPER-V3-CANARY-FAKE"),
                dict(series_id="PAPER-V2R4-20261009T110135Z"),
                dict(repo_sha="f" * 39),
                dict(bundle_sha256="a" * 63),
                dict(strategy_sha256="g" * 64),
                dict(journal=common["capture_dir"]),
                dict(ack_file=common["journal"] / "journal-is-not-ack.json"),
                dict(read_active_series=None),
            )
            with patch.object(launcher, "released_paper_cloud_ack_once") as ack:
                for mod in cases:
                    with self.subTest(mod=mod):
                        params = dict(common, **mod)
                        with self.assertRaises(ValueError):
                            launcher.dispatch_one_owned_paper_phase(
                                phase="CLOUD_RECEIPT_ACK", **params,
                                relay_token="NON_REAL_TOKEN_123456789_TEST_ONLY")
                ack.assert_not_called()

    def test_unknown_phase_or_missing_real_model_approval_never_calls_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            common = self.common(tmp)
            with patch.object(launcher, "released_paper_first_scanner_model_once") as first:
                for phase in ("ACTIVATE", "INSTALL_TASK", "CAS", ""):
                    with self.assertRaises(ValueError):
                        launcher.dispatch_one_owned_paper_phase(
                            phase=phase, **common)
                for bad in (None, {}, {"status": "NOT_APPROVED"}):
                    with self.subTest(bad=bad):
                        if bad is None:
                            with self.assertRaises(ValueError):
                                launcher.dispatch_one_owned_paper_phase(
                                    phase="FIRST_SCANNER_MODEL_P4", **common,
                                    candidate={}, preflight={},
                                    model_key="FAKE_BUT_NO_AUTHORIZED_BUDGET")
                        else:
                            # The worker owns actual budget policy; dispatcher
                            # may delegate only a real-looking approval object.
                            with self.assertRaises(ValueError):
                                launcher.dispatch_one_owned_paper_phase(
                                    phase="FIRST_SCANNER_MODEL_P4", **common,
                                    candidate={}, preflight={},
                                    approval=None, model_key="FAKE")
                first.assert_not_called()


    def original_release_host(self, series_id, pin):
        # Contract fixture only, not an original Windows receipt.
        return {
            "kind": "V3_NATIVE_ONE_OWNER_POST_CAS_ORIGINALHOST_READBACK_V1",
            "source": "ORIGINAL_MINIPC_WINDOWS_TASK_PROCESS_AND_FENCE",
            "task_name": "CryptoMiniPC-V3PaperSingleWriter",
            "task_state": "Running",
            "series_id": series_id,
            "release_repo_sha": pin,
            "old_candidates_task_state": "Disabled",
            "old_wait_task_state": "Disabled",
            "old_candidates_workers_absent": True,
            "old_wait_workers_absent": True,
            "v3_task_one_original_action_verified": True,
            "v3_worker_pinned_source_verified": True,
            "native_writer_owner_singleton_verified": True,
            "original_no_rearm_fence": "CLOUD_COMMITTED",
            "original_supervisor_no_rearm_ack": True,
            "old_lifecycle_task_running": True,
            "old_cloudsync_task_running": True,
            "independent_cloud_cas_committed": True,
            "six_external_original_e2e_proofs_approved": True,
            "paper_only": True,
            "real_money_actions": False,
            "observed_at_utc": "2026-10-19T14:00:00Z",
        }

    def test_authenticated_host_boundary_connects_exactly_one_existing_phase(self):
        # No worker/HTTP/Cloud/Windows call; delegation is mocked.
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "ORIGINAL_RECEIPT_ONLY"})
            host = self.original_release_host(self.SID, self.REPO)
            original = dict(kwargs)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]) as proofs, patch.object(
                    launcher, "dispatch_one_owned_paper_phase",
                    return_value={"status": "SOURCE_ONLY_MOCK"}) as one:
                result = launcher.dispatch_after_native_release_readback(
                    originalhost_readback=lambda: host,
                    release_root=Path(root), release_packet=packet, **kwargs)
                self.assertEqual(result["status"], "SOURCE_ONLY_MOCK")
                proofs.assert_called_once_with(Path(root), launcher.REVISION, packet)
                one.assert_called_once_with(**original)
            # This seam does not silently modify the CLI or task definition.
            self.assertFalse((Path(root) / "release-proof.json").exists())

    def test_native_seam_fail_closed_on_missing_bad_stale_or_false_originals(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FIRST_SCANNER_MODEL_P4",
                          candidate={"candidate_id": "NOT_ACTUALLY_BOUGHT"})
            good = self.original_release_host(self.SID, self.REPO)
            invalid = [
                {"task_state": "Disabled"},
                {"task_name": "CryptoMiniPC-V2R4PaperWait"},
                {"series_id": "PAPER-V3-20261018T170000Z"},
                {"release_repo_sha": "d" * 40},
                {"old_wait_task_state": "Running"},
                {"old_candidates_workers_absent": False},
                {"old_wait_workers_absent": False},
                {"v3_task_one_original_action_verified": False},
                {"v3_worker_pinned_source_verified": False},
                {"native_writer_owner_singleton_verified": False},
                {"original_no_rearm_fence": "QUIESCED"},
                {"original_supervisor_no_rearm_ack": False},
                {"old_lifecycle_task_running": False},
                {"old_cloudsync_task_running": False},
                {"independent_cloud_cas_committed": False},
                {"six_external_original_e2e_proofs_approved": False},
                {"paper_only": False},
                {"real_money_actions": True},
                {"observed_at_utc": "2026-10-19T13:58:00Z"},
                {"observed_at_utc": "2026-10-19T14:01:00Z"},
                {"observed_at_utc": "2026-10-19T14:00:00"},
                {"observed_at_utc": "NOT-A-TIMESTAMP"},
            ]
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaises(ValueError):
                    launcher.dispatch_after_native_release_readback(**kwargs)
                with self.assertRaises(ValueError):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: None,
                        release_root=Path(root), release_packet=packet, **kwargs)
                for edits in invalid:
                    with self.subTest(edits=edits):
                        row = dict(good, **edits)
                        with self.assertRaises(ValueError):
                            launcher.dispatch_after_native_release_readback(
                                originalhost_readback=lambda r=row: r,
                                release_root=Path(root), release_packet=packet,
                                **kwargs)
                worker.assert_not_called()

    def test_native_release_clock_is_real_and_cannot_be_injected(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "OFFLINE_ONLY"})
            host = self.original_release_host(self.SID, self.REPO)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                # A client-supplied clock cannot make a prior host report fresh.
                with self.assertRaisesRegex(ValueError, "injected clock override"):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: host,
                        release_root=Path(root), release_packet=packet,
                        clock_now=lambda: "2026-10-19T14:00:25Z", **kwargs)
                # Even a release packet with mocked six proofs cannot make
                # yesterday's host readback pass the actual wall clock.
                with patch.object(
                        launcher, "_originalhost_wall_clock_utc",
                        return_value=datetime(2026, 10, 20, 14, 0, 25,
                                              tzinfo=timezone.utc)):
                    with self.assertRaisesRegex(ValueError, "stale or future"):
                        launcher.dispatch_after_native_release_readback(
                            originalhost_readback=lambda: host,
                            release_root=Path(root), release_packet=packet,
                            **kwargs)
                worker.assert_not_called()

    def test_six_proof_release_envelopes_mandatory_before_originalhost_or_worker(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H")
            host = self.original_release_host(self.SID, self.REPO)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            with patch.object(launcher, "dispatch_one_owned_paper_phase") as worker:
                # A forged trusted-looking originalhost dict is insufficient.
                with self.assertRaisesRegex(ValueError, "release evidence missing"):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: host, **kwargs)
                # A syntactically reasonable yet unsupported six-proof packet
                # is independently refused by the existing real release gate.
                with self.assertRaisesRegex(ValueError, "envelopes incomplete"):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: host,
                        release_root=Path(root), release_packet=packet, **kwargs)
                # Even a mocked host cannot override an explicit proof blocker.
                with patch.object(launcher, "validate_experimental_paper_packet",
                                  return_value=["original cloud SHA missing"]):
                    with self.assertRaisesRegex(ValueError, "cloud SHA missing"):
                        launcher.dispatch_after_native_release_readback(
                            originalhost_readback=lambda: host,
                            release_root=Path(root), release_packet=packet, **kwargs)
                worker.assert_not_called()

    def test_wrong_revision_strategy_or_root_never_hits_six_proof_gate(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="CLOUD_RECEIPT_ACK")
            host = self.original_release_host(self.SID, self.REPO)
            good = {"strategy_revision": launcher.REVISION,
                    "strategy_fingerprint_sha256": self.STRATEGY}
            bad = [dict(good, strategy_revision="V3-FOREIGN"),
                   dict(good, strategy_fingerprint_sha256="0" * 64)]
            with patch.object(launcher, "validate_experimental_paper_packet") as gate, \
                    patch.object(launcher, "dispatch_one_owned_paper_phase") as worker:
                for packet in bad:
                    with self.assertRaisesRegex(ValueError, "evidence missing"):
                        launcher.dispatch_after_native_release_readback(
                            originalhost_readback=lambda: host,
                            release_root=Path(root), release_packet=packet, **kwargs)
                with self.assertRaisesRegex(ValueError, "evidence missing"):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: host,
                        release_root=Path(root) / "DOES_NOT_EXIST",
                        release_packet=good, **kwargs)
                gate.assert_not_called()
                worker.assert_not_called()

    def test_native_seam_never_activates_on_invalid_local_release_paths(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="CLOUD_RECEIPT_ACK")
            kwargs["journal"] = kwargs["capture_dir"]
            with patch.object(launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaises(ValueError):
                    launcher.dispatch_after_native_release_readback(
                        originalhost_readback=lambda: self.original_release_host(
                            self.SID, self.REPO), **kwargs)
                worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
