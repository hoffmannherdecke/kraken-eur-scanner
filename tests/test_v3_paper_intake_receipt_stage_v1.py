"""Tests for local immutable V3 ingress staging: no runtime, model or cloud."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from paper_evaluator.v3_paper_intake_receipt_stage_v1 import (
    prepare_receipts, stage_receipts_explicitly,
)


def sample():
    def c(name, offset, origin="SCANNER"):
        return {"candidate_id": name, "pair": "XBT/EUR", "altname": "XXBTZEUR",
                "entry_origin": origin,
                "event_time_utc": f"2026-10-12T10:{offset:02d}:00Z"}
    return {
        "kind": "V3_FUTURE_SINGLE_PAPER_WRITER_PRE_FLIGHT_PLAN_V1",
        "series_id": "PAPER-V3-TEST-INTAKE-STAGE",
        "at_utc": "2026-10-12T10:05:00Z",
        "model_http_authorized": False,
        "paper_writer_active": False,
        "orders": False,
        "real_money_actions": False,
        "v2r4_changed": False,
        "cloud_active_series_changed": False,
        "selected_candidates": [c("A", 1)],
        "review_preflights": [{
            "candidate_id": "A", "pair": "XBT/EUR",
            "status": "ELIGIBLE_FULL_REVIEW", "eligible_for_full_model_review": True,
            "model_review_authorized": False,
        }],
        "ingress": {
            "capacity_deferred_originals": [c("B", 2)],
            "same_pair_coalesced_originals": [c("C", 3)],
            "rejected_originals": [],
            "counts": {"selected": 1, "suppressed_or_deferred": 2},
            "dispositions": {
                "CAPACITY_DEFERRED_NOT_A_NEGATIVE_MARKET_DECISION": 1,
                "SAME_PAIR_CONCURRENT_REVIEW_COALESCED_NOT_LOST": 1,
            }
        }
    }


class IntakeReceiptStageTests(unittest.TestCase):
    def test_all_three_original_ids_and_pre_model_p0_are_durable_idempotent(self):
        original = sample()
        with tempfile.TemporaryDirectory() as p:
            folder = Path(p)
            first = stage_receipts_explicitly(preflight=original, journal_directory=folder)
            self.assertEqual(first["written"], 4)
            self.assertEqual(first["originals_with_receipt"], 3)
            self.assertFalse(first["cloud_ack_verified"])
            self.assertFalse(first["all_original_decisions_durable"])
            self.assertFalse(first["model_http_authorized"])
            items = [json.loads(f.read_text()) for f in folder.glob("*.json")]
            self.assertEqual({x["candidate_id"] for x in items}, {"A", "B", "C"})
            self.assertEqual({x["result"] for x in items
                              if x["candidate_id"] in ("B", "C")}, {"SKIP"})
            repeat = stage_receipts_explicitly(preflight=original, journal_directory=folder)
            self.assertEqual(repeat["written"], 0)
            self.assertEqual(repeat["identical_replays"], 4)
            self.assertEqual(len(list(folder.glob("*.json"))), 4)

    def test_real_deferred_scanner_original_can_stage_separate_once_only_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            first=sample()
            stage_receipts_explicitly(preflight=first,journal_directory=root)
            other=sample()
            original=other["ingress"]["capacity_deferred_originals"][0]
            other["selected_candidates"]=[dict(original,deferred_recheck=True)]
            other["review_preflights"]=[{
                "candidate_id":"B","pair":"XBT/EUR",
                "status":"RECHECK_ELIGIBLE","eligible_for_full_model_review":True,
                "model_review_authorized":False,
            }]
            other["at_utc"]="2026-10-12T10:06:00Z"
            other["ingress"]["capacity_deferred_originals"]=[]
            other["ingress"]["same_pair_coalesced_originals"]=[]
            other["ingress"]["counts"]={"selected":1,"suppressed_or_deferred":0}
            other["ingress"]["dispositions"]={}
            outcome=stage_receipts_explicitly(preflight=other,journal_directory=root)
            self.assertEqual(outcome["written"],2)
            rows=[json.loads(p.read_text()) for p in root.glob("*.json")]
            b_rows=[r for r in rows if r["candidate_id"]=="B"]
            self.assertEqual(len(b_rows),3)
            self.assertEqual({(r["phase"],r["event_key"],r["result"])
                 for r in b_rows},{("SCANNER_CAPTURE","FIRST","SKIP"),
                                   ("SCANNER_CAPTURE","DEFERREDRECHECK","SEEN"),
                                   ("FULL_REVIEW_ELIGIBILITY","DEFERREDRECHECK","PASS")})
            repeated=stage_receipts_explicitly(
                preflight=other,journal_directory=root)
            self.assertEqual(repeated["written"],0)
            self.assertEqual(repeated["identical_replays"],2)
            with tempfile.TemporaryDirectory() as missing:
                with self.assertRaisesRegex(ValueError,"capacity-deferred original"):
                    stage_receipts_explicitly(
                        preflight=other,journal_directory=Path(missing))

    def test_source_catalyst_never_promoted_by_untrusted_input_flag(self):
        x = sample()
        x["selected_candidates"][0]["entry_origin"] = (
            "VERIFIED_POSITIVE_SOURCE_CATALYST"
        )
        x["independently_authenticated_source_owner_runtime_proven"] = True
        rows, unattributed = prepare_receipts(x)
        self.assertEqual(unattributed, 0)
        self.assertEqual(len(rows), 3)
        source = next(r for r in rows if r["candidate_id"] == "A")
        self.assertEqual(source["phase"], "SOURCE_INPUT")
        self.assertEqual(source["result"], "UNKNOWN")
        self.assertEqual(source["data"]["source_status"],
                         "SOURCE_OWNER_RUNTIME_AUTH_NOT_PROVEN")
        self.assertFalse(any(r["phase"] == "FULL_REVIEW_ELIGIBILITY"
                             and r["candidate_id"] == "A" for r in rows))

    def test_missing_original_overflow_and_mismatch_fail_closed(self):
        for mutate in (
            lambda d: d["ingress"]["capacity_deferred_originals"].clear(),
            lambda d: d["ingress"]["same_pair_coalesced_originals"].clear(),
            lambda d: d["ingress"]["counts"].update(selected=9),
            lambda d: d["review_preflights"][0].update(candidate_id="B"),
            lambda d: d.update(model_http_authorized=True),
            lambda d: d["ingress"]["capacity_deferred_originals"][0].update(candidate_id="A"),
            lambda d: d["selected_candidates"][0].update(event_time_utc="2026-10-12T10:06:00Z"),
        ):
            x = sample()
            mutate(x)
            with self.assertRaises(ValueError):
                prepare_receipts(x)


    def test_rejections_are_individually_audited_with_no_fake_coin_or_profit(self):
        x = sample()
        x["ingress"]["counts"]["suppressed_or_deferred"] = 3
        x["ingress"]["dispositions"]["UNKNOWN_ORIGINAL_EVENT_CLOCK"] = 1
        audit = {
            "kind":"V3_ROUTER_REJECTED_ORIGINAL_AUDIT_V1",
            "audit_id":"V3-INPUT-REJECT-" + "a"*32,
            "input_stream":"SCANNER","input_index":2,
            "reason":"UNKNOWN_ORIGINAL_EVENT_CLOCK",
            "original_candidate_id_if_safe":"bad-time",
            "original_pair_if_safe":"XBT/EUR",
            "original_event_time_if_parseable":None,
            "original_source_event_id_if_safe":None,
            "original_untrusted_and_not_tradeable":True,
        }
        x["ingress"]["rejected_originals"] = [audit]
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            first=stage_receipts_explicitly(preflight=x,journal_directory=root)
            self.assertEqual(first["router_rejection_audit_receipts"],1)
            self.assertEqual(first["unattributed_router_rejections"],0)
            self.assertFalse(first["all_original_decisions_durable"])
            rows=[json.loads(p.read_text()) for p in root.glob("*.json")]
            only=next(r for r in rows if r["event_key"]=="ROUTERREJECT")
            self.assertEqual(only["candidate_id"],audit["audit_id"])
            self.assertEqual(only["pair"],"UNMAPPED/EUR")
            self.assertEqual(only["result"],"UNKNOWN")
            self.assertEqual(only["data"]["review_checks"]["original_candidate_id_if_safe"],"bad-time")
            self.assertIsNone(only["data"].get("position_net_pnl_eur"))
            self.assertEqual(first["written"],5)
            self.assertEqual(stage_receipts_explicitly(preflight=x,journal_directory=root)["identical_replays"],5)

    def test_missing_or_tampered_rejected_originals_fail_closed(self):
        x=sample()
        x["ingress"]["counts"]["suppressed_or_deferred"]=3
        x["ingress"]["dispositions"]["UNKNOWN_ORIGINAL_EVENT_CLOCK"]=1
        with self.assertRaises(ValueError):
            prepare_receipts(x)
        x["ingress"]["rejected_originals"]=[{
            "kind":"V3_ROUTER_REJECTED_ORIGINAL_AUDIT_V1",
            "audit_id":"V3-INPUT-REJECT-"+"f"*32,
            "input_stream":"SCANNER","input_index":1,
            "reason":"FUTURE_EVENT_NOT_YET_KNOWN",
            "original_untrusted_and_not_tradeable":True,
        }]
        with self.assertRaises(ValueError):
            prepare_receipts(x)
        x["ingress"]["rejected_originals"][0]["reason"]="UNKNOWN_ORIGINAL_EVENT_CLOCK"
        x["ingress"]["rejected_originals"][0]["audit_id"]="bad"
        with self.assertRaises(ValueError):
            prepare_receipts(x)

    def test_never_create_runtime_directory_and_conflicts_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as p:
            missing = Path(p)/"does-not-exist"
            with self.assertRaises(ValueError):
                stage_receipts_explicitly(preflight=sample(), journal_directory=missing)
            root = Path(p)
            stage_receipts_explicitly(preflight=sample(), journal_directory=root)
            x = sample()
            x["ingress"]["capacity_deferred_originals"][0]["pair"] = "ETH/EUR"
            with self.assertRaises(ValueError):
                stage_receipts_explicitly(preflight=x, journal_directory=root)
            self.assertEqual(len(list(root.glob("*.json"))), 4)


if __name__ == "__main__":
    unittest.main()
