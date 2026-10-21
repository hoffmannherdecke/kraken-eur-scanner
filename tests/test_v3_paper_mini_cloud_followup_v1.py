"""No outside IO in CI: Mini-PC closed 1m captures, 6h net outcomes, cloud ACK."""
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m,assemble
from paper_evaluator.v3_paper_minipc_followup_v1 import record_horizon
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate,REVISION
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once,read_active_paper_series
from tests.test_v3_paper_minipc_one_candidate_v1 import (
    fixture, fake_acquire, fake_model, valid_approval,SID
)
from tests.test_v2r4_v3_entry_handoff_probe import dt


class MiniPcAndCloudTests(unittest.TestCase):
    def test_live_series_readback_uses_existing_relay_token_without_cloud_write(self):
        sid="PAPER-V3-20261017T141500Z"
        token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL"
        payloads=[]
        original={
            "ok":True,"kind":"V3_PAPER_ACTIVE_SERIES_READONLY_V1",
            "series_id":sid,"status":"active",
            "strategy_revision":REVISION,
            "observed_at_utc":"2026-10-17T14:16:00Z",
            "read_only":True,"orders":False,
            "real_money_actions":False,"cloud_cas_performed":False,
            "physical_release_proofs_credited":0,
            "config":{"series_id":sid,"strategy_revision":REVISION,
                      "release_repo_sha":"a"*40,
                      "runtime_bundle_fingerprint_sha256":"b"*64,
                      "strategy_fingerprint_sha256":"c"*64,
                      "paper_only":True,
                      "real_money_actions_enabled":False,
                      "automatic_activation_allowed":False,
                      "physical_v2r4_writer_fence_verified":True,
                      "supervisor_old_intake_rearm_blocked":True,
                      "old_followup_owner_preserved":True,
                      "independent_six_e2e_proofs_verified":True}
        }
        def post(url,secret,payload):
            self.assertIn("v3-paper-evidence-relay",url)
            self.assertEqual(secret,token)
            payloads.append(payload)
            return original
        out=read_active_paper_series(series_id=sid,token=token,post=post)
        self.assertEqual(payloads,[{"action":"read_active_paper_series","series_id":sid}])
        self.assertEqual(out["series_id"],sid)
        self.assertEqual(out["observed_at_utc"],original["observed_at_utc"])
        self.assertEqual(out["config"]["runtime_bundle_fingerprint_sha256"],"b"*64)
        self.assertNotIn("cloud_cas_performed",out)
        self.assertNotIn("orders",out)

    def test_readback_rejects_canary_and_embedded_canary_before_network(self):
        for bad in ("PAPER-V3-CANARY-ONESHOT-20261016",
                    "PAPER-V3-LIVE-CANARY-FAKE",
                    "PAPER-V3-20261017T141500Z-extra",
                    "PAPER-V3-20261017T141500Z/../../",
                    "PAPER-V2R4-20261009T110135Z"):
            with self.subTest(series=bad):
                with self.assertRaises(ValueError):
                    read_active_paper_series(
                        series_id=bad,token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",
                        post=lambda *_:self.fail("invalid series contacted Cloud"))

    def test_fail_closed_missing_inactive_or_foreign_cloud_receipt(self):
        sid="PAPER-V3-20261017T141500Z"
        base={"ok":True,"kind":"V3_PAPER_ACTIVE_SERIES_READONLY_V1",
            "series_id":sid,"status":"active","strategy_revision":REVISION,
            "observed_at_utc":"2026-10-17T14:16:00Z","read_only":True,
            "orders":False,"real_money_actions":False,
            "cloud_cas_performed":False,"physical_release_proofs_credited":0,
            "config":{"series_id":sid}}
        badcases=(None,{},dict(base,ok=False),
             dict(base,status="strategy_cutover_closed"),
             dict(base,series_id="PAPER-V3-20261017T141501Z"),
             dict(base,kind="V3_FAKE_RELEASE"),
             dict(base,read_only=False),
             dict(base,orders=True),
             dict(base,cloud_cas_performed=True),
             dict(base,physical_release_proofs_credited=6),
             dict(base,config=None),
             dict(base,observed_at_utc=None))
        for bad in badcases:
            with self.subTest(bad=repr(bad)[:110]):
                with self.assertRaises(ValueError):
                    read_active_paper_series(
                        series_id=sid,token="TEST_ONLY_SECRET_LONG_ENOUGH_NOT_REAL",
                        post=lambda *_:bad)
        with self.assertRaises(ValueError):
            read_active_paper_series(series_id=sid,token="too_short",
                post=lambda *_:self.fail("no network with short token"))

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


    def test_v3_ack_history_over_5000_preserves_every_prior_cloud_receipt(self):
        """No V2R4 5,000-entry pruning in V3; original ACKs remain durable."""
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / "journal"
            journal.mkdir()
            identity = {
                "series_id": SID,
                "candidate_id": "V3-CLOUD-CAPACITY-TEST-0001",
                "phase": "FIRST_SKIP",
                "event_key": "test-only-new-receipt",
            }
            event_id = hashlib.sha256("|".join(str(identity[key]) for key in
                ("series_id", "candidate_id", "phase", "event_key")).encode()).hexdigest()
            receipt = {**identity, "revision": REVISION,
                       "real_money_actions": False, "orders": False}
            (journal / (event_id + ".json")).write_text(
                json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
            prior = [f"{i:064x}" for i in range(5001)]
            ack = root / "cloud_ack.json"
            ack.write_text(json.dumps({
                "schema": 1, "series_id": SID,
                "revision": REVISION, "acked": prior}), encoding="utf-8")
            token = "CI_OFFLINE_ONLY_NOT_A_REAL_SECRET_000000"
            posts = []
            def relay(_url, _token, payload):
                self.assertEqual(payload["action"], "sync_paper_receipts")
                self.assertEqual(len(payload["receipts"]), 1)
                posts.append(payload)
                return {"ok": True, "series_id": SID, "accepted_receipts": 1}
            result = sync_once(journal=journal, series_id=SID,
                               ack_file=ack, token=token, post=relay)
            self.assertEqual(result["total_acked"], 5002)
            persisted = json.loads(ack.read_text(encoding="utf-8"))
            self.assertEqual(len(persisted["acked"]), 5002)
            self.assertTrue(set(prior).issubset(persisted["acked"]))
            self.assertIn(event_id, persisted["acked"])
            again = sync_once(journal=journal, series_id=SID,
                              ack_file=ack, token=token,
                              post=lambda *_: self.fail("unchanged V3 event re-uploaded"))
            self.assertEqual(again["status"], "NO_UNSYNCED_V3_RECEIPTS")
            self.assertEqual(len(posts), 1)

    def test_v3_large_ack_history_failed_post_keeps_original_retry_state(self):
        """Failed Cloud transport must not acknowledge, truncate, or drop the retry."""
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            journal = root / "journal"
            journal.mkdir()
            candidate = "V3-CLOUD-FAILURE-TEST-0002"
            phase = "FIRST_SKIP"
            event_key = "retry-after-network-timeout"
            event_id = hashlib.sha256(
                "|".join((SID, candidate, phase, event_key)).encode()).hexdigest()
            receipt = {"series_id": SID, "candidate_id": candidate,
                       "phase": phase, "event_key": event_key,
                       "revision": REVISION, "real_money_actions": False}
            (journal / (event_id + ".json")).write_text(
                json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
            ack = root / "cloud_ack.json"
            old_ids = [f"{i:064x}" for i in range(5001)]
            old_bytes = json.dumps({"schema": 1, "series_id": SID,
                                    "revision": REVISION,
                                    "acked": old_ids}).encode("utf-8")
            ack.write_bytes(old_bytes)
            token = "CI_OFFLINE_ONLY_NOT_A_REAL_SECRET_000000"
            def failed(_url, _token, _payload):
                raise TimeoutError("synthetic delivery timeout")
            with self.assertRaises(TimeoutError):
                sync_once(journal=journal, series_id=SID,
                          ack_file=ack, token=token, post=failed)
            self.assertEqual(ack.read_bytes(), old_bytes)
            seen = []
            def recovered(_url, _token, payload):
                seen.extend(payload["receipts"])
                return {"ok": True, "series_id": SID,
                        "accepted_receipts": len(payload["receipts"])}
            result = sync_once(journal=journal, series_id=SID,
                               ack_file=ack, token=token, post=recovered)
            self.assertEqual(result["total_acked"], 5002)
            self.assertEqual([r["event_id"] for r in seen], [event_id])
            self.assertTrue(set(old_ids).issubset(
                json.loads(ack.read_text(encoding="utf-8"))["acked"]))


if __name__=="__main__":
    unittest.main()
