import copy
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools.project_followthrough_router import route, read_json as original_read_json

ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc


class ProjectFollowthroughRoutingTests(unittest.TestCase):
    def test_covers_all_registered_streams_and_project_areas_without_trading(self):
        result = route(ROOT, dt.datetime(2026, 10, 10, 8, 0, tzinfo=UTC))
        routing = json.loads((ROOT / "research/monitoring-evidence-routing-v1.json").read_text())
        self.assertEqual(result["stream_coverage_count"], len(routing["streams"]))
        self.assertGreaterEqual(result["crosscut_coverage_count"], 9)
        self.assertNotIn("V3-H3-ARCHIVE-DISPOSITION",
                         [x["id"] for x in result["ready_control_decisions"]])
        state = json.loads((ROOT / "project-current-state.json").read_text())
        h3 = next(x for x in state["closed_or_rejected_tracks"]
                  if x.get("id") == "V3-H3-SHADOW-001")
        self.assertEqual(h3.get("archive_disposition"), "DEFER_WITH_GATE")
        self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                      [x["id"] for x in result["gated_control_decisions"]])
        self.assertFalse(result["may_change_strategy"])
        self.assertFalse(result["may_execute_orders"])
        self.assertFalse(result["may_schedule_new_runs"])
        context = result["context_before_material_work"]
        self.assertTrue(context["required"])
        self.assertTrue(context["must_read_original_relevant_sources"])
        self.assertTrue(context["receipt_does_not_grant_release"])
        self.assertEqual(context["command"], "tools/context_before_action.py")

    def test_v3_five_source_after_cutover_is_real_work_not_a_claim(self):
        from tools.project_followthrough_router import v3_five_source_followthrough
        state=json.loads((ROOT/"project-current-state.json").read_text("utf-8"))
        now=dt.datetime(2026,10,14,9,tzinfo=UTC)
        before=v3_five_source_followthrough(ROOT,state,{},now)
        self.assertEqual(before["status"],"WAIT_FOR_REAL_V3_PAPER_CUTOVER")
        self.assertEqual(len(before["open_roles"]),5)
        self.assertEqual(before["next_safe_actions"],[])
        state=copy.deepcopy(state)
        state["active_strategy"]["strategy_revision"]="V3-EXPERIMENTAL-PAPER-001"
        state["active_strategy"]["series_id"]="PAPER-V3-EXPERIMENTAL-001"
        state["pending_strategy_transition"]["status"]="V3_PAPER_ACTIVE_VERIFIED"
        state["pending_strategy_transition"]["verified_cutover_evidence"]={
            "mini_pc_and_single_active_supabase_series_ack":True}
        due=v3_five_source_followthrough(ROOT,state,{},now)
        self.assertEqual(due["status"],"SOURCE_WORK_OPEN")
        self.assertEqual(len(due["open_roles"]),5)
        self.assertEqual(len(due["next_safe_actions"]),2)
        self.assertTrue(due["no_paper_start_block"])
        self.assertFalse(due["runtime_changed"])
        self.assertFalse(due["acknowledged_roles"])
        state["pending_strategy_transition"]["verified_cutover_evidence"]={}
        self.assertEqual(v3_five_source_followthrough(ROOT,state,{},now)["status"],
                         "WAIT_FOR_REAL_V3_PAPER_CUTOVER")

    def test_source_ack_cannot_be_closed_by_boolean_or_missing_report(self):
        from tools.project_followthrough_router import v3_five_source_followthrough
        import hashlib
        state=copy.deepcopy(json.loads((ROOT/"project-current-state.json").read_text()))
        state["active_strategy"]["strategy_revision"]="V3-RELEASE-NEW"
        state["active_strategy"]["series_id"]="PAPER-V3-NEW"
        state["pending_strategy_transition"]["status"]="V3_PAPER_ACTIVE_VERIFIED"
        state["pending_strategy_transition"]["verified_cutover_evidence"]={
            "mini_pc_and_single_active_supabase_series_ack":True}
        now=dt.datetime(2026,10,15,9,tzinfo=UTC)
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            p=base/"research/project-followthrough-routing-v1.json"
            p.parent.mkdir(parents=True)
            shutil.copy(ROOT/"research/project-followthrough-routing-v1.json",p)
            report=base/"research/work-analysis/real-source-readback.md"
            report.parent.mkdir(parents=True)
            report.write_text("One V3 source / consumer evidence review",encoding="utf-8")
            item={
              "status":"OWNER_TO_V3_CONSUMER_E2E_REVIEWED",
              "strategy_revision":"V3-RELEASE-NEW","series_id":"PAPER-V3-NEW",
              "report":"research/work-analysis/real-source-readback.md",
              "evidence_sha256":hashlib.sha256(report.read_bytes()).hexdigest(),
              "source_original_ref":"SOURCE-IMMUTABLE-20261015",
              "consumer_original_ref":"V3-MODEL-IMMUTABLE-20261015",
              "verified_at_utc":"2026-10-15T08:00:00Z",
              "independent_owner_consumer_readback":True}
            ledger={"acknowledgements":{"v3_paper_source_e2e":{
                     "smart_money_h10":dict(item)}}}
            result=v3_five_source_followthrough(base,state,ledger,now)
            self.assertEqual(result["acknowledged_roles"],["smart_money_h10"])
            self.assertEqual(len(result["open_roles"]),4)
            accepted=ledger["acknowledgements"]["v3_paper_source_e2e"]["smart_money_h10"]
            accepted["evidence_sha256"]="0"*64
            result=v3_five_source_followthrough(base,state,ledger,now)
            self.assertEqual(len(result["open_roles"]),5)
            accepted["evidence_sha256"]=hashlib.sha256(report.read_bytes()).hexdigest()
            accepted["source_original_ref"]="V3-MODEL-IMMUTABLE-20261015"
            result=v3_five_source_followthrough(base,state,ledger,now)
            self.assertEqual(len(result["open_roles"]),5)


    def test_26_streams_are_not_mistaken_for_actual_commitment_execution(self):
        from tools.project_followthrough_router import project_implementation_commitments
        state=json.loads((ROOT/"project-current-state.json").read_text())
        now=dt.datetime(2026,10,13,5,35,tzinfo=UTC)
        out=project_implementation_commitments(ROOT,state,{},now)
        self.assertGreaterEqual(out["registered_count"],10)
        self.assertEqual(out["open_count"],out["registered_count"])
        self.assertFalse(out["no_auto_paper_release"] is False)
        self.assertIn("V3_EXPERIMENTAL_PAPER_SIX_PROOFS",
                      [r["id"] for r in out["ready_safe_actions"]])
        self.assertIn("V3_H3_ORDERBOOK_REEXAMINATION",
                      [r["id"] for r in out["items"]])
        self.assertEqual(next(x for x in out["items"]
                   if x["id"]=="V3_H3_ORDERBOOK_REEXAMINATION")["state"],
                         "WAIT_FOR_EVIDENCE_GATE")
        self.assertEqual(next(x for x in out["items"]
                   if x["id"]=="V3_CANARY_28H_PHYSICAL_CLOSURE")["state"],
                         "WAIT_FOR_EVIDENCE_GATE")

    def test_commitment_registry_refuses_missing_backlog_and_fake_ack(self):
        from tools.project_followthrough_router import project_implementation_commitments
        state=json.loads((ROOT/"project-current-state.json").read_text())
        now=dt.datetime(2026,10,13,12,5,tzinfo=UTC)
        out=project_implementation_commitments(ROOT,state,{},now)
        self.assertIn("V3_CANARY_28H_PHYSICAL_CLOSURE",
                       [x["id"] for x in out["ready_safe_actions"]])
        spoof={"acknowledgements":{"project_implementation_commitments":{
          "V3_CANARY_28H_PHYSICAL_CLOSURE":{"status":"INDEPENDENT_EVIDENCE_REVIEWED",
             "completed_at_utc":"2026-10-13T12:01:00Z",
             "report":"research/work-analysis/nonexistent-evidence.md",
             "evidence_sha256":"0"*64,
             "source_original_ref":"PHYSICAL-ORIGINAL-ACK",
             "consumer_original_ref":"INDEPENDENT-REVIEW-ACK",
             "independent_live_readback_confirmed":True}}}}
        after=project_implementation_commitments(ROOT,state,spoof,now)
        self.assertEqual(after["open_count"],after["registered_count"])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for path in ("research/project-followthrough-routing-v1.json",
                         "research/monitoring-evidence-routing-v1.json","PROJECT_BACKLOG.md"):
                target=root/path
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy(ROOT/path,target)
            registry=root/"research/project-followthrough-routing-v1.json"
            content=json.loads(registry.read_text())
            content["project_wide_implementation_commitments"]["obligations"][0][
                "backlog_marker"]="NOT_A_REAL_COMMITMENT"
            registry.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError,"backlog backlink"):
                project_implementation_commitments(root,state,{},now)


    def test_wait_incident_surfaces_automatically_after_canary_and_cannot_fake_close(self):
        from tools.project_followthrough_router import project_implementation_commitments
        state=json.loads((ROOT/"project-current-state.json").read_text())
        ident="V2R4_WAIT_INCIDENT_PHYSICAL_FOLLOWTHROUGH"
        pre=dt.datetime(2026,10,13,11,59,59,tzinfo=UTC)
        post=dt.datetime(2026,10,13,12,0,13,tzinfo=UTC)
        before=project_implementation_commitments(ROOT,state,{},pre)
        row=next(x for x in before["items"] if x["id"]==ident)
        self.assertEqual(row["state"],"WAIT_FOR_EVIDENCE_GATE")
        due=project_implementation_commitments(ROOT,state,{},post)
        row=next(x for x in due["items"] if x["id"]==ident)
        self.assertEqual(row["state"],"READY_SAFE_IMPLEMENTATION")
        self.assertIn(ident,[x["id"] for x in due["ready_safe_actions"]])
        self.assertTrue(row["requires_user_release"])
        self.assertGreater(len(due["ready_safe_actions"]),2)
        fake={"acknowledgements":{"project_implementation_commitments":{
            ident:{"status":"INDEPENDENT_EVIDENCE_REVIEWED",
                   "completed_at_utc":"2026-10-13T12:00:13Z",
                   "report":"research/work-analysis/not-a-physical-proof.md",
                   "evidence_sha256":"0"*64,
                   "source_original_ref":"MINIPC-ACTIVE-SHA-BEFORE-AFTER",
                   "consumer_original_ref":"CLOUD-CONSUMER-READBACK",
                   "independent_live_readback_confirmed":True}
        }}}
        still_open=project_implementation_commitments(ROOT,state,fake,post)
        self.assertIn(ident,[x["id"] for x in still_open["ready_safe_actions"]])

    def test_every_legacy_open_checkbox_is_visible_until_evidenced_disposition(self):
        from tools.project_followthrough_router import historical_backlog_reconciliation
        now=dt.datetime(2026,10,13,6,tzinfo=UTC)
        out=historical_backlog_reconciliation(ROOT,{},now)
        current_open=sum(
            1 for line in
            (ROOT/"PROJECT_BACKLOG.md").read_text(encoding="utf-8").splitlines()
            if line.lstrip().startswith("- [ ]")
        )
        self.assertEqual(out["open_checkboxes_total"],current_open)
        self.assertGreater(current_open,0)
        self.assertEqual(out["still_unclassified"],out["open_checkboxes_total"])
        self.assertEqual(len(out["next_review"]),3)
        self.assertTrue(out["legacy_open_box_not_a_live_task_without_review"])
        fake={"acknowledgements":{"historical_backlog_dispositions":{
            out["next_review"][0]["id"]:{
                "disposition":"COMPLETED_VERIFIED","owner":"FAKE_OWNER",
                "next_gate":"FAKE_RELEASE_GATES","evidence_sha256":"0"*64,
                "report":"research/work-analysis/absent.md",
                "reviewed_at_utc":"2026-10-13T05:00:00Z"}}}}
        after=historical_backlog_reconciliation(ROOT,fake,now)
        self.assertEqual(after["still_unclassified"],out["open_checkboxes_total"])

    def test_missing_context_handoff_blocks_substantive_work(self):
        manifest_path = "research/project-followthrough-routing-v1.json"
        original = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
        original.pop("context_preflight")
        def replaced(root, name):
            return original if name == manifest_path else original_read_json(root, name)
        with patch("tools.project_followthrough_router.read_json", side_effect=replaced):
            with self.assertRaisesRegex(ValueError, "context before material action"):
                route(ROOT, dt.datetime(2026, 10, 11, 8, 0, tzinfo=UTC))

    def test_due_gate_needs_real_report_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ("research/project-followthrough-routing-v1.json",
                         "research/monitoring-evidence-routing-v1.json",
                         "project-current-state.json", "research/work-analysis-state.json",
                         "PROJECT_BACKLOG.md"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / path, target)
            for area in json.loads((root / "research/project-followthrough-routing-v1.json").read_text())["extra_project_areas"]:
                path = root / area["owner"]
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text("owner")
            late = dt.datetime(2026, 10, 11, 8, 0, tzinfo=UTC)
            result = route(root, late)
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in result["ready_control_decisions"]])
            report = "research/work-analysis/v2r4-72h-decision.md"
            dst = root / report
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text("real review", encoding="utf-8")
            ackfile = root / "research/work-analysis-state.json"
            ack = json.loads(ackfile.read_text())
            ack.setdefault("acknowledgements", {}).setdefault("control_decision_reviews", {})[
                "V2R4_72H_STRATEGY_EPOCH_20261010"] = {
                    "status": "DECISION_PACKET_READY",
                    "completed_at_utc": "2026-10-11T07:00:00Z",
                    "report": report}
            ackfile.write_text(json.dumps(ack))
            result = route(root, late)
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW", result["previously_acknowledged"])
            ack["acknowledgements"]["control_decision_reviews"][
                "V2R4_72H_STRATEGY_EPOCH_20261010"]["completed_at_utc"] = "2099-10-11T07:00:00Z"
            ackfile.write_text(json.dumps(ack))
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in route(root, late)["ready_control_decisions"]])
            dst.unlink()
            self.assertIn("V2R4-PRODUCTIVITY-REVIEW",
                          [x["id"] for x in route(root, late)["ready_control_decisions"]])

    def test_missing_facets_or_unsafe_permissions_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in ("research/project-followthrough-routing-v1.json",
                         "research/monitoring-evidence-routing-v1.json",
                         "project-current-state.json", "research/work-analysis-state.json",
                         "PROJECT_BACKLOG.md"):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / path, target)
            routing_path = root / "research/monitoring-evidence-routing-v1.json"
            routing = json.loads(routing_path.read_text())
            routing["streams"] = routing["streams"][:2]
            routing_path.write_text(json.dumps(routing))
            with self.assertRaisesRegex(ValueError, "missing/duplicate monitoring route"):
                route(root, dt.datetime.now(UTC))
            routing = json.loads((ROOT / "research/monitoring-evidence-routing-v1.json").read_text())
            routing["streams"][0]["id"] = "unregistered_replacement"
            routing_path.write_text(json.dumps(routing))
            with self.assertRaisesRegex(ValueError, "missing/duplicate monitoring route"):
                route(root, dt.datetime.now(UTC))



    def test_implementation_commitments_legacy_per_run_cap_is_rejected(self):
        from tools.project_followthrough_router import project_implementation_commitments
        old=json.loads((ROOT/"research/project-followthrough-routing-v1.json").read_text())
        cfg=old["project_wide_implementation_commitments"]
        cfg.pop("max_concurrent_active_work_packages")
        cfg["max_safe_actions_per_run"]=2
        def spoofed(root,name):
            return old if name=="research/project-followthrough-routing-v1.json" else original_read_json(root,name)
        state=json.loads((ROOT/"project-current-state.json").read_text())
        with patch("tools.project_followthrough_router.read_json",side_effect=spoofed):
            with self.assertRaisesRegex(ValueError,"canonical implementation commitment"):
                project_implementation_commitments(ROOT,state,{},dt.datetime.now(UTC))

if __name__ == "__main__":
    unittest.main()
