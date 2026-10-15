param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$ForceRecovery,
  [switch]$WaitSourceProgressOptIn,
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

# A live WAIT owner can be source-limited without being process-dead.
# Suppress only an otherwise fresh, actively running, rate-only WAIT restart.
# A mixed source/recheck error, stale heartbeat or stopped task still recovers.
function Test-WaitRateOnly([object]$Heartbeat,[object]$AgeSeconds,[double]$MaxAgeSeconds,[bool]$TaskRunning) {
  if(-not $Heartbeat -or -not $TaskRunning -or $null -eq $AgeSeconds){ return $false }
  if([string]$Heartbeat.status -ne "DEGRADED"){ return $false }
  $age=[double]$AgeSeconds
  if($age -lt -30 -or $age -gt $MaxAgeSeconds){ return $false }
  if(-not $Heartbeat.error_classes -or -not $Heartbeat.counters){ return $false }
  $classes=@($Heartbeat.error_classes.PSObject.Properties)
  if($classes.Count -ne 1 -or $classes[0].Name -ne "KRAKEN_RATE_LIMIT"){ return $false }
  if([int]$classes[0].Value -lt 1){ return $false }
  if([int]$Heartbeat.counters.fresh_recheck_failures -ne 0){ return $false }
  if([int]$Heartbeat.counters.data_unavailable_checks -lt 1){ return $false }
  return $true
}


# Pure opt-in WAIT source-progress policy. A genuine source response is NOT
# proof that the whole WAIT evaluation has completed. A newer final heartbeat
# always outranks an old in-progress marker. Worker identity is caller-verified.
function Test-WaitSourceProgress([object]$Progress,[object]$Heartbeat,[datetime]$ObservedUtc,
                                [bool]$TaskRunning,[bool]$VerifiedWorker,
                                [double]$MaxProgressAgeSeconds=90.0) {
  if(-not $Progress -or -not $Heartbeat -or -not $TaskRunning -or -not $VerifiedWorker){
    return $false
  }
  if([string]$Progress.kind -cne "V2R4_WAIT_SOURCE_PROGRESS_V1" -or
     [string]$Progress.status -cne "IN_PROGRESS_NOT_HEALTHY" -or
     $Progress.paper_only -ne $true -or $Progress.order_api -ne $false -or
     [string]$Progress.successful_source_steps -notmatch '^[1-9][0-9]{0,7}$' -or
     [string]$Progress.worker_pid -notmatch '^[1-9][0-9]{0,8}$' -or
     [string]$Heartbeat.status -notin @("HEALTHY","DEGRADED")){
    return $false
  }
  foreach($value in @($Progress.cycle_started_at_utc,
                      $Progress.last_source_progress_at_utc,
                      $Heartbeat.checked_at_utc)){
    if([string]$value -notmatch 'Z$'){return $false}
  }
  try {
    $start=([datetime]$Progress.cycle_started_at_utc).ToUniversalTime()
    $last=([datetime]$Progress.last_source_progress_at_utc).ToUniversalTime()
    $completed=([datetime]$Heartbeat.checked_at_utc).ToUniversalTime()
  } catch { return $false }
  $now=$ObservedUtc.ToUniversalTime()
  $age=($now-$last).TotalSeconds
  if($age -lt -5 -or $age -gt $MaxProgressAgeSeconds -or
     $last -lt $start -or ($now-$start).TotalSeconds -gt 600 -or
     ($now-$start).TotalSeconds -lt -5 -or
     $last -le $completed -or $start -le $completed){
    return $false
  }
  return $true
}

# Read-only OS identity check: the PID inside JSON is never trusted by itself.
# An opted-in WAIT child must be Python from the frozen isolated Paper stage.
function Test-WaitSourceWorkerOnHost([object]$Progress,[string]$TradingRoot) {
  if(-not $Progress -or
     [string]$Progress.worker_pid -notmatch '^[1-9][0-9]{0,8}$'){return $false}
  try {
    $id=[int]$Progress.worker_pid
    $found=@(Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $id" -ErrorAction Stop)
    if($found.Count -ne 1){return $false}
    $process=$found[0]
    $command=[string]$process.CommandLine
    $stage=Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
    # Normalize Windows/Linux separators for the same pure mock-driven
    # policy regression; the actual host is still Windows and read-only.
    $stagePrefix=($stage.Replace('\','/')).TrimEnd('/') + '/'
    $normalizedCommand=$command.Replace('\','/')
    $born=([datetime]$process.CreationDate).ToUniversalTime()
    $started=([datetime]$Progress.cycle_started_at_utc).ToUniversalTime()
    return (
      [string]$process.Name -match '^pythonw?\.exe$' -and
      $normalizedCommand.IndexOf($stagePrefix,[System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
      $command -match '(?i)(?:wait_launcher\.py|v2r4_wait_runtime(?:\.py)?)' -and
      $born -le $started -and $born -le (Get-Date).ToUniversalTime()
    )
  } catch { return $false }
}

# V3 scoped policy, inside existing Supervisor; absent marker = unchanged.
# A local marker is not a physical stop or Cloud CAS/release receipt.
function Test-V3PaperIntakeFence([bool]$Present,[object]$Marker) {
  if(-not $Present){ return "NONE" }
  if($null -eq $Marker){ return "INVALID_FAIL_CLOSED" }
  $expected=@("CryptoMiniPC-V2R4PaperCandidates","CryptoMiniPC-V2R4PaperWait")
  $got=@($Marker.task_names | Sort-Object)
  if($Marker.kind -ne "V3_EXPERIMENTAL_OLD_INTAKE_FENCE_V1" -or
     $Marker.phase -notin @("ARMED","QUIESCED","CLOUD_COMMITTED") -or
     $Marker.predecessor_series_id -ne "PAPER-V2R4-20261009T110135Z" -or
     [string]$Marker.proposed_successor_series_id -notmatch '^PAPER-V3-[A-Za-z0-9-]{8,96}$' -or
     [string]$Marker.proposed_v3_repo_sha -notmatch '^[a-f0-9]{40}$' -or
     [string]$Marker.proposed_v3_bundle_sha256 -notmatch '^[a-f0-9]{64}$' -or
     [string]$Marker.proposed_v3_strategy_sha256 -notmatch '^[a-f0-9]{64}$' -or
     $Marker.paper_only -ne $true -or
     $Marker.orders_enabled -ne $false -or
     $Marker.real_money_actions -ne $false -or
     $Marker.persistent_until_explicit_owner_release -ne $true -or
     ($got -join '|') -cne ($expected -join '|')) {
    return "INVALID_FAIL_CLOSED"
  }
  return [string]$Marker.phase
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

# Older maintenance marker is bound to 07 Oct, not this 09 Oct predecessor.
# V3 marker MUST NOT be installed during normal V2R4 Paper operation.
$v3IntakeTasks=@("CryptoMiniPC-V2R4PaperCandidates","CryptoMiniPC-V2R4PaperWait")
$v3FenceFile=Join-Path $stateDir "v3-experimental-paper-old-intake-fence.json"
$v3FencePresent=Test-Path -LiteralPath $v3FenceFile
# Even an unexpected DIRECTORY at this marker path fails closed on read.
$v3FenceReceipt=$null
if($v3FencePresent){
  try{$v3FenceReceipt=Get-Content -LiteralPath $v3FenceFile -Raw | ConvertFrom-Json}
  catch{$v3FenceReceipt=$null}
}
$v3FenceMode=Test-V3PaperIntakeFence -Present $v3FencePresent -Marker $v3FenceReceipt
if($v3FenceMode -ne "NONE" -and $maintenanceMode -ne "NONE"){
  $v3FenceMode="INVALID_FAIL_CLOSED"
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
    if($v3FenceMode -ne "NONE" -and $spec.name -in $v3IntakeTasks){
      # Supervisor-only skip: Windows recovery, PID stop and aftercare
      # all require separate independent physical evidence.
      $guardedTask=Get-ScheduledTask -TaskName $spec.name -ErrorAction SilentlyContinue
      $guardedState=if($guardedTask){[string]$guardedTask.State}else{"MISSING"}
      $requiresDisabled=($v3FenceMode -in @("QUIESCED","CLOUD_COMMITTED"))
      $violation=$requiresDisabled -and $guardedState -ne "Disabled"
      $rows += [pscustomobject]@{
        task=$spec.name; installed=($null -ne $guardedTask)
        healthy_before=$null
        action=$(if($v3FenceMode -eq "INVALID_FAIL_CLOSED"){"V3_FENCE_INVALID_FAIL_CLOSED"}
          elseif($violation){"V3_FENCE_VIOLATION_WINDOWS_TASK_NOT_DISABLED"}
          else{"V3_INTAKE_SUPERVISOR_REARM_BLOCKED"})
        before=[pscustomobject]@{scheduler_state=$guardedState}
        healthy_after=$null; after=$null
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
    $rateOnlyWaiting = $false
    $sourceProgressActive = $false
    if($spec.name -eq "CryptoMiniPC-V2R4PaperWait" -and $WaitSourceProgressOptIn -and
       (-not $fresh) -and $schedulerRunning){
      $progress = Read-Heartbeat (Join-Path $stateDir "v2r4-paper-wait-source-progress.json")
      $workerVerified = Test-WaitSourceWorkerOnHost -Progress $progress -TradingRoot $TradingRoot
      $sourceProgressActive = Test-WaitSourceProgress -Progress $progress -Heartbeat $hb -ObservedUtc $now -TaskRunning $schedulerRunning -VerifiedWorker $workerVerified
    }
    if($spec.name -eq "CryptoMiniPC-V2R4PaperWait"){
      $rateOnlyWaiting = Test-WaitRateOnly -Heartbeat $hb -AgeSeconds $age -MaxAgeSeconds $spec.max_age -TaskRunning $schedulerRunning
    }
    # Keep the real health WARNING visible, but do NOT restart a live process
    # merely for a source-level rate-limit. Backoff is done by the source owner.
    $needsRecovery = ((-not $fresh) -and (-not $rateOnlyWaiting) -and
                      (-not $sourceProgressActive)) -or (-not $schedulerRunning)

    if (-not $attemptHistory.ContainsKey($spec.name)) {
      $attemptHistory[$spec.name] = @{ last_attempt_at_utc=$null; consecutive_failures=0 }
    }
    $attempt = $attemptHistory[$spec.name]
    if (-not $needsRecovery -and -not $sourceProgressActive) {
      # Genuine in-progress source activity must not clear restart failures.
      $attempt.consecutive_failures = 0
    }
    $lastAttempt = $attempt.last_attempt_at_utc
    $exp = [math]::Min(5, [int]$attempt.consecutive_failures)
    $cooldownSeconds = [math]::Min(3600, [double]$spec.restart_backoff_min * 60 * [math]::Pow(2, $exp))
    $restartAllowed = ([bool]$ForceRecovery -or (-not $lastAttempt) -or
      (($now - $lastAttempt).TotalSeconds -ge $cooldownSeconds))
    $upstreamMissing = ((-not $krakenSourceHealthy) -and $schedulerRunning -and
      ($spec.name -in $krakenDependents))

    $action = $(if($sourceProgressActive){"WAIT_SOURCE_ACTIVE_NOT_HEALTHY"}
      elseif($rateOnlyWaiting){"KRAKEN_RATE_LIMIT_WAIT"}else{"NONE"})
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
        source_progress_state=$(if($sourceProgressActive){"ACTIVE_NOT_HEALTHY"}else{$null})
      }
    }
  }

  if ($restarted.Count -gt 0) { Start-Sleep -Seconds $PostRestartVerifySeconds }

  $allHealthy = $true
  foreach ($row in $rows) {
    if($row.action -in @("MAINTENANCE_SKIP","MAINTENANCE_FAIL_CLOSED","ARCHIVED_BASELINE_NOT_RESTARTED","V3_FENCE_INVALID_FAIL_CLOSED","V3_FENCE_VIOLATION_WINDOWS_TASK_NOT_DISABLED","V3_INTAKE_SUPERVISOR_REARM_BLOCKED")){ continue }
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

  $v3FenceViolation=@($rows | Where-Object { $_.action -eq "V3_FENCE_VIOLATION_WINDOWS_TASK_NOT_DISABLED" }).Count -gt 0
  $status = if($v3FenceMode -eq "INVALID_FAIL_CLOSED" -or $v3FenceViolation){"CRITICAL"}
    elseif($maintenanceMode -in @("INVALID_FAIL_CLOSED","EXPIRED_FAIL_CLOSED")){"CRITICAL"}
    elseif($v3FenceMode -ne "NONE"){"WARNING"}
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
  v3_paper_old_intake_fence=[pscustomobject]@{
    mode=$v3FenceMode
    marker_present=$v3FencePresent
    protected_supervisor_task_names=@($v3IntakeTasks)
    old_aftercare_tasks_remain_in_supervisor_scope=$true
    windows_scheduler_rearm_fence_proven=$false
    physical_stop_process_tree_ack_proven=$false
    historical_followup_exit_cloud_ack_proven=$false
    v3_cloud_cas_or_release_authorized=$false
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
    wait_source_progress_opt_in=[bool]$WaitSourceProgressOptIn
    wait_source_progress_never_healthy=$true
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
