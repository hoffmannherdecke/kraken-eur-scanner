"""V3 Paper missed-opportunity and correct no-BUY learning, not fake fills.

Mature the SAME 6h/24h observations for SCANNER->SKIP/UNKNOWN/WAIT/REJECT
as for hypothetical BUY. No counterfactual profit calculations without a
valid stop/entry, no later winner is fed into model historical prompt.
"""
from __future__ import annotations
import json,math
from datetime import timedelta
from pathlib import Path
from typing import Any
from paper_evaluator.v3_experimental_paper_journal_v1 import (
    make_receipt,store_receipt_explicitly,clock,
)
from paper_evaluator.v3_paper_minipc_one_candidate_v1 import REVISION
from paper_evaluator.v3_paper_minipc_closed_1m_capture_v1 import require_prospective_assembled_path

def followup_no_buy(*,journal:Path,series_id:str,candidate_id:str,
                    captured_1m:dict[str,Any],hours:int)->dict:
    if hours not in (6,24,72):raise ValueError("unsupported horizon")
    rows=[]
    for p in journal.glob("*.json"):
        r=json.loads(p.read_text("utf-8"))
        if r.get("series_id")==series_id and r.get("candidate_id")==candidate_id:
            rows.append(r)
    first=next((x for x in rows if x["phase"] in (
        "SCANNER_CAPTURE","P1_CHILD_ENROLLMENT")),None)
    if not first:raise ValueError("immutable scanner or P1 episode source absent")
    if any(x["phase"]=="PAPER_FILL" for x in rows):
        raise ValueError("BUY followup must use stop/Stage2 actual paper model")
    phase=f"FOLLOWUP_{hours}H"
    if any(x["phase"]==phase and x["result"] in ("CENSORED","MATURE_COMPLETE") for x in rows):
        return {"status":"NO_BUY_FOLLOWUP_ALREADY_FINAL","hours":hours}
    require_prospective_assembled_path(assembled=captured_1m,pair=first["pair"])
    start=clock(first["event_time_utc"])
    observed=clock(captured_1m["captured_at_utc"])
    due=start+timedelta(hours=hours)
    if observed<due:return {"status":"PENDING_NO_BUY_HORIZON_NOT_MATURE"}
    source_ok=(captured_1m.get("kind")=="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1"
               and captured_1m.get("source")=="KRAKEN_SPOT_EUR_PUBLIC"
               and captured_1m.get("pair")==first["pair"])
    bars=captured_1m.get("closed_bars") if source_ok else None
    contiguous=True
    prices=[]
    base=start.replace(second=0,microsecond=0)
    if base<start:base+=timedelta(minutes=1)
    if not isinstance(bars,list):
        contiguous=False
    else:
        for i in range(hours*60):
            if i>=len(bars) or not isinstance(bars[i],dict):
                contiguous=False;break
            b=bars[i]
            try:
                at=clock(b["start_at_utc"])
                op,hi,lo,cl=[float(b[k]) for k in ("open","high","low","close")]
                if (at!=base+timedelta(minutes=i)
                        or at+timedelta(minutes=1)>observed
                        or not all(math.isfinite(x) for x in (op,hi,lo,cl))
                        or not 0<lo<=min(op,cl)<=max(op,cl)<=hi):
                    contiguous=False;break
                prices.append((hi,lo,cl))
            except (KeyError,TypeError,ValueError,OverflowError):
                contiguous=False;break
    if not contiguous and observed<due+timedelta(minutes=60):
        return {"status":"NO_BUY_1M_GAP_PENDING_RECOVERY"}
    data={"followup_source":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
          "path_contiguous_1m_verified":contiguous,
          "source_status":"NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL"}
    if contiguous:
        # Only descriptive after-event behavior from first complete post-scan
        # close, not real entry Ask and not realized P&L or an alpha claim.
        reference=prices[0][2]
        data.update({
            "mfe_pct":round(100*(max(x[0] for x in prices)/reference-1),6),
            "mae_pct":round(100*(min(x[1] for x in prices)/reference-1),6),
            "close_return_pct":round(100*(prices[-1][2]/reference-1),6),
            "position_net_pnl_eur":None,
            "position_net_return_pct":None,
        })
    else:
        data["censor_reason"]="CENSORED_NO_CONTIGUOUS_CLOSED_KRAKEN_1M_PATH"
    out=make_receipt(
        series_id=series_id,revision=REVISION,candidate_id=candidate_id,
        pair=first["pair"],event_time_utc=first["event_time_utc"],
        known_at_utc=captured_1m["captured_at_utc"],phase=phase,
        result="MATURE_COMPLETE" if contiguous else "CENSORED",
        data=data,event_key=f"NOBUY{hours}H")
    stored,_=store_receipt_explicitly(journal,out)
    return {"status":stored,"hours":hours,"opportunity_only":True,
            "event_result":out["result"],"mfe_pct":data.get("mfe_pct"),
            "mae_pct":data.get("mae_pct"),"net_pnl_eur":None}
