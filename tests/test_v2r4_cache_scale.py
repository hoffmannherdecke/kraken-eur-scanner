"""Synthetic size/parity probe based on original-host reported counts (not live host CPU).
No real trading data, model, network, private files or runtime modifications.
"""
from __future__ import annotations
import importlib.util
import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from paper_evaluator import v2r4_wait_runtime as wait
from tests.test_v2r4_wait_runtime import plan

ROOT = Path(__file__).resolve().parents[1]

def candidates():
    spec = importlib.util.spec_from_file_location("perf_candidate_tool", ROOT/"tools"/"v2r4-paper-local-runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class V2R4CacheScaleOffline(unittest.TestCase):
    def test_candidate_16907_second_sweep_decodes_zero(self):
        mod = candidates()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = json.dumps({"kind":"V2R4_WS_SHADOW_DISCOVERY","pair":"BTC/EUR"})
            for i in range(16907):
                (root/f"{i:05d}.json").write_text(payload, "utf-8")
            files = sorted(root.glob("*.json"))
            self.assertEqual(len(files),16907)
            t=time.perf_counter()
            baseline=sum(mod.load_json(p)["kind"]=="V2R4_WS_SHADOW_DISCOVERY" for p in files)
            baseline_sec=time.perf_counter()-t
            cache=mod._UnchangedEventCache()
            with patch.object(mod,"load_json",wraps=mod.load_json) as loader:
                first=sum(cache.read(p)["kind"]=="V2R4_WS_SHADOW_DISCOVERY" for p in files)
                self.assertEqual(loader.call_count,16907)
                loader.reset_mock()
                t=time.perf_counter()
                second=sum(cache.read(p)["kind"]=="V2R4_WS_SHADOW_DISCOVERY" for p in files)
                second_sec=time.perf_counter()-t
                loader.assert_not_called()
            self.assertEqual((baseline,first,second),(16907,16907,16907))
            self.assertLessEqual(cache.bytes_cached,cache.byte_budget)
            print(f"OFFLINE_CANDIDATE: 16907 records; uncached={baseline_sec:.3f}s; warm_cache={second_sec:.3f}s; repeat_decodes=0")

    def test_candidate_warm_identity_and_source_revision_parity(self):
        mod = candidates()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"event.json"
            event = {
                "kind": "V2R4_WS_SHADOW_DISCOVERY",
                "pair": "BTC/EUR",
                "observed_at_utc": "2026-10-17T07:00:00Z",
                "source_pair_received_at_utc": "2026-10-17T07:00:01Z",
                "last_eur": 101,
            }
            path.write_text(json.dumps(event), "utf-8")
            cache = mod._UnchangedEventCache()
            with patch.object(mod, "parse_utc", wraps=mod.parse_utc) as clock, \
                 patch.object(mod, "event_id", wraps=mod.event_id) as digest:
                first_record, first_identity = cache.read_prepared(path)
                self.assertEqual(first_record, event)
                self.assertEqual(first_identity[1], mod.event_id(event))
                digest.reset_mock()
                clock.reset_mock()
                for _ in range(5):
                    self.assertEqual(cache.read_prepared(path), (event, first_identity))
                    self.assertEqual(cache.read(path), event)
                clock.assert_not_called()
                digest.assert_not_called()
                # A corrected file MUST be reconsidered, never suppressed as "seen".
                event["last_eur"] = 10102
                event["observed_at_utc"] = "2026-10-17T07:00:02Z"
                path.write_text(json.dumps(event), "utf-8")
                corrected_record, corrected_identity = cache.read_prepared(path)
                self.assertEqual(corrected_record, event)
                self.assertNotEqual(corrected_identity, first_identity)
                self.assertEqual(clock.call_count, 1)
                self.assertEqual(digest.call_count, 1)
                # Corrupt-to-corrected timestamps are retried after source revision.
                event["observed_at_utc"] = "bad-date"
                path.write_text(json.dumps(event), "utf-8")
                self.assertEqual(cache.read_prepared(path)[1], (None, None))
                event["observed_at_utc"] = "2026-10-17T07:00:04Z"
                path.write_text(json.dumps(event), "utf-8")
                self.assertEqual(cache.read_prepared(path)[1][1], mod.event_id(event))

    def test_wait_4767_four_active_second_sweep_decodes_zero(self):
        at=datetime(2026,10,17,7,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/"decisions";d.mkdir()
            r=Path(td)/"rechecks";r.mkdir()
            inactive=json.dumps({"decision":"REJECT"})
            for i in range(4767):
                record=json.dumps({"v2r4_trigger_plan":plan(at,candidate_id=f"WAIT-{i}")}) if i<4 else inactive
                (d/f"{i:05d}.json").write_text(record,"utf-8")
            t=time.perf_counter()
            expected=wait.discover_plans(d,r,now=at)
            baseline_sec=time.perf_counter()-t
            self.assertEqual(len(expected),4)
            cache=wait._ReadOnlyWaitPlanCache()
            with patch.object(wait,"read_json",wraps=wait.read_json) as loader:
                first=wait.discover_plans(d,r,now=at,file_cache=cache)
                self.assertEqual(loader.call_count,4767)
                loader.reset_mock()
                t=time.perf_counter()
                second=wait.discover_plans(d,r,now=at,file_cache=cache)
                second_sec=time.perf_counter()-t
                loader.assert_not_called()
            self.assertEqual(first,expected)
            self.assertEqual(second,expected)
            self.assertLessEqual(cache.bytes_cached,cache.byte_budget)
            print(f"OFFLINE_WAIT: 4767 records, 4 plans; uncached={baseline_sec:.3f}s; warm_cache={second_sec:.3f}s; repeat_decodes=0")

    def test_tiny_byte_budgets_evict_without_dropping_sources(self):
        mod=candidates()
        at=datetime(2026,10,17,7,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            raw=json.dumps({"kind":"V2R4_WS_SHADOW_DISCOVERY","pair":"BTC/EUR","padding":"x"*30})
            cp=[d/f"candidate-{i}.json" for i in range(3)]
            for p in cp:p.write_text(raw,"utf-8")
            cache=mod._UnchangedEventCache(limit=50,byte_budget=2*cp[0].stat().st_size)
            for p in cp:self.assertEqual(cache.read(p)["pair"],"BTC/EUR")
            self.assertEqual(len(cache.entries),2)
            self.assertNotIn(cp[0],cache.entries)
            self.assertLessEqual(cache.bytes_cached,cache.byte_budget)
            self.assertEqual(cache.read(cp[0])["pair"],"BTC/EUR")

            wd=d/"decision";wr=d/"recheck";wd.mkdir();wr.mkdir()
            wp=[wd/f"{i}.json" for i in range(3)]
            for i,p in enumerate(wp):p.write_text(json.dumps({"v2r4_trigger_plan":plan(at,candidate_id=f"C-{i}")}),"utf-8")
            budget=2*max(p.stat().st_size for p in wp)
            wcache=wait._ReadOnlyWaitPlanCache(limit=50,byte_budget=budget)
            actual=wait.discover_plans(wd,wr,now=at,file_cache=wcache)
            self.assertEqual(len(actual),3)
            self.assertEqual(len(wcache.entries),2)
            self.assertNotIn(wp[0],wcache.entries)
            self.assertLessEqual(wcache.bytes_cached,wcache.byte_budget)
            self.assertEqual(actual,wait.discover_plans(wd,wr,now=at))

if __name__=="__main__":
    unittest.main()
