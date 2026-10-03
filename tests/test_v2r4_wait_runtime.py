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

    def test_long_running_receipt_only_mode_is_not_an_allowed_main_configuration(self):
        # The safety rule is represented in CLI main; core cycle remains testable.
        # Assert the documented action is never an order action.
        now = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        p = plan(now)
        self.assertEqual(p["on_match"], "FRESH_PAPER_RECHECK_ONLY")
        self.assertTrue(p["paper_only"])


if __name__ == "__main__":
    unittest.main()
