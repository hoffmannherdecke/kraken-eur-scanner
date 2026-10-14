param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading'),
  [string]$PatcherPath = '',
  [switch]$Apply
)

# One-time pinned-source fix only (NOT a new Windows service or task).
# Does not stop/start tasks or touch live watcher state, Kraken, V3 or orders.
$ErrorActionPreference = 'Stop'
$taskName = 'CryptoMiniPC-V2R4WSShadow'
$expectedOldSha = '86A99A778C6062F683194B4AD61CDD9EDDD11D477B1338DB46B90528A7588604'
$src = Join-Path $TradingRoot 'Runtime\v2r4-ws-shadow-code\paper_evaluator\v2r4_ws_shadow_watcher.py'
$python = Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$backupParent = Join-Path $TradingRoot 'Backups'
$staging = Join-Path $TradingRoot 'Staging'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop

if ([string]::IsNullOrWhiteSpace($PatcherPath)) {
  throw 'PatcherPath to verified GitHub source is required'
}
foreach ($path in @($src,$python,$PatcherPath)) {
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing source: $path" }
}
if (@($task.Actions).Count -ne 1 -or
    $task.Principal.UserId -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18') -or
    ([string]$task.Actions[0].Execute).Trim('"') -ine $python -or
    ([string]$task.Actions[0].Arguments).IndexOf($src,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
  throw 'Live WS-Shadow scheduled task action or SYSTEM identity does not match original'
}
if (([string]$task.Actions[0].Arguments) -notmatch '--heartbeat' -or
    ([string]$task.Actions[0].Arguments) -notmatch '--state' -or
    ([string]$task.Actions[0].Arguments) -notmatch '--snapshot') {
  throw 'Original watcher arguments unexpectedly changed'
}
$currentSha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
if ($currentSha -ne $expectedOldSha) {
  throw "Watcher source SHA mismatch: $currentSha. No mutation permitted."
}
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Administrator PowerShell required'
}
Write-Host "WS_SHADOW_LAST_EUR_PREFLIGHT_PASS original=$currentSha task=$($task.State)"
if (-not $Apply) {
  Write-Host 'WS_SHADOW_FIX_READ_ONLY_NO_ACTION'
  return
}

# Make snapshot before ANY source modification. Existing JSON state is NOT rolled
# back; no new manager, heartbeat or task scheduler action is installed.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $backupParent "WSShadow-LastEurFix-$stamp"
if (Test-Path $backup) { throw 'Backup directory already exists' }
New-Item -Path $backup -ItemType Directory -ErrorAction Stop | Out-Null
$backupSource = Join-Path $backup 'original-watcher.py'
Copy-Item -LiteralPath $src -Destination $backupSource -ErrorAction Stop
if ((Get-FileHash $backupSource -Algorithm SHA256).Hash -ne $expectedOldSha) {
  throw 'Backup does not match live pinned source'
}
$xml = Export-ScheduledTask -TaskName $taskName -ErrorAction Stop
if ([string]::IsNullOrWhiteSpace($xml)) { throw 'Original scheduled task XML not available' }
[System.IO.File]::WriteAllText(
  (Join-Path $backup 'original-task.xml'), $xml,
  [System.Text.Encoding]::Unicode
)
$manifest = [ordered]@{
  kind = 'WS_SHADOW_LAST_EUR_FIX_V1'
  pinned_source = $src
  original_sha256 = $expectedOldSha
  backup_source = $backupSource
  original_task = $taskName
  created_at = (Get-Date).ToString('o')
  live_state_or_ledger_modified = $false
  task_action_modified = $false
  restore_old_state_on_rollback = $false
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backup 'manifest.json') -Encoding UTF8

# Create a candidate in the new backup directory; never run the real watcher.
$candidate = Join-Path $backup 'fixed-watcher.py'
& $python -B $PatcherPath --source $src --output $candidate --original-sha256 $expectedOldSha
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $candidate)) {
  throw 'Pinned source last-price fix builder failed'
}
$alteredSha = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
if ($alteredSha -eq $expectedOldSha) { throw 'Source patch produced identical code unexpectedly' }
$originalFooter = 'v2r4-ws-shadow-python-crash.log'
if (-not (Select-String -LiteralPath $src -Pattern $originalFooter -SimpleMatch -Quiet) -or
    -not (Select-String -LiteralPath $candidate -Pattern $originalFooter -SimpleMatch -Quiet)) {
  throw 'Installed PR297 crash footer must remain preserved'
}
& $python -m py_compile $candidate
if ($LASTEXITCODE -ne 0) { throw 'Fixed source syntax failed' }
if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $expectedOldSha) {
  throw 'Pinned source changed since backup; refusing swap'
}

# Atomic replacement at the ORIGINAL path, preserving the current task action.
# Existing running Python processes retain their already-imported code;
# source fix starts with the next NATURAL scheduled launch, no forced restart.
$swap = $src + '.last-eur-fix-once.tmp'
if (Test-Path -LiteralPath $swap) { throw 'Unexpected pre-existing swap file' }
Copy-Item -LiteralPath $candidate -Destination $swap -ErrorAction Stop
if ((Get-FileHash -LiteralPath $swap -Algorithm SHA256).Hash -ne $alteredSha) {
  Remove-Item -LiteralPath $swap -Force -ErrorAction SilentlyContinue
  throw 'Swap file content differs from staged source'
}
$replaced = $false
try {
  [System.IO.File]::Replace(
    $swap, $src, (Join-Path $backup 'atomic-previous-watcher.py'), $true
  )
  $replaced = $true
  if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $alteredSha) {
    throw 'Unexpected live source hash after atomic replacement'
  }
  $newTask = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
  if (@($newTask.Actions).Count -ne 1 -or
      ([string]$newTask.Actions[0].Arguments).IndexOf($src,[StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'Task action changed during swap'
  }
  Write-Host "WS_SHADOW_LAST_EUR_FIX_INSTALLED new_sha256=$alteredSha"
  Write-Host "BACKUP_DIRECTORY=$backup"
  Write-Host 'ORIGINAL_TASK_ACTION_UNCHANGED; NO_FORCED_RESTART'
  Write-Host 'AWAIT_NATURAL_SYSTEM_RESTART_AND_CONFIRM_HEALTHY_CYCLES'
} catch {
  $first = $_.Exception.Message
  # Only source bytes may be rolled back. Never restore old state/ACK ledgers.
  if ($replaced) {
    try {
      $rollback = $src + '.last-eur-fix-rollback.tmp'
      if (Test-Path $rollback) { throw 'Rollback temp file unexpectedly exists' }
      Copy-Item -LiteralPath $backupSource -Destination $rollback
      [System.IO.File]::Replace(
        $rollback, $src, (Join-Path $backup 'failed-diagnostic-watcher.py'), $true
      )
      if ((Get-FileHash $src -Algorithm SHA256).Hash -eq $expectedOldSha) {
        Write-Host 'WS_SHADOW_LAST_EUR_SOURCE_ROLLBACK_PASS'
      } else {
        Write-Host 'WS_SHADOW_LAST_EUR_CRITICAL_MANUAL_RECOVERY_REQUIRED'
      }
    } catch {
      Write-Host "WS_SHADOW_LAST_EUR_CRITICAL_MANUAL_RECOVERY_REQUIRED $($_.Exception.Message)"
    }
  }
  throw $first
} finally {
  if (Test-Path $swap) { Remove-Item $swap -Force -ErrorAction SilentlyContinue }
}
