"""No-profit-before-paper is permitted ONLY with actual technical proofs."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.v3_experimental_paper_technical_gate import (
    PROOFS, PROOF_KIND, PROOF_ORIGINS, validate_experimental_paper_packet,
)
from tools.strategy_successor_gate import ROOT, GATE_FILE, validate_learning_gate


def fixture(root:Path)->dict:
    items=[]
    for key in sorted(PROOFS):
        dest=root/"research"/("proof-"+key.lower()+".json")
        dest.parent.mkdir(parents=True,exist_ok=True)
        originals=[]
        # Synthetic unit envelope exercises the *structure* of a proof;
        # never represent this helper as a true Mini-PC/Cloud E2E success.
        for origin in sorted(PROOF_ORIGINS[key]):
            oid=f"test-contract/{origin}/{key}"
            record={"source_id":oid,"observed_at_utc":"2026-10-13T09:30:00Z",
                    "source_status":"ACK_READBACK_AVAILABLE"}
            if key=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN":
                record.update({
                    "expected_predecessor_series_id":"PAPER-V2R4-20261009T110135Z",
                    "proposed_successor_series_id":"PAPER-V3-EXPERIMENTAL-TEST-001",
                    "dry_run_only":True,
                    "expected_old_repo_sha":"d8b35a8ec2e6f392f219b1c36cad95f3ad629b64",
                    "proposed_v3_repo_sha":"c"*40,
                    "proposed_v3_bundle_sha256":"a"*64,
                    "proposed_v3_strategy_sha256":"b"*64,
                })
                if origin=="MINIPC_PHYSICAL":
                    record.update({
                        "physical_writer_fence_dry_run_passed":True,
                        "new_v3_writer_started":False,
                        "v2r4_live_strategy_modified":False,
                        "precommit_original_backup_verified":True,
                        "precommit_restore_only_before_cloud_commit_tested":True,
                        "old_followups_retained_on_original_series_tested":True,
                        "old_followup_owner_running_after_cutover_tested":True,
                        "old_supervisor_intake_rearm_fence_tested":True,
                    })
                if origin=="SUPABASE_CLOUD":
                    record.update({
                        "single_active_unique_index_present":True,
                        "expected_predecessor_cas_dry_run_passed":True,
                        "v2r4_only_rotation_not_invoked":True,
                        "active_paper_series_changed":False,
                        "phase":"CLOUD_COMMIT_NOT_ATTEMPTED",
                        "active_paper_series":[{
                            "series_id":"PAPER-V2R4-20261009T110135Z",
                            "status":"active"}],
                        "stale_predecessor_cas_rejected_tested":True,
                        "ambiguous_cloud_outcome_quarantines_both_tested":True,
                        "postcommit_no_predecessor_restart_tested":True,
                        "closed_old_series_followup_update_accepted_tested":True,
                        "closed_old_series_trade_exit_update_accepted_tested":True,
                        "closed_old_series_new_intake_rejected_tested":True,
                    })
            canonical=json.dumps(record,sort_keys=True,separators=(",",":")).encode()
            originals.append({"origin":origin,"original_id":oid,
                 "original_record":record,
                 "original_sha256":hashlib.sha256(canonical).hexdigest()})
        dest.write_text(json.dumps({"kind":PROOF_KIND,"proof_id":key,
                          "source_originals":originals},sort_keys=True),
                        encoding="utf-8")
        items.append({"id":key,"status":"VERIFIED_PHYSICAL_OR_CLOUD_E2E",
                      "evidence_path":str(dest.relative_to(root)),
                      "sha256":hashlib.sha256(dest.read_bytes()).hexdigest()})
    return {"kind":"SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1",
            "strategy_revision":"V3-PAPER-EXPERIMENTAL-001",
            "paper_phase":"EXPERIMENTAL_PAPER_ONLY",
            "status":"READY_WITH_EXPLICIT_EXPERIMENTAL_PAPER_APPROVAL",
            "paper_only":True,"real_money_actions":False,
            "automatic_activation":False,
            "explicit_human_release_decision":"APPROVED_EXPERIMENTAL_PAPER",
            "code_fingerprint_sha256":"a"*64,
            "strategy_fingerprint_sha256":"b"*64,
            "economic_alpha_claimed":False,
            "post_experiment_promotion_requires_economic_gate":True,
            "physical_single_writer_cutover_dry_run_passed":True,
            "physical_single_writer_cutover_ack_obtained":False,
            "fixed_api_cost_limit_user_authorized":True,
            "bounded_research_scope":{
              "max_candidates":100,"max_model_http_attempts_including_retries":200,
              "max_observation_days":14,"deduplicate_pair_clock":True,
              "mandatory_real_6h_24h_and_censored_followups":True,
              "stop_when_budget_exhausted":True},
            "frozen_execution_risk":{
              "taker_pct_each_side":0.6,"scout_eur":50,"stage2_eur":50,
              "kraken_online_spot_eur":True,"true_pit_1m5m15m_atr_stop":True,
              "full_model_decision_before_any_paper_buy":True,
              "stop_stage2_spread_slippage_required":True,
              "no_real_orders":True,"no_h3_h6_auto_activation":True},
            "experimental_paper_technical_proofs":items,
            "prospective_feasibility":{"evaluated_candidates":0,"valid_buy_scouts":0}}


class ExperimentalV3PaperTechnicalReleaseTests(unittest.TestCase):
    def test_current_v2r4_unchanged_and_no_v3_evidence_is_blocked(self):
        self.assertEqual(validate_learning_gate(ROOT,
            active_revision="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION"),[])
        x=validate_learning_gate(ROOT,active_revision="V3-PAPER-EXPERIMENTAL-001")
        self.assertTrue(any("NEW_STRATEGY_BLOCKED" in e for e in x))

    def test_experimental_paper_technical_release_not_alpha(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            p=root/GATE_FILE
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text((ROOT/GATE_FILE).read_text("utf-8"),encoding="utf-8")
            evidence=fixture(root)
            self.assertEqual(validate_learning_gate(root,"V3-PAPER-EXPERIMENTAL-001",
                                                    evidence),[])
            # NO requirement to invent a profitable BUY before a Paper experiment.
            self.assertEqual(evidence["prospective_feasibility"]["valid_buy_scouts"],0)
            self.assertFalse(evidence["economic_alpha_claimed"])
            self.assertFalse(evidence["physical_single_writer_cutover_ack_obtained"])
            # The later economic promotion path remains separate and strict.
            normal=copy.deepcopy(evidence)
            normal["paper_phase"]="ECONOMIC_PROMOTION"
            x=validate_learning_gate(root,"V3-PAPER-EXPERIMENTAL-001",normal)
            self.assertTrue(any("NEW_STRATEGY_BLOCKED" in e for e in x))

    def test_missing_one_real_proof_wrong_hash_budget_approval_always_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            base=fixture(root)
            mods=[
                lambda d:d["experimental_paper_technical_proofs"].pop(),
                lambda d:d["experimental_paper_technical_proofs"][0].update(status="MOCK_ONLY"),
                lambda d:d["experimental_paper_technical_proofs"][0].update(sha256="0"*64),
                lambda d:d["experimental_paper_technical_proofs"][0].update(evidence_path="../secret"),
                lambda d:d["experimental_paper_technical_proofs"].append(
                    copy.deepcopy(d["experimental_paper_technical_proofs"][0])),
                lambda d:d.update(fixed_api_cost_limit_user_authorized=False),
                lambda d:d.update(explicit_human_release_decision="SILENT_AUTO_APPROVED"),
                lambda d:d.update(physical_single_writer_cutover_dry_run_passed=False),
                lambda d:d.update(physical_single_writer_cutover_ack_obtained=True),
                lambda d:d.update(real_money_actions=True),
                lambda d:d.update(paper_only=False),
                lambda d:d.update(automatic_activation=True),
                lambda d:d.update(economic_alpha_claimed=True),
                lambda d:d.update(code_fingerprint_sha256="test-not-a-sha"),
                lambda d:d["bounded_research_scope"].update(max_candidates=0),
                lambda d:d["bounded_research_scope"].update(max_observation_days=999),
                lambda d:d["bounded_research_scope"].update(
                    max_model_http_attempts_including_retries=1001),
                lambda d:d["bounded_research_scope"].update(
                    mandatory_real_6h_24h_and_censored_followups=False),
                lambda d:d["frozen_execution_risk"].update(taker_pct_each_side=0),
                lambda d:d["frozen_execution_risk"].update(
                    full_model_decision_before_any_paper_buy=False),
                lambda d:d["frozen_execution_risk"].update(no_real_orders=False),
                lambda d:d.update(strategy_revision="OLD_V2R4"),
            ]
            for m in mods:
                d=copy.deepcopy(base);m(d)
                self.assertTrue(
                    validate_experimental_paper_packet(root,"V3-PAPER-EXPERIMENTAL-001",d),
                    m)

    def test_six_dummy_hash_correct_files_never_count_as_physical_e2e(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            evidence=fixture(root)
            for row in evidence["experimental_paper_technical_proofs"]:
                target=root/row["evidence_path"]
                target.write_text(json.dumps({"real_e2e_fixture_only":True}))
                row["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertTrue(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",evidence))

    def test_original_content_tampering_and_missing_cloud_role_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            base=fixture(root)
            row=next(x for x in base["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN")
            target=root/row["evidence_path"]
            valid_proof=json.loads(target.read_text("utf-8"))
            for modifier in (
                lambda proof: proof["source_originals"][0]
                    ["original_record"].update(source_status="FORGED"),
                lambda proof: proof.update(source_originals=[
                    x for x in proof["source_originals"]
                    if x["origin"]!="SUPABASE_CLOUD"]),
                lambda proof: proof.update(proof_id="WRONG_PROOF_ID"),
            ):
                proof=json.loads(target.read_text("utf-8"))
                modifier(proof)
                target.write_text(json.dumps(proof,sort_keys=True))
                row["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
                self.assertTrue(validate_experimental_paper_packet(
                    root,"V3-PAPER-EXPERIMENTAL-001",base))
                target.write_text(json.dumps(valid_proof,sort_keys=True))
                row["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()

    def test_cas_dryrun_requires_same_original_predecessor_on_host_and_cloud(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(x for x in packet["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN")
            path=root/row["evidence_path"]
            valid=json.loads(path.read_text("utf-8"))
            for field,bad in (
                ("expected_predecessor_series_id","PAPER-V2R4-20261007T184255Z"),
                ("proposed_successor_series_id","PAPER-V3-CONFLICT-0001"),
                ("expected_predecessor_cas_dry_run_passed",False),
                ("v2r4_only_rotation_not_invoked",False),
                ("active_paper_series_changed",True),
                ("single_active_unique_index_present",False),
                ("expected_old_repo_sha","0"*40),
                ("proposed_v3_repo_sha","e"*40),
                ("proposed_v3_bundle_sha256","f"*64),
                ("proposed_v3_strategy_sha256","e"*64),
                ("stale_predecessor_cas_rejected_tested",False),
                ("postcommit_no_predecessor_restart_tested",False),
                ("closed_old_series_followup_update_accepted_tested",False),
                ("closed_old_series_trade_exit_update_accepted_tested",False),
                ("closed_old_series_new_intake_rejected_tested",False),
                ("phase","CLOUD_COMMITTED"),
                ("active_paper_series",[
                    {"series_id":"PAPER-V3-EXPERIMENTAL-TEST-001","status":"active"}]),
            ):
                with self.subTest(field=field):
                    proof=copy.deepcopy(valid)
                    cloud=next(x for x in proof["source_originals"]
                               if x["origin"]=="SUPABASE_CLOUD")
                    cloud["original_record"][field]=bad
                    raw=json.dumps(cloud["original_record"],
                                   sort_keys=True,separators=(",",":")).encode()
                    cloud["original_sha256"]=hashlib.sha256(raw).hexdigest()
                    path.write_text(json.dumps(proof,sort_keys=True))
                    row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "cross-origin CAS mismatch must block even after rehash")
            path.write_text(json.dumps(valid,sort_keys=True))
            row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_cas_mini_pc_old_followup_owner_missing_blocks_before_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(x for x in packet["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN")
            path=root/row["evidence_path"]
            valid=json.loads(path.read_text("utf-8"))
            changed=copy.deepcopy(valid)
            host=next(x for x in changed["source_originals"]
                      if x["origin"]=="MINIPC_PHYSICAL")
            host["original_record"]["old_followup_owner_running_after_cutover_tested"]=False
            raw=json.dumps(host["original_record"],sort_keys=True,
                           separators=(",",":")).encode()
            host["original_sha256"]=hashlib.sha256(raw).hexdigest()
            path.write_text(json.dumps(changed,sort_keys=True))
            row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet))
            path.write_text(json.dumps(valid,sort_keys=True))
            row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_cas_same_wrong_bundle_cannot_bypass_outer_release_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(r for r in packet["experimental_paper_technical_proofs"]
                     if r["id"]=="V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN")
            file=root/row["evidence_path"]
            original=json.loads(file.read_text(encoding="utf-8"))
            for key,bad in (
                    ("proposed_v3_bundle_sha256","e"*64),
                    ("proposed_v3_strategy_sha256","f"*64),
                    ("proposed_v3_repo_sha","bad"),
                    ("expected_old_repo_sha",None)):
                with self.subTest(key=key):
                    modified=copy.deepcopy(original)
                    for item in modified["source_originals"]:
                        item["original_record"][key]=bad
                        raw=json.dumps(item["original_record"],sort_keys=True,
                                       separators=(",",":")).encode()
                        item["original_sha256"]=hashlib.sha256(raw).hexdigest()
                    file.write_text(json.dumps(modified,sort_keys=True))
                    row["sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "two matching but unapproved release fingerprints must fail")
            file.write_text(json.dumps(original,sort_keys=True))
            row["sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_canonical_cutover_runbook_does_not_delay_first_paper_until_profit(self):
        # The release gate already distinguishes experimentation from promotion.
        # Keep the *operational* host runbook aligned so an old A+B sentence
        # cannot become an artificial second 28h/72h Shadow requirement.
        text=(ROOT/"docs/v3-controlled-paper-cutover-20261011.md").read_text("utf-8")
        self.assertIn("## 2. Reihenfolge der physischen Mini-PC-Übernahme, erst **nach** A + technischem",text)
        self.assertIn("B: Wirtschaftliche Nachfolger-Promotion",text)
        self.assertIn("KEINE Vorbedingung für den ersten `EXPERIMENTAL_PAPER_ONLY`-Start",text)
        self.assertIn("sechs **echte**",text)
        self.assertIn("ein profitabler Vorabkauf ist dabei nicht gefordert",text)
        self.assertNotIn("erst **nach** A+B",text)

    def test_current_runtime_does_not_depend_on_experimental_gate(self):
        for f in ("paper_evaluator/evaluate.py",
                  "paper_evaluator/v2r4_local_recheck.py",
                  "tools/v2r4-paper-local-runtime.py"):
            s=(ROOT/f).read_text("utf-8")
            self.assertNotIn("v3_experimental_paper_technical_gate",s)


if __name__=="__main__":
    unittest.main()
