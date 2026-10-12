"""Exact existing H10/H11/H5 research → verified source → V3 future writer seam."""
from __future__ import annotations
import copy,unittest
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
    return {"source_name":name,"pair":"XBT/EUR",
            "altname":"XBTEUR","snapshot":snapshot,
            "market_move":move,
            "owner_integrity":{
                "authenticated_owner_id":snapshot["source_owner"],
                "authentication_checked_by_trusted_caller":True,
                "canonical_payload_sha256":fingerprint(snapshot),
            }}
def bridge(events=(),h10=H10,h11=H11,h5=H5,owners=OWNER):
    return join_owner_sources(
        h10_context=h10,h11_market_capture=h11,
        h5_macro_calendar=h5,owner_event_packets=list(events),
        authenticated_owner_ids=owners,decision_at_utc=dt(12))
def preflight(scanners=(),owner_events=(),observations=None):
    return plan_writer_preflight(
        scanner_events=list(scanners),owner_event_packets=list(owner_events),
        h10_context=H10,h11_market_capture=H11,h5_macro_calendar=H5,
        authenticated_owner_ids=OWNER,journal_receipts=[],known_pairs=PAIR,
        market_observations=observations if observations is not None else {},
        series_id=SID,decision_at_utc=dt(12))
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
