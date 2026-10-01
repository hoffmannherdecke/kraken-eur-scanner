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
$worktree = Join-Path $tempRoot ("v2r4-e2e-" + $stamp)
$caseRoot = Join-Path $tempRoot ("v2r4-e2e-case-" + $stamp)
New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null

Write-Host "[V2R4-E2E] 1/7 Fetch isolated prep branch"
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
    Write-Host "[V2R4-E2E] 2/7 Compile exact branch sources"
    & $python -m py_compile paper_evaluator/evaluate.py paper_evaluator/v2r4_trigger_contract.py paper_evaluator/v2r4_trigger_plan.py paper_evaluator/v2r4_wait_watcher.py paper_evaluator/v2r4_local_recheck.py
    if ($LASTEXITCODE -ne 0) { throw "V2R4 compile failed" }

    Write-Host "[V2R4-E2E] 3/7 Prepare isolated synthetic candidate/control/spec"
    $prepare = @'
import json,time,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path
import sys
root=Path(sys.argv[1])
now=datetime.now(timezone.utc)
ts=int(now.timestamp())
stamp=now.strftime("%Y%m%d-%H%M%S")
cid=f"{stamp}-BTC-EUR-r0"
q=urllib.parse.urlencode({"pair":"XBTEUR"})
req=urllib.request.Request("https://api.kraken.com/0/public/Ticker?"+q,headers={"User-Agent":"minipc-v2r4-e2e"})
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
    "sensor_price_eur":price,"source":"synthetic_minipc_e2e_with_live_kraken_ticker"
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
cpath=root/(cid+".json")
cpath.write_text(json.dumps(candidate,indent=2)+"\n","utf-8")
control={
  "enabled":True,
  "test_id":"V2R4-MINIPC-TRIGGER-RECHECK-E2E",
  "series_id":"PAPER-V2R4-MINIPC-TRIGGER-RECHECK-E2E",
  "strategy_revision":"V2R4-PROPOSED-2026-09-30-PRECANDIDATE",
  "series_started_at_utc":(now-timedelta(minutes=2)).isoformat().replace("+00:00","Z"),
  "target_completed_paper_trades":1,
  "real_money_actions_enabled":False
}
(root/"control.json").write_text(json.dumps(control,indent=2)+"\n","utf-8")
(root/"candidate-path.txt").write_text(str(cpath)+"\n","utf-8")
(root/"candidate-id.txt").write_text(cid+"\n","utf-8")
print(cid,price)
'@
    $prepare | & $python - $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "candidate/control preparation failed" }

    Copy-Item "research\v2r4\paper_strategy_spec_v2r4_proposed.json" (Join-Path $caseRoot "spec.json")

    $candidatePath = (Get-Content (Join-Path $caseRoot "candidate-path.txt") -Raw).Trim()
    $candidateId = (Get-Content (Join-Path $caseRoot "candidate-id.txt") -Raw).Trim()
    $planPath = Join-Path $caseRoot "plan.json"
    $receiptDir = Join-Path $caseRoot "receipts"
    $outDir = Join-Path $caseRoot "recheck"

    Write-Host "[V2R4-E2E] 4/7 Build deterministic WAIT trigger"
    $planCode = @'
import json,sys
from datetime import datetime,timezone
from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan
candidate=json.load(open(sys.argv[1],encoding="utf-8"))
decision={
  "decision":"WAIT",
  "ttl_minutes":10,
  "watch_conditions":[{"metric":"spread_pct","op":"<=","value":100.0}]
}
plan=build_wait_trigger_plan(candidate,decision,datetime.now(timezone.utc))
open(sys.argv[2],"w",encoding="utf-8").write(json.dumps(plan,indent=2)+"\n")
'@
    $planCode | & $python - $candidatePath $planPath
    if ($LASTEXITCODE -ne 0) { throw "trigger-plan build failed" }

    Write-Host "[V2R4-E2E] 5/7 Match trigger against live public Kraken data"
    & $python paper_evaluator/v2r4_wait_watcher.py $planPath --once --receipt-dir $receiptDir
    if ($LASTEXITCODE -ne 0) { throw "live trigger watcher failed" }
    $receipt = Get-ChildItem $receiptDir -Filter "*.json" | Select-Object -First 1
    if (-not $receipt) { throw "trigger receipt missing" }

    Write-Host "[V2R4-E2E] 6/7 Fresh local paper recheck through actual model"
    & $python paper_evaluator/v2r4_local_recheck.py --candidate $candidatePath --trigger-receipt $receipt.FullName --spec (Join-Path $caseRoot "spec.json") --control (Join-Path $caseRoot "control.json") --out-dir $outDir --api-key-file $keyFile
    if ($LASTEXITCODE -ne 0) { throw "local fresh recheck failed" }

    Write-Host "[V2R4-E2E] 7/7 Verify timestamps and safety contract"
    $verify = @'
import glob,json,sys
from datetime import datetime
files=glob.glob(sys.argv[1]+"/*.json")
assert len(files)==1,files
d=json.load(open(files[0],encoding="utf-8"))
assert d["kind"]=="V2R4_LOCAL_TRIGGER_RECHECK_V1"
assert d["paper_only"] is True
assert d["real_money_actions_enabled"] is False
assert d["order_api"] is False
assert d["decision"]["decision"] in {"BUY_SCOUT","WAIT","REJECT"}
t0=datetime.fromisoformat(d["trigger_observed_at_utc"].replace("Z","+00:00"))
t1=datetime.fromisoformat(d["recheck_started_at_utc"].replace("Z","+00:00"))
t2=datetime.fromisoformat(d["recheck_completed_at_utc"].replace("Z","+00:00"))
trigger_to_start=(t1-t0).total_seconds()
runtime=(t2-t1).total_seconds()
assert trigger_to_start >= 0
assert trigger_to_start <= 20, trigger_to_start
if d["decision"]["decision"]=="WAIT":
    assert d["next_wait_trigger_plan"] is not None
    assert d["next_wait_trigger_plan"]["on_match"]=="FRESH_PAPER_RECHECK_ONLY"
if d["decision"]["decision"]=="BUY_SCOUT":
    assert d["paper_entry"] is not None
    assert d["paper_entry"]["status"].startswith("SCOUT_FILLED_SIMULATED")
print(json.dumps({
  "decision":d["decision"]["decision"],
  "trigger_to_recheck_start_s":round(trigger_to_start,3),
  "recheck_runtime_s":round(runtime,3),
  "paper_entry_simulated":d["paper_entry"] is not None,
  "next_wait_trigger_plan":d["next_wait_trigger_plan"] is not None,
  "paper_only":True,
  "order_api":False
},sort_keys=True))
'@
    $summaryJson = $verify | & $python - $outDir
    if ($LASTEXITCODE -ne 0) { throw "E2E verification failed" }
    $summary = $summaryJson | ConvertFrom-Json

    Write-Host ""
    Write-Host "=== MINI-PC V2R4 TRIGGER-RECHECK E2E SUMMARY ==="
    Write-Host ("Branch SHA: " + $branchSha)
    Write-Host ("Kraken canary: " + $hb.status + " | age_sec=" + $hbAge)
    Write-Host ("Candidate: " + $candidateId)
    Write-Host ("Decision: " + $summary.decision)
    Write-Host ("Trigger to recheck start: " + $summary.trigger_to_recheck_start_s + " s")
    Write-Host ("Recheck runtime: " + $summary.recheck_runtime_s + " s")
    Write-Host ("Paper entry simulated: " + $summary.paper_entry_simulated)
    Write-Host ("Next WAIT trigger plan: " + $summary.next_wait_trigger_plan)
    Write-Host "Safety: PAPER ONLY / PUBLIC KRAKEN / NO EXCHANGE ACCOUNT / NO ORDER API / NO REAL-MONEY ACTION"
    Write-Host "Result: PASS"
    Write-Host "=== END ==="
  } finally {
    Pop-Location
  }
} finally {
  Push-Location $repo
  try {
    & git worktree remove --force $worktree 2>$null
    & git worktree prune
  } finally {
    Pop-Location
  }
  Remove-Item -LiteralPath $caseRoot -Recurse -Force -ErrorAction SilentlyContinue
}
