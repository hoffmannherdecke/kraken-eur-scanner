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

$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$stateDir = Join-Path $TradingRoot "State"
$logDir = Join-Path $TradingRoot "Logs"
$healthState = Join-Path $stateDir "minipc-health.json"
$healthLog = Join-Path $logDir "minipc-watchdog.log"

foreach ($p in @($repo,$stateDir,$logDir)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $logDir "minipc-post-recovery-$stamp.json"

Stage "1/8 Boot-Zeit und Basisdaten"
$os = Get-CimInstance Win32_OperatingSystem
$boot = [datetime]$os.LastBootUpTime
$now = Get-Date
$uptimeMinutes = [math]::Round(($now - $boot).TotalMinutes,1)

$issues = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Issue([string]$code) {
  if (-not $issues.Contains($code)) { $issues.Add($code) }
}
function Add-Warning([string]$code) {
  if (-not $warnings.Contains($code)) { $warnings.Add($code) }
}

# --- Scheduled tasks: prove automatic post-boot recovery, not just existence.
Stage "2/8 Scheduled Tasks nach Kaltstart"
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
if ($healthTask) {
  if (-not $healthTask.ran_since_boot) { Add-Issue "health_task_not_run_since_boot" }
}

# --- Health state freshness: proves watchdog wrote fresh state after this boot.
Stage "3/8 Watchdog-State und Log-Frische"
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

$lastHealthLogLine = $null
if (Test-Path $healthLog) {
  $lastHealthLogLine = Get-Content $healthLog -Tail 1 -ErrorAction SilentlyContinue
} else {
  Add-Warning "health_log_missing"
}

# --- Core connectivity after cold start.
Stage "4/8 RDP/LAN nach Kaltstart"
$termService = Get-Service TermService -ErrorAction SilentlyContinue
if (-not $termService -or $termService.Status -ne "Running") {
  Add-Issue "rdp_service_not_running"
}

$ipv4 = @(
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.AddressState -eq "Preferred" } |
    Select-Object -ExpandProperty IPAddress
)
if ($ipv4 -notcontains "192.168.178.179") {
  Add-Warning "expected_lan_ip_not_seen"
}

Stage "5/8 Kraken DNS/TCP (je max. 5 Sekunden)"
$krakenDnsOk = $false
$krakenTcpOk = $false
try {
  $dnsTask = [System.Net.Dns]::GetHostAddressesAsync("api.kraken.com")
  if ($dnsTask.Wait(5000)) {
    $krakenDnsOk = @($dnsTask.Result).Count -gt 0
  }
} catch {}

# Use a bounded TcpClient connect instead of Test-NetConnection.
# Test-NetConnection can remain visibly stuck for a long time on some Windows systems.
try {
  $client = [System.Net.Sockets.TcpClient]::new()
  $connectTask = $client.ConnectAsync("api.kraken.com",443)
  if ($connectTask.Wait(5000) -and $client.Connected) {
    $krakenTcpOk = $true
  }
  $client.Dispose()
} catch {
  try { if ($client) { $client.Dispose() } } catch {}
}
if (-not $krakenDnsOk) { Add-Issue "kraken_dns_failed" }
if (-not $krakenTcpOk) { Add-Issue "kraken_tcp443_failed" }

# --- External storage D: mount / identity / health / tiny reversible write-read-delete smoke.
Stage "6/8 Externe Platte D: Mount/Identitaet/RW-Test"
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

# --- Storage/system errors since this boot only.
Stage "7/8 Ereignislog seit diesem Boot (max. 100 letzte Systemevents)"
$postBootStorageErrors = @()
try {
  $postBootStorageErrors = @(
    Get-WinEvent -LogName System -MaxEvents 100 -ErrorAction SilentlyContinue |
      Where-Object {
        $_.TimeCreated -ge $boot -and
        $_.Level -in @(1,2) -and
        $_.ProviderName -match '(?i)(disk|ntfs|volmgr|partmgr|storage|storport|stornvme|usb)'
      } |
      Select-Object -First 20 TimeCreated,Id,ProviderName,LevelDisplayName,Message
  )
  if ($postBootStorageErrors.Count -gt 0) { Add-Warning "post_boot_storage_errors_present" }
} catch {
  Add-Warning "post_boot_storage_event_query_failed"
}

# Expected evidence of the deliberate hard power-loss can exist as Kernel-Power 41.
Stage "8/8 Ergebnis schreiben"
$kernelPower41 = @()
try {
  $kernelPower41 = @(
    Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Kernel-Power'; Id=41; StartTime=$boot.AddMinutes(-5)} -ErrorAction SilentlyContinue |
      Select-Object -First 5 TimeCreated,Id,ProviderName,Message
  )
} catch {}

$status = if ($issues.Count -gt 0) { "FAIL" } elseif ($warnings.Count -gt 0) { "PASS_WITH_NOTES" } else { "PASS" }

$result = [ordered]@{
  kind = "MINIPC_POST_POWER_RECOVERY_GATE_V1"
  checked_at_local = $now.ToString("o")
  status = $status
  issues = @($issues)
  warnings = @($warnings)
  boot = [ordered]@{
    last_boot = $boot.ToString("o")
    uptime_minutes = $uptimeMinutes
    kernel_power_41_count = $kernelPower41.Count
  }
  rdp = [ordered]@{
    termservice = if ($termService) { [string]$termService.Status } else { "Missing" }
    ipv4 = $ipv4
  }
  scheduled_tasks = $tasks
  watchdog = [ordered]@{
    state_path = $healthState
    status = if ($health) { [string]$health.status } else { $null }
    checked_at = if ($healthChecked) { $healthChecked.ToString("o") } else { $null }
    age_minutes = $healthAgeMinutes
    last_log_line = $lastHealthLogLine
  }
  network = [ordered]@{
    kraken_dns = $krakenDnsOk
    kraken_tcp443 = $krakenTcpOk
  }
  external_storage = $external
  post_boot_storage_errors = $postBootStorageErrors
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
Write-Host ("RDP: TermService=" + $result.rdp.termservice + " | expected LAN IP=" + ($ipv4 -contains "192.168.178.179"))
Write-Host ("Tasks found: " + $tasks.Count + "/3 | Health ran since boot=" + $(if ($healthTask) { $healthTask.ran_since_boot } else { $false }))
Write-Host ("Watchdog: " + $result.watchdog.status + " | age=" + $healthAgeMinutes + " min")
Write-Host ("Kraken: DNS=" + $krakenDnsOk + " | TCP443=" + $krakenTcpOk)
Write-Host ("D: present=" + $external.present + " | label=" + $external.label + " | fs=" + $external.filesystem + " | health=" + $external.health + " | free=" + $external.free_gb + " GB")
Write-Host ("D: disk=" + $external.disk_model + " | bus=" + $external.bus_type + " | disk_health=" + $external.disk_health + " | RW-delete=" + $external.write_read_delete_smoke)
Write-Host ("Post-boot storage Critical/Error events: " + $postBootStorageErrors.Count)
if ($issues.Count -gt 0) { Write-Host ("Issues: " + ($issues -join ", ")) } else { Write-Host "Issues: none" }
if ($warnings.Count -gt 0) { Write-Host ("Notes: " + ($warnings -join ", ")) } else { Write-Host "Notes: none" }
Write-Host ("Report: " + $reportPath)
Write-Host "=== END ==="

if ($issues.Count -gt 0) { exit 2 }
exit 0
