"""Read-only selective Kraken Spot EUR 1m capture reuse for V3 Paper followups.

Each invocation does ONE PUBLIC OHLC GET for a TRACKED candidate and persists
only closed 1m bars in a compact, append-only snapshot. Not a new scanner, not
a full market archive, not a scheduler. V2R4 and H3/H6 unchanged.
"""
from __future__ import annotations
import hashlib,json,os,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any

def timestamp(x:str)->datetime:
    d=datetime.fromisoformat(x.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError("timezone-aware clock required")
    return d.astimezone(timezone.utc)
def now()->datetime:return datetime.now(timezone.utc)
def capture_public_1m(*,pair:str,altname:str,outdir:Path,
                      loader=None,clock=now)->dict[str,Any]:
    if not pair.endswith("/EUR") or not altname.isalnum():
        raise ValueError("current confirmed Kraken EUR altname required")
    if not outdir.is_dir() or outdir.is_symlink():
        raise ValueError("host-created local capture directory required")
    if loader is None:
        def loader(symbol):
            query=urllib.parse.urlencode({"pair":symbol,"interval":1})
            request=urllib.request.Request("https://api.kraken.com/0/public/OHLC?"+query,
                        headers={"User-Agent":"v3-mini-pc-followup-spot-readonly/1"})
            with urllib.request.urlopen(request,timeout=9) as response:
                return json.loads(response.read(1_000_000).decode("utf-8"))
    started=clock()
    resp=loader(altname)
    received=clock()
    result=resp.get("result") if isinstance(resp,dict) and not resp.get("error") else None
    if not isinstance(result,dict):
        raise ValueError("Kraken Spot EUR 1m source unavailable")
    entries=[v for k,v in result.items() if k!="last"]
    if len(entries)!=1 or not isinstance(entries[0],list):
        raise ValueError("ambiguous Kraken 1m array")
    rows=[]
    for raw in entries[0]:
        if not isinstance(raw,list) or len(raw)<7:raise ValueError("invalid 1m OHLC")
        at=datetime.fromtimestamp(int(raw[0]),timezone.utc)
        if at+timedelta(minutes=1)>started:continue
        op,hi,lo,close=(float(raw[k]) for k in (1,2,3,4))
        if not 0<lo<=min(op,close)<=max(op,close)<=hi:
            raise ValueError("malformed real Kraken OHLC")
        rows.append({"start_at_utc":at.isoformat(),"open":op,"high":hi,
                     "low":lo,"close":close})
    if not rows:
        raise ValueError("no genuinely closed Kraken Spot EUR minute data")
    rows.sort(key=lambda x:x["start_at_utc"])
    if len({x["start_at_utc"] for x in rows})!=len(rows):
        raise ValueError("duplicate 1m source times")
    # Kraken can return hundreds of historical candles on EVERY 5-minute
    # observation. They were not observed prospectively and would later be
    # rejected by assemble() (maximum supported live lag is 60 minutes).
    # Keep only candles within that exact provenance ceiling: no additional
    # request, no lossy compression of eligible bars, and no unbounded
    # duplicate raw OHLC archives for the future one-writer Paper path.
    returned_closed_count=len(rows)
    rows=[bar for bar in rows
          if received-(timestamp(bar["start_at_utc"])+timedelta(minutes=1))
          <=timedelta(minutes=60)]
    if not rows:
        raise ValueError("no recently witnessed closed Kraken Spot EUR 1m bars")
    report={"kind":"KRAKEN_CLOSED_1M_PATH_SNAPSHOT_V1",
            "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":pair,"altname":altname,
            "observed_at_utc":started.isoformat(),
            "captured_at_utc":received.isoformat(),
            "closed_bars":rows,"orders":False,"real_money_actions":False}
    data=(json.dumps(report,separators=(",",":"),sort_keys=True)+"\n").encode()
    digest=hashlib.sha256(data).hexdigest()
    p=outdir/(digest+".json")
    try:
        with p.open("xb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
    except FileExistsError:
        if p.read_bytes()!=data:raise ValueError("capture digest collision")
    return {"status":"CLOSED_KRAKEN_1M_SNAPSHOT_SAVED",
            "count":len(rows),
            "historical_closed_rows_not_archived":returned_closed_count-len(rows),
            "sha256":digest,"file":str(p),
            "observed_at_utc":started.isoformat(),"captured_at_utc":received.isoformat()}

def assemble(*,snapshots:Path,pair:str,entry_at_utc:str,
             observed_at_utc:str,max_live_capture_lag_minutes:int=15)->dict[str,Any]:
    if not snapshots.is_dir() or snapshots.is_symlink():
        raise ValueError("capture folder missing or symlink")
    if type(max_live_capture_lag_minutes) is not int or not 1<=max_live_capture_lag_minutes<=60:
        raise ValueError("bounded live-capture delay required")
    # No historical backfill from next day's OHLC may masquerade as
    # actually archived capture: only witnessed snapshots count.
    entry=timestamp(entry_at_utc);now_at=timestamp(observed_at_utc)
    all_rows={}
    for p in snapshots.glob("*.json"):
        raw=p.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=p.stem:raise ValueError("corrupt capture SHA")
        snap=json.loads(raw)
        if snap.get("kind")!="KRAKEN_CLOSED_1M_PATH_SNAPSHOT_V1" or snap.get("pair")!=pair:
            continue
        observed=timestamp(snap["observed_at_utc"])
        captured=timestamp(snap["captured_at_utc"])
        if observed>captured or captured>now_at:continue
        for b in snap["closed_bars"]:
            at=timestamp(b["start_at_utc"])
            if at+timedelta(minutes=1)>observed:raise ValueError("open candle found in capture")
            if at<entry:continue
            # Archive provenance: downloading older OHLC now is NOT proof
            # that a live Paper collector witnessed it when it happened.
            if captured-(at+timedelta(minutes=1))>timedelta(minutes=max_live_capture_lag_minutes):
                continue
            key=at.isoformat()
            if key in all_rows and all_rows[key]!=b:
                raise ValueError("different captured prices for same closed 1m")
            all_rows[key]=b
    return {"kind":"KRAKEN_CLOSED_1M_PATH_CAPTURE_V1",
            "source":"KRAKEN_SPOT_EUR_PUBLIC","pair":pair,
            "captured_at_utc":observed_at_utc,
            "closed_bars":[all_rows[k] for k in sorted(all_rows)],
            "source_snapshots_with_conflicts":False,
            "no_future_backfill":True,
            "max_original_snapshot_lag_minutes":max_live_capture_lag_minutes,
            "historical_late_backfill_excluded":True}


def require_prospective_assembled_path(*,assembled:dict[str,Any],pair:str)->None:
    """Structural provenance gate for already assembled public Kraken 1m data.

    This is NOT independent host/Cloud authentication. Actual exchange 1m
    snapshots must already have been verified by assemble(): per-file SHA
    against original persisted bytes, observed/closed clock, original live
    witness lag and immutable duplicate-price rejection. Requiring all of
    its exact status flags prevents callers from directly feeding arbitrary
    timestamp-matching historical OHLC into a mature Paper followup.
    """
    if (not isinstance(assembled,dict)
            or assembled.get("kind")!="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1"
            or assembled.get("source")!="KRAKEN_SPOT_EUR_PUBLIC"
            or assembled.get("pair")!=pair
            or assembled.get("no_future_backfill") is not True
            or assembled.get("historical_late_backfill_excluded") is not True
            or assembled.get("source_snapshots_with_conflicts") is not False):
        raise ValueError("verified prospective assembled Kraken 1m capture required")
    lag=assembled.get("max_original_snapshot_lag_minutes")
    if type(lag) is not int or not 1<=lag<=15:
        raise ValueError("strict 15-minute original source witness lag required")
    bars=assembled.get("closed_bars")
    if not isinstance(bars,list) or len(bars)>5000:
        raise ValueError("bounded verified 1m bars required")
    captured=timestamp(assembled["captured_at_utc"])
    previous=None
    for row in bars:
        if not isinstance(row,dict) or "start_at_utc" not in row:
            raise ValueError("invalid closed minute source row")
        moment=timestamp(row["start_at_utc"])
        if (moment.second!=0 or moment.microsecond!=0
                or moment+timedelta(minutes=1)>captured
                or (previous is not None and moment<=previous)):
            raise ValueError("open duplicate or unordered minute evidence")
        previous=moment

def early_path_coverage(*,assembled:dict[str,Any],entry_at_utc:str,
                        observed_at_utc:str)->dict[str,Any]:
    """Pure early-warning check on ALREADY captured, trustworthy 1m snapshots.

    This is not an OHLC backfill or another source poll. Detect genuine gaps
    before a 6/24h final receipt irreversibly becomes CENSORED. The 2-minute
    stable clock margin excludes the newest exchange candle. An old missing
    minute is not repaired using an OHLC response fetched after the fact.
    """
    if (not isinstance(assembled,dict)
            or assembled.get("kind")!="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1"
            or assembled.get("source")!="KRAKEN_SPOT_EUR_PUBLIC"
            or assembled.get("no_future_backfill") is not True):
        raise ValueError("verified prospective assembled 1m path required")
    bars=assembled.get("closed_bars")
    if not isinstance(bars,list) or len(bars)>5000:
        raise ValueError("bounded closed 1m evidence required")
    at=timestamp(observed_at_utc)
    entry=timestamp(entry_at_utc)
    if at<entry:
        raise ValueError("source observation cannot predate candidate")
    first=entry.replace(second=0,microsecond=0)
    if first<entry:
        first+=timedelta(minutes=1)
    last_stable=(at-timedelta(minutes=2)).replace(second=0,microsecond=0)-timedelta(minutes=1)
    # A single candidate is tracked for at most the already supported 72h.
    last_stable=min(last_stable,first+timedelta(minutes=72*60-1))
    start_times=set()
    for bar in bars:
        if not isinstance(bar,dict):
            raise ValueError("invalid prospective minute evidence")
        t=timestamp(bar["start_at_utc"])
        if t in start_times or t.second or t.microsecond:
            raise ValueError("duplicate or non-minute 1m evidence")
        start_times.add(t)
    missing=0
    first_missing=None
    old_gap=False
    contiguous_prefix=0
    prefix_active=True
    cursor=first
    while cursor<=last_stable:
        if cursor in start_times:
            if prefix_active:
                contiguous_prefix+=1
        else:
            missing+=1
            if first_missing is None:
                first_missing=cursor
            prefix_active=False
            if at-(cursor+timedelta(minutes=1))>timedelta(minutes=15):
                old_gap=True
        cursor+=timedelta(minutes=1)
    expected=max(0,int((last_stable-first).total_seconds()//60)+1)
    status=("WAIT_FIRST_STABLE_MINUTE" if expected==0
            else "SOURCE_1M_GAP_PAST_PROVENANCE_LIMIT" if old_gap
            else "SOURCE_1M_RECENT_GAP_MONITOR" if missing
            else "CONTIGUOUS_PROSPECTIVE_1M_AS_OF_STABLE_CUTOFF")
    return {
        "kind":"V3_EARLY_1M_PROSPECTIVE_COVERAGE_READONLY_V1",
        "status":status,
        "first_expected_start_utc":first.isoformat(),
        "first_missing_start_utc":first_missing.isoformat() if first_missing else None,
        "expected_stable_minutes":expected,
        "missing_stable_minutes":missing,
        "contiguous_prefix_minutes":contiguous_prefix,
        "gap_past_15m_provenance_limit":old_gap,
        "retroactive_market_labels_authorized":False,
        "model_http_calls":0,"new_schedules":0,"orders":False,
    }
