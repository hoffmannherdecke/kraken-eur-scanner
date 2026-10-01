param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$SecondsPerCycle = 12,
  [switch]$Execute
)
$ErrorActionPreference="Stop"
if($SecondsPerCycle -lt 5 -or $SecondsPerCycle -gt 30){throw "SecondsPerCycle must be 5..30"}
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$reports=Join-Path $TradingRoot "Logs"
foreach($p in @($repo,$python)){if(-not(Test-Path $p)){throw "Required path missing: $p"}}
New-Item -ItemType Directory -Force -Path $reports|Out-Null
$stamp=Get-Date -Format "yyyyMMdd-HHmmss"
$out=Join-Path $reports ("v3-h3-ws-book-smoke-"+$stamp+".json")
$script=Join-Path $repo "tools\v3-h3-kraken-ws-book-reconciliation-smoke.py"
Write-Host "=== V3 H3 MINI-PC WS BOOK GATE ==="
Write-Host "Mode: " ($(if($Execute){"EXECUTE"}else{"PLAN ONLY"}))
Write-Host "Pairs: BTC/EUR, ETH/EUR, SOL/EUR | depth=10 | cycles=2"
Write-Host "Output: $out"
Write-Host "Safety: public WS only / compact report / no evaluator / no orders / no strategy mutation"
if(-not $Execute){
  Write-Host "No WebSocket capture executed. Re-run with -Execute at the bundled physical gate."
  exit 0
}
Push-Location $repo
try{
  & $python $script --symbols "BTC/EUR,ETH/EUR,SOL/EUR" --depth 10 --cycles 2 --seconds-per-cycle $SecondsPerCycle --output $out
  if($LASTEXITCODE -ne 0){throw "H3 WS book smoke failed"}
  $r=Get-Content $out -Raw|ConvertFrom-Json
  if($r.status -ne "PASS"){throw "H3 report is not PASS"}
  if([int]$r.totals.checksum_fail -ne 0){throw "H3 checksum failure"}
  if(-not $r.interpretation.bounded_reconnect_resubscribe_proven){throw "Reconnect proof missing"}
  if($r.guardrails.orders -ne $false -or $r.guardrails.real_money_actions -ne $false){throw "Safety guard failed"}
}finally{Pop-Location}
Write-Host ("PASS updates="+$r.totals.updates+" checksum_pass="+$r.totals.checksum_pass+" checksum_fail="+$r.totals.checksum_fail)
Write-Host "Queue position / maker-fill remain UNPROVEN by design."
