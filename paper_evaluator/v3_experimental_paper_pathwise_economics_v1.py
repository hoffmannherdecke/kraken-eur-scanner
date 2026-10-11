"""V3 experimental Paper only: conservative ordered Kraken 1m path economics.

1m public trade OHLC cannot prove exchange best bid/ask or order execution.
All paths are ESTIMATES; they MUST NEVER be treated as actual filled trades,
guaranteed profits or real historical live-PIT model decisions.

A fully continuous clock-ordered path is mandatory; ambiguous minute with
BOTH stop and stage2 assumes STOP FIRST. Pessimistic gap stop fill, expenses
for entry/exit and stage2 are independently included. No network/model/IO.
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any
from paper_evaluator.v3_entry_handoff_probe import utc

KIND="V3_EXPERIMENTAL_PAPER_PATHWISE_ECONOMICS_ESTIMATE_V1"
HORIZONS={360,1440,4320}


def _n(v:Any,allow_zero:bool=False)->float:
    if type(v) not in (float,int):
        raise ValueError("finite decimal price or cost required")
    f=float(v)
    if not math.isfinite(f) or (f<0 if allow_zero else f<=0):
        raise ValueError("invalid finite positive or nonnegative amount")
    return f


def estimate_closed_1m_paper_path(
    *,candidate_id:str,pair:str,entry_at_utc:str,observed_at_utc:str,
    entry_ask_eur:float,stop_eur:float,stage2_trigger_eur:float,
    stage2_ttl_minutes:int,closed_1m_bars:list[dict[str,Any]],
    horizon_minutes:int,
    scout_eur:float=50.0,stage2_eur:float=50.0,
    taker_fee_pct_each_side:float=0.6,
    spread_assumption_pct:float=0.2,slippage_pct_each_side:float=0.08
)->dict[str,Any]:
    """Conservative virtual entry at real initial ask, then synthetic bid exits.

    Caller MUST prove Kraken closed 1m provenance and preserve price source and
    real observed clocks in the independent V3 event journal. A source gap is
    CENSORED, NOT ZERO-PROFIT, even when price rose later.
    """
    out={"kind":KIND,"candidate_id":candidate_id,"pair":pair,
         "horizon_minutes":horizon_minutes,
         "status":"UNKNOWN_NOT_EVALUATED",
         "net_pnl_eur":None,"net_return_pct":None,
         "economic_edge_or_fill_real_world_proven":False,
         "paper_only":True,"real_money_actions":False,"orders":False,
         "path_is_estimate_not_exchange_trade":True,
         "fee_pct_each_side":taker_fee_pct_each_side,
         "no_intrabar_lookahead":True}
    if (not isinstance(candidate_id,str) or not candidate_id
            or not isinstance(pair,str) or not pair.endswith("/EUR")
            or horizon_minutes not in HORIZONS or type(stage2_ttl_minutes) is not int
            or not 1<=stage2_ttl_minutes<=60):
        return {**out,"status":"UNKNOWN_INVALID_PAPER_IDENTITY_OR_HORIZON"}
    try:
        entry=utc(entry_at_utc)
        observed=utc(observed_at_utc)
        ask=_n(entry_ask_eur)
        stop=_n(stop_eur)
        stage2=_n(stage2_trigger_eur)
        scout=_n(scout_eur);stage2_nominal=_n(stage2_eur)
        fee=_n(taker_fee_pct_each_side,True)/100
        spread=_n(spread_assumption_pct,True)/100
        slip=_n(slippage_pct_each_side,True)/100
        if not (0<stop<ask<stage2 and 0<=fee<=.05 and 0<=spread<=.1 and 0<=slip<=.1):
            raise ValueError("paper risk or fees not valid")
        if observed<entry+timedelta(minutes=horizon_minutes):
            return {**out,"status":"CENSORED_HORIZON_NOT_YET_MATURE"}
        if not isinstance(closed_1m_bars,list) or not closed_1m_bars:
            return {**out,"status":"CENSORED_NO_CLOSED_ONE_MINUTE_PATH"}
        # Use only completely closed bars strictly AFTER decision/entry.
        first=entry.replace(second=0,microsecond=0)
        if first<entry:
            first+=timedelta(minutes=1)
        target=entry+timedelta(minutes=horizon_minutes)
        seq=[]
        previous=None
        for bar in closed_1m_bars:
            if not isinstance(bar,dict):
                raise ValueError("invalid bar source")
            start=utc(bar["start_at_utc"])
            if start<first:
                # Caller must never silently "recover" from truncated first bar
                # with a hindsight partial OHLC.
                raise ValueError("pre-entry candle masquerading as entry path")
            if not seq and start!=first:
                return {**out,"status":"CENSORED_MISSING_FIRST_POST_ENTRY_BAR"}
            if previous is not None and start-previous!=timedelta(minutes=1):
                return {**out,"status":"CENSORED_NONCONTIGUOUS_ONE_MINUTE_PATH"}
            previous=start
            if start+timedelta(minutes=1)>observed:
                return {**out,"status":"CENSORED_UNCLOSED_ONE_MINUTE_BAR"}
            op=_n(bar["open"]);hi=_n(bar["high"])
            lo=_n(bar["low"]);cl=_n(bar["close"])
            if not lo<=min(op,cl)<=max(op,cl)<=hi:
                raise ValueError("invalid closed OHLC")
            seq.append((start,op,hi,lo,cl))
            if start+timedelta(minutes=1)>=target:
                break
        if not seq or seq[-1][0]+timedelta(minutes=1)<target:
            return {**out,"status":"CENSORED_INCOMPLETE_HORIZON_PRICE_PATH",
                    "valid_post_entry_bars":len(seq)}
        # Conservative euro notionals are 50/50, entry fees additional.
        fill1=ask*(1+slip)
        q1=scout/fill1
        entry_total=scout*(1+fee)
        qty=q1
        stage2_done=False
        stage2_fill=None
        exited=False
        exit_reason="HORIZON"
        exit_at=None
        exit_trade_price=None
        ambig=False
        stop_clock=None
        early_window=entry+timedelta(minutes=stage2_ttl_minutes)
        running_hi=ask
        running_lo=ask
        for at,op,hi,lo,cl in seq:
            running_hi=max(running_hi,hi)
            running_lo=min(running_lo,lo)
            # Stop is the active downside protection from first minute;
            # when OHLC touches BOTH stop and stage2 in same minute, EXIT
            # first (conservative ordering, never hindsight stage2-profit).
            if lo<=stop:
                exited=True
                exit_reason="STOP"
                stop_clock=at.isoformat()
                exit_at=at
                exit_trade_price=min(op,stop)
                ambig=hi>=stage2 and not stage2_done
                break
            # Stage2 is NOT a free immediate second buy. It requires a
            # later timestamped public-price confirmation while TTL valid.
            if not stage2_done and at<early_window and hi>=stage2:
                stage2_fill=max(stage2,op)*(1+spread/2+slip)
                qty+=stage2_nominal/stage2_fill
                entry_total+=stage2_nominal*(1+fee)
                stage2_done=True
        if not exited:
            exit_at,op,hi,lo,cl=seq[-1]
            exit_trade_price=cl
        # Exit at a pessimistic synthetic bid, including slippage. Gaps
        # through stop are penalized by selecting min(open,stop).
        synthetic_bid=exit_trade_price*(1-spread/2)*(1-slip)
        proceeds=qty*synthetic_bid*(1-fee)
        pnl=proceeds-entry_total
        return {
            **out,"status":"MATURE_ESTIMATED_PAPER_NET_NOT_VERIFIED_FILL",
            "net_pnl_eur":round(pnl,6),
            "net_return_pct":round(100*pnl/entry_total,6),
            "actual_economic_edge_proven":False,
            "scout_assumed_entry_ask_eur":ask,
            "scout_modelled_fill_eur":round(fill1,10),
            "scout_qty":round(q1,10),
            "stage2_trigger_eur":stage2,
            "stage2_modelled_filled":stage2_done,
            "stage2_modelled_fill_eur":None if stage2_fill is None else round(stage2_fill,10),
            "total_invested_including_buy_fees_eur":round(entry_total,6),
            "exit_reason":exit_reason,
            "exit_at_utc":exit_at.isoformat(),
            "exit_synthetic_bid_eur":round(synthetic_bid,10),
            "stop_first_when_bar_ambiguous":ambig,
            "first_stop_touched_at_utc":stop_clock,
            "gross_mfe_from_entry_ask_pct":round(100*(running_hi/ask-1),6),
            "gross_mae_from_entry_ask_pct":round(100*(running_lo/ask-1),6),
            "closed_1m_bars_processed":len(seq),
            "applied_exit_spread_assumption_pct":spread_assumption_pct,
            "applied_slippage_pct_each_side":slippage_pct_each_side,
            "fill_assumptions":"INITIAL_KRAKEN_ASK; STAGE2_TRADE_HIGH_APPROX; STOP_FIRST_GAP_CONSERVATIVE; FINAL_SYNTHETIC_BID",
            "known_limit":"No actual book/fill evidence, dynamic exit spread or intrabar trade sequencing",
        }
    except (ValueError,KeyError,TypeError,OverflowError,AttributeError):
        return {**out,"status":"UNKNOWN_INVALID_PRICE_RISK_OR_CLOCK_PROVENANCE"}
