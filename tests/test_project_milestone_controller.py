import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('controller', ROOT / 'tools/project_milestone_controller.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)

class MilestoneTests(unittest.TestCase):
    @staticmethod
    def _historic_h3_fixture(state):
        """Synthetic historical running-H3 branch for old contract regression only."""
        active=state["active_strategy"]
        state["strategy_changing_shadow_wip"]["active"]=[{
            "candidate_id":"V3-H3-SHADOW-001",
            "baseline_series_id":active["series_id"],
            "baseline_strategy_revision":active["strategy_revision"],
            "status":"SHADOW_RUNNING",
            "automatic_promotion":False
        }]
        return state


    def test_canonical_state(self):
        state = controller.load_local_state(ROOT)
        self.assertFalse(state['active_strategy']['real_money_actions'])

    def test_dedup(self):
        first = controller.event('H3_FIXED_REVIEW', 'a', 'first')
        second = controller.event('H3_FIXED_REVIEW', 'a', 'second')
        self.assertEqual(first['event_key'], second['event_key'])

    def test_fixture_gates_and_no_action(self):
        import datetime as dt
        import tempfile
        import json
        state = controller.load_local_state(ROOT)
        active = state['active_strategy']
        self._historic_h3_fixture(state)
        paper = dict(series_id=active['technical_rotation_runtime_last_verified']['series_id'], strategy_revision=active['strategy_revision'],
                     fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                     candidate_outcomes=239, completed_trades=0, complete_24h=0,
                     series_age_days=.6, completion_ready=False, intake_should_stop=False)
        h3 = dict(shadow_candidate_id='V3-H3-SHADOW-001',
                  generated_at='2026-10-08T11:50:00Z',
                  payload=dict(baseline_series_id=active['series_id'],
                               baseline_strategy_revision=active['strategy_revision'],
                               orders=False, real_money_actions=False,
                               automatic_extension=False, automatic_promotion=False,
                               minimum_gate_met=False))
        with tempfile.TemporaryDirectory() as directory:
            now = dt.datetime(2026,10,8,12,tzinfo=dt.timezone.utc)
            r = controller.evaluate(state, paper, h3, now, Path(directory))
            self.assertIn('H3:COLLECTING', r['statuses'])
            self.assertFalse(r['strategy_changed'])
            self.assertFalse(r['real_money_actions'])
            paper['completion_ready'] = True
            with self.assertRaises(ValueError):
                controller.evaluate(state, paper, h3, now, Path(directory))
            paper['completion_ready'] = False
            h3['payload']['baseline_series_id'] = 'incorrect'
            with self.assertRaises(ValueError):
                controller.evaluate(state, paper, h3, now, Path(directory))


    def test_h3_fixed_review_reintroduces_second_leg_learning_without_new_automation(self):
        import datetime as dt
        state=controller.load_local_state(ROOT)
        active=state['active_strategy']
        self._historic_h3_fixture(state)
        paper=dict(series_id=active['technical_rotation_runtime_last_verified']['series_id'],strategy_revision=active['strategy_revision'],
                   fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                   candidate_outcomes=1300,completed_trades=0,complete_24h=1300,
                   series_age_days=4,completion_ready=False,intake_should_stop=False)
        now=dt.datetime(2026,10,10,19,0,tzinfo=dt.timezone.utc)
        h3=dict(shadow_candidate_id='V3-H3-SHADOW-001',generated_at='2026-10-10T18:50:00Z',
                payload=dict(baseline_series_id=active['series_id'],
                             baseline_strategy_revision=active['strategy_revision'],
                             orders=False,real_money_actions=False,
                             automatic_promotion=False,automatic_extension=False,
                             minimum_gate_met=True,eligible_matched_candidates=20,
                             distinct_utc_dates=['2026-10-08','2026-10-09'],
                             capture_success_pct=100, intake_should_stop=True,
                             outcome_review_ready=True,causal_decision_divergences=2))
        r=controller.evaluate(state,paper,h3,now,ROOT)
        self.assertIn('V3:EXTENDED_SECOND_LEG_STAGED_FOR_NEXT_REVIEW_NO_AUTO_START',r['statuses'])
        h3_fixed=[x for x in r['events'] if x['kind']=='H3_FIXED_REVIEW']
        self.assertEqual(len(h3_fixed),1)
        self.assertIn('EXTENDED-Zweite-Welle',h3_fixed[0]['detail'])
        self.assertIn('Coin-Daten',h3_fixed[0]['detail'])
        low=[x for x in r['events'] if x['kind']=='PAPER_LOW_TRADES']
        self.assertEqual(len(low),1)
        self.assertIn('V3-EXTENDED-Zweite-Welle',low[0]['detail'])
        self.assertFalse(any(x['kind']=='NEW_CONTROL_DECISION' for x in r['events']))
        self.assertFalse(r['strategy_changed'])
        self.assertFalse(r['orders'])
        self.assertFalse(r['real_money_actions'])



    def test_real_technical_rotation_does_not_restart_72h_strategy_productivity_clock(self):
        import datetime as dt
        state = controller.load_local_state(ROOT)
        a = state['active_strategy']
        technical = a['technical_rotation_runtime_last_verified']
        assert technical['series_id'] == 'PAPER-V2R4-20261009T110135Z'
        paper = dict(
            series_id=technical['series_id'],
            strategy_revision=a['strategy_revision'],
            fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
            candidate_outcomes=172,completed_trades=0,complete_24h=40,
            series_age_days=.35,completion_ready=False,intake_should_stop=False)
        def h3(at):
            return dict(shadow_candidate_id='V3-H3-SHADOW-001',
                        generated_at=at.isoformat(),
                        payload=dict(baseline_series_id=a['series_id'],
                                     baseline_strategy_revision=a['strategy_revision'],
                                     orders=False,real_money_actions=False,
                                     automatic_extension=False,automatic_promotion=False,
                                     minimum_gate_met=False))
        before=dt.datetime(2026,10,10,18,42,54,tzinfo=dt.timezone.utc)
        after=dt.datetime(2026,10,10,18,42,56,tzinfo=dt.timezone.utc)
        early=controller.evaluate(state,paper,h3(before),before,ROOT)
        late=controller.evaluate(state,paper,h3(after),after,ROOT)
        self.assertNotIn('V2R4:LOW_TRADE_REVIEW',early['statuses'])
        self.assertIn('V2R4:LOW_TRADE_REVIEW',late['statuses'])
        self.assertEqual(late['live_technical_series_id'],technical['series_id'])
        self.assertEqual(late['series_id'],a['series_id'])
        self.assertEqual(late['strategy_epoch_started_at_utc'],'2026-10-07T18:42:55Z')
        notices=[x for x in late['events'] if x['kind']=='PAPER_LOW_TRADES']
        self.assertEqual(len(notices),1)
        self.assertIn('72h-STRATEGIEEPOCHEN',notices[0]['detail'])
        self.assertIn('Coin-Evidence-Stufe A',notices[0]['detail'])
        self.assertFalse(any(x['kind']=='NEW_CONTROL_DECISION' for x in late['events']))
        self.assertFalse(late['strategy_changed'])
        self.assertFalse(late['orders'])
        self.assertFalse(late['real_money_actions'])
        paper['series_id']='PAPER-V2R4-UNREVIEWED-20261010'
        with self.assertRaisesRegex(ValueError,'unapproved technical series'):
            controller.evaluate(state,paper,h3(after),after,ROOT)

    def test_archived_predecessor_24h_followups_count_for_early_epoch_review(self):
        import datetime as dt
        state=controller.load_local_state(ROOT)
        a=state['active_strategy']
        t=dt.datetime(2026,10,11,18,0,tzinfo=dt.timezone.utc)
        paper=dict(series_id=a['technical_rotation_runtime_last_verified']['series_id'],
                   strategy_revision=a['strategy_revision'],
                   fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                   candidate_outcomes=1000,completed_trades=0,complete_24h=0,
                   series_age_days=2,completion_ready=False,intake_should_stop=False)
        h3=dict(shadow_candidate_id='V3-H3-SHADOW-001',generated_at=t.isoformat(),
                payload=dict(baseline_series_id=a['series_id'],baseline_strategy_revision=a['strategy_revision'],
                             orders=False,real_money_actions=False,automatic_extension=False,
                             automatic_promotion=False,minimum_gate_met=False))
        r=controller.evaluate(state,paper,h3,t,ROOT)
        self.assertIn('V2R4:LOW_TRADE_REVIEW',r['statuses'])
        self.assertEqual(r['epoch_minimum_complete_24h'],260)
        self.assertEqual(r['epoch_minimum_candidate_outcomes'],2011)
        self.assertEqual(r['epoch_minimum_completed_trades'],0)
        self.assertNotIn('V2R4:FINAL_REVIEW_READY',r['statuses'])


    def test_stale_h3_does_not_block_independent_v2r4_quality_gate(self):
        import datetime as dt
        state=controller.load_local_state(ROOT)
        a=state['active_strategy']
        self._historic_h3_fixture(state)
        now=dt.datetime(2026,10,10,18,44,tzinfo=dt.timezone.utc)
        paper=dict(series_id=a['technical_rotation_runtime_last_verified']['series_id'],
                   strategy_revision=a['strategy_revision'],
                   fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                   candidate_outcomes=250,completed_trades=0,complete_24h=150,
                   series_age_days=1.35,completion_ready=False,intake_should_stop=False)
        h3=dict(shadow_candidate_id='V3-H3-SHADOW-001',
                generated_at='2026-10-09T11:00:03.459542+00:00',
                payload=dict(baseline_series_id=a['series_id'],
                             baseline_strategy_revision=a['strategy_revision'],
                             orders=False,real_money_actions=False,automatic_extension=False,
                             automatic_promotion=False,minimum_gate_met=True,
                             eligible_matched_candidates=24,distinct_utc_dates=['2026-10-08','2026-10-09'],
                             capture_success_pct=99,intake_should_stop=True,
                             outcome_review_ready=True,causal_decision_divergences=20))
        result=controller.evaluate(state,paper,h3,now,ROOT)
        self.assertIn('H3:EVIDENCE_STALE_FIXED_REVIEW_BLOCKED',result['statuses'])
        self.assertIn('V2R4:LOW_TRADE_REVIEW',result['statuses'])
        keys=[x['kind'] for x in result['events']]
        self.assertIn('PAPER_LOW_TRADES',keys)
        self.assertIn('H3_STALE_EVIDENCE',keys)
        self.assertNotIn('H3_FIXED_REVIEW',keys)
        self.assertFalse(result['strategy_changed'])
        self.assertFalse(result['real_money_actions'])
        h3['payload']['automatic_promotion']=True
        with self.assertRaisesRegex(ValueError,'H3 safety invariant'):
            controller.evaluate(state,paper,h3,now,ROOT)



    def test_real_central_state_reports_archived_h3_with_zero_causal_data(self):
        import datetime as dt
        state=controller.load_local_state(ROOT)
        a=state['active_strategy']
        self.assertEqual(state['strategy_changing_shadow_wip']['active'],[])
        paper=dict(series_id=a['technical_rotation_runtime_last_verified']['series_id'],
                   strategy_revision=a['strategy_revision'],
                   fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                   candidate_outcomes=175,completed_trades=0,complete_24h=0,
                   series_age_days=.37,completion_ready=False,intake_should_stop=False)
        now=dt.datetime(2026,10,9,19,55,tzinfo=dt.timezone.utc)
        result=controller.evaluate(state,paper,None,now,ROOT)
        self.assertIn('H3:ARCHIVED_INCOMPLETE_NO_FIXED_REVIEW',result['statuses'])
        self.assertIn('H6:BLOCKED_H3_ARCHIVED_INCOMPLETE_NO_AUTO_START',result['statuses'])
        self.assertNotIn('H3:FIXED_REVIEW_READY',result['statuses'])
        self.assertNotIn('V2R4:LOW_TRADE_REVIEW',result['statuses'])
        self.assertEqual(result['epoch_minimum_candidate_outcomes'],1186)
        self.assertEqual(result['epoch_minimum_complete_24h'],260)
        self.assertTrue(result['epoch_combines_verified_technical_segments'])
        events=[x for x in result['events'] if x['kind']=='H3_ARCHIVED_INCOMPLETE_REVIEW']
        self.assertEqual(len(events),1)
        self.assertFalse(any(x['kind']=='H3_STALE_EVIDENCE' for x in result['events']))
        self.assertFalse(result['orders'])
        self.assertFalse(result['strategy_changed'])
        self.assertFalse(result['real_money_actions'])

    def test_archive_does_not_forge_H3_fixed_review_when_cloud_status_lies(self):
        import datetime as dt
        state=controller.load_local_state(ROOT)
        a=state['active_strategy']
        now=dt.datetime(2026,10,11,19,tzinfo=dt.timezone.utc)
        paper=dict(series_id=a['technical_rotation_runtime_last_verified']['series_id'],
                   strategy_revision=a['strategy_revision'],
                   fasttrack_policy_version='EVIDENCE_DIVERSITY_FASTTRACK_V2',
                   candidate_outcomes=180,completed_trades=0,complete_24h=0,
                   series_age_days=2,completion_ready=False,intake_should_stop=False)
        fake_h3={"shadow_candidate_id":"V3-H3-SHADOW-001",
                  "generated_at":now.isoformat(),
                  "payload":{"baseline_series_id":a['series_id'],
                             "minimum_gate_met":True,"outcome_review_ready":True}}
        result=controller.evaluate(state,paper,fake_h3,now,ROOT)
        self.assertNotIn('H3:FIXED_REVIEW_READY',result['statuses'])
        self.assertNotIn('H3_FIXED_REVIEW',[x['kind'] for x in result['events']])



    def test_future_two_cutdown_rollovers_have_one_economic_epoch_without_double_count(self):
        import copy
        from tools.strategy_epoch_lineage import validate_epoch,summarize_epoch
        state=controller.load_local_state(ROOT)
        a=copy.deepcopy(state['active_strategy'])
        current=a['technical_rotation_runtime_last_verified']['series_id']
        next_id='PAPER-V2R4-20261012T110000Z'
        fp=a['technical_rotation_runtime_last_verified']['strategy_fingerprint_sha256']
        a['strategy_epoch_closed_segments'].append({
            'series_id':current,'successor_series_id':next_id,
            'status':'technical_closed','immutable':True,
            'strategy_revision':a['strategy_revision'],
            'strategy_fingerprint_sha256':fp,
            'followups_beyond_cutover':'CENSORED_NOT_0_LOSS',
            'cutover_at_utc':'2026-10-12T11:00:00Z',
            'observed_at_utc':'2026-10-12T11:02:00Z',
            'frozen_outcomes_at_cutover':500,
            'frozen_completed_trades_at_cutover':0,
            'verified_complete_24h_at_cutover':250,
            'verified_eligible_24h_at_cutover':250,
        })
        snapshot=a['technical_rotation_runtime_last_verified']
        snapshot['series_id']=next_id
        snapshot['predecessor_outcomes_immutable_at_cutover']=500
        snapshot['predecessor_trades_immutable_at_cutover']=0
        snapshot['predecessor_24h_complete_at_cutover']=250
        snapshot['predecessor_24h_eligible_at_cutover']=250
        self.assertEqual(validate_epoch(a),[])
        report=summarize_epoch(a,{
            'series_id':next_id,'strategy_revision':a['strategy_revision'],
            'candidate_outcomes':50,'completed_trades':0,'complete_24h':0})
        self.assertEqual(report['technical_closed_segment_count'],2)
        self.assertEqual(report['epoch_minimum_candidate_outcomes'],1561)
        self.assertEqual(report['epoch_minimum_complete_24h'],510)
        self.assertEqual(report['epoch_minimum_completed_trades'],0)
        a['strategy_epoch_closed_segments'][1]['series_id']=a['series_id']
        self.assertTrue(any('lineage' in x for x in validate_epoch(a)))
        with self.assertRaises(ValueError):
            summarize_epoch(a,{'series_id':next_id,'strategy_revision':a['strategy_revision'],
                               'candidate_outcomes':50,'completed_trades':0,'complete_24h':0})

    def test_closed_segment_missing_followups_cannot_fake_mature_24h(self):
        import copy
        from tools.strategy_epoch_lineage import validate_epoch
        active=copy.deepcopy(controller.load_local_state(ROOT)['active_strategy'])
        source=active['strategy_epoch_closed_segments'][0]
        source['verified_complete_24h_at_cutover']=261
        self.assertTrue(validate_epoch(active))
        source['verified_complete_24h_at_cutover']=260
        source['verified_eligible_24h_at_cutover']=259
        self.assertTrue(any('maturity' in x for x in validate_epoch(active)))


if __name__ == '__main__':
    unittest.main()
