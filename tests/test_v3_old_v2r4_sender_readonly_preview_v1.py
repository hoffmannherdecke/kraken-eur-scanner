"""Genuine existing V2R4 sender's future closed-original preview: offline only."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"tools/v2r4-paper-cloud-sync.py"
SPEC=importlib.util.spec_from_file_location("v2r4_paper_cloud_sync_preview",SCRIPT)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
OLD="PAPER-V2R4-20261009T110135Z"
V3="PAPER-V3-20261013T120012Z"
SHA="a"*40
CUT="2026-10-13T12:00:12Z"


def original():
    control={"series_id":OLD,"strategy_revision":
             "V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION",
             "paper_only":True,"real_money_actions_enabled":False}
    decision={"candidate_id":"O-C1","series_id":OLD,"pair":"XBT/EUR",
              "evaluated_at_utc":"2026-10-13T11:30:00Z",
              "real_money_actions_enabled":False,
              "decision":{"decision":"REJECT"}}
    follow={"kind":"PAPER_FOLLOWUP_V2","series_id":OLD,"candidate_id":"O-C1",
            "pair":"XBT/EUR","updated_at_utc":"2026-10-13T12:20:00Z",
            "horizons":{"60":{"complete":True}}}
    candidate={"candidate_id":"O-C1","series_id":OLD,"pair":"XBT/EUR",
               "decision":"REJECT","evaluated_at":decision["evaluated_at_utc"],
               "followup":follow,
               "payload":{"decision":decision,"followup":follow,"recheck":None}}
    trade={"candidate_id":"O-T1","series_id":OLD,"pair":"ETH/EUR",
           "status":"CLOSED","opened_at":"2026-10-13T10:30:00Z",
           "closed_at":"2026-10-13T12:30:00Z",
           "net_pnl_eur":0.25,"net_return_pct":0.5,
           "payload":{"real_money_actions_enabled":False,
                      "exit":{"closed_at_utc":"2026-10-13T12:30:00Z"}}}
    return control,candidate,trade


class ClosedOriginalSenderPreview(unittest.TestCase):
    def plan(self,control,candidates,trades,**kwargs):
        params={"old_series_id":OLD,"future_v3_series_id":V3,
                "old_release_sha":SHA,"cutover_at_utc":CUT}
        params.update(kwargs)
        return MOD.closed_original_readonly_preview(
            control,candidates,trades,**params)

    def test_canonical_old_followups_and_terminal_trade_are_only_previewed(self):
        control,candidate,trade=original()
        before=copy.deepcopy((control,candidate,trade))
        plan=self.plan(control,[candidate],[trade])
        self.assertEqual(plan["status"],"REVIEW_ONLY_NOT_ACTIVATED")
        self.assertEqual(plan["candidate_followup_count"],1)
        self.assertEqual(plan["pending_unstamped_followups_not_promoted"],0)
        self.assertEqual(plan["old_terminal_trade_count"],1)
        self.assertEqual(plan["bounded_batches"],2)
        self.assertTrue(all(len(x["candidates"])<=20 and len(x["trades"])<=20
                            for x in plan["batches"]))
        for row in plan["batches"]:
            self.assertEqual(row["action"],"sync_closed_original_followups")
            self.assertEqual(row["expected_old_release_sha"],SHA)
            self.assertEqual(row["expected_active_v3_series_id"],V3)
            self.assertEqual(row["series_id"],OLD)
        self.assertFalse(plan["cloud_updated"])
        self.assertFalse(plan["physical_old_writer_fence_verified"])
        self.assertFalse(plan["cloud_preexisting_originals_verified"])
        self.assertEqual((control,candidate,trade),before)

    def test_never_preview_fresh_original_candidate_or_new_trade(self):
        control,candidate,trade=original()
        fresh=copy.deepcopy(candidate)
        fresh["candidate_id"]="FUTURE-CANDIDATE"
        fresh["evaluated_at"]="2026-10-13T12:01:00Z"
        fresh["followup"]["candidate_id"]="FUTURE-CANDIDATE"
        new_trade=copy.deepcopy(trade)
        new_trade["opened_at"]="2026-10-13T12:04:00Z"
        new_trade["candidate_id"]="NEW-TRADE"
        trade["status"]="OPEN"
        plan=self.plan(control,[fresh,candidate],[new_trade,trade])
        self.assertEqual(plan["candidate_followup_count"],1)
        self.assertEqual(plan["old_terminal_trade_count"],0)

    def test_pending_unstamped_old_followup_does_not_poison_entire_preview(self):
        control,candidate,trade=original()
        waiting=copy.deepcopy(candidate)
        waiting["candidate_id"]="O-WAIT-PENDING"
        waiting["decision"]="WAIT"
        waiting["followup"]["candidate_id"]="O-WAIT-PENDING"
        waiting["followup"].pop("updated_at_utc")
        waiting["followup"]["horizons"]={}
        waiting["payload"]["followup"]=waiting["followup"]
        plan=self.plan(control,[candidate,waiting],[trade])
        self.assertEqual(plan["candidate_followup_count"],1)
        self.assertEqual(plan["pending_unstamped_followups_not_promoted"],1)
        self.assertEqual(plan["old_terminal_trade_count"],1)
        for batch in plan["batches"]:
            self.assertTrue(all(x["candidate_id"]!="O-WAIT-PENDING"
                                for x in batch["candidates"]))
        # Nonempty time-window evidence with missing original event time
        # is contradictory, not a reason to invent a timestamp.
        waiting["followup"]["horizons"]={"60":{"complete":True}}
        with self.assertRaisesRegex(ValueError,"unstamped nonempty"):
            self.plan(control,[candidate,waiting],[trade])

    def test_wrong_old_runtime_or_future_id_fails_closed(self):
        control,candidate,trade=original()
        for key,val in (("series_id","PAPER-V2R4-20261007T184255Z"),
                        ("real_money_actions_enabled",True),
                        ("paper_only",False),
                        ("strategy_revision","V3-WRONG")):
            with self.subTest(key=key):
                wrong=dict(control,**{key:val})
                with self.assertRaises(ValueError):
                    self.plan(wrong,[candidate],[trade])
        for params in ({"old_release_sha":"0"},
                       {"future_v3_series_id":OLD},
                       {"cutover_at_utc":"not-a-date"}):
            with self.subTest(params=params),self.assertRaises(ValueError):
                self.plan(control,[candidate],[trade],**params)

    def test_cli_preview_does_not_read_secrets_write_heartbeat_or_call_cloud(self):
        control,candidate,trade=original()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            app=root/"app"
            for name in ("paper_decisions","paper_followups","paper_positions"):
                (app/name).mkdir(parents=True)
            (app/"paper_runtime_control.json").write_text(json.dumps(control))
            (app/"paper_decisions"/"decision.json").write_text(
                json.dumps(candidate["payload"]["decision"]))
            (app/"paper_followups"/"followup.json").write_text(
                json.dumps(candidate["followup"]))
            (app/"paper_positions"/"trade.json").write_text(
                json.dumps({"candidate_id":trade["candidate_id"],
                            "series_id":OLD,"pair":"ETH/EUR","status":"CLOSED",
                            "opened_at_utc":trade["opened_at"],
                            "exit":{"closed_at_utc":trade["closed_at"],
                                    "net_pnl_eur":trade["net_pnl_eur"],
                                    "net_return_pct":trade["net_return_pct"]},
                            "real_money_actions_enabled":False}))
            args=[sys.executable,str(SCRIPT),"--app-root",str(app),
                  "--trading-root",str(root/"uncreated"),
                  "--preview-closed-original",
                  "--preview-old-series-id",OLD,
                  "--preview-new-v3-series-id",V3,
                  "--preview-old-release-sha",SHA,
                  "--preview-cutover-at-utc",CUT,
                  "--endpoint","http://127.0.0.1:9/must-never-contact"]
            result=subprocess.run(args,capture_output=True,text=True,timeout=12)
            self.assertEqual(result.returncode,0,result.stderr)
            out=json.loads(result.stdout)
            self.assertEqual(out["status"],"REVIEW_ONLY_NOT_ACTIVATED")
            self.assertEqual(out["candidate_followup_count"],1)
            self.assertEqual(out["old_terminal_trade_count"],1)
            self.assertNotIn("batches",out)
            self.assertFalse((root/"uncreated").exists())



class ClosedOriginalSenderOfflineCutover(unittest.TestCase):
    def fixture(self,root,phase='CLOUD_COMMITTED'):
        control,candidate,trade=original()
        control['release_repo_sha']=SHA
        app=root/'app'
        for name in ('paper_decisions','paper_followups','paper_positions'):
            (app/name).mkdir(parents=True)
        (app/'paper_runtime_control.json').write_text(json.dumps(control))
        (app/'paper_decisions'/'candidate.json').write_text(
            json.dumps(candidate['payload']['decision']))
        (app/'paper_followups'/'follow.json').write_text(
            json.dumps(candidate['followup']))
        (app/'paper_positions'/'trade.json').write_text(json.dumps({
            'candidate_id':trade['candidate_id'],'series_id':OLD,
            'pair':'ETH/EUR','status':'CLOSED',
            'opened_at_utc':trade['opened_at'],
            'exit':{'closed_at_utc':trade['closed_at'],
                    'net_pnl_eur':trade['net_pnl_eur'],
                    'net_return_pct':trade['net_return_pct']},
            'real_money_actions_enabled':False}))
        (root/'Secrets').mkdir()
        (root/'Secrets/shadow-evidence-token.txt').write_text('a'*32)
        (root/'Secrets/minipc-status-token.txt').write_text('b'*32)
        if phase is not None:
            (root/'State').mkdir(exist_ok=True)
            marker={'kind':'V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1',
                    'phase':phase,'predecessor_series_id':OLD,
                    'proposed_successor_series_id':V3,
                    'proposed_v3_repo_sha':SHA,
                    'proposed_v3_bundle_sha256':'a'*64,
                    'proposed_v3_strategy_sha256':'b'*64,
                    'paper_only':True,'orders_enabled':False,
                    'real_money_actions':False,
                    'persistent_until_explicit_owner_release':True,
                    'task_names':['CryptoMiniPC-V2R4PaperCandidates',
                                  'CryptoMiniPC-V2R4PaperWait']}
            (root/'State/v3-experimental-paper-old-intake-fence.json').write_text(
                json.dumps(marker))
        return type('Args',(),{'trading_root':root,'app_root':app,
                              'paper_state_dir':None,'endpoint':'http://127.0.0.1:9/no-network'})()

    @staticmethod
    def original_ack(endpoint,token,packet,**kwargs):
        if packet['action']=='sync':
            return {'ok':True,'action':'sync',
                    'accepted_candidates':len(packet['candidates']),
                    'accepted_trades':len(packet['trades'])}
        assert len(token)>=24 and len(kwargs.get('second_token') or '')>=24
        return {'ok':True,'action':'sync_closed_original_followups',
                'accepted_candidates':len(packet['candidates']),
                'accepted_trades':len(packet['trades']),
                'unchanged_replays':0,'paper_only':True,
                'real_money_actions':False,'new_v2r4_intake_allowed':False}

    def test_no_marker_keeps_existing_active_sender(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d),phase=None)
            with patch.object(MOD,'post',side_effect=self.original_ack) as post, \
                 patch.object(MOD,'dispatch_alerts_if_needed',
                              return_value={'status':'NONE_PENDING'}):
                result=MOD.run_once(args)
            self.assertEqual(result['status'],'HEALTHY')
            self.assertNotIn('mode',result)
            self.assertTrue(post.called)
            self.assertTrue(all(c.args[2]['action']=='sync'
                                for c in post.call_args_list))
            self.assertFalse((args.trading_root/'State/v2r4-paper-closed-aftercare-state.json').exists())

    def test_arming_marker_blocks_any_sync_or_network(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d),phase='ARMED')
            with patch.object(MOD,'post') as post:
                result=MOD.run_once(args)
            self.assertEqual(result['status'],'DEGRADED')
            self.assertEqual(result['mode'],'CLOSED_ORIGINAL_AFTERCARE')
            post.assert_not_called()

    def test_committed_marker_sends_only_originals_and_replays_none(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d))
            with patch.object(MOD,'post',side_effect=self.original_ack) as post:
                first=MOD.run_once(args)
                second=MOD.run_once(args)
            self.assertEqual(first['status'],'HEALTHY')
            self.assertEqual(first['accepted_original_updates'],2)
            self.assertEqual(first['batches'],2)
            self.assertEqual(second['status'],'HEALTHY')
            self.assertEqual(second['batches'],0)
            self.assertEqual(post.call_count,2)
            self.assertTrue(all(c.args[2]['action']=='sync_closed_original_followups'
                                for c in post.call_args_list))
            self.assertTrue(all(c.args[2]['expected_active_v3_series_id']==V3
                                for c in post.call_args_list))
            state=json.loads((args.trading_root/'State/v2r4-paper-closed-aftercare-state.json').read_text())
            self.assertEqual(len(state['sent']),2)

    def test_pre_cutover_active_ack_deduplicates_closed_replays(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d))
            _,candidates,trades=MOD.collect(args.app_root)
            already={}
            for prefix,rows in (('candidate',candidates),('trade',trades)):
                for row in rows:
                    already[f"{prefix}:{row['candidate_id']}"]=MOD.row_hash(row)
            state=args.trading_root/'State/v2r4-paper-cloud-sync-state.json'
            state.write_text(json.dumps({'schema_version':1,'sent':already}))
            with patch.object(MOD,'post') as post:
                result=MOD.run_once(args)
            self.assertEqual(result['status'],'HEALTHY')
            self.assertEqual(result['batches'],0)
            post.assert_not_called()

    def test_cloud_failure_never_advances_cursor(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d))
            cursor=args.trading_root/'State/v2r4-paper-closed-aftercare-state.json'
            with patch.object(MOD,'post',side_effect=RuntimeError('offline failure')):
                failed=MOD.run_once(args)
            self.assertEqual(failed['status'],'DEGRADED')
            self.assertFalse(cursor.exists())
            with patch.object(MOD,'post',side_effect=self.original_ack):
                recovered=MOD.run_once(args)
            self.assertEqual(recovered['status'],'HEALTHY')
            self.assertEqual(recovered['accepted_original_updates'],2)

    def test_closed_mode_refuses_late_old_wait_recheck(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d))
            rechecks=args.app_root/'paper_rechecks'
            rechecks.mkdir()
            rechecks.joinpath('late.json').write_text(json.dumps({
                'series_id':OLD,'candidate_id':'O-C1',
                'recheck_completed_at_utc':'2026-10-13T12:20:00Z',
                'paper_only':True,'real_money_actions_enabled':False,
                'decision':{'decision':'REJECT'}}))
            with patch.object(MOD,'post') as post:
                result=MOD.run_once(args)
            self.assertEqual(result['status'],'DEGRADED')
            post.assert_not_called()

    def test_aftercare_rejects_new_old_intake_and_unsafe_control(self):
        with tempfile.TemporaryDirectory() as d:
            args=self.fixture(Path(d))
            p=args.app_root/'paper_runtime_control.json'
            bad=json.loads(p.read_text());bad['real_money_actions_enabled']=True
            p.write_text(json.dumps(bad))
            with patch.object(MOD,'post') as post:
                out=MOD.run_once(args)
            self.assertEqual(out['status'],'DEGRADED')
            post.assert_not_called()
            bad['real_money_actions_enabled']=False
            p.write_text(json.dumps(bad))
            decision_path=args.app_root/'paper_decisions'/'candidate.json'
            decision=json.loads(decision_path.read_text())
            decision['evaluated_at_utc']='2026-10-13T12:01:00Z'
            decision_path.write_text(json.dumps(decision))
            with patch.object(MOD,'post') as post:
                late=MOD.run_once(args)
            self.assertEqual(late['status'],'DEGRADED')
            post.assert_not_called()


if __name__=="__main__":
    unittest.main()
