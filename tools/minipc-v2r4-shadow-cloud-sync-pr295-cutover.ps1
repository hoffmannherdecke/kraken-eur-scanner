param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading'),
  [string]$BackupDir = (Join-Path $env:USERPROFILE 'Trading\Backups\PR295-CloudSync-20261014-081243'),
  [string]$StageDir = (Join-Path $env:USERPROFILE 'Trading\Staging\kraken-shadow-pr295-offline'),
  [switch]$Apply
)

# ONE SHOT, original CloudSync task ONLY. No scheduler/new daemon installed.
# Never call the original installer: its --once invokes the live relay!
$ErrorActionPreference = 'Stop'
$targetName = 'CryptoMiniPC-V2R4ShadowCloudSync'
$supervisorName = 'CryptoMiniPC-RuntimeSupervisor'
$expectedCommit = '3b958e95a851dd53603c9bb0019ae640324d74f8'
$sourcePath = Join-Path $TradingRoot 'Repos\kraken-eur-scanner\tools\v2r4-shadow-cloud-sync.py'
$stagePath = Join-Path $StageDir 'tools\v2r4-shadow-cloud-sync.py'
$backupSource = Join-Path $BackupDir 'original-cloud-sync.py'
$manifestPath = Join-Path $BackupDir 'rollback-manifest.json'
$hbPath = Join-Path $TradingRoot 'State\v2r4-shadow-cloud-sync-heartbeat.json'
$statePath = Join-Path $TradingRoot 'State\v2r4-shadow-cloud-sync-state.json'

function Sha([string]$path) {
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash
}
function Task([string]$name) {
  return Get-ScheduledTask -TaskName $name -ErrorAction Stop
}
function Wait-NotRunning([string]$name,[int]$seconds=30) {
  $until = (Get-Date).AddSeconds($seconds)
  do {
    if ((Task $name).State -ne 'Running') { return }
    Start-Sleep -Milliseconds 300
  } while ((Get-Date) -lt $until)
  throw "Task bleibt Running: $name"
}
function Assert-NoCloudWorker {
  # Fail closed rather than replacing the code while a child Python process is alive.
  $running = @(Get-CimInstance Win32_Process -ErrorAction Stop |
    Where-Object {
      $_.Name -in @('python.exe','pythonw.exe') -and
      $null -ne $_.CommandLine -and
      $_.CommandLine.IndexOf($sourcePath,[StringComparison]::OrdinalIgnoreCase) -ge 0
    })
  if ($running.Count -ne 0) { throw "Python CloudSync Originalprozess weiterhin aktiv ($($running.Count))" }
}
function Atomic-Swap([string]$from,[string]$expected,[string]$previousBackup) {
  $swap = $sourcePath + '.pr295-once.tmp'
  if (Test-Path -LiteralPath $swap) { throw "Vorhandene Swap-Datei: $swap" }
  Copy-Item -LiteralPath $from -Destination $swap -ErrorAction Stop
  try {
    if ((Sha $swap) -ne $expected) { throw 'Swap-Quelldatei Hash falsch' }
    [System.IO.File]::Replace($swap,$sourcePath,$previousBackup,$true)
    if ((Sha $sourcePath) -ne $expected) { throw 'Swap-Ziel Hash falsch' }
  } finally {
    if (Test-Path -LiteralPath $swap) { Remove-Item -LiteralPath $swap -Force }
  }
}
function Verify-NewHeartbeat([datetime]$started) {
  $until = (Get-Date).AddSeconds(65)
  do {
    $t = Task $targetName
    if ($t.State -eq 'Running' -and (Test-Path -LiteralPath $hbPath)) {
      try {
        $h = Get-Content -LiteralPath $hbPath -Raw -ErrorAction Stop | ConvertFrom-Json
        $checked = ([datetime]$h.checked_at_utc).ToUniversalTime()
        $cycle = ([datetime]$h.cycle_started_at_utc).ToUniversalTime()
        $age = ([datetime]::UtcNow - $checked).TotalSeconds
        if ($h.status -eq 'HEALTHY' -and $h.kind -eq 'V2R4_SHADOW_CLOUD_SYNC_HEARTBEAT_V1' -and
            $h.cycle_duration_seconds -ne $null -and $cycle -ge $started.AddSeconds(-1) -and
            $checked -ge $cycle -and $age -ge -10 -and $age -le 25) {
          return $h
        }
        if ($h.status -eq 'DEGRADED' -and $cycle -ge $started.AddSeconds(-1)) {
          throw "Neuer CloudSync Heartbeat DEGRADED: $($h.detail)"
        }
      } catch [System.Management.Automation.RuntimeException] {
        if ($_.Exception.Message -match 'Neuer CloudSync Heartbeat DEGRADED') { throw }
      }
    }
    Start-Sleep -Seconds 2
  } while ((Get-Date) -lt $until)
  throw 'Neuer CloudSync hat keinen frischen erfolgreichen kompletten Zyklus innerhalb 65s nachgewiesen'
}

# Preflight: abort without change on any unexpected prior state.
if (-not (Test-Path -LiteralPath $stagePath) -or
    -not (Test-Path -LiteralPath $backupSource) -or
    -not (Test-Path -LiteralPath $manifestPath) -or
    -not (Test-Path -LiteralPath $sourcePath) -or
    -not (Test-Path -LiteralPath $statePath) -or
    -not (Test-Path -LiteralPath (Join-Path $BackupDir 'original-task.xml'))) {
  throw 'Pflichtdatei fehlt: bestehende Quelle, Staging, Backup, Task-XML oder Live-ACK-State'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Als Administrator ausführen' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$oldHash = [string]$manifest.original_sha256
$newHash = [string]$manifest.new_sha256
if ($manifest.staging_commit -ne $expectedCommit -or
    $manifest.original_path -ne $sourcePath -or
    $manifest.original_task -ne $targetName -or
    $manifest.restore_old_ack_state -ne $false -or
    (Sha $sourcePath) -ne $oldHash -or
    (Sha $backupSource) -ne $oldHash -or
    (Sha $stagePath) -ne $newHash -or $oldHash -eq $newHash) {
  throw 'Sicherheitsgate: Original, SHA, Backup oder Merge-Commit inkonsistent'
}
$actualCommit = (git -C $StageDir rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualCommit -ne $expectedCommit) { throw 'Staging-Commit unpassend' }
$t = Task $targetName
$s = Task $supervisorName
if ($t.State -ne 'Running') { throw 'CloudSync Originaltask nicht Running' }
if ($s.State -eq 'Disabled') { throw 'Supervisor war bereits deaktiviert; Abbruch' }
if ($t.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) { throw 'CloudSync Task nicht SYSTEM' }
if (@($t.Actions).Count -ne 1 -or
    ([string]$t.Actions[0].Arguments).IndexOf($sourcePath,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
  throw 'Live Task zeigt nicht auf genau die geprüfte Original-Python-Datei'
}

Write-Host 'PR295_CUTOVER_PREFLIGHT_PASS'
Write-Host "OriginalHash=$oldHash"
Write-Host "NewHash=$newHash"
Write-Host "Backup=$BackupDir"
if (-not $Apply) {
  Write-Host 'PR295_READ_ONLY_NO_ACTION; -Apply ist zum gezielten Cutover nötig'
  return
}

$supervisorDisabled = $false
$cloudStopped = $false
$changedSource = $false
$completed = $false
$rollbackOk = $false
$gateError = $null
try {
  # Supervisor is a scheduled 2-minute task. Disable while idle to avoid a
  # competing self-heal/restart during our one-component replacement.
  $until = (Get-Date).AddSeconds(45)
  while ((Task $supervisorName).State -eq 'Running' -and (Get-Date) -lt $until) {
    Start-Sleep -Milliseconds 500
  }
  if ((Task $supervisorName).State -eq 'Running') { throw 'Supervisor momentan beschäftigt; ohne Änderung abbrechen' }
  Disable-ScheduledTask -TaskName $supervisorName -ErrorAction Stop | Out-Null
  $supervisorDisabled = $true
  if ((Task $supervisorName).State -ne 'Disabled') { throw 'Supervisor nicht sicher deaktiviert' }

  Stop-ScheduledTask -TaskName $targetName -ErrorAction Stop
  Wait-NotRunning $targetName 30
  $cloudStopped = $true
  Assert-NoCloudWorker

  # No state rollback or deletion! Preserve current sent ACKs and late results.
  if ((Sha $sourcePath) -ne $oldHash) { throw 'Original SHA hat sich nach Preflight verändert' }
  Atomic-Swap $stagePath $newHash (Join-Path $BackupDir 'pr295-swap-previous.py')
  $changedSource = $true
  $started = [datetime]::UtcNow
  Start-ScheduledTask -TaskName $targetName -ErrorAction Stop
  $newHeartbeat = Verify-NewHeartbeat $started
  if ((Sha $sourcePath) -ne $newHash) { throw 'Produktive SHA ist nach dem Start verändert' }

  $completed = $true
  Write-Host "PR295_CLOUDSYNC_FIRST_CYCLE_PASS DurationSeconds=$($newHeartbeat.cycle_duration_seconds)"
} catch {
  $gateError = $_.Exception.Message
  Write-Host "PR295_CUTOVER_ERROR $gateError"
  try {
    if ($changedSource) {
      $current = Task $targetName
      if ($current.State -eq 'Running') { Stop-ScheduledTask -TaskName $targetName -ErrorAction Stop }
      Wait-NotRunning $targetName 30
      Assert-NoCloudWorker
      Atomic-Swap $backupSource $oldHash (Join-Path $BackupDir 'pr295-failed-new-source.py')
    }
    if ($cloudStopped) {
      if ((Task $targetName).State -ne 'Running') {
        Start-ScheduledTask -TaskName $targetName -ErrorAction Stop
      }
    }
    $rollbackOk = ((Sha $sourcePath) -eq $oldHash -and (Task $targetName).State -eq 'Running')
    if ($rollbackOk) { Write-Host 'PR295_ORIGINAL_ROLLBACK_STARTED_NEEDS_RUNTIME_ACK' }
  } catch {
    Write-Host "PR295_CRITICAL_MANUAL_RECOVERY_REQUIRED $($_.Exception.Message)"
  }
} finally {
  if ($supervisorDisabled) {
    try {
      Enable-ScheduledTask -TaskName $supervisorName -ErrorAction Stop | Out-Null
      if ((Task $supervisorName).State -eq 'Disabled') { throw 'Supervisor blieb Disabled' }
      Write-Host 'PR295_SUPERVISOR_REENABLED'
    } catch {
      Write-Host "PR295_CRITICAL_SUPERVISOR_REENABLE_REQUIRED $($_.Exception.Message)"
      $completed = $false
    }
  }
}
if (-not $completed) {
  throw "PR295_CUTOVER_NOT_ACCEPTED error=$gateError rollback_started=$rollbackOk"
}
Write-Host 'PR295_CLOUDSYNC_HOST_CUTOVER_INITIAL_PASS'
Write-Host 'SUPABASE_ACK_AND_SECOND_CYCLE_STILL_REQUIRED'
