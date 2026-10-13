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

if __name__=="__main__":unittest.main()
