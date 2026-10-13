"""No outside IO in CI: Mini-PC closed 1m captures, 6h net outcomes, cloud ACK."""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m,assemble
from paper_evaluator.v3_paper_minipc_followup_v1 import record_horizon
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate,REVISION
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once
from tests.test_v3_paper_minipc_one_candidate_v1 import (
    fixture, fake_acquire, fake_model, valid_approval,SID
)
from tests.test_v2r4_v3_entry_handoff_probe import dt


class MiniPcAndCloudTests(unittest.TestCase):
    def test_public_1m_capture_reuses_existing_source_and_rejects_open_bar(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            from datetime import datetime,timezone
            base=datetime(2026,10,11,10,0,tzinfo=timezone.utc)
            def loader(_):
                rows=[]
                for i in range(12):
                    point=int((base+timedelta(minutes=i)).timestamp())
                    rows.append([point,"10.0","10.2","9.9","10.1","10.1","8.0",10])
                return {"error":[],"result":{"XXBTZEUR":rows,"last":1}}
            tick=[base+timedelta(minutes=11,seconds=5)]
            out=capture_public_1m(pair="XBT/EUR",altname="XBTEUR",
                outdir=root,loader=loader,clock=lambda:tick[0])
            self.assertEqual(out["count"],11) # newest unfinished excluded
            self.assertTrue(Path(out["file"]).exists())
            merged=assemble(snapshots=root,pair="XBT/EUR",
                            entry_at_utc=(base-timedelta(minutes=1)).isoformat(),
                            observed_at_utc=(base+timedelta(minutes=12)).isoformat())
            self.assertEqual(len(merged["closed_bars"]),11)
            self.assertTrue(merged["no_future_backfill"])

    def test_closed_6h_path_matures_and_cloud_ack_does_not_change_series(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);j=root/"journal";b=root/"budgets";j.mkdir();b.mkdir()
            state=one_candidate(candidate=fixture()[0],series_id=SID,
                local_receipts=j,model_reservations=b,approval=valid_approval(),
                model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=fake_model,
                clock=lambda:dt(12),allow_model=True)
            self.assertEqual(state["p4_decision"],"BUY_SCOUT")
            from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import timestamp
            buy=timestamp(dt(12))
            first=buy.replace(second=0,microsecond=0)+timedelta(minutes=1)
            minutes=[{"start_at_utc":(first+timedelta(minutes=i)).isoformat(),
                      "open":10.24,"high":10.26,"low":10.22,"close":10.24}
                     for i in range(360)]
            cap={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                 "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":"XBT/EUR",
                 "no_future_backfill":True,"historical_late_backfill_excluded":True,
                 "source_snapshots_with_conflicts":False,
                 "max_original_snapshot_lag_minutes":15,
                 "captured_at_utc":(first+timedelta(minutes=362)).isoformat(),
                 "closed_bars":minutes}
            out=record_horizon(journal=j,series_id=SID,
                candidate_id=fixture()[0]["candidate_id"],captured_1m=cap,
                horizon_hours=6)
            self.assertEqual(out["economic_estimate_status"],
                "MATURE_ESTIMATED_PAPER_NET_NOT_VERIFIED_FILL")
            self.assertLess(out["net_estimate_eur"],0)
            self.assertFalse(out["source_is_true_exchange_fill"])
            ack_file=root/"cloud_ack.json"
            called=[]
            def post(url,token,payload):
                called.append(payload)
                return {"ok":True,"accepted_receipts":len(payload["receipts"]),
                        "series_id":SID}
            synced=sync_once(journal=j,series_id=SID,
                ack_file=ack_file,token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",post=post)
            self.assertEqual(synced["status"],"V3_RECEIPTS_CLOUD_ACK_VERIFIED")
            self.assertEqual(sync_once(journal=j,series_id=SID,
                ack_file=ack_file,token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",post=post)["count"],0)
            self.assertEqual(len(called),1)

    def test_unverified_assembled_path_cannot_create_buy_followup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);j=root/"journal";b=root/"budgets";j.mkdir();b.mkdir()
            one_candidate(candidate=fixture()[0],series_id=SID,
                local_receipts=j,model_reservations=b,approval=valid_approval(),
                model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=fake_model,
                clock=lambda:dt(12),allow_model=True)
            original_files={p.name for p in j.glob("*.json")}
            from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import timestamp
            at=timestamp(dt(12))+timedelta(hours=7)
            fake={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                  "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":"XBT/EUR",
                  "captured_at_utc":at.isoformat(),"closed_bars":[]}
            for extra in ({},{"no_future_backfill":True,
                              "historical_late_backfill_excluded":True,
                              "source_snapshots_with_conflicts":False,
                              "max_original_snapshot_lag_minutes":60}):
                with self.assertRaisesRegex(ValueError,"prospective|witness"):
                    record_horizon(journal=j,series_id=SID,
                        candidate_id=fixture()[0]["candidate_id"],
                        captured_1m={**fake,**extra},horizon_hours=6)
            self.assertEqual({p.name for p in j.glob("*.json")},original_files)

    def test_crash_abandoned_legacy_temp_does_not_block_subsequent_cloud_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);j=root/"journal";b=root/"budgets";j.mkdir();b.mkdir()
            one_candidate(candidate=fixture()[0],series_id=SID,
                local_receipts=j,model_reservations=b,acquire=fake_acquire,
                clock=lambda:dt(12))
            ack=root/"cloud_ack.json"
            stale=root/"cloud_ack.tmp"
            stale.write_text("incomplete previous crash",encoding="utf-8")
            sent=[]
            def post(url,token,payload):
                sent.append(payload)
                return {"ok":True,"accepted_receipts":len(payload["receipts"]),
                        "series_id":SID}
            out=sync_once(journal=j,series_id=SID,ack_file=ack,
                token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",post=post)
            self.assertEqual(out["status"],"V3_RECEIPTS_CLOUD_ACK_VERIFIED")
            self.assertTrue(ack.exists())
            self.assertEqual(stale.read_text(encoding="utf-8"),
                             "incomplete previous crash")
            again=sync_once(journal=j,series_id=SID,ack_file=ack,
                token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",post=post)
            self.assertEqual(again["count"],0)
            self.assertEqual(len(sent),1)
            self.assertEqual(len(list(root.glob("cloud_ack.json.*.tmp"))),0)

    def test_cloud_failure_keeps_all_receipts_retryable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);j=root/"journal";b=root/"budgets";j.mkdir();b.mkdir()
            one_candidate(candidate=fixture()[0],series_id=SID,
                local_receipts=j,model_reservations=b,acquire=fake_acquire,
                clock=lambda:dt(12))
            with self.assertRaises(ValueError):
                sync_once(journal=j,series_id=SID,ack_file=root/"acked.json",
                    token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",
                    post=lambda *args:{"ok":False})
            self.assertFalse((root/"acked.json").exists())

if __name__=="__main__":
    unittest.main()
