import copy
import hashlib
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
    def test_post_v3_source_adoption_is_safe_real_work_only_after_verified_cutover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=ROOT/"research/project-followthrough-routing-v1.json"
            dst=root/"research/project-followthrough-routing-v1.json"
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(src.read_bytes())
            state=copy.deepcopy(STATE)
            before=selector.select(root,QUEUE,state,{})
            self.assertNotIn("V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH",
                             [x["id"] for x in before["ready"]])
            state["active_strategy"]["strategy_revision"]="V3-PAPER-RELEASE"
            state["active_strategy"]["series_id"]="PAPER-V3-NEW"
            state["pending_strategy_transition"]["status"]="V3_PAPER_ACTIVE_VERIFIED"
            state["pending_strategy_transition"]["verified_cutover_evidence"]={
                "mini_pc_and_single_active_supabase_series_ack":True}
            after=selector.select(root,QUEUE,state,{})
            self.assertIn("V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH",
                           [x["id"] for x in after["ready"]])
            job=next(x for x in after["ready"]
                     if x["id"]=="V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH")
            self.assertIn("POST_CUTOVER_SOURCE_E2E",job["gate"])
            self.assertFalse(after["strategy_changed"])
            self.assertFalse(after["real_money_actions"])
            self.assertLessEqual(len(after["ready"]),2)
            state["pending_strategy_transition"]["verified_cutover_evidence"]={}
            blocked=selector.select(root,QUEUE,state,{})
            self.assertNotIn("V3_PAPER_FIVE_SOURCE_FOLLOWTHROUGH",
                             [x["id"] for x in blocked["ready"]])


    def test_project_safe_obligations_are_selected_without_new_per_id_adapter(self):
        r=selector.select(ROOT,QUEUE,STATE,{})
        self.assertEqual(r["status"],"READY_SAFE_WORK")
        self.assertIn("PROJECT_WIDE_COMMITMENT_SAFE_WORK",
                      [x["id"] for x in r["ready"]])
        self.assertLessEqual(len(r["ready"]),2)
        self.assertFalse(r["strategy_changed"])
        self.assertFalse(r["real_money_actions"])


    def test_real_root_queues_bounded_legacy_backlog_review_not_runtime(self):
        r=selector.select(ROOT,QUEUE,STATE,{})
        self.assertTrue(any(t["id"]=="HISTORICAL_BACKLOG_RECONCILIATION"
                            for t in r["ready"]) or
                        r["open_work_count"]>=2)
        self.assertFalse(r["real_money_actions"])
        self.assertLessEqual(len(r["ready"]),2)

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


    def test_two_concurrent_packages_refill_only_after_documented_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"docs").mkdir()
            (root/"docs/minipc-analytics-rollout-v1.md").write_text(
                "PLAN_APPROVED_PREP_ONLY",encoding="utf-8")
            (root/"PROJECT_BACKLOG.md").write_text(
                "MINIPC_ANALYTICS_ROLLOUT_V1",encoding="utf-8")
            state=copy.deepcopy(STATE)
            state["next_control_decisions"].append({"id":"NEW_CONTROL_GATE"})
            initial=selector.select(root,QUEUE,state,{})
            self.assertEqual(len(initial["ready"]),2)
            self.assertEqual(initial["active_work_package_count"],0)
            self.assertIn("UNKNOWN_CONTROL_DECISION_ADAPTER",
                [x["id"] for x in initial["waiting_due"]])
            first,second=[x["id"] for x in initial["ready"]]
            attempts={
                first:{"gate_fingerprint":initial["fingerprint"],"status":"IN_PROGRESS"},
                second:{"gate_fingerprint":initial["fingerprint"],"status":"ACTIVE_PR"}}
            full=selector.select(root,QUEUE,state,{"autonomy_task_attempts":attempts})
            self.assertFalse(full["ready"])
            self.assertEqual(full["active_work_package_count"],2)
            self.assertEqual(full["active_implementation_pr_count"],1)
            self.assertIn("UNKNOWN_CONTROL_DECISION_ADAPTER",
                [x["id"] for x in full["waiting_due"]])
            # A bare label is not a real completion. It must not release
            # a slot or permit another package to start.
            attempts[first]["status"]="COMPLETED"
            fake=selector.select(root,QUEUE,state,{"autonomy_task_attempts":attempts})
            self.assertEqual(fake["status"],"BLOCKED")
            self.assertIn("unverified completion receipt "+first,fake["errors"])
            report = root/"research/work-analysis/real-work-receipt.md"
            report.parent.mkdir(parents=True,exist_ok=True)
            report.write_text("Independent original source outcome checked",encoding="utf-8")
            attempts[first].update({
                "report": "research/work-analysis/real-work-receipt.md",
                "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                "reason":"Offline safe contract and independent source acknowledgement",
                "completed_at_utc":"2026-10-17T10:00:00Z",
            })
            refilled=selector.select(root,QUEUE,state,{"autonomy_task_attempts":attempts})
            self.assertEqual(refilled["active_work_package_count"],1)
            self.assertEqual([x["id"] for x in refilled["ready"]],
                             ["UNKNOWN_CONTROL_DECISION_ADAPTER"])
            self.assertTrue(refilled["refill_after_evidenced_ack_same_run"])
            self.assertTrue(refilled["external_github_pr_count_must_be_verified_by_work"])

    def test_work_complete_cannot_be_claimed_with_fake_or_missing_local_ack(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            target=root/"research/work-analysis/verified.md"
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text("original source verification receipt\n",encoding="utf-8")
            good={
                "status":"COMPLETED","report":"research/work-analysis/verified.md",
                "report_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
                "reason":"Safe work completed after independent read-only inspection",
                "completed_at_utc":"2026-10-17T10:12:00Z",
            }
            self.assertTrue(selector.verified_completed_work_receipt(root,good))
            invalid=[
                {"report_sha256":"0"*64},
                {"report":"research/work-analysis/not-found.md"},
                {"report":"research/work-analysis/../../SECRET.txt"},
                {"report":"/tmp/not-an-artifact"},
                {"report":"research/work-analysis/verified.md\\outside"},
                {"report_sha256":"xxxx"},
                {"completed_at_utc":"2026-10-17T10:12:00"},
                {"completed_at_utc":None},
                {"reason":""},
                {"status":"BLOCKED"},
            ]
            for changes in invalid:
                bad={**good,**changes}
                with self.subTest(changes=changes):
                    self.assertFalse(selector.verified_completed_work_receipt(root,bad))
            target.write_text("this artifact was changed after acknowledgement\n",encoding="utf-8")
            self.assertFalse(selector.verified_completed_work_receipt(root,good))

    def test_overcommitted_ledger_and_legacy_run_cap_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            attempts={"ACTIVE_"+str(i):{"status":"IN_PROGRESS"} for i in range(3)}
            r=selector.select(root,QUEUE,STATE,{"autonomy_task_attempts":attempts})
            self.assertEqual(r["status"],"BLOCKED")
            self.assertIn("overcommitted active work / implementation PR",r["errors"])
            two_prs={"ACTIVE_A":{"status":"ACTIVE_PR"},
                     "ACTIVE_B":{"status":"ACTIVE_PR"}}
            self.assertEqual(selector.select(root,QUEUE,STATE,
                {"autonomy_task_attempts":two_prs})["status"],"BLOCKED")
            self.assertEqual(selector.select(root,QUEUE,STATE,
                {"autonomy_task_attempts":[]})["status"],"BLOCKED")
            unsafe=copy.deepcopy(QUEUE)
            unsafe.pop("max_concurrent_active_work_packages")
            unsafe["max_safe_actions_per_open_work_run"]=2
            self.assertEqual(selector.select(root,unsafe,STATE,{})["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
