"""No-network regression of the original WS-shadow archive/relay owner.

Use temporary evidence only: never a real MINI-PC path, token or Supabase endpoint.
"""
import argparse
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


PATH = Path(__file__).resolve().parents[1] / "tools" / "v2r4-shadow-cloud-sync.py"
SPEC = importlib.util.spec_from_file_location("shadow_cloud_sync_under_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ShadowArchiveIncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.event_dir = self.root / "State" / "v2r4-ws-shadow-events"
        self.outcome_dir = self.root / "State" / "v2r4-ws-shadow-outcomes"
        self.event_dir.mkdir(parents=True)
        self.outcome_dir.mkdir(parents=True)
        secret = self.root / "Secrets" / "shadow-evidence-token.txt"
        secret.parent.mkdir()
        secret.write_text("x" * 32, encoding="utf-8")
        self.args = argparse.Namespace(
            trading_root=self.root, endpoint="https://invalid.example.test/no-network",
            once=True, interval_seconds=60,
        )
        self.sent_batches = []

    def event(self, name="A", price=11.0):
        event = {
            "kind": "V2R4_WS_SHADOW_DISCOVERY", "pair": name + "/EUR",
            "observed_at_utc": "2026-10-14T05:00:00Z",
            "source_pair_received_at_utc": "2026-10-14T05:00:01Z",
            "last_eur": price,
        }
        path = self.event_dir / (name + ".json")
        MODULE.atomic_json(path, event)
        return MODULE.event_id(event), path

    def outcome(self, eid, status):
        MODULE.atomic_json(self.outcome_dir / (eid + ".json"), {
            "kind": "V2R4_WS_SHADOW_OUTCOME_V1",
            "status": status, "evidence": {"mfe": 1.3},
        })

    def run_cycle(self, side_effect=None):
        def relay(endpoint, token, records):
            self.sent_batches.append(list(records))
            if side_effect is not None:
                return side_effect(endpoint, token, records)
            return {"ok": True, "accepted": len(records)}
        with mock.patch.object(MODULE, "post_batch", side_effect=relay):
            return MODULE.run_once(self.args)

    def sent_ids(self):
        return [r["event_id"] for batch in self.sent_batches for r in batch]

    def test_acknowledged_unchanged_event_skips_json_read_even_across_restart(self):
        eid, _ = self.event()
        self.assertEqual(self.run_cycle()["status"], "HEALTHY")
        self.assertEqual(self.sent_ids(), [eid])
        self.sent_batches.clear()

        real_read = MODULE.load_json
        def fail_if_evidence_read(path):
            if path.parent in (self.event_dir, self.outcome_dir):
                raise AssertionError("stable evidence JSON must not be reopened")
            return real_read(path)
        with mock.patch.object(MODULE, "load_json", side_effect=fail_if_evidence_read):
            self.assertEqual(self.run_cycle()["status"], "HEALTHY")
        self.assertEqual(self.sent_batches, [])
        self.assertTrue((self.root / "State" / "v2r4-shadow-cloud-sync-state.json").exists())

    def test_late_outcome_is_uploaded_once_and_not_missed(self):
        eid, _ = self.event()
        self.run_cycle()
        self.sent_batches.clear()
        self.outcome(eid, "COMPLETE")
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)
        record = self.sent_batches[0][0]
        self.assertEqual(record["outcome_status"], "COMPLETE")
        self.assertEqual(record["event_id"], eid)
        self.sent_batches.clear()
        self.assertEqual(self.run_cycle()["pending_records"], 0)
        self.assertFalse(self.sent_batches)

    def test_changed_outcome_status_is_relayed(self):
        eid, _ = self.event()
        self.outcome(eid, "INCOMPLETE_TIMEOUT")
        self.run_cycle()
        self.sent_batches.clear()
        self.outcome(eid, "COMPLETE")
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)
        self.assertEqual(self.sent_batches[0][0]["outcome_status"], "COMPLETE")

    def test_relay_failure_cannot_create_false_sent_ack(self):
        eid, _ = self.event()
        def failure(endpoint, token, records):
            raise TimeoutError("offline relay")
        result = self.run_cycle(side_effect=failure)
        self.assertEqual(result["status"], "DEGRADED")
        state = MODULE.load_json(self.root / "State" / "v2r4-shadow-cloud-sync-state.json")
        self.assertNotIn(eid, state["sent"])
        self.sent_batches.clear()
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)
        self.assertEqual(self.sent_ids(), [eid])

    def test_file_replaced_under_same_name_is_reconsidered(self):
        first_id, path = self.event("A", 11.0)
        self.run_cycle()
        self.sent_batches.clear()
        second_id, _ = self.event("A", 12.0)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)
        self.assertEqual(self.sent_ids(), [second_id])

    def test_invalid_index_falls_back_to_full_scan(self):
        eid, _ = self.event()
        self.run_cycle()
        path = self.root / "State" / "v2r4-shadow-cloud-sync-state.json"
        state = MODULE.load_json(path)
        state["event_file_index"] = "corrupted-index"
        MODULE.atomic_json(path, state)
        self.sent_batches.clear()
        self.assertEqual(self.run_cycle()["status"], "HEALTHY")
        self.assertFalse(self.sent_batches)
        self.assertIsInstance(MODULE.load_json(path)["event_file_index"], dict)

    def test_partial_batch_failure_retries_only_unacknowledged(self):
        ids = [self.event(str(i))[0] for i in range(51)]
        def fail_second(endpoint, token, records):
            if len(self.sent_batches) == 2:
                raise TimeoutError("second batch dropped")
            return {"ok": True, "accepted": len(records)}
        self.assertEqual(self.run_cycle(side_effect=fail_second)["status"], "DEGRADED")
        state = MODULE.load_json(self.root / "State" / "v2r4-shadow-cloud-sync-state.json")
        self.assertEqual(len(state["sent"]), 50)
        self.sent_batches.clear()
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)
        self.assertEqual(set(self.sent_ids()), set(ids) - set(state["sent"]))

    def test_bad_outcome_json_is_retried_after_repair(self):
        eid, _ = self.event()
        self.run_cycle()
        (self.outcome_dir / (eid + ".json")).write_text("{", encoding="utf-8")
        self.sent_batches.clear()
        self.assertEqual(self.run_cycle()["uploaded_records"], 0)
        self.outcome(eid, "COMPLETE")
        self.assertEqual(self.run_cycle()["uploaded_records"], 1)

    def test_index_prunes_removed_files(self):
        eid, path = self.event()
        self.run_cycle()
        path.unlink()
        self.assertEqual(self.run_cycle()["status"], "HEALTHY")
        state = MODULE.load_json(self.root / "State" / "v2r4-shadow-cloud-sync-state.json")
        self.assertFalse(state["event_file_index"])
        self.assertIn(eid, state["sent"])

    def test_finish_heartbeat_marks_end_not_beginning(self):
        self.event()
        original = MODULE.collect_records
        def slow_scan(root, state):
            time.sleep(0.035)
            return original(root, state)
        with mock.patch.object(MODULE, "collect_records", side_effect=slow_scan):
            result = self.run_cycle()
        self.assertEqual(result["status"], "HEALTHY")
        self.assertGreaterEqual(result["cycle_duration_seconds"], 0.03)
        self.assertGreater(
            result["checked_at_utc"], result["cycle_started_at_utc"]
        )
        self.assertEqual(
            MODULE.load_json(self.root / "State" / "v2r4-shadow-cloud-sync-heartbeat.json")["checked_at_utc"],
            result["checked_at_utc"],
        )

    def test_no_secret_or_network_when_token_missing(self):
        self.event()
        (self.root / "Secrets" / "shadow-evidence-token.txt").unlink()
        with mock.patch.object(MODULE, "post_batch", side_effect=AssertionError("network")):
            result = MODULE.run_once(self.args)
        self.assertEqual(result["status"], "DEGRADED")
        self.assertFalse(result["real_money_actions"])


if __name__ == "__main__":
    unittest.main()
