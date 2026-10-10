import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("selector",ROOT/"tools/select-autonomous-implementation.py")
selector=importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)
QUEUE=json.loads((ROOT/"research/autonomous-implementation-queue-v1.json").read_text())
STATE=json.loads((ROOT/"project-current-state.json").read_text())

class SafeAutonomyTests(unittest.TestCase):
    def test_safe_h10_contract_due_and_readonly(self):
        with tempfile.TemporaryDirectory() as p:
            r=selector.select(Path(p),QUEUE,STATE,{})
        self.assertEqual(r["status"],"READY_SAFE_WORK")
        self.assertEqual([t["id"] for t in r["ready"]],["H10_PROSPECTIVE_JOIN_CONTRACT"])
        self.assertFalse(r["strategy_changed"])
        self.assertFalse(r["real_money_actions"])
    def test_gate_closes_after_artifact(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            f=root/"research/v3/h10-kraken-outcome-context-join-contract-v1.json"
            f.parent.mkdir(parents=True)
            f.write_text("{}")
            r=selector.select(root,QUEUE,STATE,{})
        self.assertEqual(r["status"],"NO_SAFE_WORK")
    def test_blocked_attempt_cannot_loop(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            first=selector.select(root,QUEUE,STATE,{})
            ack={"autonomy_task_attempts":{"H10_PROSPECTIVE_JOIN_CONTRACT":{
              "gate_fingerprint":first["fingerprint"],"status":"BLOCKED"}}}
            after=selector.select(root,QUEUE,STATE,ack)
        self.assertFalse(after["safe_work_requested"])
    def test_archived_h3_is_supported_without_phantom_adapter(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            f=root/"research/v3/h10-kraken-outcome-context-join-contract-v1.json"
            f.parent.mkdir(parents=True)
            f.write_text("{}")
            r=selector.select(root,QUEUE,STATE,{})
        self.assertNotIn("UNKNOWN_CONTROL_DECISION_ADAPTER",[t["id"] for t in r["ready"]])
        self.assertEqual(r["status"],"NO_SAFE_WORK")

    def test_minipc_plan_autonomous_preparation_is_ready_only_when_authorized(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            (root/"docs").mkdir()
            (root/"docs/minipc-analytics-rollout-v1.md").write_text(
                "MINI-PC PLAN_APPROVED_PREP_ONLY",encoding="utf-8")
            initial=selector.select(root,QUEUE,STATE,{})
            self.assertNotIn("MINIPC_ANALYTICS_READONLY_PREP",
                [x["id"] for x in initial["ready"]])
            (root/"PROJECT_BACKLOG.md").write_text(
                "MINIPC_ANALYTICS_ROLLOUT_V1",encoding="utf-8")
            ready=selector.select(root,QUEUE,STATE,{})
            self.assertIn("MINIPC_ANALYTICS_READONLY_PREP",
                [x["id"] for x in ready["ready"]])
            self.assertFalse(ready["strategy_changed"])
            self.assertFalse(ready["orders"])
            fingerprint=ready["fingerprint"]
            ack={"autonomy_task_attempts":{"MINIPC_ANALYTICS_READONLY_PREP":{
                "gate_fingerprint":fingerprint,"status":"ACTIVE_PR"}}}
            suppressed=selector.select(root,QUEUE,STATE,ack)
            self.assertNotIn("MINIPC_ANALYTICS_READONLY_PREP",
                [x["id"] for x in suppressed["ready"]])
            target=root/"research/v3/minipc-analytics-readonly-reuse-preflight-v1.md"
            target.parent.mkdir(parents=True)
            target.write_text("gated research review",encoding="utf-8")
            done=selector.select(root,QUEUE,STATE,{})
            self.assertNotIn("MINIPC_ANALYTICS_READONLY_PREP",
                [x["id"] for x in done["ready"]])

    def test_unknown_next_decision_schedules_adapter(self):
        with tempfile.TemporaryDirectory() as p:
            state=copy.deepcopy(STATE)
            state["next_control_decisions"].append({"id":"NEW_VERSION_REVIEW"})
            r=selector.select(Path(p),QUEUE,state,{})
        self.assertIn("UNKNOWN_CONTROL_DECISION_ADAPTER",[x["id"] for x in r["ready"]])
    def test_no_unreviewed_action(self):
        q=copy.deepcopy(QUEUE)
        q["tasks"].append({"id":"AUTO_TRADE","gate":"NOW","status":"APPROVED_SAFE_SCOPE"})
        with tempfile.TemporaryDirectory() as p:
            r=selector.select(Path(p),q,STATE,{})
        self.assertEqual(r["status"],"BLOCKED")
    def test_shadow_wip_fail_closed(self):
        state=copy.deepcopy(STATE)
        state["strategy_changing_shadow_wip"]["active"].extend([
            {"candidate_id":"V3-H3-SHADOW"},
            {"candidate_id":"V3-H6-SHADOW"},
        ])
        with tempfile.TemporaryDirectory() as p:
            r=selector.select(Path(p),QUEUE,state,{})
        self.assertEqual(r["status"],"BLOCKED")
    def test_no_real_money_enabling(self):
        state=copy.deepcopy(STATE)
        state["active_strategy"]["real_money_actions"]=True
        with tempfile.TemporaryDirectory() as p:
            r=selector.select(Path(p),QUEUE,state,{})
        self.assertEqual(r["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
