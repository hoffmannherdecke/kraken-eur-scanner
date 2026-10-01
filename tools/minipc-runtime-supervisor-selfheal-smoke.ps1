param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$TargetTask = "CryptoMiniPC-V2R4ShadowCloudSync",
  [int]$TimeoutSeconds = 210
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "Bitte dieses Skript in einer als Administrator gestarteten PowerShell ausführen."
}

if ($TimeoutSeconds -lt 120 -or $TimeoutSeconds -gt 300) {
  throw "TimeoutSeconds must be between 120 and 300."
}

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$supervisorTaskName = "CryptoMiniPC-RuntimeSupervisor"
$supervisorState = Join-Path $TradingRoot "State\minipc-runtime-supervisor.json"
$watchdog = Join-Path $repo "tools\minipc-watchdog.ps1"
$cloudHeartbeat = Join-Path $TradingRoot "State\v2r4-shadow-cloud-sync-heartbeat.json"
$reportPath = Join-Path $TradingRoot "Logs\minipc-runtime-supervisor-selfheal-latest.json"

foreach ($p in @($repo,$supervisorState,$watchdog,$cloudHeartbeat)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$supervisorTask = Get-ScheduledTask -TaskName $supervisorTaskName -ErrorAction SilentlyContinue
if (-not $supervisorTask) { throw "$supervisorTaskName is not installed." }

$target = Get-ScheduledTask -TaskName $TargetTask -ErrorAction SilentlyContinue
if (-not $target) { throw "$TargetTask is not installed." }

$beforeSupervisor = Get-Content $supervisorState -Raw | ConvertFrom-Json
if ($beforeSupervisor.status -ne "HEALTHY") {
  throw "Runtime supervisor is not HEALTHY before self-heal smoke."
}

$beforeHeartbeat = Get-Content $cloudHeartbeat -Raw | ConvertFrom-Json
if ($beforeHeartbeat.status -ne "HEALTHY") {
  throw "Target cloud-sync heartbeat is not HEALTHY before self-heal smoke."
}
if ([string]$beforeHeartbeat.strategy_action -ne "NONE_ARCHIVE_ONLY" -or [bool]$beforeHeartbeat.real_money_actions) {
  throw "Target guardrails are not in the expected archive-only state."
}
$beforeChecked = ([datetime]$beforeHeartbeat.checked_at_utc).ToUniversalTime()

Write-Host "=== MINI-PC RUNTIME SUPERVISOR SELF-HEAL SMOKE ==="
Write-Host ("Target: " + $TargetTask)
Write-Host ("Before heartbeat: " + $beforeHeartbeat.status + " @ " + $beforeChecked.ToString("o"))
Write-Host "Stopping the idempotent archive-only support task once..."
Stop-ScheduledTask -TaskName $TargetTask -ErrorAction Stop

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$recovered = $false
$lastTaskState = $null
$afterHeartbeat = $null
$afterSupervisor = $null

while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 5

  $targetNow = Get-ScheduledTask -TaskName $TargetTask -ErrorAction SilentlyContinue
  if ($targetNow) { $lastTaskState = [string]$targetNow.State }

  if (Test-Path $cloudHeartbeat) {
    try { $afterHeartbeat = Get-Content $cloudHeartbeat -Raw | ConvertFrom-Json } catch {}
  }
  if (Test-Path $supervisorState) {
    try { $afterSupervisor = Get-Content $supervisorState -Raw | ConvertFrom-Json } catch {}
  }

  $hbAdvanced = $false
  if ($afterHeartbeat -and $afterHeartbeat.checked_at_utc) {
    try {
      $afterChecked = ([datetime]$afterHeartbeat.checked_at_utc).ToUniversalTime()
      $hbAdvanced = ($afterChecked -gt $beforeChecked)
    } catch {}
  }

  $supervisorSawTarget = $false
  if ($afterSupervisor -and $afterSupervisor.tasks) {
    foreach ($row in $afterSupervisor.tasks) {
      if ($row.task -eq $TargetTask -and $row.action -eq "RESTART" -and $row.healthy_after -eq $true) {
        $supervisorSawTarget = $true
        break
      }
    }
  }

  $guardrailsOk = (
    $afterHeartbeat -and
    $afterHeartbeat.status -eq "HEALTHY" -and
    [string]$afterHeartbeat.strategy_action -eq "NONE_ARCHIVE_ONLY" -and
    -not [bool]$afterHeartbeat.real_money_actions
  )

  if ($lastTaskState -eq "Running" -and $hbAdvanced -and $supervisorSawTarget -and $guardrailsOk) {
    $recovered = $true
    break
  }
}

& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdog -TradingRoot $TradingRoot | Out-Null
$watchdogCode = $LASTEXITCODE
$healthPath = Join-Path $TradingRoot "State\minipc-health.json"
$health = if (Test-Path $healthPath) { Get-Content $healthPath -Raw | ConvertFrom-Json } else { $null }

$result = [ordered]@{
  schema_version = 1
  kind = "MINIPC_RUNTIME_SUPERVISOR_SELFHEAL_V1"
  checked_at_local = (Get-Date).ToString("o")
  status = $(if ($recovered -and $watchdogCode -eq 0) { "PASS" } else { "FAIL" })
  target_task = $TargetTask
  target_state_after = $lastTaskState
  before_heartbeat_utc = $beforeChecked.ToString("o")
  after_heartbeat_utc = $(if ($afterHeartbeat) { $afterHeartbeat.checked_at_utc } else { $null })
  supervisor_status = $(if ($afterSupervisor) { $afterSupervisor.status } else { $null })
  watchdog_status = $(if ($health) { $health.status } else { $null })
  guardrails = [ordered]@{
    strategy_changes = $false
    evaluator_invoked = $false
    order_api = $false
    real_money_actions = $false
  }
}

[System.IO.File]::WriteAllText(
  $reportPath,
  ($result | ConvertTo-Json -Depth 8) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== MINI-PC RUNTIME SUPERVISOR SELF-HEAL SUMMARY ==="
Write-Host ("Status: " + $result.status)
Write-Host ("Target task after test: " + $result.target_state_after)
Write-Host ("Heartbeat advanced: " + $(if ($afterHeartbeat) { $afterHeartbeat.checked_at_utc } else { "missing" }))
Write-Host ("Supervisor: " + $result.supervisor_status)
Write-Host ("Local watchdog: " + $result.watchdog_status)
Write-Host ("Report: " + $reportPath)
Write-Host "Safety: ARCHIVE SUPPORT TASK ONLY / NO STRATEGY CHANGE / NO EVALUATOR / NO ORDERS / NO REAL-MONEY ACTION"
Write-Host "=== END ==="

if ($result.status -ne "PASS") { exit 2 }
exit 0
