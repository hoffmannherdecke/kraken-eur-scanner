import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[1]


def import_script(name, file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TechnicalSuccessorStateIsolation(unittest.TestCase):
    def test_candidate_parser_accepts_distinct_paper_state_path(self):
        import sys
        mod=import_script("cutover_paper_runtime","v2r4-paper-local-runtime.py")
        with tempfile.TemporaryDirectory() as td:
            new=Path(td)/"successor_state"
            with patch.object(sys,"argv",["prog","--mode","candidates",
                                          "--app-root",str(Path(td)/"new-app"),
                                          "--paper-state-dir",str(new)]):
                parsed=mod.parse_args()
                self.assertEqual(new,parsed.paper_state_dir)

    def test_cloud_sync_never_mutates_legacy_sent_state(self):
        import sys
        mod=import_script("cutover_paper_cloud_sync","v2r4-paper-cloud-sync.py")
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            oldstate=root/"State"/"v2r4-paper-cloud-sync-state.json"
            oldstate.parent.mkdir(parents=True)
            oldstate.write_text('{"schema_version":1,"sent":{"old":"frozen"}}')
            before=oldstate.read_bytes()
            successor=root/"Runtime"/"successor"/"State"
            with patch.object(sys,"argv",[
                "prog","--trading-root",str(root),
                "--app-root",str(root/"Runtime"/"successor"),
                "--paper-state-dir",str(successor),"--once"
            ]):
                args=mod.parse_args()
            control={"series_id":"PAPER-V2R4-NEW","strategy_revision":"V2R4"}
            candidate={
                "candidate_id":"new-only","series_id":control["series_id"],
                "pair":"ETH/EUR","decision":"WAIT","evaluated_at":"2026-10-09T00:00:00Z",
                "payload":{"decision":{"real_money_actions_enabled":False}}
            }
            with patch.object(mod,"load_token",return_value="x"*32),\
                 patch.object(mod,"collect",return_value=(control,[candidate],[])),\
                 patch.object(mod,"post",return_value={"ok":True,"accepted_candidates":1}),\
                 patch.object(mod,"dispatch_alerts_if_needed",return_value={"status":"NONE_PENDING"}):
                result=mod.run_once(args)
            self.assertEqual("HEALTHY",result["status"])
            self.assertEqual(before,oldstate.read_bytes())
            state=json.loads((successor/"v2r4-paper-cloud-sync-state.json").read_text())
            self.assertIn("candidate:new-only",state["sent"])
            self.assertFalse((successor/"v2r4-paper-alert-dispatch-state.json").exists())
            self.assertTrue((root/"State"/"v2r4-paper-cloud-sync-heartbeat.json").exists())


if __name__=="__main__":
    unittest.main()
