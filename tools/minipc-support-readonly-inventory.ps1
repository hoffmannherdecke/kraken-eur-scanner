#requires -Version 5.1
<#
  MINI-PC SUPPORT V1 / block 1, read-only, non-admin.
  No network, secrets, file writes, service restarts, task dispatch or repo pull.
  Use from the local MINI-PC PowerShell: & "$HOME\Trading\Repos\kraken-eur-scanner\tools\minipc-support-readonly-inventory.ps1"
#>
param(
    [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading")
)
$ErrorActionPreference = "Stop"

$os = Get-CimInstance -ClassName Win32_OperatingSystem
$processors = @(Get-CimInstance -ClassName Win32_Processor)
$cpuValues = @($processors | ForEach-Object { [double]$_.LoadPercentage })
$cpuAvg = if ($cpuValues.Count) { [math]::Round(($cpuValues | Measure-Object -Average).Average, 1) } else { $null }
$ramTotal = [math]::Round([double]$os.TotalVisibleMemorySize / 1048576, 2)
$ramFree = [math]::Round([double]$os.FreePhysicalMemory / 1048576, 2)

$volumes = @()
foreach ($disk in @(Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=3")) {
    if ($disk.DeviceID -notin @("C:", "D:")) { continue }
    $volumes += [ordered]@{
        drive = [string]$disk.DeviceID
        filesystem = [string]$disk.FileSystem
        free_gb = [math]::Round([double]$disk.FreeSpace / 1GB, 1)
        total_gb = [math]::Round([double]$disk.Size / 1GB, 1)
    }
}

$healthPath = Join-Path $TradingRoot "State\minipc-health.json"
$health = [ordered]@{ present = $false; status = "NOT_READ"; checked_at_local = $null }
if (Test-Path -LiteralPath $healthPath -PathType Leaf) {
    $health.present = $true
    try {
        $stored = Get-Content -LiteralPath $healthPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $health.status = [string]$stored.status
        if ($stored.PSObject.Properties["checked_at_local"]) {
            $health.checked_at_local = [string]$stored.checked_at_local
        }
    } catch {
        $health.status = "INVALID_OR_UNREADABLE"
    }
}

$taskSummary = @()
try {
    $tasks = @(Get-ScheduledTask -TaskName "CryptoMiniPC-*" -ErrorAction Stop)
    foreach ($task in $tasks) {
        $entry = [ordered]@{ name = [string]$task.TaskName; state = [string]$task.State; last_result = $null }
        try {
            $info = $task | Get-ScheduledTaskInfo -ErrorAction Stop
            $entry.last_result = [int]$info.LastTaskResult
        } catch { $entry.last_result = "UNAVAILABLE" }
        $taskSummary += $entry
    }
} catch {
    $taskSummary += [ordered]@{ name = "TASK_ENUMERATION_UNAVAILABLE"; state = "UNKNOWN"; last_result = $null }
}
$runnerServices = @()
try {
    $runnerServices = @(Get-Service -Name "actions.runner*" -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{ status = [string]$_.Status }
    })
} catch { $runnerServices = @() }

$summary = [ordered]@{
    kind = "MINIPC_SUPPORT_READONLY_BASELINE_V1"
    observed_at_local = (Get-Date).ToString("o")
    total_ram_gb = $ramTotal
    free_ram_gb = $ramFree
    cpu_load_snapshot_pct = $cpuAvg
    os_caption = [string]$os.Caption
    drives = $volumes
    current_watchdog = $health
    crypto_task_count = @($taskSummary).Count
    crypto_tasks = $taskSummary
    existing_github_runner_services = @($runnerServices).Count
    local_repo_present = (Test-Path -LiteralPath (Join-Path $TradingRoot "Repos\kraken-eur-scanner") -PathType Container)
    read_only = $true
    changes_made = $false
}
$summary | ConvertTo-Json -Depth 6
