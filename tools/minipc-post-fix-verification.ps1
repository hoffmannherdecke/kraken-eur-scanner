param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$reconciliation = Join-Path $repo "tools\paper-runtime-reconciliation-audit.py"
$watchdogSmoke = Join-Path $repo "tools\minipc-watchdog-effectiveness-smoke.ps1"

foreach ($p in @($reconciliation,$watchdogSmoke)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== MINI-PC POST-FIX VERIFICATION ==="

Write-Host "1/2 Corrected paper runtime reconciliation audit..."
& python $reconciliation
$reconciliationCode = $LASTEXITCODE

Write-Host ""
Write-Host "2/2 Watchdog effectiveness + operational taxonomy..."
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdogSmoke -TradingRoot $TradingRoot
$watchdogCode = $LASTEXITCODE

$status = if ($reconciliationCode -eq 0 -and $watchdogCode -eq 0) { "PASS" } else { "FAIL" }

Write-Host ""
Write-Host "=== MINI-PC POST-FIX VERIFICATION SUMMARY ==="
Write-Host ("Status: " + $status)
Write-Host ("Reconciliation audit exit: " + $reconciliationCode)
Write-Host ("Effectiveness watchdog exit: " + $watchdogCode)
Write-Host "Safety: READ-ONLY VERIFICATION / NO MODEL / NO EXCHANGE / NO ORDERS / NO STRATEGY CHANGE"
Write-Host "=== END ==="

if ($status -ne "PASS") { exit 2 }
exit 0
