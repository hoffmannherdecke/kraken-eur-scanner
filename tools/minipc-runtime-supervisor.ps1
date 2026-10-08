param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$ForceRecovery,
  [int]$MinRestartIntervalMinutes = 10,
  [int]$StopWaitSeconds = 15,
  [int]$PostRestartVerifySeconds = 20
)

$ErrorActionPreference = "Stop"

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

function Read-Heartbeat([string]$Path) {
  if (-not (Test-Path $Path)) { return $null }
  try { return (Get-Content $Path -Raw | ConvertFrom-Json) } catch { return $null }
}

function Read-RestartHistory {
  $map = @{}
  if (-not (Test-Path $historyPath)) { return $map }
  try {
    $raw = Get-Content $historyPath -Raw | ConvertFrom-Json
    if ($raw.tasks) {
      foreach ($prop in $raw.tasks.PSObject.Properties) {
        $map[$prop.Name] = Parse-Utc $prop.Value.last_restart_at_utc
      }
    }
  } catch {}
  return $map
}

# Failed verifications still count as recovery attempts; old history is compatible.
function Read-AttemptHistory {
  $map = @{}
  if (-not (Test-Path $historyPath)) { return $map }
  try {
    $raw = Get-Content $historyPath -Raw | ConvertFrom-Json
    if ($raw.tasks) {
      foreach ($prop in $raw.tasks.PSObject.Properties) {
        $item = $prop.Value
        $count = 0
        try { $count = [math]::Max(0, [int]$item.consecutive_failures) } catch {}
        $map[$prop.Name] = @{
          last_attempt_at_utc = Parse-Utc $item.last_attempt_at_utc
          consecutive_failures = [math]::Min(5, $count)
        }
      }
    }
  } catch {}
  return $map
}

function Write-JsonAtomic([string]$Path,[object]$Payload,[int]$Depth=10) {
  $tmp = $Path + ".tmp"
  [System.IO.File]::WriteAllText(
    $tmp,
    ($Payload | ConvertTo-Json -Depth $Depth) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
  )
  Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Wait-TaskNotRunning([string]$TaskName,[int]$TimeoutSeconds) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  do {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { return $false }
    if ([string]$task.State -ne "Running") { return $true }
    Start-Sleep -Milliseconds 250
  } while ((Get-Date) -lt $deadline)
  return $false
}

$specs = @(
  [pscustomobject]@{ name="CryptoMiniPC-KrakenCanary"; path=(Join-Path $stateDir "kraken-canary-heartbeat.json"); max_age=60.0; good=@("HEALTHY","CONNECTED"); restart_backoff_min=$MinRestartIntervalMinutes },
  [pscustomobject]@{ name="CryptoMiniPC-KrakenUniverse"; path=(Join-Path $stateDir "kraken-eur-universe-heartbeat.json"); max_age=90.0; good=@("HEALTHY","CONNECTED"); restart_backoff_min=$MinRestartIntervalMinutes },
  [pscustomobject]@{ name="CryptoMiniPC-AltradyTrigger"; path=(Join-Path $stateDir "altrady-trigger-heartbeat.json"); max_age=120.0; good=@("HEALTHY"); restart_backoff_min=$MinRestartIntervalMinutes },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4WSShadow"; path=(Join-Path $stateDir "v2r4-ws-shadow-heartbeat.json"); max_age=45.0; good=@("HEALTHY","DUPLICATE_SKIPPED"); restart_backoff_min=2 },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4ShadowOutcomes"; path=(Join-Path $stateDir "v2r4-ws-shadow-outcome-heartbeat.json"); max_age=90.0; good=@("HEALTHY"); restart_backoff_min=$MinRestartIntervalMinutes },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4ShadowCloudSync"; path=(Join-Path $stateDir "v2r4-shadow-cloud-sync-heartbeat.json"); max_age=240.0; good=@("HEALTHY"); restart_backoff_min=$MinRestartIntervalMinutes },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4PaperCandidates"; path=(Join-Path $stateDir "v2r4-paper-candidate-runtime-heartbeat.json"); max_age=60.0; good=@("HEALTHY"); restart_backoff_min=2 },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4PaperWait"; path=(Join-Path $stateDir "v2r4-paper-wait-runtime-heartbeat.json"); max_age=30.0; good=@("HEALTHY"); restart_backoff_min=2 },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4PaperLifecycle"; path=(Join-Path $stateDir "v2r4-paper-lifecycle-heartbeat.json"); max_age=180.0; good=@("HEALTHY"); restart_backoff_min=5 },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4PaperCloudSync"; path=(Join-Path $stateDir "v2r4-paper-cloud-sync-heartbeat.json"); max_age=180.0; good=@("HEALTHY"); restart_backoff_min=5 },
  [pscustomobject]@{ name="CryptoMiniPC-V3H3Shadow001"; path=(Join-Path $stateDir "v3-h3-shadow-001-heartbeat.json"); max_age=30.0; good=@("HEALTHY"); restart_backoff_min=5 },
  [pscustomobject]@{ name="CryptoMiniPC-StatusSync"; path=(Join-Path $stateDir "minipc-status-sync-heartbeat.json"); max_age=900.0; good=@("HEALTHY"); restart_backoff_min=$MinRestartIntervalMinutes }
)

# During an exact technical PAPER cutover never restart the frozen old
# scheduled tasks. Malformed or expired markers fail closed rather than
# silently resurrecting H3-001/PAPER-V2R4.
$maintenanceTasks=@(
  "CryptoMiniPC-V2R4PaperCandidates","CryptoMiniPC-V2R4PaperWait",
  "CryptoMiniPC-V2R4PaperLifecycle","CryptoMiniPC-V2R4PaperCloudSync",
  "CryptoMiniPC-V3H3Shadow001"
)
$maintenanceMode="NONE"
$maintenanceExpires=$null
$maintenanceFile=Join-Path $stateDir "v2r4-technical-cutover-maintenance.json"
if(Test-Path -LiteralPath $maintenanceFile){
  $maintenanceMode="INVALID_FAIL_CLOSED"
  try {
    $m=Get-Content -LiteralPath $maintenanceFile -Raw | ConvertFrom-Json
    $expires=Parse-Utc $m.expires_at_utc
    $created=Parse-Utc $m.created_at_utc
    $old=Get-Content (Join-Path $TradingRoot "Runtime\v2r4-paper-app\paper_runtime_control.json") -Raw | ConvertFrom-Json
    $got=@($m.task_names | Sort-Object)
    $expected=@($maintenanceTasks | Sort-Object)
    if($m.kind -eq "V2R4_TECHNICAL_MAINTENANCE_V1" -and
       $m.phase -in @("ARMING","QUIESCED","CLOUD_COMMITTED") -and
       $old.series_id -eq "PAPER-V2R4-20261007T184255Z" -and
       $old.release_repo_sha -eq "3c6729a6c548d169f56a97f07f75892f37211636" -and
       $m.predecessor_series_id -eq $old.series_id -and
       [string]$m.successor_repo_sha -match '^[a-f0-9]{40}$' -and
       $m.orders_enabled -eq $false -and
       ($got -join '|') -ceq ($expected -join '|') -and
       $created -and $expires -and
       ($expires-$created).TotalMinutes -gt 0 -and
       ($expires-$created).TotalMinutes -le 10 -and
       ($created-(Get-Date).ToUniversalTime()).TotalSeconds -le 15){
      $maintenanceExpires=$expires
      $maintenanceMode=if((Get-Date).ToUniversalTime() -gt $expires){"EXPIRED_FAIL_CLOSED"}else{"ACTIVE"}
    }
  } catch { $maintenanceMode="INVALID_FAIL_CLOSED" }
}

# Post-cutover V3-H3-001 is permanently frozen on its ORIGINAL baseline.
# A committed, fully verified local record only prevents restarting that
# retired old H3 task; Kraken and successor Paper tasks remain supervised.
$h3Retired=$false
$retirementFile=Join-Path $stateDir "v2r4-technical-cutover-completed.json"
if(Test-Path -LiteralPath $retirementFile){
  try {
    $retired=Get-Content -LiteralPath $retirementFile -Raw | ConvertFrom-Json
    $h3=Get-ScheduledTask -TaskName "CryptoMiniPC-V3H3Shadow001" -ErrorAction SilentlyContinue
    $h3Retired=(
      $retired.kind -eq "V2R4_TECHNICAL_CUTOVER_COMPLETED_V1" -and
      $retired.predecessor_series_id -eq "PAPER-V2R4-20261007T184255Z" -and
      [string]$retired.successor_series_id -match '^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$' -and
      $retired.h3_001_retired -eq $true -and
      $retired.real_money_actions -eq $false -and
      $retired.orders -eq $false -and
      $h3 -and [string]$h3.State -eq "Disabled"
    )
  }catch{$h3Retired=$false}
}

$rows = @()
$restarted = @()
$failed = @()
$restartHistory = Read-RestartHistory
$attemptHistory = Read-AttemptHistory
$now = (Get-Date).ToUniversalTime()
# Only the canonical Kraken canary proves that the primary upstream is fresh.
$krakenHb = Read-Heartbeat (Join-Path $stateDir "kraken-canary-heartbeat.json")
$krakenSourceHealthy = $false
if ($krakenHb) {
  $krakenChecked = Parse-Utc $krakenHb.checked_at_utc
  if ($krakenChecked) {
    $krakenSourceHealthy = (
      [string]$krakenHb.status -in @("HEALTHY","CONNECTED") -and
      ($now - $krakenChecked).TotalSeconds -ge -30 -and
      ($now - $krakenChecked).TotalSeconds -le 60
    )
  }
}
$krakenDependents = @(
  "CryptoMiniPC-KrakenUniverse", "CryptoMiniPC-V2R4WSShadow",
  "CryptoMiniPC-V2R4ShadowOutcomes", "CryptoMiniPC-V2R4PaperCandidates",
  "CryptoMiniPC-V2R4PaperWait", "CryptoMiniPC-V2R4PaperLifecycle",
  "CryptoMiniPC-V3H3Shadow001"
)
$topError = $null
$status = "UNKNOWN"

try {
  foreach ($spec in $specs) {
    if($h3Retired -and $spec.name -eq "CryptoMiniPC-V3H3Shadow001"){
      $rows += [pscustomobject]@{
        task=$spec.name; installed=$true; healthy_before=$null
        action="ARCHIVED_BASELINE_NOT_RESTARTED"; before=$null; healthy_after=$null; after=$null
      }
      continue
    }
    if($maintenanceMode -ne "NONE" -and $spec.name -in $maintenanceTasks){
      $rows += [pscustomobject]@{
        task=$spec.name; installed=$true; healthy_before=$null
        action=$(if($maintenanceMode -eq "ACTIVE"){"MAINTENANCE_SKIP"}else{"MAINTENANCE_FAIL_CLOSED"})
        before=$null; healthy_after=$null; after=$null
      }
      continue
    }
    $task = Get-ScheduledTask -TaskName $spec.name -ErrorAction SilentlyContinue
    if (-not $task) {
      $rows += [pscustomobject]@{
        task=$spec.name
        installed=$false
        healthy_before=$null
        action="SKIP_NOT_INSTALLED"
        before=$null
      }
      continue
    }

    $info = $task | Get-ScheduledTaskInfo
    $hb = Read-Heartbeat $spec.path
    $hbStatus = $null
    $age = $null
    $fresh = $false

    if ($hb) {
      $hbStatus = [string]$hb.status
      $checked = Parse-Utc $hb.checked_at_utc
      if ($checked) {
        $age = [math]::Round(($now - $checked).TotalSeconds,1)
        $fresh = ($age -le $spec.max_age -and $hbStatus -in $spec.good)
      }
    }

    $schedulerRunning = ([string]$task.State -eq "Running")
    $needsRecovery = (-not $fresh) -or (-not $schedulerRunning)

    if (-not $attemptHistory.ContainsKey($spec.name)) {
      $attemptHistory[$spec.name] = @{ last_attempt_at_utc=$null; consecutive_failures=0 }
    }
    $attempt = $attemptHistory[$spec.name]
    if (-not $needsRecovery) {
      # Only actual health clears the exponential retry penalty.
      $attempt.consecutive_failures = 0
    }
    $lastAttempt = $attempt.last_attempt_at_utc
    $exp = [math]::Min(5, [int]$attempt.consecutive_failures)
    $cooldownSeconds = [math]::Min(3600, [double]$spec.restart_backoff_min * 60 * [math]::Pow(2, $exp))
    $restartAllowed = ([bool]$ForceRecovery -or (-not $lastAttempt) -or
      (($now - $lastAttempt).TotalSeconds -ge $cooldownSeconds))
    $upstreamMissing = ((-not $krakenSourceHealthy) -and $schedulerRunning -and
      ($spec.name -in $krakenDependents))

    $action = "NONE"
    if ($needsRecovery -and $upstreamMissing -and (-not $ForceRecovery)) {
      $action = "WAIT_FOR_UPSTREAM"
    } elseif ($needsRecovery -and $restartAllowed) {
      # Record every ATTEMPT, including failures and unverified restarts.
      # Otherwise failed 20s health probes can trigger infinite restart loops.
      $attempt.last_attempt_at_utc = $now
      $attempt.consecutive_failures = [math]::Min(5, [int]$attempt.consecutive_failures + 1)
      try {
        Stop-ScheduledTask -TaskName $spec.name -ErrorAction SilentlyContinue
        $stopped = Wait-TaskNotRunning -TaskName $spec.name -TimeoutSeconds $StopWaitSeconds
        if (-not $stopped) {
          throw "Task did not leave Running state within $StopWaitSeconds seconds."
        }
        Start-ScheduledTask -TaskName $spec.name
        $restarted += $spec.name
        $action = "RESTART_STARTED"
      } catch {
        $failed += $spec.name
        $action = "RESTART_FAILED"
      }
    } elseif ($needsRecovery) {
      $action = "BACKOFF"
    }

    $rows += [pscustomobject]@{
      task=$spec.name
      installed=$true
      healthy_before=$fresh
      action=$action
      before=[pscustomobject]@{
        scheduler_state=[string]$task.State
        last_run_time=$(if ($info.LastRunTime) { $info.LastRunTime.ToString("o") } else { $null })
        last_task_result=[int64]$info.LastTaskResult
        heartbeat_status=$hbStatus
        heartbeat_age_sec=$age
      }
    }
  }

  if ($restarted.Count -gt 0) { Start-Sleep -Seconds $PostRestartVerifySeconds }

  $allHealthy = $true
  foreach ($row in $rows) {
    if($row.action -in @("MAINTENANCE_SKIP","MAINTENANCE_FAIL_CLOSED","ARCHIVED_BASELINE_NOT_RESTARTED")){ continue }
    if (-not $row.installed) { continue }
    $spec = $specs | Where-Object { $_.name -eq $row.task } | Select-Object -First 1
    $task = Get-ScheduledTask -TaskName $row.task -ErrorAction SilentlyContinue
    $hb = Read-Heartbeat $spec.path
    $hbStatus = $null
    $age = $null
    $healthy = $false

    if ($hb) {
      $hbStatus = [string]$hb.status
      $checked = Parse-Utc $hb.checked_at_utc
      if ($checked) {
        $age = [math]::Round(((Get-Date).ToUniversalTime() - $checked).TotalSeconds,1)
        $healthy = ($age -le $spec.max_age -and $hbStatus -in $spec.good)
      }
    }
    if (-not $task -or [string]$task.State -ne "Running") { $healthy = $false }

    $row | Add-Member -NotePropertyName healthy_after -NotePropertyValue $healthy -Force
    $row | Add-Member -NotePropertyName after -NotePropertyValue ([pscustomobject]@{
      scheduler_state=$(if ($task) { [string]$task.State } else { "MISSING" })
      heartbeat_status=$hbStatus
      heartbeat_age_sec=$age
    }) -Force

    if ($row.action -eq "RESTART_STARTED") {
      if ($healthy) {
        $row.action = "RESTART_VERIFIED"
        $restartHistory[$row.task] = $now
        $attemptHistory[$row.task].consecutive_failures = 0
      } else {
        $row.action = "RESTART_UNVERIFIED"
        if ($row.task -notin $failed) { $failed += $row.task }
      }
    }

    if (-not $healthy) { $allHealthy = $false }
  }

  $status = if($maintenanceMode -in @("INVALID_FAIL_CLOSED","EXPIRED_FAIL_CLOSED")){"CRITICAL"}
    elseif ($failed.Count -gt 0) { "CRITICAL" } elseif ($allHealthy) { "HEALTHY" } else { "WARNING" }
} catch {
  $status = "CRITICAL"
  $topError = $_.Exception.Message
}

$report = [pscustomobject]@{
  schema_version=1
  kind="MINIPC_RUNTIME_SUPERVISOR_V1"
  checked_at_utc=(Get-Date).ToUniversalTime().ToString("o")
  status=$status
  restarted=@($restarted)
  failed_restarts=@($failed)
  h3_001_archived=$h3Retired
  maintenance=[pscustomobject]@{
    mode=$maintenanceMode
    expires_at_utc=$(if($maintenanceExpires){$maintenanceExpires.ToString("o")}else{$null})
    scoped_task_names=@($maintenanceTasks)
    order_api=$false
    real_money_actions=$false
  }
  kraken_upstream_healthy=$krakenSourceHealthy
  error=$topError
  tasks=@($rows)
  guardrails=[pscustomobject]@{
    monitored_tasks_only=$true
    restart_requires_task_stop_confirmation=$true
    restart_history_records_verified_recovery_only=$true
    restart_attempt_history_persisted=$true
    max_restart_cooldown_seconds=3600
    strategy_changes=$false
    evaluator_invoked=$false
    order_api=$false
    real_money_actions=$false
  }
}
Write-JsonAtomic $statePath $report 10

$historyTasks = [ordered]@{}
foreach ($key in ($restartHistory.Keys | Sort-Object)) {
  $value = $restartHistory[$key]
  $attempt = $attemptHistory[$key]
  $historyTasks[$key] = [ordered]@{
    last_restart_at_utc=$(if ($value) { $value.ToString("o") } else { $null })
    last_attempt_at_utc=$(if ($attempt -and $attempt.last_attempt_at_utc) { $attempt.last_attempt_at_utc.ToString("o") } else { $null })
    consecutive_failures=$(if ($attempt) { [int]$attempt.consecutive_failures } else { 0 })
  }
}
# Failed attempts can precede the very first verified recovery.
foreach ($key in ($attemptHistory.Keys | Sort-Object)) {
  if ($historyTasks.Contains($key)) { continue }
  $attempt = $attemptHistory[$key]
  $historyTasks[$key] = [ordered]@{
    last_restart_at_utc=$null
    last_attempt_at_utc=$(if ($attempt.last_attempt_at_utc) { $attempt.last_attempt_at_utc.ToString("o") } else { $null })
    consecutive_failures=[int]$attempt.consecutive_failures
  }
}
$historyPayload = [pscustomobject]@{
  schema_version=1
  updated_at_utc=(Get-Date).ToUniversalTime().ToString("o")
  status=$status
  tasks=$historyTasks
}
Write-JsonAtomic $historyPath $historyPayload 8

$line = "{0} status={1} restarted={2} failed={3} error={4}" -f (Get-Date).ToString("o"),$status,($restarted -join ","),($failed -join ","),$topError
Add-Content -Path $logPath -Value $line -Encoding UTF8

Write-Output ($report | ConvertTo-Json -Depth 10)
if ($status -eq "CRITICAL") { exit 2 }
exit 0
