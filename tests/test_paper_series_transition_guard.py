"""Pre-cutover alert flood regression: one writer, matching readiness, truthful label."""
import unittest
from tools.paper_series_transition_guard import (
    PaperSeriesRoutingError, select_current_readiness, paper_completion_message_label)


def active(revision="V2R4-FROZEN", series="PAPER-V2R4-A"):
    return [{"status":"active","series_id":series,"strategy_revision":revision}]


def row(revision="V2R4-FROZEN", series="PAPER-V2R4-A"):
    return {"series_id":series,"strategy_revision":revision,
            "candidate_outcomes":100,"completion_ready":False}


class PaperTransitionAlertTests(unittest.TestCase):
    def test_existing_v2r4_remains_unchanged_and_correctly_named(self):
        self.assertEqual(select_current_readiness(active(),[row()]),row())
        self.assertEqual(paper_completion_message_label(row()),"V2R4-Paper")

    def test_v3_only_after_actual_cloud_active_identity(self):
        a=active("V3-PAPER-RELEASE","PAPER-V3-NEW")
        rows=[row(),row("V3-PAPER-RELEASE","PAPER-V3-NEW")]
        got=select_current_readiness(a,rows)
        self.assertEqual(got["series_id"],"PAPER-V3-NEW")
        self.assertEqual(paper_completion_message_label(got),"V3-Paper")

    def test_legacy_readiness_after_v3_cutover_must_not_trigger(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"MISSING_OR_DUPLICATE"):
            select_current_readiness(active("V3-PAPER-RELEASE","PAPER-V3-NEW"),[row()])

    def test_conflicting_two_writers_must_never_be_silenced(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"CARDINALITY"):
            select_current_readiness(active()+active("V3-PAPER-RELEASE","PAPER-V3-NEW"),[row()])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"CARDINALITY"):
            select_current_readiness([],[row()])

    def test_stale_revision_or_duplicate_readiness_fail_closed(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"WRONG_ACTIVE_REVISION"):
            select_current_readiness(active(),[row("V3-PAPER-RELEASE")])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"MISSING_OR_DUPLICATE"):
            select_current_readiness(active(),[row(),row()])

    def test_unknown_strategy_cannot_assume_v3_or_v2r4(self):
        with self.assertRaisesRegex(PaperSeriesRoutingError,"UNAPPROVED"):
            select_current_readiness(active("V2R3-HISTORIC"),[row("V2R3-HISTORIC")])
        with self.assertRaisesRegex(PaperSeriesRoutingError,"UNAPPROVED"):
            paper_completion_message_label(row("V2R3-HISTORIC"))


if __name__=="__main__":
    unittest.main()
