param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) {
    throw "Unable to resolve user home directory."
  }
  $TradingRoot = Join-Path $homeRoot "Trading"
}

$ExpectedConfirm = "RUN_BINANCE_PUBLIC_ACCESS_SMOKE"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\minipc-binance-public-access-smoke.py"
$report = Join-Path $TradingRoot "Logs\minipc-binance-public-access-latest.json"

$plan = [ordered]@{
  kind = "MINIPC_BINANCE_PUBLIC_ACCESS_SMOKE_PLAN_V1"
  status = $(if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" })
  execute = [bool]$Execute
  public_endpoints_only = $true
  checks = @(
    "api.binance.com/api/v3/time",
    "fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
    "fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT"
  )
  guardrails = [ordered]@{
    api_key = $false
    account_endpoint = $false
    private_data = $false
    orders = $false
    leverage_action = $false
    real_money_actions = $false
    active_strategy_change = $false
    paper_shadow_runtime_change = $false
  }
}

if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 8
  exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}
foreach ($p in @($repo,$python,$tool)) {
  if (-not (Test-Path -LiteralPath $p)) { throw "Required path missing: $p" }
}

New-Item -ItemType Directory -Force -Path (Split-Path $report -Parent) | Out-Null
& $python $tool --output $report
$code = $LASTEXITCODE

if (-not (Test-Path -LiteralPath $report)) {
  throw "Binance public-access smoke did not create a report."
}
$result = Get-Content $report -Raw | ConvertFrom-Json

Write-Host ""
Write-Host "=== MINI-PC BINANCE PUBLIC ACCESS SMOKE SUMMARY ==="
Write-Host ("Status: " + $result.status)
foreach ($check in $result.checks) {
  Write-Host ($check.name + ": " + $(if ($check.ok) { "PASS" } else { "FAIL" }) + $(if ($check.latency_ms) { " | " + $check.latency_ms + " ms" } else { "" }))
}
Write-Host ("Report: " + $report)
Write-Host "Safety: PUBLIC ONLY / NO API KEY / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($code -ne 0) { exit $code }
