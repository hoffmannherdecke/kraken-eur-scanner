"""One Mini-PC CANARY tick: no model, real-time WAIT, later censored maturity."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import tick_once
from paper_evaluator.v3_paper_wait_observer_v1 import finish_wait
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
    capture_public_1m,assemble,early_path_coverage,
)
from tests.test_v3_paper_wait_observer_v1 import seed,SID,CID,START,DECISION,t

def candidate():
    return {"kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
            "candidate_id":CID,"pair":"ZRO/EUR","altname":"ZROEUR",
            "event_time_utc":t(START),"action":"REVIEW_ONLY_NOT_ORDER"}
def tick_capture(at):
    def source(*,pair,altname,outdir):
        base=at.replace(second=0,microsecond=0)-timedelta(minutes=16)
        def loader(_):
            rows=[]
            for i in range(16):
                minute=int((base+timedelta(minutes=i)).timestamp())
                rows.append([minute,"2.09","2.12","2.08","2.10","2.10","10.0",2])
            return {"error":[],"result":{"ZROEUR":rows,"last":1}}
        return capture_public_1m(pair=pair,altname=altname,outdir=outdir,
                      loader=loader,clock=lambda:at)
    return source
def frames(at):
    def get(altname,pair):
        return {"pair":pair,"status":"COMPLETE",
                "observed_at_utc":t(at-timedelta(seconds=2)),
                "known_at_utc":t(at-timedelta(seconds=1)),
                "frames":{"5":{"status":"VALID",
                   "last_closed_bar_end_utc":t(at.replace(second=0,microsecond=0)),
                   "closed_close_eur":2.115,"volume_ratio_prior_5":1.3}}}
    return get
def ticker(altname):
    return {"ask":2.11,"bid":2.10,"spread_pct":.47}

class HostTickTests(unittest.TestCase):
    def test_real_time_wait_model_absent_but_p4_followup_trigger_journaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"capture";j.mkdir();cap.mkdir()
            seed(j)
            at=datetime(2026,10,12,6,50,7,tzinfo=timezone.utc)
            out=tick_once(candidate=candidate(),series_id=SID,journal=j,
                 capture_dir=cap,clock_now=lambda:t(at),
                 capture=tick_capture(at),fetch=frames(at),ticker=ticker)
            self.assertEqual(out["wait"]["status"],
                "WAIT_CONDITIONS_MATCHED_REQUIRES_NEW_MODEL_P4_AUTH")
            self.assertFalse(out["model_called"])
            self.assertEqual(out["model_attempts"],0)
            self.assertEqual(out["new_schedules"],0)
            self.assertFalse(out["orders"])
            self.assertFalse(out["v2r4_changed"])
            self.assertTrue(list(cap.glob("*.json")))
            self.assertTrue(any(json.loads(p.read_text())["phase"]=="WAIT_RECHECK"
                                for p in j.glob("*.json")))
            self.assertEqual(out["horizons"],{})

    def test_late_zro_canary_marks_unknown_watch_no_retrospective_buy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"capture";j.mkdir();cap.mkdir()
            seed(j)
            at=datetime(2026,10,12,8,45,0,tzinfo=timezone.utc)
            out=tick_once(candidate=candidate(),series_id=SID,journal=j,
                 capture_dir=cap,clock_now=lambda:t(at),
                 capture=tick_capture(at),
                 fetch=lambda *_: (_ for _ in ()).throw(AssertionError("not fetch old WAIT")),
                 ticker=lambda *_: (_ for _ in ()).throw(AssertionError("not ticker")))
            self.assertEqual(out["wait"]["status"],
                "WAIT_EXPIRED_UNKNOWN_WITH_UNPROVEN_MISSED_OPPORTUNITY")
            self.assertEqual(out["prospective_1m_bars"],16)
            self.assertFalse(any(json.loads(p.read_text())["phase"]=="PAPER_FILL"
                                 for p in j.glob("*.json")))

    def test_6h_missing_live_capture_is_censored_not_expost_fake_profit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"capture";j.mkdir();cap.mkdir()
            seed(j)
            at=datetime(2026,10,12,14,0,0,tzinfo=timezone.utc)
            out=tick_once(candidate=candidate(),series_id=SID,journal=j,
                 capture_dir=cap,clock_now=lambda:t(at),
                 capture=tick_capture(at))
            self.assertEqual(out["horizons"]["6h"],"IMMUTABLE_NEW_RECEIPT")
            records=[json.loads(p.read_text()) for p in j.glob("*.json")]
            final=[r for r in records if r["phase"]=="FOLLOWUP_6H"
                   and r["result"]=="CENSORED"]
            self.assertEqual(len(final),1)
            self.assertFalse(final[0]["data"]["path_contiguous_1m_verified"])
            self.assertIsNone(final[0]["data"].get("position_net_pnl_eur"))
            self.assertEqual(out["prospective_1m_bars"],16)
            self.assertEqual(finish_wait(journal=j,series_id=SID,candidate_id=CID,
                    now_at_utc=t(at))["status"],"WAIT_EXPIRY_ALREADY_FINAL")

    def test_live_capture_keeps_only_supported_prospective_archive_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            at=datetime(2026,10,13,8,0,0,tzinfo=timezone.utc)
            cap=Path(tmp)
            base=at-timedelta(minutes=75)
            def loader(_):
                candles=[]
                for n in range(75):
                    t0=base+timedelta(minutes=n)
                    candles.append([int(t0.timestamp()),"2.09","2.12",
                                    "2.08","2.10","2.10","10",2])
                return {"error":[],"result":{"ZROEUR":candles,"last":1}}
            result=capture_public_1m(pair="ZRO/EUR",altname="ZROEUR",
                                      outdir=cap,loader=loader,clock=lambda:at)
            self.assertEqual(result["count"],61)
            self.assertEqual(result["historical_closed_rows_not_archived"],14)
            # Same API snapshot is an immutable replay, not another payload.
            again=capture_public_1m(pair="ZRO/EUR",altname="ZROEUR",
                                     outdir=cap,loader=loader,clock=lambda:at)
            self.assertEqual(result["sha256"],again["sha256"])
            self.assertEqual(len(list(cap.glob("*.json"))),1)
            disk=json.loads(Path(result["file"]).read_text("utf-8"))
            self.assertEqual(len(disk["closed_bars"]),61)
            joined=assemble(snapshots=cap,pair="ZRO/EUR",
                entry_at_utc=t(at-timedelta(hours=2)),observed_at_utc=t(at),
                max_live_capture_lag_minutes=60)
            self.assertEqual(len(joined["closed_bars"]),61)
            strict=assemble(snapshots=cap,pair="ZRO/EUR",
                entry_at_utc=t(at-timedelta(hours=2)),observed_at_utc=t(at))
            self.assertEqual(len(strict["closed_bars"]),16)
            self.assertFalse(any(b["start_at_utc"]==
                t(base) for b in disk["closed_bars"]))

    def test_stale_only_ohlc_is_not_healthy_source_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            at=datetime(2026,10,13,8,0,0,tzinfo=timezone.utc)
            def loader(_):
                old=at-timedelta(hours=2)
                return {"error":[],"result":{"ZROEUR":[
                    [int(old.timestamp()),"2.09","2.12","2.08",
                     "2.10","2.10","10",2]],"last":1}}
            with self.assertRaisesRegex(ValueError,"no recently witnessed"):
                capture_public_1m(pair="ZRO/EUR",altname="ZROEUR",
                                  outdir=Path(tmp),loader=loader,clock=lambda:at)
            self.assertEqual(list(Path(tmp).glob("*.json")),[])


    def test_early_coverage_identifies_first_missing_minute_before_horizon(self):
        start=datetime(2026,10,13,7,45,30,tzinfo=timezone.utc)
        at=start+timedelta(minutes=25)
        rows=[{"start_at_utc":t(start.replace(second=0)+timedelta(minutes=i)),
               "open":2.0,"high":2.1,"low":1.9,"close":2.0}
              for i in range(1,25) if i!=2]
        assembled={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                   "source":"KRAKEN_SPOT_EUR_PUBLIC","no_future_backfill":True,
                   "closed_bars":rows}
        result=early_path_coverage(assembled=assembled,entry_at_utc=t(start),
                                   observed_at_utc=t(at))
        self.assertEqual(result["status"],"SOURCE_1M_GAP_PAST_PROVENANCE_LIMIT")
        self.assertEqual(result["first_missing_start_utc"],
                         t(start.replace(second=0)+timedelta(minutes=2)))
        self.assertEqual(result["contiguous_prefix_minutes"],1)
        self.assertTrue(result["gap_past_15m_provenance_limit"])
        self.assertFalse(result["retroactive_market_labels_authorized"])
        # Later authentic 1m timestamps cannot be used to invent this
        # missing original first-period minute retroactively.
        self.assertEqual(result["model_http_calls"],0)

    def test_early_coverage_contiguous_and_future_excluded(self):
        start=datetime(2026,10,13,7,45,30,tzinfo=timezone.utc)
        at=datetime(2026,10,13,7,54,0,tzinfo=timezone.utc)
        base=start.replace(second=0)+timedelta(minutes=1)
        rows=[{"start_at_utc":t(base+timedelta(minutes=i)),
               "open":2.0,"high":2.1,"low":1.9,"close":2.0}
              for i in range(6)]
        assembled={"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
                   "source":"KRAKEN_SPOT_EUR_PUBLIC","no_future_backfill":True,
                   "closed_bars":rows}
        good=early_path_coverage(assembled=assembled,entry_at_utc=t(start),
                                 observed_at_utc=t(at))
        self.assertEqual(good["status"],
                         "CONTIGUOUS_PROSPECTIVE_1M_AS_OF_STABLE_CUTOFF")
        self.assertEqual(good["expected_stable_minutes"],6)
        self.assertEqual(good["missing_stable_minutes"],0)
        self.assertEqual(good["contiguous_prefix_minutes"],6)
        right_after=early_path_coverage(assembled={**assembled,"closed_bars":[]},
            entry_at_utc=t(start),observed_at_utc=t(start+timedelta(seconds=10)))
        self.assertEqual(right_after["status"],"WAIT_FIRST_STABLE_MINUTE")
        recent=early_path_coverage(assembled={**assembled,"closed_bars":[]},
            entry_at_utc=t(start),observed_at_utc=t(start+timedelta(minutes=8)))
        self.assertEqual(recent["status"],"SOURCE_1M_RECENT_GAP_MONITOR")
        self.assertFalse(recent["gap_past_15m_provenance_limit"])
        with self.assertRaisesRegex(ValueError,"verified prospective"):
            early_path_coverage(assembled={"closed_bars":rows},
                entry_at_utc=t(start),observed_at_utc=t(at))

    def test_15m_volume_ratio_four_previous_is_not_five_previous(self):
        from paper_evaluator.successor_coin_entry_evidence_v1 import _frame
        as_of=datetime(2026,10,12,6,46,tzinfo=timezone.utc)
        base=datetime(2026,10,12,4,15,tzinfo=timezone.utc)
        volumes=[100.0,1.0,2.0,3.0,4.0,10.0,20.0,14.0,3.0,8.0]
        # The final candle is 06:30-06:45: already closed at 06:46.
        bars=[[int((base+timedelta(minutes=15*i)).timestamp()),
               "2.0","2.1","1.9","2.02","2.02",str(vol),2]
              for i,vol in enumerate(volumes)]
        frame=_frame(bars,15,as_of)
        self.assertEqual(frame["status"],"VALID")
        prior_four=sum(volumes[-5:-1])/4
        self.assertAlmostEqual(frame["volume_ratio_prior_4"],volumes[-1]/prior_four,places=5)
        self.assertNotEqual(frame["volume_ratio_prior_4"],frame["volume_ratio_prior_5"])

    def test_old_ohlc_backfill_22h_later_must_not_be_called_live_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cap=root/"c";cap.mkdir()
            at=datetime(2026,10,13,8,0,0,tzinfo=timezone.utc)
            base=at.replace(second=0,microsecond=0)-timedelta(minutes=16)
            def loader(_):
                timestamps=[at-timedelta(hours=19)]+[
                    base+timedelta(minutes=i) for i in range(16)]
                candles=[[int(x.timestamp()),"2.09","2.12","2.08","2.10",
                          "2.10","10.0",2] for x in timestamps]
                return {"error":[],"result":{"ZROEUR":candles,"last":1}}
            snapshot=capture_public_1m(pair="ZRO/EUR",altname="ZROEUR",
                           outdir=cap,loader=loader,clock=lambda:at)
            self.assertEqual(snapshot["count"],16)
            self.assertEqual(snapshot["historical_closed_rows_not_archived"],1)
            joined=assemble(snapshots=cap,pair="ZRO/EUR",
                entry_at_utc=t(at-timedelta(hours=20)),
                observed_at_utc=t(at))
            # 19h-old bar was fetched NOW, not captured live 19h ago.
            self.assertEqual(len(joined["closed_bars"]),16)
            self.assertTrue(joined["historical_late_backfill_excluded"])

if __name__=="__main__":unittest.main()
