"""Offline regression tests: no network, secrets, orders, runner or active strategy."""
import unittest
from datetime import datetime, timezone
from paper_evaluator.successor_coin_entry_evidence_v1 import (
    build_entry_evidence, fetch_public_entry_evidence,
)

BASE = 1791550800  # aligned 15m boundary, fixed UTC anchor

def bars(interval, n=24, *, gap=False, spike=1.0):
    span = interval * 60
    result=[]
    for i in range(n):
        ts=BASE - n * span + i * span
        if gap and i == n-3:
            continue
        o=10 + i*0.01
        c=o+0.004
        v=100 * (spike if i == n-1 else 1.0)
        result.append([ts, str(o), str(o+0.07), str(o-0.07), str(c), str(c), str(v), "3"])
    return result

class SuccessorCoinEntryEvidenceTests(unittest.TestCase):
    def test_closed_only_ratios_atr_and_no_trade_authority(self):
        # The final row of each interval is still open at BASE.
        snap={i:bars(i)+[[BASE,"900","901","899","900","900","999999","1"]] for i in (1,5,15)}
        result=build_entry_evidence("ETH/EUR",snap,
                 observed_at_utc=datetime.fromtimestamp(BASE,timezone.utc).isoformat(),
                 known_at_utc=datetime.fromtimestamp(BASE+11,timezone.utc).isoformat())
        self.assertEqual(result["status"],"COMPLETE")
        self.assertEqual(result["frames"]["5"]["closed_close_eur"],10.234)
        self.assertEqual(result["frames"]["15"]["volume_ratio_prior_5"],1.0)
        self.assertGreater(result["frames"]["15"]["atr14_eur"],0)
        self.assertTrue(result["guardrails"]["no_buy_authority"])
        self.assertNotIn("900",str(result))
    def test_missing_feed_is_not_reject(self):
        result=build_entry_evidence("ETH/EUR",{1:bars(1),5:None,15:bars(15)},
              observed_at_utc=datetime.fromtimestamp(BASE,timezone.utc).isoformat(),
              known_at_utc=datetime.fromtimestamp(BASE+5,timezone.utc).isoformat())
        self.assertEqual(result["status"],"PARTIAL_OR_MISSING")
        self.assertEqual(result["frames"]["5"]["status"],"MISSING")
        self.assertNotIn("decision",result)
    def test_gap_fails_closed_without_fake_atr(self):
        result=build_entry_evidence("SOL/EUR",{i:bars(i,gap=True) for i in (1,5,15)},
              observed_at_utc=datetime.fromtimestamp(BASE,timezone.utc).isoformat(),
              known_at_utc=datetime.fromtimestamp(BASE+5,timezone.utc).isoformat())
        self.assertEqual(result["frames"]["5"]["status"],"INCOMPLETE")
        self.assertEqual(result["status"],"PARTIAL_OR_MISSING")
    def test_zero_volume_baseline_does_not_invent_ratio(self):
        snap={i:bars(i) for i in (1,5,15)}
        for row in snap[5][-6:-1]: row[6]="0"
        result=build_entry_evidence("ETH/EUR",snap,
             observed_at_utc=datetime.fromtimestamp(BASE,timezone.utc).isoformat(),
             known_at_utc=datetime.fromtimestamp(BASE+5,timezone.utc).isoformat())
        self.assertIsNone(result["frames"]["5"]["volume_ratio_prior_5"])
    def test_stale_missing_and_future_timestamp(self):
        result=build_entry_evidence("ETH/EUR",{i:bars(i) for i in (1,5,15)},
             observed_at_utc=datetime.fromtimestamp(BASE+1200,timezone.utc).isoformat(),
             known_at_utc=datetime.fromtimestamp(BASE+1210,timezone.utc).isoformat())
        self.assertEqual(result["frames"]["1"]["status"],"STALE")
        with self.assertRaises(ValueError):
            build_entry_evidence("ETH/EUR",{},observed_at_utc="2026-10-09T11:00:00Z",known_at_utc="2026-10-09T10:00:00Z")
    def test_three_bounded_reads_and_no_persistence(self):
        requests=[]
        def loader(pair, interval):
            requests.append((pair,interval))
            return {"error":[],"result":{"XXBTZEUR":bars(interval),"last":123}}
        times=iter((datetime.fromtimestamp(BASE,timezone.utc),datetime.fromtimestamp(BASE+8,timezone.utc)))
        result=fetch_public_entry_evidence("XBTEUR","XBT/EUR",clock=lambda:next(times),loader=loader)
        self.assertEqual(requests,[("XBTEUR",1),("XBTEUR",5),("XBTEUR",15)])
        self.assertEqual(result["status"],"COMPLETE")
        self.assertEqual(result["available_for_decision_no_earlier_than_utc"],"2026-10-09T"+datetime.fromtimestamp(BASE+8,timezone.utc).strftime("%H:%M:%S")+"Z")
    def test_malformed_response_fail_soft(self):
        times=iter((datetime.fromtimestamp(BASE,timezone.utc),datetime.fromtimestamp(BASE+8,timezone.utc)))
        result=fetch_public_entry_evidence("XBTEUR","XBT/EUR",clock=lambda:next(times),loader=lambda p,i:{"error":["bad"]})
        self.assertTrue(all(x["status"]=="MISSING" for x in result["frames"].values()))

if __name__ == "__main__": unittest.main()
