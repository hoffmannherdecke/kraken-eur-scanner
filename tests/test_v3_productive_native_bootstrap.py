"""Offline executable-entry plumbing; no physical Windows/Cloud claims."""
import argparse
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from paper_evaluator import v3_paper_minipc_native_launcher_v1 as native
from paper_evaluator.v3_paper_native_scanner_input_v1 import original_candidate


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
        self.capture_dir = self.root / "capture"
        self.capture_dir.mkdir()
        self.scanner_heartbeat = self.state / "v2r4-ws-shadow-heartbeat.json"
        self.write_scanner_heartbeat()
        self.spec = dict(kind=native.REPEATED_SPEC, series_id="PAPER-V3-20260101T000000Z",
            repo_sha="a"*40, bundle_sha256="b"*64, strategy_sha256="c"*64,
            release_root=str(self.root), candidate=None, preflight=None)
        self.lease = dict(scope="V3_PAPER_RUNTIME_REPEATED", approval_sha256="d"*64,
                          runtime_spec=self.spec.copy(),
                          not_before_utc=(self.now-timedelta(seconds=1)).isoformat())
        self.phases = []
        self.heartbeats = []

    def write_scanner_heartbeat(self):
        self.scanner_heartbeat.write_text(json.dumps({
            "kind": "V2R4_WS_SHADOW_HEARTBEAT_V1", "checked_at_utc": self.now.isoformat(),
            "status": "HEALTHY", "paper_only": True, "real_money_actions": False,
        }))

    def run_writer(self):
        return native._run_repeated_paper(args=None, spec=self.spec,
            params={"journal": self.journal, "capture_dir": self.capture_dir}, packet={"primary_decision_route": native.FREE_RULE_ROUTE,
                    "bounded_research_scope":{"max_observation_days":1, "max_candidates":4}},
            token="offline")

    def test_multiple_cycles_expiry_and_restart_use_one_owner(self):
        def observe(**kwargs):
            return {"runtime_lease": {**self.lease, "expires_at_utc": self.deadline.isoformat()}}

        candidate = {"candidate_id": "real-original-fixture"}
        preflight = {"selected_candidates": [candidate]}

        def prepare(**kwargs):
            return None if candidate["candidate_id"] in kwargs["seen"] else (candidate, preflight)

        def dispatch(**kwargs):
            kwargs["originalhost_release_readback"]()
            phase = kwargs["phase"]
            self.phases.append(phase)
            if phase == "FIRST_SCANNER_MODEL_P4":
                self.assertEqual(kwargs["preflight"], preflight)
                (self.journal / "scanner.json").write_text(json.dumps({
                    "series_id": self.spec["series_id"], **candidate,
                    "phase": "SCANNER_CAPTURE", "result": "SEEN", "event_key": "FIRST",
                }))
            elif phase == "FOLLOWUP_6H24H72H":
                self.assertEqual(kwargs["candidate"], candidate)
            with self.assertRaisesRegex(ValueError, "ANOTHER_CANARY_OWNER"):
                self.run_writer()
            return {"status": {
                "FIRST_SCANNER_MODEL_P4": "FIRST_SCANNER_FREE_RULE_P4_DURABLE_WAIT_FOR_FOLLOWUP",
                "FOLLOWUP_6H24H72H": "NONCANARY_FOLLOWUP_HOLD_ALL_FOLLOWUPS_FINAL_NO_NEW_SOURCE",
                "CLOUD_RECEIPT_ACK": "NO_UNSYNCED_V3_RECEIPTS",
            }[kwargs["phase"]]}

        def wait(seconds):
            self.heartbeats.append(json.loads(self.heartbeat.read_text()))
            self.now += timedelta(seconds=seconds)
            self.write_scanner_heartbeat()

        with patch.object(native, "ORIGINALHOST_TRADING_ROOT", str(self.root)), \
             patch.object(native, "_originalhost_wall_clock_utc", side_effect=lambda: self.now), \
             patch.object(native, "authenticated_originalhost_release_provider", side_effect=observe), \
             patch.object(native, "dispatch_from_original_windows_one_shot", side_effect=dispatch), \
             patch.object(native, "prepare_next_scanner_input", side_effect=prepare), \
             patch.object(native.time, "sleep", side_effect=wait):
            self.run_writer()
            self.assertEqual(self.phases, ["CLOUD_RECEIPT_ACK", "FIRST_SCANNER_MODEL_P4",
                                          "FOLLOWUP_6H24H72H", "CLOUD_RECEIPT_ACK"]
                              + ["CLOUD_RECEIPT_ACK", "FOLLOWUP_6H24H72H", "CLOUD_RECEIPT_ACK"] * 2)
            self.assertTrue(all(row["status"] == "HEALTHY" and row["paper_only"]
                                and not row["orders"] for row in self.heartbeats))
            self.assertEqual(json.loads(self.heartbeat.read_text())["status"], "EXPIRED")
            with self.assertRaises(native.PaperRuntimeLeaseExpired):
                self.run_writer()
            self.deadline += timedelta(seconds=20)
            self.run_writer()
            self.assertEqual(len(self.phases), 13)

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


class OriginalScannerTests(unittest.TestCase):
    def test_only_fresh_eligible_source_preserves_original_clock_and_identity(self):
        observed = datetime(2026, 11, 8, 15, 42, tzinfo=timezone.utc)
        event = {
            "kind": "V2R4_WS_SHADOW_DISCOVERY", "schema_version": 1, "pair": "SCOR/EUR",
            "shadow_only": True, "paper_only": True, "real_money_actions_enabled": False,
            "fresh_recheck_invoked": False, "next_action": "SHADOW_OBSERVE_ONLY",
            "would_request_fresh_recheck": True,
            "liquidity_class_without_depth": "STANDARD_EXECUTION_GATE",
            "observed_at_utc": "2026-11-08T15:34:44.133104Z",
            "source_pair_received_at_utc": "2026-11-08T15:34:41.420751Z",
            "source_snapshot_written_at_utc": "2026-11-08T15:34:43.309110Z",
            "last_eur": 1.0, "returns": {}, "reasons": [],
        }
        window = {"observed": observed, "series_started": observed - timedelta(minutes=9)}
        candidate = original_candidate(event, **window)
        self.assertEqual(candidate["event_time_utc"], event["observed_at_utc"])
        self.assertEqual(candidate["scanner_market_context"]["source_event"], event)
        self.assertEqual(candidate, original_candidate(event, **window))
        for invalid in (
            {"would_request_fresh_recheck": False, "liquidity_class_without_depth": "WATCH_ONLY"},
            {"real_money_actions_enabled": True},
            {"source_pair_received_at_utc": "2026-11-08T15:42:01Z"},
        ):
            with self.subTest(invalid=invalid):
                self.assertIsNone(original_candidate({**event, **invalid}, **window))
        self.assertIsNone(original_candidate(event, observed=observed + timedelta(minutes=5),
                                             series_started=window["series_started"]))

    def test_live_input_preflight_keeps_market_and_source_identity(self):
        from paper_evaluator import v3_paper_native_scanner_input_v1 as scanner

        observed = datetime(2026, 11, 8, 15, 42, tzinfo=timezone.utc)
        event = {
            "kind": "V2R4_WS_SHADOW_DISCOVERY", "schema_version": 1, "pair": "SCOR/EUR",
            "shadow_only": True, "paper_only": True, "real_money_actions_enabled": False,
            "fresh_recheck_invoked": False, "next_action": "SHADOW_OBSERVE_ONLY",
            "would_request_fresh_recheck": True,
            "liquidity_class_without_depth": "STANDARD_EXECUTION_GATE",
            "observed_at_utc": "2026-11-08T15:34:44.133104Z",
            "source_pair_received_at_utc": "2026-11-08T15:34:41.420751Z",
            "source_snapshot_written_at_utc": "2026-11-08T15:34:43.309110Z",
            "last_eur": 1.0, "returns": {}, "reasons": [],
        }
        pairs = {"result": {"SCOREUR": {"status": "online", "wsname": "SCOR/EUR",
                                       "quote": "EUR", "altname": "SCOREUR"}}}
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            file = source / "20261108T153444.133104Z-SCOR-EUR.json"
            file.write_text(json.dumps({**event, "would_request_fresh_recheck": False}))
            attempted = set()
            args = dict(source=source, series_id="PAPER-V3-20261108T153400Z",
                        series_started=observed - timedelta(minutes=8), seen=set(),
                        attempted=attempted, clock=lambda: observed, read_json=native._bounded_release_json)
            with patch.object(scanner, "http_json", return_value=pairs) as fetch, \
                 patch.object(scanner, "fetch_public_entry_evidence", return_value={"pit": "fixture"}), \
                 patch.object(scanner, "kraken_ticker", return_value={"ask": 1.0}), \
                 patch.object(scanner, "verified_spot_metadata", return_value={"status": "online"}), \
                 patch.object(scanner, "plan_writer_preflight") as plan:
                self.assertIsNone(scanner.prepare_next_scanner_input(**args))
                fetch.assert_not_called()
                file.write_text(json.dumps(event))
                plan.side_effect = lambda **kw: {
                    "selected_candidates": kw["scanner_events"],
                    "review_preflights": [{"eligible_for_full_model_review": True}],
                }
                candidate, preflight = scanner.prepare_next_scanner_input(**args)
                self.assertEqual(candidate["scanner_market_context"]["source_event"], event)
                self.assertEqual(candidate["altname"], "SCOREUR")
                self.assertEqual(preflight["selected_candidates"], [candidate])
                self.assertEqual(plan.call_args.kwargs["series_id"], args["series_id"])
                self.assertEqual(plan.call_args.kwargs["market_observations"]["SCOR/EUR"]["entry_evidence"],
                                 {"pit": "fixture"})
                self.assertIsNone(scanner.prepare_next_scanner_input(**args))
                fetch.assert_called_once()
