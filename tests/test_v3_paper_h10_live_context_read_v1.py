"""Actual H10 Cloud PIT read path: exact pair, no forged positive multi-buy."""
import json,tempfile,unittest
from pathlib import Path
from paper_evaluator.v3_paper_h10_context_read_v1 import fetch_h10,merge_context_file
from paper_evaluator.v3_paper_context_bridge_v1 import fuse_existing_sources
from paper_evaluator.v3_paper_positive_source_entry_v1 import (
    assess_positive_source,ELIGIBLE,
)
from tests.test_v2r4_v3_entry_handoff_probe import dt

def source():
    return {"pair":"ZEC/EUR","source_verified":True,
            "source_owner":"EXISTING_H10_HYPERLIQUID_PROSPECTIVE_CAPTURE",
            "source_id":"v3_h10_asset_consensus_30m",
            "observed_at_utc":dt(2),"known_at_utc":dt(3),
            "consensus_direction":"LONG","independent_wallet_count":1,
            "cohort_id":"V3-H10-COHORT-001",
            "source_fill_seen_at_utc":dt(2),
            "research_consensus_not_buy_authority":True}

class V3H10LiveReadTests(unittest.TestCase):
    def test_verified_same_coin_live_context_flows_to_actual_v3_model_context(self):
        def cloud(url,token,payload):
            self.assertEqual(payload["pair"],"ZEC/EUR")
            self.assertEqual(payload["action"],"read_existing_h10_optional_context")
            self.assertEqual(token,"local-secret-not-logged-or-persisted")
            return {"ok":True,"status":"H10_PIT_CONTEXT_ONLY",
                    "pair":"ZEC/EUR","sources":{"smart_money_h10":source()}}
        raw=fetch_h10(pair="ZEC/EUR",
             token="local-secret-not-logged-or-persisted",post=cloud)
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"context.json"
            f.write_text(json.dumps({"market_phase_radar":{
                "source_verified":True,"source_owner":"EXISTING_2H",
                "source_id":"EPISODE-001","observed_at_utc":dt(2),
                "known_at_utc":dt(3),"regime":"RECOVERY"}}),"utf-8")
            x=merge_context_file(path=f,pair="ZEC/EUR",live=raw)
            self.assertTrue(x["h10_available"])
            payload=json.loads(f.read_text("utf-8"))
            c=fuse_existing_sources(payload,decision_at_utc=dt(5),pair="ZEC/EUR")
            self.assertEqual(c["sources"]["smart_money_h10"]["state"],
                             "AVAILABLE_PIT_CONTEXT_ONLY")
            self.assertEqual(c["sources"]["market_phase_radar"]["state"],
                             "AVAILABLE_PIT_CONTEXT_ONLY")
            self.assertEqual(c["sources"]["smart_money_h10"]["values"]["independent_wallet_count"],1)
            candidate=assess_positive_source(pair="ZEC/EUR",
                source_name="smart_money_h10",snapshot=payload["smart_money_h10"],
                decision_at_utc=dt(5))
            self.assertNotEqual(candidate["status"],ELIGIBLE)
            self.assertFalse(candidate["buy_authorized"])

    def test_no_source_stays_soft_and_filters_old_wrong_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/"context.json"
            f.write_text(json.dumps({"news_sentiment":{"pair":"ETH/EUR"},
                                     "market_phase_radar":{"regime":"UNKNOWN"},
                                     "smart_money_h10":source()}),"utf-8")
            out=merge_context_file(path=f,pair="XBT/EUR",
                                   live={"sources":{},"status":"NOT_AVAILABLE_OR_STALE"})
            self.assertFalse(out["h10_available"])
            c=json.loads(f.read_text("utf-8"))
            self.assertNotIn("news_sentiment",c)
            self.assertNotIn("smart_money_h10",c)
            self.assertIn("market_phase_radar",c)

    def test_invalid_pair_remote_identity_or_untrusted_owner_fail_closed(self):
        with self.assertRaises(ValueError):
            fetch_h10(pair="ZEC/USDT",token="known-secret-value-min-24-chars",post=lambda *_:None)
        for response in ({"ok":False,"pair":"ZEC/EUR"},
                         {"ok":True,"pair":"ETH/EUR","sources":{}},
                         {"ok":True,"pair":"ZEC/EUR","sources":{"something":1}},
                         {"ok":True,"pair":"ZEC/EUR","sources":{
                            "smart_money_h10":dict(source(),source_owner="FORGED")}}):
            with self.assertRaises(ValueError):
                fetch_h10(pair="ZEC/EUR",token="known-secret-value-min-24-chars",
                          post=lambda *_,response=response:response)

if __name__=="__main__":unittest.main()
