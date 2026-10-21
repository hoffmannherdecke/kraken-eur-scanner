"""Original V3 Paper one native-owner launcher: offline only, never Cloud/model."""

import contextlib
import hashlib
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
        # The original Windows PowerShell probe must be a child of the
        # launcher process whose PID appears in the offline CIM fixture.
        # These mocked PIDs are NEVER host attestation.
        native_pid = patch.object(launcher.os, "getpid", return_value=21704)
        native_pid.start()
        self.addCleanup(native_pid.stop)
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

    @staticmethod
    def correlated_originalhost(timestamp="2026-10-19T14:00:10Z", **overrides):
        # Offline fixture ONLY: no actual Windows/SYSTEM/loaded PID evidence.
        local_sha = hashlib.sha256(Path(launcher.__file__).read_bytes()).hexdigest()
        report = {
            "status": "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE",
            "native_task_state": "Running",
            "native_task_uses_old_readonly_launcher": False,
            "native_python_parent_process_observed": True,
            "native_python_parent_matches_task_action_hint": True,
            "native_python_parent_pid": 21704,
            "native_python_parent_started_at_utc": "2026-10-19T13:40:00Z",
            "native_powershell_process_token_is_system": True,
            "native_task_action_sha256": "a" * 64,
            "native_task_launcher_file_sha256": local_sha,
            "observed_at_utc": timestamp,
        }
        report.update(overrides)
        return report

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


    def test_one_shot_readonly_source_acceptance_reuses_exact_stage_pins(self):
        # A checked SHA is only an observed staged FILE identity, not a
        # physical loaded-module/OS-owner/E2E/Cloud CAS release credential.
        host = self.correlated_originalhost()
        with patch.object(launcher, "_require_staged_v3_source_manifest") as stage, patch.object(
                launcher, "read_originalhost_readonly", return_value=host
                ) as original, patch.object(
                launcher, "read_active_paper_series") as cloud, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            out = launcher.preflight_native_windows_one_shot(
                expected_repo_sha=self.REPO)
            stage.assert_called_once_with(repo_sha=self.REPO)
            original.assert_called_once_with()
            self.assertTrue(out["staged_source_manifest_sha256_rechecked_read_only"])
            self.assertTrue(out["staged_source_sha_is_only_local_source_identity"])
            self.assertFalse(out["actual_loaded_python_bytecode_independently_verified"])
            self.assertFalse(out["v3_paper_activated"])
            self.assertEqual(out["model_http_calls"], 0)
            cloud.assert_not_called()
            worker.assert_not_called()

    def test_one_shot_source_preflight_blocks_bad_pins_before_any_host_probe(self):
        with patch.object(launcher, "_require_staged_v3_source_manifest",
                          side_effect=ValueError("native staged source byte drift")), patch.object(
                launcher, "read_originalhost_readonly") as original, patch.object(
                launcher, "read_active_paper_series") as cloud, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError, "byte drift"):
                launcher.preflight_native_windows_one_shot(
                    expected_repo_sha=self.REPO)
            original.assert_not_called()
            cloud.assert_not_called()
            worker.assert_not_called()

    def test_native_source_readonly_cli_rejects_other_modes_and_no_worker(self):
        for args in (["launcher", "--read-only", "--expected-source-sha", self.REPO],
                     ["launcher", "--originalhost-readonly",
                      "--expected-source-sha", self.REPO]):
            with self.subTest(args=args), patch("sys.argv", args):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        launcher.main()
                self.assertEqual(exc.exception.code, 2)
        with patch("sys.argv", ["launcher", "--one-shot-preflight",
                                "--expected-source-sha", self.REPO]), patch.object(
                launcher, "_require_staged_v3_source_manifest") as stage, patch.object(
                launcher, "read_originalhost_readonly",
                return_value=self.correlated_originalhost()), patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(launcher.main(), 0)
            out = json.loads(buffer.getvalue())
            self.assertTrue(out["staged_source_manifest_sha256_rechecked_read_only"])
            self.assertFalse(out["independent_task_pid_and_source_ack"])
            self.assertFalse(out["six_real_technical_e2e_proofs_accepted"])
            self.assertFalse(out["actual_v3_cloud_cas_committed"])
            stage.assert_called_once_with(repo_sha=self.REPO)
            worker.assert_not_called()

    def test_real_windows_one_shot_preflight_is_diagnostic_not_live(self):
        original = {
            "kind": "V3_NATIVE_ORIGINALHOST_DIAGNOSTIC_HANDOFF_V1",
            "status": "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE",
            "native_task_state": "Disabled",
            "paper_activated": False,
        }
        with patch.object(launcher, "read_originalhost_readonly",
                          return_value=original) as inventory, patch.object(
                          launcher, "dispatch_one_owned_paper_phase") as worker, patch.object(
                          launcher, "read_active_paper_series") as cloud:
            buf = io.StringIO()
            with patch("sys.argv", ["launcher", "--one-shot-preflight"]):
                with contextlib.redirect_stdout(buf):
                    self.assertEqual(launcher.main(), 0)
            result = json.loads(buf.getvalue())
            inventory.assert_called_once_with()
            worker.assert_not_called()
            cloud.assert_not_called()
        self.assertEqual(result["kind"], "V3_NATIVE_WINDOWS_ONE_SHOT_PREFLIGHT_V1")
        self.assertEqual(result["status"],
                         "BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE")
        self.assertEqual(result["diagnostic"], original)
        self.assertEqual(result["phase_names"], list(launcher.PHASES))
        self.assertEqual(result["existing_native_release_entrypoint"],
                         "dispatch_after_originalhost_and_cloud_readback")
        for flag in ("premaintenance_activation_allowed",
                     "independent_task_pid_and_source_ack",
                     "six_real_technical_e2e_proofs_accepted",
                     "physical_maintenance_and_script_ack_accepted",
                     "actual_v3_cloud_cas_committed",
                     "one_shot_worker_invoked", "windows_task_changes",
                     "v2r4_changed", "v3_paper_activated", "orders",
                     "real_money_actions"):
            self.assertIs(result[flag], False, flag)
        self.assertEqual(result["model_http_calls"], 0)
        self.assertEqual(result["cloud_writes"], 0)

    def test_one_shot_preflight_joins_exact_originalhost_and_relay_without_release(self):
        series = "PAPER-V3-20261020T090000Z"
        report = self.correlated_originalhost()
        reply = {"series_id": series, "status": "active",
                 "strategy_revision": launcher.REVISION,
                 "observed_at_utc": "2026-10-19T14:00:20Z",
                 "config": {"untrusted_secret": "NEVER_DISCLOSE"}}
        token = "ONLY_FOR_LOCAL_OFFLINE_RELAY_TEST_NOT_REAL"
        with patch.dict(launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": token}), patch.object(
                launcher, "read_originalhost_readonly", return_value=report) as host, patch.object(
                launcher, "read_active_paper_series", return_value=reply) as cloud, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            buf = io.StringIO()
            with patch("sys.argv", ["launcher", "--one-shot-preflight",
                                   "--proposed-v3-series", series]), contextlib.redirect_stdout(buf):
                self.assertEqual(launcher.main(), 0)
            host.assert_called_once_with()
            cloud.assert_called_once_with(series_id=series, token=token)
            worker.assert_not_called()
        text = buf.getvalue()
        self.assertNotIn(token, text)
        self.assertNotIn("NEVER_DISCLOSE", text)
        result = json.loads(text)
        self.assertTrue(result["cloud_readback_requested"])
        self.assertTrue(result["originalhost_task_process_source_correlated_read_only"])
        self.assertEqual(result["diagnostic"], report)
        self.assertEqual(result["cloud_readonly_observation"]["series_id"], series)
        self.assertTrue(result["cloud_readonly_observation"]["temporal_pair_checked_read_only"])
        self.assertFalse(result["cloud_readonly_observation"]["cloud_cas_independently_proven"])
        self.assertEqual(result["status"],
                         "BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE")
        self.assertFalse(result["one_shot_worker_invoked"])
        self.assertFalse(result["v3_paper_activated"])
        self.assertFalse(result["actual_v3_cloud_cas_committed"])
        self.assertEqual(result["model_http_calls"], 0)
        self.assertEqual(result["cloud_writes"], 0)

    def test_proposed_series_wrong_or_missing_relay_token_blocks_every_worker(self):
        valid = "PAPER-V3-20261020T090000Z"
        with patch.object(launcher, "read_originalhost_readonly",
                          return_value=self.correlated_originalhost()) as host, patch.object(
                          launcher, "read_active_paper_series") as relay, patch.object(
                          launcher, "dispatch_one_owned_paper_phase") as worker, patch.dict(
                          launcher.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "exact non-CANARY"):
                launcher.preflight_native_windows_one_shot(proposed_v3_series="CANARY")
            host.assert_not_called()
            with self.assertRaisesRegex(ValueError, "credential unavailable"):
                launcher.preflight_native_windows_one_shot(proposed_v3_series=valid)
            relay.assert_not_called()
            worker.assert_not_called()


    def test_one_shot_rejects_stale_or_future_host_before_cloud_request(self):
        series = "PAPER-V3-20261020T090000Z"
        for observed in ("2026-10-19T13:56:00Z",
                         "2026-10-19T14:00:50Z",
                         "2026-10-19T14:00:10",
                         "not-a-timestamp", None):
            with self.subTest(observed=observed), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=self.correlated_originalhost(observed)), patch.object(
                    launcher, "read_active_paper_series") as relay, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaises(ValueError):
                    launcher.preflight_native_windows_one_shot(
                        proposed_v3_series=series)
                relay.assert_not_called()
                worker.assert_not_called()

    def test_one_shot_cloud_timestamp_denied_when_stale_naive_or_future(self):
        series = "PAPER-V3-20261020T090000Z"
        valid_host = self.correlated_originalhost()
        for observed in ("2026-10-19T13:56:00Z",
                         "2026-10-19T14:00:50Z",
                         "2026-10-19T14:00:10",
                         "garbled"):
            cloud = {"series_id": series, "status": "active",
                     "strategy_revision": launcher.REVISION,
                     "observed_at_utc": observed}
            with self.subTest(observed=observed), patch.dict(
                    launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": "R"*32}), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=valid_host), patch.object(
                    launcher, "read_active_paper_series", return_value=cloud), patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaises(ValueError):
                    launcher.preflight_native_windows_one_shot(
                        proposed_v3_series=series)
                worker.assert_not_called()

    def test_one_shot_rejects_two_individually_fresh_but_uncorrelated_clocks(self):
        # Each sample is less than 180s old at the fixed test clock,
        # but separated by 184s; a coincidental match cannot become an ACK.
        series = "PAPER-V3-20261020T090000Z"
        host = self.correlated_originalhost("2026-10-19T13:57:26Z")
        reply = {"series_id": series, "status": "active",
                 "strategy_revision": launcher.REVISION,
                 "observed_at_utc": "2026-10-19T14:00:30Z"}
        with patch.dict(launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": "R"*32}), patch.object(
                launcher, "read_originalhost_readonly", return_value=host), patch.object(
                launcher, "read_active_paper_series", return_value=reply) as relay, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError, "do not correlate"):
                launcher.preflight_native_windows_one_shot(
                    proposed_v3_series=series)
            relay.assert_called_once()
            worker.assert_not_called()

    def test_slow_cloud_relay_cannot_reuse_host_snapshot_that_aged_out(self):
        # At entry the host report is only 15 seconds old. During the
        # authenticated relay call real time advances; the Cloud result
        # and the host are mutually within 180s, and Cloud is still fresh,
        # but the HOST is now 190s old. PR467's pre-relay-only host check
        # must not incorrectly accept this as a current paired observation.
        series = "PAPER-V3-20261020T090000Z"
        report = self.correlated_originalhost()
        reply = {"series_id": series, "status": "active",
                 "strategy_revision": launcher.REVISION,
                 "observed_at_utc": "2026-10-19T14:01:30Z"}
        before = datetime(2026, 10, 19, 14, 0, 25, tzinfo=timezone.utc)
        after = datetime(2026, 10, 19, 14, 3, 20, tzinfo=timezone.utc)
        with patch.dict(launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": "R"*32}), patch.object(
                launcher, "read_originalhost_readonly", return_value=report), patch.object(
                launcher, "read_active_paper_series", return_value=reply) as cloud, patch.object(
                launcher, "_originalhost_wall_clock_utc",
                side_effect=[before, after]) as clock, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError, "originalhost post-relay"):
                launcher.preflight_native_windows_one_shot(
                    proposed_v3_series=series)
            cloud.assert_called_once_with(series_id=series, token="R"*32)
            self.assertEqual(clock.call_count, 2)
            worker.assert_not_called()

    def test_paired_cloud_preflight_requires_running_real_task_source_hints(self):
        series = "PAPER-V3-20261020T090000Z"
        invalid = (
            {"native_task_state": "Disabled"},
            {"native_task_uses_old_readonly_launcher": True},
            {"native_python_parent_process_observed": False},
            {"native_python_parent_matches_task_action_hint": False},
            {"native_powershell_process_token_is_system": False},
            {"native_powershell_process_token_is_system": 1},
            {"native_task_action_sha256": None},
            {"native_task_action_sha256": "f" * 63},
            {"native_task_launcher_file_sha256": "b" * 64},
            {"status": "RELEASE_APPROVED"},
        )
        for fields in invalid:
            with self.subTest(fields=fields), patch.dict(
                    launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": "R"*32}), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=self.correlated_originalhost(**fields)), patch.object(
                    launcher, "read_active_paper_series") as cloud, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaisesRegex(ValueError, "Task/PID/source"):
                    launcher.preflight_native_windows_one_shot(
                        proposed_v3_series=series)
                cloud.assert_not_called()
                worker.assert_not_called()

    def test_native_windows_binding_uses_one_actual_imported_core_source_root(self):
        # Positive source-only observation, NOT external loaded-bytecode proof.
        launcher._require_one_loaded_release_module_root()

    def test_native_windows_binding_blocks_mixed_imported_module_origins(self):
        actual = launcher.sys.modules["paper_evaluator.v3_paper_minipc_selective_tick_v1"]
        origin = actual.__spec__.origin
        for modpath, modorigin in (
                (str(Path(origin).with_name("incorrect_checkout.py")), origin),
                (actual.__file__, str(Path(origin).with_name("wrong_import_spec.py")))):
            with self.subTest(path=modpath, origin=modorigin), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    actual, "__file__", modpath), patch.object(
                    actual.__spec__, "origin", modorigin), patch.object(
                    launcher, "read_originalhost_readonly") as inspector, patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback") as owner:
                with self.assertRaisesRegex(ValueError, "mixed-vintage"):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: {},
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID)
                inspector.assert_not_called()
                owner.assert_not_called()

    def test_native_windows_binding_blocks_missing_core_module_source(self):
        name = "tools.v3_experimental_paper_technical_gate"
        original = launcher.sys.modules[name]
        with patch.object(launcher.sys, "platform", "win32"), patch.dict(
                launcher.sys.modules, {name: None}), patch.object(
                launcher, "read_originalhost_readonly") as inspector, patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback") as owner:
            with self.assertRaisesRegex(ValueError, "source unavailable"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda: {},
                    phase="FOLLOWUP_6H24H72H", series_id=self.SID)
            inspector.assert_not_called()
            owner.assert_not_called()
        self.assertIs(launcher.sys.modules[name], original)

    def test_native_windows_phase_binding_stops_before_inspector_without_real_owner(self):
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher, "read_originalhost_readonly") as inspector, patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback") as owner:
            with self.assertRaisesRegex(ValueError, "owner unavailable"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=None)
            inspector.assert_not_called()
            owner.assert_not_called()
        with patch.object(launcher.sys, "platform", "linux"), patch.object(
                launcher, "read_originalhost_readonly") as inspector:
            with self.assertRaisesRegex(ValueError, "original Windows host"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda: {})
            inspector.assert_not_called()

    def test_native_windows_phase_binding_rejects_old_task_and_false_owner(self):
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=self.correlated_originalhost(
                    native_task_state="Disabled")) as inspector, patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback") as owner:
            with self.assertRaisesRegex(ValueError, "Task/PID/source"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda: {
                        "six_external_original_e2e_proofs_approved": True},
                    phase="FOLLOWUP_6H24H72H", series_id=self.SID)
            inspector.assert_called_once()
            owner.assert_not_called()

    def test_native_windows_phase_binding_reuses_exact_original_dispatcher(self):
        # An offline mock of a real release owner is NOT a physical E2E proof.
        # Two offline synthetic observations only: not physical attestation.
        host = self.correlated_originalhost()
        external = {
            "observed_at_utc": "2026-10-19T14:00:16Z",
            "native_task_action_sha256": host["native_task_action_sha256"],
            "native_task_launcher_file_sha256":
                host["native_task_launcher_file_sha256"],
            "native_python_parent_pid": host["native_python_parent_pid"],
            "native_python_parent_started_at_utc":
                host["native_python_parent_started_at_utc"],
        }
        calls = []
        def physical_provider():
            calls.append(1)
            return dict(external)
        def delegated(**kwargs):
            # The one original dispatcher obtains the same independent
            # release-owner callback, not the unauthoritative host inventory.
            got = kwargs["originalhost_readback"]()
            self.assertEqual(got, external)
            return {"status": "OFFLINE_DELEGATED_NO_WORKER"}
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=host) as inspector, patch.object(
                launcher, "_require_staged_v3_source_manifest") as stage_pin, patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback",
                side_effect=delegated) as owner, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            result=launcher.dispatch_from_original_windows_one_shot(
                originalhost_release_readback=physical_provider,
                release_root=Path("offline-only"), release_packet={},
                original_cloud_relay_token="OFFLINE_TOKEN_NO_NETWORK_123456",
                phase="FOLLOWUP_6H24H72H", series_id=self.SID,
                repo_sha=self.REPO)
            self.assertEqual(result["status"], "OFFLINE_DELEGATED_NO_WORKER")
            stage_pin.assert_called_once_with(repo_sha=self.REPO)
            inspector.assert_called_once_with()
            owner.assert_called_once()
            params=owner.call_args.kwargs
            self.assertTrue(callable(params["originalhost_readback"]))
            self.assertEqual(params["phase"], "FOLLOWUP_6H24H72H")
            self.assertEqual(params["series_id"], self.SID)
            self.assertEqual(calls, [1])
            worker.assert_not_called()

    def test_native_windows_process_cannot_borrow_another_valid_task_parent(self):
        # Both source fingerprints, Task state, inspected SYSTEM parent and
        # external release-owner callback could look valid for DIFFERENT
        # Python process 21704. Our actual native launcher is PID 21705.
        # The original host PowerShell child is not its own child, so refuse
        # the attempt before independent owner/Cloud or any Paper worker.
        host = self.correlated_originalhost()
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher.os, "getpid", return_value=21705), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=host) as inspector, patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback"
                ) as dispatcher, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError,
                                        "inspector parent is not invoking Python"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda:
                        self.fail("wrong OS parent may not request owner receipt"),
                    release_root=Path("offline-only"),
                    phase="FOLLOWUP_6H24H72H", series_id=self.SID)
            inspector.assert_called_once()
            dispatcher.assert_not_called()
            worker.assert_not_called()

    def test_native_windows_release_must_match_original_task_and_launcher_hashes(self):
        host = self.correlated_originalhost()
        expected = dict(
            observed_at_utc="2026-10-19T14:00:16Z",
            native_task_action_sha256=host["native_task_action_sha256"],
            native_task_launcher_file_sha256=host["native_task_launcher_file_sha256"],
            native_python_parent_pid=host["native_python_parent_pid"],
            native_python_parent_started_at_utc=host["native_python_parent_started_at_utc"])
        changes = (
            {"native_task_action_sha256": "d"*64},
            {"native_task_launcher_file_sha256": "e"*64},
            {"native_task_action_sha256": None},
            {"native_task_launcher_file_sha256": "BAD"},
        )
        for change in changes:
            external = dict(expected, **change)
            with self.subTest(change=change), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=host), patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback"
                    ) as dispatcher, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                def evaluate_adapter(**kwargs):
                    return kwargs["originalhost_readback"]()
                dispatcher.side_effect = evaluate_adapter
                with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: external,
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID)
                dispatcher.assert_called_once()
                worker.assert_not_called()

    def test_native_windows_release_requires_fresh_independent_pair(self):
        host = self.correlated_originalhost()
        aligned = dict(
            native_task_action_sha256=host["native_task_action_sha256"],
            native_task_launcher_file_sha256=host["native_task_launcher_file_sha256"],
            native_python_parent_pid=host["native_python_parent_pid"],
            native_python_parent_started_at_utc=host["native_python_parent_started_at_utc"])
        for obs in ("2026-10-19T14:02:00Z", None, "bad-time"):
            with self.subTest(obs=obs), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=host), patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback"
                    ) as owner, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                owner.side_effect = lambda **kw: kw["originalhost_readback"]()
                with self.assertRaises(ValueError):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: dict(aligned,
                            observed_at_utc=obs),
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID)
                worker.assert_not_called()

    def test_native_windows_release_rejects_pid_reuse_and_birth_mismatch(self):
        host = self.correlated_originalhost()
        original = {
            "observed_at_utc": "2026-10-19T14:00:16Z",
            "native_task_action_sha256": host["native_task_action_sha256"],
            "native_task_launcher_file_sha256": host["native_task_launcher_file_sha256"],
            "native_python_parent_pid": host["native_python_parent_pid"],
            "native_python_parent_started_at_utc": host["native_python_parent_started_at_utc"],
        }
        changed_cases = (
            {"native_python_parent_pid": 21705},
            {"native_python_parent_started_at_utc": "2026-10-19T13:40:01Z"},
            {"native_python_parent_pid": True},
            {"native_python_parent_pid": None},
            {"native_python_parent_started_at_utc": "invalid"},
            {"native_python_parent_started_at_utc": "2026-10-19T13:40:00"},
        )
        for changed in changed_cases:
            with self.subTest(changed=changed), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=host), patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback"
                    ) as delegate, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                delegate.side_effect = lambda **kw: kw["originalhost_readback"]()
                with self.assertRaises(ValueError):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: dict(original, **changed),
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID)
                delegate.assert_called_once()
                worker.assert_not_called()

    def test_native_windows_release_rejects_missing_local_pid_birth(self):
        for mutation in (
            {"native_python_parent_pid": None},
            {"native_python_parent_pid": False},
            {"native_python_parent_started_at_utc": "bad"},
        ):
            with self.subTest(mutation=mutation), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    launcher, "read_originalhost_readonly",
                    return_value=self.correlated_originalhost(**mutation)), patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback"
                    ) as owner, patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                with self.assertRaisesRegex(ValueError, "Task/PID/source"):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: {},
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID)
                owner.assert_not_called()
                worker.assert_not_called()

    def test_existing_windows_inventory_process_birth_is_rechecked(self):
        original = Path(launcher.__file__).resolve().parent.parent
        source = (original / "tools" /
                  "check-minipc-v3-physical-writer-readiness.ps1").read_text("utf-8")
        for text in (
            "native_python_parent_pid=$parentId",
            "native_python_parent_started_at_utc=$parentBorn.ToString('o')",
            "$freshParent=@(Get-CimInstance Win32_Process",
            "$stableParent", "native_runtime_identity_independently_verified=$false"):
            self.assertIn(text, source)

    def test_native_windows_release_rejects_stale_local_task_before_owner(self):
        report = self.correlated_originalhost("2026-10-19T13:58:00Z")
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=report), patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback"
                ) as owner, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError, "original Windows Task"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda: {},
                    phase="FOLLOWUP_6H24H72H", series_id=self.SID)
            owner.assert_not_called()
            worker.assert_not_called()

    def test_native_windows_binding_rejects_injected_cloud_before_inspector(self):
        for injected in ("read_active_series", "clock_now", "cloud_post",
                         "model_client", "source_acquire", "source_ticker"):
            with self.subTest(injected=injected), patch.object(
                    launcher.sys, "platform", "win32"), patch.object(
                    launcher, "read_originalhost_readonly") as inspector, patch.object(
                    launcher, "dispatch_after_originalhost_and_cloud_readback") as owner:
                with self.assertRaisesRegex(ValueError, "injected source"):
                    launcher.dispatch_from_original_windows_one_shot(
                        originalhost_release_readback=lambda: {},
                        phase="FOLLOWUP_6H24H72H", series_id=self.SID,
                        **{injected: object()})
                inspector.assert_not_called()
                owner.assert_not_called()

    def test_one_shot_host_only_mode_has_no_new_clock_gate(self):
        # Pre-maintenance V2R4 diagnostics must remain usable even with
        # historic/absent timestamps; no relay is requested in this mode.
        with patch.object(launcher, "read_originalhost_readonly",
                          return_value={"observed_at_utc": None}) as host, patch.object(
                          launcher, "read_active_paper_series") as relay:
            report = launcher.preflight_native_windows_one_shot()
            host.assert_called_once_with()
            relay.assert_not_called()
            self.assertIsNone(report["cloud_readonly_observation"])
            self.assertEqual(report["status"],
                             "BLOCKED_PENDING_MAINTENANCE_AND_ORIGINAL_RELEASE")

    def test_unavailable_or_wrong_relay_series_fails_without_paper_release(self):
        valid = "PAPER-V3-20261020T090000Z"
        with patch.dict(launcher.os.environ, {"V3_PAPER_RELAY_TOKEN": "R"*32}), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=self.correlated_originalhost()), patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with patch.object(launcher, "read_active_paper_series",
                              side_effect=ValueError("Cloud has no active V3 series")):
                with self.assertRaisesRegex(ValueError, "no active V3"):
                    launcher.preflight_native_windows_one_shot(proposed_v3_series=valid)
            with patch.object(launcher, "read_active_paper_series",
                              return_value={"series_id": "PAPER-V3-20261020T100000Z",
                                            "status": "active",
                                            "strategy_revision": launcher.REVISION,
                                            "observed_at_utc": "2026-10-20T09:00:00Z"}):
                with self.assertRaisesRegex(ValueError, "exact authenticated"):
                    launcher.preflight_native_windows_one_shot(proposed_v3_series=valid)
            worker.assert_not_called()

    def test_proposed_cloud_series_forbidden_without_one_shot_host_preflight(self):
        with patch("sys.argv", ["launcher", "--read-only", "--proposed-v3-series",
                               "PAPER-V3-20261020T090000Z"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stop:
                    launcher.main()
        self.assertEqual(stop.exception.code, 2)

    def test_one_shot_preflight_propagates_missing_original_host_not_false_success(self):
        with patch.object(launcher, "read_originalhost_readonly",
                          side_effect=ValueError("physical host missing")), patch.object(
                          launcher, "dispatch_one_owned_paper_phase") as worker:
            with patch("sys.argv", ["launcher", "--one-shot-preflight"]):
                with self.assertRaisesRegex(ValueError, "physical host missing"):
                    launcher.main()
            worker.assert_not_called()

    def test_physical_inventory_powershell_execution_policy_is_process_local(self):
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher.Path, "is_file", return_value=True), patch.object(
                launcher.Path, "is_symlink", return_value=False), patch.object(
                launcher.subprocess, "run") as call:
            report = {
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
                    "live_paper_activation_authorized": False,
                    "tasks_changed": 0, "cloud_writes": 0, "model_calls": 0
                }
            }
            call.return_value.returncode = 0
            call.return_value.stdout = json.dumps(report)
            result = launcher.read_originalhost_readonly()
            self.assertEqual(result["status"], "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE")
            args = call.call_args.args[0]
            self.assertEqual(args[1:5],
                ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"])
            self.assertEqual(args[5], "-File")
            self.assertEqual(args[-2:], ["-TradingRoot",
                                         launcher.ORIGINALHOST_TRADING_ROOT])
            self.assertEqual(call.call_args.kwargs["timeout"], 90)
            self.assertFalse(call.call_args.kwargs["check"])

    def test_native_phase_uses_original_cloud_readback_inside_worker(self):
        with tempfile.TemporaryDirectory() as root:
            common = self.common(root)
            common.pop("read_active_series")
            kwargs = dict(common, phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "ORIGINAL_ONLY"})
            original = self.original_release_host(self.SID, self.REPO)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            cloud = {"series_id": self.SID, "status": "active", "config": {}}
            token = "OFFLINE_ONLY_NOT_A_REAL_SECRET_12345678"
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "read_active_paper_series", return_value=cloud) as relay, \
                    patch.object(launcher, "dispatch_one_owned_paper_phase") as phase:
                def single_phase(**parameters):
                    return parameters["read_active_series"](self.SID)
                phase.side_effect = single_phase
                result = launcher.dispatch_after_originalhost_and_cloud_readback(
                    originalhost_readback=lambda: original,
                    release_root=Path(root), release_packet=packet,
                    original_cloud_relay_token=token, **kwargs)
                self.assertEqual(result, cloud)
                relay.assert_called_once_with(series_id=self.SID, token=token)
                phase.assert_called_once()
                args = phase.call_args.kwargs
                self.assertIsNone(args.get("relay_token"))
                self.assertEqual(args["phase"], "FOLLOWUP_6H24H72H")

    def test_native_phase_rechecks_host_after_slow_cloud_relay_inside_lock(self):
        # Real native boundary, mocked Cloud/phase only. Host is fresh at the
        # original independent native release check (25s) but after the one
        # Cloud request it is 105s old. This must fail before any phase body.
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "OFFLINE_NATIVE_ONLY"})
            kwargs.pop("read_active_series")
            host = self.original_release_host(self.SID, self.REPO)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            first = datetime(2026, 10, 19, 14, 0, 25, tzinfo=timezone.utc)
            after = datetime(2026, 10, 19, 14, 1, 45, tzinfo=timezone.utc)
            cloud = {"series_id": self.SID, "status": "active",
                     "observed_at_utc": "2026-10-19T14:01:44Z",
                     "config": {}}
            token = "OFFLINE_ONLY_NOT_A_REAL_SECRET_12345678"
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "_originalhost_wall_clock_utc",
                    side_effect=[first, after]) as clock, patch.object(
                    launcher, "read_active_paper_series", return_value=cloud) as relay, \
                    patch.object(launcher, "dispatch_one_owned_paper_phase") as phase:
                def locked_phase(**parameters):
                    parameters["read_active_series"](self.SID)
                    self.fail("stale host would have reached the Paper phase")
                phase.side_effect = locked_phase
                with self.assertRaisesRegex(ValueError, "stale after Cloud relay"):
                    launcher.dispatch_after_originalhost_and_cloud_readback(
                        originalhost_readback=lambda: host,
                        release_root=Path(root), release_packet=packet,
                        original_cloud_relay_token=token, **kwargs)
                relay.assert_called_once_with(series_id=self.SID, token=token)
                self.assertEqual(clock.call_count, 2)
                phase.assert_called_once()

    def test_native_cloud_callback_cannot_run_without_native_host_readback(self):
        # A mocked native caller cannot skip the physical host gate and then
        # use the authenticated relay callback to mint a release.
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "NO_HOST"})
            kwargs.pop("read_active_series")
            with patch.object(launcher, "dispatch_after_native_release_readback"
                              ) as native, patch.object(
                              launcher, "read_active_paper_series") as relay:
                def skip_host(**forwarded):
                    return forwarded["read_active_series"](self.SID)
                native.side_effect = skip_host
                with self.assertRaisesRegex(ValueError, "originalhost release missing"):
                    launcher.dispatch_after_originalhost_and_cloud_readback(
                        originalhost_readback=lambda: {},
                        release_root=Path(root), release_packet={},
                        original_cloud_relay_token="OFFLINE_ONLY_1234567890_1234567890",
                        **kwargs)
                relay.assert_not_called()

    def test_native_original_cloud_adapter_rejects_injected_transport(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FIRST_SCANNER_MODEL_P4",
                          candidate={})
            kwargs.pop("read_active_series")
            token = "FAKE_MODELLESS_TEST_ONLY_TOKEN_123456"
            with patch.object(launcher, "dispatch_after_native_release_readback") as owner, \
                    patch.object(launcher, "read_active_paper_series") as relay:
                for field, value in (
                    ("read_active_series", lambda sid: {}),
                    ("cloud_post", lambda *_: {}),
                    ("relay_token", "different"),
                    ("clock_now", lambda: "2026-10-19T14:00:00Z"),
                    ("model_client", lambda **_: None),
                    ("source_capture", lambda **_: None),
                    ("source_acquire", lambda *_: None),
                    ("source_fetch", lambda *_: None),
                    ("source_ticker", lambda *_: None)):
                    with self.subTest(field=field), self.assertRaisesRegex(
                            ValueError, "forbidden"):
                        launcher.dispatch_after_originalhost_and_cloud_readback(
                            originalhost_readback=lambda: {},
                            release_root=Path(root), release_packet={},
                            original_cloud_relay_token=token,
                            **dict(kwargs, **{field: value}))
                for bad in (None, "", "short", "fake token with space",
                            "T" * 513):
                    with self.subTest(token=repr(bad)), self.assertRaises(ValueError):
                        launcher.dispatch_after_originalhost_and_cloud_readback(
                            originalhost_readback=lambda: {},
                            release_root=Path(root), release_packet={},
                            original_cloud_relay_token=bad, **kwargs)
                owner.assert_not_called()
                relay.assert_not_called()

    def test_original_cloud_ack_receives_only_existing_relay_token(self):
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="CLOUD_RECEIPT_ACK")
            kwargs.pop("read_active_series")
            with patch.object(launcher, "dispatch_after_native_release_readback",
                              return_value={"status": "OFFLINE"}) as owner:
                token = "ORIGINAL_CLOUD_TEST_TOKEN_NO_NETWORK_1234567"
                self.assertEqual(
                    launcher.dispatch_after_originalhost_and_cloud_readback(
                        originalhost_readback=lambda: {}, release_root=Path(root),
                        release_packet={}, original_cloud_relay_token=token,
                        **kwargs)["status"], "OFFLINE")
                owner.assert_called_once()
                forwarded = owner.call_args.kwargs
                self.assertEqual(forwarded["relay_token"], token)
                self.assertTrue(callable(forwarded["read_active_series"]))

    def test_native_action_and_file_hash_inventory_is_not_a_release(self):
        fixture = {
            "kind": "V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1",
            "checked_at_utc": "2026-10-20T08:00:00Z",
            "filesystem_writes": False, "v2r4_changed": False,
            "new_v3_writer_started": False,
            "experimental_paper_release_authorized_by_this_check": False,
            "physical_v3_postcas_local_inventory": {
                "kind": "V3_NATIVE_POSTCAS_LOCAL_INSPECTION_ONLY_V1",
                "status": "NOT_INDEPENDENT_RELEASE_EVIDENCE",
                "native_task_state": "Disabled",
                "native_task_action_sha256": "a" * 64,
                "native_task_launcher_file_sha256": "b" * 64,
                "native_task_loaded_module_independently_verified": False,
                "live_paper_activation_authorized": False,
                "tasks_changed": 0, "cloud_writes": 0, "model_calls": 0,
            },
        }
        summary = launcher.summarize_originalhost_readonly(fixture)
        self.assertEqual(summary["native_task_action_sha256"], "a" * 64)
        self.assertEqual(summary["native_task_launcher_file_sha256"], "b" * 64)
        self.assertFalse(summary["native_task_loaded_module_independently_verified"])
        self.assertFalse(summary["paper_activated"])
        for candidate in ("Not-A-Hash", "z" * 64, None):
            local = dict(fixture["physical_v3_postcas_local_inventory"],
                         native_task_action_sha256=candidate)
            summary = launcher.summarize_originalhost_readonly(dict(
                fixture, physical_v3_postcas_local_inventory=local))
            self.assertIsNone(summary["native_task_action_sha256"])
            self.assertFalse(summary["runtime_bootstrap_executable"])

    def test_native_process_hint_cannot_authorize_loaded_module_or_paper(self):
        local = {
            "kind": "V3_NATIVE_POSTCAS_LOCAL_INSPECTION_ONLY_V1",
            "status": "NOT_INDEPENDENT_RELEASE_EVIDENCE",
            "native_task_state": "Running",
            "native_python_parent_process_observed": True,
            "native_python_parent_matches_task_action_hint": True,
            "native_powershell_process_token_is_system": True,
            "native_runtime_identity_independently_verified": True,
            "native_task_loaded_module_independently_verified": True,
            "live_paper_activation_authorized": False,
            "tasks_changed": 0, "cloud_writes": 0, "model_calls": 0,
        }
        report = {
            "kind": "V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1",
            "physical_v3_postcas_local_inventory": local,
            "new_v3_writer_started": False, "filesystem_writes": False,
            "v2r4_changed": False,
            "experimental_paper_release_authorized_by_this_check": False,
        }
        summary = launcher.summarize_originalhost_readonly(report)
        self.assertTrue(summary["native_python_parent_process_observed"])
        self.assertTrue(summary["native_powershell_process_token_is_system"])
        self.assertTrue(summary["native_python_parent_matches_task_action_hint"])
        self.assertFalse(summary["native_runtime_identity_independently_verified"])
        self.assertFalse(summary["native_task_loaded_module_independently_verified"])
        self.assertFalse(summary["paper_activated"])
        self.assertFalse(summary["runtime_bootstrap_executable"])

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
                          return_value={"status": "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE"}) as host, \
                patch.object(launcher, "dispatch_one_owned_paper_phase") as worker:
            out = io.StringIO()
            with patch("sys.argv", ["launcher", "--originalhost-readonly"]), \
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

    def test_originalhost_readonly_runs_only_existing_fixed_windows_script(self):
        report = {
            "kind": "V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1",
            "checked_at_utc": "2026-10-20T08:00:00Z",
            "filesystem_writes": False, "v2r4_changed": False,
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
        from unittest.mock import Mock
        completed = Mock(returncode=0, stdout=json.dumps(report))
        with patch.object(launcher.sys, "platform", "win32"), \
                patch.object(launcher.Path, "is_file", return_value=True), \
                patch.object(launcher.Path, "is_symlink", return_value=False), \
                patch.object(launcher.subprocess, "run",
                             return_value=completed) as probe, \
                patch.object(launcher, "dispatch_one_owned_paper_phase") as writer:
            result = launcher.read_originalhost_readonly()
        self.assertEqual(result["status"], "ORIGINALHOST_INVENTORY_ONLY_NO_RELEASE")
        probe.assert_called_once()
        args = probe.call_args.args[0]
        self.assertEqual(args[0], str(launcher.ORIGINALHOST_POWERSHELL))
        self.assertEqual(args[1:6], [
                    "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                    "Bypass", "-File"])
        self.assertTrue(args[6].replace(chr(92), "/").endswith(
            launcher.ORIGINALHOST_READONLY_SCRIPT))
        self.assertEqual(args[7:], ["-TradingRoot",
                                   launcher.ORIGINALHOST_TRADING_ROOT])
        self.assertEqual(probe.call_args.kwargs["timeout"], 90)
        self.assertFalse(probe.call_args.kwargs["check"])
        writer.assert_not_called()

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
            # OFFLINE FAKE only, never a physical maintenance approval.
            "maintenance_receipt_kind":
                "V3_EXISTING_MINIPC_MAINTENANCE_ORIGINALHOST_ACK_V1",
            "maintenance_receipt_sha256": "d" * 64,
            "maintenance_release_repo_sha": pin,
            "maintenance_completed_at_utc": "2026-10-19T13:00:00Z",
            "maintenance_cpu_bios_boot_thermal_originalhost_pass": True,
            "maintenance_windows_drivers_reboots_originalhost_pass": True,
            "maintenance_ups_configuration_shutdown_originalhost_pass": True,
            "maintenance_scripts_originalhost_source_ack_pass": True,
            "maintenance_v2r4_restart_and_aftercare_originalhost_pass": True,
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
                {"maintenance_receipt_sha256": "not-a-sha"},
                {"maintenance_receipt_kind": "USER_ASSERTED"},
                {"maintenance_release_repo_sha": "b" * 40},
                {"maintenance_completed_at_utc": "2026-10-19T14:10:00Z"},
                {"maintenance_completed_at_utc": "2026-10-19T13:00:00"},
                {"maintenance_cpu_bios_boot_thermal_originalhost_pass": False},
                {"maintenance_windows_drivers_reboots_originalhost_pass": False},
                {"maintenance_scripts_originalhost_source_ack_pass": False},
                {"maintenance_v2r4_restart_and_aftercare_originalhost_pass": False},
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

    def test_optional_ups_is_not_a_paper_release_veto(self):
        # Source-only regression: no optional UPS while genuine gates stay mandatory.
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "OPTIONAL_UPS_ONLY"})
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            base = self.original_release_host(self.SID, self.REPO)
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "dispatch_one_owned_paper_phase",
                    return_value={"status": "SOURCE_ONLY_MOCK"}) as worker:
                variants = [
                    {k: v for k, v in base.items()
                     if k != "maintenance_ups_configuration_shutdown_originalhost_pass"},
                    dict(base, maintenance_ups_configuration_shutdown_originalhost_pass=False),
                    dict(base, maintenance_ups_configuration_shutdown_originalhost_pass=True),
                ]
                for host in variants:
                    with self.subTest(optional_ups=host.get(
                            "maintenance_ups_configuration_shutdown_originalhost_pass",
                            "MISSING")):
                        result = launcher.dispatch_after_native_release_readback(
                            originalhost_readback=lambda h=host: h,
                            release_root=Path(root), release_packet=packet,
                            **kwargs)
                        self.assertEqual(result["status"], "SOURCE_ONLY_MOCK")
                self.assertEqual(worker.call_count, 3)
                # Still deny missing real physical, cloud or six-proof gates.
                for blocker in (
                    {"maintenance_scripts_originalhost_source_ack_pass": False},
                    {"maintenance_cpu_bios_boot_thermal_originalhost_pass": False},
                    {"maintenance_windows_drivers_reboots_originalhost_pass": False},
                    {"maintenance_v2r4_restart_and_aftercare_originalhost_pass": False},
                    {"six_external_original_e2e_proofs_approved": False},
                    {"independent_cloud_cas_committed": False},
                ):
                    with self.subTest(blocker=blocker):
                        with self.assertRaises(ValueError):
                            launcher.dispatch_after_native_release_readback(
                                originalhost_readback=lambda b=blocker: dict(base, **b),
                                release_root=Path(root), release_packet=packet,
                                **kwargs)
                self.assertEqual(worker.call_count, 3)

    def test_maintenance_receipt_is_not_seventh_technical_proof_or_cli_release(self):
        # The physical maintenance handoff is part of the original native
        # stop-start/rollback/release source, not a replacement for six proofs.
        self.assertEqual(len(launcher.PHASES), 3)
        with patch("sys.argv", ["launcher", "--read-only"]):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.assertEqual(launcher.main(), 0)
        status = json.loads(buf.getvalue())
        self.assertFalse(status["v3_paper_activated"])
        self.assertFalse(status["independent_six_e2e_proofs_verified"])
        self.assertFalse(status["cloud_cas_performed"])

        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(self.common(root), phase="FOLLOWUP_6H24H72H",
                          candidate={"candidate_id": "OFFLINE_ONLY"})
            good = self.original_release_host(self.SID, self.REPO)
            packet = {"strategy_revision": launcher.REVISION,
                      "strategy_fingerprint_sha256": self.STRATEGY}
            with patch.object(launcher, "validate_experimental_paper_packet",
                              return_value=[]), patch.object(
                    launcher, "dispatch_one_owned_paper_phase") as worker:
                for changed in (
                    {"maintenance_receipt_sha256": None},
                    {"maintenance_cpu_bios_boot_thermal_originalhost_pass": 1},
                    {"maintenance_v2r4_restart_and_aftercare_originalhost_pass": None},
                    {"maintenance_completed_at_utc": "2026-10-19T14:00:01Z"},
                    {"maintenance_release_repo_sha": "f" * 40},
                ):
                    host = dict(good, **changed)
                    with self.subTest(changed=changed), self.assertRaises(ValueError):
                        launcher.dispatch_after_native_release_readback(
                            originalhost_readback=lambda h=host: h,
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




class NativeStageSourcePinTests(unittest.TestCase):
    """One original source manifest only; these are synthetic bytes, not an E2E."""

    SHA = "e" * 40
    REQUIRED = (
        "paper_evaluator/v3_paper_minipc_native_launcher_v1.py",
        "paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
        "paper_evaluator/v3_paper_minipc_selective_tick_v1.py",
        "paper_evaluator/v3_paper_cloud_receipt_sync_v1.py",
        "tools/v3_experimental_paper_technical_gate.py",
        "tools/paper_series_transition_guard.py",
        "research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json",
    )

    def stage(self, root):
        r = Path(root) / "Staging" / ("V3Paper-INACTIVE-" + self.SHA[:12])
        r.mkdir(parents=True)
        files = list(self.REQUIRED) + [
            f"paper_evaluator/offline_dep_{i:02d}.py" for i in range(15)
        ]
        rows = []
        for relative in files:
            destination = r / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = ("# FAKE STAGE " + relative + "\n").encode("utf-8")
            destination.write_bytes(data)
            rows.append({"relative_path": relative,
                         "sha256": hashlib.sha256(data).hexdigest()})
        closure_names = [row["relative_path"] for row in rows]
        manifest = {
            "kind": "V3_PAPER_INACTIVE_ISOLATED_SOURCE_STAGE_V1",
            "status": "STAGED_INACTIVE_CODE_ONLY_NOT_INSTALLED",
            "source_git_sha": self.SHA,
            "v3_paper_activated": False,
            "task_changes": False,
            "source_closure_is_only_candidate_not_loaded_code_ack": True,
            "tracked_code_files": len(rows),
            "source_manifest": rows,
            "static_transitive_closure_file_count": len(closure_names),
            "static_transitive_closure_files": closure_names,
            "static_transitive_closure_sha256": "f" * 64,
        }
        (r / "v3-paper-inactive-source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")
        closure = {
            "static_local_import_closure_complete": True,
            "candidate_transitive_file_count": len(closure_names),
            "candidate_transitive_files": [
                [n, next(row["sha256"] for row in rows
                         if row["relative_path"] == n)]
                for n in closure_names],
            "candidate_transitive_source_sha256": "f" * 64,
        }
        return r, manifest, closure

    @staticmethod
    def rewrite(root, manifest):
        (root / "v3-paper-inactive-source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")

    def test_exact_stage_source_and_existing_closure_pass_only_locally(self):
        with tempfile.TemporaryDirectory() as temp:
            root, manifest, closure = self.stage(temp)
            with patch.object(launcher, "assess_v3_native_source_import_closure",
                              return_value=closure) as check:
                self.assertIsNone(launcher._require_staged_v3_source_manifest(
                    repo_sha=self.SHA, stage_root=root))
                check.assert_called_once_with(root)
            self.assertTrue(manifest["source_closure_is_only_candidate_not_loaded_code_ack"])

    def test_inactive_stage_rejects_byte_tampering_wrong_sha_or_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root, manifest, closure = self.stage(temp)
            path = root / self.REQUIRED[0]
            path.write_bytes(b"# different imported Python source")
            with patch.object(launcher, "assess_v3_native_source_import_closure",
                              return_value=closure) as check:
                with self.assertRaisesRegex(ValueError, "byte drift"):
                    launcher._require_staged_v3_source_manifest(
                        repo_sha=self.SHA, stage_root=root)
                check.assert_not_called()
        for corruption in ("source_git_sha", "v3_paper_activated",
                           "task_changes", "duplicate", "escape",
                           "static_transitive_closure_file_count",
                           "closure_foreign_name"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temp:
                root, m, closure = self.stage(temp)
                if corruption == "source_git_sha":
                    m["source_git_sha"] = "c" * 40
                elif corruption == "v3_paper_activated":
                    m["v3_paper_activated"] = True
                elif corruption == "task_changes":
                    m["task_changes"] = True
                elif corruption == "duplicate":
                    m["source_manifest"][-1] = dict(m["source_manifest"][0])
                elif corruption == "escape":
                    m["source_manifest"][-1]["relative_path"] = "../outside.py"
                elif corruption == "static_transitive_closure_file_count":
                    m["static_transitive_closure_file_count"] += 1
                else:
                    m["static_transitive_closure_files"][-1] = "../foreign.py"
                self.rewrite(root, m)
                with patch.object(launcher, "assess_v3_native_source_import_closure",
                                  return_value=closure):
                    with self.assertRaises(ValueError):
                        launcher._require_staged_v3_source_manifest(
                            repo_sha=self.SHA, stage_root=root)

    def test_symlinked_stage_file_and_changed_closure_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root, m, closure = self.stage(temp)
            item = root / self.REQUIRED[0]
            item.unlink()
            item.symlink_to(root / self.REQUIRED[1])
            with patch.object(launcher, "assess_v3_native_source_import_closure",
                              return_value=closure):
                with self.assertRaises(ValueError):
                    launcher._require_staged_v3_source_manifest(
                        repo_sha=self.SHA, stage_root=root)
        for changed in ({"static_local_import_closure_complete": False},
                        {"candidate_transitive_source_sha256": "0" * 64},
                        {"candidate_transitive_file_count": 1},
                        {"candidate_transitive_files": []}):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temp:
                root, m, closure = self.stage(temp)
                with patch.object(launcher, "assess_v3_native_source_import_closure",
                                  return_value=dict(closure, **changed)):
                    with self.assertRaisesRegex(ValueError, "closure changed"):
                        launcher._require_staged_v3_source_manifest(
                            repo_sha=self.SHA, stage_root=root)

    def test_native_dispatch_cannot_skip_stage_source_verification(self):
        # Correlated offline Task + independent callback are insufficient if
        # the original pinned stage cannot be re-read. No actual E2E authority.
        case = SingleNativeOwnerLauncherTests()
        host = case.correlated_originalhost()
        independent = dict(
            observed_at_utc="2026-10-19T14:00:16Z",
            native_task_action_sha256=host["native_task_action_sha256"],
            native_task_launcher_file_sha256=host["native_task_launcher_file_sha256"],
            native_python_parent_pid=host["native_python_parent_pid"],
            native_python_parent_started_at_utc=host["native_python_parent_started_at_utc"])
        with patch.object(launcher.sys, "platform", "win32"), patch.object(
                launcher.os, "getpid", return_value=21704), patch.object(
                launcher, "_originalhost_wall_clock_utc",
                return_value=datetime(2026, 10, 19, 14, 0, 25, tzinfo=timezone.utc)), patch.object(
                launcher, "read_originalhost_readonly",
                return_value=host), patch.object(
                launcher, "dispatch_after_originalhost_and_cloud_readback",
                side_effect=lambda **kw: kw["originalhost_readback"]()) as owner, patch.object(
                launcher, "dispatch_one_owned_paper_phase") as worker:
            with self.assertRaisesRegex(ValueError, "native source not in exact original inactive stage"):
                launcher.dispatch_from_original_windows_one_shot(
                    originalhost_release_readback=lambda: independent,
                    phase="FOLLOWUP_6H24H72H",
                    series_id=case.SID, repo_sha=self.SHA)
            owner.assert_called_once()
            worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
