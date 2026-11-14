"""Assemble the post-STOP CAS request and read-only exact PG17 digest query."""
import argparse
import base64
import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXED = ROOT
REVISION = 'V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001'
STATE = r'C:\Users\ADMIN\Trading\State'
WRITER = 'CryptoMiniPC-V3PaperSingleWriter'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    assert parsed.tzinfo is not None
    return parsed


def write_new(path, value):
    with path.open('xb') as output:
        output.write(value.encode())


def prepare(plan, stop_path, xml_path, cloud, approved_cas_facts, fixed):
    old = load(ROOT / 'v2r4-identity-prewindow.json')
    assert plan['kind'] == 'V3_ONE_TIME_PAPER_RELEASE_PLAN_V1'
    assert all(plan[k] == fixed[k] for k in ('repo_sha','bundle_sha256','strategy_sha256'))
    assert plan['supersession'] == fixed['supersession']
    series = plan['series_id']
    assert re.fullmatch(r'PAPER-V3-[0-9]{8}T[0-9]{6}Z', series)
    created = datetime.strptime(series[9:], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    epoch = plan['cas_epoch']
    assert re.fullmatch(r'V3CAS-AUDIT-[a-f0-9]{32}',epoch['epoch_id'])
    assert epoch['source_sha256'] == fixed['cas_source_sha256']
    assert epoch['caller_acl_sha256'] == fixed['caller_acl_sha256']
    assert re.fullmatch(r'[a-f0-9]{64}', epoch['fence_sha256'])
    release_id = 'V3-ONETIME-' + epoch['epoch_id'].removeprefix('V3CAS-AUDIT-')
    stop = load(stop_path)
    assert stop['state'] == 'QUIESCED' and re.fullmatch(r'[a-f0-9]{64}',stop['approval_sha256'])
    assert approved_cas_facts['kind'] == 'PR700_REVIEWED_CAS_INPUT_FACTS_V1'
    assert approved_cas_facts['series_id'] == series and approved_cas_facts['epoch_id'] == epoch['epoch_id']
    assert approved_cas_facts['original_stop_sha256'] == sha(stop_path)
    assert approved_cas_facts['explicit_human_release_decision'] == 'APPROVED_EXPERIMENTAL_PAPER'
    fact_keys = ('old_followup_owner_preserved', 'physical_v2r4_writer_fence_verified',
                 'supervisor_old_intake_rearm_blocked', 'independent_six_e2e_proofs_verified')
    facts = {k: approved_cas_facts[k] for k in fact_keys}
    assert all(value is True for value in facts.values())
    observed = time(cloud['observed_at_utc'])
    now = datetime.now(timezone.utc)
    assert created <= time(stop['observed_at_utc']) <= observed <= now < created + timedelta(minutes=10)
    assert now - observed <= timedelta(seconds=60)
    assert cloud['proposed_series_id'] == series and cloud['successor_already_present'] is False
    assert cloud['single_active_unique_index_present'] is True
    assert cloud['executor_can_login'] is False and cloud['executor_connlimit'] == cloud['executor_sessions'] == 0
    active, = cloud['active_paper_series']
    assert all(active[k] == old[k] for k in ('series_id','status','strategy_revision','release_repo_sha',
                                             'paper_only','real_money_actions'))
    assert active['strategy_sha256'] == old['strategy_sha'] and active['runtime_sha256'] == old['runtime_sha']
    assert active['automatic_activation'] == old['automatic_activation_allowed'] == 'false'
    for prefix, last in [('candidate','outcome'),('trade','trade')]:
        count = cloud[f'old_{prefix}_count']
        value = cloud[f'old_last_{last}_updated_at']
        assert type(count) is int and count >= 0
        assert value is None and count == 0 or value is not None and time(value) <= observed
    when = created.strftime('%Y-%m-%dT%H:%M:%SZ')
    config = dict(series_id=series, test_id=series, strategy_revision=REVISION, predecessor_series_id=old['series_id'],
                  release_repo_sha=plan['repo_sha'], runtime_bundle_fingerprint_sha256=plan['bundle_sha256'],
                  strategy_fingerprint_sha256=plan['strategy_sha256'], series_started_at_utc=when,
                  paper_phase='EXPERIMENTAL_PAPER_ONLY',
                  explicit_human_release_decision=approved_cas_facts['explicit_human_release_decision'],
                  real_money_actions_enabled=False, automatic_activation_allowed=False, paper_only=True, enabled=True,
                  scout_notional_eur=50, stage2_notional_eur=50, target_completed_paper_trades=20,
                  preinvoke_epoch_id=epoch['epoch_id'],preinvoke_intent_id=str(uuid.uuid4()),
                  preinvoke_source_sha256=epoch['source_sha256'],preinvoke_fence_sha256=epoch['fence_sha256'],
                  preinvoke_caller_acl_sha256=epoch['caller_acl_sha256'],preinvoke_inhibit_receipt_sha256=sha(stop_path),
                  **facts)
    request = dict(expected_old_series_id=old['series_id'], expected_old_release_sha=old['release_repo_sha'],
                   expected_old_strategy_sha256=old['strategy_sha'], expected_old_runtime_sha256=old['runtime_sha'],
                   expected_old_candidate_count=cloud['old_candidate_count'], expected_old_trade_count=cloud['old_trade_count'],
                   expected_old_last_outcome_updated_at=cloud['old_last_outcome_updated_at'],
                   expected_old_last_trade_updated_at=cloud['old_last_trade_updated_at'], proposed_v3_series_id=series,
                   proposed_v3_test_id=series, proposed_v3_revision=REVISION, cutover_at_utc=when, new_v3_config=config,
                   reviewed_new_repo_sha=plan['repo_sha'], reviewed_new_bundle_sha256=plan['bundle_sha256'],
                   reviewed_new_strategy_sha256=plan['strategy_sha256'])
    prepared, = [item for item in plan['tasks'] if item['name'] == WRITER]
    prepared['xml_path'] = STATE + '\\' + release_id + '.v3-disabled.xml'
    prepared['xml_sha256'] = sha(xml_path)
    plan['cas_request'] = request
    sql = (FIXED / 'pr700-cas-request-digest-readonly.sql.in').read_text()
    for key,value in request.items():
        token = '__' + key.upper() + '__'
        assert sql.count(token) == 1
        if value is None:
            literal = 'NULL'
        else:
            text = wire(value) if isinstance(value,dict) else str(value)
            payload = base64.b64encode(text.encode()).decode()
            literal = f"convert_from(decode('{payload}','base64'),'UTF8')"
        sql = sql.replace(token,literal)
    assert not re.search(r'__[A-Z0-9_]+__',sql)
    return plan,sql


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('plan','stop','xml','cloud','reviewed_cas_facts','output'):
        p.add_argument(arg,type=Path)
    p.add_argument('--fixed-inputs', type=Path, required=True)
    p.add_argument('--fixed-inputs-sha256', required=True)
    a = p.parse_args()
    expected_path = a.plan.resolve().parent / 'cutover-fixed-inputs.json'
    if a.fixed_inputs.absolute() != expected_path or a.fixed_inputs.resolve() != expected_path:
        raise ValueError('PR701_FIXED_INPUT_PATH_DRIFT')
    fixed_bytes = a.fixed_inputs.read_bytes()
    if hashlib.sha256(fixed_bytes).hexdigest() != a.fixed_inputs_sha256:
        raise ValueError('PR701_FIXED_INPUT_DRIFT')
    fixed = json.loads(fixed_bytes)
    cloud, = load(a.cloud)
    plan,sql = prepare(load(a.plan),a.stop,a.xml,cloud,load(a.reviewed_cas_facts),fixed)
    a.output.mkdir()
    write_new(a.output/'poststop-plan-pending-postgres-digest.json',wire(plan)+'\n')
    write_new(a.output/'request-digest-readonly.sql',sql)
