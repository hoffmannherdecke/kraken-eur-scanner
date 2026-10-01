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
  "CryptoMiniPC-KrakenUniverse",
  "CryptoMiniPC-V2R4WSShadow"
)
$startupNames = @(
  "CryptoMiniPC-Health",
  "CryptoMiniPC-KrakenCanary",
  "CryptoMiniPC-AltradyTrigger",
  "CryptoMiniPC-KrakenUniverse",
  "CryptoMiniPC-V2R4WSShadow"
)
if (Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowOutcomes" -ErrorAction SilentlyContinue) {
  $taskNames += "CryptoMiniPC-V2R4ShadowOutcomes"
  $startupNames += "CryptoMiniPC-V2R4ShadowOutcomes"
}
if (Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowCloudSync" -ErrorAction SilentlyContinue) {
  $taskNames += "CryptoMiniPC-V2R4ShadowCloudSync"
  $startupNames += "CryptoMiniPC-V2R4ShadowCloudSync"
}
if (Get-ScheduledTask -TaskName "CryptoMiniPC-StatusSync" -ErrorAction SilentlyContinue) {
  $taskNames += "CryptoMiniPC-StatusSync"
  $startupNames += "CryptoMiniPC-StatusSync"
}
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

$shadow = $null
$shadowPath = Join-Path $stateDir "v2r4-ws-shadow-heartbeat.json"
if (-not (Test-Path $shadowPath)) {
  Add-Issue "v2r4_ws_shadow_heartbeat_missing"
} else {
  try {
    $shadow = Get-Content $shadowPath -Raw | ConvertFrom-Json
    $age = Age-Sec $shadow.checked_at_utc
    if ([string]$shadow.status -notin @("HEALTHY","DUPLICATE_SKIPPED")) { Add-Issue "v2r4_ws_shadow_not_healthy" }
    if ($age -gt 30) { Add-Issue "v2r4_ws_shadow_stale" }
    if ([int]$shadow.counters.snapshots_processed -le 0) { Add-Issue "v2r4_ws_shadow_no_processed_snapshots" }
    if ([string]$shadow.strategy_action -ne "NONE_SHADOW_ONLY") { Add-Issue "v2r4_ws_shadow_guardrail_changed" }
    if ([bool]$shadow.real_money_actions) { Add-Issue "v2r4_ws_shadow_real_money_guardrail_changed" }
  } catch {
    Add-Issue "v2r4_ws_shadow_invalid"
  }
}

$outcomes = $null
$outcomesTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowOutcomes" -ErrorAction SilentlyContinue
if ($outcomesTask) {
  $outcomesPath = Join-Path $stateDir "v2r4-ws-shadow-outcome-heartbeat.json"
  if (-not (Test-Path $outcomesPath)) {
    Add-Issue "v2r4_ws_shadow_outcomes_heartbeat_missing"
  } else {
    try {
      $outcomes = Get-Content $outcomesPath -Raw | ConvertFrom-Json
      $age = Age-Sec $outcomes.checked_at_utc
      if ([string]$outcomes.status -ne "HEALTHY") { Add-Issue "v2r4_ws_shadow_outcomes_not_healthy" }
      if ($age -gt 60) { Add-Issue "v2r4_ws_shadow_outcomes_stale" }
      if ([string]$outcomes.strategy_action -ne "NONE_EVIDENCE_ONLY") { Add-Issue "v2r4_ws_shadow_outcomes_guardrail_changed" }
      if ([bool]$outcomes.real_money_actions) { Add-Issue "v2r4_ws_shadow_outcomes_real_money_guardrail_changed" }
    } catch {
      Add-Issue "v2r4_ws_shadow_outcomes_invalid"
    }
  }
}

$cloudSync = $null
$cloudTask = Get-ScheduledTask -TaskName "CryptoMiniPC-V2R4ShadowCloudSync" -ErrorAction SilentlyContinue
if ($cloudTask) {
  $cloudPath = Join-Path $stateDir "v2r4-shadow-cloud-sync-heartbeat.json"
  if (-not (Test-Path $cloudPath)) {
    Add-Issue "v2r4_shadow_cloud_sync_heartbeat_missing"
  } else {
    try {
      $cloudSync = Get-Content $cloudPath -Raw | ConvertFrom-Json
      $age = Age-Sec $cloudSync.checked_at_utc
      if ([string]$cloudSync.status -ne "HEALTHY") { Add-Issue "v2r4_shadow_cloud_sync_not_healthy" }
      if ($age -gt 180) { Add-Issue "v2r4_shadow_cloud_sync_stale" }
      if ([string]$cloudSync.strategy_action -ne "NONE_ARCHIVE_ONLY") { Add-Issue "v2r4_shadow_cloud_sync_guardrail_changed" }
      if ([bool]$cloudSync.real_money_actions) { Add-Issue "v2r4_shadow_cloud_sync_real_money_guardrail_changed" }
    } catch {
      Add-Issue "v2r4_shadow_cloud_sync_invalid"
    }
  }
}

$statusSync = $null
$statusTask = Get-ScheduledTask -TaskName "CryptoMiniPC-StatusSync" -ErrorAction SilentlyContinue
if ($statusTask) {
  $statusPath = Join-Path $stateDir "minipc-status-sync-heartbeat.json"
  if (-not (Test-Path $statusPath)) {
    Add-Issue "minipc_status_sync_heartbeat_missing"
  } else {
    try {
      $statusSync = Get-Content $statusPath -Raw | ConvertFrom-Json
      $age = Age-Sec $statusSync.checked_at_utc
      if ([string]$statusSync.status -ne "HEALTHY") { Add-Issue "minipc_status_sync_not_healthy" }
      if ($age -gt 900) { Add-Issue "minipc_status_sync_stale" }
      if ([string]$statusSync.strategy_action -ne "NONE_STATUS_ONLY") { Add-Issue "minipc_status_sync_guardrail_changed" }
      if ([bool]$statusSync.real_money_actions) { Add-Issue "minipc_status_sync_real_money_guardrail_changed" }
    } catch {
      Add-Issue "minipc_status_sync_invalid"
    }
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
    v2r4_ws_shadow = if ($shadow) {
      [ordered]@{
        status = $shadow.status
        age_sec = Age-Sec $shadow.checked_at_utc
        snapshots_processed = [int]$shadow.counters.snapshots_processed
        events_emitted = [int]$shadow.counters.events_emitted
        gap_recoveries = [int]$shadow.counters.gap_recoveries
        recovery_epoch = [int]$shadow.recovery_epoch
        strategy_action = $shadow.strategy_action
      }
    } else { $null }
    v2r4_ws_shadow_outcomes = if ($outcomes) {
      [ordered]@{
        status = $outcomes.status
        age_sec = Age-Sec $outcomes.checked_at_utc
        active_events = [int]$outcomes.active_events
        enrolled = [int]$outcomes.counters.events_enrolled
        completed = [int]$outcomes.counters.events_completed
        incomplete_timeout = [int]$outcomes.counters.events_incomplete_timeout
        strategy_action = $outcomes.strategy_action
      }
    } else { $null }
    v2r4_shadow_cloud_sync = if ($cloudSync) {
      [ordered]@{
        status = $cloudSync.status
        age_sec = Age-Sec $cloudSync.checked_at_utc
        pending_records = [int]$cloudSync.pending_records
        uploaded_records = [int]$cloudSync.uploaded_records
        strategy_action = $cloudSync.strategy_action
      }
    } else { $null }
    minipc_status_sync = if ($statusSync) {
      [ordered]@{
        status = $statusSync.status
        age_sec = Age-Sec $statusSync.checked_at_utc
        uploaded_health_status = $statusSync.uploaded_health_status
        strategy_action = $statusSync.strategy_action
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
if ($shadow) {
  Write-Host ("V2R4 WS shadow: " + $shadow.status + " | age=" + (Age-Sec $shadow.checked_at_utc) + "s | snapshots=" + $shadow.counters.snapshots_processed + " | events=" + $shadow.counters.events_emitted + " | recovery_epoch=" + $shadow.recovery_epoch)
}
if ($outcomes) {
  Write-Host ("V2R4 shadow outcomes: " + $outcomes.status + " | age=" + (Age-Sec $outcomes.checked_at_utc) + "s | active=" + $outcomes.active_events + " | enrolled=" + $outcomes.counters.events_enrolled + " | completed=" + $outcomes.counters.events_completed)
}
if ($cloudSync) {
  Write-Host ("V2R4 shadow cloud sync: " + $cloudSync.status + " | age=" + (Age-Sec $cloudSync.checked_at_utc) + "s | pending=" + $cloudSync.pending_records + " | uploaded=" + $cloudSync.uploaded_records)
}
if ($statusSync) {
  Write-Host ("MINI-PC status sync: " + $statusSync.status + " | age=" + (Age-Sec $statusSync.checked_at_utc) + "s | uploaded_health_status=" + $statusSync.uploaded_health_status)
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
