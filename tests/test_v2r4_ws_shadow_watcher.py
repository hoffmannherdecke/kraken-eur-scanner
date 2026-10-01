import unittest
from datetime import datetime, timedelta, timezone

from paper_evaluator.v2r4_ws_shadow_watcher import (
    process_snapshot,
)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def base_state(now, *, previous_source=None):
    return {
        "schema_version": 1,
        "last_source_written_at_utc": iso(previous_source) if previous_source else None,
        "recovery_epoch": 0,
        "pairs": {
            "TEST/EUR": {
                "samples": [[int((now - timedelta(minutes=10)).timestamp()), 100.0]],
                "last_pair_received_at_utc": None,
                "last_event_ts": 0,
                "last_liquidity_class": "WATCH_ONLY",
            }
        },
        "counters": {
            "snapshots_processed": 0,
            "duplicates_skipped": 0,
            "stale_inputs": 0,
            "gap_recoveries": 0,
            "events_emitted": 0,
        },
    }


def snapshot(now, *, price=102.0, written=None, received=None):
    written = written or now
    received = received or now
    return {
        "schema_version": 1,
        "kind": "MINIPC_KRAKEN_EUR_TICKER_LATEST_V1",
        "written_at_utc": iso(written),
        "universe_sha256": "abc",
        "pair_count": 1,
        "observed_pair_count": 1,
        "pairs": {
            "TEST/EUR": {
                "symbol": "TEST/EUR",
                "received_at_utc": iso(received),
                "bid_eur": price - 0.1,
                "ask_eur": price + 0.1,
                "last_eur": price,
                "spread_pct": 0.196,
                "turnover24_est_eur": 250000.0,
            }
        },
    }


def run(snap, state, now):
    return process_snapshot(
        snap,
        state,
        now=now,
        max_snapshot_age_seconds=15.0,
        max_pair_age_seconds=180.0,
        max_gap_seconds=45.0,
        cooldown_seconds=1800,
        sample_seconds=60,
    )


class V2R4WSShadowWatcherTests(unittest.TestCase):
    def test_fresh_ws_snapshot_can_emit_shadow_event_without_recheck(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        state, events, heartbeat = run(snapshot(now), base_state(now), now)

        self.assertEqual(heartbeat["status"], "HEALTHY")
        self.assertFalse(heartbeat["gap_suppressed"])
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["kind"], "V2R4_WS_SHADOW_DISCOVERY")
        self.assertTrue(event["shadow_only"])
        self.assertTrue(event["paper_only"])
        self.assertFalse(event["fresh_recheck_invoked"])
        self.assertEqual(event["next_action"], "SHADOW_OBSERVE_ONLY")
        self.assertTrue(event["would_request_fresh_recheck"])
        self.assertFalse(event["real_money_actions_enabled"])
        self.assertIn("FAST_10M", event["reasons"])
        self.assertEqual(state["counters"]["events_emitted"], 1)

    def test_stale_global_snapshot_is_rejected(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        old = now - timedelta(seconds=30)
        state, events, heartbeat = run(snapshot(now, written=old), base_state(now), now)

        self.assertEqual(events, [])
        self.assertEqual(heartbeat["status"], "STALE_INPUT")
        self.assertEqual(state["counters"]["stale_inputs"], 1)
        self.assertEqual(state["counters"]["snapshots_processed"], 0)

    def test_duplicate_snapshot_is_not_reprocessed(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        state = base_state(now)
        state["last_source_written_at_utc"] = iso(now)
        state, events, heartbeat = run(snapshot(now), state, now)

        self.assertEqual(events, [])
        self.assertEqual(heartbeat["status"], "DUPLICATE_SKIPPED")
        self.assertEqual(state["counters"]["duplicates_skipped"], 1)

    def test_first_fresh_cycle_after_gap_is_suppressed_then_next_cycle_may_emit(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        state = base_state(now, previous_source=now - timedelta(seconds=120))

        state, events1, heartbeat1 = run(snapshot(now), state, now)
        self.assertEqual(events1, [])
        self.assertTrue(heartbeat1["gap_suppressed"])
        self.assertEqual(state["recovery_epoch"], 1)
        self.assertEqual(state["counters"]["gap_recoveries"], 1)

        later = now + timedelta(seconds=2)
        state, events2, heartbeat2 = run(
            snapshot(later, price=102.1, written=later, received=later),
            state,
            later,
        )
        self.assertFalse(heartbeat2["gap_suppressed"])
        self.assertEqual(len(events2), 1)
        self.assertEqual(events2[0]["recovery_epoch"], 1)

    def test_stale_pair_update_is_not_used_for_discovery(self):
        now = datetime(2026, 10, 1, 6, 0, tzinfo=timezone.utc)
        old_pair = now - timedelta(minutes=5)
        state, events, heartbeat = run(
            snapshot(now, received=old_pair),
            base_state(now),
            now,
        )
        self.assertEqual(events, [])
        self.assertEqual(heartbeat["stale_pairs"], 1)
        self.assertEqual(heartbeat["changed_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
