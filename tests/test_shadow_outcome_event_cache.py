import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


source = Path(__file__).resolve().parents[1] / "tools/v2r4-ws-shadow-outcome-tracker.py"
spec = importlib.util.spec_from_file_location("tracker", source)
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


class ShadowOutcomeCacheTest(unittest.TestCase):
    def test_archive_and_changed_new_deleted_or_incomplete_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            events, outcomes = root / "events", root / "outcomes"
            events.mkdir()
            outcomes.mkdir()
            now = datetime.now(timezone.utc)
            state = tracker.load_state(root / "state", now)
            cache = {}
            event = dict(kind="V2R4_WS_SHADOW_DISCOVERY", observed_at_utc=tracker.iso(now), last_eur=5)
            for index in range(5000):
                row = dict(event, pair=f"{index}/EUR")
                (events / f"{index}.json").write_text(json.dumps(row))
                (outcomes / (tracker.event_id(row) + ".json")).write_text("{}")

            def step():
                with patch.object(tracker, "load_json", wraps=tracker.load_json) as reads:
                    tracker.enroll_events(state, events, outcomes, now, cache)
                    return reads.call_count

            self.assertEqual(step(), 5000)
            self.assertEqual(step(), 0)
            (events / "0.json").unlink()
            (outcomes / (tracker.event_id(dict(event, pair="1/EUR")) + ".json")).unlink()
            (events / "2.json").write_text(json.dumps(dict(event, pair="REPLACEMENT/EUR")))
            (events / "new.json").write_text("{")
            self.assertEqual(step(), 3)
            self.assertNotIn("0.json", cache)
            self.assertEqual(len(state["active"]), 2)
            (events / "new.json").write_text(json.dumps(dict(event, pair="NEW/EUR")))
            self.assertEqual(step(), 1)
            self.assertEqual(len(state["active"]), 3)
            self.assertEqual(step(), 0)
