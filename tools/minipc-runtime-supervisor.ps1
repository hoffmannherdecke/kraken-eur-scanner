param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$ForceRecovery,
  [int]$MinRestartIntervalMinutes = 10
)

$ErrorActionPreference = "Stop"
$now = (Get-Date).ToUniversalTime()
$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$statePath = Join-Path $stateDir "minipc-runtime-supervisor.json"
$historyPath = Join-Path $stateDir "minipc-runtime-supervisor-history.json"
$logPath = Join-Path $logDir "minipc-runtime-supervisor.log"

New-Item -ItemType Directory -Force -Path $stateDir,$logDir | Out-Null

function Parse-Utc([object]$Value) {
  if (-not $Value) { return $null }
  try { return ([datetime]$Value).ToUniversalTime() } catch { return $null }
}

function Load-History {
  if (-not (Test-Path $historyPath)) {
    return [ordered]@{ schema_version=1; tasks=[ordered]@{} }
  }
  try {
    $s = Get-Content $historyPath -Raw | ConvertFrom-Json
    if ([int]$s.schema_version -ne 1) { throw "schema" }
    return $s
  } catch {
    return [ordered]@{ schema_version=1; tasks=[ordered]@{} }
  }
}

function Get-TaskState($taskName) {
  $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
  if (-not $task) { return $null }
  $info = $task | Get-ScheduledTaskInfo
  return [ordered]@{ task=$task; info=$info }
}

function Get-Heartbeat($path) {
  if (-not (Test-Path $path)) { return $null }
  try { return (Get-Content $path -Raw | ConvertFrom-Json) } catch { return $null }
}

$specs = @(
  [ordered]@{ name="CryptoMiniPC-KrakenCanary"; path=(Join-Path $stateDir "kraken-canary-heartbeat.json"); max_age=60; good=@("HEALTHY","CONNECTED") },
  [ordered]@{ name="CryptoMiniPC-KrakenUniverse"; path=(Join-Path $stateDir "kraken-eur-universe-heartbeat.json"); max_age=90; good=@("HEALTHY","CONNECTED") },
  [ordered]@{ name="CryptoMiniPC-AltradyTrigger"; path=(Join-Path $stateDir "altrady-trigger-heartbeat.json"); max_age=120; good=@("HEALTHY") },
  [ordered]@{ name="CryptoMiniPC-V2R4WSShadow"; path=(Join-Path $stateDir "v2r4-ws-shadow-heartbeat.json"); max_age=45; good=@("HEALTHY","DUPLICATE_SKIPPED") },
  [ordered]@{ name="CryptoMiniPC-V2R4ShadowOutcomes"; path=(Join-Path $stateDir "v2r4-ws-shadow-outcome-heartbeat.json"); max_age=90; good=@("HEALTHY") },
  [ordered]@{ name="CryptoMiniPC-V2R4ShadowCloudSync"; path=(Join-Path $stateDir "v2r4-shadow-cloud-sync-heartbeat.json"); max_age=240; good=@("HEALTHY") },
  [ordered]@{ name="CryptoMiniPC-StatusSync"; path=(Join-Path $stateDir "minipc-status-sync-heartbeat.json"); max_age=900; good=@("HEALTHY") }
)

$history = Load-History
if (-not $history.tasks) { $history | Add-Member -NotePropertyName tasks -NotePropertyValue ([ordered]@{}) -Force }

$rows = New-Object System.Collections.Generic.List[object]
$restarted = New-Object System.Collections.Generic.List[string]
$failed = New-Object System.Collections.Generic.List[string]

foreach ($spec in $specs) {
  $ts = Get-TaskState $spec.name
  if (-not $ts) {
    $rows.Add([ordered]@{ task=$spec.name; installed=$false; healthy=$null; action="SKIP_NOT_INSTALLED" })
    continue
  }

  $hb = Get-Heartbeat $spec.path
  $age = $null
  $hbStatus = $null
  $fresh = $false
  if ($hb) {
    $hbStatus = [string]$hb.status
    $checked = Parse-Utc $hb.checked_at_utc
    if ($checked) {
      $age = [math]::Round(($now - $checked).TotalSeconds,1)
      $fresh = ($age -le [double]$spec.max_age -and $hbStatus -in $spec.good)
    }
  }

  $taskRunning = ([string]$ts.task.State -eq "Running")
  $needsRecovery = (-not $fresh) -or (-not $taskRunning)

  $lastRestart = $null
  try {
    $entry = $history.tasks.($spec.name)
    if ($entry) { $lastRestart = Parse-Utc $entry.last_restart_at_utc }
  } catch {}

  $restartAllowed = $ForceRecovery
  if (-not $restartAllowed) {
    if (-not $lastRestart) {
      $restartAllowed = $true
    } else {
      $restartAllowed = (($now - $lastRestart).TotalMinutes -ge $MinRestartIntervalMinutes)
    }
  }

  $action = "NONE"
  $before = [ordered]@{
    scheduler_state = [string]$ts.task.State
    last_run_time = if ($ts.info.LastRunTime) { $ts.info.LastRunTime.ToString("o") } else { $null }
    last_task_result = [int64]$ts.info.LastTaskResult
    heartbeat_status = $hbStatus
    heartbeat_age_sec = $age
  }

  if ($needsRecovery -and $restartAllowed) {
    $action = "RESTART"
    try {
      Stop-ScheduledTask -TaskName $spec.name -ErrorAction SilentlyContinue
      Start-Sleep -Milliseconds 500
      Start-ScheduledTask -TaskName $spec.name
      $restarted.Add($spec.name)

      if (-not $history.tasks.($spec.name)) {
        $history.tasks | Add-Member -NotePropertyName $spec.name -NotePropertyValue ([ordered]@{}) -Force
      }
      $history.tasks.($spec.name) | Add-Member -NotePropertyName last_restart_at_utc -NotePropertyValue $now.ToString("o") -Force
    } catch {
      $action = "RESTART_FAILED"
      $failed.Add($spec.name)
    }
  } elseif ($needsRecovery) {
    $action = "BACKOFF"
  }

  $rows.Add([ordered]@{
    task = $spec.name
    installed = $true
    healthy_before = $fresh
    action = $action
    before = $before
  })
}

if ($restarted.Count -gt 0) { Start-Sleep -Seconds 20 }

$allHealthy = $true
foreach ($row in $rows) {
  if (-not $row.installed) { continue }
  $spec = $specs | Where-Object { $_.name -eq $row.task } | Select-Object -First 1
  $ts = Get-TaskState $row.task
  $hb = Get-Heartbeat $spec.path
  $age = $null
  $hbStatus = $null
  $healthy = $false
  if ($hb) {
    $hbStatus = [string]$hb.status
    $checked = Parse-Utc $hb.checked_at_utc
    if ($checked) {
      $age = [math]::Round(((Get-Date).ToUniversalTime() - $checked).TotalSeconds,1)
      $healthy = ($age -le [double]$spec.max_age -and $hbStatus -in $spec.good)
    }
  }
  if (-not $ts -or [string]$ts.task.State -ne "Running") { $healthy = $false }
  $row | Add-Member -NotePropertyName healthy_after -NotePropertyValue $healthy -Force
  $row | Add-Member -NotePropertyName after -NotePropertyValue ([ordered]@{
    scheduler_state = if ($ts) { [string]$ts.task.State } else { "MISSING" }
    heartbeat_status = $hbStatus
    heartbeat_age_sec = $age
  }) -Force
  if (-not $healthy) { $allHealthy = $false }
}

$status = if ($failed.Count -gt 0) { "CRITICAL" } elseif ($allHealthy) { "HEALTHY" } else { "WARNING" }

$report = [ordered]@{
  schema_version = 1
  kind = "MINIPC_RUNTIME_SUPERVISOR_V1"
  checked_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  status = $status
  restarted = @($restarted)
  failed_restarts = @($failed)
  tasks = @($rows)
  guardrails = [ordered]@{
    monitored_tasks_only = $true
    strategy_changes = $false
    evaluator_invoked = $false
    order_api = $false
    real_money_actions = $false
  }
}

[System.IO.File]::WriteAllText(
  $statePath,
  ($report | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

$history.schema_version = 1
$history | Add-Member -NotePropertyName updated_at_utc -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
$history | Add-Member -NotePropertyName status -NotePropertyValue $status -Force
[System.IO.File]::WriteAllText(
  $historyPath,
  ($history | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

$line = "{0} status={1} restarted={2} failed={3}" -f (Get-Date).ToString("o"),$status,($restarted -join ","),($failed -join ",")
Add-Content -Path $logPath -Value $line -Encoding UTF8

Write-Output ($report | ConvertTo-Json -Depth 10)
if ($failed.Count -gt 0) { exit 2 }
exit 0
