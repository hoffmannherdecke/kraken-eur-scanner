param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$Branch = "prep/v2r4-refresh-20261001"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$keyFile = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$heartbeat = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"
$tempRoot = Join-Path $TradingRoot "Temp"

foreach ($p in @($repo,$python,$keyFile,$heartbeat,$tempRoot)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
$hbTime = [datetime]$hb.checked_at_utc
$hbAge = [math]::Round(((Get-Date).ToUniversalTime() - $hbTime.ToUniversalTime()).TotalSeconds,1)
if ($hb.status -ne "HEALTHY" -or $hbAge -gt 30) {
  throw ("Kraken canary is not fresh/healthy: status=" + $hb.status + " age_sec=" + $hbAge)
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$worktree = Join-Path $tempRoot ("v2r4-wait-runtime-smoke-code-" + $stamp)
$caseRoot = Join-Path $tempRoot ("v2r4-wait-runtime-smoke-case-" + $stamp)
New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null

Write-Host "[V2R4-WAIT-RUNTIME] 1/7 Fetch isolated refreshed candidate branch"
Push-Location $repo
try {
  & git fetch origin $Branch
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
  $branchSha = (& git rev-parse ("origin/" + $Branch)).Trim()
  & git worktree add --detach $worktree ("origin/" + $Branch)
  if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }
} finally {
  Pop-Location
}

try {
  Push-Location $worktree
  try {
    Write-Host "[V2R4-WAIT-RUNTIME] 2/7 Compile runtime sources"
    $compileArgs = @(
      "-m","py_compile",
      "paper_evaluator/v2r4_trigger_contract.py",
      "paper_evaluator/v2r4_trigger_plan.py",
      "paper_evaluator/v2r4_wait_watcher.py",
      "paper_evaluator/v2r4_local_recheck.py",
      "paper_evaluator/v2r4_wait_runtime.py"
    )
    & $python @compileArgs
    if ($LASTEXITCODE -ne 0) { throw "V2R4 WAIT runtime compile failed" }

    Write-Host "[V2R4-WAIT-RUNTIME] 3/7 Prepare isolated candidate, WAIT plan and local Altrady wakeup hint"
    $prepare = @'
import json,sys,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan

root=Path(sys.argv[1])
now=datetime.now(timezone.utc)
ts=int(now.timestamp())
cid=f"{now.strftime('%Y%m%d-%H%M%S')}-BTC-EUR-r0"

q=urllib.parse.urlencode({"pair":"XBTEUR"})
req=urllib.request.Request(
    "https://api.kraken.com/0/public/Ticker?"+q,
    headers={"User-Agent":"minipc-v2r4-wait-runtime-smoke"},
)
with urllib.request.urlopen(req,timeout=15) as r:
    payload=json.loads(r.read().decode())
if payload.get("error"):
    raise RuntimeError(payload["error"])
row=next(iter(payload["result"].values()))
price=float(row["c"][0])

candidate={
  "schema_version":1,
  "kind":"CANONICAL_CANDIDATE_HANDOFF_V1",
  "candidate_id":cid,
  "queue_id":f"0:BTC-EUR:{ts}",
  "source_scanner_run_id":0,
  "event_time_utc":now.isoformat().replace("+00:00","Z"),
  "event_ts":ts,
  "pair":"BTC/EUR",
  "altname":"XBTEUR",
  "action":"REVIEW_ONLY_NOT_ORDER",
  "scanner_candidate":{
    "pair":"BTC/EUR","altname":"XBTEUR","price":price,"score":8.0,
    "ret15_live":0.0,"ret1h":0.0,"ret3h":0.0,"ret24h":0.0,
    "volume_ratio_closed":1.0,"volume_ratio_live":1.0,
    "late":False,"fresh_move_3h":0.0,"spread_pct":0.1,
    "turnover24h":1000000000.0
  },
  "scanner_market_context":{
    "schema_version":1,"pair":"BTC/EUR","altname":"XBTEUR",
    "sensor_price_eur":price,
    "source":"synthetic_wait_runtime_smoke_with_live_kraken_ticker"
  },
  "scanner_market_breadth":{"positive_1h_count":1,"positive_3h_count":1},
  "timing":{
    "candidate_detected_at_utc":now.isoformat().replace("+00:00","Z"),
    "candidate_detected_ts":ts,
    "candidate_snapshot_at_utc":now.isoformat().replace("+00:00","Z"),
    "handoff_written_at_utc":now.isoformat().replace("+00:00","Z"),
    "scan_step_started_at_utc":now.isoformat().replace("+00:00","Z")
  }
}

decision={
  "decision":"WAIT",
  "ttl_minutes":10,
  "watch_conditions":[{"metric":"spread_pct","op":"<=","value":100.0}]
}
plan=build_wait_trigger_plan(candidate,decision,now)

for name in ("decisions","candidates","rechecks","receipts","state","logs"):
    (root/name).mkdir(parents=True,exist_ok=True)

(root/"candidates"/f"{cid}.json").write_text(json.dumps(candidate,indent=2)+"\n","utf-8")
(root/"decisions"/f"{cid}.json").write_text(
    json.dumps({"v2r4_trigger_plan":plan},indent=2)+"\n","utf-8"
)

hint={
  "kind":"ALTRADY_TRIGGER_RECEIVED_V1",
  "received_by_minipc_at_utc":now.isoformat().replace("+00:00","Z"),
  "event":{"id":"SYNTHETIC-WAKEUP","exchange":"KRAKEN","symbol":"XXBTZEUR"},
  "strategy_action":"NONE_TRANSPORT_ONLY"
}
(root/"logs"/"altrady-trigger-events.jsonl").write_text(
    json.dumps(hint,separators=(",",":"))+"\n","utf-8"
)

control={
  "enabled":True,
  "test_id":"V2R4-WAIT-RUNTIME-SMOKE",
  "series_id":"PAPER-V2R4-WAIT-RUNTIME-SMOKE",
  "strategy_revision":"V2R4-PROPOSED-2026-09-30-PRECANDIDATE",
  "series_started_at_utc":(now-timedelta(minutes=2)).isoformat().replace("+00:00","Z"),
  "target_completed_paper_trades":1,
  "real_money_actions_enabled":False
}
(root/"control.json").write_text(json.dumps(control,indent=2)+"\n","utf-8")
print(cid,price)
'@
    $prepare | & $python - $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "smoke fixture preparation failed" }

    Copy-Item "research\v2r4\paper_strategy_spec_v2r4_proposed.json" (Join-Path $caseRoot "spec.json")

    Write-Host "[V2R4-WAIT-RUNTIME] 4/7 Execute one bounded wakeup -> Kraken condition -> fresh PAPER recheck cycle"
    $runArgs = @(
      "paper_evaluator/v2r4_wait_runtime.py",
      "--once",
      "--execute-recheck",
      "--decision-dir",(Join-Path $caseRoot "decisions"),
      "--recheck-dir",(Join-Path $caseRoot "rechecks"),
      "--candidate-dir",(Join-Path $caseRoot "candidates"),
      "--receipt-dir",(Join-Path $caseRoot "receipts"),
      "--state",(Join-Path $caseRoot "state\wait-runtime-state.json"),
      "--heartbeat",(Join-Path $caseRoot "state\wait-runtime-heartbeat.json"),
      "--altrady-log",(Join-Path $caseRoot "logs\altrady-trigger-events.jsonl"),
      "--spec",(Join-Path $caseRoot "spec.json"),
      "--control",(Join-Path $caseRoot "control.json"),
      "--api-key-file",$keyFile
    )
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw "V2R4 WAIT runtime smoke failed" }

    Write-Host "[V2R4-WAIT-RUNTIME] 5/7 Verify wakeup, Kraken condition and recheck safety"
    $verify = @'
import glob,json,sys
from datetime import datetime
from pathlib import Path

root=Path(sys.argv[1])
h=json.load(open(root/"state"/"wait-runtime-heartbeat.json",encoding="utf-8"))
s=json.load(open(root/"state"/"wait-runtime-state.json",encoding="utf-8"))
assert h["status"]=="HEALTHY",h
assert h["paper_only"] is True
assert h["kraken_public_is_condition_truth"] is True
assert h["altrady_role"]=="WAKEUP_HINT_ONLY"
assert h["order_api"] is False
assert h["real_money_actions"] is False
assert h["counters"]["altrady_wakeup_checks"]==1,h["counters"]
assert h["counters"]["condition_matches"]==1,h["counters"]
assert h["counters"]["receipts_written"]==1,h["counters"]
assert h["counters"]["fresh_rechecks"]==1,h["counters"]
assert h["counters"]["fresh_recheck_failures"]==0,h["counters"]

handled=list(s["handled"].values())
assert len(handled)==1,handled
assert handled[0]["status"]=="FRESH_PAPER_RECHECK_COMPLETE",handled

receipts=glob.glob(str(root/"receipts"/"*.json"))
rechecks=glob.glob(str(root/"rechecks"/"*.json"))
assert len(receipts)==1,receipts
assert len(rechecks)==1,rechecks
r=json.load(open(rechecks[0],encoding="utf-8"))
assert r["paper_only"] is True
assert r["real_money_actions_enabled"] is False
assert r["order_api"] is False

t0=datetime.fromisoformat(r["trigger_observed_at_utc"].replace("Z","+00:00"))
t1=datetime.fromisoformat(r["recheck_started_at_utc"].replace("Z","+00:00"))
trigger_to_start=(t1-t0).total_seconds()
assert 0 <= trigger_to_start <= 20,trigger_to_start

print(json.dumps({
  "status":"PASS",
  "decision":r["decision"]["decision"],
  "altrady_wakeup_checks":h["counters"]["altrady_wakeup_checks"],
  "fresh_rechecks":h["counters"]["fresh_rechecks"],
  "trigger_to_recheck_start_s":round(trigger_to_start,3),
  "paper_only":True,
  "order_api":False
},sort_keys=True))
'@
    $summaryJson = $verify | & $python - $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "WAIT runtime safety verification failed" }
    $summary = $summaryJson | ConvertFrom-Json

    Write-Host "[V2R4-WAIT-RUNTIME] 6/7 Re-run same state and prove idempotency"
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw "idempotency cycle failed" }

    $verify2 = @'
import glob,json,sys
from pathlib import Path
root=Path(sys.argv[1])
h=json.load(open(root/"state"/"wait-runtime-heartbeat.json",encoding="utf-8"))
assert h["counters"]["fresh_rechecks"]==0,h
assert len(glob.glob(str(root/"rechecks"/"*.json")))==1
assert len(glob.glob(str(root/"receipts"/"*.json")))==1
print("IDEMPOTENT_PASS")
'@
    $verify2 | & $python - $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "idempotency verification failed" }

    Write-Host "[V2R4-WAIT-RUNTIME] 7/7 Summary"
    Write-Host ""
    Write-Host "=== MINI-PC V2R4 WAIT RUNTIME SMOKE SUMMARY ==="
    Write-Host ("Branch SHA: " + $branchSha)
    Write-Host ("Kraken canary: " + $hb.status + " | age_sec=" + $hbAge)
    Write-Host ("Decision: " + $summary.decision)
    Write-Host ("Altrady role: WAKEUP_HINT_ONLY | checks=" + $summary.altrady_wakeup_checks)
    Write-Host ("Fresh paper rechecks: " + $summary.fresh_rechecks)
    Write-Host ("Trigger to recheck start: " + $summary.trigger_to_recheck_start_s + " s")
    Write-Host "Safety: PAPER ONLY / KRAKEN CONDITION TRUTH / ALTRADY WAKEUP ONLY / NO ORDER API / NO REAL-MONEY ACTION"
    Write-Host "Result: PASS"
    Write-Host "=== END ==="
  } finally {
    Pop-Location
  }
} finally {
  Push-Location $repo
  try {
    if (Test-Path $worktree) {
      & git worktree remove --force $worktree 2>$null
    }
    & git worktree prune
  } finally {
    Pop-Location
  }
  Remove-Item -LiteralPath $caseRoot -Recurse -Force -ErrorAction SilentlyContinue
}
