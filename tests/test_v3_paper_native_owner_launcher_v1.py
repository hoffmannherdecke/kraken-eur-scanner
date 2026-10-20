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
                launcher.ORIGINALHOST_POWERSHELL, "is_file", return_value=True), patch.object(
                launcher.ORIGINALHOST_POWERSHELL, "is_symlink", return_value=False), patch.object(
                launcher.Path, "is_file", autospec=True, return_value=True), patch.object(
                launcher.Path, "is_symlink", autospec=True, return_value=False), patch.object(
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
        self.assertEqual(args[1:4], ["-NoProfile", "-NonInteractive", "-File"])
        self.assertTrue(args[4].replace(chr(92), "/").endswith(
            launcher.ORIGINALHOST_READONLY_SCRIPT))
        self.assertEqual(args[5:], ["-TradingRoot",
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
                {"maintenance_ups_configuration_shutdown_originalhost_pass": False},
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


if __name__ == "__main__":
    unittest.main()
