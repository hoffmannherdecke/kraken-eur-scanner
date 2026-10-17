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
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION

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

    def test_all_final_6h24h72h_horizons_stop_new_kraken_poll(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"capture";j.mkdir();cap.mkdir()
            seed(j)
            for hours in (6,24,72):
                row=make_receipt(
                    series_id=SID,revision=REVISION,candidate_id=CID,
                    pair="ZRO/EUR",event_time_utc=t(START),
                    known_at_utc=t(START+timedelta(hours=hours,minutes=65)),
                    phase=f"FOLLOWUP_{hours}H",result="CENSORED",
                    data={"censor_reason":"ACTUAL_PROSPECTIVE_1M_GAP"},
                    event_key=f"FINAL{hours}H")
                store_receipt_explicitly(j,row)
            old_files={p.name for p in j.glob("*.json")}
            calls=[]
            def forbid(*args,**kwargs):
                calls.append(True)
                raise AssertionError("no more Kraken source request after all final")
            out=tick_once(candidate=candidate(),series_id=SID,journal=j,
                capture_dir=cap,
                clock_now=lambda:t(START+timedelta(hours=73)),
                capture=forbid,fetch=forbid,ticker=forbid)
            self.assertEqual(out["status"],
                "ALL_FOLLOWUP_HORIZONS_FINAL_NO_NEW_PUBLIC_KRAKEN_REQUEST")
            self.assertEqual(out["source_capture"],
                             "SKIPPED_COMPLETE_IMMUTABLE_6H24H72H")
            self.assertEqual(calls,[])
            self.assertEqual({p.name for p in j.glob("*.json")},old_files)
            self.assertEqual(list(cap.glob("*.json")),[])
            self.assertEqual(out["new_schedules"],0)
            self.assertFalse(out["model_called"])
            self.assertFalse(out["v2r4_changed"])

    def test_partial_final_horizons_do_not_silently_end_24h_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"capture";j.mkdir();cap.mkdir()
            seed(j)
            row=make_receipt(
                series_id=SID,revision=REVISION,candidate_id=CID,
                pair="ZRO/EUR",event_time_utc=t(START),
                known_at_utc=t(START+timedelta(hours=6,minutes=65)),
                phase="FOLLOWUP_6H",result="CENSORED",
                data={"censor_reason":"TRUE_1M_GAP"},event_key="FINAL6H")
            store_receipt_explicitly(j,row)
            calls=[]
            def observe(*,pair,altname,outdir):
                calls.append(pair)
                return tick_capture(START+timedelta(hours=8))(
                    pair=pair,altname=altname,outdir=outdir)
            out=tick_once(candidate=candidate(),series_id=SID,journal=j,
                capture_dir=cap,
                clock_now=lambda:t(START+timedelta(hours=8)),
                capture=observe)
            self.assertEqual(calls,["ZRO/EUR"])
            self.assertEqual(out["source_capture"],"CLOSED_KRAKEN_1M_SNAPSHOT_SAVED")
            self.assertNotIn("ALL_FOLLOWUP_HORIZONS_FINAL",out.get("status",""))

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


class ReleasedNonCanaryFollowupTests(unittest.TestCase):
    """Strict source-only post-CAS seam. All Cloud/Kraken inputs are offline fakes."""

    SERIES="PAPER-V3-20261017T160000Z"
    REPO="a"*40
    BUNDLE="b"*64
    STRATEGY="c"*64
    AT=datetime(2026,10,17,16,8,tzinfo=timezone.utc)
    ORIGINAL=datetime(2026,10,17,16,1,tzinfo=timezone.utc)

    def context(self,observed=None):
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
        return {"series_id":self.SERIES,"status":"active",
                "strategy_revision":REVISION,
                "observed_at_utc":t(observed or (self.AT-timedelta(seconds=10))),
                "config":{"series_id":self.SERIES,"strategy_revision":REVISION,
                          "release_repo_sha":self.REPO,
                          "runtime_bundle_fingerprint_sha256":self.BUNDLE,
                          "strategy_fingerprint_sha256":self.STRATEGY,
                          "paper_only":True,
                          "real_money_actions_enabled":False,
                          "automatic_activation_allowed":False,
                          "physical_v2r4_writer_fence_verified":True,
                          "supervisor_old_intake_rearm_blocked":True,
                          "old_followup_owner_preserved":True,
                          "independent_six_e2e_proofs_verified":True}}

    def seeded(self,base:Path,final_model:bool=True):
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
        journal=base/"journal";capture=base/"captures";budget=base/"budget"
        journal.mkdir();capture.mkdir();budget.mkdir()
        c=candidate()
        c["event_time_utc"]=t(self.ORIGINAL)
        receipt=make_receipt(
            series_id=self.SERIES,revision=REVISION,
            candidate_id=c["candidate_id"],pair=c["pair"],
            event_time_utc=c["event_time_utc"],
            known_at_utc=t(self.ORIGINAL+timedelta(seconds=3)),
            phase="SCANNER_CAPTURE",result="SEEN",event_key="FIRST",
            data={"candidate_origin":"SCANNER",
                  "source_status":"ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY"})
        store_receipt_explicitly(journal,receipt)
        if final_model:
            # Fake complete original model history, with a single consumed
            # O_EXCL-style reservation. No real HTTP and no fabricated BUY.
            for phase,result,seconds in (
                ("MODEL_REQUEST","PASS",10),
                ("MODEL_RESPONSE","PASS",20),
                ("P4_VALIDATION","REJECT",30)):
                record=make_receipt(
                    series_id=self.SERIES,revision=REVISION,
                    candidate_id=c["candidate_id"],pair=c["pair"],
                    event_time_utc=c["event_time_utc"],
                    known_at_utc=t(self.ORIGINAL+timedelta(seconds=seconds)),
                    phase=phase,result=result,event_key="FIRST",
                    data={"source_status":"FAKE_CI_ONLY_NO_PAID_MODEL"})
                store_receipt_explicitly(journal,record)
            (budget/"offline-unique.reserved.json").write_text(json.dumps({
                "kind":"V3_PAPER_MODEL_HTTP_RESERVED_BEFORE_NETWORK_V1",
                "series_id":self.SERIES,"candidate_id":c["candidate_id"],
                "no_automatic_retry":True}),encoding="utf-8")
        return c,journal,capture

    def call(self,c,journal,capture,readback,source):
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            released_paper_followup_tick_once,
        )
        return released_paper_followup_tick_once(
            candidate=c,series_id=self.SERIES,journal=journal,
            capture_dir=capture,model_reservations=journal.parent/"budget",
            ack_file=journal.parent/"ack.json",expected_repo_sha=self.REPO,
            expected_bundle_sha256=self.BUNDLE,
            expected_strategy_sha256=self.STRATEGY,
            read_active_series=readback,
            clock_now=lambda:t(self.AT),capture=source,
            fetch=lambda *_:self.fail("no model/extra exchange fetch"),
            ticker=lambda *_:self.fail("no ticker without WAIT"))

    def test_postcas_active_exact_source_allows_one_locked_source_only_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp));cloud=[];calls=[]
            def readback(sid):
                cloud.append(sid)
                return self.context()
            def source(**kw):
                calls.append(kw["pair"])
                return tick_capture(self.AT)(**kw)
            out=self.call(c,j,cap,readback,source)
            self.assertEqual(cloud,[self.SERIES])
            self.assertEqual(calls,["ZRO/EUR"])
            self.assertGreater(out["prospective_1m_bars"],0)
            self.assertFalse(out["orders"])
            self.assertFalse(out["model_called"])
            self.assertEqual(out["new_schedules"],0)
            self.assertFalse(out["v2r4_changed"])

    def test_unreleased_noncanary_direct_tick_is_rejected_before_kraken(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp))
            with self.assertRaisesRegex(ValueError,"requires locked external"):
                tick_once(candidate=c,series_id=self.SERIES,journal=j,
                    capture_dir=cap,
                    capture=lambda **_:self.fail("unreleased direct source"))
            self.assertFalse(list(cap.glob("*.json")))

    def test_stale_missing_foreign_or_unfenced_cloud_blocks_before_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp))
            good=self.context()
            cases=[
                None,
                dict(good,status="strategy_cutover_closed"),
                dict(good,observed_at_utc=t(self.AT-timedelta(seconds=91))),
                dict(good,observed_at_utc=t(self.AT+timedelta(seconds=1))),
                dict(good,series_id="PAPER-V3-OTHER"),
                dict(good,config=dict(good["config"],release_repo_sha="f"*40)),
                dict(good,config=dict(good["config"],physical_v2r4_writer_fence_verified=False)),
                dict(good,config=dict(good["config"],old_followup_owner_preserved=False)),
                dict(good,config=dict(good["config"],independent_six_e2e_proofs_verified=False)),
            ]
            before={p.name:p.read_bytes() for p in j.glob("*.json")}
            for case in cases:
                with self.subTest(case=repr(case)[:110]):
                    with self.assertRaises(ValueError):
                        self.call(c,j,cap,lambda _sid:case,
                            lambda **_:self.fail("Cloud gate failed but Kraken ran"))
                    self.assertEqual(before,{p.name:p.read_bytes()
                                              for p in j.glob("*.json")})
                    self.assertFalse(list(cap.glob("*.json")))

    def test_missing_model_or_budget_reservation_never_becomes_no_buy(self):
        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp),final_model=False)
            before={p.name:p.read_bytes() for p in j.glob("*.json")}
            result=self.call(c,j,cap,lambda sid:self.context(),
                             lambda **_:self.fail("P4 not final; no Kraken GET"))
            self.assertTrue(result["status"].startswith("NONCANARY_FOLLOWUP_HOLD_"))
            self.assertFalse(result["tick_called"])
            self.assertEqual(before,{p.name:p.read_bytes() for p in j.glob("*.json")})
            self.assertFalse(list(cap.glob("*.json")))

        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp),final_model=True)
            (j.parent/"budget"/"offline-unique.reserved.json").unlink()
            result=self.call(c,j,cap,lambda sid:self.context(),
                             lambda **_:self.fail("reservation missing; no Kraken GET"))
            self.assertIn("UNVERIFIED_MODEL_P4_PROVENANCE",result["status"])
            self.assertFalse(result["tick_called"])
            self.assertFalse(list(cap.glob("*.json")))

    def test_strict_cas_timestamp_namespace_never_accepts_canary(self):
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            released_paper_followup_tick_once,
        )
        with tempfile.TemporaryDirectory() as tmp:
            c,j,cap=self.seeded(Path(tmp))
            for sid in ("PAPER-V3-CANARY-ONESHOT-20261016",
                        "PAPER-V3-LIVE-CANARY-BYPASS",
                        "PAPER-V3-20261017T160000Z-EXTRA"):
                with self.subTest(sid=sid):
                    with self.assertRaises(ValueError):
                        released_paper_followup_tick_once(
                            candidate=c,series_id=sid,journal=j,capture_dir=cap,
                            model_reservations=j.parent/"budget",
                            ack_file=j.parent/"ack.json",expected_repo_sha=self.REPO,
                            expected_bundle_sha256=self.BUNDLE,
                            expected_strategy_sha256=self.STRATEGY,
                            read_active_series=lambda _sid:self.fail(
                                "invalid identity contacted Cloud"))



class FirstReleasedScannerOwnerTests(unittest.TestCase):
    """Offline injected Cloud/PIT/model only, no real HTTP, no actual V3 release."""

    SERIES="PAPER-V3-20261009T130000Z"
    REPO="a"*40
    BUNDLE="b"*64
    STRATEGY="c"*64

    def inputs(self):
        from tests.test_v3_paper_existing_source_owner_to_single_writer_seam_v1 import (
            preflight,xbt_real_pit_fixture,
        )
        from tests.test_v3_paper_shared_candidate_intake_plan_v1 import scanner
        from tests.test_v2r4_v3_entry_handoff_probe import dt
        from tests.test_v3_paper_minipc_one_candidate_v1 import valid_approval
        candidate=scanner("V3-INITIAL-EUR-1","XBT/EUR",dt(9))
        plan=preflight(scanners=[candidate],observations=xbt_real_pit_fixture())
        candidate=plan["selected_candidates"][0]  # canonical enriched SCANNER identity
        plan["series_id"]=self.SERIES
        approval=dict(valid_approval(),series_id=self.SERIES)
        config={"series_id":self.SERIES,
                "strategy_revision":REVISION,
                "release_repo_sha":self.REPO,
                "runtime_bundle_fingerprint_sha256":self.BUNDLE,
                "strategy_fingerprint_sha256":self.STRATEGY,
                "paper_only":True,
                "real_money_actions_enabled":False,
                "automatic_activation_allowed":False,
                "physical_v2r4_writer_fence_verified":True,
                "supervisor_old_intake_rearm_blocked":True,
                "old_followup_owner_preserved":True,
                "independent_six_e2e_proofs_verified":True}
        cloud={"series_id":self.SERIES,
               "status":"active",
               "strategy_revision":REVISION,
               "observed_at_utc":dt(12),
               "config":config}
        return candidate,plan,approval,cloud

    def call(self,root,candidate,plan,approval,cloud,*,client=None,
             source=None,model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB"):
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            released_paper_first_scanner_model_once,
        )
        from tests.test_v2r4_v3_entry_handoff_probe import dt
        from tests.test_v3_paper_minipc_one_candidate_v1 import (
            fake_acquire,fake_model,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
            capture_public_1m,
        )
        from datetime import datetime
        if source is None:
            source=lambda **_:self.fail("not-yet-closed first minute must not fetch")
        for label in ("journal","capture","budget"):
            (root/label).mkdir(exist_ok=True)
        return released_paper_first_scanner_model_once(
            preflight=plan,candidate=candidate,series_id=self.SERIES,
            journal=root/"journal",capture_dir=root/"capture",
            model_reservations=root/"budget",expected_repo_sha=self.REPO,
            expected_bundle_sha256=self.BUNDLE,
            expected_strategy_sha256=self.STRATEGY,
            read_active_series=lambda _:cloud,
            approval=approval,model_key=model_key,
            clock_now=lambda:dt(12),capture=source,
            acquire=fake_acquire,model_client=client or fake_model)

    def test_exact_active_one_owner_stages_and_models_once_without_cloud_post(self):
        from tests.test_v2r4_v3_entry_handoff_probe import dt
        c,plan,budget,cloud=self.inputs()
        self.assertTrue(plan["review_preflights"][0]["eligible_for_full_model_review"])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            responses=[]
            from tests.test_v3_paper_minipc_one_candidate_v1 import fake_model
            def model(prompt,key):
                responses.append(1)
                return fake_model(prompt,key)
            result=self.call(root,c,plan,budget,cloud,client=model)
            self.assertEqual(result["status"],"FIRST_SCANNER_MODEL_P4_DURABLE_WAIT_FOR_FOLLOWUP")
            self.assertEqual(len(responses),1)
            self.assertEqual(result["model_http_attempts_reserved"],1)
            self.assertEqual(result["first_minute_witness_status"],
                             "WAIT_FOR_FIRST_CLOSED_MINUTE_NO_CAPTURE")
            self.assertEqual(result["source_capture_calls"],0)
            self.assertFalse(result["orders"])
            self.assertFalse(result["paper_writer_active"])
            rows=[json.loads(p.read_text("utf-8"))
                  for p in (root/"journal").glob("*.json")]
            self.assertTrue(any(r["phase"]=="SCANNER_CAPTURE" for r in rows))
            self.assertTrue(any(r["phase"]=="P4_VALIDATION" for r in rows))
            self.assertEqual(len(list((root/"budget").glob("*.reserved.json"))),1)
            unchanged={p.name:p.read_bytes() for p in (root/"journal").glob("*.json")}
            repeat=self.call(root,c,plan,budget,cloud,
                client=lambda *_:self.fail("never a second model"))
            self.assertEqual(repeat["status"],"FIRST_SCANNER_ALREADY_JOURNALED_NO_MODEL_RETRY")
            self.assertEqual(unchanged,{p.name:p.read_bytes()
                    for p in (root/"journal").glob("*.json")})

    def test_bad_cloud_and_missing_budget_block_before_any_original_write(self):
        c,plan,approval,cloud=self.inputs()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for case in (
                None,
                dict(cloud,status="strategy_cutover_closed"),
                dict(cloud,config=dict(cloud["config"],release_repo_sha="f"*40)),
                dict(cloud,config=dict(cloud["config"],old_followup_owner_preserved=False)),
            ):
                with self.subTest(cloud=repr(case)[:85]):
                    with self.assertRaises(ValueError):
                        self.call(root,c,plan,approval,case)
                    self.assertFalse(list((root/"journal").glob("*.json")))
                    self.assertFalse(list((root/"budget").glob("*.reserved.json")))
            for budget in (None,dict(approval,explicit_user_new_budget_approval=False)):
                with self.subTest(budget=budget):
                    with self.assertRaises(ValueError):
                        self.call(root,c,plan,budget,cloud)
                    self.assertFalse(list((root/"journal").glob("*.json")))
                    self.assertFalse(list((root/"budget").glob("*.reserved.json")))

    def test_model_failure_is_durable_and_never_retried(self):
        c,plan,budget,cloud=self.inputs()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            failed=self.call(root,c,plan,budget,cloud,
                client=lambda *_: (_ for _ in ()).throw(ValueError("offline fake error")))
            self.assertEqual(failed["status"],"FIRST_SCANNER_MODEL_OR_SOURCE_INCOMPLETE_HOLD")
            self.assertEqual(failed["model_result"]["status"],
                             "MODEL_FAILED_HTTP_ATTEMPT_BUDGET_CONSUMED")
            self.assertEqual(len(list((root/"budget").glob("*.reserved.json"))),1)
            rows=[json.loads(p.read_text("utf-8"))
                  for p in (root/"journal").glob("*.json")]
            self.assertTrue(any(r["phase"]=="MODEL_ERROR" for r in rows))
            retry=self.call(root,c,plan,budget,cloud,
                client=lambda *_:self.fail("no HTTP retry"))
            self.assertEqual(retry["status"],"FIRST_SCANNER_ALREADY_JOURNALED_NO_MODEL_RETRY")

    def test_direct_postcas_model_bypass_refused(self):
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
        from tests.test_v2r4_v3_entry_handoff_probe import dt
        c,_,_,_=self.inputs()
        with tempfile.TemporaryDirectory() as td:
            journal=Path(td)
            with self.assertRaisesRegex(ValueError,"original OS owner"):
                one_candidate(candidate=c,series_id=self.SERIES,
                    local_receipts=journal,model_reservations=journal,
                    acquire=lambda *_:self.fail("direct source bypass"),
                    clock=lambda:dt(12))
            self.assertFalse(list(journal.glob("*.json")))

if __name__=="__main__":unittest.main()
