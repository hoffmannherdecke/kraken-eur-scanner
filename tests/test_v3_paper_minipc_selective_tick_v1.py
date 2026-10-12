"""One Mini-PC CANARY tick: no model, real-time WAIT, later censored maturity."""
import json,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from paper_evaluator.v3_paper_minipc_selective_tick_v1 import tick_once
from paper_evaluator.v3_paper_wait_observer_v1 import finish_wait
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
    capture_public_1m,assemble,
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
            self.assertEqual(out["prospective_1m_bars"],15)
            self.assertEqual(finish_wait(journal=j,series_id=SID,candidate_id=CID,
                    now_at_utc=t(at))["status"],"WAIT_EXPIRY_ALREADY_FINAL")

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
            self.assertEqual(snapshot["count"],17)
            joined=assemble(snapshots=cap,pair="ZRO/EUR",
                entry_at_utc=t(at-timedelta(hours=20)),
                observed_at_utc=t(at))
            # 19h-old bar was fetched NOW, not captured live 19h ago.
            self.assertEqual(len(joined["closed_bars"]),16)
            self.assertTrue(joined["historical_late_backfill_excluded"])

if __name__=="__main__":unittest.main()
