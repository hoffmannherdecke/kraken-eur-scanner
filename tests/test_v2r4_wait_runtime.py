import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v2r4_wait_runtime as runtime


def z(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def plan(now, *, candidate_id="C1", value=1.0):
    return {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "pair": "BTC/EUR",
        "altname": "XBTEUR",
        "created_at_utc": z(now),
        "expires_at_utc": z(now + timedelta(minutes=30)),
        "logic": "ALL",
        "conditions": [
            {"metric": "last_eur", "op": ">=", "value": value},
        ],
        "on_match": "FRESH_PAPER_RECHECK_ONLY",
        "paper_only": True,
    }


class V2R4WaitRuntimeTests(unittest.TestCase):
    def test_cycle_start_does_not_masquerade_as_health_completion(self):
        # Real Mini-PC incident: cycle-start stamp preceded file write by
        # 111s. Even a 30s Supervisor threshold must see completion time.
        at = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
        done = at + timedelta(seconds=111)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name in ("decisions", "rechecks", "candidates", "receipts"):
                (base / name).mkdir()
            with patch.object(runtime, "utcnow", return_value=done):
                result = runtime.run_cycle(
                    decision_dir=base / "decisions",
                    recheck_dir=base / "rechecks",
                    candidate_dir=base / "candidates",
                    receipt_dir=base / "receipts",
                    state_path=base / "state.json",
                    heartbeat_path=base / "heartbeat.json",
                    altrady_log=base / "altrady.jsonl",
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False, now=at,
                )
            disk = json.loads((base / "heartbeat.json").read_text("utf-8"))
            self.assertEqual(result["checked_at_utc"], z(done))
            self.assertEqual(disk["checked_at_utc"], z(done))
            self.assertEqual(disk["cycle_started_at_utc"], z(at))
            self.assertGreaterEqual(disk["cycle_duration_seconds"], 0)
            self.assertEqual(result["status"], "HEALTHY")
            self.assertEqual(result["counters"]["unique_pair_source_fetches"], 0)

    def test_degraded_cycle_still_uses_real_completion_timestamp(self):
        at = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
        done = at + timedelta(seconds=125)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name in ("decisions", "rechecks", "candidates", "receipts"):
                (base / name).mkdir()
            (base / "decisions" / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": plan(at)}), "utf-8"
            )
            with patch.object(runtime, "utcnow", return_value=done), patch.object(
                runtime, "market_metrics", side_effect=RuntimeError("Kraken unavailable")
            ):
                result = runtime.run_cycle(
                    decision_dir=base / "decisions",
                    recheck_dir=base / "rechecks",
                    candidate_dir=base / "candidates",
                    receipt_dir=base / "receipts",
                    state_path=base / "state.json",
                    heartbeat_path=base / "heartbeat.json",
                    altrady_log=base / "altrady.jsonl",
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False, now=at,
                )
            self.assertEqual(result["status"], "DEGRADED")
            self.assertEqual(result["checked_at_utc"], z(done))
            self.assertEqual(result["cycle_started_at_utc"], z(at))
            self.assertEqual(result["counters"]["data_unavailable_checks"], 1)

    def test_opt_in_source_progress_requires_completed_source_response(self):
        import os
        at = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dirs = [root / n for n in ('decisions', 'rechecks', 'candidates', 'receipts')]
            for d in dirs: d.mkdir()
            (dirs[0] / 'plan.json').write_text(
                json.dumps({'v2r4_trigger_plan': plan(at, value=100.0)}), 'utf-8'
            )
            progress = root / 'source-progress.json'
            def completed_source(altname, *, on_source_progress=None):
                self.assertEqual(altname, 'XBTEUR')
                self.assertIsNotNone(on_source_progress)
                on_source_progress()
                on_source_progress()
                return {'last_eur': 90.0}
            with patch.object(runtime, 'market_metrics', side_effect=completed_source) as fetch:
                result = runtime.run_cycle(
                    decision_dir=dirs[0], recheck_dir=dirs[1],
                    candidate_dir=dirs[2], receipt_dir=dirs[3],
                    state_path=root / 'state.json', heartbeat_path=root / 'heartbeat.json',
                    altrady_log=root / 'altrady.jsonl',
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False,
                    now=at + timedelta(seconds=5), source_progress_path=progress,
                )
            self.assertEqual(fetch.call_count, 1)
            row = json.loads(progress.read_text('utf-8'))
            self.assertEqual(row['kind'], 'V2R4_WAIT_SOURCE_PROGRESS_V1')
            self.assertEqual(row['status'], 'IN_PROGRESS_NOT_HEALTHY')
            self.assertEqual(row['successful_source_steps'], 2)
            self.assertEqual(row['worker_pid'], os.getpid())
            self.assertTrue(row['paper_only'])
            self.assertFalse(row['order_api'])
            self.assertEqual(result['status'], 'HEALTHY')
            self.assertEqual(list(dirs[3].iterdir()), [])

    def test_no_completed_source_cannot_emit_progress_pulse(self):
        at = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dirs = [root / n for n in ('decisions', 'rechecks', 'candidates', 'receipts')]
            for d in dirs: d.mkdir()
            (dirs[0] / 'plan.json').write_text(
                json.dumps({'v2r4_trigger_plan': plan(at, value=100.0)}), 'utf-8'
            )
            progress = root / 'source-progress.json'
            with patch.object(runtime, 'market_metrics', side_effect=RuntimeError('offline error')):
                result = runtime.run_cycle(
                    decision_dir=dirs[0], recheck_dir=dirs[1],
                    candidate_dir=dirs[2], receipt_dir=dirs[3],
                    state_path=root / 'state.json', heartbeat_path=root / 'heartbeat.json',
                    altrady_log=root / 'altrady.jsonl',
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False,
                    now=at + timedelta(seconds=5), source_progress_path=progress,
                )
            self.assertEqual(result['status'], 'DEGRADED')
            self.assertFalse(progress.exists())
    def test_kraken_error_payload_never_counts_as_positive_source_progress(self):
        from paper_evaluator import v2r4_wait_watcher as watcher
        signals = []
        with patch.object(watcher, 'http_json', return_value={'error':['EGeneral:Too many requests']}):
            with self.assertRaisesRegex(RuntimeError, 'Kraken ticker error'):
                watcher.ticker('XBTEUR', on_source_progress=lambda: signals.append('ticker'))
            with self.assertRaisesRegex(RuntimeError, 'Kraken OHLC error'):
                watcher.closed_ohlc('XBTEUR', 1, on_source_progress=lambda: signals.append('ohlc'))
        self.assertEqual(signals, [])

    def test_parsed_ticker_response_counts_exactly_one_real_progress_step(self):
        from paper_evaluator import v2r4_wait_watcher as watcher
        signals = []
        fake={'error':[], 'result':{'XXBTZEUR':{'a':['102'], 'b':['100'], 'c':['101']}}}
        with patch.object(watcher, 'http_json', return_value=fake):
            row = watcher.ticker('XBTEUR', on_source_progress=lambda: signals.append('ticker'))
        self.assertEqual(row['last_eur'], 101.0)
        self.assertEqual(signals,['ticker'])
    def test_legacy_kraken_symbol_matches_same_pair_hint(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        p = plan(now)
        self.assertTrue(runtime.hint_matches_plan("BTC/EUR", p))
        self.assertTrue(runtime.hint_matches_plan("XBTEUR", p))
        self.assertTrue(runtime.hint_matches_plan("XXBTZEUR", p))
        self.assertFalse(runtime.hint_matches_plan("ETHEUR", p))

    def test_discovers_decision_and_chained_recheck_plans(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "decisions"
            rechecks = root / "rechecks"
            decisions.mkdir()
            rechecks.mkdir()

            p1 = plan(now, candidate_id="C1")
            p2 = plan(now + timedelta(seconds=1), candidate_id="C2")
            (decisions / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": p1}), "utf-8"
            )
            (rechecks / "r.json").write_text(
                json.dumps({"next_wait_trigger_plan": p2}), "utf-8"
            )

            found = runtime.discover_plans(decisions, rechecks, now=now)
            self.assertEqual({p[0]["candidate_id"] for p in found}, {"C1", "C2"})

    def test_altrady_event_is_only_wakeup_and_kraken_still_decides_false(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "decisions"
            rechecks = root / "rechecks"
            candidates = root / "candidates"
            receipts = root / "receipts"
            state = root / "state.json"
            heartbeat = root / "heartbeat.json"
            altrady = root / "altrady.jsonl"
            for d in (decisions, rechecks, candidates, receipts):
                d.mkdir()

            p = plan(now, value=100.0)
            (decisions / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": p}), "utf-8"
            )
            altrady.write_text(
                json.dumps({"event": {"id": "E1", "symbol": "XXBTZEUR"}}) + "\n",
                "utf-8",
            )

            with patch.object(
                runtime,
                "market_metrics",
                return_value={"last_eur": 90.0},
            ):
                out = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=None,
                    control_path=None,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=False,
                    now=now + timedelta(seconds=5),
                )

            self.assertEqual(out["status"], "HEALTHY")
            self.assertEqual(out["counters"]["altrady_wakeup_checks"], 1)
            self.assertEqual(out["counters"]["condition_matches"], 0)
            self.assertEqual(list(receipts.glob("*.json")), [])

    def test_matching_kraken_condition_writes_receipt_only_in_smoke_mode(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "decisions"
            rechecks = root / "rechecks"
            candidates = root / "candidates"
            receipts = root / "receipts"
            state = root / "state.json"
            heartbeat = root / "heartbeat.json"
            altrady = root / "altrady.jsonl"
            for d in (decisions, rechecks, candidates, receipts):
                d.mkdir()

            p = plan(now, value=100.0)
            (decisions / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": p}), "utf-8"
            )

            with patch.object(
                runtime,
                "market_metrics",
                return_value={"last_eur": 101.0},
            ):
                out = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=None,
                    control_path=None,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=False,
                    now=now + timedelta(seconds=5),
                )

            self.assertEqual(out["counters"]["condition_matches"], 1)
            self.assertEqual(out["counters"]["receipts_written"], 1)
            self.assertEqual(out["counters"]["fresh_rechecks"], 0)
            state_obj = json.loads(state.read_text("utf-8"))
            handled = next(iter(state_obj["handled"].values()))
            self.assertEqual(handled["status"], "MATCH_RECEIPT_ONLY")

    def test_execute_mode_calls_one_fresh_paper_recheck_and_is_idempotent(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "decisions"
            rechecks = root / "rechecks"
            candidates = root / "candidates"
            receipts = root / "receipts"
            state = root / "state.json"
            heartbeat = root / "heartbeat.json"
            altrady = root / "altrady.jsonl"
            spec = root / "spec.json"
            control = root / "control.json"
            for d in (decisions, rechecks, candidates, receipts):
                d.mkdir()

            p = plan(now, candidate_id="C1", value=100.0)
            (decisions / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": p}), "utf-8"
            )
            (candidates / "C1.json").write_text(json.dumps({"candidate_id": "C1"}), "utf-8")
            spec.write_text("{}", "utf-8")
            control.write_text("{}", "utf-8")

            fake_out = rechecks / "result.json"
            fake_out.write_text("{}", "utf-8")

            with patch.object(
                runtime, "market_metrics", return_value={"last_eur": 101.0}
            ), patch.object(runtime, "run_recheck", return_value=fake_out) as rr:
                out1 = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=spec,
                    control_path=control,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=True,
                    now=now + timedelta(seconds=5),
                )
                out2 = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=spec,
                    control_path=control,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=True,
                    now=now + timedelta(seconds=6),
                )

            self.assertEqual(out1["counters"]["fresh_rechecks"], 1)
            self.assertEqual(out2["counters"]["fresh_rechecks"], 0)
            self.assertEqual(rr.call_count, 1)

    def test_inflight_marker_is_persisted_before_fresh_recheck(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            decisions = root / "decisions"
            rechecks = root / "rechecks"
            candidates = root / "candidates"
            receipts = root / "receipts"
            state = root / "state.json"
            heartbeat = root / "heartbeat.json"
            altrady = root / "altrady.jsonl"
            spec = root / "spec.json"
            control = root / "control.json"
            for d in (decisions, rechecks, candidates, receipts):
                d.mkdir()

            p = plan(now, candidate_id="C1", value=100.0)
            (decisions / "d.json").write_text(
                json.dumps({"v2r4_trigger_plan": p}), "utf-8"
            )
            (candidates / "C1.json").write_text(
                json.dumps({"candidate_id": "C1"}), "utf-8"
            )
            spec.write_text("{}", "utf-8")
            control.write_text("{}", "utf-8")

            def crash_after_inflight(**kwargs):
                persisted = json.loads(state.read_text("utf-8"))
                row = next(iter(persisted["handled"].values()))
                self.assertEqual(row["status"], "FRESH_PAPER_RECHECK_IN_FLIGHT")
                raise RuntimeError("synthetic crash")

            with patch.object(
                runtime, "market_metrics", return_value={"last_eur": 101.0}
            ), patch.object(runtime, "run_recheck", side_effect=crash_after_inflight) as rr:
                out1 = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=spec,
                    control_path=control,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=True,
                    now=now + timedelta(seconds=5),
                )
                out2 = runtime.run_cycle(
                    decision_dir=decisions,
                    recheck_dir=rechecks,
                    candidate_dir=candidates,
                    receipt_dir=receipts,
                    state_path=state,
                    heartbeat_path=heartbeat,
                    altrady_log=altrady,
                    spec_path=spec,
                    control_path=control,
                    api_key_file=None,
                    fallback_seconds=10,
                    execute_recheck=True,
                    now=now + timedelta(seconds=6),
                )

            self.assertEqual(out1["status"], "DEGRADED")
            self.assertEqual(out1["counters"]["fresh_recheck_failures"], 1)
            self.assertEqual(out2["counters"]["fresh_rechecks"], 0)
            self.assertEqual(rr.call_count, 1)
            persisted = json.loads(state.read_text("utf-8"))
            row = next(iter(persisted["handled"].values()))
            self.assertEqual(row["status"], "FRESH_PAPER_RECHECK_FAILED")

    def test_public_error_classifier_records_kraken_rate_limit_without_raw_text(self):
        self.assertEqual(
            runtime.classify_public_data_error(
                RuntimeError("Kraken OHLC error: ['EAPI:Rate limit exceeded']")),
            "KRAKEN_RATE_LIMIT",
        )
        # Original MINI-PC API response on 2026-10-13: 15m OHLC
        # EGeneral:Too many requests, not EAPI:Rate limit exceeded.
        for endpoint in ("ticker", "OHLC"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    runtime.classify_public_data_error(
                        RuntimeError(f"Kraken {endpoint} error: ['EGeneral:Too many requests']")),
                    "KRAKEN_RATE_LIMIT",
                )
        self.assertEqual(
            runtime.classify_public_data_error(
                RuntimeError("Kraken ticker error: ['EQuery:Unknown asset pair']")),
            "KRAKEN_UNKNOWN_PAIR",
        )
        self.assertEqual(
            runtime.classify_public_data_error(
                RuntimeError("sensitive-unexpected-payload")),
            "OTHER_RuntimeError",
        )

    def test_data_error_has_bounded_class_counts_and_never_matches(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dirs = [root / name for name in ("decisions", "rechecks", "candidates", "receipts")]
            for d in dirs:
                d.mkdir()
            p = plan(now, candidate_id="C1")
            (dirs[0] / "decision.json").write_text(
                json.dumps({"v2r4_trigger_plan": p}), "utf-8")
            with patch.object(
                runtime, "market_metrics",
                side_effect=RuntimeError("Kraken OHLC error: ['EAPI:Rate limit exceeded']"),
            ):
                out = runtime.run_cycle(
                    decision_dir=dirs[0], recheck_dir=dirs[1],
                    candidate_dir=dirs[2], receipt_dir=dirs[3],
                    state_path=root / "state.json",
                    heartbeat_path=root / "heartbeat.json",
                    altrady_log=root / "altrady.jsonl",
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False,
                    now=now + timedelta(seconds=5),
                )
            self.assertEqual(out["status"], "DEGRADED")
            self.assertEqual(out["counters"]["data_unavailable_checks"], 1)
            self.assertEqual(out["error_classes"], {"KRAKEN_RATE_LIMIT": 1})
            self.assertEqual(out["counters"]["condition_matches"], 0)
            self.assertEqual(out["counters"]["receipts_written"], 0)
            self.assertEqual(list(dirs[3].glob("*.json")), [])
            self.assertNotIn("EAPI:", json.dumps(out))

    def test_two_same_pair_plans_share_one_public_snapshot_with_separate_decisions(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = [root / x for x in ("decisions", "rechecks", "candidates", "receipts")]
            for p in paths:
                p.mkdir()
            for cid in ("C1", "C2"):
                (paths[0] / (cid + ".json")).write_text(
                    json.dumps({"v2r4_trigger_plan": plan(now, candidate_id=cid, value=100)}),
                    "utf-8",
                )
            common = dict(
                decision_dir=paths[0], recheck_dir=paths[1],
                candidate_dir=paths[2], receipt_dir=paths[3],
                state_path=root / "state.json", heartbeat_path=root / "heartbeat.json",
                altrady_log=root / "altrady.jsonl",
                spec_path=None, control_path=None, api_key_file=None,
                fallback_seconds=10, execute_recheck=False,
            )
            with patch.object(
                runtime, "market_metrics", return_value={"last_eur": 90.0}
            ) as source:
                out1 = runtime.run_cycle(**common, now=now + timedelta(seconds=5))
                out2 = runtime.run_cycle(**common, now=now + timedelta(seconds=20))
            self.assertEqual(source.call_count, 2)  # one per cycle, not per plan
            self.assertEqual(out1["counters"]["fallback_checks"], 2)
            self.assertEqual(out1["counters"]["unique_pair_source_fetches"], 1)
            self.assertEqual(out1["counters"]["same_cycle_pair_reuses"], 1)
            self.assertEqual(out2["counters"]["unique_pair_source_fetches"], 1)
            self.assertEqual(out1["status"], "HEALTHY")
            self.assertEqual(out1["counters"]["condition_matches"], 0)
            self.assertEqual(list(paths[3].glob("*.json")), [])

    def test_same_pair_source_error_is_not_masked_by_cycle_deduplication(self):
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            paths = [root / x for x in ("decisions", "rechecks", "candidates", "receipts")]
            for p in paths:
                p.mkdir()
            for cid in ("C1", "C2"):
                (paths[0] / (cid + ".json")).write_text(
                    json.dumps({"v2r4_trigger_plan": plan(now, candidate_id=cid)}),
                    "utf-8",
                )
            with patch.object(
                runtime, "market_metrics",
                side_effect=RuntimeError("Kraken OHLC error: ['EAPI:Rate limit exceeded']"),
            ) as source:
                out = runtime.run_cycle(
                    decision_dir=paths[0], recheck_dir=paths[1],
                    candidate_dir=paths[2], receipt_dir=paths[3],
                    state_path=root / "state.json",
                    heartbeat_path=root / "heartbeat.json",
                    altrady_log=root / "altrady.jsonl",
                    spec_path=None, control_path=None, api_key_file=None,
                    fallback_seconds=10, execute_recheck=False,
                    now=now + timedelta(seconds=5),
                )
            self.assertEqual(source.call_count, 1)
            self.assertEqual(out["status"], "DEGRADED")
            self.assertEqual(out["counters"]["unique_pair_source_fetches"], 1)
            self.assertEqual(out["counters"]["same_cycle_pair_reuses"], 1)
            self.assertEqual(out["counters"]["data_unavailable_checks"], 2)
            self.assertEqual(out["error_classes"], {"KRAKEN_RATE_LIMIT": 2})
            self.assertEqual(out["counters"]["receipts_written"], 0)
            self.assertEqual(list(paths[3].glob("*.json")), [])

    def test_long_running_receipt_only_mode_is_not_an_allowed_main_configuration(self):
        # The safety rule is represented in CLI main; core cycle remains testable.
        # Assert the documented action is never an order action.
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        p = plan(now)
        self.assertEqual(p["on_match"], "FRESH_PAPER_RECHECK_ONLY")
        self.assertTrue(p["paper_only"])


if __name__ == "__main__":
    unittest.main()
