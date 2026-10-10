"""No-network regression for V3 shared entry evidence ownership (not a trading test)."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read_json(rel):
    return json.loads((ROOT / rel).read_text("utf-8"))


class V3EntryLineageContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = read_json("research/v3/coin-entry-evidence-lineage-v1.json")
        self.ledger = read_json("research/v3-migration-ledger.json")
        self.components = {c["id"]: c for c in self.ledger["components"]}

    def test_unique_single_owner_and_no_extra_signal(self):
        ids = [c["id"] for c in self.ledger["components"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids.count("coin_specific_entry_evidence_provenance"), 1)
        self.assertEqual(self.contract["canonical_ledger_component"], "coin_specific_entry_evidence_provenance")
        self.assertFalse(self.contract["new_strategy_signal_component_created"])
        self.assertEqual(
            self.components[self.contract["canonical_ledger_component"]]["category"],
            "shared_candidate_entry_data_quality_not_independent_signal"
        )

    def test_existing_h6_and_legacy_alias_not_duplicated(self):
        self.assertEqual(self.components["price_volume_trend_primitives"]["migration_status"], "MORE_TESTING_REQUIRED")
        self.assertEqual(self.components["simple_price_volume_primitives"]["migration_status"], "NO_SUCCESSOR_CHANGE")
        overlap = {x["family"]: x for x in self.contract["overlap_ownership"]}
        self.assertEqual(overlap["H6"]["existing"], "price_volume_trend_primitives")
        self.assertEqual(overlap["H6"]["policy"], "REUSE_AS_EVIDENCE_ONLY_NO_DUPLICATE_FEATURE_VOTE")

    def test_neighbor_statuses_and_no_hidden_activation(self):
        overlap = {x["family"]: x for x in self.contract["overlap_ownership"]}
        self.assertEqual(set(overlap), {"H1","H3","H4","H6","H7","V2R4"})
        self.assertEqual(self.components["cross_crypto_lead_lag_breadth"]["migration_status"], "REJECT_WITH_EVIDENCE")
        for family, expected in (("H3","orderflow_depth_imbalance"),("H4","stop_trailing_ttl_exit_logic"),("H7","meta_take_no_take")):
            self.assertEqual(overlap[family]["existing"], expected)
        self.assertEqual(self.components["coin_specific_entry_evidence_provenance"]["migration_status"], "MORE_TESTING_REQUIRED")
        self.assertEqual(self.components["coin_specific_entry_evidence_provenance"]["strategy_coupling"], "NONE_INACTIVE_NOT_ATTACHED")
        for key, value in self.contract["runtime_guardrails"].items():
            self.assertIs(value, False, key)

    def test_source_reuse_and_files_exist(self):
        self.assertEqual(self.contract["source_registry_authority"], "kraken_spot_rest_public")
        src = read_json("research/source-registry.json")
        # Do not create a second OHLC source authority when the existing Kraken REST registry is suitable.
        self.assertIn("kraken_spot_rest_public", str(src))
        self.assertFalse(self.contract["new_market_data_source_created"])
        for key in ("implementation", "documentation"):
            self.assertTrue((ROOT / self.contract[key]).is_file())
        self.assertIn("coin-entry-evidence-lineage-v1.json",
                      (ROOT / "docs/v3-research-framework.md").read_text("utf-8"))

    def test_no_active_evaluator_import_or_automatic_queue(self):
        evaluator=(ROOT/"paper_evaluator/evaluate.py").read_text("utf-8")
        runner=(ROOT/"tools/v2r4-paper-local-runtime.py").read_text("utf-8")
        self.assertNotIn("successor_coin_entry_evidence_v1", evaluator)
        self.assertNotIn("successor_coin_entry_evidence_v1", runner)
        self.assertIn("V3_H3_001_ARCHIVE_DISPOSITION_AND_V2R4_ECONOMIC_REVIEW_BEFORE_NEW_SHADOW",self.contract["review_gates"])
        self.assertNotIn("V3_H3_FIXED_REVIEW_BEFORE_ANY_NEW_STRATEGY_CHANGING_SHADOW",self.contract["review_gates"])
        self.assertTrue(any("PROSPECTIVE" in x for x in self.contract["review_gates"]))


if __name__ == "__main__":
    unittest.main()
