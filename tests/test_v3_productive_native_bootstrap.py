"""Offline executable-entry plumbing; no physical Windows/Cloud claims."""
import argparse
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from paper_evaluator import v3_paper_minipc_native_launcher_v1 as native


class ProductiveNativeBootstrapTests(unittest.TestCase):
    def test_bounded_parser_rejects_duplicate_and_nonfinite_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'spec.json'
            for raw in ('{"phase":1,"phase":2}', '{"v":NaN}', '[]'):
                p.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    native._bounded_release_json(p)
            p.write_text('{"valid":true}')
            self.assertEqual(native._bounded_release_json(p), {'valid': True})
            with self.assertRaises(ValueError):
                native._bounded_release_json(Path('relative.json'))

    def test_provider_uses_fixed_original_operator_and_no_secret_arguments(self):
        args = argparse.Namespace(runtime_spec='spec', approval_json='approval',
            approval_cms='cms', admission_json='admission', admission_sha256='a'*64,
            expected_source_sha='b'*40, host_receipt='host', host_cms='host-cms')
        result = argparse.Namespace(returncode=0, stdout='{"kind":"observed"}')
        with patch.object(native.subprocess, 'run', return_value=result) as run:
            self.assertEqual(native.authenticated_originalhost_release_provider(args=args), {'kind':'observed'})
        cmd = run.call_args.args[0]
        self.assertIn('PaperHostReadback', cmd)
        self.assertIn('-ExpectedReleaseCommit', cmd)
        self.assertNotIn('-PostgresPassword', cmd)
        self.assertEqual(cmd[cmd.index('-File')+1], str(Path(native.__file__).absolute().parents[1]/'tools/v3-one-time-release.ps1'))

    def test_provider_failure_never_returns_report(self):
        args = argparse.Namespace(**{k:'x' for k in ('runtime_spec','approval_json',
            'approval_cms','admission_json','admission_sha256','expected_source_sha','host_receipt','host_cms')})
        for code, out in ((1,'{}'), (0,''), (0,'[]'), (0,'x'*65537)):
            with self.subTest(code=code, length=len(out)), patch.object(native.subprocess,
                'run', return_value=argparse.Namespace(returncode=code,stdout=out)), self.assertRaises(ValueError):
                native.authenticated_originalhost_release_provider(args=args)

    def test_runtime_spec_forbids_paid_model_and_transport_injection(self):
        spec = dict.fromkeys(('kind','series_id','repo_sha','bundle_sha256','strategy_sha256',
            'phase','journal','capture_dir','model_reservations','ack_file','release_root',
            'release_packet','candidate','preflight','paper_plan'), '')
        spec.update(kind='V3_NATIVE_RELEASE_RUNTIME_SPEC_V1',repo_sha='a'*40,phase=native.PHASES[0])
        args=argparse.Namespace(expected_source_sha='a'*40)
        for extra in ('model_key','model_client','read_active_series','clock_now','approval'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                native.run_authenticated_windows_spec(args=args,spec={**spec,extra:'untrusted'})

    def test_productive_bootstrap_rejects_non_windows_before_import_or_io(self):
        argv=['native','--released-one-shot']
        for flag in ('runtime-spec','approval-json','approval-cms','admission-json',
                     'admission-sha256','expected-source-sha','host-receipt','host-cms'):
            argv += ['--'+flag,'missing']
        with patch.object(native.sys,'platform','linux'), patch.object(native.sys,'argv',argv), \
             patch.object(native,'load_native_runtime_snapshot') as load, self.assertRaises(ValueError):
            native._released_windows_bootstrap()
        load.assert_not_called()


class RepeatedPaperTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.state = self.root / "State"
        self.state.mkdir()
        self.journal = self.root / "journal"
        self.journal.mkdir()
        self.heartbeat = self.state / "v3-paper-single-writer-heartbeat.json"
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.deadline = self.now + timedelta(seconds=65)
        self.spec = dict(kind=native.REPEATED_SPEC, series_id="PAPER-V3-20000101T000000Z",
            repo_sha="a"*40, bundle_sha256="b"*64, strategy_sha256="c"*64,
            release_root=str(self.root), candidate=str(self.root/"candidate.json"),
            preflight=str(self.root/"preflight.json"))
        for key in ("candidate", "preflight"):
            Path(self.spec[key]).write_text("{}")
        self.lease = dict(scope="V3_PAPER_RUNTIME_REPEATED", approval_sha256="d"*64,
                          runtime_spec=self.spec.copy(),
                          not_before_utc=(self.now-timedelta(seconds=1)).isoformat())
        self.phases = []
        self.heartbeats = []

    def run_writer(self):
        return native._run_repeated_paper(args=None, spec=self.spec,
            params={"journal": self.journal}, packet={"primary_decision_route": native.FREE_RULE_ROUTE,
                    "bounded_research_scope":{"max_observation_days":1}},
            token="offline")

    def test_multiple_cycles_expiry_and_restart_use_one_owner(self):
        def observe(**kwargs):
            return {"runtime_lease": {**self.lease, "expires_at_utc": self.deadline.isoformat()}}

        def dispatch(**kwargs):
            kwargs["originalhost_release_readback"]()
            self.phases.append(kwargs["phase"])
            with self.assertRaisesRegex(ValueError, "ANOTHER_CANARY_OWNER"):
                self.run_writer()
            return {"status": {
                "FIRST_SCANNER_MODEL_P4": "FIRST_SCANNER_ALREADY_JOURNALED_NO_RULE_REPLAY",
                "FOLLOWUP_6H24H72H": "NONCANARY_FOLLOWUP_HOLD_ALL_FOLLOWUPS_FINAL_NO_NEW_SOURCE",
                "CLOUD_RECEIPT_ACK": "NO_UNSYNCED_V3_RECEIPTS",
            }[kwargs["phase"]]}

        def wait(seconds):
            self.heartbeats.append(json.loads(self.heartbeat.read_text()))
            self.now += timedelta(seconds=seconds)

        with patch.object(native, "ORIGINALHOST_TRADING_ROOT", str(self.root)), \
             patch.object(native, "_originalhost_wall_clock_utc", side_effect=lambda: self.now), \
             patch.object(native, "authenticated_originalhost_release_provider", side_effect=observe), \
             patch.object(native, "dispatch_from_original_windows_one_shot", side_effect=dispatch), \
             patch.object(native.time, "sleep", side_effect=wait):
            self.run_writer()
            self.assertEqual(self.phases, ["FIRST_SCANNER_MODEL_P4", "CLOUD_RECEIPT_ACK",
                                          "FOLLOWUP_6H24H72H", "CLOUD_RECEIPT_ACK"] * 3)
            self.assertTrue(all(row["status"] == "HEALTHY" and row["paper_only"]
                                and not row["orders"] for row in self.heartbeats))
            self.assertEqual(json.loads(self.heartbeat.read_text())["status"], "EXPIRED")
            with self.assertRaises(native.PaperRuntimeLeaseExpired):
                self.run_writer()
            self.deadline += timedelta(seconds=20)
            self.run_writer()
            self.assertEqual(len(self.phases), 16)

    def test_missing_wrong_or_expired_signature_never_dispatches_or_writes_heartbeat(self):
        for lease in (None, {**self.lease, "scope": "V3_PAPER_RUNTIME"},
                      {**self.lease, "runtime_spec": {}},
                      {**self.lease, "expires_at_utc": self.now.isoformat()}):
            with self.subTest(lease=lease), \
                 patch.object(native, "ORIGINALHOST_TRADING_ROOT", str(self.root)), \
                 patch.object(native, "_originalhost_wall_clock_utc", return_value=self.now), \
                 patch.object(native, "authenticated_originalhost_release_provider",
                              return_value={"runtime_lease": lease}), \
                 patch.object(native, "dispatch_from_original_windows_one_shot") as dispatch:
                with self.assertRaises(ValueError):
                    self.run_writer()
                dispatch.assert_not_called()
                self.assertFalse(self.heartbeat.exists())

    def test_phase_failure_publishes_hold_and_releases_process_lock(self):
        lease = {**self.lease, "expires_at_utc": self.deadline.isoformat()}
        with patch.object(native, "ORIGINALHOST_TRADING_ROOT", str(self.root)), \
             patch.object(native, "_originalhost_wall_clock_utc", return_value=self.now), \
             patch.object(native, "authenticated_originalhost_release_provider",
                          return_value={"runtime_lease": lease}), \
             patch.object(native, "dispatch_from_original_windows_one_shot",
                          side_effect=ValueError("reconciliation required")) as dispatch:
            with self.assertRaisesRegex(ValueError, "reconciliation required"):
                self.run_writer()
            self.assertEqual(json.loads(self.heartbeat.read_text())["status"], "HOLD")
            self.assertEqual(dispatch.call_count, 1)
            with native._one_canary_owner(self.state):
                pass


if __name__ == '__main__':
    unittest.main()
