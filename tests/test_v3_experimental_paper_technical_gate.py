"""No-profit-before-paper is permitted ONLY with actual technical proofs."""
import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.v3_experimental_paper_technical_gate import (
    PROOFS, PROOF_KIND, PROOF_ORIGINS, validate_experimental_paper_packet,
    assess_v3_experimental_source_inventory, BUNDLE_SOURCE, REQUIRED_SOURCE_ANCHORS,
    assess_v3_native_source_import_closure, native_source_closure_readonly_main,
    reconcile_v3_cloud_canary_model_p4_rows,
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
            if key=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E" and origin=="MINIPC_PHYSICAL":
                # Contract fixtures only. These literal hashes/flags are NOT
                # physical ACK, Cloud receipt or evidence of a real model BUY.
                def writer(case,cid,p4_result,fill_result,fill_count):
                    return {
                        "case":case,"series_id":"PAPER-V3-CANARY-TEST-001",
                        "candidate_id":cid,
                        "execution_kind":"PHYSICAL_MINIPC_OFFLINE_MODEL_STUB",
                        "p4_decision":p4_result,
                        "paper_fill_result":fill_result,
                        "paper_fill_count":fill_count,
                        "paper_scout_eur":50,
                        "paper_entry_taker_fee_eur":0.30,
                        "p4_known_at_utc":"2026-10-13T09:30:00Z",
                        "paper_fill_known_at_utc":"2026-10-13T09:30:01Z",
                        "original_native_owner_lock_verified":True,
                        "disk_ledger_readback_verified":True,
                        "no_real_orders":True,
                        "no_provider_model_http_in_dryrun":True,
                        "v2r4_runtime_unchanged":True,
                        "p4_record_sha256":("d" if case=="POSITIVE_BUY_SCOUT" else "c")*64,
                        "native_journal_record_sha256":(
                            "e" if case=="POSITIVE_BUY_SCOUT" else "f")*64,
                    }
                record.update({
                    # An original physical observation cannot predate the
                    # underlying real 16 October model/P4 event.
                    "observed_at_utc":"2026-10-19T09:32:00Z",
                    "original_model_p4_readback":{
                        "model_http_attempts_reserved":1,
                        "model_http_retries":0,
                        "p4_decision":"WAIT",
                        "source_pit_complete":True,
                        "no_real_orders":True,
                        "model_response_id":"CI_REAL_RESPONSE_ID_SHAPE_ONLY",
                        "original_pit_sha256":"a"*64,
                        "original_p4_receipt_sha256":"b"*64,
                        "original_series_id":"PAPER-V3-CANARY-ONESHOT-20261016",
                        "original_candidate_id":"20261016-190002-TIA-EUR-r17497221611485",
                        "original_event_key":"FRESHRECHECK",
                        "model_response_known_at_utc":"2026-10-16T19:04:48.008903Z",
                        "p4_known_at_utc":"2026-10-16T19:04:48.020750Z",
                    },
                    "native_paper_writer_dryrun_cases":[
                        writer("POSITIVE_BUY_SCOUT","CI-BUY-SCOUT-ONE",
                               "BUY_SCOUT","PAPER_FILLED",1),
                        writer("NEGATIVE_REJECT","CI-REJECT-ONE",
                               "REJECT","NO_PAPER_FILL",0),
                    ],
                })
            if key=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E" and origin=="SUPABASE_CLOUD":
                # Production original can only authenticate the real model/P4
                # TIA WAIT source, never the separate synthetic BUY fixture.
                record.update({
                    "cloud_project_id":"nlgzjmqgwueojlyqmoru",
                    "observed_at_utc":"2026-10-19T09:32:00Z",
                    "read_only":True,
                    "cloud_cas_performed":False,
                    "active_paper_series_changed":False,
                    "v2r4_live_strategy_modified":False,
                    "independent_original_receipt_query":True,
                    "same_event_id_reread_no_duplicate_verified":True,
                    "original_model_response_id":"CI_REAL_RESPONSE_ID_SHAPE_ONLY",
                    "original_model_p4_receipt_sha256":"b"*64,
                    "original_model_series_id":"PAPER-V3-CANARY-ONESHOT-20261016",
                    "original_model_candidate_id":"20261016-190002-TIA-EUR-r17497221611485",
                    "original_model_event_key":"FRESHRECHECK",
                    "original_model_response_known_at_utc":"2026-10-16T19:04:48.008903Z",
                    "original_p4_known_at_utc":"2026-10-16T19:04:48.020750Z",
                })
            if key=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E" and origin=="SUPABASE_SANDBOX":
                # An already witnessed historical 16/16 synthetic journal
                # readback from the separate PAUSED/revoked sandbox.
                record.update({
                    "cloud_project_id":"zxyhunwpviafyxyqysne",
                    "observed_at_utc":"2026-10-13T09:32:00Z",
                    "read_only":True,
                    "cloud_cas_performed":False,
                    "active_paper_series_changed":False,
                    "v2r4_live_strategy_modified":False,
                    "historical_independent_original_query_previously_completed":True,
                    "fresh_sandbox_network_access":False,
                    "synthetic_offline_fixtures_only":True,
                    "original_synthetic_event_count":16,
                    "original_historical_join_sha256":
                        "a5f9660f96fd714447566607539d1a05ce700fdab0a779cc457b746dc7dd25d1",
                    "same_event_id_reread_no_duplicate_verified":True,
                    "paper_writer_dryrun_case_readbacks":[
                        {"case":"POSITIVE_BUY_SCOUT",
                         "series_id":"PAPER-V3-CANARY-TEST-001",
                         "candidate_id":"CI-BUY-SCOUT-ONE",
                         "p4_decision":"BUY_SCOUT",
                         "p4_record_sha256":"d"*64,
                         "native_journal_record_sha256":"e"*64,
                         "paper_fill_count":1,"paper_fill_result":"PAPER_FILLED",
                         "cloud_query_readback_verified":True,
                         "orders":False,"real_money_actions":False},
                        {"case":"NEGATIVE_REJECT",
                         "series_id":"PAPER-V3-CANARY-TEST-001",
                         "candidate_id":"CI-REJECT-ONE",
                         "p4_decision":"REJECT",
                         "p4_record_sha256":"c"*64,
                         "native_journal_record_sha256":"f"*64,
                         "paper_fill_count":0,"paper_fill_result":"NO_PAPER_FILL",
                         "cloud_query_readback_verified":True,
                         "orders":False,"real_money_actions":False},
                    ],
                })
            if key=="V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT" and origin=="MINIPC_PHYSICAL":
                record.update({
                    "paper_scout_eur":50,"paper_stage2_eur":50,
                    "taker_fee_pct_each_side":0.6,
                    "paper_entry_fee_eur":0.30,
                })
                for chk in (
                    "stop_below_current_ask_tested",
                    "stage2_above_current_ask_and_ttl_tested",
                    "taker_fee_roundtrip_spread_slippage_counted_tested",
                    "invalid_stop_or_stage2_never_creates_fill_tested",
                    "negative_net_edge_never_creates_fill_tested",
                    "wait_trigger_no_buy_without_new_full_model_p4_tested",
                    "missing_response_id_quarantined_tested",
                    "p4_buy_without_durable_fill_quarantined_tested",
                    "interrupted_http_reservation_never_retried_tested",
                    "duplicate_child_episode_never_bought_twice_tested",
                    "no_real_orders_tested",
                ):
                    record[chk]=True
            if key=="V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE":
                # Structural fixture only; these flags are NEVER real host ACKs.
                record.update({
                    "witnessed_v3_series_id":"PAPER-V3-CANARY-ONESHOT-20261016",
                    "witnessed_v3_candidate_id":"20261016-190002-TIA-EUR-r17497221611485",
                })
                if origin=="MINIPC_PHYSICAL":
                    record.update({
                        "original_v3_single_writer_wait_tick_tested":True,
                        "valid_closed_5m_wait_observation_within_ttl_tested":True,
                        "missing_or_late_wait_ticks_become_unknown_tested":True,
                        "trigger_requires_fresh_full_model_and_p4_tested":True,
                        "no_buy_wait_reject_skip_unknown_followup_routing_tested":True,
                        "prospective_closed_1m_no_historical_backfill_tested":True,
                        "followup_6h24h72h_and_gap_censor_logic_tested":True,
                        "old_v2r4_aftercare_separate_series_preserved_tested":True,
                    })
                if origin=="SUPABASE_CLOUD":
                    record.update({
                        "v3_wait_recheck_expiry_original_readback_verified":True,
                        "v3_no_buy_followup_original_journal_readback_verified":True,
                        "missingness_never_claimed_as_zero_pnl_verified":True,
                        "old_v2r4_aftercare_remains_original_series_verified":True,
                    })
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
            if key=="V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK" and origin=="MINIPC_PHYSICAL":
                record.update({
                    "original_task_identity_and_source_pins_verified":True,
                    "stop_only_candidates_wait_lifecycle_continues":True,
                    "unknown_python_worker_blocks_unclassified":True,
                    "admin_shell_path_reference_not_worker":True,
                    "interrupted_marker_transition_preserves_armed_backup":True,
                    "atomic_marker_repair_has_verified_backup":True,
                    "partial_restore_keeps_fence_until_actual_worker_ack":True,
                    "both_original_worker_heartbeats_advance_after_restart":True,
                    "supervisor_healthy_after_marker_removed":True,
                    "cloudsync_returns_active_original_no_network_hold_cleared":True,
                    "no_v3_cas_or_real_money_actions":True,
                    "final_fence_state":"ABSENT",
                    "restore_boundary":"PRECOMMIT_ORIGINAL_ONLY",
                    "recovery_ack_kind":"REAL_MINIPC_POST_RESTORE_READBACK",
                })
            canonical=json.dumps(record,sort_keys=True,separators=(",",":")).encode()
            originals.append({"origin":origin,"original_id":oid,
                 "original_record":record,
                 "original_sha256":hashlib.sha256(canonical).hexdigest()})
        dest.write_text(json.dumps({"kind":PROOF_KIND,"proof_id":key,
                          "source_originals":originals},sort_keys=True),
                        encoding="utf-8")
        items.append({"id":key,"status":"VERIFIED_PHYSICAL_OR_CLOUD_E2E",
                      "evidence_path":dest.relative_to(root).as_posix(),
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

    def test_evidence_fixture_paths_are_posix_and_backslashes_stay_rejected(self):
        # Release proof paths are canonical repository-relative POSIX paths.
        # pathlib stringification produces backslashes on Windows, causing
        # false invalid-path failures in otherwise valid synthetic fixtures.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            paths=[item["evidence_path"]
                   for item in packet["experimental_paper_technical_proofs"]]
            self.assertEqual(len(paths),len(PROOFS))
            self.assertTrue(all(p.startswith("research/") and "\\\\" not in p
                                for p in paths))
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])
            bad=copy.deepcopy(packet)
            bad["experimental_paper_technical_proofs"][0]["evidence_path"]=(
                paths[0].replace("/", "\\\\"))
            self.assertTrue(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",bad))

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

    def test_first_two_existing_proofs_reject_mismatched_positive_negative_and_costs(self):
        # Hash-correct synthetic claims alone cannot replace independent
        # physical-source review. This tests mandatory content boundaries.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            required=(
                "V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E",
                "V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT",
            )
            variants={
                required[0]:[
                    lambda h:h["original_model_p4_readback"].update(
                        model_http_attempts_reserved=2),
                    lambda h:h["original_model_p4_readback"].update(
                        model_response_id=""),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        paper_fill_count=0),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        paper_fill_result="NO_PAPER_FILL"),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        paper_entry_taker_fee_eur=0.0),
                    lambda h:h["native_paper_writer_dryrun_cases"][1].update(
                        paper_fill_count=1),
                    lambda h:h["native_paper_writer_dryrun_cases"][1].update(
                        candidate_id="CI-BUY-SCOUT-ONE"),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        paper_fill_known_at_utc="2026-10-13T09:29:00Z"),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        disk_ledger_readback_verified=False),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        no_real_orders=False),
                    lambda h:h["native_paper_writer_dryrun_cases"][0].update(
                        native_journal_record_sha256="not-a-physical-hash"),
                ],
                required[1]:[
                    lambda h:h.update(paper_scout_eur=100),
                    lambda h:h.update(paper_stage2_eur=0),
                    lambda h:h.update(taker_fee_pct_each_side=0.0),
                    lambda h:h.update(paper_entry_fee_eur=0),
                    lambda h:h.update(negative_net_edge_never_creates_fill_tested=False),
                    lambda h:h.update(p4_buy_without_durable_fill_quarantined_tested=None),
                    lambda h:h.update(interrupted_http_reservation_never_retried_tested=False),
                    lambda h:h.update(wait_trigger_no_buy_without_new_full_model_p4_tested=False),
                ],
            }
            for proof_id in required:
                row=next(x for x in packet["experimental_paper_technical_proofs"]
                         if x["id"]==proof_id)
                path=root/row["evidence_path"]
                valid=json.loads(path.read_text("utf-8"))
                for modifier in variants[proof_id]:
                    with self.subTest(proof_id=proof_id,modifier=repr(modifier)):
                        broken=copy.deepcopy(valid)
                        host=next(item for item in broken["source_originals"]
                                  if item["origin"]=="MINIPC_PHYSICAL")
                        modifier(host["original_record"])
                        original=json.dumps(host["original_record"],sort_keys=True,
                                            separators=(",",":")).encode()
                        host["original_sha256"]=hashlib.sha256(original).hexdigest()
                        path.write_text(json.dumps(broken,sort_keys=True))
                        row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                        self.assertTrue(validate_experimental_paper_packet(
                            root,"V3-PAPER-EXPERIMENTAL-001",packet),
                            "invalid original model/positive-negative Paper dryrun must block")
                path.write_text(json.dumps(valid,sort_keys=True))
                row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_first_proof_requires_independently_read_same_cloud_paper_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(x for x in packet["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E")
            path=root/row["evidence_path"]
            valid=json.loads(path.read_text("utf-8"))
            changes=[
                lambda p:p.update(source_originals=[
                    x for x in p["source_originals"] if x["origin"]!="SUPABASE_CLOUD"]),
                lambda p:p.update(source_originals=[
                    x for x in p["source_originals"] if x["origin"]!="SUPABASE_SANDBOX"]),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"].update(
                                  historical_independent_original_query_previously_completed=False),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"].update(
                                  original_model_response_id="ANOTHER_RESPONSE"),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"].update(
                                  observed_at_utc="2026-10-13T09:29:59Z"),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"]
                              ["paper_writer_dryrun_case_readbacks"][0].update(
                                  paper_fill_count=0),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"]
                              ["paper_writer_dryrun_case_readbacks"][1].update(
                                  native_journal_record_sha256="9"*64),
                lambda p:next(x for x in p["source_originals"]
                              if x["origin"]=="SUPABASE_SANDBOX")["original_record"]
                              ["paper_writer_dryrun_case_readbacks"][1].update(
                                  real_money_actions=True),
            ]
            for change in changes:
                with self.subTest(change=repr(change)):
                    altered=copy.deepcopy(valid)
                    change(altered)
                    for item in altered["source_originals"]:
                        payload=json.dumps(item["original_record"],sort_keys=True,
                                           separators=(",",":")).encode()
                        item["original_sha256"]=hashlib.sha256(payload).hexdigest()
                    path.write_text(json.dumps(altered,sort_keys=True))
                    row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "a merely rehashed but mismatched Cloud original is NOT a V3 Paper fill")
            path.write_text(json.dumps(valid,sort_keys=True))
            row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_first_proof_pins_real_model_p4_to_same_original_candidate_episode(self):
        # Real production TIA Cloud receipt "received_at" inverted model/P4
        # delivery order, while its SOURCE known_at correctly has model first.
        # No ingestion order or synthetic writer timestamp can substitute.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            proof=next(x for x in packet["experimental_paper_technical_proofs"]
                       if x["id"]=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E")
            target=root/proof["evidence_path"]
            original=json.loads(target.read_text("utf-8"))
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])
            def role(items,name):
                return next(x for x in items if x["origin"]==name)["original_record"]
            changes=[
                lambda xs: role(xs,"MINIPC_PHYSICAL")[
                    "original_model_p4_readback"].update(original_candidate_id=
                        "20261012-064219-ZRO-EUR-r168479886848322"),
                lambda xs: role(xs,"SUPABASE_CLOUD").update(
                    original_model_event_key="FIRST"),
                lambda xs: role(xs,"SUPABASE_CLOUD").update(
                    original_model_series_id="PAPER-V3-CANARY-20261011"),
                lambda xs: role(xs,"SUPABASE_CLOUD").update(
                    original_model_response_known_at_utc="2026-10-16T19:04:48.009999Z"),
                lambda xs: role(xs,"MINIPC_PHYSICAL")[
                    "original_model_p4_readback"].update(
                        p4_known_at_utc="2026-10-16T19:04:47.999999Z"),
                lambda xs: role(xs,"MINIPC_PHYSICAL")[
                    "original_model_p4_readback"].update(
                        model_response_known_at_utc="2026-10-16T19:04:48"),
                lambda xs: role(xs,"MINIPC_PHYSICAL")[
                    "original_model_p4_readback"].update(
                        original_event_key=""),
                # A rehashed original observed before its purported event
                # is impossible, even if candidate IDs and source clock match.
                lambda xs: role(xs,"MINIPC_PHYSICAL").update(
                    observed_at_utc="2026-10-15T19:04:48Z"),
                lambda xs: role(xs,"SUPABASE_CLOUD").update(
                    observed_at_utc="2026-10-15T19:04:48Z"),
            ]
            for change in changes:
                with self.subTest(change=repr(change)):
                    altered=copy.deepcopy(original)
                    change(altered["source_originals"])
                    for item in altered["source_originals"]:
                        encoded=json.dumps(item["original_record"],sort_keys=True,
                                           separators=(",",":")).encode()
                        item["original_sha256"]=hashlib.sha256(encoded).hexdigest()
                    target.write_text(json.dumps(altered,sort_keys=True))
                    proof["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "re-hashed cross-candidate/out-of-time original must not release V3")
            target.write_text(json.dumps(original,sort_keys=True))
            proof["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_first_gate_rejects_mixed_or_wrong_cloud_project_without_new_cas(self):
        # Tests demonstrate that a rehashed cross-project synthetic report
        # cannot pose as the production paid-model readback (or vice versa).
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            proof=next(x for x in packet["experimental_paper_technical_proofs"]
                       if x["id"]=="V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E")
            target=root/proof["evidence_path"]
            original=json.loads(target.read_text("utf-8"))
            for invalid in (
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_CLOUD")
                    ["original_record"].update(cloud_project_id="zxyhunwpviafyxyqysne"),
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_SANDBOX")
                    ["original_record"].update(cloud_project_id="nlgzjmqgwueojlyqmoru"),
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_SANDBOX")
                    ["original_record"].update(fresh_sandbox_network_access=True),
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_SANDBOX")
                    ["original_record"].update(original_historical_join_sha256="e"*64),
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_SANDBOX")
                    ["original_record"].update(original_model_response_id="FORGED"),
                lambda items: next(x for x in items if x["origin"]=="SUPABASE_CLOUD")
                    ["original_record"].update(paper_writer_dryrun_case_readbacks=[]),
                lambda items: items.append(copy.deepcopy(next(
                    x for x in items if x["origin"]=="SUPABASE_SANDBOX"))),
            ):
                with self.subTest(change=repr(invalid)):
                    content=copy.deepcopy(original)
                    invalid(content["source_originals"])
                    for item in content["source_originals"]:
                        original_bytes=json.dumps(
                            item["original_record"],sort_keys=True,
                            separators=(",",":")).encode()
                        item["original_sha256"]=hashlib.sha256(original_bytes).hexdigest()
                    target.write_text(json.dumps(content,sort_keys=True))
                    proof["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet))
            target.write_text(json.dumps(original,sort_keys=True))
            proof["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_v3_journal_wait_no_buy_inheritance_blocks_on_missing_originals(self):
        # All tests use synthetic packets; each edited source record is
        # consistently rehashed to show a valid SHA alone proves no coverage.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(x for x in packet["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE")
            path=root/row["evidence_path"]
            valid=json.loads(path.read_text("utf-8"))
            variants=[]
            for item in valid["source_originals"]:
                for key,value in item["original_record"].items():
                    if value is True:
                        variants.append((item["origin"],key,False))
                        variants.append((item["origin"],key,None))
            variants.extend([
                ("MINIPC_PHYSICAL","witnessed_v3_candidate_id","OTHER-TEST-CANDIDATE"),
                ("SUPABASE_CLOUD","witnessed_v3_series_id","PAPER-V3-WRONG-SERIES-001"),
                ("MINIPC_PHYSICAL","witnessed_v3_series_id","NOT_A_V3_SERIES"),
            ])
            for origin,key,value in variants:
                with self.subTest(origin=origin,key=key,value=value):
                    changed=copy.deepcopy(valid)
                    part=next(i for i in changed["source_originals"]
                              if i["origin"]==origin)
                    part["original_record"][key]=value
                    raw=json.dumps(part["original_record"],sort_keys=True,
                                   separators=(",",":")).encode()
                    part["original_sha256"]=hashlib.sha256(raw).hexdigest()
                    path.write_text(json.dumps(changed,sort_keys=True))
                    row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "missing true TTL/No-BUY/Cloud evidence must block V3")
            path.write_text(json.dumps(valid,sort_keys=True))
            row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

    def test_v3_existing_recovery_proof_requires_failure_and_return_acks(self):
        # Synthetic contract-only fixture; a rehashed claim is not a live
        # receipt. The external owner must separately validate source truth.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            packet=fixture(root)
            row=next(x for x in packet["experimental_paper_technical_proofs"]
                     if x["id"]=="V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK")
            target=root/row["evidence_path"]
            original=json.loads(target.read_text("utf-8"))
            host=original["source_originals"][0]["original_record"]
            bool_fields=[k for k,v in host.items() if v is True]
            cases=[(k,False) for k in bool_fields]
            cases += [(k,None) for k in bool_fields]
            cases += [
                ("final_fence_state","ARMED"),
                ("final_fence_state",None),
                ("restore_boundary","POSTCOMMIT"),
                ("recovery_ack_kind","SOURCE_ONLY_CI"),
            ]
            for key,bad in cases:
                with self.subTest(field=key,bad=bad):
                    changed=copy.deepcopy(original)
                    payload=changed["source_originals"][0]["original_record"]
                    payload[key]=bad
                    raw=json.dumps(payload,sort_keys=True,
                                   separators=(",",":")).encode()
                    changed["source_originals"][0]["original_sha256"]=hashlib.sha256(raw).hexdigest()
                    target.write_text(json.dumps(changed,sort_keys=True))
                    row["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
                    self.assertTrue(validate_experimental_paper_packet(
                        root,"V3-PAPER-EXPERIMENTAL-001",packet),
                        "Unverified physical recovery must block even after rehash")
            target.write_text(json.dumps(original,sort_keys=True))
            row["sha256"]=hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(validate_experimental_paper_packet(
                root,"V3-PAPER-EXPERIMENTAL-001",packet),[])

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


class V3ExistingReleaseSourceInventoryTests(unittest.TestCase):
    """Read-only source facts must never be promoted into live Paper authority."""

    def _sample(self,root:Path)->dict:
        source={
            "kind":"V3_EXPERIMENTAL_PAPER_ALL_LESSONS_POLICY_BUNDLE_V1",
            "strategy_revision":"V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001",
            "status":"CODE_READY_INACTIVE_RUNTIME_NOT_ACTIVATED",
            "scope":"ONLY_EXPERIMENTAL_PAPER_NOT_REAL_MONEY",
            "canonical_modules":{
                "k"+str(i):path for i,path in
                enumerate(sorted(REQUIRED_SOURCE_ANCHORS))
            } | {"extra_module":"paper_evaluator/v3_paper_minipc_one_candidate_v1.py"},
            "entry_priority":[{
                "module":"paper_evaluator/v3_paper_minipc_one_candidate_v1.py",
                "runtime_enabled":False
            } for _ in range(6)],
        }
        target=root/BUNDLE_SOURCE
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(source,sort_keys=True),encoding="utf-8")
        for rel in REQUIRED_SOURCE_ANCHORS:
            dest=root/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text("# synthetic offline source\n",encoding="utf-8")
        return source

    def _assess(self,root:Path):
        result=assess_v3_experimental_source_inventory(root)
        self.assertFalse(result["paper_release_authorized"])
        self.assertFalse(result["physical_runtime_loaded_or_started_here"])
        self.assertFalse(result["real_model_e2e_authenticated_here"])
        self.assertFalse(result["model_api_budget_approved_here"])
        self.assertFalse(result["cloud_successor_cas_or_writer_started_here"])
        self.assertFalse(result["original_writer_stop_rollback_proven_here"])
        self.assertFalse(result["full_transitive_dependency_closure_proven"])
        self.assertTrue(result["candidate_digests_not_release_fingerprints"])
        self.assertEqual(result["authentic_technical_e2e_proofs_credited"],0)
        return result

    def test_native_source_import_closure_is_readonly_and_not_release(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        result=assess_v3_native_source_import_closure(ROOT)
        self.assertTrue(result["static_local_import_closure_complete"],
                        result["errors"])
        self.assertGreater(result["candidate_transitive_file_count"],20)
        self.assertEqual(len(result["candidate_transitive_source_sha256"]),64)
        self.assertFalse(result["actual_loaded_python_bytecode_independently_verified"])
        self.assertFalse(result["physical_mini_pc_or_cloud_release_proven"])
        self.assertFalse(result["paper_release_authorized"])
        self.assertFalse(result["real_money_actions"])
        included={r[0] for r in result["candidate_transitive_files"]}
        self.assertIn("paper_evaluator/v3_paper_minipc_native_launcher_v1.py",included)
        self.assertIn("tools/v3_experimental_paper_technical_gate.py",included)

    def test_native_source_import_closure_rejects_missing_and_linked_source(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        from unittest.mock import patch
        with patch("tools.v3_experimental_paper_technical_gate."
                   "assess_v3_experimental_source_inventory",
                   return_value={"source_inventory_complete":True,
                                 "candidate_source_files":[
                                  "paper_evaluator/not-installed.py"]}):
            report=assess_v3_native_source_import_closure(ROOT)
        self.assertFalse(report["static_local_import_closure_complete"])
        self.assertIn("INCOMPLETE",report["errors"][0])
        self.assertFalse(report["paper_release_authorized"])

    def test_native_source_import_closure_never_needs_runtime_or_network(self):
        from tools.v3_experimental_paper_technical_gate import (
            assess_v3_native_source_import_closure)
        from unittest.mock import patch
        with patch("subprocess.run",side_effect=AssertionError("no subprocess")), \
                patch("socket.create_connection",
                      side_effect=AssertionError("no network")):
            report=assess_v3_native_source_import_closure(ROOT)
        self.assertTrue(report["static_local_import_closure_complete"],report["errors"])


    def test_native_source_closure_cli_is_a_real_nonwriting_readback(self):
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code=native_source_closure_readonly_main(
                ["--source-closure-readonly", "--source-root", str(ROOT)])
        data=json.loads(buf.getvalue())
        self.assertEqual(exit_code,0,data["errors"])
        self.assertEqual(data["inspection_authority"],
                         "SOURCE_ONLY_NO_ORIGINALHOST_OR_CLOUD_ACK")
        self.assertGreater(data["candidate_transitive_file_count"],20)
        self.assertFalse(data["runtime_dependency_versions_verified"])
        self.assertFalse(data["physical_mini_pc_or_cloud_release_proven"])
        self.assertFalse(data["paper_release_authorized"])
        self.assertFalse(data["actual_loaded_python_bytecode_independently_verified"])
        self.assertEqual(set(data["external_import_prefixes_requiring_host_review"])
                         & set(data["stdlib_import_prefixes"]),set())
        self.assertFalse(
            {"paper_series_transition_guard", "v2r4_trigger_contract",
             "v2r4_trigger_plan"} &
            set(data["external_import_prefixes_requiring_host_review"]),
            "Existing local direct-script imports must not appear as pip requirements")
        print("V3_STATIC_RELEASE_STAGE_READBACK", json.dumps({
            "file_count":data["candidate_transitive_file_count"],
            "external_packages":data["external_import_prefixes_requiring_host_review"],
            "dynamic_import_file_count":
                len(data["dynamic_import_source_paths_review_required"]),
            "static_local_import_closure_complete":
                data["static_local_import_closure_complete"],
            "host_versions_verified":False,
        },sort_keys=True))

    def test_real_command_readonly_cli_runs_as_direct_script(self):
        # Python -B keeps this report read-only; Python -I additionally
        # removes the direct tools/ script directory, so the real stage
        # SOURCE listing is a separate command from the -I runtime smoke.
        command=[sys.executable,"-B",
                 str(ROOT/"tools/v3_experimental_paper_technical_gate.py"),
                 "--source-closure-readonly","--source-root",str(ROOT)]
        proc=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,
                            check=False,timeout=30)
        self.assertEqual(proc.returncode,0,proc.stderr[:1500])
        result=json.loads(proc.stdout)
        self.assertTrue(result["static_local_import_closure_complete"],
                        result["errors"])
        self.assertFalse(result["paper_release_authorized"])
        self.assertEqual(result["inspection_authority"],
                         "SOURCE_ONLY_NO_ORIGINALHOST_OR_CLOUD_ACK")

    def test_native_source_closure_cli_rejects_missing_original_source(self):
        with tempfile.TemporaryDirectory() as empty:
            buf=io.StringIO()
            with contextlib.redirect_stdout(buf):
                result=native_source_closure_readonly_main(
                    ["--source-closure-readonly", "--source-root", empty])
            self.assertEqual(result,2)
            payload=json.loads(buf.getvalue())
            self.assertFalse(payload["static_local_import_closure_complete"])
            self.assertFalse(payload["paper_release_authorized"])

    def test_actual_canonical_bundle_has_source_inventory_but_not_release(self):
        r=self._assess(ROOT)
        self.assertTrue(r["source_inventory_complete"],r["source_inventory_errors"])
        self.assertGreaterEqual(r["source_files_count"],18)
        self.assertEqual(len(r["candidate_source_inventory_sha256"]),64)
        self.assertEqual(len(r["candidate_strategy_bundle_source_sha256"]),64)

    def test_inventory_is_stable_and_hash_changes_with_true_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self._sample(root)
            before=self._assess(root)
            repeat=self._assess(root)
            self.assertEqual(before,repeat)
            self.assertTrue(before["source_inventory_complete"])
            self.assertEqual(before["source_files_count"],len(REQUIRED_SOURCE_ANCHORS))
            file=root/"paper_evaluator/v3_paper_minipc_one_candidate_v1.py"
            file.write_text("# changed synthetic source\n",encoding="utf-8")
            after=self._assess(root)
            self.assertTrue(after["source_inventory_complete"])
            self.assertNotEqual(before["candidate_source_inventory_sha256"],
                                after["candidate_source_inventory_sha256"])
            self.assertEqual(before["candidate_strategy_bundle_source_sha256"],
                             after["candidate_strategy_bundle_source_sha256"])

    def test_mutated_bundle_strategy_identity_does_not_change_code_by_itself(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            v=self._sample(root)
            before=self._assess(root)
            v["strategy_revision"]="V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-002"
            (root/BUNDLE_SOURCE).write_text(json.dumps(v),encoding="utf-8")
            after=self._assess(root)
            self.assertNotEqual(before["candidate_strategy_bundle_source_sha256"],
                                after["candidate_strategy_bundle_source_sha256"])
            self.assertNotEqual(before["candidate_source_inventory_sha256"],
                                after["candidate_source_inventory_sha256"])

    def test_missing_module_rejects_not_fake_released(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self._sample(root)
            (root/"paper_evaluator/v3_experimental_paper_journal_v1.py").unlink()
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIsNone(r["candidate_source_inventory_sha256"])
            self.assertIn("V3_MISSING_OR_UNSAFE_REFERENCED_SOURCE",r["source_inventory_errors"])

    def test_malicious_reference_and_false_activation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);v=self._sample(root)
            v["entry_priority"][0]["module"]="../credentials.py"
            v["entry_priority"][1]["runtime_enabled"]=True
            (root/BUNDLE_SOURCE).write_text(json.dumps(v),encoding="utf-8")
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIn("V3_UNSAFE_SOURCE_PATH",r["source_inventory_errors"])
            self.assertIn("V3_SOURCE_MISTAKENLY_RUNTIME_ENABLED",r["source_inventory_errors"])

    def test_missing_entry_module_reference_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);v=self._sample(root)
            v["entry_priority"][0]["module"]=None
            (root/BUNDLE_SOURCE).write_text(json.dumps(v),encoding="utf-8")
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIn("V3_INVALID_ENTRY_MODULE_REFERENCE",
                          r["source_inventory_errors"])

    def test_missing_bundle_and_fake_ready_status_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);v=self._sample(root)
            bundle=root/BUNDLE_SOURCE
            bundle.unlink()
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIn("V3_SOURCE_BUNDLE_UNAVAILABLE_OR_INVALID",
                          r["source_inventory_errors"])
            v["status"]="READY_FOR_V3_REAL_MONEY"
            bundle.write_text(json.dumps(v),encoding="utf-8")
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIn("V3_BUNDLE_NOT_INACTIVE_PAPER_ONLY",
                          r["source_inventory_errors"])

    def test_symlinked_source_rejected_if_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self._sample(root)
            dest=root/"paper_evaluator/v3_experimental_paper_journal_v1.py"
            dest.unlink()
            target=root/"external.py"
            target.write_text("# should be rejected\n",encoding="utf-8")
            try:
                dest.symlink_to(target)
            except (OSError,NotImplementedError):
                self.skipTest("symlink creation unsupported")
            r=self._assess(root)
            self.assertFalse(r["source_inventory_complete"])
            self.assertIn("V3_MISSING_OR_UNSAFE_REFERENCED_SOURCE",
                          r["source_inventory_errors"])


class V3OriginalCloudKnownAtSequenceTests(unittest.TestCase):
    """Pure test rows, not live Supabase, physical host or real paid HTTP."""

    SERIES="PAPER-V3-CANARY-ONESHOT-20261016"
    CANDIDATE="20261016-190002-TIA-EUR-r17497221611485"
    EPISODE="FRESHRECHECK"

    def cloud_rows(self):
        roles=("SOURCE_INPUT","FULL_REVIEW_ELIGIBILITY",
               "MODEL_REQUEST","MODEL_RESPONSE","P4_VALIDATION")
        times=("2026-10-16T19:04:36.169022Z",
               "2026-10-16T19:04:36.181011Z",
               "2026-10-16T19:04:36.194720Z",
               "2026-10-16T19:04:48.008903Z",
               "2026-10-16T19:04:48.020750Z")
        rows=[]
        for phase,known in zip(roles,times):
            result="WAIT" if phase=="P4_VALIDATION" else "PASS"
            payload={
                "series_id":self.SERIES,"candidate_id":self.CANDIDATE,
                "pair":"TIA/EUR","phase":phase,"result":result,
                "event_key":self.EPISODE,"known_at_utc":known,
                "orders":False,"real_money_actions":False,
                "data":({"model_response_id":"resp_CI_STUB_NOT_PAID_HTTP",
                         "model_name":"CI-ONLY"} if phase=="MODEL_RESPONSE"
                        else {}),
            }
            event_id=hashlib.sha256(
                "|".join((self.SERIES,self.CANDIDATE,phase,self.EPISODE))
                .encode()).hexdigest()
            rows.append({
                "series_id":self.SERIES,
                "candidate_id":self.CANDIDATE,
                "pair":"TIA/EUR","phase":phase,"result":result,
                "source_known_at":known,
                # Deliberately cloud upload is NOT known-at order.
                "received_at":"2026-10-16T19:04:49.900000Z",
                "payload":payload,"event_id":event_id,
                "content_sha256":"a"*64,
            })
        return list(reversed(rows))

    def assess(self,rows):
        return reconcile_v3_cloud_canary_model_p4_rows(
            rows,series_id=self.SERIES,candidate_id=self.CANDIDATE,
            event_key=self.EPISODE)

    def test_cloud_upload_out_of_order_uses_original_known_at(self):
        result=self.assess(self.cloud_rows())
        self.assertEqual(result["p4_decision"],"WAIT")
        self.assertEqual(result["technical_release_proofs_credited"],0)
        self.assertFalse(result["cloud_content_bytes_independently_verified"])
        self.assertFalse(result["paper_release_authorized"])
        self.assertFalse(result["independent_host_model_http_verified"])
        self.assertEqual(len(result["cloud_event_ids_by_phase"]),5)

    def test_one_missing_or_duplicate_original_blocks(self):
        rows=self.cloud_rows()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            self.assess(rows[1:])
        with self.assertRaisesRegex(ValueError,"duplicate"):
            self.assess(rows+[copy.deepcopy(rows[0])])

    def test_wrong_canonical_id_or_drifted_candidate_blocks(self):
        rows=self.cloud_rows()
        rows[0]["event_id"]="b"*64
        with self.assertRaisesRegex(ValueError,"canonical"):
            self.assess(rows)
        rows=self.cloud_rows()
        rows[0]["payload"]["candidate_id"]="OTHER-CANDIDATE"
        with self.assertRaisesRegex(ValueError,"identity"):
            self.assess(rows)

    def test_stage_order_from_true_source_time_not_cloud_receipt(self):
        rows=self.cloud_rows()
        # A forged source known-at for P4 predates MODEL_RESPONSE.
        p4=rows[0]
        p4["source_known_at"]="2026-10-16T19:04:30Z"
        p4["payload"]["known_at_utc"]="2026-10-16T19:04:30Z"
        with self.assertRaisesRegex(ValueError,"chronology"):
            self.assess(rows)

    def test_missing_billing_proof_stays_uncredited(self):
        rows=self.cloud_rows()
        rows[1]["payload"]["data"]["model_response_id"]=""
        with self.assertRaisesRegex(ValueError,"identifier"):
            self.assess(rows)
        rows=self.cloud_rows()
        rows[1]["payload"]["orders"]=True
        with self.assertRaisesRegex(ValueError,"identity"):
            self.assess(rows)

    def test_missing_timezone_and_future_ingestion_rejected(self):
        rows=self.cloud_rows()
        rows[0]["source_known_at"]="2026-10-16T19:04:48"
        rows[0]["payload"]["known_at_utc"]="2026-10-16T19:04:48"
        with self.assertRaisesRegex(ValueError,"timestamp"):
            self.assess(rows)
        rows=self.cloud_rows()
        rows[0]["received_at"]="2026-10-16T19:04:00Z"
        with self.assertRaisesRegex(ValueError,"timestamp"):
            self.assess(rows)


if __name__=="__main__":
    unittest.main()
