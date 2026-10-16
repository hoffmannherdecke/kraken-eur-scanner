"""Only tempdir/no-network V3 paper fence lane contract for existing V2R4 CloudSync.

No original Mini-PC, Supabase, credentials, process or real scheduled Task.
Synthetic marker hashes here are NOT source pins, release evidence or CAS proof.
"""
import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "v2r4_paper_cloud_sync_fence_contract",ROOT/"tools/v2r4-paper-cloud-sync.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fence(phase="ARMED"):
    return {
        "kind":"V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1",
        "phase":phase,
        "predecessor_series_id":"PAPER-V2R4-20261009T110135Z",
        "task_names":[
            "CryptoMiniPC-V2R4PaperCandidates",
            "CryptoMiniPC-V2R4PaperWait",
        ],
        "proposed_successor_series_id":"PAPER-V3-20261016T123456Z",
        "proposed_v3_repo_sha":"a"*40,
        "proposed_v3_bundle_sha256":"b"*64,
        "proposed_v3_strategy_sha256":"c"*64,
        "paper_only":True,
        "orders_enabled":False,
        "real_money_actions":False,
        "persistent_until_explicit_owner_release":True,
    }


class OriginalCloudSyncV3PrecommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"State").mkdir()
        self.args=argparse.Namespace(
            trading_root=self.root,app_root=self.root/"FauxPaperState",
            paper_state_dir=self.root/"State",
            endpoint="https://never-sent.example.invalid",
        )
        self.marker=self.root/"State/v3-experimental-paper-old-intake-fence.json"
        self.posts=[]

    def put(self,data):
        self.marker.write_text(json.dumps(data),encoding="utf-8")

    def run_synthetic_old_sync(self):
        def post(_endpoint,_token,packet,**kwargs):
            self.posts.append(packet)
            return {"ok":True,"accepted_candidates":1,"accepted_trades":0}
        fake_collect=lambda _app: (
            {"series_id":"PAPER-V2R4-20261009T110135Z",
             "strategy_revision":"V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"},
            [{"candidate_id":"OLD-PENDING","series_id":"PAPER-V2R4-20261009T110135Z",
              "followup":{"status":"PENDING"}}],
            []
        )
        with mock.patch.object(module,"load_token",return_value="synthetic"*4), \
             mock.patch.object(module,"post",side_effect=post), \
             mock.patch.object(module,"collect",side_effect=fake_collect), \
             mock.patch.object(module,"dispatch_alerts_if_needed",return_value=None):
            return module.run_once(self.args)

    def test_normal_legacy_sync_without_fence(self):
        result=self.run_synthetic_old_sync()
        self.assertEqual(result["status"],"HEALTHY")
        self.assertEqual(result["v3_fence_cloud_sync_lane"],"ACTIVE_ORIGINAL")
        self.assertEqual(result["v3_fence_precommit_phase"],None)
        self.assertEqual(len(self.posts),1)
        self.assertEqual(self.posts[0]["action"],"sync")

    def test_armed_and_quiesced_keep_old_series_sync_until_real_cas(self):
        for phase in ("ARMED","QUIESCED"):
            with self.subTest(phase=phase):
                with tempfile.TemporaryDirectory() as d:
                    # Fresh state ensures one synthetic batch for each phase.
                    self.args.paper_state_dir=Path(d)
                    self.put(fence(phase))
                    self.posts.clear()
                    result=self.run_synthetic_old_sync()
                    self.assertEqual(result["status"],"HEALTHY")
                    self.assertEqual(result["v3_fence_cloud_sync_lane"],"PRECOMMIT_ORIGINAL")
                    self.assertEqual(result["v3_fence_precommit_phase"],phase)
                    self.assertEqual(len(self.posts),1)
                    self.assertEqual(self.posts[0]["action"],"sync")
                    self.assertEqual(self.posts[0]["series_id"],
                                     "PAPER-V2R4-20261009T110135Z")

    def test_committed_switches_to_existing_aftercare_only(self):
        self.put(fence("CLOUD_COMMITTED"))
        with mock.patch.object(module,"run_closed_aftercare_once",
                               return_value={"status":"FIXTURE_ONLY"}) as closed, \
             mock.patch.object(module,"post",side_effect=AssertionError(
                 "old series relay cannot run after committed")):
            self.assertEqual(module.run_once(self.args)["status"],"FIXTURE_ONLY")
            closed.assert_called_once_with(self.args)

    def test_invalid_fence_has_no_cloud_request_and_no_normal_fallback(self):
        changes=[
            ("wrong_kind",{"kind":"INVALID"}),
            ("wrong_phase",{"phase":"CAS_INVOKED"}),
            ("wrong_predecessor",{"predecessor_series_id":"PAPER-V2R4-OBSOLETE"}),
            ("missing_task",{"task_names":["CryptoMiniPC-V2R4PaperWait"]}),
            ("duplicate_task",{"task_names":["CryptoMiniPC-V2R4PaperWait"]*2}),
            ("extra_protected_task",{"task_names":["CryptoMiniPC-V2R4PaperCandidates",
                                                   "CryptoMiniPC-V2R4PaperLifecycle"]}),
            ("wrong_strategy_sha",{"proposed_v3_strategy_sha256":"no"}),
            ("bad_successor",{"proposed_successor_series_id":"PAPER-V3/INVALID"}),
            ("real_money",{"real_money_actions":True}),
            ("orders",{"orders_enabled":True}),
            ("paper_only_disabled",{"paper_only":False}),
            ("persistent_false",{"persistent_until_explicit_owner_release":False}),
        ]
        for label,patch in changes:
            with self.subTest(label=label):
                self.put(fence()|patch)
                self.posts.clear()
                with mock.patch.object(module,"post",side_effect=AssertionError(
                        "no HTTP request allowed for invalid marker")), \
                     mock.patch.object(module,"collect",side_effect=AssertionError(
                        "no original relay collection for invalid marker")):
                    res=module.run_once(self.args)
                self.assertEqual(res["status"],"DEGRADED")
                self.assertIn("V3_FENCE_INVALID_FAIL_CLOSED",res["detail"])
                self.assertEqual(self.posts,[])

    def test_malformed_marker_and_conflicting_maintenance_fail_closed(self):
        self.marker.write_text("{invalid json",encoding="utf-8")
        self.assertEqual(module.run_once(self.args)["status"],"DEGRADED")
        self.put(fence())
        technical=self.root/"State/v2r4-technical-cutover-maintenance.json"
        technical.write_text("{}",encoding="utf-8")
        self.assertEqual(module.run_once(self.args)["status"],"DEGRADED")
        self.assertEqual(self.posts,[])

    def test_marker_cannot_be_a_directory(self):
        self.marker.mkdir()
        result=module.run_once(self.args)
        self.assertEqual(result["status"],"DEGRADED")
        self.assertIn("V3_FENCE_INVALID_FAIL_CLOSED",result["detail"])


if __name__=="__main__":
    unittest.main()
