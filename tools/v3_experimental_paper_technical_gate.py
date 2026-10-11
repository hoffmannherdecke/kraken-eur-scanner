"""Optional STRICT technical-only release gate for V3 EXPERIMENTAL PAPER.

Paper is where economics are tested; profitability is NOT a prerequisite to
an exploratory Paper trial. But technical/recording/stop and single-writer
correctness ARE prerequisites. No effects, network, orders or strategy changes.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Any

PROOFS=frozenset({
    "V3_REAL_MODEL_COIN_PIT_P4_INPUT_E2E",
    "V3_FAIL_CLOSED_STOP_STAGE2_FEE_WAIT_CONTRACT",
    "V3_JOURNAL_REASONS_ERRORS_6H24H_FOLLOWUP_CENSURE",
    "V3_SINGLE_WRITER_FENCE_CLOUD_CAS_DRYRUN",
    "V3_MINIPC_SUPERVISOR_STOP_START_ROLLBACK",
    "V3_GITHUB_WORK_ALERT_DYNAMIC_SERIES_ROUTING",
})
SHA=re.compile(r"[0-9a-f]{64}\Z")


def validate_experimental_paper_packet(root: Path, revision: str,
                                       packet: dict[str, Any]) -> list[str]:
    """Return blockers. No approval from a CI fixture or old V3 model budget."""
    errors: list[str]=[]
    def block(why: str)->None:
        errors.append("EXPERIMENTAL_PAPER_BLOCKED: "+why)

    if not revision.startswith("V3-") or packet.get("strategy_revision")!=revision:
        block("exact V3 revision not pinned")
    if (packet.get("kind")!="SUCCESSOR_STRATEGY_CAUSAL_RELEASE_EVIDENCE_V1"
            or packet.get("paper_phase")!="EXPERIMENTAL_PAPER_ONLY"
            or packet.get("status")!="READY_WITH_EXPLICIT_EXPERIMENTAL_PAPER_APPROVAL"):
        block("wrong experimental Paper release packet")
    if (packet.get("explicit_human_release_decision")!="APPROVED_EXPERIMENTAL_PAPER"
            or packet.get("real_money_actions") is not False
            or packet.get("paper_only") is not True
            or packet.get("automatic_activation") is not False):
        block("human-authorized Paper-only and no-auto-start required")
    for k in ("code_fingerprint_sha256","strategy_fingerprint_sha256"):
        v=packet.get(k)
        if not isinstance(v,str) or not SHA.fullmatch(v):
            block("invalid pinned "+k)
    scope=packet.get("bounded_research_scope")
    if not isinstance(scope,dict):
        scope={}
    for k,maximum in (("max_candidates",500),("max_model_http_attempts_including_retries",1000),
                      ("max_observation_days",21)):
        v=scope.get(k)
        if type(v) is not int or not 1<=v<=maximum:
            block("missing/invalid finite "+k)
    for k in ("deduplicate_pair_clock","mandatory_real_6h_24h_and_censored_followups",
              "stop_when_budget_exhausted"):
        if scope.get(k) is not True:
            block("missing "+k)
    risk=packet.get("frozen_execution_risk")
    if not isinstance(risk,dict):
        risk={}
    for k,want in (("taker_pct_each_side",0.6),("scout_eur",50),("stage2_eur",50)):
        if risk.get(k)!=want: block("altered "+k)
    for k in ("kraken_online_spot_eur","true_pit_1m5m15m_atr_stop",
              "full_model_decision_before_any_paper_buy",
              "stop_stage2_spread_slippage_required","no_real_orders",
              "no_h3_h6_auto_activation"):
        if risk.get(k) is not True: block("missing risk "+k)
    if packet.get("economic_alpha_claimed") is not False:
        block("Paper experiment cannot claim economic alpha")
    if packet.get("post_experiment_promotion_requires_economic_gate") is not True:
        block("later economic promotion gate missing")
    if packet.get("fixed_api_cost_limit_user_authorized") is not True:
        block("new fixed-cost budget authorization missing")
    # Pre-cutover requirement is a physically verified dry run, not a
    # POST-cutover ACK (requiring post ACK to authorize cutover is circular).
    # Post-cutover ACK is checked later by the existing cloud+Mini-PC monitors.
    if packet.get("physical_single_writer_cutover_dry_run_passed") is not True:
        block("physical single-writer transition dry run missing")
    if packet.get("physical_single_writer_cutover_ack_obtained") is True:
        block("release packet falsely claims post-cutover ACK before activation")
    rows=packet.get("experimental_paper_technical_proofs")
    if not isinstance(rows,list) or len(rows)!=len(PROOFS) or any(not isinstance(x,dict) for x in rows):
        block("six actual technical evidence rows required")
        return errors
    by_id={x.get("id"):x for x in rows}
    if len(by_id)!=len(rows) or set(by_id)!=PROOFS:
        block("technical proof IDs mismatch or duplicated")
    for name in PROOFS:
        x=by_id.get(name)
        if not isinstance(x,dict):
            continue
        if x.get("status")!="VERIFIED_PHYSICAL_OR_CLOUD_E2E":
            block(name+" not physically verified")
        path=x.get("evidence_path")
        digest=x.get("sha256")
        if (not isinstance(path,str) or not path.startswith("research/")
                or Path(path).is_absolute() or ".." in Path(path).parts):
            block(name+" invalid path")
            continue
        try:
            data=(root/path).read_bytes()
        except OSError:
            block(name+" evidence file not present")
            continue
        if not isinstance(digest,str) or not SHA.fullmatch(digest) or hashlib.sha256(data).hexdigest()!=digest:
            block(name+" evidence SHA mismatch")
    return errors
