"""Real V3 P0 -> immutable original SOURCE_INPUT -> source-clocked 15m base.

All acquisition/model data are offline fixtures. These tests are NOT physical
Mini-PC, Cloud or real Paper entry proof.
"""
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from paper_evaluator.v3_first_pit_presignal_15m_v1 import (
    KIND, capture_first_pit_base, read_first_pit_base,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
from tests.test_v3_experimental_paper_initial_review_v1 import fixture
from tests.test_v2r4_v3_entry_handoff_probe import dt

SID = "PAPER-V3-P0-PRESIGNAL-TEST"


def scenario():
    candidate, coin, ticker, meta = fixture()
    candidate = dict(candidate, entry_origin="SCANNER", altname="XBTEUR")
    # Original public OHLC P0 already has four CLOSED 15m candles.
    # Two of them fully precede the scanner's event_time at BASE-60sec.
    assert len(coin["initial_pit_closed_15m_ohlc"]) == 4
    return candidate, coin, ticker, meta


class OriginalFirstPIT15mTests(unittest.TestCase):
    def test_same_original_kraken_pit_base_persists_without_new_poll_or_model(self):
        candidate, coin, quote, meta = scenario()
        with tempfile.TemporaryDirectory() as tmp:
            journal = Path(tmp) / "journal"
            budgets = Path(tmp) / "budgets"
            journal.mkdir()
            budgets.mkdir()
            called = []
            result = one_candidate(
                candidate=candidate, series_id=SID,
                local_receipts=journal, model_reservations=budgets,
                acquire=lambda _: called.append("original_p0") or (
                    copy.deepcopy(coin), copy.deepcopy(quote), copy.deepcopy(meta)),
                clock=lambda: dt(12),
                model_client=lambda *_: self.fail("no paid model authorized"))
            self.assertEqual(result["status"],
                "V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            self.assertEqual(called, ["original_p0"])
            self.assertEqual(list(budgets.iterdir()), [])
            rows = [json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            source = next(r for r in rows if r["phase"] == "SOURCE_INPUT")
            actual = source["data"]["initial_pit_15m_base"]
            self.assertEqual(actual["kind"], KIND)
            self.assertEqual(actual["first_known_at_utc"], coin["known_at_utc"])
            self.assertTrue(actual["bar_closes_are_not_observation_times"])
            self.assertEqual(len(actual["bars"]), 2)
            self.assertTrue(all(
                b["start_utc"] + 900 <= int(datetime.fromisoformat(
                    candidate["event_time_utc"]).timestamp())
                for b in actual["bars"]))
            valid = read_first_pit_base(
                candidate, source, decision_at_utc=dt(60))
            self.assertEqual(valid["bars"], actual["bars"])
            self.assertEqual(source["data"]["input_known_at_utc"],
                             actual["first_known_at_utc"])
            self.assertFalse(any(r["phase"] == "PAPER_FILL" for r in rows))

    def test_first_pit_source_known_late_or_altered_does_not_become_presignal(self):
        candidate, coin, _, _ = scenario()
        original = capture_first_pit_base(candidate, coin, written_at_utc=dt(12))
        self.assertIsNotNone(original)
        for change in (
            lambda e: e.update(pair="ETH/EUR"),
            lambda e: e.update(known_at_utc=dt(900)),
            lambda e: e.update(observed_at_utc=dt(-90)),
            lambda e: e.update(initial_pit_closed_15m_ohlc=[]),
            lambda e: e["frames"]["15"].update(status="INVALID"),
            lambda e: e["initial_pit_closed_15m_ohlc"][-2].update(close=1000),
            lambda e: e["initial_pit_closed_15m_ohlc"][-2].update(start_utc=1791531000),
        ):
            trial = copy.deepcopy(coin)
            change(trial)
            with self.subTest(change=str(change)):
                self.assertIsNone(capture_first_pit_base(
                    candidate, trial, written_at_utc=dt(12)))
        self.assertIsNone(capture_first_pit_base(
            {**candidate, "entry_origin":"P1_REENTRY_EPISODE"},
            coin, written_at_utc=dt(12)))

    def test_receipt_replay_rejects_forged_source_and_clock(self):
        from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
        candidate, coin, _, _ = scenario()
        base = capture_first_pit_base(candidate, coin, written_at_utc=dt(12))
        self.assertIsNotNone(base)
        receipt = make_receipt(
            series_id=SID, revision=REVISION,
            candidate_id=candidate["candidate_id"], pair=candidate["pair"],
            event_time_utc=candidate["event_time_utc"],
            known_at_utc=dt(12), phase="SOURCE_INPUT", result="PASS",
            data={"input_known_at_utc": coin["known_at_utc"],
                  "source_status": "COMPLETE",
                  "initial_pit_15m_base": base})
        self.assertIsNotNone(read_first_pit_base(
            candidate, receipt, decision_at_utc=dt(30)))
        mutations = (
            lambda r:r["data"]["initial_pit_15m_base"].update(
                first_known_at_utc=dt(100)),
            lambda r:r["data"]["initial_pit_15m_base"].update(
                candidate_id="OTHER"),
            lambda r:r["data"]["initial_pit_15m_base"].update(
                bar_closes_are_not_observation_times=False),
            lambda r:r["data"].update(input_known_at_utc=dt(100)),
            lambda r:r.update(result="UNKNOWN"),
            lambda r:r["data"]["initial_pit_15m_base"]["bars"][-1].update(
                start_utc=r["data"]["initial_pit_15m_base"]["bars"][0]["start_utc"]),
        )
        for change in mutations:
            changed = copy.deepcopy(receipt)
            change(changed)
            with self.subTest(change=str(change)):
                self.assertIsNone(read_first_pit_base(
                    candidate, changed, decision_at_utc=dt(30)))
        self.assertIsNone(read_first_pit_base(
            candidate, receipt, decision_at_utc=dt(5)))


    def test_existing_selective_tick_reuses_first_pit_without_any_new_model_or_writer(self):
        from datetime import timedelta
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import tick_once
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
            capture_public_1m,
        )
        from paper_evaluator.v3_experimental_paper_journal_v1 import (
            make_receipt, store_receipt_explicitly,
        )
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
        from tests.test_v3_paper_wait_observer_v1 import (
            seed, CID, SID as CANARY, START, t,
        )
        now = datetime(2026, 10, 12, 6, 46, 7, tzinfo=timezone.utc)
        candidate = {"kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
                     "candidate_id":CID,"pair":"ZRO/EUR",
                     "altname":"ZROEUR","event_time_utc":t(START),
                     "action":"REVIEW_ONLY_NOT_ORDER"}
        def source_minute(*,pair,altname,outdir):
            base = now.replace(second=0,microsecond=0)-timedelta(minutes=16)
            def loader(_):
                xs=[]
                for i in range(16):
                    ts=int((base+timedelta(minutes=i)).timestamp())
                    xs.append([ts,"2.09","2.12","2.08","2.10","2.10","10",2])
                return {"error":[],"result":{"ZROEUR":xs,"last":1}}
            return capture_public_1m(pair=pair,altname=altname,
                outdir=outdir,loader=loader,clock=lambda:now)
        def coin_at_tick(*unused):
            def frame(interval,end,close,ratio):
                return {"status":"VALID","interval_min":interval,
                        "last_closed_bar_end_utc":t(end),
                        "closed_close_eur":close,"volume_ratio_prior_5":ratio}
            f15=frame(15,datetime(2026,10,12,6,30,tzinfo=timezone.utc),
                      2.10,1.3)
            f15.update(atr14_eur=0.20,recent_8bar_low_eur=2.07)
            return {"kind":"SUCCESSOR_COIN_ENTRY_EVIDENCE_V1",
                    "pair":"ZRO/EUR","status":"COMPLETE",
                    "observed_at_utc":t(now-timedelta(seconds=3)),
                    "known_at_utc":t(now-timedelta(seconds=2)),
                    "frames":{
                        "1":frame(1,datetime(2026,10,12,6,46,tzinfo=timezone.utc),2.13,1.3),
                        "5":frame(5,datetime(2026,10,12,6,45,tzinfo=timezone.utc),2.13,1.3),
                        "15":f15}}
        def first_source(*,late_after_p4=False):
            start=datetime(2026,10,12,5,30,tzinfo=timezone.utc)
            bars=[]
            for i in range(4):
                at=start+timedelta(minutes=15*i)
                bars.append({"start_utc":int(at.timestamp()),
                             "open":2.09,"high":2.12,
                             "low":2.08,"close":2.10,"volume":12.0})
            observed=datetime(2026,10,12,6,43,57,tzinfo=timezone.utc)
            known=datetime(2026,10,12,6,44,55 if late_after_p4 else 0,tzinfo=timezone.utc)
            coin={"pair":"ZRO/EUR","status":"COMPLETE",
                  "observed_at_utc":t(observed),"known_at_utc":t(known),
                  "frames":{"15":{"status":"VALID"}},
                  "initial_pit_closed_15m_ohlc":bars}
            return capture_first_pit_base(
                candidate,coin,written_at_utc=t(known+timedelta(seconds=1)))
        def observe(with_source,*,late_after_p4=False,late_original_decision=False,
                    witnessed_pre_signal=False):
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp);journal=path/"journal";captures=path/"cap"
                journal.mkdir();captures.mkdir()
                # First-known source before P4 is not sufficient: a P4
                # *after* the newly closed 5m bar is retrospective.
                late_decision=datetime(2026,10,12,6,45,20,tzinfo=timezone.utc)
                seed(journal,model_setup_lane="CONTINUITY",
                     decision_at=late_decision if late_original_decision else None)
                if witnessed_pre_signal:
                    # Four ORIGINAL captures from 06:00..06:30, all completed
                    # before the 06:42 scanner signal. Each actual snapshot
                    # knows its own clock and its SHA; the final tick cannot
                    # retroactively fill in any of these older minutes.
                    for a,z,capture_at in (
                        (0,7,datetime(2026,10,12,6,8,tzinfo=timezone.utc)),
                        (7,17,datetime(2026,10,12,6,18,tzinfo=timezone.utc)),
                        (17,27,datetime(2026,10,12,6,28,tzinfo=timezone.utc)),
                        (27,30,datetime(2026,10,12,6,31,tzinfo=timezone.utc)),
                    ):
                        def stored_earlier_ohlc(_,start=a,stop=z):
                            first=datetime(2026,10,12,6,0,tzinfo=timezone.utc)
                            candles=[]
                            for minute in range(start,stop):
                                at=first+timedelta(minutes=minute)
                                candles.append([int(at.timestamp()),"2.09","2.12",
                                                "2.08","2.10","2.10","10",2])
                            return {"error":[],"result":{"ZROEUR":candles,"last":1}}
                        capture_public_1m(
                            pair="ZRO/EUR",altname="ZROEUR",outdir=captures,
                            loader=stored_earlier_ohlc,clock=lambda at=capture_at:at)
                if with_source:
                    base=first_source(late_after_p4=late_after_p4)
                    self.assertIsNotNone(base)
                    receipt=make_receipt(
                        series_id=CANARY,revision=REVISION,
                        candidate_id=CID,pair="ZRO/EUR",
                        event_time_utc=t(START),
                        known_at_utc=("2026-10-12T06:44:56+00:00" if late_after_p4
                                      else "2026-10-12T06:44:01+00:00"),
                        phase="SOURCE_INPUT",result="PASS",
                        data={"source_status":"COMPLETE",
                              "input_known_at_utc":base["first_known_at_utc"],
                              "initial_pit_15m_base":base})
                    store_receipt_explicitly(journal,receipt)
                calls=[]
                def fetch(*args):
                    calls.append("coin")
                    return coin_at_tick()
                def quote(*args):
                    calls.append("ticker")
                    return {"ask":2.135,"bid":2.134,
                            "spread_pct":.05}
                result=tick_once(
                    candidate=candidate,series_id=CANARY,
                    journal=journal,capture_dir=captures,
                    clock_now=lambda:t(now),
                    capture=source_minute,fetch=fetch,ticker=quote)
                return result,calls,[
                    json.loads(x.read_text("utf-8")) for x in journal.glob("*.json")]
        hold,calls,rows=observe(False)
        self.assertEqual(hold["continuity_offensive_shadow"]["status"],
                         "PRE_SIGNAL_15M_PROSPECTIVE_HISTORY_MISSING")
        # Existing WAIT observer still legitimately reads coin+quote once.
        # Missing pre-signal history must not add a SECOND shadow poll.
        self.assertEqual(calls,["coin","ticker"])
        eligible,calls,rows=observe(True)
        shadow=eligible["continuity_offensive_shadow"]
        self.assertEqual(shadow["status"],"SOURCE_CLOCKED_PIT_RESEARCH_ONLY")
        self.assertEqual(shadow["early_base_provenance"],
                         "ORIGINAL_P0_15M_FIRST_KNOWN_NOT_PRE_SIGNAL_WITNESS")
        self.assertEqual(shadow["early_5m_status"],
                         "EARLY_5M_CONTINUITY_SUPPORTS_NEW_FULL_REVIEW_ONLY")
        self.assertTrue(shadow["early_5m_review_only"])
        self.assertFalse(shadow["same_witnessed_archive"])
        self.assertEqual(calls,["coin","ticker"])
        self.assertFalse(eligible["model_called"])
        self.assertEqual(eligible["model_attempts"],0)
        self.assertFalse(any(row["phase"]=="PAPER_FILL" for row in rows))
        late,calls,rows=observe(True,late_after_p4=True)
        self.assertEqual(late["continuity_offensive_shadow"]["early_5m_status"],
                         "FIRST_PIT_P4_5M_CHRONOLOGY_UNPROVEN_NO_REVIEW")
        self.assertFalse(late["continuity_offensive_shadow"]["early_5m_review_only"])
        self.assertEqual(calls,["coin","ticker"])
        self.assertFalse(any(row["phase"]=="PAPER_FILL" for row in rows))
        late_p4,calls,rows=observe(True,late_original_decision=True)
        shadow=late_p4["continuity_offensive_shadow"]
        self.assertEqual(shadow["status"],"SOURCE_CLOCKED_PIT_RESEARCH_ONLY")
        self.assertEqual(shadow["early_5m_status"],
                         "FIRST_PIT_P4_5M_CHRONOLOGY_UNPROVEN_NO_REVIEW")
        self.assertFalse(shadow["early_5m_review_only"])
        self.assertFalse(late_p4["model_called"])
        self.assertFalse(any(row["phase"]=="PAPER_FILL" for row in rows))
        genuine,calls,rows=observe(False,witnessed_pre_signal=True)
        shadow=genuine["continuity_offensive_shadow"]
        self.assertEqual(shadow["status"],"SOURCE_CLOCKED_PIT_RESEARCH_ONLY")
        self.assertEqual(shadow["early_base_provenance"],
                         "PROSPECTIVELY_SHA_WITNESSED_PRE_SIGNAL_1M")
        self.assertTrue(shadow["same_witnessed_archive"])
        self.assertEqual(shadow["early_5m_status"],
                         "EARLY_5M_CONTINUITY_SUPPORTS_NEW_FULL_REVIEW_ONLY")
        self.assertTrue(shadow["early_5m_review_only"])
        self.assertEqual(calls,["coin","ticker"])
        self.assertFalse(any(row["phase"]=="PAPER_FILL" for row in rows))
        late_witnessed,calls,rows=observe(
            False,witnessed_pre_signal=True,late_original_decision=True)
        shadow=late_witnessed["continuity_offensive_shadow"]
        self.assertEqual(shadow["early_base_provenance"],
                         "PROSPECTIVELY_SHA_WITNESSED_PRE_SIGNAL_1M")
        self.assertEqual(shadow["early_5m_status"],
                         "FIRST_PIT_P4_5M_CHRONOLOGY_UNPROVEN_NO_REVIEW")
        self.assertFalse(shadow["early_5m_review_only"])
        self.assertEqual(calls,["coin","ticker"])
        self.assertFalse(any(row["phase"]=="PAPER_FILL" for row in rows))


if __name__ == "__main__":
    unittest.main()
