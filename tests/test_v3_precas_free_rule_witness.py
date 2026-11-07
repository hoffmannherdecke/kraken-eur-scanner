"""Isolated replay uses the actual free rule, P4, journal and sandbox export."""
import copy
import hashlib
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_rule_based_paper_decision_v1 import fixture, iso
from tools.v3_paper_precas_originalhost_offline_witness_v1 import (
    CONTROLLED_INPUT_KIND, FREE_KIND, free_rule_cases,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import (
    CONTROLLED_BUY_CANDIDATE_ID, _RELEASED_MODEL_NATIVE_OWNER, one_candidate,
)
from tools.v3_paper_precas_synthetic_cloud_sandbox_v1 import (
    compare_free_rule_sql_readback, free_rule_export,
)

COMMIT = "1" * 40
SERIES = "PAPER-V3-CANARY-PRECAS-FREE-" + COMMIT[:12].upper()


def input_case(negative):
    candidate, ticker, context, _, _ = fixture(atr=0.25 if negative else 2)
    candidate = dict(candidate, kind="CANONICAL_CANDIDATE_HANDOFF_V1",
                     entry_origin="SCANNER")
    if negative:
        candidate["candidate_id"] += "-NEGATIVE"
    pair = candidate["pair"]
    preflight = dict.fromkeys(("model_http_authorized", "paper_writer_active",
                              "orders", "real_money_actions", "v2r4_changed",
                              "cloud_active_series_changed"), False)
    preflight.update(kind="V3_FUTURE_SINGLE_PAPER_WRITER_PRE_FLIGHT_PLAN_V1",
                     at_utc=iso(-2), selected_candidates=[candidate],
                     ingress={"capacity_deferred_originals": [], "same_pair_coalesced_originals": [],
                              "rejected_originals": [], "counts": {"selected": 1, "suppressed_or_deferred": 0},
                              "dispositions": {}},
                     review_preflights=[{"candidate_id": candidate["candidate_id"], "pair": pair,
                                        "model_review_authorized": False, "status": "READY",
                                        "eligible_for_full_model_review": True}])
    return {"candidate": candidate, "preflight": preflight, "decision_at_utc": iso(0),
            "entry_evidence": context["candidate_entry_evidence"],
            "ticker": dict(ticker, pair=pair, observed_at_utc=iso(-2)),
            "pair_metadata": dict(context["kraken_pair_metadata"], pair=pair, spot=True,
                                  quote="EUR", minimum_order_passed=True, observed_at_utc=iso(-3))}


class FreeRuleWitnessTests(unittest.TestCase):
    def test_isolated_real_worker_and_exact_cloud_readback_contract(self):
        with tempfile.TemporaryDirectory() as td, \
             patch("paper_evaluator.evaluate.http_json",
                   side_effect=AssertionError("no provider or Kraken HTTP in replay")), \
             patch("paper_evaluator.v3_paper_minipc_selective_tick_v1._require_released_paper_cloud",
                   side_effect=AssertionError("isolated replay must not enter release guard")):
            root = Path(td) / "Research" / "V3Paper" / ("PRECAS-FREE-RULE-" + COMMIT[:12])
            root.parent.mkdir(parents=True)
            inputs = {"kind": "V3_PRECAS_PINNED_SCANNER_PIT_CASES_V1",
                      "cases": {"POSITIVE_BUY_SCOUT": input_case(False),
                                "NEGATIVE_REJECT": input_case(True)}}
            with self.assertRaisesRegex(ValueError, "isolated"):
                free_rule_cases(root, "PAPER-V3-20261107T130000Z", inputs)
            self.assertFalse(root.exists())
            cases = free_rule_cases(root, SERIES, inputs)
            self.assertEqual([(c["p4_decision"], c["paper_fill_count"]) for c in cases],
                             [("BUY_SCOUT", 1), ("REJECT", 0)])
            with self.assertRaises(FileExistsError):
                free_rule_cases(root, SERIES, inputs)
            witness = {"kind": FREE_KIND, "release_commit": COMMIT, "series_id": SERIES,
                       "paper_release_authorized": False, "technical_release_proofs_credited": 0,
                       "runtime_identity": {"repo_sha": COMMIT, "code_fingerprint_sha256": "a" * 64,
                                            "strategy_fingerprint_sha256": "b" * 64}, "cases": cases}
            (root / "free-rule-witness.json").write_text(json.dumps(witness), encoding="utf-8")
            exported = free_rule_export(root, COMMIT)
            self.assertEqual(len(exported["receipts"]), 7)
            readback = [{"series_id": SERIES, "event_id": row["event_id"],
                         "content_sha256": row["sha256"], "payload": json.loads(row["canonical_json"])}
                        for row in exported["receipts"]]
            compare_free_rule_sql_readback(exported, readback)
            changed = copy.deepcopy(readback)
            changed[0]["payload"]["result"] = "OTHER"
            with self.assertRaisesRegex(ValueError, "payload differs"):
                compare_free_rule_sql_readback(exported, changed)
            with self.assertRaisesRegex(ValueError, "row set differs"):
                compare_free_rule_sql_readback(exported, readback + [readback[0]])
            path = root / "journal" / (readback[0]["event_id"] + ".json")
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "missing or changed"):
                free_rule_export(root, COMMIT)


    def test_controlled_buy_with_original_reject_stays_isolated(self):
        neg = input_case(True)
        candidate = neg["candidate"]
        at = datetime.fromisoformat(candidate["event_time_utc"].replace("Z", "+00:00"))
        run, pair, ts = 23, candidate["pair"].replace("/", "-"), int(at.timestamp())
        candidate.update(candidate_id=f"{at:%Y%m%d-%H%M%S}-{pair}-r{run}",
                         source_scanner_run_id=run, queue_id=f"{run}:{pair}:{ts}",
                         event_ts=ts, scanner_candidate={}, scanner_market_context={})
        neg["preflight"]["review_preflights"][0]["candidate_id"] = candidate["candidate_id"]
        raw = json.dumps(candidate)
        bundle = {"kind": CONTROLLED_INPUT_KIND, "cases": {"NEGATIVE_REJECT": neg},
                  "negative_original": {"raw_scanner_handoff": raw, "capture_commit": "a" * 40,
                                        "sha256": hashlib.sha256(raw.encode()).hexdigest()}}
        with tempfile.TemporaryDirectory() as td, patch(
                "paper_evaluator.evaluate.http_json", side_effect=AssertionError("HTTP forbidden")):
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "isolated technical witness"):
                one_candidate(candidate={"candidate_id": CONTROLLED_BUY_CANDIDATE_ID},
                              series_id="PAPER-V3-20261107T130000Z", local_receipts=root,
                              model_reservations=root, admit_staged_scanner_one_free_rule=True,
                              _released_model_capability=_RELEASED_MODEL_NATIVE_OWNER)
            tampered = copy.deepcopy(bundle)
            tampered["negative_original"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "REJECT Scanner original"):
                free_rule_cases(root / "tampered", SERIES, tampered)
            self.assertFalse((root / "tampered").exists())
            cases = free_rule_cases(root / "mixed", SERIES, bundle)
            self.assertEqual([(c["p4_decision"], c["paper_fill_count"], c["input_origin"])
                              for c in cases], [("BUY_SCOUT", 1, "CONTROLLED_TECHNICAL_BUY_V1"),
                                               ("REJECT", 0, "ORIGINAL_SCANNER_PIT_V1")])
            self.assertEqual(cases[0]["candidate_id"], CONTROLLED_BUY_CANDIDATE_ID)
            self.assertEqual(cases[1]["candidate_id"], candidate["candidate_id"])
