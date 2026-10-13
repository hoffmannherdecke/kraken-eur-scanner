"""V3 ingress joins original V2R4 scanners + verified positive H5/H10/H11, no model."""
import unittest
from paper_evaluator.v3_paper_shared_candidate_intake_plan_v1 import (
    KIND,plan_intake,
)
from tests.test_v3_paper_positive_source_entry_v1 import (
    official,money,poly,movement,
)
from tests.test_v2r4_v3_entry_handoff_probe import dt
from paper_evaluator.v3_experimental_paper_journal_v1 import make_receipt
from paper_evaluator.v3_paper_cloud_receipt_sync_v1 import REVISION

SID="PAPER-V3-CANARY-20261011"
PAIR={"XBT/EUR":{"pair":"XBT/EUR","altname":"XBTEUR","quote":"EUR","status":"online","spot":True},
      "ETH/EUR":{"pair":"ETH/EUR","altname":"ETHEUR","quote":"EUR","status":"online","spot":True},
      "ZRO/EUR":{"pair":"ZRO/EUR","altname":"ZROEUR","quote":"EUR","status":"online","spot":True}}
def scanner(cid="scanner01",pair="ETH/EUR",event=dt(9),**extra):
    return {"kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
            "candidate_id":cid,"pair":pair,
            "altname":PAIR[pair]["altname"],
            "event_time_utc":event,
            "action":"REVIEW_ONLY_NOT_ORDER",**extra}
def origin(name,snapshot,market_move=None):
    return {"source_name":name,"pair":"XBT/EUR","altname":"XBTEUR",
            "snapshot":snapshot,"market_move":market_move}
def plan(scanners=None,sources=None,journal=None,as_of=dt(12),limit=3,known=PAIR):
    return plan_intake(scanner_events=[] if scanners is None else scanners,
                       source_events=[] if sources is None else sources,
                       journal_receipts=[] if journal is None else journal,
                       known_pairs=known,series_id=SID,decision_at_utc=as_of,
                       max_reviews=limit)
class V3SharedIngressTests(unittest.TestCase):
    def test_scanner_plus_independent_verified_official_buy_review_not_order(self):
        r=plan([scanner()], [origin("news_sentiment",official())])
        self.assertEqual(r["kind"],KIND)
        self.assertEqual(r["counts"]["selected"],2)
        self.assertEqual(r["candidates"][0]["entry_origin"],"VERIFIED_POSITIVE_SOURCE_CATALYST")
        self.assertEqual(r["candidates"][0]["event_time_utc"],dt(5))
        self.assertEqual(r["candidates"][1]["entry_origin"],"SCANNER")
        self.assertEqual(r["candidates"][1]["event_time_utc"],dt(9))
        self.assertFalse(r["model_http_authorized"])
        self.assertFalse(r["paper_writer_active"])
        self.assertEqual(r["model_calls"],0)
        self.assertFalse(r["orders"])
        self.assertTrue(r["v2r4_unchanged"])
        self.assertTrue(r["requires_full_v3_model_and_p4"])

    def test_source_types_eligible_separately_but_no_weak_h10_or_weak_poly(self):
        for ev in (origin("smart_money_h10",money()),
                   origin("polymarket_h11",poly(),movement())):
            with self.subTest(origin=ev["source_name"]):
                r=plan(sources=[ev])
                self.assertEqual(r["counts"]["selected"],1)
                self.assertEqual(r["candidates"][0]["positive_source_name"],ev["source_name"])
                self.assertFalse(r["model_http_authorized"])
        weak=dict(money(),independent_wallet_count=1,
                  not_self_dealing_checked=False)
        weak_poly=dict(poly(),observed_probability_delta=0.02)
        r=plan([scanner()],[
            origin("smart_money_h10",weak),
            origin("polymarket_h11",weak_poly,movement())])
        self.assertEqual(r["counts"]["selected"],1)
        self.assertEqual(r["candidates"][0]["entry_origin"],"SCANNER")
        self.assertEqual(r["dispositions"]["SOURCE_CATALYST_NOT_INDEPENDENTLY_VERIFIED"],2)

    def test_original_dedupe_while_paper_series_stays_unmodified(self):
        first=plan([scanner()])
        c=first["candidates"][0]
        receipt={"kind":"V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1",
                 "series_id":SID,"candidate_id":c["candidate_id"],
                 "pair":c["pair"],"event_time_utc":c["event_time_utc"],
                 "phase":"SCANNER_CAPTURE"}
        r=plan([scanner(),scanner(cid="new-scanner"),
                 scanner(cid="new-scanner")],journal=[receipt])
        self.assertEqual(r["counts"]["selected"],1)
        self.assertEqual(r["dispositions"]["ALREADY_JOURNALED_NO_REPEAT_NO_SPEND"],1)
        self.assertEqual(r["dispositions"]["EXACT_CANDIDATE_DUPLICATE_IN_INPUT"],1)
        with self.assertRaises(ValueError):
            plan([scanner()],journal=[dict(receipt,pair="ETH/EUR"),
                dict(receipt,pair="XBT/EUR")])

    def test_only_fresh_exact_capacity_deferred_scanner_can_reenter(self):
        old=make_receipt(
            series_id=SID,revision=REVISION,candidate_id="deferred-one",
            pair="ETH/EUR",event_time_utc=dt(9),known_at_utc=dt(12),
            phase="SCANNER_CAPTURE",result="SKIP",
            data={"candidate_origin":"SCANNER",
                  "source_status":"CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION"},
            event_key="FIRST")
        r=plan([scanner("deferred-one","ETH/EUR",dt(9))],journal=[old])
        self.assertEqual(r["counts"]["selected"],1)
        self.assertTrue(r["candidates"][0]["deferred_recheck"])
        self.assertFalse(r["model_http_authorized"])
        duplicate=make_receipt(
            series_id=SID,revision=REVISION,candidate_id="deferred-one",
            pair="ETH/EUR",event_time_utc=dt(9),known_at_utc=dt(12),
            phase="SCANNER_CAPTURE",result="SEEN",
            data={"candidate_origin":"SCANNER",
                  "source_status":"ORIGINAL_SELECTED_FOR_PRE_MODEL_REVIEW_ONLY"},
            event_key="DEFERREDRECHECK")
        blocked=plan([scanner("deferred-one","ETH/EUR",dt(9))],
                     journal=[old,duplicate])
        self.assertEqual(blocked["counts"]["selected"],0)
        self.assertIn("ALREADY_JOURNALED_NO_REPEAT_NO_SPEND",
                      blocked["dispositions"])
        bad=make_receipt(
            series_id=SID,revision=REVISION,candidate_id="not-capacity",
            pair="ETH/EUR",event_time_utc=dt(9),known_at_utc=dt(12),
            phase="SCANNER_CAPTURE",result="SKIP",
            data={"candidate_origin":"SCANNER",
                  "source_status":"SOURCE_REJECTED"},
            event_key="FIRST")
        invalid=plan([scanner("not-capacity","ETH/EUR",dt(9))],journal=[bad])
        self.assertEqual(invalid["counts"]["selected"],0)
        self.assertFalse(invalid["model_http_authorized"])

    def test_stale_future_wrong_quote_hardblock_and_no_technical_vol_veto(self):
        old=scanner(cid="old",event=dt(-650))
        future=scanner(cid="future",event=dt(50))
        wrong=scanner(cid="wrong",pair="ZRO/EUR")
        pairs=dict(PAIR,**{"ZRO/EUR":dict(PAIR["ZRO/EUR"],status="offline")})
        bad_action=scanner(cid="act",action="ORDER")
        r=plan([old,future,wrong,bad_action,
                scanner(cid="clean",pair="ETH/EUR",
                        scanner_candidate={"volume_ratio_prior_5":0.0})],
               known=pairs)
        self.assertEqual(r["counts"]["selected"],1)
        self.assertEqual(r["candidates"][0]["candidate_id"],"clean")
        self.assertIn("EXPIRED_ORIGINAL_10M_WINDOW",r["dispositions"])
        self.assertIn("FUTURE_EVENT_NOT_YET_KNOWN",r["dispositions"])
        self.assertIn("SCANNER_EVENT_NOT_AUTHORIZED_REVIEW_ONLY",r["dispositions"])
        self.assertIn("PAIR_NOT_VERIFIED_AS_SPOT_EUR_METADATA_RECHECK_REQUIRED",r["dispositions"])

    def test_bounded_limit_discloses_backlog_no_invisible_drop(self):
        names=("ETH","XBT","ZRO","AVAX","FET")
        mappings=dict(PAIR)
        for name in names:
            pair=name+"/EUR"
            mappings[pair]={"pair":pair,"altname":name+"EUR",
                            "quote":"EUR","status":"online","spot":True}
        xs=[{"kind":"CANONICAL_CANDIDATE_HANDOFF_V1","candidate_id":"N"+str(i),
             "pair":name+"/EUR","altname":name+"EUR",
             "event_time_utc":dt(3+i),"action":"REVIEW_ONLY_NOT_ORDER"}
            for i,name in enumerate(names)]
        r=plan(scanners=xs,limit=1,known=mappings)
        self.assertEqual(r["counts"]["selected"],1)
        self.assertEqual(r["dispositions"]["CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION"],4)
        self.assertEqual(len(r["capacity_deferred_originals"]),4)
        self.assertEqual({c["candidate_id"] for c in r["capacity_deferred_originals"]},
                         {"N1","N2","N3","N4"})
        self.assertTrue(r["overflow_requires_durable_owner_queue_before_runtime"])
        self.assertTrue(r["all_rejected_and_deferred_originals_not_yet_journaled"])
        self.assertFalse(r["model_http_authorized"])

    def test_same_coin_nearby_source_dominates_scanner_but_later_independent_is_not_silenced(self):
        scan=scanner(cid="x",pair="XBT/EUR",event=dt(7))
        near=plan([scan], [origin("news_sentiment",official())])
        self.assertEqual(near["counts"]["selected"],1)
        self.assertEqual(near["candidates"][0]["entry_origin"],"VERIFIED_POSITIVE_SOURCE_CATALYST")
        self.assertEqual(near["dispositions"]["SAME_PAIR_CONCURRENT_REVIEW_COALESCED_NOT_LOST"],1)
        self.assertEqual(len(near["same_pair_coalesced_originals"]),1)
        self.assertEqual(near["same_pair_coalesced_originals"][0]["candidate_id"],"x")
        self.assertEqual(near["same_pair_coalesced_originals"][0]["event_time_utc"],dt(7))
        later=plan([scanner(cid="x",pair="XBT/EUR",event=dt(480))],
                   [origin("news_sentiment",official())],as_of=dt(500))
        self.assertEqual(later["counts"]["selected"],2)

    def test_every_router_rejection_has_bounded_original_audit_without_secrets(self):
        bad_action=scanner(cid="invalid-approval",action="ORDER")
        old=scanner(cid="old1",event=dt(-650))
        future=scanner(cid="future1",event=dt(99))
        invalid=scanner(cid="messed-up",event="not-a-clock")
        raw_secret={"kind":"BAD","candidate_id":"TOKEN SECRET DO NOT COPY",
                    "pair":"BAD","auth_secret":"never-echo"}
        r=plan(scanners=[bad_action,old,future,invalid,raw_secret],
               sources=[origin("smart_money_h10",
                               dict(money(),onchain_fills_confirmed=False))])
        self.assertEqual(len(r["rejected_originals"]),6)
        self.assertEqual(r["counts"]["selected"],0)
        self.assertEqual(
            {x["reason"] for x in r["rejected_originals"]},
            {"SCANNER_EVENT_NOT_AUTHORIZED_REVIEW_ONLY",
             "EXPIRED_ORIGINAL_10M_WINDOW","FUTURE_EVENT_NOT_YET_KNOWN",
             "UNKNOWN_ORIGINAL_EVENT_CLOCK",
             "SOURCE_CATALYST_NOT_INDEPENDENTLY_VERIFIED"})
        self.assertEqual(r["rejected_originals"][0]["input_index"],0)
        self.assertEqual(r["rejected_originals"][1]["original_candidate_id_if_safe"],"old1")
        self.assertEqual(r["rejected_originals"][2]["original_event_time_if_parseable"],dt(99).replace("Z","+00:00"))
        from json import dumps
        serialized=dumps(r["rejected_originals"])
        self.assertNotIn("never-echo",serialized)
        self.assertNotIn("TOKEN SECRET",serialized)
        self.assertNotIn("confirmed_net_buy_usd",serialized)
        self.assertTrue(all(x["original_untrusted_and_not_tradeable"]
                            for x in r["rejected_originals"]))
        self.assertFalse(r["model_http_authorized"])

    def test_rejection_audit_original_ids_replay_deterministic_no_buy(self):
        invalid=scanner(cid="wrong-action",action="ORDER")
        a=plan(scanners=[invalid])
        b=plan(scanners=[invalid])
        self.assertEqual(a["rejected_originals"],b["rejected_originals"])
        self.assertEqual(len({x["audit_id"] for x in a["rejected_originals"]}),1)
        self.assertFalse(a["orders"])
        self.assertTrue(a["all_rejected_and_deferred_originals_not_yet_journaled"])

    def test_no_past_approval_and_forged_payload_cannot_buy(self):
        fake=dict(official(),official_primary_url="https://www.treasury.gov.evil.example/a")
        r=plan(sources=[origin("news_sentiment",fake)])
        self.assertEqual(r["counts"]["selected"],0)
        self.assertEqual(r["status"],"NO_FRESH_UNJOURNALED_INPUT")
        self.assertFalse(r["model_http_authorized"])
        self.assertFalse(r["orders"])
        with self.assertRaises(ValueError):
            plan(scanners=[],journal=[{"kind":"UNVERIFIED","series_id":SID}])
        with self.assertRaises(ValueError):
            plan(scanners=[],limit=8)

if __name__=="__main__":unittest.main()
