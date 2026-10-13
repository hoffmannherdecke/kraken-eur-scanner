"""Missed moves count only from mature no-BUY price paths, never pseudo trades."""
import json,tempfile,unittest
from datetime import timedelta
from pathlib import Path
from paper_evaluator.v3_paper_missed_opportunity_followup_v1 import followup_no_buy
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import timestamp
from tests.test_v3_paper_minipc_one_candidate_v1 import fixture,fake_acquire,SID
from tests.test_v2r4_v3_entry_handoff_probe import dt

class NoBuyFollowupTests(unittest.TestCase):
    def test_captures_genuine_post_scan_move_without_fake_net_returns(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp);journal=r/"journal";b=r/"budgets";journal.mkdir();b.mkdir()
            c=fixture()[0]
            one_candidate(candidate=c,series_id=SID,local_receipts=journal,
                          model_reservations=b,acquire=fake_acquire,
                          clock=lambda:dt(12))
            signal=timestamp(c["event_time_utc"])
            first=signal.replace(second=0,microsecond=0)
            if first<signal:first+=timedelta(minutes=1)
            bars=[]
            for i in range(360):
                price=10+(i/359)*1.5
                bars.append({"start_at_utc":(first+timedelta(minutes=i)).isoformat(),
                             "open":price,"high":price+0.03,
                             "low":price-0.03,"close":price})
            captured={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                      "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":"XBT/EUR",
                      "no_future_backfill":True,"historical_late_backfill_excluded":True,
                      "source_snapshots_with_conflicts":False,
                      "max_original_snapshot_lag_minutes":15,
                      "captured_at_utc":(first+timedelta(minutes=361)).isoformat(),
                      "closed_bars":bars}
            outcome=followup_no_buy(journal=journal,series_id=SID,
                    candidate_id=c["candidate_id"],captured_1m=captured,hours=6)
            self.assertEqual(outcome["event_result"],"MATURE_COMPLETE")
            self.assertGreater(outcome["mfe_pct"],12)
            self.assertIsNone(outcome["net_pnl_eur"])
            records=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            follow=[x for x in records if x["phase"]=="FOLLOWUP_6H"]
            self.assertEqual(len(follow),1)
            self.assertEqual(follow[0]["data"]["source_status"],
                "NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL")
            self.assertEqual(followup_no_buy(journal=journal,series_id=SID,
                    candidate_id=c["candidate_id"],captured_1m=captured,hours=6)["status"],
                "NO_BUY_FOLLOWUP_ALREADY_FINAL")

    def test_direct_fake_closed_1m_path_fails_before_followup_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);j=root/"journal";b=root/"budgets";j.mkdir();b.mkdir()
            c=fixture()[0]
            one_candidate(candidate=c,series_id=SID,
                          local_receipts=j,model_reservations=b,
                          acquire=fake_acquire,clock=lambda:dt(12))
            old_files={p.name for p in j.glob("*.json")}
            at=timestamp(c["event_time_utc"])+timedelta(hours=7)
            fake={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                  "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":"XBT/EUR",
                  "captured_at_utc":at.isoformat(),"closed_bars":[]}
            for extra in ({},{"no_future_backfill":True,
                              "historical_late_backfill_excluded":True,
                              "source_snapshots_with_conflicts":False,
                              "max_original_snapshot_lag_minutes":60}):
                with self.assertRaisesRegex(ValueError,"prospective|witness"):
                    followup_no_buy(journal=j,series_id=SID,
                        candidate_id=c["candidate_id"],
                        captured_1m={**fake,**extra},hours=6)
            self.assertEqual({p.name for p in j.glob("*.json")},old_files)

    def test_gap_is_not_0_return_and_recovery_is_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp);journal=r/"journal";b=r/"budgets";journal.mkdir();b.mkdir()
            c=fixture()[0]
            one_candidate(candidate=c,series_id=SID,local_receipts=journal,
                          model_reservations=b,acquire=fake_acquire,
                          clock=lambda:dt(12))
            observed=timestamp(c["event_time_utc"])+timedelta(hours=6,minutes=10)
            cap={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1","source":"KRAKEN_SPOT_EUR_PUBLIC",
                 "pair":"XBT/EUR","captured_at_utc":observed.isoformat(),
                 "no_future_backfill":True,"historical_late_backfill_excluded":True,
                 "source_snapshots_with_conflicts":False,
                 "max_original_snapshot_lag_minutes":15,
                 "closed_bars":[]}
            self.assertEqual(followup_no_buy(journal=journal,series_id=SID,
                    candidate_id=c["candidate_id"],captured_1m=cap,hours=6)["status"],
                "NO_BUY_1M_GAP_PENDING_RECOVERY")
            cap["captured_at_utc"]=(observed+timedelta(hours=2)).isoformat()
            final=followup_no_buy(journal=journal,series_id=SID,
                    candidate_id=c["candidate_id"],captured_1m=cap,hours=6)
            self.assertEqual(final["event_result"],"CENSORED")
            self.assertIsNone(final["net_pnl_eur"])
if __name__=="__main__":unittest.main()
