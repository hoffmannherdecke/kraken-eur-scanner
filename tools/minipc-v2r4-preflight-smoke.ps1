param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$Branch = "prep/v2r4-refresh-20261001"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$heartbeat = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"
$tempRoot = Join-Path $TradingRoot "Temp"

foreach ($p in @($repo,$python,$heartbeat,$tempRoot)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
$hbTime = [datetime]$hb.checked_at_utc
$hbAge = [math]::Round(((Get-Date).ToUniversalTime() - $hbTime.ToUniversalTime()).TotalSeconds,1)
if ($hb.status -ne "HEALTHY" -or $hbAge -gt 30) {
  throw ("Kraken canary is not fresh/healthy: status=" + $hb.status + " age_sec=" + $hbAge)
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$worktree = Join-Path $tempRoot ("v2r4-preflight-" + $stamp)
$plan = Join-Path $tempRoot ("v2r4-plan-" + $stamp + ".json")
$receipts = Join-Path $tempRoot ("v2r4-receipts-" + $stamp)
$preState = Join-Path $tempRoot ("v2r4-pre-state-" + $stamp + ".json")
$preEvents = Join-Path $tempRoot ("v2r4-pre-events-" + $stamp)

Write-Host "[V2R4-PREFLIGHT] 1/6 Fetch isolated prep branch"
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
  Write-Host "[V2R4-PREFLIGHT] 2/6 Compile V2R4/evaluator sources"
  Push-Location $worktree
  try {
    & $python -m py_compile paper_evaluator/evaluate.py paper_evaluator/revalidate.py paper_evaluator/v2r4_trigger_contract.py paper_evaluator/v2r4_trigger_plan.py paper_evaluator/v2r4_wait_watcher.py paper_evaluator/v2r4_precandidate_discovery.py paper_evaluator/v2r4_precandidate_watcher.py paper_evaluator/v2r4_local_recheck.py
    if ($LASTEXITCODE -ne 0) { throw "V2R4 py_compile failed" }

    Write-Host "[V2R4-PREFLIGHT] 3/6 Run deterministic V2R4 tests"
    & $python -m unittest tests.test_v2r4_trigger_contract tests.test_v2r4_trigger_plan tests.test_v2r4_precandidate_discovery tests.test_v2r4_precandidate_watcher tests.test_v2r4_tradability_policy tests.test_v2r4_evaluator_watch_conditions tests.test_v2r4_local_recheck tests.test_v2r4_spec_runtime_compatibility -v
    if ($LASTEXITCODE -ne 0) { throw "V2R4 unit tests failed" }

    Write-Host "[V2R4-PREFLIGHT] 4/6 Build harmless synthetic WAIT trigger plan"
    $planCode = @'
import json
from datetime import datetime, timezone
from paper_evaluator.v2r4_trigger_plan import build_wait_trigger_plan
now=datetime.now(timezone.utc)
candidate={"candidate_id":"V2R4-MINIPC-SYNTHETIC","pair":"BTC/EUR","altname":"XXBTZEUR"}
decision={
  "decision":"WAIT",
  "ttl_minutes":10,
  "watch_conditions":[{"metric":"spread_pct","op":"<=","value":100.0}]
}
plan=build_wait_trigger_plan(candidate,decision,now)
print(json.dumps(plan))
'@
    $planJson = $planCode | & $python -
    if ($LASTEXITCODE -ne 0) { throw "synthetic trigger-plan build failed" }
    [System.IO.File]::WriteAllText($plan,$planJson,[System.Text.UTF8Encoding]::new($false))

    Write-Host "[V2R4-PREFLIGHT] 5/6 Live Kraken WAIT watcher smoke"
    & $python paper_evaluator/v2r4_wait_watcher.py $plan --once --receipt-dir $receipts
    if ($LASTEXITCODE -ne 0) { throw "live V2R4 WAIT watcher smoke failed" }
    $receiptFile = Get-ChildItem $receipts -Filter "*.json" | Select-Object -First 1
    if (-not $receiptFile) { throw "V2R4 watcher receipt missing" }
    $receipt = Get-Content $receiptFile.FullName -Raw | ConvertFrom-Json
    if ($receipt.matched -ne $true -or $receipt.next_action -ne "FRESH_PAPER_RECHECK_ONLY" -or $receipt.real_money_actions_enabled -ne $false) {
      throw "V2R4 watcher receipt safety contract failed"
    }

    Write-Host "[V2R4-PREFLIGHT] 6/6 Broad live Kraken EUR pre-candidate smoke"
    & $python paper_evaluator/v2r4_precandidate_watcher.py --once --state $preState --event-dir $preEvents --max-depth-checks 2 --cooldown-seconds 0
    if ($LASTEXITCODE -ne 0) { throw "V2R4 pre-candidate watcher smoke failed" }
    if (-not (Test-Path $preState)) { throw "V2R4 pre-candidate state missing" }

    $state = Get-Content $preState -Raw | ConvertFrom-Json
    $pairCount = @($state.pairs.PSObject.Properties).Count

    Write-Host ""
    Write-Host "=== MINI-PC V2R4 PREFLIGHT SUMMARY ==="
    Write-Host ("Branch SHA: " + $branchSha)
    Write-Host ("Kraken canary: " + $hb.status + " | age_sec=" + $hbAge)
    Write-Host ("Synthetic WAIT receipt: matched=" + $receipt.matched + " | next_action=" + $receipt.next_action)
    Write-Host ("Pre-candidate state pairs observed: " + $pairCount)
    Write-Host "Tradability: LIVE PUBLIC KRAKEN ASSETPAIRS / NO STATIC BLACKLIST"
    Write-Host "Safety: PAPER/SHADOW ONLY / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
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
  Remove-Item -LiteralPath $plan -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $receipts -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $preState -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $preEvents -Recurse -Force -ErrorAction SilentlyContinue
}
