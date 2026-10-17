"""Original V3 Paper one native-owner launcher: offline only, never Cloud/model."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v3_paper_minipc_native_launcher_v1 as launcher


class SingleNativeOwnerLauncherTests(unittest.TestCase):
    SID = "PAPER-V3-20261017T170000Z"
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


if __name__ == "__main__":
    unittest.main()
