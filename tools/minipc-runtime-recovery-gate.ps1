param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)

$ErrorActionPreference = "Stop"

$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"

foreach ($p in @($stateDir,$logDir,$repo)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$now = Get-Date
$boot = [datetime](Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$issues = New-Object System.Collections.Generic.List[string]
$notes = New-Object System.Collections.Generic.List[string]

function Add-Issue([string]$Code) {
  if (-not $issues.Contains($Code)) { $issues.Add($Code) }
}
function Add-Note([string]$Code) {
  if (-not $notes.Contains($Code)) { $notes.Add($Code) }
}
function Age-Sec([string]$Timestamp) {
  return [math]::Round(((Get-Date).ToUniversalTime() - ([datetime]$Timestamp).ToUniversalTime()).TotalSeconds,1)
}

Write-Host "[RUNTIME-RECOVERY] 1/5 Scheduled tasks"

$taskNames = @(
  "CryptoMiniPC-Health",
  "CryptoMiniPC-Backup",
  "CryptoMiniPC-LogCleanup",
  "CryptoMiniPC-KrakenCanary",
  "CryptoMiniPC-AltradyTrigger",
  "CryptoMiniPC-KrakenUniverse"
)
$startupNames = @(
  "CryptoMiniPC-Health",
  "CryptoMiniPC-KrakenCanary",
  "CryptoMiniPC-AltradyTrigger",
  "CryptoMiniPC-KrakenUniverse"
)
$taskRows = @()

foreach ($name in $taskNames) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if (-not $task) {
    Add-Issue ("task_missing_" + $name)
    continue
  }

  $info = $task | Get-ScheduledTaskInfo
  $lastRun = $info.LastRunTime
  $row = [ordered]@{
    name = $name
    state = [string]$task.State
    last_result = [int]$info.LastTaskResult
    last_run = if ($lastRun -and $lastRun -gt [datetime]::MinValue) { $lastRun.ToString("o") } else { $null }
    ran_since_boot = [bool]($lastRun -and $lastRun -ge $boot)
  }
  $taskRows += $row

  if ([int]$info.LastTaskResult -notin @(0,267009,267011)) {
    Add-Issue ("task_bad_result_" + $name)
  }
  if ($name -in $startupNames -and -not $row.ran_since_boot) {
    Add-Issue ("startup_task_not_run_" + $name)
  }
}

Write-Host "[RUNTIME-RECOVERY] 2/5 Local heartbeats"

$canary = $null
$canaryPath = Join-Path $stateDir "kraken-canary-heartbeat.json"
if (-not (Test-Path $canaryPath)) {
  Add-Issue "kraken_canary_heartbeat_missing"
} else {
  try {
    $canary = Get-Content $canaryPath -Raw | ConvertFrom-Json
    $age = Age-Sec $canary.checked_at_utc
    if ([string]$canary.status -notin @("HEALTHY","CONNECTED")) { Add-Issue "kraken_canary_not_healthy" }
    if ($age -gt 60) { Add-Issue "kraken_canary_stale" }
    if ([int]$canary.events_total -le 0) { Add-Issue "kraken_canary_no_events" }
    if ([int]$canary.subscription_errors -gt 0) { Add-Issue "kraken_canary_subscription_errors" }
  } catch {
    Add-Issue "kraken_canary_invalid"
  }
}

$universe = $null
$universePath = Join-Path $stateDir "kraken-eur-universe-heartbeat.json"
if (-not (Test-Path $universePath)) {
  Add-Issue "kraken_universe_heartbeat_missing"
} else {
  try {
    $universe = Get-Content $universePath -Raw | ConvertFrom-Json
    $age = Age-Sec $universe.checked_at_utc
    if ([string]$universe.status -notin @("HEALTHY","CONNECTED")) { Add-Issue "kraken_universe_not_healthy" }
    if ($age -gt 60) { Add-Issue "kraken_universe_stale" }
    if ([int]$universe.pair_count -le 0) { Add-Issue "kraken_universe_empty" }
    if ([int]$universe.observed_pair_count -le 0) { Add-Issue "kraken_universe_no_observations" }
    if ([double]$universe.coverage_pct -lt 80) { Add-Issue "kraken_universe_low_coverage" }
    if ([int]$universe.subscription_errors -gt 0) { Add-Issue "kraken_universe_subscription_errors" }
  } catch {
    Add-Issue "kraken_universe_invalid"
  }
}

$altrady = $null
$altradyPath = Join-Path $stateDir "altrady-trigger-heartbeat.json"
if (-not (Test-Path $altradyPath)) {
  Add-Issue "altrady_heartbeat_missing"
} else {
  try {
    $altrady = Get-Content $altradyPath -Raw | ConvertFrom-Json
    $age = Age-Sec $altrady.checked_at_utc
    if ([string]$altrady.status -ne "HEALTHY") { Add-Issue "altrady_not_healthy" }
    if ($age -gt 90) { Add-Issue "altrady_stale" }
  } catch {
    Add-Issue "altrady_invalid"
  }
}

Write-Host "[RUNTIME-RECOVERY] 3/5 Watchdog"

$health = $null
$healthPath = Join-Path $stateDir "minipc-health.json"
if (-not (Test-Path $healthPath)) {
  Add-Issue "minipc_health_missing"
} else {
  try {
    $health = Get-Content $healthPath -Raw | ConvertFrom-Json
    $healthAge = [math]::Round(($now - ([datetime]$health.checked_at_local)).TotalMinutes,2)
    if ($healthAge -gt 10) { Add-Issue "minipc_health_stale" }
    if ([string]$health.status -eq "CRITICAL") { Add-Issue "minipc_health_critical" }
    elseif ([string]$health.status -eq "WARNING") { Add-Note "minipc_health_warning" }
  } catch {
    Add-Issue "minipc_health_invalid"
  }
}

Write-Host "[RUNTIME-RECOVERY] 4/5 Kraken public reachability"

$krakenHttp = $null
try {
  $response = Invoke-WebRequest -UseBasicParsing -Uri "https://api.kraken.com/0/public/AssetPairs?pair=XBTEUR" -TimeoutSec 20
  $krakenHttp = [int]$response.StatusCode
  if ($krakenHttp -ne 200) { Add-Issue "kraken_http_non_200" }
} catch {
  Add-Issue "kraken_http_failed"
}

Write-Host "[RUNTIME-RECOVERY] 5/5 Compact report"

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $logDir "minipc-runtime-recovery-$stamp.json"
$status = if ($issues.Count -gt 0) { "FAIL" } elseif ($notes.Count -gt 0) { "PASS_WITH_NOTES" } else { "PASS" }

$result = [ordered]@{
  schema_version = 1
  kind = "MINIPC_RUNTIME_RECOVERY_GATE_V1"
  checked_at_local = $now.ToString("o")
  boot_time_local = $boot.ToString("o")
  uptime_minutes = [math]::Round(($now-$boot).TotalMinutes,1)
  status = $status
  tasks = $taskRows
  heartbeats = [ordered]@{
    kraken_canary = if ($canary) {
      [ordered]@{
        status = $canary.status
        age_sec = Age-Sec $canary.checked_at_utc
        events = [int]$canary.events_total
        gaps = [int]$canary.gaps
        subscription_errors = [int]$canary.subscription_errors
      }
    } else { $null }
    kraken_universe = if ($universe) {
      [ordered]@{
        status = $universe.status
        age_sec = Age-Sec $universe.checked_at_utc
        pair_count = [int]$universe.pair_count
        observed_pair_count = [int]$universe.observed_pair_count
        coverage_pct = [double]$universe.coverage_pct
        reconnects = [int]$universe.reconnects
        subscription_errors = [int]$universe.subscription_errors
      }
    } else { $null }
    altrady = if ($altrady) {
      [ordered]@{
        status = $altrady.status
        age_sec = Age-Sec $altrady.checked_at_utc
        detail = $altrady.detail
      }
    } else { $null }
  }
  watchdog = if ($health) {
    [ordered]@{
      status = $health.status
      checked_at_local = $health.checked_at_local
    }
  } else { $null }
  kraken_http_status = $krakenHttp
  issues = @($issues)
  notes = @($notes)
  guardrails = [ordered]@{
    read_only = $true
    configuration_changes = $false
    git_mutation = $false
    process_restart = $false
    strategy_changes = $false
    real_money_actions = $false
  }
}

[System.IO.File]::WriteAllText(
  $reportPath,
  ($result | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== MINI-PC RUNTIME RECOVERY SUMMARY ==="
Write-Host ("Status: " + $status)
Write-Host ("Boot: " + $boot.ToString("yyyy-MM-dd HH:mm:ss") + " | uptime=" + $result.uptime_minutes + " min")
Write-Host ("Tasks: " + $taskRows.Count + "/" + $taskNames.Count)
if ($canary) {
  Write-Host ("Kraken canary: " + $canary.status + " | age=" + (Age-Sec $canary.checked_at_utc) + "s | events=" + $canary.events_total)
}
if ($universe) {
  Write-Host ("Kraken EUR universe: " + $universe.status + " | " + $universe.observed_pair_count + "/" + $universe.pair_count + " | coverage=" + $universe.coverage_pct + "% | sub_errors=" + $universe.subscription_errors)
}
if ($altrady) {
  Write-Host ("Altrady transport: " + $altrady.status + " | age=" + (Age-Sec $altrady.checked_at_utc) + "s")
}
Write-Host ("Watchdog: " + $(if ($health) { [string]$health.status } else { "missing" }))
Write-Host ("Kraken HTTP: " + $(if ($krakenHttp) { $krakenHttp } else { "failed" }))
if ($issues.Count -gt 0) { Write-Host ("Issues: " + ($issues -join ", ")) } else { Write-Host "Issues: none" }
if ($notes.Count -gt 0) { Write-Host ("Notes: " + ($notes -join ", ")) } else { Write-Host "Notes: none" }
Write-Host ("Report: " + $reportPath)
Write-Host "Safety: READ-ONLY / NO CONFIG CHANGE / NO STRATEGY CHANGE / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($issues.Count -gt 0) { exit 2 }
exit 0
