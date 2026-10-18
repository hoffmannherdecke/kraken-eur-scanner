"""Independent source-catalyst entry is REAL V3 Paper policy, not only a note."""
import copy,json,tempfile,unittest
from pathlib import Path
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    ELIGIBLE,assess_positive_source,make_source_candidate,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import one_candidate
from paper_evaluator.v3_experimental_paper_initial_review_v1 import propose_initial_full_review
from paper_evaluator.v3_experimental_paper_model_prompt_v1 import build_v3_paper_full_model_prompt
from paper_evaluator.v3_full_entry_decision_candidate_v1 import validate_full_entry_decision
from tests.test_v3_experimental_paper_initial_review_v1 import fixture
from tests.test_v3_paper_minipc_one_candidate_v1 import fake_model, SID
from tests.test_v2r4_v3_entry_handoff_probe import dt


def official():
    return {
        "pair":"XBT/EUR","source_owner":"OFFICIAL_US_CURATOR",
        "source_id":"federal/2026/001","event_id":"statement-001",
        "source_verified":True,"coin_relevance_verified":True,
        "observed_at_utc":dt(3),"known_at_utc":dt(5),
        "impact_mechanism":"Direct, confirmed economic benefit to this exact asset",
        "sentiment":"POSITIVE","news_category":"DIRECT_REGULATORY_BENEFIT",
        "official_confirmation":True,"direct_pair_beneficiary":True,
        "official_primary_url":"https://www.treasury.gov/example-fictional-test",
    }

def money():
    return {
        "pair":"XBT/EUR","source_owner":"H10_CAPTURE_OWNER",
        "source_id":"h10/wallets/source-1","event_id":"wallets-001",
        "source_verified":True,"coin_relevance_verified":True,
        "observed_at_utc":dt(3),"known_at_utc":dt(5),
        "impact_mechanism":"Three independent actual net buyers in the same coin",
        "consensus_direction":"NET_BUY","independent_wallet_count":3,
        "confirmed_net_buy_usd":30000,
        "onchain_fills_confirmed":True,"not_self_dealing_checked":True,
    }

def poly():
    return {
        "pair":"XBT/EUR","source_owner":"H11_CAPTURE_OWNER",
        "source_id":"h11/market-42","event_id":"market-42-shift",
        "source_verified":True,"coin_relevance_verified":True,
        "observed_at_utc":dt(3),"known_at_utc":dt(5),
        "impact_mechanism":"Directly positive coin event with improving binary odds",
        "market_id":"market-42","question":"Example XBT-specific economic event",
        "yes_midpoint":.74,"observed_probability_delta":.15,
        "market_liquidity_usd":30000,"market_resolved":False,
        "direct_positive_outcome_for_pair":True,
    }

def movement():
    return {"pair":"XBT/EUR","source_verified":True,"known_at_utc":dt(6),
            "observed_at_utc":dt(4),"movement_phase":"EARLY_ACCELERATION",
            "velocity_band":"POSITIVE","source_owner":"MINIPC_SCANNER"}

def create(name,raw,other=None):
    return make_source_candidate(
        pair="XBT/EUR",kraken_altname="XBTEUR",source_name=name,
        snapshot=raw,decision_at_utc=dt(12),market_move=other)

def prompt(candidate,context):
    c,e,t,m=fixture()
    e["frames"]["5"]["volume_ratio_prior_5"]=.20
    ready=propose_initial_full_review(candidate,e,t,m,decision_at_utc=dt(12))
    assert ready["request_model_recheck_only"]
    out=build_v3_paper_full_model_prompt(
        candidate=candidate,eligibility=ready,entry_evidence=e,
        ticker=t,pair_metadata=m,decision_at_utc=dt(12),
        optional_context={
            "kind":"V3_PAPER_EXISTING_RESEARCH_CONTEXT_BRIDGE_V1",
            "raw_snapshots":context,
        })
    return out,ready,(e,t,m)


class SourceDrivenV3PaperTests(unittest.TestCase):
    def test_official_source_creates_model_candidate_without_scanner_or_technical_volume(self):
        c=create("news_sentiment",official())
        self.assertEqual(c["entry_origin"],"VERIFIED_POSITIVE_SOURCE_CATALYST")
        self.assertEqual(c["event_time_utc"],dt(5))
        self.assertNotIn("scanner_score",c)
        text,review,(e,t,m)=prompt(c,{"news_sentiment":official()})
        self.assertIn("positive_source_trigger_for_independent_paper_entry",text)
        self.assertIn("DIRECT_VERIFIED_OFFICIAL_POSITIVE_EVENT",text)
        self.assertIn("INDEPENDENT SOURCE-CATALYST ENTRY PATH",text)
        self.assertIn('"source_5m_volume_ratio":0.2',text)
        self.assertEqual(review["status"],"INITIAL_FRESH_PIT_READY_FOR_FULL_V3_MODEL_ONLY")
        from tests.test_v3_full_entry_decision_candidate_v1 import fixture as p4_fixture
        model=p4_fixture()[-1]
        model.update(setup_lane="IGNITION",candidate_id=c["candidate_id"],
                     decision_at_utc=dt(12))
        result=validate_full_entry_decision(
            review,c,e,t,m,model,decision_at_utc=dt(12),
            slippage_pct_each_side=.08)
        self.assertEqual(result["decision"],"BUY_SCOUT")
        self.assertFalse(result["orders"])
        self.assertGreater(result["total_round_trip_cost_pct"],1.2)

    def test_real_minipc_one_candidate_actually_routes_source_entry_to_p4_and_journal(self):
        c=create("news_sentiment",official())
        f=fixture()
        e=f[1];e["frames"]["5"]["volume_ratio_prior_5"]=.20
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);j=d/"journal";b=d/"budgets";j.mkdir();b.mkdir()
            r=one_candidate(candidate=c,series_id=SID,local_receipts=j,
                model_reservations=b,existing_context={"news_sentiment":official()},
                acquire=lambda unused:(e,f[2],f[3]),clock=lambda:dt(12))
            self.assertEqual(r["status"],"V3_PAPER_REAL_KRAKEN_PIT_PREFLIGHT_PASS_MODEL_NOT_CALLED")
            records=[json.loads(x.read_text("utf-8")) for x in j.glob("*.json")]
            seen={(x["phase"],x["result"]) for x in records}
            self.assertIn(("SOURCE_CATALYST","PASS"),seen)
            self.assertIn(("FULL_REVIEW_ELIGIBILITY","PASS"),seen)
            self.assertEqual(len(records),5)
            self.assertEqual(next(x for x in records if x["phase"]=="FULL_REVIEW_ELIGIBILITY")["data"]["review_family"],
                             "SOURCE_CATALYST_INDEPENDENT")
            self.assertFalse(list(b.glob("*")))
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);j=d/"journal";b=d/"budgets";j.mkdir();b.mkdir()
            forged=dict(c,positive_source_event_id="FORGED")
            r=one_candidate(candidate=forged,series_id=SID,local_receipts=j,
                model_reservations=b,existing_context={"news_sentiment":official()},
                acquire=lambda unused: (_ for _ in ()).throw(AssertionError("must not acquire")),
                clock=lambda:dt(12))
            self.assertEqual(r["status"],"SOURCE_CATALYST_NOT_VERIFIED_NO_MODEL")
            self.assertFalse(list(b.glob("*")))

    def test_released_positive_owner_refuses_unreleased_cloud_and_source_forgery(self):
        from unittest.mock import patch
        from paper_evaluator.v3_paper_minipc_selective_tick_v1 import (
            released_paper_positive_catalyst_model_once,
        )
        # Reuse the EXISTING owner-authenticated original packet contract,
        # not a caller-supplied source_verified boolean.
        from tests.test_v3_paper_existing_source_owner_to_single_writer_seam_v1 import (
            KEYS,event,
        )
        original=official()
        signed=event("news_sentiment",original)
        c=create("news_sentiment",original)
        calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);journal=root/"journal";budget=root/"budget"
            journal.mkdir();budget.mkdir()
            common=dict(
                candidate=c,series_id="PAPER-V3-20261018T100000Z",
                journal=journal,model_reservations=budget,
                expected_repo_sha="a"*40,
                expected_bundle_sha256="b"*64,
                expected_strategy_sha256="c"*64,
                read_active_series=lambda series: calls.append("cloud") or {},
                approval={"unused":"mock"},model_key="X"*24,
                existing_context={"news_sentiment":original},
                authenticated_owner_packet=signed,
                trusted_owner_hmac_keys=KEYS,
                clock_now=lambda:dt(12),
                acquire=lambda unused: calls.append("kraken"),
                model_client=lambda *args: calls.append("model"))
            with patch("paper_evaluator.v3_paper_minipc_selective_tick_v1.preflight_budget",
                       return_value=None):
                with self.assertRaisesRegex(ValueError,"active Paper-series"):
                    released_paper_positive_catalyst_model_once(**common)
                self.assertEqual(calls,["cloud"])
                self.assertFalse(list(journal.glob("*.json")))
                self.assertFalse(list(budget.glob("*")))
                calls.clear()
                wrong=dict(c,positive_source_event_id="FAKE")
                with self.assertRaisesRegex(ValueError,"identity changed"):
                    released_paper_positive_catalyst_model_once(
                        **dict(common,candidate=wrong))
                self.assertEqual(calls,[])
                stale=dict(official(),known_at_utc=dt(-4000))
                result=released_paper_positive_catalyst_model_once(
                    **dict(common,existing_context={"news_sentiment":stale}))
                self.assertEqual(result["status"],"POSITIVE_SOURCE_NOT_CURRENT_NO_MODEL")
                self.assertEqual(calls,[])
                self.assertFalse(list(journal.glob("*.json")))
                # Content-qualified unsiged or tampered packets must not
                # reach Cloud, Kraken, a paid model or the Paper journal.
                unsigned=released_paper_positive_catalyst_model_once(
                    **dict(common,authenticated_owner_packet=None))
                self.assertEqual(unsigned["status"],
                    "POSITIVE_SOURCE_OWNER_NOT_AUTHENTICATED_NO_MODEL")
                invalid=copy.deepcopy(signed)
                invalid["owner_integrity"]["owner_hmac_sha256"]="0"*64
                forged=released_paper_positive_catalyst_model_once(
                    **dict(common,authenticated_owner_packet=invalid))
                self.assertEqual(forged["status"],
                    "POSITIVE_SOURCE_OWNER_NOT_AUTHENTICATED_NO_MODEL")
                self.assertEqual(forged["source_status"],
                    "OWNER_HMAC_CONTENT_OR_IDENTITY_MISMATCH")
                altered=copy.deepcopy(original)
                altered["confirmed_net_buy_usd"]=999999
                # The signed original cannot be reused for a different
                # source-context payload, even with a valid old signature.
                mismatch=released_paper_positive_catalyst_model_once(
                    **dict(common,existing_context={"news_sentiment":altered}))
                self.assertEqual(mismatch["status"],
                    "POSITIVE_SOURCE_OWNER_NOT_AUTHENTICATED_NO_MODEL"
                    if mismatch.get("status")== "POSITIVE_SOURCE_OWNER_NOT_AUTHENTICATED_NO_MODEL"
                    else "POSITIVE_SOURCE_NOT_CURRENT_NO_MODEL")
                self.assertEqual(calls,[])
                self.assertFalse(list(journal.glob("*.json")))
                self.assertFalse(list(budget.glob("*")))

    def test_positive_smart_money_source_qualifies_without_news(self):
        c=create("smart_money_h10",money())
        self.assertEqual(c["positive_source_name"],"smart_money_h10")
        p,_,_=prompt(c,{"smart_money_h10":money()})
        self.assertIn("MULTIPLE_INDEPENDENT_CONFIRMED_NET_BUYS",p)
        wrong=dict(money(),not_self_dealing_checked=False)
        self.assertNotEqual(assess_positive_source(
            pair="XBT/EUR",source_name="smart_money_h10",
            snapshot=wrong,decision_at_utc=dt(12))["status"],ELIGIBLE)

    def test_polymarket_qualified_only_with_exact_pair_early_market_velocity(self):
        c=create("polymarket_h11",poly(),movement())
        p,_,_=prompt(c,{"polymarket_h11":poly(),"dynamic_move_radar":movement()})
        self.assertIn("DIRECT_POLYMARKET_EVENT_AND_COIN_EARLY_MOVE",p)
        for bad_move in (None,dict(movement(),pair="ETH/EUR"),
                         dict(movement(),known_at_utc=dt(60)),
                         dict(movement(),movement_phase="NONE")):
            out=assess_positive_source(
                pair="XBT/EUR",source_name="polymarket_h11",
                snapshot=poly(),decision_at_utc=dt(12),market_move=bad_move)
            self.assertNotEqual(out["status"],ELIGIBLE)
        negative_outcome=dict(poly(),direct_positive_outcome_for_pair=False)
        self.assertNotEqual(assess_positive_source(
            pair="XBT/EUR",source_name="polymarket_h11",
            snapshot=negative_outcome,decision_at_utc=dt(12),
            market_move=movement())["status"],ELIGIBLE)

    def test_misinformation_and_future_news_cannot_create_positive_candidates(self):
        changes=[
            {"official_primary_url":"https://treasury.gov.evil.example/press"},
            {"official_primary_url":"http://www.treasury.gov/press"},
            {"official_confirmation":False},
            {"coin_relevance_verified":False},
            {"direct_pair_beneficiary":False},
            {"pair":"ETH/EUR"},
            {"known_at_utc":dt(120)},
            {"known_at_utc":dt(-4200)},
            {"source_verified":False},
            {"sentiment":"NEUTRAL"},
            {"impact_mechanism":"vague"},
        ]
        for change in changes:
            news=dict(official(),**change)
            result=assess_positive_source(
                pair="XBT/EUR",source_name="news_sentiment",
                snapshot=news,decision_at_utc=dt(12))
            with self.subTest(change=change):
                self.assertNotEqual(result["status"],ELIGIBLE)
                self.assertFalse(result["buy_authorized"])
                self.assertFalse(result["approval_to_call_model"])
                self.assertFalse(result["orders"])

    def test_positive_missing_never_blocks_existing_scanner_route(self):
        c,e,t,m=fixture()
        r=propose_initial_full_review(c,e,t,m,decision_at_utc=dt(12))
        self.assertTrue(r["request_model_recheck_only"])
        old_prompt=build_v3_paper_full_model_prompt(
            candidate=c,eligibility=r,entry_evidence=e,ticker=t,
            pair_metadata=m,decision_at_utc=dt(12))
        self.assertIn('"positive_source_trigger_for_independent_paper_entry":null',old_prompt)
        self.assertIn("Missing optional sources must not block",old_prompt)

if __name__=="__main__":unittest.main()
