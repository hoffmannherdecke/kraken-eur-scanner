"""Assemble exact runtime inputs for independent signature; grants no authority."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
REVISION = 'V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001'
MAINTENANCE_SHA = 'ddaba06df17adcf1b1f377cde37befbf9f09f8672f3c30b9863dba4b0a73ffe2'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()


def save_once(path, data):
    if path.exists():
        require(path.read_bytes() == data, f'immutable bytes drift: {path.name}')
        return
    pending = path.with_suffix(path.suffix + '.pending')
    with pending.open('xb') as f:
        f.write(data)
        f.flush()
    pending.rename(path)


def build(window, stage, expected_fixed_inputs_sha256):
    fixed_path = window/'cutover-fixed-inputs.json'
    fixed_bytes = fixed_path.read_bytes()
    require(sha256(fixed_bytes).hexdigest() == expected_fixed_inputs_sha256,
            'fixed PR701 pins drift')
    fixed = json.loads(fixed_bytes)
    require(stage.name == 'V3Paper-INACTIVE-' + fixed['repo_sha'][:12]
            and sha(stage/'v3-paper-inactive-source-manifest.json') == fixed['stage_manifest_sha256'],
            'staged PR701 manifest mismatch')
    gate_source = stage/'tools/v3_experimental_paper_technical_gate.py'
    require(sha(gate_source) == 'd89736ee1df67bcaeb94d48d8dc8b2ed3338177fe5f17a96a780a76df090a9a6',
            'staged gate source mismatch')
    sys.path.insert(0,str(stage))
    from tools import v3_experimental_paper_technical_gate as gate

    plan_path=window/'plan.cas.json'
    plan=read(plan_path)
    stop_plan=read(window/'plan.stop.json')
    review=read(window/'Sechs-Nachweise-zur-unabhaengigen-Freigabe.json')
    action=read(window/'prepared-task-action.json')
    owner=read(window/'stage4-owner-approved.json')
    maintenance=ROOT/'maintenance-originals-for-runtime-review.json'
    require(sha(maintenance)==MAINTENANCE_SHA,'reviewed original maintenance bytes changed')
    m=read(maintenance)
    require(m['current_stage_original_sha256']==fixed['stage_original_sha256']
            and m['release_commit']==fixed['repo_sha'],'maintenance/source binding mismatch')
    require(all(sha256(row['body'].encode()).hexdigest()==row['original_body_sha256']
                and row['author_id']==331995561 for row in m['original_owner_records']),
            'underlying owner record bytes changed')
    for identity in (plan,stop_plan):
        require(all(identity[k]==fixed[k] for k in ('repo_sha','bundle_sha256','strategy_sha256')),'plan identity')
    require(review['release_commit']==owner['release_commit']==action['release_commit']==fixed['repo_sha'],'release commit mismatch')
    require(review['series_id']==action['series_id']==plan['series_id']==owner['successor_series_id'],'series mismatch')
    require(action['epoch_id']==plan['cas_epoch']['epoch_id']==stop_plan['cas_epoch']['epoch_id'],'epoch mismatch')
    require(owner['scope']=='CLOUD_STAGE4_EPOCH_OPEN' and owner['decision']=='ISSUED_FOR_EXACT_RUNTIME_RELEASE'
            and owner['plan_sha256']==review['stage4_plan_sha256']==sha(window/'plan.stage4.json')
            and re.fullmatch(r'https://github\.com/hoffmannherdecke/kraken-eur-scanner/issues/99#issuecomment-[0-9]+',
                             owner['original_approval_url']),'original series assignment mismatch')
    writer,=(row for row in plan['tasks'] if row['name']=='CryptoMiniPC-V3PaperSingleWriter')
    require(writer['xml_sha256']==action['task_xml_sha256'] and sha(Path(writer['xml_path']))==writer['xml_sha256'],
            'prepared Task XML mismatch')
    require(re.fullmatch(r'[a-f0-9]{64}',action['native_task_action_sha256']) is not None
            and action['native_task_launcher_file_sha256']==fixed['artifacts']['paper_evaluator/v3_paper_minipc_native_launcher_v1.py'],
            'prepared Task action mismatch')
    rows=review['verified_content_envelopes']
    sixth,=(row for row in rows if row['id']=='V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN')
    require(sixth['sha256']==owner['dry_run_sha256'],'sixth proof does not match original scope')
    require(len(rows)==6 and {row['id'] for row in rows}==set(gate.PROOFS),'missing original proof')
    packet=dict(kind='SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1',paper_phase='EXPERIMENTAL_PAPER_ONLY',
                status='READY_WITH_EXPLICIT_EXPERIMENTAL_PAPER_APPROVAL',strategy_revision=REVISION,
                explicit_human_release_decision='APPROVED_EXPERIMENTAL_PAPER',paper_only=True,real_money_actions=False,
                automatic_activation=False,code_fingerprint_sha256=fixed['bundle_sha256'],
                strategy_fingerprint_sha256=fixed['strategy_sha256'],primary_decision_route='FREE_RULE_P4',
                historical_proof_reuse='PR692_ORIGINALS_EXACT_STAGE_EQUIVALENCE_V1',
                bounded_research_scope=dict(max_candidates=500,max_observation_days=4,max_model_http_attempts_including_retries=0,
                    deduplicate_pair_clock=True,mandatory_real_6h_24h_and_censored_followups=True,stop_when_budget_exhausted=True),
                frozen_execution_risk=dict(taker_pct_each_side=0.6,scout_eur=50,stage2_eur=50,kraken_online_spot_eur=True,
                    true_pit_1m5m15m_atr_stop=True,full_rule_p4_decision_before_any_paper_buy=True,
                    stop_stage2_spread_slippage_required=True,no_real_orders=True,no_h3_h6_auto_activation=True),
                economic_alpha_claimed=False,post_experiment_promotion_requires_economic_gate=True,
                fixed_api_cost_limit_user_authorized=False,physical_single_writer_cutover_dry_run_passed=True,
                physical_single_writer_cutover_ack_obtained=False,
                experimental_paper_technical_proofs=[dict(row,status='VERIFIED_PHYSICAL_OR_CLOUD_E2E') for row in rows])
    errors=gate.validate_experimental_paper_packet(window,REVISION,packet)
    require(not errors,'; '.join(errors))
    packet_bytes=canonical(packet)
    packet_sha=sha256(packet_bytes).hexdigest()
    authority=dict(native_task_action_sha256=action['native_task_action_sha256'],
                   native_task_launcher_file_sha256=action['native_task_launcher_file_sha256'],
                   runtime_release_packet_file_sha256=packet_sha,approved_six_proof_release_packet_sha256=packet_sha,
                   six_external_original_e2e_proofs_approved=True,
                   successor_series_assignment=dict(release_owner='https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99',
                       decision=owner['decision'],independent_decision_reference=owner['original_approval_url'],
                       successor_series_id=plan['series_id'],repo_sha=fixed['repo_sha'],
                       code_fingerprint_sha256=fixed['bundle_sha256'],strategy_fingerprint_sha256=fixed['strategy_sha256']),
                   maintenance_receipt_sha256=MAINTENANCE_SHA,maintenance_receipt_kind=m['kind'],
                   maintenance_completed_at_utc=m['maintenance_completed_at_utc'],maintenance_release_repo_sha=fixed['repo_sha'],
                   maintenance_cpu_bios_boot_thermal_originalhost_pass=True,
                   maintenance_windows_drivers_reboots_originalhost_pass=True,
                   maintenance_scripts_originalhost_source_ack_pass=True,
                   maintenance_v2r4_restart_and_aftercare_originalhost_pass=True,paper_only=True,real_money_actions=False)
    save_once(window/'runtime-release-packet.json',packet_bytes)
    save_once(window/'reviewed-runtime-start-authority.json',canonical(dict(
        kind='PR701_RUNTIME_INPUTS_PENDING_INDEPENDENT_CMS_V1',plan_sha256=sha(plan_path),
        explicit_lease_hours=95,start_authority=authority,production_authorized=False)))
    print('PR701_RUNTIME_PACKET_INPUTS_BOUND_PENDING_INDEPENDENT_SIGNATURES')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('window',type=Path)
    parser.add_argument('stage',type=Path)
    parser.add_argument('--fixed-inputs-sha256', required=True)
    args=parser.parse_args()
    build(args.window,args.stage,args.fixed_inputs_sha256)
