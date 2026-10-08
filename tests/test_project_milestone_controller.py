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

if __name__ == '__main__':
    unittest.main()
