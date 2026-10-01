param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [switch]$ForceRecovery,
  [int]$MinRestartIntervalMinutes = 10
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

function Write-JsonAtomic([string]$Path,[object]$Payload,[int]$Depth=10) {
  $tmp = $Path + ".tmp"
  [System.IO.File]::WriteAllText(
    $tmp,
    ($Payload | ConvertTo-Json -Depth $Depth) + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
  )
  Move-Item -LiteralPath $tmp -Destination $Path -Force
}

$specs = @(
  [pscustomobject]@{ name="CryptoMiniPC-KrakenCanary"; path=(Join-Path $stateDir "kraken-canary-heartbeat.json"); max_age=60.0; good=@("HEALTHY","CONNECTED") },
  [pscustomobject]@{ name="CryptoMiniPC-KrakenUniverse"; path=(Join-Path $stateDir "kraken-eur-universe-heartbeat.json"); max_age=90.0; good=@("HEALTHY","CONNECTED") },
  [pscustomobject]@{ name="CryptoMiniPC-AltradyTrigger"; path=(Join-Path $stateDir "altrady-trigger-heartbeat.json"); max_age=120.0; good=@("HEALTHY") },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4WSShadow"; path=(Join-Path $stateDir "v2r4-ws-shadow-heartbeat.json"); max_age=45.0; good=@("HEALTHY","DUPLICATE_SKIPPED") },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4ShadowOutcomes"; path=(Join-Path $stateDir "v2r4-ws-shadow-outcome-heartbeat.json"); max_age=90.0; good=@("HEALTHY") },
  [pscustomobject]@{ name="CryptoMiniPC-V2R4ShadowCloudSync"; path=(Join-Path $stateDir "v2r4-shadow-cloud-sync-heartbeat.json"); max_age=240.0; good=@("HEALTHY") },
  [pscustomobject]@{ name="CryptoMiniPC-StatusSync"; path=(Join-Path $stateDir "minipc-status-sync-heartbeat.json"); max_age=900.0; good=@("HEALTHY") }
)

$rows = @()
$restarted = @()
$failed = @()
$restartHistory = Read-RestartHistory
$now = (Get-Date).ToUniversalTime()
$topError = $null
$status = "UNKNOWN"

try {
  foreach ($spec in $specs) {
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

    $lastRestart = $null
    if ($restartHistory.ContainsKey($spec.name)) {
      $lastRestart = $restartHistory[$spec.name]
    }
    $restartAllowed = [bool]$ForceRecovery
    if (-not $restartAllowed) {
      $restartAllowed = (-not $lastRestart) -or (($now - $lastRestart).TotalMinutes -ge $MinRestartIntervalMinutes)
    }

    $action = "NONE"
    if ($needsRecovery -and $restartAllowed) {
      try {
        Stop-ScheduledTask -TaskName $spec.name -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Start-ScheduledTask -TaskName $spec.name
        $restarted += $spec.name
        $restartHistory[$spec.name] = $now
        $action = "RESTART"
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

  if ($restarted.Count -gt 0) { Start-Sleep -Seconds 20 }

  $allHealthy = $true
  foreach ($row in $rows) {
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

    if (-not $healthy) { $allHealthy = $false }
  }

  $status = if ($failed.Count -gt 0) { "CRITICAL" } elseif ($allHealthy) { "HEALTHY" } else { "WARNING" }
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
  error=$topError
  tasks=@($rows)
  guardrails=[pscustomobject]@{
    monitored_tasks_only=$true
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
  $historyTasks[$key] = [ordered]@{
    last_restart_at_utc=$(if ($value) { $value.ToString("o") } else { $null })
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
