param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [int]$SmokeSeconds = 45
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Installationsskript in einer als Administrator gestarteten PowerShell ausführen."
}

if ($SmokeSeconds -lt 15 -or $SmokeSeconds -gt 180) {
  throw "SmokeSeconds must be between 15 and 180."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$daemon = Join-Path $repo "tools\minipc-kraken-universe-feed.py"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$heartbeat = Join-Path $TradingRoot "State\kraken-eur-universe-heartbeat.json"

foreach ($p in @($daemon,$python)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

& $python -m pip install --disable-pip-version-check "websockets==15.0.1"
if ($LASTEXITCODE -ne 0) { throw "websockets installation failed" }

Write-Host ""
Write-Host "Running bounded broad Kraken-EUR WebSocket proof before installing the 24/7 task..."
& $python $daemon --trading-root $TradingRoot --seconds $SmokeSeconds
$smokeCode = $LASTEXITCODE
if ($smokeCode -ne 0) {
  if (Test-Path $heartbeat) {
    try {
      $failed = Get-Content $heartbeat -Raw | ConvertFrom-Json
      Write-Host ("Smoke status: " + $failed.status)
      Write-Host ("Pairs: " + $failed.pair_count + " | observed=" + $failed.observed_pair_count + " | coverage=" + $failed.coverage_pct + "%")
      Write-Host ("Subscription errors: " + $failed.subscription_errors + " | last_error=" + $failed.last_error)
    } catch {}
  }
  throw "Broad Kraken-EUR WebSocket smoke failed with exit code $smokeCode. Persistent task was NOT installed."
}

$smoke = Get-Content $heartbeat -Raw | ConvertFrom-Json
if ($smoke.status -ne "HEALTHY") { throw "Bounded smoke did not finish HEALTHY." }
if ([int]$smoke.pair_count -lt 1) { throw "Bounded smoke returned no EUR pairs." }
if ([double]$smoke.coverage_pct -lt 80) { throw "Bounded smoke coverage below 80%." }
if ([int]$smoke.subscription_errors -ne 0) { throw "Bounded smoke had subscription errors." }

$args = '"' + $daemon + '" --trading-root "' + $TradingRoot + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse" -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName "CryptoMiniPC-KrakenUniverse"

$deadline = (Get-Date).AddSeconds(45)
$state = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $heartbeat) {
    try {
      $candidate = Get-Content $heartbeat -Raw | ConvertFrom-Json
      $ageSec = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$candidate.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      if (
        $candidate.status -eq "HEALTHY" -and
        $ageSec -le 20 -and
        [int]$candidate.pair_count -gt 0 -and
        [double]$candidate.coverage_pct -ge 80 -and
        [int]$candidate.subscription_errors -eq 0
      ) {
        $state = $candidate
        break
      }
    } catch {}
  }
}

if (-not $state) {
  throw "Kraken universe task started but no fresh HEALTHY heartbeat with >=80% coverage was observed within 45 seconds."
}

Write-Host ""
Write-Host "=== KRAKEN EUR UNIVERSE INSTALL SUMMARY ==="
Write-Host "Task: CryptoMiniPC-KrakenUniverse"
Write-Host ("Status: " + $state.status)
Write-Host ("Online EUR pairs: " + $state.pair_count + " | observed=" + $state.observed_pair_count + " | coverage=" + $state.coverage_pct + "%")
Write-Host ("Ticker rows: " + $state.ticker_rows + " | updates=" + $state.ticker_updates + " | subscription_errors=" + $state.subscription_errors)
Write-Host ("Connections: " + $state.connections_started + " | reconnects=" + $state.reconnects)
Write-Host ("Heartbeat: " + $heartbeat)
Write-Host ("Latest snapshot: " + (Join-Path $TradingRoot "State\kraken-eur-ticker-latest.json"))
Write-Host "Safety: PUBLIC DATA ONLY / NO ACCOUNT / NO ORDERS / NO STRATEGY ACTION"
Write-Host "=== END ==="
