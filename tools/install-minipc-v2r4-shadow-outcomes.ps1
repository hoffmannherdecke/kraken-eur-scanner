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
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$tool = Join-Path $repo "tools\v2r4-ws-shadow-outcome-tracker.py"
$snapshot = Join-Path $TradingRoot "State\kraken-eur-ticker-latest.json"
$eventDir = Join-Path $TradingRoot "State\v2r4-ws-shadow-events"
$heartbeat = Join-Path $TradingRoot "State\v2r4-ws-shadow-outcome-heartbeat.json"
$taskName = "CryptoMiniPC-V2R4ShadowOutcomes"

foreach ($p in @($repo,$python,$tool,$snapshot,$eventDir)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Write-Host "=== V2R4 SHADOW OUTCOME TRACKER INSTALL ==="
Write-Host "1/3 Compile + isolated synthetic smoke..."

& $python -m py_compile $tool
if ($LASTEXITCODE -ne 0) { throw "Outcome tracker compile failed." }

$smokeRoot = Join-Path $TradingRoot ("Temp\v2r4-outcome-smoke-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
$smokeEvents = Join-Path $smokeRoot "State\v2r4-ws-shadow-events"
New-Item -ItemType Directory -Force -Path $smokeEvents | Out-Null
$now = [datetime]::UtcNow.ToString("o").Replace("+00:00","Z")
$event = @{
  kind = "V2R4_WS_SHADOW_DISCOVERY"
  pair = "TEST/EUR"
  observed_at_utc = $now
  source_pair_received_at_utc = $now
  last_eur = 100.0
  reasons = @("FAST_10M")
  feed_to_shadow_latency_ms = 100.0
}
$snap = @{
  schema_version = 1
  kind = "MINIPC_KRAKEN_EUR_TICKER_LATEST_V1"
  written_at_utc = $now
  pair_count = 1
  observed_pair_count = 1
  pairs = @{
    "TEST/EUR" = @{ symbol="TEST/EUR"; received_at_utc=$now; last_eur=101.0 }
  }
}
$event | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $smokeEvents "event.json")
$snap | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $smokeRoot "State\kraken-eur-ticker-latest.json")

& $python $tool --trading-root $smokeRoot --once
if ($LASTEXITCODE -ne 0) { throw "Outcome tracker synthetic smoke failed." }
$smokeHb = Get-Content (Join-Path $smokeRoot "State\v2r4-ws-shadow-outcome-heartbeat.json") -Raw | ConvertFrom-Json
if ($smokeHb.status -ne "HEALTHY" -or [int]$smokeHb.active_events -ne 1) {
  throw "Synthetic smoke did not enroll exactly one prospective event."
}
Remove-Item -LiteralPath $smokeRoot -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "2/3 Register persistent startup task..."
$args = @(
  ('"' + $tool + '"'),
  "--trading-root",('"' + $TradingRoot + '"'),
  "--interval-seconds","10"
) -join " "
$action = New-ScheduledTaskAction -Execute $python -Argument $args
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "3/3 Verify heartbeat..."
$deadline = (Get-Date).AddSeconds(45)
$hb = $null
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 2
  if (Test-Path $heartbeat) {
    try {
      $candidate = Get-Content $heartbeat -Raw | ConvertFrom-Json
      $age = [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$candidate.checked_at_utc).ToUniversalTime()).TotalSeconds,1)
      if ($candidate.kind -eq "V2R4_WS_SHADOW_OUTCOME_HEARTBEAT_V1" -and $candidate.status -eq "HEALTHY" -and $age -le 20) {
        $hb = $candidate
        break
      }
    } catch {}
  }
}
if (-not $hb) { throw "Outcome tracker task started but no fresh HEALTHY heartbeat was observed." }

Write-Host ""
Write-Host "=== V2R4 SHADOW OUTCOME TRACKER INSTALL SUMMARY ==="
Write-Host "Status: HEALTHY"
Write-Host ("Task: " + $taskName)
Write-Host ("Active prospective events: " + $hb.active_events)
Write-Host ("Enrolled: " + $hb.counters.events_enrolled + " | ignored pre-tracker: " + $hb.counters.events_ignored_pretracker)
Write-Host "Horizons: 5m / 15m / 30m / 1h / 3h / 6h + running MFE/MAE"
Write-Host "Safety: EVIDENCE ONLY / NO EVALUATOR / NO ACCOUNT / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="
