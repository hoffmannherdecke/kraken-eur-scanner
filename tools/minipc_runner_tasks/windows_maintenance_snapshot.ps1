# MINIPC_REVIEWED_TASK_V1
# Windows maintenance evidence, fixed local sources only; no updates or writes.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'WIN_MAINT_BLOCK: restricted reviewed runner required'
}
function UtcOrNull([object]$value) {
    try {
        if ($null -eq $value -or ([datetime]$value).Year -lt 2000) { return $null }
        return ([datetime]$value).ToUniversalTime().ToString('o')
    } catch { return $null }
}

$task = [ordered]@{ readback='UNAVAILABLE'; state=$null; enabled=$null;
    last_run_utc=$null; next_run_utc=$null; last_result=$null }
try {
    $t = Get-ScheduledTask -TaskName 'CryptoSupport - Bounded Runner Window' -ErrorAction Stop
    $task.readback = 'READ_OK'
    $task.state = [string]$t.State
    $task.enabled = [bool]$t.Settings.Enabled
    try {
        $i = Get-ScheduledTaskInfo -TaskName 'CryptoSupport - Bounded Runner Window' -ErrorAction Stop
        $task.last_run_utc = UtcOrNull $i.LastRunTime
        $task.next_run_utc = UtcOrNull $i.NextRunTime
        $task.last_result = [int64]$i.LastTaskResult
    } catch { $task.readback = 'PARTIAL_INFO_UNAVAILABLE' }
} catch [System.UnauthorizedAccessException] {
    $task.readback = 'ACCESS_DENIED'
} catch { $task.readback = 'UNAVAILABLE' }

# Exact service name is shared with existing bounded_window.ps1.
$service = [ordered]@{ readback='UNAVAILABLE'; state=$null; start_mode=$null;
    restricted_account_matches=$null }
try {
    $name = 'actions.runner.hoffmannherdecke-kraken-readonly-bridge.MINI-PC-CryptoSupport'
    $svc = Get-CimInstance -ClassName Win32_Service -Filter "Name='$name'" -ErrorAction Stop
    if ($null -eq $svc) { $service.readback = 'NOT_FOUND' } else {
        $service.readback = 'READ_OK'
        $service.state = [string]$svc.State
        $service.start_mode = [string]$svc.StartMode
        $service.restricted_account_matches = ([string]$svc.StartName -ceq '.\CryptoSupportSvc')
    }
} catch [System.UnauthorizedAccessException] {
    $service.readback = 'ACCESS_DENIED'
} catch { $service.readback = 'UNAVAILABLE' }

$hostReadback = [ordered]@{ readback='UNAVAILABLE'; last_boot_utc=$null;
    windows_version=$null; physical_ram_gib=$null;
    cpu_model=$null; logical_processors=$null }
try {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $cpu = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop | Select-Object -First 1)
    if ($null -ne $os -and $cpu.Count -eq 1) {
        $hostReadback.readback = 'READ_OK'
        $hostReadback.last_boot_utc = UtcOrNull $os.LastBootUpTime
        $hostReadback.windows_version = [string]$os.Version
        $hostReadback.physical_ram_gib = [math]::Round([double]$os.TotalVisibleMemorySize / 1048576,2)
        $hostReadback.cpu_model = ([string]$cpu[0].Name).Trim()
        $hostReadback.logical_processors = [int]$cpu[0].NumberOfLogicalProcessors
    }
} catch [System.UnauthorizedAccessException] {
    $hostReadback.readback = 'ACCESS_DENIED'
} catch { $hostReadback.readback = 'UNAVAILABLE' }

# Marker presence alone is not a complete reboot-decision authority.
$markers = @()
foreach ($entry in @(
    [pscustomobject]@{ name='component_servicing'; key='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending' },
    [pscustomobject]@{ name='windows_update'; key='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired' }
)) {
    $value = 'UNAVAILABLE'
    try {
        [void](Get-Item -LiteralPath $entry.key -ErrorAction Stop)
        $value = 'PRESENT'
    } catch [System.Management.Automation.ItemNotFoundException] {
        $value = 'ABSENT'
    } catch [System.UnauthorizedAccessException] {
        $value = 'ACCESS_DENIED'
    } catch { $value = 'UNAVAILABLE' }
    $markers += [pscustomobject][ordered]@{ marker=$entry.name; readback=$value }
}

$pause = [ordered]@{ readback='UNAVAILABLE'; expiry_utc=$null }
try {
    $settings = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Name 'PauseUpdatesExpiryTime' -ErrorAction Stop
    $pause.expiry_utc = UtcOrNull $settings.PauseUpdatesExpiryTime
    if ($null -eq $pause.expiry_utc) { $pause.readback = 'VALUE_UNPARSEABLE' }
    else { $pause.readback = 'READ_OK' }
} catch [System.UnauthorizedAccessException] {
    $pause.readback = 'ACCESS_DENIED'
} catch {
    # Missing property is UNKNOWN, not proof that updates are not paused.
    $pause.readback = 'UNAVAILABLE'
}

[pscustomobject][ordered]@{
    kind='MINIPC_REVIEWED_TASK_ACK_V1'
    status='SUCCESS'
    task='windows_maintenance_snapshot'
    mutation_scope='RESTRICTED'
    checked_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
    bounded_runner_task=$task
    bounded_runner_service=$service
    windows_host=$hostReadback
    reboot_marker_readbacks=@($markers)
    update_pause_registry=$pause
    scheduled_window_safe_pause_proven=$false
    windows_update_ready_to_install_proven=$false
    cpu_replacement_physically_accepted=$false
    windows_restart_authorized=$false
    v2r4_or_v3_release_authorized=$false
    local_filesystem_writes=$false
    secrets_used=$false
    active_runtime_release=$false
    trading_orders_permitted=$false
} | ConvertTo-Json -Depth 6 -Compress
