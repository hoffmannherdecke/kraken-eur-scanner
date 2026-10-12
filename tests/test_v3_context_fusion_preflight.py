"""V3 optional context: structural authority, PIT anti-lookahead and neutral missing data."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.v3_context_fusion_preflight import (
    ROOT, GateError, PLAN, read as original_read, validate, classify_snapshot,
)


class V3ContextFusionTests(unittest.TestCase):
    def setUp(self):
        self.gate = validate(ROOT)
        self.now = "2026-10-11T10:30:00Z"
        self.base = {
            "kind": "V3_OPTIONAL_CONTEXT_PROBE_V1",
            "pair": "XBT/EUR", "decision_at_utc": self.now,
            "evidence_refs": [],
        }

    def event(self, stream="smartmoney_h10", **kwargs):
        row = {
            "stream_id": stream, "pair": "XBT/EUR",
            "source_event_at_utc": "2026-10-11T10:00:00Z",
            "first_seen_at_utc": "2026-10-11T10:12:00Z",
            "retrieved_at_utc": "2026-10-11T10:12:04Z",
            "known_at_utc": "2026-10-11T10:12:04Z",
            "kraken_pit_mapping_verified": True,
            "event_pair_link_preregistered": True,
            "evidence_ref": "synthetic-contract-reference-001",
        }
        row.update(kwargs)
        return row

    def test_exact_nine_existing_owners_and_no_release(self):
        self.assertEqual(self.gate["status"],
                         "PASSIVE_RESEARCH_ROUTES_VERIFIED_NO_STRATEGY_INTEGRATION")
        ids = {x["stream_id"] for x in self.gate["lanes"]}
        self.assertEqual(len(ids), 9)
        self.assertTrue({"smartmoney_h10", "prediction_h11", "source_quality",
                         "market_regime", "derivatives_h2", "onchain_h8"}.issubset(ids))
        self.assertFalse(self.gate["permission_to_trade"])
        self.assertFalse(self.gate["added_schedules"])
        self.assertTrue(self.gate["frozen_policy_preserved"])

    def test_empty_context_stays_neutral_not_buy_denial(self):
        result = classify_snapshot(self.gate, self.base)
        self.assertEqual(result["records"], [])
        self.assertTrue(result["no_buy_wait_reject_stop_sizing_decision"])
        self.assertFalse(result["no_new_schedules"] is False)

    def test_future_info_cannot_be_backfilled(self):
        for key, updates, expected in [
            ("source_is_future", {"source_event_at_utc": "2026-10-11T10:31:00Z"},
             "KNOWN_AT_PRECEDES_SOURCE_OR_OBSERVATION"),
            ("retrieved_after_decision", {
                "source_event_at_utc": "2026-10-11T10:01:00Z",
                "first_seen_at_utc": "2026-10-11T10:35:00Z",
                "retrieved_at_utc": "2026-10-11T10:35:00Z",
                "known_at_utc": "2026-10-11T10:35:00Z"}, "FUTURE_INFORMATION_LEAKAGE"),
            ("missing_timestamp", {"first_seen_at_utc": None},
             "INCOMPLETE_KNOWN_AT_TIMESTAMPS"),
        ]:
            with self.subTest(key=key):
                req = dict(self.base, evidence_refs=[self.event(**updates)])
                row = classify_snapshot(self.gate, req)["records"][0]
                self.assertEqual(row["reason"], expected)
                self.assertEqual(row["status"], "NOT_EVALUABLE")

    def test_h10_pit_matching_does_not_claim_trade_edge(self):
        req = dict(self.base, evidence_refs=[self.event()])
        result = classify_snapshot(self.gate, req)
        self.assertEqual(result["records"][0]["status"],
                         "PIT_TIME_ADMISSIBLE_RESEARCH_ONLY")
        self.assertTrue(result["source_claims_are_not_independently_verified"])
        self.assertTrue(result["no_trade_or_order_permission"])

    def test_h10_unverified_contemporaneous_kraken_mapping_neutral(self):
        req = dict(self.base, evidence_refs=[
            self.event(kraken_pit_mapping_verified=False)])
        result = classify_snapshot(self.gate, req)
        self.assertEqual(result["records"][0]["status"], "NOT_ASSOCIABLE")

    def test_polymarket_without_preregistered_event_to_pair_is_not_a_signal(self):
        req = dict(self.base, evidence_refs=[
            self.event(stream="prediction_h11", event_pair_link_preregistered=False)])
        result = classify_snapshot(self.gate, req)
        self.assertEqual(result["records"][0]["status"], "NOT_ASSOCIABLE")
        self.assertEqual(result["records"][0]["reason"],
                         "NO_PREDECLARED_EVENT_TO_PAIR_LINK")

    def test_source_manager_cannot_become_buy_confirmation(self):
        req = dict(self.base, evidence_refs=[self.event(stream="source_quality")])
        result = classify_snapshot(self.gate, req)
        self.assertEqual(result["records"][0]["status"], "STEWARDSHIP_ONLY")

    def test_deduplicate_exact_source_reference(self):
        req = dict(self.base, evidence_refs=[self.event(), self.event()])
        result = classify_snapshot(self.gate, req)
        self.assertEqual(result["records"][1]["status"], "RESEARCH_DUPLICATE")

    def test_unknown_stream_and_wrong_venue_are_rejected(self):
        req = dict(self.base, evidence_refs=[self.event(stream="real_money_orders")])
        with self.assertRaisesRegex(GateError, "unregistered"):
            classify_snapshot(self.gate, req)
        req = dict(self.base, pair="BTC/USDT")
        with self.assertRaisesRegex(GateError, "Kraken Spot EUR"):
            classify_snapshot(self.gate, req)

    def _bad(self, mutate):
        base = copy.deepcopy(original_read(ROOT, PLAN))
        mutate(base)
        def mocked(root, path):
            return base if path == PLAN else original_read(root, path)
        return mocked

    def test_dropped_h11_or_source_steward_fails_closed(self):
        for sid in ("prediction_h11", "source_quality", "smartmoney_h10"):
            with self.subTest(sid=sid):
                def remove(j):
                    j["optional_context_fusion"]["lanes"] = [
                        x for x in j["optional_context_fusion"]["lanes"]
                        if x["stream_id"] != sid
                    ]
                with patch("tools.v3_context_fusion_preflight.read",
                           side_effect=self._bad(remove)):
                    with self.assertRaisesRegex(GateError, "missing or duplicate"):
                        validate(ROOT)

    def test_unsafe_optional_source_veto_or_echtgeld_fails_closed(self):
        for key, value in (("optional_missing_is_neutral", False),
                           ("no_signal_votes_or_optional_buy_vetos", False)):
            def mutate(j):
                j["optional_context_fusion"][key] = value
            with self.subTest(key=key):
                with patch("tools.v3_context_fusion_preflight.read",
                           side_effect=self._bad(mutate)):
                    with self.assertRaisesRegex(GateError, "unsafe optional data"):
                        validate(ROOT)
        def allow_live(j):
            j["optional_context_fusion"]["restrictions"]["real_money_actions"] = True
        with patch("tools.v3_context_fusion_preflight.read",
                   side_effect=self._bad(allow_live)):
            with self.assertRaisesRegex(GateError, "unsafe shadow/release"):
                validate(ROOT)



from paper_evaluator.v3_paper_context_bridge_v1 import (
    fuse_existing_sources, STREAMS as MODEL_CONTEXT_STREAMS,
)


class V3ExistingModelContextIntegrationTests(unittest.TestCase):
    """Offline regression for the already used V3 full-model context seam."""

    def setUp(self):
        self.when = "2026-10-12T18:00:00Z"

    def fact(self, **values):
        return {
            "known_at_utc": "2026-10-12T17:35:00Z",
            "observed_at_utc": "2026-10-12T17:34:00Z",
            "source_verified": True,
            "source_owner": "EXISTING_RESEARCH_OWNER",
            "source_id": "offline-test-source",
            **values,
        }

    def test_existing_full_model_bridge_receives_four_missing_research_lanes(self):
        self.assertTrue({"global_market_crosscheck", "derivatives_h2",
                         "macro_h5", "onchain_h8"}.issubset(MODEL_CONTEXT_STREAMS))
        inputs = {
            "global_market_crosscheck": self.fact(btc_state="RISK_OFF"),
            "derivatives_h2": self.fact(pair="XBT/EUR", funding_rate_pct=0.1),
            "macro_h5": self.fact(event_id="official-calendar-test"),
            "onchain_h8": self.fact(pair="XBT/EUR", chain="bitcoin"),
            "smart_money_h10": self.fact(pair="XBT/EUR", independent_wallet_count=3),
            "polymarket_h11": self.fact(pair="XBT/EUR", event_id="event-test"),
        }
        out = fuse_existing_sources(inputs, decision_at_utc=self.when, pair="XBT/EUR")
        for key in inputs:
            with self.subTest(key=key):
                self.assertEqual(out["sources"][key]["state"], "AVAILABLE_PIT_CONTEXT_ONLY")
                self.assertFalse(out["sources"][key]["hard_veto"])
        self.assertTrue(out["optional_failure_never_hard_veto"])

    def test_wrong_pair_is_neutral_and_cannot_bleed_into_candidate(self):
        for key in ("derivatives_h2", "onchain_h8", "smart_money_h10",
                    "polymarket_h11", "news_sentiment"):
            with self.subTest(key=key):
                inp = {key: self.fact(pair="ETH/EUR", consensus_direction="BULLISH")}
                row = fuse_existing_sources(inp, decision_at_utc=self.when,
                                            pair="XBT/EUR")["sources"][key]
                self.assertEqual(row["state"], "NOT_ASSOCIABLE_OTHER_PAIR")
                self.assertFalse(row["hard_veto"])
                self.assertNotIn("values", row)

    def test_future_or_stale_provenance_never_becomes_model_fact(self):
        cases = [
            (self.fact(pair="XBT/EUR", first_seen_at_utc="2026-10-12T19:00:00Z"),
             "INVALID_FUTURE_OR_REVERSED_CLOCK"),
            (self.fact(pair="XBT/EUR", known_at_utc="2026-10-12T19:00:00Z"),
             "INVALID_FUTURE_OR_REVERSED_CLOCK"),
            (self.fact(pair="XBT/EUR", known_at_utc="2026-10-12T15:00:00Z",
                       observed_at_utc="2026-10-12T14:00:00Z"), "STALE_OPTIONAL"),
        ]
        for inp, expected in cases:
            with self.subTest(expected=expected):
                row = fuse_existing_sources(
                    {"derivatives_h2": inp}, decision_at_utc=self.when,
                    pair="XBT/EUR")["sources"]["derivatives_h2"]
                self.assertEqual(row["state"], expected)
                self.assertFalse(row["hard_veto"])

    def test_missing_context_is_neutral_and_never_promotes_new_strategy(self):
        out = fuse_existing_sources({}, decision_at_utc=self.when, pair="XBT/EUR")
        self.assertTrue(all(item["state"] == "NOT_AVAILABLE" and
                            item["hard_veto"] is False
                            for item in out["sources"].values()))
        self.assertTrue(out["provenance_guards"]["no_auto_strategy_promotion"])

if __name__ == "__main__":
    unittest.main()
