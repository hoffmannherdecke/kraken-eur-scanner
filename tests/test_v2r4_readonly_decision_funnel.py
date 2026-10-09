"""Offline invariants for the V2R4 all-candidate read-only decision funnel."""
from collections import Counter
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"tools/v2r4-readonly-decision-funnel.py"
spec=importlib.util.spec_from_file_location("v2r4_readonly_decision_funnel",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW=datetime(2026,10,9,20,0,tzinfo=timezone.utc)
SERIES=module.EXPECTED_SERIES

def initial(cid,kind,*,codes=(),ttl=30,at="2026-10-09T18:00:00Z",pair="XBT/EUR"):
    return {"series_id":SERIES,"candidate_id":cid,"pair":pair,
            "candidate_event_time_utc":at,"evaluated_at_utc":at,
            "decision_context":{"kraken_pair_metadata":{"available":True}},
            "decision":{"decision":kind,"reason_codes":list(codes),"ttl_minutes":ttl},
            "v2r4_trigger_plan":{"conditions":[{"metric":"spread_pct"},{"metric":"closed_5m_volume_ratio_5"}]}
                     if kind=="WAIT" else None}

def recheck(cid,kind,*,time="2026-10-09T18:15:00Z",codes=(),record_kind="V2R4_LOCAL_TRIGGER_RECHECK_V1"):
    return {"series_id":SERIES,"candidate_id":cid,"kind":record_kind,
            "recheck_completed_at_utc":time,
            "decision":{"decision":kind,"reason_codes":list(codes)}}


class ReadOnlyCohortFunnelTests(unittest.TestCase):
    def test_recheck_events_not_double_counted_as_converted_candidates(self):
        src=[
            initial("a","WAIT",codes=["PAIR_ONLINE","REMAINING_MOVE_UNVERIFIED"]),
            initial("b","WAIT",codes=["VOLUME_CONFIRMATION_MISSING"]),
            initial("c","WAIT"),
            initial("d","REJECT",codes=["SPREAD_ACCEPTABLE","COSTS_MATERIAL"]),
        ]
        rows=[
            recheck("a","WAIT",time="2026-10-09T18:08:00Z",codes=["NO_CONFIRMATION"]),
            recheck("a","REJECT",time="2026-10-09T18:40:00Z",
                    record_kind="V2R4_WAIT_EXPIRY_V1",codes=["TTL_EXPIRED_NO_TRIGGER"]),
            recheck("b","REJECT",codes=["REMAINING_MOVE_UNVERIFIED"]),
            recheck("orphan","REJECT",codes=["ORPHAN"]),
        ]
        report=module.describe_cohort(src,rows,now=NOW)
        self.assertEqual(report["unique_initial"],4)
        self.assertEqual(report["initial_counts"],Counter({"WAIT":3,"REJECT":1}))
        self.assertEqual(report["recheck_event_count"],4)
        self.assertEqual(report["distinct_recheck_candidate_ids"],3)
        self.assertEqual(report["matched_initial_WAIT_ids_with_recheck"],2)
        self.assertEqual(report["orphan_recheck_ids"],1)
        self.assertEqual(report["latest_matched_WAIT_states"],Counter({"REJECT":2}))
        self.assertEqual(report["WAIT_ids_without_recheck"],1)
        self.assertEqual(report["WAIT_due_no_recheck"],1)
        self.assertEqual(report["latest_matched_WAIT_codes"]["TTL_EXPIRED_NO_TRIGGER"],1)
        self.assertEqual(report["initial_codes"]["WAIT"]["PAIR_ONLINE"],1)
        self.assertIn("PAIR_ONLINE",report["positive_reason_codes"])
        self.assertEqual(report["missing_structured_entry_provenance"],4)
        self.assertEqual(report["WAIT_watch_metrics"]["spread_pct"],3)
        self.assertEqual(report["pair_6h_episodes"],1)
        self.assertEqual(report["repeat_events_inside_pair_6h"],3)

    def test_initial_duplicates_cannot_inflate_denominator(self):
        cases=[initial("x","REJECT"), initial("x","REJECT"), initial("bad","WAIT")]
        cases[-1].pop("decision")
        report=module.describe_cohort(cases,[],now=NOW)
        self.assertEqual(report["unique_initial"],1)
        self.assertEqual(report["invalid_or_duplicate_initial"],2)

    def test_reading_filters_foreign_series_and_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/"ok.json").write_text(json.dumps(initial("y","REJECT")),encoding="utf-8")
            (folder/"foreign.json").write_text(json.dumps({"series_id":"OTHER"}),encoding="utf-8")
            (folder/"broken.json").write_text("{",encoding="utf-8")
            records,bad=module.read_snapshots(folder,SERIES)
            self.assertEqual(len(records),1)
            self.assertEqual(bad,1)

    def test_full_command_never_mutates_files_or_accepts_legacy_series(self):
        with tempfile.TemporaryDirectory() as d:
            app=Path(d)/module.EXPECTED_APP
            app.mkdir()
            (app/"paper_runtime_control.json").write_text(json.dumps({
                "series_id":SERIES,"paper_only":True,"real_money_actions_enabled":False
            }))
            decisions=app/"paper_decisions";decisions.mkdir()
            (decisions/"one.json").write_text(json.dumps(initial("a","WAIT")))
            before={p.relative_to(app).as_posix():p.read_bytes() for p in app.rglob("*") if p.is_file()}
            self.assertEqual(module.run(app,SERIES),0)
            after={p.relative_to(app).as_posix():p.read_bytes() for p in app.rglob("*") if p.is_file()}
            self.assertEqual(before,after)
            with self.assertRaises(ValueError):
                module.run(app,"PAPER-V2R4-20261007T184255Z")
            with self.assertRaises(ValueError):
                module.run(app.parent/"v2r4-paper-app",SERIES)

if __name__=="__main__":
    unittest.main()
