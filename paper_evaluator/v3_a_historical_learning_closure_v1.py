#!/usr/bin/env python3
"""V3-A: close the PRE-SELECTED historical casepack with an explicit decision.

Research only. No price replay, no Kraken/network/API, no paper writer.
Outcome labels are used for AFTER-THE-FACT research comparisons only.
This is a closed learning decision, never a claim of a successful trade.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

KIND="V3_A_EVIDENCE_BOUNDED_STRATEGY_LEARNING_CLOSURE_V1"
SOURCE_KIND="V3_A_RETROSPECTIVE_MATCHED_NO_BUY_CASEPACK_V1"
EXPECTED_LANES={"CONTINUITY":2, "EXTENDED":2, "IGNITION":1, "NONE":1}
EXPECTED_OPPORTUNITY={"STRK/EUR","OP/EUR","BAT/EUR","W/EUR","JUP/EUR","DRV/EUR"}
EXPECTED_CONTROL={"WLD/EUR","GRT/EUR","ORCA/EUR","ALGO/EUR","ADA/EUR","SYN/EUR"}
HARD_COST_FEE_ROUND_TRIP_PCT=1.2


def _number(value: object) -> float:
    if type(value) not in (int,float):
        raise ValueError("non-numeric research label")
    n=float(value)
    if not math.isfinite(n):
        raise ValueError("non-finite research label")
    return n


def classify(manifest: dict) -> dict:
    """Classify original-known versus future outcomes, preserving frozen pairs."""
    if manifest.get("kind")!=SOURCE_KIND or manifest.get("status")!="RETROSPECTIVE_HYPOTHESIS_PANEL_NOT_MODEL_REPLAY":
        raise ValueError("not the frozen original research manifest")
    cases=manifest.get("cases")
    if not isinstance(cases,list) or len(cases)!=12 or manifest.get("sample_size")!=12:
        raise ValueError("casepack cohort cannot be resized")
    if manifest.get("favorable_selected")!=6 or manifest.get("adverse_controls")!=6:
        raise ValueError("six-vs-six selection must remain frozen")
    if (manifest.get("point_in_time_source_inventory",{}).get("coin_specific_1m_5m_15m_ohlc_volume_atr")
            != "ABSENT_FROM_PERSISTED_FIRST_EVALUATOR_INPUT; HISTORICAL_CLOSED_BARS_AT_T0_NOT_VERIFIED"):
        raise ValueError("historical input provenance changed; independent re-audit required")
    groups=defaultdict(lambda: {"OPPORTUNITY":[],"ADVERSE_CONTROL":[]})
    ids=set()
    pairs=set()
    results=[]
    for case in cases:
        lane=case.get("setup_lane")
        category=case.get("outcome_stratum")
        pair=case.get("pair")
        cid=case.get("candidate_id")
        if (lane not in EXPECTED_LANES or category not in ("OPPORTUNITY","ADVERSE_CONTROL")
                or not isinstance(cid,str) or cid in ids
                or not isinstance(pair,str) or pair in pairs
                or (category=="OPPORTUNITY" and pair not in EXPECTED_OPPORTUNITY)
                or (category=="ADVERSE_CONTROL" and pair not in EXPECTED_CONTROL)):
            raise ValueError("cohort, pair or lane drift")
        ids.add(cid);pairs.add(pair)
        if case.get("initial_decision") not in ("WAIT","REJECT"):
            raise ValueError("not an original no-BUY")
        if case.get("final_decision")!="REJECT" or case.get("validated_v3_buy") is not False:
            raise ValueError("unexpected purchase claim in historical source")
        if case.get("at_time_closed_coin_1m_5m_15m_complete_evidence")!="NOT_VERIFIED":
            raise ValueError("historical closed-coin PIT re-audit required")
        if case.get("at_time_h10_closed_30m_records_in_prior_3h")!=0 or case.get("at_time_h10_5m_records_in_prior_3h")!=0:
            raise ValueError("future H10 cannot become historical signal")
        spread=_number(case.get("initial_spread_pct"))
        mfe=_number(case.get("mfe24_pct"))
        mae=_number(case.get("mae24_pct"))
        end=_number(case.get("close24_pct"))
        if spread<0 or not -100<=mae<=end<=mfe:
            raise ValueError("unreliable horizon ordering")
        groups[lane][category].append(case)
        results.append({
            "candidate_id":cid,
            "pair":pair,
            "initial_lane":lane,
            "initial_decision":case["initial_decision"],
            "final_decision":case["final_decision"],
            "risk_control_or_opportunity_research_label":category,
            "source_original_decision_utc":case["original_evaluation_utc"],
            "source_model_context_closed_coin_PIT_proven":False,
            "valid_historical_v3_replay":False,
            "post_event_24h_mfe_pct":mfe,
            "post_event_24h_mae_pct":mae,
            "post_event_24h_close_pct":end,
            "initial_public_spread_pct":spread,
            "realized_net_pnl_eur":None,
            "valid_executable_buy_path":False,
            "release_economic_outcome_inferred":False,
            "missing_evidence":["HISTORICAL_KRAKEN_COIN_1M5M15M_OHLC_ATR_KNOWN_AT",
                                "MODEL_CONSUMER_FULL_ENTRY_STOP_STAGE2_AT_T0",
                                "ORDER_FILL_STOP_FIRST_6H24H_PATH_NET"],
        })
    for lane,n in EXPECTED_LANES.items():
        if (len(groups[lane]["OPPORTUNITY"])!=n or
                len(groups[lane]["ADVERSE_CONTROL"])!=n):
            raise ValueError("case-matching stratum changed")
    return {
        "kind":KIND,
        "status":"HISTORICAL_DIAGNOSTIC_LEARNING_CLOSED_ECONOMIC_RELEASE_NOT_PROVEN",
        "panel_selection":"OUTCOME_CONDITIONED_HINDSIGHT_NO_CAUSAL_EFFECT_OR_TRADE_WIN_RATE",
        "sample_size":12, "favorable_selected":6, "adverse_controls":6,
        "exact_lane_match_maintained":True,
        "retrospective_outcomes_are_only_labels":True,
        "historical_coin_PIT_v3_replay_eligible":0,
        "verified_economic_buy_paths":0,
        "net_pnl_sum_eur":None,
        "net_expected_value_proven":False,
        "fee_pct_per_side":HARD_COST_FEE_ROUND_TRIP_PCT/2,
        "model_calls":0, "shadow_started":False, "orders":False,
        "paper_writer_started":False, "v2r4_changed":False,
        "real_money_actions":False,
        "learning_decision":{
            "ADOPT_V3_INACTIVE_ENGINEERING_FIXES":[
                "P0_CLOSED_KRAKEN_COIN_1M_5M_15M_ATR_STOP_INPUT_TO_REAL_MODEL_CONSUMER",
                "P4_VALID_DETERMINISTIC_WAIT_WATCH_GRAMMAR",
                "P0_P3_P4_EVIDENCE_REVIEW_RECEIPTS_WITH_KNOWN_AT_AND_MODEL_RESPONSE_CLOCKS",
                "P8_ECONOMIC_OUTCOME_AND_CENSORING_LEDGER_SAME_COHORT_6H24H",
            ],
            "HOLD_OR_REJECT_WITH_EVIDENCE":[
                "NO_RETRO_P4_BUY_REPLAY_WITHOUT_AUTHENTIC_KNOWN_AT_SOURCE",
                "NO_PROMOTE_ANY_EXTENDED_OR_WAIT_TO_BUY_BY_OUTCOME_LABEL",
                "NO_STRATEGY_RULE_RELEASE_FROM_THIS_12_CASE_PANEL",
                "NO_CLASSIFY_POSITIVE_MFE_AS_NET_PROFIT",
            ],
            "FUTURE_SEPARATE_CAUSAL_HYPOTHESIS":
                "ONE_CHANGE_EARLY_FRESH_P3_CONFIRMATION_VS_STANDARD_SAME_CLOCK_WITH_VALID_STOP_COSTS",
            "strategy_rule_cutover_authorized":False,
            "model_budget_authorized_by_this_decision":False,
            "real_trade_inferred":False,
        },
        "cases":results,
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--casepack",type=Path,required=True)
    args=ap.parse_args()
    source=json.loads(args.casepack.read_text(encoding="utf-8"))
    result=classify(source)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
