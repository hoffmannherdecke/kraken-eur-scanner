import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('controller', ROOT / 'tools/project_milestone_controller.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)

class MilestoneTests(unittest.TestCase):
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
        paper = dict(series_id=active['series_id'], strategy_revision=active['strategy_revision'],
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
        paper=dict(series_id=active['series_id'],strategy_revision=active['strategy_revision'],
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

    def test_72h_low_trade_gate_requires_mature_followups_not_fake_technical_pass(self):
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
        self.assertNotIn('V2R4:LOW_TRADE_REVIEW',r['statuses'])

if __name__ == '__main__':
    unittest.main()
