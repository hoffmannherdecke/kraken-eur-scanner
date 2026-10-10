"""Offline-only checks for a strict 4-case / 8-real-HTTP-call V3-A research budget."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paper_evaluator import v3_bounded_four_candidate_compare as batch


class V3BoundedFourCandidateTests(unittest.TestCase):
    def fixture(self, directory, n=4, duplicate_pair=False):
        root = Path(directory)
        stage = root/"Runtime"/"v2r4-paper-stage-d8b35a8ec2e6"
        queue = stage/"handoff_queue"
        queue.mkdir(parents=True)
        (root/"Secrets").mkdir()
        (root/"Secrets"/"openai-api-key.txt").write_text("MOCK_ONLY_RESEARCH_API_TOKEN_NOT_REAL_1234")
        t = datetime(2026, 10, 10, 23, 40, tzinfo=timezone.utc)
        control = {
            "series_id": batch.EXPECTED_SERIES,
            "enabled": True,
            "paper_only": True,
            "real_money_actions_enabled": False,
            "series_started_at_utc": (t - timedelta(hours=2)).isoformat(),
            "strategy_revision": batch.REVISION,
        }
        spec = {
            "strategy_revision": batch.REVISION,
            "entry": {"scout_notional_eur": 50, "stage2_notional_eur": 50},
            "fees": {"taker_pct_per_side": 0.6},
        }
        (stage/"paper_strategy_spec.json").write_text(json.dumps(spec))
        names = ["XBT", "ETH", "SOL", "ADA"]
        for i in range(n):
            coin = "XBT" if duplicate_pair else names[i]
            pair = coin + "/EUR"
            tag = coin + "-EUR"
            event = t + timedelta(seconds=10)
            run_id = 100 + i
            event_ts = int(event.timestamp())
            candidate = {
                "candidate_id": event.strftime("%Y%m%d-%H%M%S") + "-" + tag + "-r" + str(run_id),
                "queue_id": f"{run_id}:{tag}:{event_ts}",
                "source_scanner_run_id": run_id,
                "event_time_utc": event.isoformat(),
                "event_ts": event_ts,
                "pair": pair,
                "altname": coin + "EUR",
                "action": "REVIEW_ONLY_NOT_ORDER",
                "scanner_candidate": {},
                "scanner_market_context": {},
            }
            (queue/(candidate["candidate_id"] + ".json")).write_text(json.dumps(candidate))
        return root, stage, control, t

    @staticmethod
    def decision():
        return {
            "decision": "REJECT", "setup_lane": "NONE", "reason_codes": ["NO_AT_TIME_CONFIRMATION"],
            "missing_triggers": [], "stop_eur": None, "ttl_minutes": 0,
            "expected_remaining_move_pct": None, "risk_reward_after_costs": None,
            "stage2_trigger_eur": None, "stage2_ttl_minutes": 0,
            "watch_conditions": [],
        }

    def mocks(self, stage, control, t, ai_func):
        ticker = {"ask": 10.0, "bid": 9.99, "spread_pct": 0.1, "last": 9.995}
        return (
            patch.object(batch, "discover_active_paper_runtime", return_value=(stage, control)),
            patch.object(batch, "freeze_runtime_provenance", return_value={"frozen": "hash"}),
            patch.object(batch.evaluate, "kraken_ticker", return_value=ticker),
            patch.object(batch, "build_context", return_value={"kraken_pair_metadata": {
                "available": True, "status": "online", "ordermin": "0.001", "costmin": "0.5"}}),
            patch.object(batch, "fetch_public_entry_evidence", return_value={
                "kind": "SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
                "known_at_utc": t.isoformat(), "status": "COMPLETE"}),
            patch.object(batch, "attach_to_future_evaluator",
                         side_effect=lambda c, ctx, evidence, at: {**ctx, "candidate_entry_evidence": evidence}),
            patch.object(batch, "now_utc", return_value=t.isoformat()),
            patch.object(batch.evaluate, "call_evaluator", side_effect=ai_func),
        )

    def test_four_distinct_new_candidates_cap_actual_http_calls_at_eight(self):
        with tempfile.TemporaryDirectory() as d:
            root, stage, control, t = self.fixture(d)
            ticker_snapshot = []
            attempts = []
            def evaluator(c, current, ctx, spec, ctl):
                # Calls the intercepted external OpenAI transport one time.
                batch.evaluate.http_json("https://api.openai.com/v1/responses", "POST")
                ticker_snapshot.append((c["candidate_id"], id(current),
                                        "candidate_entry_evidence" in ctx))
                attempts.append(c["candidate_id"])
                return self.decision(), {"response_id": "TEST"}
            def http(url, method="GET", headers=None, body=None, timeout=30):
                return {"id": "MOCK"}
            report = root/"v3-research-report.json"
            patches = self.mocks(stage, control, t + timedelta(seconds=10), evaluator)
            from contextlib import ExitStack
            with ExitStack() as stack:
                for patcher in patches: stack.enter_context(patcher)
                stack.enter_context(patch.object(batch.evaluate, "http_json", side_effect=http))
                result = batch.run_batch(root, root, batch.EXPECTED_SERIES, report, 0,
                                         now_fn=lambda: t + timedelta(seconds=10))
            self.assertEqual(result["completed_comparisons"], 4)
            self.assertEqual(result["actual_model_http_requests_reserved"], 8)
            self.assertEqual(len(result["cases"]), 4)
            self.assertEqual(len(set(x["pair"] for x in result["cases"])), 4)
            self.assertEqual(result["orders"], 0)
            self.assertFalse(result["paper_state_changed"])
            self.assertEqual(len(ticker_snapshot), 8)
            for i in range(0, 8, 2):
                self.assertEqual(ticker_snapshot[i][0], ticker_snapshot[i+1][0])
                self.assertEqual(ticker_snapshot[i][1], ticker_snapshot[i+1][1])
                self.assertEqual(ticker_snapshot[i][2:], (False,))
                self.assertEqual(ticker_snapshot[i+1][2:], (True,))
            ledger = json.loads(report.read_text())
            self.assertEqual(ledger["actual_model_http_requests_reserved"], 8)
            with self.assertRaisesRegex(ValueError, "EXISTING_REPORT"):
                batch.run_batch(root, root, batch.EXPECTED_SERIES, report, 0,
                                now_fn=lambda: t + timedelta(seconds=10))

    def test_internal_retries_are_counted_instead_of_adding_hidden_paid_calls(self):
        with tempfile.TemporaryDirectory() as d:
            root, stage, control, t = self.fixture(d, n=1)
            def evaluator(*args):
                # Simulate frozen evaluator retry on failure.
                for _ in range(3):
                    batch.evaluate.http_json("https://api.openai.com/v1/responses", "POST")
                return self.decision(), {}
            report = root/"report.json"
            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in self.mocks(stage, control, t + timedelta(seconds=10), evaluator):
                    stack.enter_context(p)
                stack.enter_context(patch.object(batch.evaluate, "http_json", return_value={}))
                result = batch.run_batch(root, root, batch.EXPECTED_SERIES, report, 0,
                                         now_fn=lambda: t + timedelta(seconds=10))
            self.assertEqual(result["actual_model_http_requests_reserved"], 2)
            self.assertEqual(result["completed_comparisons"], 0)
            self.assertEqual(result["cases"][0]["status"], "STOP_MODEL_BUDGET")
            self.assertEqual(result["status"], "STOPPED_PRESERVE_BUDGET")

    def test_source_unavailable_does_not_consume_model_budget(self):
        with tempfile.TemporaryDirectory() as d:
            root, stage, control, t = self.fixture(d, n=1)
            report = root/"report.json"
            from contextlib import ExitStack
            with ExitStack() as stack:
                for p in self.mocks(stage, control, t + timedelta(seconds=10),
                                    lambda *args: self.fail("NO MODEL WHEN SOURCE MISSING")):
                    stack.enter_context(p)
                stack.enter_context(patch.object(batch, "fetch_public_entry_evidence",
                                                side_effect=ValueError("STALE")))
                result = batch.run_batch(root, root, batch.EXPECTED_SERIES, report, 0,
                                         now_fn=lambda: t + timedelta(seconds=10))
            self.assertEqual(result["completed_comparisons"], 0)
            self.assertEqual(result["actual_model_http_requests_reserved"], 0)
            self.assertEqual(result["cases"][0]["status"], "SKIPPED_INPUT_UNAVAILABLE")
            self.assertEqual(result["cases"][0]["phase"], "COIN_ENTRY_EVIDENCE")

    def test_no_repeat_pair_and_no_future_events(self):
        with tempfile.TemporaryDirectory() as d:
            root, stage, control, t = self.fixture(d, n=4, duplicate_pair=True)
            queue = stage/"handoff_queue"
            result = batch.eligible_handoffs(queue, t, control, set(), set(),
                                              t + timedelta(seconds=20))
            self.assertEqual(len(result), 4)
            selection = batch.eligible_handoffs(queue, t, control, set(), {"XBT/EUR"},
                                                t + timedelta(seconds=20))
            self.assertEqual(selection, [])
            future = batch.eligible_handoffs(queue, t, control, set(), set(), t)
            self.assertEqual(len(future), 0)
            too_old = batch.eligible_handoffs(queue, t, control, set(), set(),
                                              t + timedelta(seconds=1100))
            self.assertEqual(too_old, [])

    def test_frozen_production_spec_accepts_exact_fee_and_rejects_relaxation(self):
        # Regression for the 2026-10-10 real Mini-PC block: the canonical
        # spec uses "fees", never "fee". Test the committed production spec
        # rather than a fabricated fixture alone.
        production_spec = json.loads(
            (Path(__file__).resolve().parents[1] /
             "research/v2r4/paper_strategy_spec_v2r4_release_candidate.json")
            .read_text("utf-8"))
        batch.verify_frozen_strategy_spec(production_spec)
        self.assertEqual(production_spec["fees"]["taker_pct_per_side"], 0.6)
        for field, replacement in (
                ("fees", {"taker_pct_per_side": 0.0}),
                ("fees", {"taker_pct_per_side": 0.5}),
                ("fees", {}),
                ("entry", {"scout_notional_eur": 100, "stage2_notional_eur": 50})):
            changed = {**production_spec, field: replacement}
            with self.assertRaisesRegex(ValueError, "SIZING_FEE_OR_REVISION_DRIFT_STOP"):
                batch.verify_frozen_strategy_spec(changed)

    def test_pinned_series_and_budget_window_cannot_be_overridden(self):
        with tempfile.TemporaryDirectory() as d:
            root, stage, control, t = self.fixture(d, n=1)
            with self.assertRaisesRegex(ValueError, "UNREVIEWED_SERIES"):
                batch.run_batch(root, root, "PAPER-V2R4-UNAUTHORIZED", root/"report.json", 0)
            with self.assertRaisesRegex(ValueError, "WAIT_WINDOW_INVALID"):
                batch.run_batch(root, root, batch.EXPECTED_SERIES, root/"report.json", 999)

if __name__ == "__main__":
    unittest.main()
