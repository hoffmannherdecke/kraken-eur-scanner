import argparse
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


def load_helper():
    path=Path("tools/v2r4-real-altrady-release-smoke.py")
    spec=importlib.util.spec_from_file_location("v2r4_real_altrady_release_smoke", path)
    module=importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class V2R4RealAltradySmokeFixtureTests(unittest.TestCase):
    def test_prepare_emits_canonical_candidate_identity(self):
        helper=load_helper()
        now=datetime.now(timezone.utc)
        row={
            "received_by_minipc_at_utc":now.isoformat().replace("+00:00","Z"),
            "event":{"id":"evt-test","symbol":"XXBTZEUR"},
        }
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            args=argparse.Namespace(
                real_log=root/"unused.jsonl",
                max_age_minutes=30.0,
                root=root/"case",
                code_root=Path(".").resolve(),
            )
            with patch.object(helper,"read_latest_real_event",return_value=(row,now,0.0)), \
                 patch.object(helper,"map_symbol",return_value=("XXBTZEUR","XBTEUR","XBT/EUR")), \
                 patch.object(helper,"get_json",return_value={"result":{"XXBTZEUR":{"c":["75000.0"]}}}), \
                 redirect_stdout(io.StringIO()):
                rc=helper.prepare(args)
            self.assertEqual(rc,0)
            candidates=list((args.root/"candidates").glob("*.json"))
            self.assertEqual(len(candidates),1)
            candidate=json.loads(candidates[0].read_text("utf-8"))
            self.assertEqual(candidate["source_scanner_run_id"],0)
            self.assertTrue(candidate["candidate_id"].endswith("-XBT-EUR-r0"))
            self.assertEqual(candidates[0].stem,candidate["candidate_id"])
            self.assertEqual(
                candidate["queue_id"],
                f"0:XBT-EUR:{candidate['event_ts']}",
            )


if __name__=="__main__":
    unittest.main()
