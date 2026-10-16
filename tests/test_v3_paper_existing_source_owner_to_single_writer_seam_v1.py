"""Exact existing H10/H11/H5 research → verified source → V3 future writer seam."""
from __future__ import annotations
import copy,unittest,hmac,hashlib
from paper_evaluator.v3_paper_source_owner_hmac_v1 import (
    KIND as OWNER_AUTH_KIND,canonical_owner_message,
)
from paper_evaluator.v3_paper_existing_owner_source_bridge_v1 import (
    join_owner_sources,fingerprint,
)
from paper_evaluator.v3_paper_single_writer_preflight_v1 import plan_writer_preflight
from tests.test_v3_paper_shared_candidate_intake_plan_v1 import (
    SID,PAIR,scanner,
)
from tests.test_v3_paper_positive_source_entry_v1 import (
    official,money,poly,movement,
)
from tests.test_v3_experimental_paper_initial_review_v1 import fixture
from tests.test_v2r4_v3_entry_handoff_probe import dt

OWNER={
    "news_sentiment":["OFFICIAL_US_CURATOR"],
    "smart_money_h10":["H10_CAPTURE_OWNER"],
    "polymarket_h11":["H11_CAPTURE_OWNER"]
}
KEYS={
    "news_sentiment":{"OFFICIAL_US_CURATOR":b"N"*32},
    "smart_money_h10":{"H10_CAPTURE_OWNER":b"H"*32},
    "polymarket_h11":{"H11_CAPTURE_OWNER":b"P"*32}
}
H10={"status":"H10_PIT_CONTEXT_ONLY","sources":{
    "smart_money_h10":{
        "pair":"XBT/EUR","source_verified":True,
        "source_owner":"EXISTING_H10_HYPERLIQUID_PROSPECTIVE_CAPTURE",
        "consensus_direction":"LONG","independent_wallet_count":20}}}
H11={"kind":"V3_H11_POLYMARKET_PROSPECTIVE_STATE_CAPTURE_V1",
     "status":"PASS","rows":[{"market_id":"synthetic-market-42",
                                "tokens":[{"midpoint":.7}]}]}
H5={"kind":"V3_H5_MACRO_EVENT_WINDOW_PIT_SMOKE_V1",
    "events":[{"event_family":"CPI","known_at_utc":dt(3)}]}
def event(name,snapshot,move=None):
    packet={"source_name":name,"pair":"XBT/EUR",
            "altname":"XBTEUR","snapshot":snapshot,
            "market_move":move,
            "owner_integrity":{
                "authenticated_owner_id":snapshot["source_owner"],
                "authentication_checked_by_trusted_caller":True,
                "canonical_payload_sha256":fingerprint(snapshot),
                "proof_version":OWNER_AUTH_KIND,
                "signed_at_utc":dt(12)
            }}
    packet["owner_integrity"]["owner_hmac_sha256"]=hmac.new(
        KEYS[name][snapshot["source_owner"]],
        canonical_owner_message(packet),hashlib.sha256).hexdigest()
    return packet

def bridge(events=(),h10=H10,h11=H11,h5=H5,owners=OWNER,keys=KEYS):
    return join_owner_sources(
        h10_context=h10,h11_market_capture=h11,
        h5_macro_calendar=h5,owner_event_packets=list(events),
        authenticated_owner_ids=owners,decision_at_utc=dt(12),
        trusted_owner_hmac_keys=keys)
def preflight(scanners=(),owner_events=(),observations=None,limit=3):
    return plan_writer_preflight(
        scanner_events=list(scanners),owner_event_packets=list(owner_events),
        h10_context=H10,h11_market_capture=H11,h5_macro_calendar=H5,
        authenticated_owner_ids=OWNER,journal_receipts=[],known_pairs=PAIR,
        market_observations=observations if observations is not None else {},
        series_id=SID,decision_at_utc=dt(12),max_reviews=limit,
        trusted_owner_hmac_keys=KEYS)
def xbt_real_pit_fixture():
    c,e,t,m=fixture()
    return {"XBT/EUR":{"ticker":t,"entry_evidence":e,"pair_metadata":m}}

class ExistingSourceOwnerBridgeTests(unittest.TestCase):
    def test_full_staged_scanner_model_p4_and_cloud_ack_single_integrated_path(self):
        """Only injected fake-model and fake Cloud; no real paid/physical proof."""
        import json,tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once
        from tests.test_v3_paper_minipc_one_candidate_v1 import (
            valid_approval,fake_acquire,fake_model,
        )
        plan=preflight(scanners=[
            scanner("V3-INITIAL-EUR-1","XBT/EUR",dt(9))],
            observations=xbt_real_pit_fixture())
        self.assertEqual(len(plan["selected_candidates"]),1)
        self.assertEqual(plan["selected_candidates"][0]["entry_origin"],"SCANNER")
        self.assertTrue(plan["review_preflights"][0]
                        ["eligible_for_full_model_review"])
        self.assertFalse(plan["model_http_authorized"])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);journal=root/"journal";budget=root/"budget"
            journal.mkdir();budget.mkdir()
            staged=stage_receipts_explicitly(
                preflight=plan,journal_directory=journal)
            self.assertEqual(staged["written"],2)
            original={p.name:p.read_bytes() for p in journal.glob("*.json")}
            approval=dict(valid_approval(),series_id=SID)
            attempts=[]
            def fake_once(prompt,key):
                attempts.append((prompt,key))
                return fake_model(prompt,key)
            modeled=one_candidate(candidate=plan["selected_candidates"][0],
                series_id=SID,local_receipts=journal,model_reservations=budget,
                approval=approval,model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=fake_once,
                clock=lambda:dt(12),allow_model=True,
                admit_staged_scanner_one_approved_model=True)
            self.assertEqual(modeled["status"],
                             "V3_CANARY_MODEL_P4_RECORDED_NO_PAPER_ACTIVATION")
            self.assertEqual(modeled["p4_decision"],"BUY_SCOUT")
            self.assertEqual(len(attempts),1)
            self.assertEqual(len(list(budget.glob("*.reserved.json"))),1)
            self.assertEqual({p.name:p.read_bytes() for p in journal.glob("*.json")
                              if p.name in original},original)
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual({r["event_key"] for r in rows
                              if r["phase"]=="MODEL_REQUEST"},{"FRESHRECHECK"})
            self.assertEqual(len([r for r in rows
                                 if r["phase"]=="SCANNER_CAPTURE"]),1)
            self.assertTrue(any(r["phase"]=="P4_VALIDATION"
                                and r["result"]=="BUY_SCOUT" for r in rows))
            self.assertEqual({r["phase"] for r in rows if r["result"]=="PENDING"},
                {"FOLLOWUP_6H","FOLLOWUP_24H","FOLLOWUP_72H"})
            calls=[]
            def fake_cloud(url,token,payload):
                calls.append(payload)
                return {"ok":True,"accepted_receipts":len(payload["receipts"]),
                        "series_id":SID}
            ack=root/"ack.json"
            cloud=sync_once(journal=journal,series_id=SID,ack_file=ack,
                token="SYNTHETIC_TEST_ONLY_V3_RELAY_TOKEN_NO_NETWORK",
                post=fake_cloud)
            self.assertEqual(cloud["status"],"V3_RECEIPTS_CLOUD_ACK_VERIFIED")
            self.assertEqual(len(calls),1)
            self.assertEqual(cloud["count"],len(rows))
            no_retry=sync_once(journal=journal,series_id=SID,ack_file=ack,
                token="SYNTHETIC_TEST_ONLY_V3_RELAY_TOKEN_NO_NETWORK",
                post=lambda *_: (_ for _ in ()).throw(
                    AssertionError("no duplicate cloud originals")))
            self.assertEqual(no_retry["count"],0)
            repeated=one_candidate(candidate=plan["selected_candidates"][0],
                series_id=SID,local_receipts=journal,model_reservations=budget,
                approval=approval,model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=lambda *_: (_ for _ in ()).throw(
                    AssertionError("second Kraken read forbidden")),
                model_client=lambda *_: (_ for _ in ()).throw(
                    AssertionError("second paid model forbidden")),
                clock=lambda:dt(12),allow_model=True,
                admit_staged_scanner_one_approved_model=True)
            self.assertEqual(repeated["status"],
                             "NO_UNIQUE_UNPROCESSED_STAGED_SCANNER_NO_RECHECK")
            self.assertEqual(len(attempts),1)
            self.assertFalse(plan["paper_writer_active"])
            self.assertFalse(plan["cloud_active_series_changed"])

    def test_real_current_h10_edge_h11_raw_h5_macro_not_auto_positive_signal(self):
        result=bridge()
        self.assertEqual(result["owner_source_events"],[])
        self.assertEqual(result["status"],"NO_AUTHENTICATED_POSITIVE_OWNER_EVENTS")
        self.assertEqual(result["raw_source_dispositions"]["smart_money_h10"],
                         "H10_RESEARCH_CONTEXT_NOT_CONFIRMED_INDEPENDENT_FILLS")
        self.assertEqual(result["raw_source_dispositions"]["polymarket_h11"],
                         "H11_RAW_MARKET_BOOK_ONLY_NO_PAIR_IMPACT_OR_PROBABILITY_DELTA")
        self.assertEqual(result["raw_source_dispositions"]["news_sentiment"],
                         "H5_MACRO_CALENDAR_NOT_VERIFIED_OFFICIAL_COIN_NEWS")
        self.assertFalse(result["model_http_authorized"])
        self.assertFalse(result["paper_writer_active"])
        self.assertFalse(result["orders"])

    def test_verified_separate_owner_events_all_three_real_positive_origins(self):
        for kind,payload,move in (
            ("news_sentiment",official(),None),
            ("smart_money_h10",money(),None),
            ("polymarket_h11",poly(),movement()),
        ):
            with self.subTest(origin=kind):
                record=bridge([event(kind,payload,move)])
                self.assertEqual(record["status"],"VERIFIED_OWNER_POSITIVE_EVENTS_PRESENT")
                self.assertEqual(len(record["owner_source_events"]),1)
                self.assertEqual(record["owner_source_events"][0]["pair"],"XBT/EUR")
                self.assertFalse(record["model_http_authorized"])
                self.assertFalse(record["orders"])

    def test_attestation_identity_and_exact_digest_are_not_optional(self):
        original=event("news_sentiment",official())
        rejected=[
            dict(original,owner_integrity=dict(original["owner_integrity"],
                                               authenticated_owner_id="UNTRUSTED")),
            dict(original,owner_integrity=dict(original["owner_integrity"],
                                               authentication_checked_by_trusted_caller=False)),
            dict(original,snapshot=dict(original["snapshot"],sentiment="NEGATIVE")),
            dict(original,owner_integrity=dict(original["owner_integrity"],
                                               canonical_payload_sha256="0"*64)),
            dict(original,snapshot=dict(original["snapshot"],
                                        official_primary_url="https://www.treasury.gov.evil.invalid")),
        ]
        for input_ in rejected:
            with self.subTest(input=input_):
                result=bridge([input_])
                self.assertEqual(result["owner_source_events"],[])
                self.assertEqual(sum(result["source_event_rejections"].values()),1)
        with self.assertRaises(ValueError):
            bridge(owners={"news_sentiment":["OFFICIAL_US_CURATOR"]})
        with self.assertRaises(ValueError):
            bridge(events=[original]*61)

    def test_sha256_and_caller_trust_boolean_cannot_authenticate_any_source(self):
        trusted=event("news_sentiment",official())
        for packet in (
            dict(trusted,owner_integrity={
                "authenticated_owner_id":"OFFICIAL_US_CURATOR",
                "authentication_checked_by_trusted_caller":True,
                "canonical_payload_sha256":fingerprint(official())
            }),
            dict(trusted,owner_integrity={
                **trusted["owner_integrity"],"owner_hmac_sha256":"0"*64}),
            dict(trusted,source_name="smart_money_h10")
        ):
            with self.subTest(packet=packet):
                result=bridge([packet])
                self.assertEqual(result["owner_source_events"],[])
                self.assertEqual(sum(result["source_event_rejections"].values()),1)
        without_keys=bridge([trusted],keys=None)
        self.assertEqual(without_keys["owner_source_events"],[])
        self.assertFalse(without_keys["model_http_authorized"])
        self.assertFalse(without_keys["orders"])

    def test_exact_content_signature_prevents_cross_coin_or_event_mutations(self):
        packet=event("polymarket_h11",poly(),movement())
        tampered=[
            dict(packet,pair="ETH/EUR"),
            dict(packet,altname="ETHEUR"),
            dict(packet,market_move=dict(movement(),movement_phase="BREAKOUT_INITIATION")),
            dict(packet,snapshot=dict(packet["snapshot"],confirmed_net_buy_usd=123)),
        ]
        for change in tampered:
            with self.subTest(change=change):
                result=bridge([change])
                self.assertEqual(result["owner_source_events"],[])
        accepted=bridge([packet])
        self.assertEqual(len(accepted["owner_source_events"]),1)
        self.assertFalse(accepted["physical_source_key_provisioning_or_owner_live_event_proven"])

    def test_denied_owner_originals_are_individually_auditable_and_never_tradeable(self):
        import json,tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
            prepare_receipts,stage_receipts_explicitly,
        )
        good=event("news_sentiment",official())
        wrong=dict(good,snapshot=dict(good["snapshot"],
                                     raw_api_token="SECRET_SHOULD_NEVER_BE_PERSISTED"))
        forged=dict(good,owner_integrity={
            "authenticated_owner_id":"OFFICIAL_US_CURATOR",
            "authentication_checked_by_trusted_caller":True,
            "canonical_payload_sha256":fingerprint(good["snapshot"])
        })
        planning=preflight(owner_events=[wrong,forged])
        source=planning["source_provenance"]
        self.assertEqual(source["owner_source_events"],[])
        self.assertEqual(len(source["source_event_rejected_originals"]),2)
        self.assertEqual(planning["ingress"]["counts"]["selected"],0)
        self.assertEqual(planning["ingress"]["counts"]["suppressed_or_deferred"],2)
        self.assertEqual(len(planning["ingress"]["rejected_originals"]),2)
        self.assertEqual(len({a["audit_id"] for a in
                              planning["ingress"]["rejected_originals"]}),2)
        self.assertTrue(all(a["input_stream"]=="SOURCE_OWNER" for a in
                            planning["ingress"]["rejected_originals"]))
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)
            one=stage_receipts_explicitly(
                preflight=planning,journal_directory=journal)
            self.assertEqual(one["written"],2)
            self.assertEqual(one["originals_with_receipt"],0)
            self.assertEqual(one["owner_pre_router_rejection_audit_receipts"],2)
            self.assertEqual(one["router_rejection_audit_receipts"],2)
            self.assertFalse(one["cloud_ack_verified"])
            self.assertFalse(one["model_http_authorized"])
            rows=[json.loads(p.read_text("utf-8")) for p in journal.glob("*.json")]
            self.assertEqual(len(rows),2)
            self.assertTrue(all(x["phase"]=="SOURCE_INPUT" and
                                x["pair"]=="UNMAPPED/EUR" and
                                x["result"]=="UNKNOWN" and
                                x["event_key"]=="ROUTERREJECT" for x in rows))
            self.assertNotIn("SECRET_SHOULD_NEVER_BE_PERSISTED",
                             json.dumps(rows))
            again=stage_receipts_explicitly(
                preflight=planning,journal_directory=journal)
            self.assertEqual(again["identical_replays"],2)

    def test_complete_shared_v3_scanner_and_official_market_PIT_gate_but_no_spend(self):
        obs=xbt_real_pit_fixture()
        result=preflight(
            scanners=[scanner("ETH-original","ETH/EUR",dt(9))],
            owner_events=[event("news_sentiment",official())],
            observations=obs)
        self.assertEqual(result["ingress"]["counts"]["selected"],2)
        self.assertEqual(result["review_preflights"][0]["review_family"],
                         "SOURCE_CATALYST_INDEPENDENT")
        self.assertEqual(result["review_preflights"][0]["status"],
                         "INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY")
        self.assertTrue(result["review_preflights"][0]["eligible_for_full_model_review"])
        self.assertEqual(result["review_preflights"][1]["status"],
                         "UNKNOWN_NO_FRESH_COIN_KRAKEN_CONSUMER_INPUT")
        self.assertEqual(result["status"],
                         "REAL_PIT_REVIEW_ELIGIBLE_BUT_MODEL_SPEND_UNAUTHORIZED")
        self.assertEqual(result["model_calls"],0)
        self.assertFalse(result["model_http_authorized"])
        self.assertFalse(result["paper_buy_authorized"])
        self.assertFalse(result["cloud_active_series_changed"])
        self.assertFalse(result["v2r4_changed"])
        self.assertEqual(result["new_schedules"],0)

    def test_first_1m_enrollment_deadline_protects_original_clock_not_trade_claim(self):
        result=preflight(scanners=[
            scanner("late-scanner","ETH/EUR",dt(9)),
            scanner("early-scanner","ZRO/EUR",dt(3))])
        rows=result["prospective_first_1m_capture_enrollment"]
        self.assertEqual(len(rows),2)
        self.assertEqual([x["candidate_id"] for x in rows],
                         ["early-scanner","late-scanner"])
        self.assertTrue(all(x["ingress_disposition"]==
                            "SELECTED_FOR_MODEL_REVIEW" for x in rows))
        self.assertTrue(all(x["new_capture_window_still_open_as_of_preflight"]
                            for x in rows))
        self.assertFalse(any(x["first_bar_physically_witnessed_by_this_preflight"]
                             for x in rows))
        self.assertTrue(result["capture_enrollment_is_deadline_plan_not_live_proof"])
        self.assertEqual(result["model_calls"],0)
        self.assertFalse(result["paper_writer_active"])
        self.assertFalse(result["model_http_authorized"])
        from paper_evaluator.v3_paper_positive_source_entry_v1 import utc
        from datetime import timedelta
        for x in rows:
            original=utc(x["original_at_utc"])
            first=utc(x["first_expected_closed_1m_start_utc"])
            deadline=utc(x["latest_first_bar_live_witness_utc"])
            self.assertLessEqual(original,first)
            self.assertEqual(deadline,first+timedelta(minutes=16))
        # No re-prioritization of the actual V3 model decisions.
        self.assertEqual([x["candidate_id"] for x in result["selected_candidates"]],
                         ["early-scanner","late-scanner"])

    def test_capacity_deferral_source_witness_deadline_not_invisibly_lost(self):
        r=preflight(scanners=[
            scanner("sc-first","ETH/EUR",dt(8)),
            scanner("sc-deferred","XBT/EUR",dt(9))],
            limit=1)
        self.assertEqual(len(r["selected_candidates"]),1)
        self.assertEqual(len(r["ingress"]["capacity_deferred_originals"]),1)
        self.assertTrue(r["capacity_deferred_origins_need_durable_same_owner_retry"])
        byid={x["candidate_id"]:x for x in
              r["prospective_first_1m_capture_enrollment"]}
        self.assertEqual(set(byid),{"sc-first","sc-deferred"})
        self.assertEqual(byid["sc-deferred"]["ingress_disposition"],
                         "CAPACITY_DEFERRED_NEEDS_OWNER_RETRY")
        self.assertFalse(byid["sc-deferred"]
                         ["first_bar_physically_witnessed_by_this_preflight"])
        self.assertFalse(r["paper_writer_active"])
        self.assertFalse(r["model_http_authorized"])

    def test_capture_preflight_never_writes_source_provenance_or_a_buy(self):
        result=preflight(scanners=[scanner("sc-only","XBT/EUR",dt(9))],
                         observations=xbt_real_pit_fixture())
        self.assertEqual(len(result["prospective_first_1m_capture_enrollment"]),1)
        self.assertFalse(result["prospective_first_1m_capture_enrollment"][0]
                         ["first_bar_physically_witnessed_by_this_preflight"])
        self.assertFalse(result["cloud_active_series_changed"])
        self.assertFalse(result["paper_buy_authorized"])

    def test_unqualified_sources_must_not_block_scanner_and_low_volume_is_no_auto_veto(self):
        fake=dict(money(),not_self_dealing_checked=False)
        obs=xbt_real_pit_fixture()
        obs["XBT/EUR"]["entry_evidence"]["frames"]["5"]["volume_ratio_prior_5"]=0
        result=preflight(
            scanners=[scanner("sc-1","XBT/EUR",dt(9))],
            owner_events=[event("smart_money_h10",fake)],
            observations=obs)
        self.assertEqual(result["source_provenance"]["owner_source_events"],[])
        self.assertEqual(result["ingress"]["counts"]["selected"],1)
        self.assertEqual(result["review_preflights"][0]["review_family"],
                         "FIRST_SCANNER_EARLY_REVIEW")
        self.assertTrue(result["review_preflights"][0]["eligible_for_full_model_review"])
        self.assertFalse(result["model_http_authorized"])


    def test_first_minute_owner_handoff_is_durable_and_source_idempotent(self):
        """New glue uses actual existing capture/assembler; no paid model or Cloud."""
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
            stage_and_witness_first_minute,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
            capture_public_1m,
        )
        plan=preflight(scanners=[scanner("live-first","XBT/EUR",dt(9))])
        called=[]
        first=plan["prospective_first_1m_capture_enrollment"][0][
            "first_expected_closed_1m_start_utc"]
        minute=datetime.fromisoformat(first).timestamp()
        at=dt(130)
        def source(*,pair,altname,outdir):
            called.append(pair)
            def loader(_):
                return {"error":[],"result":{altname:[
                    [int(minute),"2.0","2.1","1.9","2.0","2.0","10",2],
                ],"last":1}}
            return capture_public_1m(
                pair=pair,altname=altname,outdir=outdir,
                loader=loader,
                clock=lambda:datetime.fromisoformat(at))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); journal=root/"journal"; capture=root/"capture"
            journal.mkdir();capture.mkdir()
            out=stage_and_witness_first_minute(
                preflight=plan,journal_directory=journal,
                capture_directory=capture,observed_at_utc=at,capture=source)
            self.assertEqual(out["source_capture_calls"],1)
            self.assertEqual(called,["XBT/EUR"])
            self.assertEqual(out["staged"]["written"],2)
            self.assertEqual(out["enrollment"][0]["status"],
                             "FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY")
            self.assertFalse(out["paper_writer_active"])
            self.assertFalse(out["source_owner_runtime_authenticated"])
            self.assertEqual(out["model_http_calls"],0)
            again=stage_and_witness_first_minute(
                preflight=plan,journal_directory=journal,
                capture_directory=capture,observed_at_utc=at,
                capture=lambda **kw: self.fail("duplicate public Kraken GET"))
            self.assertEqual(again["source_capture_calls"],0)
            self.assertEqual(again["staged"]["identical_replays"],2)
            self.assertEqual(again["enrollment"][0]["status"],
                             "FIRST_MINUTE_ALREADY_ARCHIVED_NO_DUPLICATE_GET")
            self.assertEqual(len(list(capture.glob("*.json"))),1)

    def test_first_minute_wait_expired_and_source_auth_never_poll(self):
        import tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
            stage_and_witness_first_minute,
        )
        from tests.test_v3_paper_positive_source_entry_v1 import official
        source_plan=preflight(owner_events=[event("news_sentiment",official())])
        for plan,at,expected in (
            (preflight(scanners=[scanner("early","XBT/EUR",dt(9))]),
             dt(12),"WAIT_FOR_FIRST_CLOSED_MINUTE_NO_CAPTURE"),
            (preflight(scanners=[scanner("expired","XBT/EUR",dt(9))]),
             dt(1400),"FIRST_WITNESS_WINDOW_EXPIRED_NO_BACKFILL"),
            (source_plan,dt(130),"SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN_NO_CAPTURE"),
        ):
            with self.subTest(expected=expected),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); journal=root/"journal";capture=root/"capture"
                journal.mkdir();capture.mkdir()
                result=stage_and_witness_first_minute(
                    preflight=plan,journal_directory=journal,
                    capture_directory=capture,observed_at_utc=at,
                    capture=lambda **kw: self.fail("unpermitted source call"))
                self.assertEqual(result["source_capture_calls"],0)
                self.assertEqual(result["enrollment"][0]["status"],expected)
                self.assertFalse(result["model_http_authorized"])
                self.assertFalse(result["cloud_ack_verified"])

    def test_missing_or_tampered_enrollment_rejected_before_journal_write(self):
        import tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
            stage_and_witness_first_minute,
        )
        plan=preflight(scanners=[scanner("identity","XBT/EUR",dt(9))])
        for mutate in ("no_callback","incomplete","wrong_clock"):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); j=root/"journal"; cap=root/"capture"
                j.mkdir();cap.mkdir()
                forged=copy.deepcopy(plan)
                cb=lambda **kw:self.fail("unapproved source capture")
                if mutate=="no_callback":
                    cb=None
                elif mutate=="incomplete":
                    forged["prospective_first_1m_capture_enrollment"]=[]
                else:
                    forged["prospective_first_1m_capture_enrollment"][0][
                        "latest_first_bar_live_witness_utc"]=dt(999)
                with self.assertRaises(ValueError):
                    stage_and_witness_first_minute(
                        preflight=forged,journal_directory=j,
                        capture_directory=cap,observed_at_utc=dt(130),
                        capture=cb)
                self.assertEqual(len(list(j.glob("*.json"))),0)


    def test_real_network_elapsed_time_uses_original_capture_clock_not_start_clock(self):
        """No false negative for a real GET that returns seconds later."""
        import tempfile
        from datetime import datetime
        from pathlib import Path
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
            stage_and_witness_first_minute,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import (
            capture_public_1m,
        )
        plan=preflight(scanners=[scanner("elapsed","XBT/EUR",dt(9))])
        first=plan["prospective_first_1m_capture_enrollment"][0][
            "first_expected_closed_1m_start_utc"]
        minute=int(datetime.fromisoformat(first).timestamp())
        for started,ended,expected in (
            (dt(130),dt(135),"FIRST_CLOSED_MINUTE_WITNESSED_RESEARCH_ONLY"),
            (dt(1000),dt(1040),"FIRST_WITNESS_EXPIRED_DURING_FETCH_NO_LIVE_PROOF"),
        ):
            with self.subTest(started=started),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); j=root/"j"; cap=root/"cap"
                j.mkdir();cap.mkdir()
                ticks=iter((datetime.fromisoformat(started),
                            datetime.fromisoformat(ended)))
                def source(*,pair,altname,outdir):
                    def loader(_):
                        return {"error":[],"result":{altname:[
                            [minute,"2.0","2.1","1.9","2.0","2.0","10",2],
                        ],"last":1}}
                    return capture_public_1m(
                        pair=pair,altname=altname,outdir=outdir,
                        loader=loader,clock=lambda:next(ticks))
                r=stage_and_witness_first_minute(
                    preflight=plan,journal_directory=j,
                    capture_directory=cap,observed_at_utc=started,
                    capture=source)
                self.assertEqual(r["source_capture_calls"],1)
                self.assertEqual(r["enrollment"][0]["status"],expected)
                self.assertEqual(r["enrollment"][0]["prospective_first_bar_verified"],
                                 started==dt(130))
                self.assertFalse(r["paper_writer_active"])
                self.assertFalse(r["cloud_ack_verified"])


    def test_canary_single_owner_first_source_to_model_p4_tick_cloud(self):
        """Existing real components linked without a second Kraken GET or paid model."""
        import tempfile,json
        from pathlib import Path
        from datetime import datetime
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            first_enrolled_canary_tick_once,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m
        from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import sync_once
        from tests.test_v3_paper_minipc_one_candidate_v1 import (
            valid_approval,fake_acquire,fake_model,
        )
        candidate=scanner("V3-INITIAL-EUR-1","XBT/EUR",dt(9))
        plan=preflight(scanners=[candidate],observations=xbt_real_pit_fixture())
        moment=dt(130)
        first=plan["prospective_first_1m_capture_enrollment"][0][
            "first_expected_closed_1m_start_utc"]
        calls=[]
        def source(*,pair,altname,outdir):
            calls.append(pair)
            def loader(_):
                return {"error":[],"result":{altname:[
                    [int(datetime.fromisoformat(first).timestamp()),
                     "2.0","2.1","1.9","2.0","2.0","10",2]
                ],"last":1}}
            return capture_public_1m(pair=pair,altname=altname,
                outdir=outdir,loader=loader,
                clock=lambda:datetime.fromisoformat(moment))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"journal";cap=root/"cap";budget=root/"budgets"
            for d in (j,cap,budget):d.mkdir()
            self.assertEqual(stage_receipts_explicitly(
                preflight=plan,journal_directory=j)["written"],2)
            m=one_candidate(candidate=plan["selected_candidates"][0],
                series_id=SID,local_receipts=j,model_reservations=budget,
                approval=dict(valid_approval(),series_id=SID),
                model_key="NON_REAL_TEST_KEY_SUPPLIED_TO_STUB",
                acquire=fake_acquire,model_client=fake_model,
                clock=lambda:dt(12),allow_model=True,
                admit_staged_scanner_one_approved_model=True)
            self.assertEqual(m["p4_decision"],"BUY_SCOUT")
            one=first_enrolled_canary_tick_once(
                preflight=plan,candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,capture_dir=cap,
                clock_now=lambda:moment,capture=source,
                fetch=lambda *_: self.fail("BUY is not WAIT source"),
                ticker=lambda *_:self.fail("no new ticker for BUY"))
            self.assertEqual(one["source_capture_calls"],1)
            self.assertEqual(one["observation"]["source_closed_1m_count"],1)
            self.assertEqual(calls,["XBT/EUR"])
            self.assertTrue(one["tick_called"])
            self.assertEqual(one["model_http_calls"],0)
            ack=root/"ack.json"
            pushed=[]
            def post(url,token,payload):
                pushed.append(payload)
                return {"ok":True,"series_id":SID,
                        "accepted_receipts":len(payload["receipts"])}
            a=sync_once(journal=j,series_id=SID,ack_file=ack,
                token="SYNTHETIC_TEST_ONLY_V3_RELAY_TOKEN_NO_NETWORK",post=post)
            self.assertEqual(a["status"],"V3_RECEIPTS_CLOUD_ACK_VERIFIED")
            another=first_enrolled_canary_tick_once(
                preflight=plan,candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,capture_dir=cap,
                clock_now=lambda:moment,
                capture=lambda **kw:self.fail("duplicate Kraken GET"),
                fetch=lambda *_:self.fail("no 2nd refresh"),
                ticker=lambda *_:self.fail("no 2nd ticker"))
            self.assertEqual(another["source_capture_calls"],0)
            self.assertTrue(another["tick_called"])
            self.assertEqual(sync_once(journal=j,series_id=SID,ack_file=ack,
                token="SYNTHETIC_TEST_ONLY_V3_RELAY_TOKEN_NO_NETWORK",
                post=lambda *_:self.fail("duplicate Cloud POST"))["count"],0)
            self.assertEqual(len(pushed),1)
            self.assertEqual(len(list(budget.glob("*.reserved.json"))),1)
            self.assertFalse(one["paper_writer_active"])

    def test_first_source_owner_tick_never_activates_actual_paper_or_stale(self):
        import tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            first_enrolled_canary_tick_once,
        )
        plan=preflight(scanners=[scanner("ineligible","XBT/EUR",dt(9))])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";cap=root/"cap";j.mkdir();cap.mkdir()
            def fail(*args,**kwargs):
                self.fail("unapproved Kraken request")
            with self.assertRaises(ValueError):
                first_enrolled_canary_tick_once(
                    preflight=plan,candidate=plan["selected_candidates"][0],
                    series_id="PAPER-V3-LIVE-UNRELEASED",journal=j,capture_dir=cap,
                    clock_now=lambda:dt(130),capture=fail)
            self.assertEqual(len(list(j.glob("*.json"))),0)
            waiting=first_enrolled_canary_tick_once(
                preflight=plan,candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,capture_dir=cap,
                clock_now=lambda:dt(12),capture=fail)
            self.assertEqual(waiting["source_capture_calls"],0)
            self.assertFalse(waiting["tick_called"])
            self.assertFalse(waiting["paper_writer_active"])


    def test_canary_restart_uncertain_reserved_model_is_quarantined(self):
        import tempfile
        from pathlib import Path
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            plan_canary_resume,resume_canary_tick_once,
        )
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
        from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
        original=scanner("restart-ambiguous","XBT/EUR",dt(9))
        plan=preflight(scanners=[original])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"journal";budget=root/"budgets";cap=root/"capture"
            for d in (j,budget,cap):d.mkdir()
            stage_receipts_explicitly(preflight=plan,journal_directory=j)
            initial=plan_canary_resume(candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,model_reservations=budget,
                ack_file=root/"cloud-ack.json")
            self.assertEqual(initial["status"],
                             "MODEL_NOT_FINAL_NO_AUTOMATIC_SPEND_OR_FOLLOWUP")
            req=make_receipt(series_id=SID,revision=REVISION,
                candidate_id=original["candidate_id"],pair=original["pair"],
                event_time_utc=original["event_time_utc"],known_at_utc=dt(12),
                phase="MODEL_REQUEST",result="PASS",event_key="FRESHRECHECK",
                data={"model_http_attempts_reserved":1})
            store_receipt_explicitly(j,req)
            guard=plan_canary_resume(candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,model_reservations=budget,
                ack_file=root/"cloud-ack.json")
            self.assertEqual(guard["status"],"MODEL_MAY_HAVE_SPENT_NO_RETRY_QUARANTINE")
            self.assertFalse(guard["can_tick"])
            out=resume_canary_tick_once(candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,capture_dir=cap,model_reservations=budget,
                ack_file=root/"cloud-ack.json",
                capture=lambda **kw:self.fail("no source on uncertain HTTP"),
                fetch=lambda *_:self.fail("no Kraken recheck"),
                ticker=lambda *_:self.fail("no ticker"))
            self.assertFalse(out["tick_called"])
            self.assertEqual(out["source_capture_calls"],0)
            self.assertEqual(out["model_http_calls"],0)
            self.assertEqual(len(list(cap.glob("*.json"))),0)

    def test_canary_recovery_wait_from_immutable_complete_model_single_owner(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            plan_canary_resume,resume_canary_tick_once,
        )
        from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import capture_public_1m
        from paper_evaluator.v3_paper_intake_receipt_stage_v1 import stage_receipts_explicitly
        from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt,store_receipt_explicitly
        from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION
        original=scanner("restart-wait","XBT/EUR",dt(9))
        plan=preflight(scanners=[original])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=root/"j";budget=root/"b";cap=root/"c"
            for d in (j,budget,cap):d.mkdir()
            stage_receipts_explicitly(preflight=plan,journal_directory=j)
            budget.joinpath("known.reserved.json").write_text(__import__("json").dumps({
                "kind":"V3_PAPER_MODEL_HTTP_RESERVED_BEFORE_NETWORK_V1",
                "series_id":SID,"candidate_id":original["candidate_id"],
                "no_automatic_retry":True}),encoding="utf-8")
            for phase,result,data in (
                ("MODEL_REQUEST","PASS",{"model_http_attempts_reserved":1}),
                ("MODEL_RESPONSE","PASS",{"raw_model_decision":"WAIT",
                                          "model_response_at_utc":dt(12)}),
                ("P4_VALIDATION","WAIT",{"p4_decision":"WAIT","p4_status":"FULL_WAIT_VALIDATED_OFFLINE"}),
                ("WAIT_WATCH","WAIT",{"raw_wait_ttl_minutes":1,
                                     "raw_watch_conditions":[
                                         {"metric":"ask_eur","op":">=","value":1.0}]}),
            ):
                event=make_receipt(series_id=SID,revision=REVISION,
                    candidate_id=original["candidate_id"],pair=original["pair"],
                    event_time_utc=original["event_time_utc"],known_at_utc=dt(12),
                    phase=phase,result=result,event_key="FRESHRECHECK",data=data)
                store_receipt_explicitly(j,event)
            safe=plan_canary_resume(candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,model_reservations=budget,
                ack_file=root/"ack.json")
            self.assertTrue(safe["can_tick"])
            captured=[]
            def original_source(*,pair,altname,outdir):
                captured.append(pair)
                # The outer OS owner lock is held during this callback.
                # A second attempted invocation must fail BEFORE its
                # duplicate public source callback can be reached.
                with self.assertRaisesRegex(
                        ValueError,"ANOTHER_CANARY_OWNER_RUNNING_FAIL_CLOSED"):
                    resume_canary_tick_once(
                        candidate=plan["selected_candidates"][0],
                        series_id=SID,journal=j,capture_dir=cap,
                        model_reservations=budget,ack_file=root/"ack.json",
                        clock_now=lambda:dt(150),
                        capture=lambda **kw:self.fail("concurrent source GET"),
                        fetch=lambda *_:self.fail("concurrent source refresh"),
                        ticker=lambda *_:self.fail("concurrent ticker"))
                at=datetime.fromisoformat(dt(150))
                moment=int(at.replace(second=0,microsecond=0).timestamp())-60
                def load(_):
                    return {"error":[],"result":{altname:[
                        [moment,"2.0","2.1","1.9","2.0","2.0","10",2]],"last":1}}
                return capture_public_1m(pair=pair,altname=altname,
                    outdir=outdir,loader=load,clock=lambda:at)
            result=resume_canary_tick_once(
                candidate=plan["selected_candidates"][0],
                series_id=SID,journal=j,capture_dir=cap,
                model_reservations=budget,ack_file=root/"ack.json",
                clock_now=lambda:dt(150),capture=original_source,
                fetch=lambda *_:self.fail("expired WAIT needs no Kraken extra"),
                ticker=lambda *_:self.fail("no real ticker"))
            self.assertTrue(result["tick_called"])
            self.assertEqual(captured,["XBT/EUR"])
            self.assertEqual(result["model_http_calls"],0)
            self.assertFalse(result["cloud_ack_verified"])
            self.assertFalse(result["paper_writer_active"])
            self.assertTrue(any("lock" in x.name for x in j.iterdir()))

if __name__=="__main__":unittest.main()
