param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$daemon = Join-Path $repo "tools\minipc-kraken-canary.py"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$heartbeat = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"

foreach ($p in @($daemon,$python)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

& $python -m pip install --disable-pip-version-check "websockets==15.0.1"
if ($LASTEXITCODE -ne 0) { throw "websockets installation failed" }

$args = '"' + $daemon + '" --trading-root "' + $TradingRoot + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName "CryptoMiniPC-KrakenCanary"

$deadline = (Get-Date).AddSeconds(25)
$state = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $heartbeat) {
    try {
      $candidate = Get-Content $heartbeat -Raw | ConvertFrom-Json
      if ($candidate.status -eq "HEALTHY" -and [int]$candidate.events_total -gt 0) {
        $state = $candidate
        break
      }
    } catch {}
  }
}

if (-not $state) {
  throw "Kraken canary task started but no healthy heartbeat was observed within 25 seconds."
}

Write-Host ""
Write-Host "=== KRAKEN CANARY INSTALL SUMMARY ==="
Write-Host "Task: CryptoMiniPC-KrakenCanary"
Write-Host ("Status: " + $state.status)
Write-Host ("Events: " + $state.events_total + " | book=" + $state.book_events + " | trade=" + $state.trade_events)
Write-Host ("Connections: " + $state.connections_started + " | gaps=" + $state.gaps + " | subscription_errors=" + $state.subscription_errors)
Write-Host ("Heartbeat: " + $heartbeat)
Write-Host "Safety: PUBLIC DATA ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION"
Write-Host "=== END ==="
