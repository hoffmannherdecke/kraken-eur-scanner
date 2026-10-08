"""Offline-only, non-trading regression for canonical Kraken symbol recovery."""
import importlib.util
import json
import tempfile
import unittest
import sys
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location("outage_local_runtime",ROOT/"tools/v2r4-paper-local-runtime.py")
runtime=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


def specimen(pair, observed):
    return {
        "kind":"V2R4_WS_SHADOW_DISCOVERY",
        "pair":pair,
        "observed_at_utc":runtime.iso(observed),
        "source_pair_received_at_utc":runtime.iso(observed),
        "last_eur":0.1,
        "liquidity_class_without_depth":runtime.STANDARD_EXECUTION_GATE,
        "would_request_fresh_recheck":True
    }


def fixture_app(root, now, event):
    app=root/"app"
    trading=root/"trading"
    (app/"paper_decisions").mkdir(parents=True)
    (trading/"State"/"v2r4-ws-shadow-events").mkdir(parents=True)
    (app/"paper_runtime_control.json").write_text(json.dumps({
        "series_id":"PAPER-V2R4-SYNTHETIC",
        "series_started_at_utc":runtime.iso(now-timedelta(hours=8)),
    }),"utf-8")
    (trading/"State"/"v2r4-ws-shadow-events"/"event.json").write_text(
        json.dumps(event),"utf-8"
    )
    key=root/"fake-token.txt"
    args=Namespace(app_root=app,trading_root=trading,
                   api_key_file=key,interval_seconds=2,once=True)
    return app,trading,args,key


class KrakenSymbolRecoveryTests(unittest.TestCase):
    @staticmethod
    def online():
        return [
            {"pair":"XBT/EUR","altname":"XBTEUR"},
            {"pair":"XDG/EUR","altname":"XDGEUR"},
            {"pair":"ETH/EUR","altname":"ETHEUR"},
        ]

    def test_canonical_symbols_and_legacy_names_resolve_to_online_rest(self):
        state={"altname_cache":{}}
        with patch.object(runtime,"eur_pairs",return_value=self.online()):
            runtime.refresh_altname_cache(state)
        self.assertEqual(state["altname_cache"]["BTC/EUR"],"XBTEUR")
        self.assertEqual(state["altname_cache"]["XBT/EUR"],"XBTEUR")
        self.assertEqual(state["altname_cache"]["DOGE/EUR"],"XDGEUR")
        self.assertEqual(state["altname_cache"]["XDG/EUR"],"XDGEUR")
        self.assertEqual(state["altname_cache"]["ETH/EUR"],"ETHEUR")
        self.assertNotIn("UNKNOWN/EUR",state["altname_cache"])

    def test_old_cache_always_migrates_even_if_age_is_fresh(self):
        state={"altname_cache":{"XBT/EUR":"XBTEUR"},
               "altname_cache_at_utc":runtime.iso()}
        with patch.object(runtime,"eur_pairs",return_value=self.online()) as lookup:
            runtime.refresh_altname_cache(state)
        lookup.assert_called_once()
        self.assertEqual(state["altname_cache_schema_version"],2)
        self.assertEqual(state["altname_cache"]["BTC/EUR"],"XBTEUR")

    def test_conflicting_online_pair_alias_refused(self):
        with patch.object(runtime,"eur_pairs",return_value=[
            {"pair":"XBT/EUR","altname":"XBTEUR"},
            {"pair":"BTC/EUR","altname":"DIFFERENT"},
        ]):
            with self.assertRaisesRegex(ValueError,"conflicting"):
                runtime.refresh_altname_cache({})

    def test_outage_age_and_future_clock_boundaries(self):
        now=datetime(2026,10,8,21,30,tzinfo=timezone.utc)
        fresh=runtime.recovery_event_age_state(now-timedelta(seconds=3600),now)
        stale=runtime.recovery_event_age_state(now-timedelta(seconds=3601),now)
        future=runtime.recovery_event_age_state(now+timedelta(seconds=31),now)
        self.assertEqual((fresh,stale,future),
                         ("FRESH","MISSED_DURING_OUTAGE","FUTURE_CLOCK_HOLD"))

    def test_stale_doge_is_recorded_not_retrospectively_evaluated(self):
        now=datetime(2026,10,8,21,30,tzinfo=timezone.utc)
        event=specimen("DOGE/EUR",now-timedelta(hours=2))
        with tempfile.TemporaryDirectory() as td:
            app,trading,args,key=fixture_app(Path(td),now,event)
            with patch.object(runtime,"utcnow",return_value=now), \
                 patch.object(runtime,"eur_pairs",return_value=self.online()), \
                 patch.object(runtime.subprocess,"run",side_effect=AssertionError("no evaluator on stale")):
                self.assertEqual(runtime.run_candidates(args),0)
            self.assertEqual(list((app/"paper_decisions").glob("*.json")),[])
            hb=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-heartbeat.json").read_text())
            self.assertEqual(hb["status"],"HEALTHY")
            self.assertEqual(hb["counters"]["missed_during_outage"],1)
            st=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-state.json").read_text())
            self.assertEqual(next(iter(st["processed"].values()))["status"],"MISSED_DURING_OUTAGE")

    def test_preexisting_decision_reconciled_without_replay(self):
        now=datetime(2026,10,8,21,30,tzinfo=timezone.utc)
        event=specimen("DOGE/EUR",now-timedelta(hours=2))
        with tempfile.TemporaryDirectory() as td:
            app,trading,args,key=fixture_app(Path(td),now,event)
            eid=runtime.event_id(event)
            cid=runtime.candidate_id_for_event(event,eid)
            (app/"paper_decisions"/(cid+".json")).write_text('{"decision":{"decision":"REJECT"}}',"utf-8")
            with patch.object(runtime,"utcnow",return_value=now), \
                 patch.object(runtime,"eur_pairs",return_value=self.online()), \
                 patch.object(runtime.subprocess,"run",side_effect=AssertionError("duplicate evaluator")):
                self.assertEqual(runtime.run_candidates(args),0)
            hb=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-heartbeat.json").read_text())
            self.assertEqual(hb["counters"]["reconciled_decisions"],1)
            self.assertEqual(hb["counters"]["missed_during_outage"],0)

    def test_fresh_canonical_doge_uses_online_rest_altname_without_order(self):
        now=datetime(2026,10,8,21,30,tzinfo=timezone.utc)
        event=specimen("DOGE/EUR",now-timedelta(seconds=30))
        with tempfile.TemporaryDirectory() as td:
            app,trading,args,key=fixture_app(Path(td),now,event)
            key.write_text("x"*32,"utf-8")
            with patch.object(runtime,"utcnow",return_value=now), \
                 patch.object(runtime,"eur_pairs",return_value=self.online()), \
                 patch.object(runtime.subprocess,"run",return_value=SimpleNamespace(returncode=0,stderr="")) as call:
                self.assertEqual(runtime.run_candidates(args),0)
            self.assertEqual(call.call_count,1)
            handoffs=list((app/"handoff_queue").glob("*.json"))
            self.assertEqual(len(handoffs),1)
            candidate=json.loads(handoffs[0].read_text())
            self.assertEqual(candidate["altname"],"XDGEUR")
            self.assertEqual(candidate["action"],"REVIEW_ONLY_NOT_ORDER")
            hb=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-heartbeat.json").read_text())
            self.assertEqual(hb["counters"]["evaluated"],1)

    def test_unknown_online_pair_is_deferred_not_permanently_blacklisted(self):
        now=datetime(2026,10,8,21,30,tzinfo=timezone.utc)
        event=specimen("UNKNOWN/EUR",now-timedelta(seconds=30))
        with tempfile.TemporaryDirectory() as td:
            app,trading,args,key=fixture_app(Path(td),now,event)
            with patch.object(runtime,"utcnow",return_value=now), \
                 patch.object(runtime,"eur_pairs",return_value=self.online()), \
                 patch.object(runtime.subprocess,"run",side_effect=AssertionError("no offline pair eval")):
                self.assertEqual(runtime.run_candidates(args),0)
            hb=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-heartbeat.json").read_text())
            st=json.loads((trading/"State"/"v2r4-paper-candidate-runtime-state.json").read_text())
            self.assertEqual(hb["counters"]["symbol_pending"],1)
            self.assertEqual(hb["counters"]["evaluated"],0)
            self.assertEqual(st["processed"],{})

if __name__=="__main__":
    unittest.main()
