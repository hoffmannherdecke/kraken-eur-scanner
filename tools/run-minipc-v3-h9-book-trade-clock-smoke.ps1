param(
  [string]$TradingRoot = "",
  [int]$Seconds = 20,
  [switch]$Execute
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}
if($Seconds -lt 10 -or $Seconds -gt 30){throw "Seconds must be 10..30"}
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python=Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool=Join-Path $repo "tools\v3-h9-public-book-trade-clock-smoke.py"
$out=Join-Path $TradingRoot ("Logs\v3-h9-book-trade-clock-"+(Get-Date -Format "yyyyMMdd-HHmmss")+".json")
$plan=[ordered]@{
  kind="V3_H9_MINIPC_BOOK_TRADE_CLOCK_GATE_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  pairs=@("BTC/EUR","ETH/EUR","SOL/EUR")
  seconds=$Seconds
  purpose="same-connection public book+trade clock/sequence evidence only"
  guardrails=[ordered]@{queue_model=$false;fill_probability=$false;orders=$false;real_money_actions=$false}
}
if(-not $Execute){$plan|ConvertTo-Json -Depth 6;exit 0}
foreach($p in @($repo,$python,$tool)){if(-not(Test-Path -LiteralPath $p)){throw "Required path missing: $p"}}
New-Item -ItemType Directory -Force -Path (Split-Path $out -Parent)|Out-Null
& $python $tool --symbols "BTC/EUR,ETH/EUR,SOL/EUR" --depth 10 --seconds $Seconds --output $out
if($LASTEXITCODE -ne 0){throw "H9 physical book+trade clock smoke failed"}
$r=Get-Content $out -Raw|ConvertFrom-Json
if($r.status -ne "PASS"){throw "H9 report not PASS"}
if([int]$r.totals.trades -lt 1){throw "H9 no trades captured"}
if([int]$r.totals.aligned_preceding_book_trades -lt 1){throw "H9 no safe preceding-book join captured"}
if($r.guardrails.orders -ne $false -or $r.guardrails.real_money_actions -ne $false){throw "H9 safety guard failed"}
Write-Host ("H9 PASS trades="+$r.totals.trades+" aligned="+$r.totals.aligned_preceding_book_trades)
Write-Host "Queue/fill/routing remain NOT PROVEN."
