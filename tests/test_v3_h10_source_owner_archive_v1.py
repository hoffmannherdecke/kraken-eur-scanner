#!/usr/bin/env python3
"""Regression for original H10 cloud source owner only. No network, DB or keys."""
import copy
import datetime as dt
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tools import v3_h10_source_owner_archive_v1 as archive
from tools.v3_h10_selected_original_receipt_v1 import OriginalEvidenceBlocked

ROOT=Path(__file__).resolve().parents[1]
COHORT=json.loads((ROOT/"research/v3/h10-trader-cohort-v1.json").read_text())


def _batch(name, when):
    stamp=dt.datetime.fromisoformat(when.replace("Z","+00:00"))
    return {"batch_id":name,"cohort_id":COHORT["cohort_id"],
            "capture_path":"GITHUB_BOOTSTRAP_30M","observed_at":when,
            "created_at":archive.iso(stamp+dt.timedelta(seconds=8)),
            "wallet_count":26,"success_count":26,"error_count":0}


def _fills():
    addresses=[x["address"] for x in COHORT["traders"] if x["role"]=="PRIMARY"][:3]
    rows=[]
    for index,address in enumerate(addresses):
        rows.append({"event_id":hashlib.sha256(f"h10-v1-{index}".encode()).hexdigest(),
                     "cohort_id":COHORT["cohort_id"],"cohort_role":"PRIMARY",
                     "address":address,"coin":"BTC",
                     "fill_time":"2026-10-12T13:40:00Z",
                     "first_seen_at":"2026-10-12T13:47:10Z",
                     "first_seen_batch_id":"a","direction":"Open Long","side":"B",
                     "px":10000,"sz":1,"oid":str(index),"tid":str(index),
                     "tx_hash":"0x"+"a"*64})
    return rows


class ArchiveSourceOwnerTests(unittest.TestCase):
    def test_coverage_uses_existing_overlapping_45m_batches(self):
        b=[_batch("a","2026-10-12T13:47:00Z"),
           _batch("b","2026-10-12T14:17:00Z")]
        got=archive.first_complete_known_at(
            b,_fills(),archive.utc("2026-10-12T13:30:00Z"),
            archive.utc("2026-10-12T14:00:00Z"))
        self.assertEqual(archive.iso(got),"2026-10-12T14:17:08.000000Z")
        with self.assertRaisesRegex(OriginalEvidenceBlocked,"NO_COMPLETE_ORIGINAL_WINDOW_COVERAGE"):
            archive.first_complete_known_at(
                b[:1],_fills(),archive.utc("2026-10-12T13:30:00Z"),
                archive.utc("2026-10-12T14:00:00Z"))

    def test_explicit_pagination_not_silent_truncation(self):
        responses=[ [{"event_id":str(i)} for i in range(500)],
                    [{"event_id":"last"}] ]
        requests=[]
        class Resp:
            def __init__(self,items):
                self.items=items
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def read(self):return json.dumps(self.items).encode()
        def fake(req,timeout=None):
            requests.append(req)
            return Resp(responses.pop(0))
        with patch.object(archive.urllib.request,"urlopen",side_effect=fake):
            rows=archive.get_rows("https://example.invalid",{"apikey":"fake"},
                                  "v3_h10_fill_events",{"select":"event_id"},max_rows=1000)
        self.assertEqual(len(rows),501)
        self.assertEqual([r.get_header("Range") for r in requests],["0-499","500-999"])
        self.assertEqual([r.get_header("Range-unit") for r in requests],["items","items"])

    def test_real_http_insert_requires_exact_select_readback(self):
        batches=[_batch("a","2026-10-12T13:47:00Z"),_batch("b","2026-10-12T14:17:00Z")]
        real_rows=_fills()
        after=[]
        def fetch(_base,_headers,table,filters,*,max_rows=5000):
            if table=="v3_h10_fill_events":
                return real_rows if "13%3A30" in str(filters) or "13:30" in str(filters) else []
            if table=="v3_h10_capture_batches":return batches
            if table==archive.TABLE:
                return after[:]
            raise AssertionError(table)
        class Post:
            status=201
            def __enter__(self):return self
            def __exit__(self,*args):return None
        def post(req,timeout=None):
            candidate=json.loads(req.data)
            from tools.v3_h10_selected_original_cloud_protocol_v1 import prepare_source_only_insert
            after.append({**candidate,"received_at_utc":"2026-10-12T14:17:09Z"})
            return Post()
        with patch.object(archive,"get_rows",side_effect=fetch),patch.object(archive.urllib.request,"urlopen",side_effect=post):
            stats=archive.archive_selected_recent_windows(
                base="https://example.invalid",headers={"apikey":"fake"},
                cohort=COHORT,observed_now=archive.utc("2026-10-12T14:18:00Z"))
            self.assertEqual(stats["stored"],1)
            self.assertEqual(stats["candidate_windows"],1)
            self.assertEqual(stats["idempotent"],0)
            self.assertEqual(len(after),1)
            with patch.object(archive.urllib.request,"urlopen",side_effect=AssertionError("no duplicate POST")):
                stats2=archive.archive_selected_recent_windows(
                    base="https://example.invalid",headers={"apikey":"fake"},
                    cohort=COHORT,observed_now=archive.utc("2026-10-12T14:18:00Z"))
            self.assertEqual(stats2["idempotent"],1)

    def test_no_qualified_wallets_never_insert_and_no_backfill(self):
        with patch.object(archive,"get_rows",return_value=_fills()[:2]) as fetch:
            result=archive.archive_selected_recent_windows(
                base="https://example.invalid",headers={},
                cohort=COHORT,observed_now=archive.utc("2026-10-12T14:18:00Z"))
        self.assertEqual(result["stored"],0)
        self.assertEqual(result["candidate_windows"],0)
        self.assertEqual(fetch.call_count,1)  # first eligible window only after cutoff

    def test_no_key_source_api_or_second_schedule(self):
        source=(ROOT/"tools/v3_h10_source_owner_archive_v1.py").read_text()
        for forbidden in ("api.hyperliquid.xyz","model_api","place_order",
                          "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                          "schedule:", "cron:"):
            self.assertNotIn(forbidden,source)
        script=(ROOT/"tools/v3-h10-activity-capture.py").read_text()
        self.assertIn("if path==\"GITHUB_BOOTSTRAP_30M\" and max_wallets is None",script)
        self.assertIn("selected_original_receipts",script)


if __name__=="__main__":unittest.main()
