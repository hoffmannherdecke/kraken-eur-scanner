"""Regression: materially important V2R4 missed second-leg learning cannot vanish in successors."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("v3_entry_lineage_guard",ROOT/"tools/validate-v3-entry-succession-lineage.py")
MODULE=importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def documents():
    return [
        json.loads((ROOT/"research/v3-migration-ledger.json").read_text("utf-8")),
        json.loads((ROOT/"project-current-state.json").read_text("utf-8")),
        json.loads((ROOT/"research/strategy-learning-causal-gate-v1.json").read_text("utf-8")),
        json.loads((ROOT/"research/v3/coin-entry-evidence-lineage-v1.json").read_text("utf-8")),
    ]


class PermanentExtendedLearningLineageTests(unittest.TestCase):
    def test_canonical_contract_passes(self):
        self.assertEqual(MODULE.validate(ROOT), [])

    def test_lost_v3_to_v4_followup_blocked(self):
        ledger, state, gate, lineage = documents()
        state["next_control_decisions"]=[
            x for x in state["next_control_decisions"]
            if x.get("id")!="V3-EXTENDED-SECOND-LEG-LEARNING-GATE"
        ]
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("future review trigger" in e for e in errs),errs)

    def test_adding_duplicate_reversal_signal_blocked(self):
        ledger, state, gate, lineage = documents()
        ledger["components"].append(copy.deepcopy(next(x for x in ledger["components"] if x["id"]=="late_chase_protection")))
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("must be unique" in e for e in errs),errs)

    def test_reversing_A_and_B_or_dropping_H3_blocked(self):
        ledger, state, gate, lineage = documents()
        late=next(x for x in ledger["components"] if x["id"]=="late_chase_protection")
        late["successor_refinement"]["stage_A"]["depends_on"]="AFTER_B"
        late["successor_refinement"]["stage_B"]["depends_on"]="NONE"
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("prospective input-only A" in e for e in errs),errs)
        self.assertTrue(any("separate EXTENDED policy B" in e for e in errs),errs)

    def test_old_h3_fixed_review_cannot_return_as_successor_gate(self):
        ledger,state,gate,lineage=documents()
        late=next(x for x in ledger["components"] if x["id"]=="late_chase_protection")
        late["successor_refinement"]["stage_A"]["depends_on"]="V3_H3_FIXED_REVIEW"
        state["next_control_decisions"].append({
            "id": "V3-H3-FIXED-REVIEW",
            "status": "READY",
        })
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("archive disposition" in e for e in errs),errs)
        self.assertTrue(any("obsolete fixed-review" in e for e in errs),errs)

    def test_false_retroactive_approval_rejected(self):
        ledger, state, gate, lineage = documents()
        gate["incident"]["retrospective_20261008_09_extended_reentry"]["status_for_release"]="VERIFIED"
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("cannot be claimed as release proof" in e for e in errs),errs)

    def test_extra_work_or_active_strategy_mutation_blocked(self):
        ledger,state,gate,lineage=documents()
        status=next(x for x in state["next_control_decisions"] if x.get("id")=="V3-EXTENDED-SECOND-LEG-LEARNING-GATE")
        status["no_new_work_run"]=False
        ref=next(x for x in ledger["components"] if x["id"]=="late_chase_protection")["successor_refinement"]
        ref["automatic_activation"]=True
        errs=MODULE.validate_documents(ledger,state,gate,lineage)
        self.assertTrue(any("new Work or live mutation" in e for e in errs),errs)
        self.assertTrue(any("illegal active coupling" in e for e in errs),errs)


if __name__=="__main__":
    unittest.main()
