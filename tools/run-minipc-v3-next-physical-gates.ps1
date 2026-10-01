param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = ""
)
$ErrorActionPreference="Stop"
if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}
Set-StrictMode -Version Latest

$ExpectedConfirm="RUN_V3_NEXT_PHYSICAL_GATES"
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$feature=Join-Path $repo "tools\run-minipc-v3-feature-integrity-gates.ps1"
$h3=Join-Path $repo "tools\run-minipc-v3-h3-ws-book-smoke.ps1"
$binance=Join-Path $repo "tools\run-minipc-binance-public-access-smoke.ps1"

$plan=[ordered]@{
  kind="V3_NEXT_PHYSICAL_GATES_BUNDLE_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  execute=[bool]$Execute
  gates=@(
    "H6 frozen pre-2026 EUR15 feature-integrity",
    "H1 frozen pre-2026 EUR15 breadth feature-integrity",
    "H3 bounded public Kraken Spot WS-v2 book checksum/reconnect confirmation",
    "Binance public-only local connectivity smoke"
  )
  explicitly_not_included=@(
    "V2R3/V2R4 strategy/runtime changes",
    "V2R4 activation",
    "H4 stop/TTL tuning",
    "H5 shadow activation",
    "H7 meta training",
    "H8 second EOD capture",
    "private APIs",
    "orders or real-money actions"
  )
  guardrails=[ordered]@{
    holdout_opened=$false
    strategy_mutation=$false
    evaluator_invoked_by_h3=$false
    private_api=$false
    orders=$false
    leverage=$false
    real_money_actions=$false
  }
}

if(-not $Execute){
  $plan|ConvertTo-Json -Depth 8
  exit 0
}
if($Confirm -ne $ExpectedConfirm){
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}
foreach($p in @($repo,$feature,$h3,$binance)){
  if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}
}

Push-Location $repo
try{
  $dirty=(git status --porcelain)
  if($LASTEXITCODE -ne 0){throw "git status failed"}
  if($dirty){throw "Repository working tree is not clean; physical research bundle fails closed."}
  $head=(git rev-parse HEAD).Trim()
  Write-Host "=== V3 NEXT PHYSICAL GATES ==="
  Write-Host ("Repo HEAD: "+$head)
  Write-Host "1/3 Historical H6+H1 feature-integrity..."
  & $feature -TradingRoot $TradingRoot -Execute
  if($LASTEXITCODE -ne 0){throw "H1/H6 feature bundle failed"}

  Write-Host "2/3 Kraken H3 WS book checksum/reconnect..."
  & $h3 -TradingRoot $TradingRoot -Execute
  if($LASTEXITCODE -ne 0){throw "H3 physical WS smoke failed"}

  Write-Host "3/3 Binance public access..."
  & $binance -TradingRoot $TradingRoot -Execute -Confirm "RUN_BINANCE_PUBLIC_ACCESS_SMOKE"
  if($LASTEXITCODE -ne 0){throw "Binance public-access smoke failed"}
}finally{
  Pop-Location
}

Write-Host ""
Write-Host "=== V3 PHYSICAL GATE BUNDLE COMPLETE ==="
Write-Host "H1/H6: feature-integrity only, holdout closed"
Write-Host "H3: public L2 transport/reconciliation only; queue/fill not claimed"
Write-Host "Binance: public connectivity only"
Write-Host "V2R3/V2R4 unchanged / no orders / no real-money action"
