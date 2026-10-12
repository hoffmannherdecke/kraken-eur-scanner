"""PIT-safe reuse of existing independent V3 optional research streams.

Do not collect, reschedule or promote H1/H3/H6/H10/H11 here.
The 2h market/source stewardship and research captures remain sole owners.
This bridge exposes time-verified supplied snapshots as MODEL CONTEXT ONLY.
"""
from __future__ import annotations
import math
from datetime import datetime,timezone
from typing import Any

KIND="V3_PAPER_EXISTING_RESEARCH_CONTEXT_BRIDGE_V1"
STREAMS={
 "market_phase_radar":(10800,("regime","confidence","breadth","reversal_observed")),
 "source_stewardship":(86400,("catalog_version","health","replaced_sources","source_quality_summary")),
 "news_sentiment":(21600,("pair","event_id","sentiment","news_category","headline_digest","official_confirmation","official_primary_url","direct_pair_beneficiary","impact_mechanism","coin_relevance_verified")),
 "dynamic_move_radar":(1800,("pair","movement_phase","breadth","velocity_band","rotation_group")),
 "missed_opportunity_learning":(86400,("learning_rule_id","historical_cohort_status","unresolved_data_gaps")),
 "economic_learning":(86400,("current_experiment","mature_6h_count","mature_24h_count","economic_verdict")),
 "minipc_reliability":(600,("scanner_delay_seconds","cloud_lag_seconds","data_capture_health","local_recheck_health")),
 "smart_money_h10":(3600,("pair","event_id","cohort_id","consensus_direction","independent_wallet_count","source_fill_seen_at_utc","confirmed_net_buy_usd","onchain_fills_confirmed","not_self_dealing_checked","coin_relevance_verified","impact_mechanism")),
 "polymarket_h11":(7200,("pair","event_id","market_id","question","yes_midpoint","observed_probability_delta","market_liquidity_usd","market_resolved","direct_positive_outcome_for_pair","coin_relevance_verified","impact_mechanism")),
 # Reuse the existing research owners as optional P-I-T facts, not extra votes.
 "global_market_crosscheck":(3600,("btc_state","eth_state","market_breadth","cross_market_dispersion")),
 "derivatives_h2":(3600,("pair","funding_rate_pct","open_interest_delta_pct","basis_pct","funding_venue","basis_venue")),
 "macro_h5":(21600,("event_id","event_type","event_time_utc","official_publication_at_utc","official_confirmation")),
 "onchain_h8":(21600,("pair","chain","netflow_direction","active_addresses_change_pct","observed_interval_minutes")),
}
# A different coin must never inherit optional coin-specific context.
PAIR_STREAMS={"news_sentiment","smart_money_h10","polymarket_h11","derivatives_h2","onchain_h8"}
def stamp(x:str)->datetime:
    d=datetime.fromisoformat(x.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("naive context clock")
    return d.astimezone(timezone.utc)
def clean(x:Any):
    if x is None or isinstance(x,(bool,str)) and (not isinstance(x,str) or len(x)<=180):
        return x
    if type(x) in (int,float) and math.isfinite(x):return x
    if isinstance(x,list) and len(x)<=12:return [clean(y) for y in x]
    if isinstance(x,dict) and len(x)<=12 and all(isinstance(k,str) and len(k)<=40 for k in x):
        return {k:clean(v) for k,v in x.items()}
    raise ValueError("invalid optional context value")
def fuse_existing_sources(snapshots:dict[str,Any],*,decision_at_utc:str,
                          pair:str|None=None)->dict[str,Any]:
    """One self-contained versioned context, unavailable sources NEVER veto BUY."""
    decision=stamp(decision_at_utc)
    items={}
    for name,(max_age,allowed) in STREAMS.items():
        row=snapshots.get(name)
        out={"state":"NOT_AVAILABLE","hard_veto":False}
        if isinstance(row,dict):
            try:
                # Evidence must be from a SEPARATE actual source owner, not
                # manually fabricated market predictions or post-event prices.
                known=stamp(row["known_at_utc"])
                observed=stamp(row["observed_at_utc"])
                if not observed<=known<=decision:
                    out["state"]="INVALID_FUTURE_OR_REVERSED_CLOCK"
                elif any(stamp(row[key])>known for key in
                         ("first_seen_at_utc","retrieved_at_utc","source_event_at_utc")
                         if key in row):
                    out["state"]="INVALID_FUTURE_OR_REVERSED_CLOCK"
                elif (decision-known).total_seconds()>max_age:
                    out["state"]="STALE_OPTIONAL"
                elif name in PAIR_STREAMS and (pair is None or row.get("pair")!=pair):
                    out["state"]="NOT_ASSOCIABLE_OTHER_PAIR"
                elif row.get("source_verified") is not True:
                    out["state"]="UNVERIFIED_OPTIONAL"
                else:
                    vals={k:clean(row[k]) for k in allowed if k in row}
                    # Polymarket markets are often unrelated to the coin; no
                    # automatic directional signal/consensus for Kraken.
                    if name=="polymarket_h11":
                        vals["not_a_crypto_direction_signal_without_validated_direct_coin_link"]=True
                    if name=="smart_money_h10":
                        vals["not_copy_trading"]=True
                    out={"state":"AVAILABLE_PIT_CONTEXT_ONLY",
                         "hard_veto":False,
                         "source_owner":str(row.get("source_owner",""))[:100],
                         "source_id":str(row.get("source_id",""))[:80],
                         "observed_at_utc":observed.isoformat(),
                         "known_at_utc":known.isoformat(),
                         "values":vals}
            except (ValueError,KeyError,TypeError,OverflowError):
                out={"state":"INVALID_OPTIONAL_SOURCE","hard_veto":False}
        items[name]=out
    return {"kind":KIND,"decision_at_utc":decision_at_utc,
            "optional_failure_never_hard_veto":True,
            "provenance_guards":{"no_future_source_data":True,
                                 "no_hidden_source_gating":True,
                                 "h10_h11_are_read_only_context":True,
                                 "no_auto_strategy_promotion":True},
            "sources":items}
