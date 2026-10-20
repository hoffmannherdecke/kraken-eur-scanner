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

    def test_armed_and_quiesced_hold_relay_without_http_until_real_cas(self):
        for phase in ("ARMED","QUIESCED"):
            with self.subTest(phase=phase):
                self.put(fence(phase))
                self.posts.clear()
                with mock.patch.object(module,"post",side_effect=AssertionError(
                         "precommit must not contact cloud")), \
                     mock.patch.object(module,"collect",side_effect=AssertionError(
                         "precommit must not collect pending old rows")):
                    result=module.run_once(self.args)
                self.assertEqual(result["status"],"HEALTHY")
                self.assertEqual(result["mode"],"V3_PRECOMMIT_NO_NETWORK_HOLD")
                self.assertEqual(result["v3_fence_cloud_sync_lane"],"PRECOMMIT_ORIGINAL")
                self.assertEqual(result["v3_fence_precommit_phase"],phase)
                self.assertTrue(result["cloud_sync_intentionally_paused"])
                self.assertTrue(result["pending_originals_preserved"])
                self.assertFalse(result["cloud_updated"])
                self.assertEqual(len(self.posts),0)
                self.assertFalse((self.root/"State/v2r4-paper-closed-aftercare-state.json").exists())

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


class ClosedOriginalAftercareFileE2ETests(unittest.TestCase):
    """Real temporary legacy files -> post-CAS aftercare -> bounded Edge ACKs.

    Only the HTTP relay is mocked; real collect, preview, hash marks, fence,
    state persistence and subsequent restart/retry paths run together.
    This is NOT a physical CAS, a V3 release or a live Windows writer.
    """

    OLD="PAPER-V2R4-20261009T110135Z"
    NEW="PAPER-V3-20261016T123456Z"

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.app=self.root/"FauxPaperState"
        for name in ("State","Secrets"):
            (self.root/name).mkdir()
        for name in ("paper_decisions","paper_followups","paper_positions"):
            (self.app/name).mkdir(parents=True)
        self.args=argparse.Namespace(
            trading_root=self.root,app_root=self.app,
            paper_state_dir=self.root/"State",
            endpoint="https://no-network.example.invalid",
        )
        self.aftercare_state=self.root/"State/v2r4-paper-closed-aftercare-state.json"
        self.write(self.app/"paper_runtime_control.json",{
            "series_id":self.OLD,
            "strategy_revision":"V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
            "release_repo_sha":"d"*40,
            "paper_only":True,
            "real_money_actions_enabled":False,
        })
        self.write(self.root/"State/v3-experimental-paper-old-intake-fence.json",
                   fence("CLOUD_COMMITTED"))
        (self.root/"Secrets/minipc-status-token.txt").write_text("x"*32)
        self.write(self.app/"paper_decisions/old-reject.json",{
            "candidate_id":"OLD-REJECT","series_id":self.OLD,
            "pair":"XBT/EUR","evaluated_at_utc":"2026-10-15T12:00:00Z",
            "decision":{"decision":"REJECT","real_money_actions_enabled":False},
        })
        self.followup={
            "kind":"PAPER_FOLLOWUP_V2","series_id":self.OLD,
            "candidate_id":"OLD-REJECT","pair":"XBT/EUR",
            "updated_at_utc":"2026-10-17T14:00:00Z",
            "horizons":{"6h":{"status":"COMPLETE"}},
        }
        self.write(self.app/"paper_followups/old-reject.json",self.followup)
        self.write(self.app/"paper_positions/old-exit.json",{
            "candidate_id":"OLD-EXIT","series_id":self.OLD,"pair":"XBT/EUR",
            "status":"CLOSED","opened_at_utc":"2026-10-15T13:00:00Z",
            "real_money_actions_enabled":False,
            "exit":{"closed_at_utc":"2026-10-17T16:00:00Z",
                    "net_pnl_eur":-0.2},
        })

    @staticmethod
    def write(path,value):
        path.write_text(json.dumps(value,sort_keys=True),encoding="utf-8")

    @staticmethod
    def good_ack(_url,_token,packet,**kwargs):
        assert kwargs.get("second_token")=="x"*32
        assert packet["action"]=="sync_closed_original_followups"
        assert packet["series_id"]=="PAPER-V2R4-20261009T110135Z"
        assert packet["expected_active_v3_series_id"]=="PAPER-V3-20261016T123456Z"
        return {
            "action":"sync_closed_original_followups",
            "paper_only":True,"real_money_actions":False,
            "new_v2r4_intake_allowed":False,
            "accepted_candidates":len(packet["candidates"]),
            "accepted_trades":len(packet["trades"]),
            "unchanged_replays":0,
        }

    def tick(self,relay):
        with mock.patch.object(module,"load_token",return_value="s"*32), \
             mock.patch.object(module,"post",side_effect=relay) as http:
            result=module.run_once(self.args)
            return result,http.call_args_list

    def test_real_file_aftercare_post_ack_persist_no_replay_and_late_followup(self):
        first,calls=self.tick(self.good_ack)
        self.assertEqual(first["status"],"HEALTHY")
        self.assertEqual(first["mode"],"CLOSED_ORIGINAL_AFTERCARE")
        self.assertEqual(first["batches"],2)
        self.assertEqual(first["accepted_original_updates"],2)
        self.assertEqual(len(calls),2)
        self.assertEqual(sorted((
            len(c.args[2]["candidates"]),len(c.args[2]["trades"]))
            for c in calls),[(0,1),(1,0)])
        marks=json.loads(self.aftercare_state.read_text())["sent"]
        self.assertEqual(set(marks),{"candidate:OLD-REJECT","trade:OLD-EXIT"})
        self.assertEqual(set(len(v) for v in marks.values()),{64})

        second,calls=self.tick(lambda *_a,**_k:
            self.fail("unchanged aftercare must never replay to Cloud"))
        self.assertEqual(second["status"],"HEALTHY")
        self.assertEqual(second["batches"],0)
        self.assertEqual(calls,[])

        # A genuine later old-series 24h followup remains eligible AFTER CAS.
        # It is a new hash of the same original candidate, not a new BUY.
        updated={**self.followup,"updated_at_utc":"2026-10-18T15:00:00Z",
                 "horizons":{"6h":{"status":"COMPLETE"},
                             "24h":{"status":"COMPLETE"}}}
        self.write(self.app/"paper_followups/old-reject.json",updated)
        third,calls=self.tick(self.good_ack)
        self.assertEqual(third["status"],"HEALTHY")
        self.assertEqual(third["batches"],1)
        self.assertEqual(len(calls),1)
        self.assertEqual(len(calls[0].args[2]["candidates"]),1)
        self.assertEqual(len(calls[0].args[2]["trades"]),0)
        new_marks=json.loads(self.aftercare_state.read_text())["sent"]
        self.assertNotEqual(new_marks["candidate:OLD-REJECT"],
                            marks["candidate:OLD-REJECT"])
        self.assertEqual(new_marks["trade:OLD-EXIT"],marks["trade:OLD-EXIT"])

    def test_denied_or_ambiguous_ack_never_advances_sent_hashes(self):
        def malformed(_url,_token,packet,**_):
            good=self.good_ack(_url,_token,packet,second_token="x"*32)
            return {**good,"new_v2r4_intake_allowed":True}
        denied,calls=self.tick(malformed)
        self.assertEqual(denied["status"],"DEGRADED")
        self.assertEqual(len(calls),1)
        self.assertFalse(self.aftercare_state.exists())

        failed,calls=self.tick(lambda *_a,**_k:
            (_ for _ in ()).throw(TimeoutError("unknown Cloud commit ACK")))
        self.assertEqual(failed["status"],"DEGRADED")
        self.assertEqual(len(calls),1)
        self.assertFalse(self.aftercare_state.exists())
        # Retry is idempotent only at the independently checked Edge; the
        # local hash marker must not be advanced on a missing/unsafe ACK.
        recovered,calls=self.tick(self.good_ack)
        self.assertEqual(recovered["status"],"HEALTHY")
        self.assertEqual(recovered["batches"],2)
        self.assertEqual(len(calls),2)

    def test_old_intake_after_cutoff_and_cas_uncertainty_never_send(self):
        first,_=self.tick(self.good_ack)
        self.assertEqual(first["status"],"HEALTHY")
        before=self.aftercare_state.read_bytes()
        # The already committed Cloud series can retain old followups, but
        # NEVER accept new candidate intake after its original cutoff.
        self.write(self.app/"paper_decisions/invalid-new-old.json",{
            "candidate_id":"UNLAWFUL-NEW-OLD","series_id":self.OLD,
            "pair":"ETH/EUR","evaluated_at_utc":"2026-10-17T00:00:00Z",
            "decision":{"decision":"REJECT","real_money_actions_enabled":False},
        })
        blocked,calls=self.tick(lambda *_a,**_k:
            self.fail("postcutover old intake must be held before Cloud"))
        self.assertEqual(blocked["status"],"DEGRADED")
        self.assertEqual(calls,[])
        self.assertEqual(self.aftercare_state.read_bytes(),before)
        (self.app/"paper_decisions/invalid-new-old.json").unlink()

        # Unknown/attempted CAS is never interpreted as a committed switch,
        # and must not quietly fall back to the original active relay.
        self.write(self.root/"State/v3-experimental-paper-old-intake-fence.json",
                   fence("CAS_INVOKED"))
        unknown,calls=self.tick(lambda *_a,**_k:
            self.fail("ambiguous CAS must prevent all relay requests"))
        self.assertEqual(unknown["status"],"DEGRADED")
        self.assertEqual(calls,[])
        self.assertEqual(self.aftercare_state.read_bytes(),before)

    def test_unstamped_pending_horizon_is_not_fabricated_as_mature(self):
        self.write(self.app/"paper_decisions/pending.json",{
            "candidate_id":"OLD-PENDING","series_id":self.OLD,
            "pair":"ADA/EUR","evaluated_at_utc":"2026-10-15T16:00:00Z",
            "decision":{"decision":"WAIT","real_money_actions_enabled":False},
        })
        self.write(self.app/"paper_followups/pending.json",{
            "kind":"PAPER_FOLLOWUP_V2","series_id":self.OLD,
            "candidate_id":"OLD-PENDING","pair":"ADA/EUR","horizons":{},
        })
        result,calls=self.tick(self.good_ack)
        self.assertEqual(result["status"],"HEALTHY")
        self.assertEqual(result["pending_unstamped_followups"],1)
        self.assertEqual(result["accepted_original_updates"],2)
        self.assertEqual(len(calls),2)
        marks=json.loads(self.aftercare_state.read_text())["sent"]
        self.assertNotIn("candidate:OLD-PENDING",marks)


if __name__=="__main__":
    unittest.main()
