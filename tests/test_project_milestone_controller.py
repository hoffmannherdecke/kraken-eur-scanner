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

if __name__ == '__main__':
    unittest.main()
