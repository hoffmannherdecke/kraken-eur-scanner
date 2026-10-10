"""H1-H11 research governance regression, read-only with no runtime coupling."""
import copy
import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
H3_GATE="V2R4_72H_ECONOMIC_REVIEW_THEN_OPTIONAL_SEPARATELY_APPROVED_NEW_H3_VERSION"
H6_GATE="V2R4_72H_ECONOMIC_REVIEW_THEN_SEPARATE_H6_ONE_CHANGE_SHADOW_APPROVAL"


def check_followthrough(state, ledger, framework):
    problems=[]
    rows=ledger.get("components") or []
    h3=[r for r in rows if r.get("id")=="orderflow_depth_imbalance"]
    h6=[r for r in rows if r.get("id")=="price_volume_trend_primitives"]
    if len(h3)!=1 or len(h6)!=1:
        return ["H3/H6 must each retain exactly one canonical migration component"]
    h3,h6=h3[0],h6[0]
    archived=[r for r in (state.get("closed_or_rejected_tracks") or [])
              if r.get("id")=="V3-H3-SHADOW-001"]
    live=[r for r in (state.get("strategy_changing_shadow_wip") or {}).get("active",[])
          if r.get("candidate_id")=="V3-H3-SHADOW-001"]
    q=[r for r in (state.get("strategy_changing_shadow_wip") or {}).get("queued",[])
       if r.get("candidate_id")=="V3-H6-NEXT"]
    reviews=[r for r in (state.get("next_control_decisions") or [])
             if r.get("id")=="V3-H3-ARCHIVE-DISPOSITION"]
    if len(archived)!=1 or archived[0].get("status")!="ARCHIVED_INCOMPLETE_NOT_FIXED_REVIEWED":
        problems.append("H3 archive status missing")
    if live:
        problems.append("Archived H3 falsely marked active")
    disposition=archived[0].get("archive_disposition") if len(archived)==1 else None
    if disposition!="DEFER_WITH_GATE" or reviews:
        problems.append("H3 archive disposition closure missing or still open")
    if h3.get("pending_gate")!=H3_GATE:
        problems.append("H3 next prospective one-change test/approval gate lost")
    h3info=h3.get("recovery_followthrough") or {}
    if (h3info.get("historic_trial_status")!="ARCHIVED_INCOMPLETE_NOT_FIXED_REVIEWED"
            or h3info.get("cloud_prospective_rows")!=0
            or h3info.get("reactivation_of_historic_trial_forbidden") is not True
            or h3info.get("new_trial_requires_new_baseline") is not True
            or h3info.get("archive_disposition")!="DEFER_WITH_GATE"
            or h3info.get("no_automatic_shadow_start") is not True):
        problems.append("H3 inconclusive evidence or no-reactivation safeguards lost")
    if "now collects" in h3.get("rationale","").lower():
        problems.append("H3 ledger still claims stale current capture")
    if len(q)!=1 or q[0].get("status")!="WAIT_FOR_V2R4_ECONOMIC_REVIEW_AND_SEPARATE_EXPLICIT_APPROVAL":
        problems.append("H6 may not start before V2R4 review and explicit approval")
    if h6.get("pending_gate")!=H6_GATE:
        problems.append("H6 sequencing/economic-release gate lost")
    h6info=h6.get("sequence_followthrough") or {}
    if (h6info.get("predecessor")!="orderflow_depth_imbalance"
            or h6info.get("requires_explicit_h3_archive_disposition") is not False
            or h6info.get("h3_archive_disposition")!="COMPLETED_DEFER_WITH_GATE"
            or h6info.get("requires_v2r4_economic_review") is not True
            or h6info.get("no_auto_start") is not True
            or h6info.get("no_duplicate_volume_vote") is not True):
        problems.append("H6 not safely sequenced after H3 and V2R4")
    headings=re.findall(r"^### H(\d+) —",framework,re.MULTILINE)
    if sorted(headings,key=int)!=[str(n) for n in range(1,12)]:
        problems.append("H1-H11 canonical hypothesis sections incomplete or duplicated")
    if "H1–H11 Managementkarte / verpflichtender Wiedervorlagepfad" not in framework:
        problems.append("H1-H11 followthrough index cannot be retrieved")
    return problems


class HComponentContinuityTests(unittest.TestCase):
    def source(self):
        state=json.loads((ROOT/"project-current-state.json").read_text("utf-8"))
        ledger=json.loads((ROOT/"research/v3-migration-ledger.json").read_text("utf-8"))
        framework=(ROOT/"docs/v3-research-framework.md").read_text("utf-8")
        return state,ledger,framework

    def test_present_lineage_and_one_to_eleven_pass(self):
        self.assertEqual(check_followthrough(*self.source()),[])

    def test_stale_h3_resume_claim_is_rejected(self):
        state,ledger,framework=self.source()
        next(x for x in ledger["components"] if x["id"]=="orderflow_depth_imbalance")["rationale"]="H3 now collects"
        self.assertTrue(any("stale current capture" in x for x in check_followthrough(state,ledger,framework)))

    def test_archived_h3_has_disposition_not_impossible_fixed_review(self):
        state,ledger,framework=self.source()
        self.assertEqual(check_followthrough(state,ledger,framework),[])
        archive=[x for x in state["next_control_decisions"]
                 if x.get("id") == "V3-H3-ARCHIVE-DISPOSITION"]
        self.assertEqual(archive,[])
        closed=next(x for x in state["closed_or_rejected_tracks"]
                    if x.get("id")=="V3-H3-SHADOW-001")
        self.assertEqual(closed["archive_disposition"],"DEFER_WITH_GATE")
        self.assertFalse(any(x.get("id")=="V3-H3-FIXED-REVIEW"
                             for x in state["next_control_decisions"]))
        self.assertEqual(state["strategy_changing_shadow_wip"]["active"],[])
        self.assertEqual(state["strategy_changing_shadow_wip"]["queued"][0]["status"],
                         "WAIT_FOR_V2R4_ECONOMIC_REVIEW_AND_SEPARATE_EXPLICIT_APPROVAL")

    def test_h6_ungated_promotion_is_rejected(self):
        state,ledger,framework=self.source()
        next(x for x in ledger["components"] if x["id"]=="price_volume_trend_primitives")["pending_gate"]="READY_NOW"
        self.assertTrue(any("H6 sequencing" in x for x in check_followthrough(state,ledger,framework)))

    def test_h3_automatic_reactivation_is_rejected(self):
        state,ledger,framework=self.source()
        next(x for x in ledger["components"] if x["id"]=="orderflow_depth_imbalance")["recovery_followthrough"]["reactivation_of_historic_trial_forbidden"]=False
        self.assertTrue(any("no-reactivation" in x for x in check_followthrough(state,ledger,framework)))

    def test_missing_h11_heading_is_rejected(self):
        state,ledger,framework=self.source()
        framework=framework.replace("### H11 — Prediction-Market Event Layer","### Prediction-Market Event Layer")
        self.assertTrue(any("sections incomplete" in x for x in check_followthrough(state,ledger,framework)))


if __name__=="__main__":
    unittest.main()
