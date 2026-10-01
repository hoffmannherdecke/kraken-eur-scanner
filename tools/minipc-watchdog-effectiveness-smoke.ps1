param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"
$healthPath = Join-Path $TradingRoot "State\minipc-health.json"

if (-not (Test-Path $watchdog)) { throw "Watchdog script missing: $watchdog" }

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
$code = $LASTEXITCODE

if (-not (Test-Path $healthPath)) { throw "Watchdog did not create minipc-health.json" }
$h = Get-Content $healthPath -Raw | ConvertFrom-Json

$focus = @(
  "kraken_canary_heartbeat",
  "kraken_universe_heartbeat",
  "v2r4_ws_shadow_heartbeat",
  "v2r4_ws_shadow_outcomes",
  "runtime_supervisor",
  "minipc_status_sync"
)

Write-Host ""
Write-Host "=== MINI-PC EFFECTIVENESS WATCHDOG SUMMARY ==="
Write-Host ("Overall: " + $h.status)
Write-Host ("Operational state: " + $(if ($h.health_state) { $h.health_state } else { "LEGACY_NOT_SET" }))
Write-Host ("State reasons: " + $(if ($h.state_reason_codes.Count -gt 0) { $h.state_reason_codes -join "," } else { "none" }))

$failed = 0
foreach ($name in $focus) {
  $entry = $h.checks.$name
  if (-not $entry) {
    Write-Host ($name + ": MISSING")
    $failed++
    continue
  }

  $state = if ($entry.ok -eq $true) { "OK" } elseif ($entry.ok -eq $false) { "FAIL" } else { "N/A" }
  Write-Host ($name + ": " + $state + " | " + $entry.detail)
  if ($entry.ok -eq $false) { $failed++ }
}

Write-Host ("Issues: " + $(if ($h.issues.Count -gt 0) { ($h.issues | ForEach-Object { $_.severity + ":" + $_.check }) -join ", " } else { "none" }))
Write-Host "Checks now verify fresh underlying data/events, not just a fresh process heartbeat."
Write-Host "Safety: READ-ONLY HEALTH CHECK / NO RESTART / NO STRATEGY CHANGE / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($code -ne 0 -or $failed -gt 0) { exit 2 }
exit 0
