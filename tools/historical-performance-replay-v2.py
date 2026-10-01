#!/usr/bin/env python3
"""Execute frozen EUR15 second-leg confirmation development replay V2.

This is development evidence only. The 2026H1 holdout is not read, labelled,
aggregated, ranked, or otherwise used.

V2 changes one core mechanism relative to rejected V1:
- retain the frozen V1 initial momentum trigger;
- require a subsequent close above the signal-bar high within four contiguous
  15m bars before entry;
- invalidate if a pre-confirmation close falls below the signal-bar low;
- enter only on the next contiguous bar open after confirmation;
- retain the same fixed 4h hold and 1.40% round-trip primary cost.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INTERVAL_SECONDS = 900
EXPECTED_HEADER = [
    "bar_start_epoch","bar_end_epoch","bar_start_utc","bar_end_utc",
    "open","high","low","close","volume","trades",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def normalized_text_sha256(path: Path) -> str:
    text = path.read_text("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iso_epoch(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())


def pct(a: float, b: float) -> float:
    return 100.0 * (a / b - 1.0)


def contiguous(starts: list[int]) -> bool:
    return all((b-a) == INTERVAL_SECONDS for a,b in zip(starts, starts[1:]))


def load_spec(path: Path) -> dict[str,Any]:
    s = json.loads(path.read_text("utf-8"))
    if s.get("kind") != "KRAKEN_EUR15_PERFORMANCE_REPLAY_SPEC_V2":
        raise ValueError("unexpected V2 spec kind")
    if s.get("status") != "FROZEN_PRE_REGISTERED_NOT_YET_EXECUTED":
        raise ValueError("V2 spec is not frozen")
    if s["evaluation_topology"]["sealed_holdout"]["status"] != "LOCKED_DO_NOT_READ_IN_V2_DEVELOPMENT":
        raise ValueError("V2 holdout is not locked")
    return s


def read_pair(path: Path, holdout_start_epoch: int) -> tuple[list[dict[str,Any]], dict[str,Any]]:
    rows: list[dict[str,Any]] = []
    stopped = False
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(f"{path.name}: unexpected normalized header")
        prev = None
        for line_no,row in enumerate(reader,2):
            start = int(row["bar_start_epoch"])
            if start >= holdout_start_epoch:
                stopped = True
                break
            end = int(row["bar_end_epoch"])
            if end-start != INTERVAL_SECONDS:
                raise ValueError(f"{path.name}:{line_no}: invalid bar duration")
            if prev is not None and start <= prev:
                raise ValueError(f"{path.name}:{line_no}: non-monotonic timestamp")
            prev = start
            rows.append({
                "start":start,"end":end,
                "start_utc":row["bar_start_utc"],"end_utc":row["bar_end_utc"],
                "open":float(row["open"]),"high":float(row["high"]),
                "low":float(row["low"]),"close":float(row["close"]),
                "volume":float(row["volume"]),"trades":int(row["trades"]),
            })
    return rows, {"stopped_at_holdout_boundary":stopped,"pre_holdout_rows":len(rows)}


def q(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs)-1)*p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo]*(hi-pos) + xs[hi]*(pos-lo)


def summary(values: list[float]) -> dict[str,Any]:
    if not values:
        return {"count":0,"mean":None,"median":None,"positive_rate":None,"p10":None,"p90":None}
    return {
        "count":len(values),
        "mean":round(statistics.fmean(values),12),
        "median":round(statistics.median(values),12),
        "positive_rate":round(sum(1 for v in values if v>0)/len(values),12),
        "p10":round(q(values,0.10),12),
        "p90":round(q(values,0.90),12),
    }


def deterministic_gzip_jsonl(path: Path, rows: list[dict[str,Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp_name = tempfile.mkstemp(prefix=path.name+".", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with tmp.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz:
                with io.TextIOWrapper(gz, encoding="utf-8", newline="") as out:
                    for row in rows:
                        out.write(json.dumps(row, sort_keys=True, separators=(",",":"))+"\n")
        digest = sha256_file(tmp)
        os.replace(tmp, path)
        return digest
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("normalized_dir", type=Path)
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--normalization-catalog", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--events-output", type=Path, required=True)
    ap.add_argument("--expected-count", type=int, default=648)
    args = ap.parse_args()

    spec = load_spec(args.spec)
    spec_sha = normalized_text_sha256(args.spec)
    norm = json.loads(args.normalization_catalog.read_text("utf-8"))
    if norm.get("status") != "PASS":
        raise SystemExit("normalization catalog status is not PASS")
    if int(norm.get("file_count",-1)) != args.expected_count:
        raise SystemExit("normalization catalog file_count mismatch")

    files = sorted(args.normalized_dir.glob("*EUR_15.normalized.csv.gz"), key=lambda p:p.name.upper())
    if len(files) != args.expected_count:
        raise SystemExit(f"normalized pair count mismatch: expected {args.expected_count}, got {len(files)}")

    topo = spec["evaluation_topology"]
    development_end = iso_epoch(topo["development_seen"]["end_utc_exclusive"])
    holdout_start = iso_epoch(topo["sealed_holdout"]["start_utc"])
    if development_end != holdout_start:
        raise SystemExit("development end and sealed holdout start must match")

    history = int(spec["initial_signal"]["required_contiguous_history_bars"])
    min_trades = int(spec["initial_signal"]["min_trades_last_15m"])
    max_wait = int(spec["confirmation"]["max_wait_bars"])
    hold_bars = int(spec["execution"]["holding_period_bars"])
    cooldown = int(spec["execution"]["same_pair_initial_signal_cooldown_bars"])
    cond = {c["feature"]:float(c["value"]) for c in spec["initial_signal"]["all_conditions_required"]}
    primary_cost = float(spec["cost_model"]["primary_cost_pct_round_trip"])

    events: list[dict[str,Any]] = []
    file_stats: list[dict[str,Any]] = []
    initial_signal_count = 0
    confirmed_count = 0
    invalidated_count = 0
    expired_count = 0
    contiguity_reject_count = 0

    for file_index,path in enumerate(files,1):
        rows,meta = read_pair(path, holdout_start)
        pair = path.name.split("_15.normalized.csv.gz")[0].upper()
        last_initial_idx = -10**12
        pair_initial = pair_confirmed = pair_invalidated = pair_expired = 0

        max_needed_after_signal = max_wait + 1 + hold_bars - 1
        for idx in range(max(history-1,12), len(rows)-max_needed_after_signal):
            if idx <= last_initial_idx + cooldown:
                continue

            hist = rows[idx-(history-1):idx+1]
            if len(hist) != history or not contiguous([r["start"] for r in hist]):
                continue

            signal_bar = rows[idx]
            if signal_bar["end"] >= holdout_start:
                break
            if signal_bar["trades"] < min_trades:
                continue

            mean_vol = statistics.fmean(r["volume"] for r in hist)
            mean_trades = statistics.fmean(r["trades"] for r in hist)
            if mean_vol <= 0 or mean_trades <= 0:
                continue

            features = {
                "return_1h_pct":pct(signal_bar["close"],rows[idx-4]["close"]),
                "return_3h_pct":pct(signal_bar["close"],rows[idx-12]["close"]),
                "volume_ratio_15m_vs_20":signal_bar["volume"]/mean_vol,
                "trades_ratio_15m_vs_20":signal_bar["trades"]/mean_trades,
            }
            if not (
                features["return_1h_pct"] >= cond["return_1h_pct"]
                and features["return_3h_pct"] >= cond["return_3h_pct"]
                and features["volume_ratio_15m_vs_20"] >= cond["volume_ratio_15m_vs_20"]
                and features["trades_ratio_15m_vs_20"] >= cond["trades_ratio_15m_vs_20"]
            ):
                continue

            initial_signal_count += 1
            pair_initial += 1
            last_initial_idx = idx

            confirm_idx = None
            invalidated = False
            prev_start = signal_bar["start"]
            contiguous_wait = True

            for offset in range(1,max_wait+1):
                j = idx+offset
                bar = rows[j]
                if bar["start"] - prev_start != INTERVAL_SECONDS:
                    contiguous_wait = False
                    break
                prev_start = bar["start"]

                if bar["close"] < signal_bar["low"]:
                    invalidated = True
                    break
                if bar["close"] > signal_bar["high"]:
                    confirm_idx = j
                    break

            if not contiguous_wait:
                contiguity_reject_count += 1
                continue
            if invalidated:
                invalidated_count += 1
                pair_invalidated += 1
                continue
            if confirm_idx is None:
                expired_count += 1
                pair_expired += 1
                continue

            entry_idx = confirm_idx + 1
            exit_idx = entry_idx + hold_bars - 1
            if exit_idx >= len(rows):
                continue

            sequence = rows[confirm_idx:exit_idx+1]
            if not contiguous([r["start"] for r in sequence]):
                contiguity_reject_count += 1
                continue
            entry_bar = rows[entry_idx]
            exit_bar = rows[exit_idx]
            if entry_bar["start"] != rows[confirm_idx]["end"]:
                raise AssertionError("entry does not start after confirmation close")
            if exit_bar["end"] > holdout_start:
                continue

            trade_bars = rows[entry_idx:exit_idx+1]
            entry = entry_bar["open"]
            exit_price = exit_bar["close"]
            if entry <= 0 or exit_price <= 0:
                continue

            gross = pct(exit_price,entry)
            mfe = pct(max(r["high"] for r in trade_bars),entry)
            mae = pct(min(r["low"] for r in trade_bars),entry)
            net = gross - primary_cost

            confirmed_count += 1
            pair_confirmed += 1
            events.append({
                "pair":pair,
                "signal_time_utc":signal_bar["end_utc"],
                "confirmation_time_utc":rows[confirm_idx]["end_utc"],
                "confirmation_wait_bars":confirm_idx-idx,
                "entry_time_utc":entry_bar["start_utc"],
                "exit_time_utc":exit_bar["end_utc"],
                "entry_open":entry,
                "exit_close":exit_price,
                "gross_return_pct":round(gross,12),
                "net_return_pct_primary_cost":round(net,12),
                "mfe_pct":round(mfe,12),
                "mae_pct":round(mae,12),
                "signal_features":{k:round(v,12) for k,v in features.items()},
                "signal_bar_high":signal_bar["high"],
                "signal_bar_low":signal_bar["low"],
            })

        file_stats.append({
            "pair":pair,
            "pre_holdout_rows":meta["pre_holdout_rows"],
            "stopped_at_holdout_boundary":meta["stopped_at_holdout_boundary"],
            "initial_signals":pair_initial,
            "confirmed_events":pair_confirmed,
            "invalidated_signals":pair_invalidated,
            "expired_signals":pair_expired,
        })
        if file_index % 25 == 0 or file_index == len(files):
            print(
                f"PERF_V2_SCAN progress={file_index}/{len(files)} "
                f"initial={initial_signal_count} confirmed={confirmed_count}",
                flush=True,
            )

    gross = [float(e["gross_return_pct"]) for e in events]
    net = [float(e["net_return_pct_primary_cost"]) for e in events]
    mfe = [float(e["mfe_pct"]) for e in events]
    mae = [float(e["mae_pct"]) for e in events]
    pair_counts = Counter(str(e["pair"]) for e in events)
    month_counts = Counter(str(e["signal_time_utc"])[:7] for e in events)
    year_counts = Counter(str(e["signal_time_utc"])[:4] for e in events)
    top10_share = (
        sum(v for _,v in pair_counts.most_common(10))/len(events)
        if events else None
    )

    gate_spec = spec["development_gate_before_holdout"]
    net_summary = summary(net)
    gate_checks = {
        "min_confirmed_event_count": len(events) >= int(gate_spec["min_confirmed_event_count"]),
        "mean_net_return_gt_zero": (
            net_summary["mean"] is not None and net_summary["mean"] > 0
        ),
        "median_net_return_gt_zero": (
            net_summary["median"] is not None and net_summary["median"] > 0
        ),
        "positive_net_rate_gte": (
            net_summary["positive_rate"] is not None
            and net_summary["positive_rate"] >= float(gate_spec["require_positive_net_rate_gte"])
        ),
        "top10_pair_event_share_lte": (
            top10_share is not None
            and top10_share <= float(gate_spec["require_top10_pair_event_share_lte"])
        ),
    }
    gate_pass = all(gate_checks.values())
    gate_action = (
        gate_spec["action_if_gate_passes"]
        if gate_pass
        else gate_spec["action_if_gate_fails"]
    )

    events_sha = deterministic_gzip_jsonl(args.events_output, events)
    holdout_events_generated = sum(
        1 for e in events if iso_epoch(e["signal_time_utc"]) >= holdout_start
    )
    if holdout_events_generated:
        raise AssertionError("sealed holdout event leakage detected")

    result = {
        "kind":"KRAKEN_EUR15_PERFORMANCE_REPLAY_V2_DEVELOPMENT_RESULT",
        "status":"PASS",
        "spec":str(args.spec),
        "spec_sha256":spec_sha,
        "normalized_file_count":len(files),
        "initial_signal_count":initial_signal_count,
        "confirmed_event_count":confirmed_count,
        "confirmation_rate":round(confirmed_count/initial_signal_count,12) if initial_signal_count else None,
        "invalidated_signal_count":invalidated_count,
        "expired_signal_count":expired_count,
        "contiguity_reject_count":contiguity_reject_count,
        "development_metrics":{
            "gross":summary(gross),
            "net_primary_cost":net_summary,
            "mfe":summary(mfe),
            "mae":summary(mae),
            "unique_pairs":len(pair_counts),
            "unique_months":len(month_counts),
            "top10_pair_event_share":round(top10_share,12) if top10_share is not None else None,
            "events_by_year":dict(sorted(year_counts.items())),
            "events_by_month":dict(sorted(month_counts.items())),
        },
        "preregistered_development_gate":{
            "pass":gate_pass,
            "checks":gate_checks,
            "action":gate_action,
        },
        "holdout_guard":{
            "holdout_start_utc":topo["sealed_holdout"]["start_utc"],
            "holdout_status":topo["sealed_holdout"]["status"],
            "holdout_events_generated":holdout_events_generated,
            "holdout_metrics_computed":False,
            "holdout_used_for_rule_selection":False,
        },
        "events_output":str(args.events_output),
        "events_output_sha256":events_sha,
        "file_stats":file_stats,
        "guardrails":{
            "network_used":False,
            "active_strategy_changed":False,
            "paper_shadow_runtime_changed":False,
            "real_money_action":False,
            "threshold_sweep_performed":False,
            "horizon_sweep_performed":False,
            "pair_subset_selection_performed":False,
            "month_subset_selection_performed":False,
        },
        "interpretation_guardrail":spec["interpretation_guardrail"],
        "next_gate":spec["next_gate_after_development"],
    }

    args.output.parent.mkdir(parents=True,exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix+".tmp")
    tmp.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n","utf-8")
    os.replace(tmp,args.output)

    compact = {
        "kind":result["kind"],
        "status":result["status"],
        "spec_sha256":spec_sha,
        "initial_signal_count":initial_signal_count,
        "confirmed_event_count":confirmed_count,
        "confirmation_rate":result["confirmation_rate"],
        "net_primary_cost":net_summary,
        "top10_pair_event_share":result["development_metrics"]["top10_pair_event_share"],
        "development_gate":result["preregistered_development_gate"],
        "holdout_guard":result["holdout_guard"],
        "events_output_sha256":events_sha,
        "guardrails":result["guardrails"],
        "next_gate":result["next_gate"],
    }
    print("KRAKEN_EUR15_PERFORMANCE_REPLAY_V2 "+json.dumps(compact,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
