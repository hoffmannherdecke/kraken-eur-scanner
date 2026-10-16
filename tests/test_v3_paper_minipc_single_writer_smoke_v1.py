"""On-host one-shot scanner-to-immutable-stage-to-real-consumer boundary; no HTTP in CI."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper_evaluator.v3_paper_minipc_single_writer_smoke_v1 import (
    SERIES, run_one_shot,
)
from tests.test_v3_experimental_paper_initial_review_v1 import fixture

MOMENT = datetime(2026, 10, 12, 10, 0, 12, tzinfo=timezone.utc)


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def physical_root(parent, *, candidate_age=90, mismatch_pin=False):
    root = Path(parent) / "Trading"
    repo = root / "Repos" / "kraken-eur-scanner"
    runtime = root / "Runtime" / "v2r4-paper"
    queue = runtime / "handoff_queue"
    queue.mkdir(parents=True)
    repo.mkdir(parents=True)
    state = root / "State"
    state.mkdir(parents=True)
    research = root / "Research" / "V3Paper"
    research.mkdir(parents=True)
    (root / "Secrets").mkdir()
    (root / "Secrets" / "v3-paper-relay-token.txt").write_text(
        "CANARY_CI_FAKE_NOT_A_REAL_TOKEN_LONG_ENOUGH", "utf-8")
    pins = []
    for i in range(9):
        rel = f"pinned/observer{i}.py"
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        body = f"ORIGINAL_28H_PIN_{i}".encode()
        path.write_bytes(body if not mismatch_pin or i != 8 else b"BAD")
        pins.append({"relative_path": rel,
                     "sha256": hashlib.sha256(body).hexdigest()})
    (state / "v3-canary-observer-28h-plan.json").write_text(json.dumps({
        "kind": "V3_LOCAL_READONLY_CANARY_28H_PLAN_V1",
        "task_name": "CryptoMiniPC-V3CanaryObservation28h",
        "until_utc": iso(MOMENT+timedelta(hours=28)),
        "paper_only": True, "v2r4_unchanged": True,
        "model_http_calls_authorized": 0,
        "orders": False, "pinned_file_hashes": pins,
    }))
    (state / "v3-canary-observer-28h-heartbeat.json").write_text(json.dumps({
        "status": "HEALTHY_NO_NEW_CLOUD_EVENTS",
        "checked_at_utc": iso(MOMENT),
        "v2r4_unchanged": True, "model_http_calls": 0,
    }))
    (runtime / "paper_runtime_control.json").write_text(json.dumps({
        "series_id": "PAPER-V2R4-20261009T110135Z",
        "paper_only": True, "real_money_actions_enabled": False,
    }))
    cand = {
        "kind": "CANONICAL_CANDIDATE_HANDOFF_V1",
        "candidate_id": "REAL-V2R4-ORIGINAL-00001",
        "pair": "XBT/EUR", "altname": "XBTEUR",
        "event_time_utc": iso(MOMENT-timedelta(seconds=candidate_age)),
        "action": "REVIEW_ONLY_NOT_ORDER",
    }
    (queue / "one-original.json").write_text(json.dumps(cand), "utf-8")
    return root, repo, research, cand


def fake_pairs():
    return [{"symbol": "XBT/EUR", "altname": "XBTEUR", "status": "online"}]


def fake_acquire(_):
    return tuple(fixture()[1:])


class SingleWriterPhysicalSmokeTests(unittest.TestCase):
    def test_first_real_owner_original_stage_then_kraken_then_exact_cloud_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root, repo, research, cand = physical_root(td)
            observed = []
            def witness(candidate):
                observed.append(candidate["candidate_id"])
                return fake_acquire(candidate)
            def cloud(_, token, payload):
                self.assertEqual(token, "CANARY_CI_FAKE_NOT_A_REAL_TOKEN_LONG_ENOUGH")
                self.assertEqual(payload["series_id"], SERIES)
                self.assertTrue(2 <= len(payload["receipts"]) <= 5)
                self.assertTrue(all("CANARY" in payload["series_id"]
                                    for _ in payload["receipts"]))
                return {"ok": True, "accepted_receipts": len(payload["receipts"]),
                        "series_id": SERIES}
            outcome = run_one_shot(
                trading_root=root, repository=repo, execute=True, cloud_ack=True,
                pair_loader=fake_pairs, acquire=witness,
                clock=lambda: MOMENT, cloud_post=cloud)
            self.assertEqual(outcome["status"],
                             "ONE_REAL_ORIGINAL_STAGED_AND_KRAKEN_REVIEWED_CANARY_ONLY")
            self.assertEqual(observed, [cand["candidate_id"]])
            self.assertEqual(outcome["staged_immutable_receipts"], 2)
            self.assertTrue(outcome["cloud_ack_verified"])
            self.assertEqual(outcome["model_http_calls"], 0)
            self.assertFalse(outcome["orders"])
            self.assertFalse(outcome["v3_paper_activated"])
            self.assertFalse(outcome["source_owner_runtime_authenticated"])
            self.assertTrue((research / "writer-smoke-20261012" / "cloud-ack.json").exists())
            staged = list((research / "writer-smoke-20261012" / "journal").glob("*.json"))
            events = [json.loads(f.read_text()) for f in staged]
            self.assertEqual(len(events), outcome["cloud_receipts_accepted"])
            self.assertEqual(
                sum(e["phase"]=="SCANNER_CAPTURE" for e in events), 1)
            self.assertEqual(
                sum(e["phase"]=="FULL_REVIEW_ELIGIBILITY" for e in events), 2)
            self.assertNotIn("MODEL_RESPONSE", [e["phase"] for e in events])
            self.assertFalse((research/"journal").exists())
            self.assertEqual(json.loads((root/"Runtime"/"v2r4-paper"/
                                        "paper_runtime_control.json").read_text())["series_id"],
                             "PAPER-V2R4-20261009T110135Z")
            with self.assertRaises(ValueError):
                run_one_shot(trading_root=root,repository=repo,execute=True,
                             pair_loader=fake_pairs,acquire=witness,clock=lambda:MOMENT)
            self.assertEqual(observed, [cand["candidate_id"]])

    def test_dry_run_or_no_fresh_never_creates_single_writer_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            root, repo, research, cand = physical_root(td)
            dry=run_one_shot(trading_root=root, repository=repo, clock=lambda:MOMENT)
            self.assertEqual(dry["status"],"ONE_FRESH_V2R4_ORIGINAL_PLAN_ONLY")
            self.assertFalse((research/"writer-smoke-20261012").exists())
            with self.assertRaises(ValueError):
                run_one_shot(trading_root=root,repository=repo,cloud_ack=True,
                             clock=lambda:MOMENT)
        with tempfile.TemporaryDirectory() as td:
            root,repo,research,_=physical_root(td,candidate_age=701)
            no=run_one_shot(trading_root=root,repository=repo,execute=True,
                            cloud_ack=True,clock=lambda:MOMENT)
            self.assertEqual(no["status"],"NO_FRESH_UNPROCESSED_10M_ORIGINAL_NO_WRITES")
            self.assertFalse((research/"writer-smoke-20261012").exists())

    def test_tampered_existing_observer_pin_blocks_before_any_write(self):
        with tempfile.TemporaryDirectory() as td:
            root,repo,research,_=physical_root(td,mismatch_pin=True)
            with self.assertRaises(ValueError):
                run_one_shot(trading_root=root,repository=repo,execute=True,
                             pair_loader=fake_pairs,acquire=fake_acquire,
                             clock=lambda:MOMENT)
            self.assertFalse((research/"writer-smoke-20261012").exists())

    def test_public_kraken_pair_must_match_original_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            root,repo,research,_=physical_root(td)
            result=run_one_shot(trading_root=root,repository=repo,execute=True,
                pair_loader=lambda:[{"symbol":"XBT/EUR","altname":"FAKEEUR",
                                     "status":"online"}],acquire=fake_acquire,
                clock=lambda:MOMENT)
            self.assertEqual(result["status"],"KRAKEN_SPOT_EUR_PAIR_NOT_VERIFIED_NO_WRITES")
            self.assertFalse((research/"writer-smoke-20261012").exists())

    def test_stale_after_public_metadata_fails_before_first_file_write(self):
        with tempfile.TemporaryDirectory() as td:
            root,repo,research,_=physical_root(td,candidate_age=590)
            calls=[MOMENT, MOMENT+timedelta(seconds=20)]
            def advancing():
                return calls.pop(0)
            result=run_one_shot(trading_root=root,repository=repo,execute=True,
                pair_loader=fake_pairs,acquire=fake_acquire,clock=advancing)
            self.assertEqual(result["status"],"ORIGINAL_EXPIRED_DURING_PUBLIC_METADATA_NO_WRITES")
            self.assertFalse((research/"writer-smoke-20261012").exists())



    def test_current_approved_one_shot_joins_genuine_first_bar_budget_p4_cloud(self):
        """Synthetic I/O: the real orchestration modules and lock, no API."""
        from paper_evaluator.v3_paper_minipc_single_writer_smoke_v1 import (
            run_approved_live_canary,_APPROVED_ROOT,_APPROVED_CANARY,
            _FROZEN_V2R4_SHA,
        )
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import reserve_before_http,REVISION
        from paper_evaluator.v3_experimental_paper_journal_v1 import (
            make_receipt,store_receipt_explicitly,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m
        pin="f"*40
        with tempfile.TemporaryDirectory() as td:
            root,prod,research,candidate=physical_root(td,candidate_age=150)
            stage=root/"V3Stage"/"source-current"
            stage.mkdir(parents=True)
            (root/"Secrets"/"openai-api-key.txt").write_text(
                "sk-ci-SYNTHETIC-NO-REAL-KEY-1234567890","utf-8")
            first=datetime.fromisoformat(candidate["event_time_utc"].replace("Z","+00:00"))
            first=first.replace(second=0,microsecond=0)+timedelta(minutes=1)
            calls=[]
            def original(*,pair,altname,outdir):
                calls.append(("kraken",pair))
                def loader(_):
                    return {"error":[],"result":{altname:[
                        [int(first.timestamp()),"2","2.1","1.9","2","2","10",2],
                    ],"last":1}}
                return capture_public_1m(
                    pair=pair,altname=altname,outdir=outdir,
                    loader=loader,clock=lambda:MOMENT)
            def paid_stub(**kw):
                self.assertTrue(kw["allow_model"])
                self.assertTrue(kw["admit_staged_scanner_one_approved_model"])
                calls.append(("model",kw["candidate"]["candidate_id"]))
                reserve_before_http(
                    kw["model_reservations"],kw["approval"],
                    kw["series_id"],kw["candidate"]["candidate_id"],
                    iso(MOMENT))
                for phase,result,data in (
                    ("MODEL_REQUEST","PASS",{"model_http_attempts_reserved":1}),
                    ("MODEL_RESPONSE","PASS",{"raw_model_decision":"WAIT",
                                               "model_response_at_utc":iso(MOMENT)}),
                    ("P4_VALIDATION","WAIT",{"p4_decision":"WAIT",
                                              "p4_status":"VALIDATED_SYNTHETIC"}),
                ):
                    receipt=make_receipt(
                        series_id=kw["series_id"],revision=REVISION,
                        candidate_id=kw["candidate"]["candidate_id"],
                        pair=kw["candidate"]["pair"],
                        event_time_utc=kw["candidate"]["event_time_utc"],
                        known_at_utc=iso(MOMENT),phase=phase,
                        result=result,event_key="FRESHRECHECK",data=data)
                    store_receipt_explicitly(kw["local_receipts"],receipt)
                return {"status":"V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION",
                        "p4_decision":"WAIT"}
            def cloud(url,token,payload):
                self.assertEqual(payload["series_id"],_APPROVED_CANARY)
                self.assertTrue(5<=len(payload["receipts"])<=15)
                calls.append(("cloud",len(payload["receipts"])))
                return {"ok":True,"series_id":_APPROVED_CANARY,
                        "accepted_receipts":len(payload["receipts"])}
            def git_head(p):
                return _FROZEN_V2R4_SHA if p==prod else pin
            out=run_approved_live_canary(
                trading_root=root,repository=stage,expected_stage_sha=pin,
                pair_loader=fake_pairs,capture=original,
                worker=paid_stub,cloud_post=cloud,
                git_head=git_head,clock=lambda:MOMENT)
            self.assertEqual(out["status"],"APPROVED_CANARY_MODEL_P4_CLOUD_ACK")
            self.assertEqual([x[0] for x in calls],
                             ["kraken","model","cloud"])
            self.assertEqual(out["model_http_attempts"],1)
            self.assertGreaterEqual(out["cloud_receipts_accepted"],5)
            self.assertEqual(out["model_decision"],"WAIT")
            self.assertFalse(out["paper_writer_active"])
            self.assertFalse(out["v2r4_changed"])
            self.assertFalse(out["full_physical_paper_release_proof"])
            self.assertTrue((research/_APPROVED_ROOT/"cloud-ack.json").is_file())
            self.assertEqual(len(list((research/_APPROVED_ROOT/"budgets").glob(
                "*.reserved.json"))),1)
            with self.assertRaisesRegex(ValueError,"ALREADY_RESERVED_NO_RETRY"):
                run_approved_live_canary(
                    trading_root=root,repository=stage,expected_stage_sha=pin,
                    pair_loader=fake_pairs,capture=lambda **kw:self.fail("GET twice"),
                    worker=lambda **kw:self.fail("model twice"),
                    cloud_post=lambda *a:self.fail("POST twice"),
                    git_head=git_head,clock=lambda:MOMENT)

    def test_current_approved_no_key_or_stale_original_stops_before_network_write(self):
        from paper_evaluator.v3_paper_minipc_single_writer_smoke_v1 import (
            run_approved_live_canary,_APPROVED_ROOT,_FROZEN_V2R4_SHA,
        )
        pin="f"*40
        for stale,key_ok in ((False,False),(True,True)):
            with self.subTest(stale=stale,key_ok=key_ok),tempfile.TemporaryDirectory() as td:
                root,prod,research,_=physical_root(
                    td,candidate_age=650 if stale else 150)
                stage=root/"V3Stage"/"source-current"
                stage.mkdir(parents=True)
                if key_ok:
                    (root/"Secrets"/"openai-api-key.txt").write_text(
                        "sk-ci-SYNTHETIC-NO-REAL-KEY-1234567890","utf-8")
                def git_head(p):
                    return _FROZEN_V2R4_SHA if p==prod else pin
                if not key_ok:
                    with self.assertRaisesRegex(ValueError,"private local credentials"):
                        run_approved_live_canary(
                            trading_root=root,repository=stage,
                            expected_stage_sha=pin,
                            pair_loader=lambda:self.fail("No metadata GET"),
                            git_head=git_head,clock=lambda:MOMENT)
                else:
                    x=run_approved_live_canary(
                        trading_root=root,repository=stage,
                        expected_stage_sha=pin,
                        pair_loader=lambda:self.fail("No metadata GET"),
                        git_head=git_head,clock=lambda:MOMENT)
                    self.assertEqual(x["model_http_attempts"],0)
                    self.assertEqual(x["status"],
                                     "NO_FRESH_ORIGINAL_NO_MODEL_OR_CLOUD")
                self.assertFalse((research/_APPROVED_ROOT).exists())

if __name__ == "__main__":
    unittest.main()
