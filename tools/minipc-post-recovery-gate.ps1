param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$ExternalDriveLetter = "D:",
  [string]$ExpectedExternalLabel = "Mistral_450"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Stage([string]$Text) {
  Write-Host ("[POST-RECOVERY] " + $Text)
}

$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$healthState = Join-Path $stateDir "minipc-health.json"
$healthLog = Join-Path $logDir "minipc-watchdog.log"

foreach ($p in @($stateDir,$logDir)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $logDir "minipc-post-recovery-$stamp.json"
$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Issue([string]$code) {
  if (-not $issues.Contains($code)) { $issues.Add($code) }
}
function Add-Warning([string]$code) {
  if (-not $warnings.Contains($code)) { $warnings.Add($code) }
}

Stage "1/5 Boot-Zeit"
$os = Get-CimInstance Win32_OperatingSystem
$boot = [datetime]$os.LastBootUpTime
$now = Get-Date
$uptimeMinutes = [math]::Round(($now - $boot).TotalMinutes,1)

Stage "2/5 Scheduled Tasks nach Kaltstart"
$taskNames = @("CryptoMiniPC-Health","CryptoMiniPC-Backup","CryptoMiniPC-LogCleanup")
$tasks = @()
foreach ($name in $taskNames) {
  $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  if (-not $task) {
    Add-Issue ("task_missing_" + $name)
    continue
  }
  $info = $task | Get-ScheduledTaskInfo
  $lastRun = $info.LastRunTime
  $tasks += [ordered]@{
    name = $name
    state = [string]$task.State
    last_run = if ($lastRun -and $lastRun -gt [datetime]::MinValue) { $lastRun.ToString("o") } else { $null }
    last_result = [int]$info.LastTaskResult
    next_run = if ($info.NextRunTime -and $info.NextRunTime -gt [datetime]::MinValue) { $info.NextRunTime.ToString("o") } else { $null }
    ran_since_boot = [bool]($lastRun -and $lastRun -ge $boot)
  }

  if ([int]$info.LastTaskResult -notin @(0,267011)) {
    Add-Issue ("task_bad_result_" + $name)
  }
}
$healthTask = $tasks | Where-Object { $_.name -eq "CryptoMiniPC-Health" } | Select-Object -First 1
if ($healthTask -and -not $healthTask.ran_since_boot) {
  Add-Issue "health_task_not_run_since_boot"
}

Stage "3/5 Watchdog-State nach Kaltstart"
$health = $null
$healthAgeMinutes = $null
$healthChecked = $null
if (-not (Test-Path $healthState)) {
  Add-Issue "health_state_missing"
} else {
  try {
    $health = Get-Content $healthState -Raw | ConvertFrom-Json
    $healthChecked = [datetime]$health.checked_at_local
    $healthAgeMinutes = [math]::Round(($now - $healthChecked).TotalMinutes,2)
    if ($healthChecked -lt $boot) { Add-Issue "health_state_predates_boot" }
    if ($healthAgeMinutes -gt 10) { Add-Issue "health_state_stale" }
    if ([string]$health.status -eq "CRITICAL") { Add-Issue "watchdog_critical" }
    elseif ([string]$health.status -eq "WARNING") { Add-Warning "watchdog_warning" }
  } catch {
    Add-Issue "health_state_invalid_json"
  }
}
$lastHealthLogLine = if (Test-Path $healthLog) {
  Get-Content $healthLog -Tail 1 -ErrorAction SilentlyContinue
} else {
  Add-Warning "health_log_missing"
  $null
}

Stage "4/5 Externe Platte D: Mount/Health/RW"
$driveLetter = $ExternalDriveLetter.TrimEnd(":")
$external = [ordered]@{
  requested_drive = $ExternalDriveLetter
  present = $false
  label = $null
  filesystem = $null
  health = $null
  operational = $null
  size_gb = $null
  free_gb = $null
  bus_type = $null
  disk_model = $null
  disk_health = $null
  write_read_delete_smoke = $false
}
$volume = Get-Volume -DriveLetter $driveLetter -ErrorAction SilentlyContinue
if (-not $volume) {
  Add-Issue "external_drive_missing"
} else {
  $external.present = $true
  $external.label = [string]$volume.FileSystemLabel
  $external.filesystem = [string]$volume.FileSystem
  $external.health = [string]$volume.HealthStatus
  $external.operational = [string]($volume.OperationalStatus -join ",")
  $external.size_gb = [math]::Round($volume.Size/1GB,1)
  $external.free_gb = [math]::Round($volume.SizeRemaining/1GB,1)

  if ($ExpectedExternalLabel -and $external.label -ne $ExpectedExternalLabel) {
    Add-Warning "external_drive_label_mismatch"
  }
  if ($external.health -and $external.health -notin @("Healthy","Unknown")) {
    Add-Issue "external_volume_unhealthy"
  }

  try {
    $partition = Get-Partition -DriveLetter $driveLetter -ErrorAction Stop
    $disk = $partition | Get-Disk -ErrorAction Stop
    $external.bus_type = [string]$disk.BusType
    $external.disk_model = [string]$disk.FriendlyName
    $external.disk_health = [string]$disk.HealthStatus
    if ($external.disk_health -and $external.disk_health -notin @("Healthy","Unknown")) {
      Add-Issue "external_disk_unhealthy"
    }
  } catch {
    Add-Warning "external_disk_mapping_unavailable"
  }

  $smokePath = Join-Path ($driveLetter + ":\") (".minipc-storage-smoke-" + [guid]::NewGuid().ToString("N") + ".tmp")
  $payload = "MINIPC_STORAGE_SMOKE|" + [guid]::NewGuid().ToString("N")
  try {
    [System.IO.File]::WriteAllText($smokePath,$payload,[System.Text.UTF8Encoding]::new($false))
    $readBack = [System.IO.File]::ReadAllText($smokePath,[System.Text.Encoding]::UTF8)
    if ($readBack -ne $payload) { throw "readback mismatch" }
    Remove-Item -LiteralPath $smokePath -Force
    if (Test-Path $smokePath) { throw "temporary smoke file not removed" }
    $external.write_read_delete_smoke = $true
  } catch {
    try { if (Test-Path $smokePath) { Remove-Item -LiteralPath $smokePath -Force -ErrorAction SilentlyContinue } } catch {}
    Add-Issue "external_drive_rw_smoke_failed"
  }
}

Stage "5/5 Ergebnis"
$status = if ($issues.Count -gt 0) { "FAIL" } elseif ($warnings.Count -gt 0) { "PASS_WITH_NOTES" } else { "PASS" }

$result = [ordered]@{
  kind = "MINIPC_POST_POWER_RECOVERY_GATE_V2"
  checked_at_local = $now.ToString("o")
  status = $status
  issues = @($issues)
  warnings = @($warnings)
  boot = [ordered]@{
    last_boot = $boot.ToString("o")
    uptime_minutes = $uptimeMinutes
  }
  scheduled_tasks = $tasks
  watchdog = [ordered]@{
    state_path = $healthState
    status = if ($health) { [string]$health.status } else { $null }
    checked_at = if ($healthChecked) { $healthChecked.ToString("o") } else { $null }
    age_minutes = $healthAgeMinutes
    last_log_line = $lastHealthLogLine
  }
  external_storage = $external
  evidence_note = "RDP and AC-recovery were already proven by the successful physical power-loss test and restored remote session. Fresh watchdog state additionally proves its built-in local Kraken DNS/TCP/HTTPS checks ran after boot."
  guardrails = [ordered]@{
    strategy_changes = $false
    real_money_actions = $false
    order_api = $false
    git_mutation = $false
    configuration_changes = $false
    external_storage_test = "temporary write-read-delete only; file removed"
  }
  report = $reportPath
}

[System.IO.File]::WriteAllText(
  $reportPath,
  ($result | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
  [System.Text.UTF8Encoding]::new($false)
)

Write-Host ""
Write-Host "=== POST-POWER-RECOVERY FINAL SUMMARY ==="
Write-Host ("Status: " + $status)
Write-Host ("Boot: " + $boot.ToString("yyyy-MM-dd HH:mm:ss") + " | uptime=" + $uptimeMinutes + " min")
Write-Host ("Tasks found: " + $tasks.Count + "/3 | Health ran since boot=" + $(if ($healthTask) { $healthTask.ran_since_boot } else { $false }))
Write-Host ("Watchdog: " + $result.watchdog.status + " | age=" + $healthAgeMinutes + " min")
Write-Host ("D: present=" + $external.present + " | label=" + $external.label + " | fs=" + $external.filesystem + " | health=" + $external.health + " | free=" + $external.free_gb + " GB")
Write-Host ("D: disk=" + $external.disk_model + " | bus=" + $external.bus_type + " | disk_health=" + $external.disk_health + " | RW-delete=" + $external.write_read_delete_smoke)
if ($issues.Count -gt 0) { Write-Host ("Issues: " + ($issues -join ", ")) } else { Write-Host "Issues: none" }
if ($warnings.Count -gt 0) { Write-Host ("Notes: " + ($warnings -join ", ")) } else { Write-Host "Notes: none" }
Write-Host ("Report: " + $reportPath)
Write-Host "=== END ==="

if ($issues.Count -gt 0) { exit 2 }
exit 0
