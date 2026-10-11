"""Only one model review per candidate/PIT across all six V3 Paper families."""
import unittest

from paper_evaluator.v3_experimental_paper_family_router_v1 import (
    PRIORITY,select_one_full_review,
)


def hint(family,status=None,eligible=True):
    row=next(x for x in PRIORITY if x[0]==family)
    return {"kind":row[1],
            "status":row[2] if status is None else status,
            "pair":"BAT/EUR","source_candidate_id":"BAT-1",
            "new_snapshot_known_at_utc":"2026-10-11T20:00:00Z",
            "request_model_recheck_only":eligible,
            "decision":"NO_DECISION_AUTHORITY","orders":False,
            "real_money_actions":False,"checks":{"valid":True}}


def route(hints,seen=None):
    return select_one_full_review(
        series_id="PAPER-V3-TEST",candidate_id="BAT-1",pair="BAT/EUR",
        known_at_utc="2026-10-11T20:00:00Z",
        hints=hints,prior_reserved_review_keys=seen)


class FamilyRouterTests(unittest.TestCase):
    def test_six_families_only_one_selection_and_no_actual_model_right(self):
        hs={x[0]:hint(x[0]) for x in PRIORITY}
        r=route(hs)
        self.assertEqual(r["selected_family"],"FIRST_SCANNER_EARLY_REVIEW")
        self.assertEqual(len(r["also_eligible_not_requested"]),5)
        self.assertEqual(len(r["family_statuses"]),6)
        self.assertFalse(r["approval_to_call_model"])
        self.assertFalse(r["reserve_model_call_here"])
        self.assertTrue(r["must_atomically_reserve_before_actual_http"])
        self.assertFalse(r["model_called"])
        self.assertFalse(r["orders"])
        self.assertFalse(r["paper_writer_started"])
        self.assertTrue(r["explicit_separate_model_budget_required"])
        self.assertEqual(
            route(hs,{r["dedup_review_key"]})["status"],
            "ALREADY_RESERVED_MODEL_REVIEW_IDEMPOTENT",
        )

    def test_later_review_when_initial_not_allowed(self):
        hs={
            "FIRST_SCANNER_EARLY_REVIEW":
                hint("FIRST_SCANNER_EARLY_REVIEW","STALE_OR_FUTURE_ORIGINAL_CANDIDATE",False),
            "EXTENDED_GENUINE_NEW_BASE":hint("EXTENDED_GENUINE_NEW_BASE"),
        }
        r=route(hs)
        self.assertEqual(r["selected_family"],"EXTENDED_GENUINE_NEW_BASE")
        self.assertEqual(r["family_statuses"]["FIRST_SCANNER_EARLY_REVIEW"]["status"],
                         "STALE_OR_FUTURE_ORIGINAL_CANDIDATE")

    def test_forged_ticket_unknown_instead_of_model(self):
        valid=hint("FIRST_SCANNER_EARLY_REVIEW")
        changes=(
            lambda h:h.update(pair="XBT/EUR"),
            lambda h:h.update(kind="FAKE"),
            lambda h:h.update(source_candidate_id="WRONG"),
            lambda h:h.update(new_snapshot_known_at_utc="2026-10-11T20:01:00Z"),
            lambda h:h.update(request_model_recheck_only=False),
            lambda h:h.update(decision="BUY_SCOUT"),
            lambda h:h.update(orders=True),
        )
        for change in changes:
            h=dict(valid);change(h)
            r=route({"FIRST_SCANNER_EARLY_REVIEW":h})
            with self.subTest(r=r["status"]):
                self.assertTrue(r["status"].startswith("UNKNOWN_"))
                self.assertFalse(r["approval_to_call_model"])
        r=route({"FIRST_SCANNER_EARLY_REVIEW":
                 hint("FIRST_SCANNER_EARLY_REVIEW","NO_REVIEW",True)})
        self.assertEqual(r["status"],"UNKNOWN_UNEXPECTED_FAMILY_MODEL_REVIEW_PERMISSION")

    def test_all_ineligible_keeps_reasons_and_no_model(self):
        r=route({"FIRST_SCANNER_EARLY_REVIEW":
                hint("FIRST_SCANNER_EARLY_REVIEW","CORE_ENTRY_OR_TRADABILITY_NOT_READY",False)})
        self.assertEqual(r["status"],"NO_FULL_REVIEW_ELIGIBLE")
        self.assertFalse(r["model_called"])
        self.assertEqual(len(r["family_statuses"]),1)

if __name__=="__main__":
    unittest.main()
