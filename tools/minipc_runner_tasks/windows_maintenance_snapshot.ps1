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

# Fail-closed classification, no raw exception strings, usernames or resource listings.
# The previous generic 'UNAVAILABLE' did not establish an ACL error.
function SchedulerReadErrorClass([System.Management.Automation.ErrorRecord]$failure) {
    $e = $failure.Exception
    if ($e -is [System.UnauthorizedAccessException] -or
        [string]$failure.CategoryInfo.Category -eq 'PermissionDenied' -or
        (([int64]$e.HResult -band 65535) -eq 5)) { return 'ACCESS_DENIED' }
    if ($e -is [System.Management.Automation.CommandNotFoundException]) {
        return 'CMDLET_NOT_AVAILABLE'
    }
    if (([int64]$e.HResult -band 65535) -in @(2,3)) { return 'NOT_FOUND' }
    return 'OTHER_ERROR'
}

# Method 1: original, exact named Windows ScheduledTasks cmdlets.
$task = [ordered]@{ readback='UNAVAILABLE'; method='NONE';
    cmdlet_probe='NOT_ATTEMPTED'; com_probe='NOT_ATTEMPTED';
    state=$null; enabled=$null; last_run_utc=$null;
    next_run_utc=$null; last_result=$null }
try {
    $t = Get-ScheduledTask -TaskName 'CryptoSupport - Bounded Runner Window' -ErrorAction Stop
    $task.cmdlet_probe = 'READ_OK'
    $task.readback = 'PARTIAL_INFO_UNAVAILABLE'
    $task.method = 'CMDLET'
    $task.state = [string]$t.State
    $task.enabled = [bool]$t.Settings.Enabled
    try {
        $i = Get-ScheduledTaskInfo -TaskName 'CryptoSupport - Bounded Runner Window' -ErrorAction Stop
        $task.last_run_utc = UtcOrNull $i.LastRunTime
        $task.next_run_utc = UtcOrNull $i.NextRunTime
        $task.last_result = [int64]$i.LastTaskResult
        $task.readback = 'READ_OK'
    } catch {
        $task.cmdlet_probe = SchedulerReadErrorClass $_
    }
} catch {
    $task.cmdlet_probe = SchedulerReadErrorClass $_
}

# Method 2: Windows' native Schedule.Service COM API for the *same* one
# root-folder task. This uses the existing CryptoSupportSvc token only.
# It cannot change task permissions or start, stop, register or edit tasks.
if ($task.readback -ne 'READ_OK') {
    try {
        $scheduler = New-Object -ComObject 'Schedule.Service' -ErrorAction Stop
        $scheduler.Connect()
        $rootFolder = $scheduler.GetFolder('\')
        $comTask = $rootFolder.GetTask('CryptoSupport - Bounded Runner Window')
        if ($null -eq $comTask) { throw 'SCHEDULER_TASK_NOT_AVAILABLE' }
        $comState = 'UNKNOWN'
        switch ([int]$comTask.State) {
            1 { $comState = 'Disabled' }
            2 { $comState = 'Queued' }
            3 { $comState = 'Ready' }
            4 { $comState = 'Running' }
        }
        $task.state = $comState
        $task.enabled = [bool]$comTask.Enabled
        $task.last_run_utc = UtcOrNull $comTask.LastRunTime
        $task.next_run_utc = UtcOrNull $comTask.NextRunTime
        $task.last_result = [int64]$comTask.LastTaskResult
        $task.com_probe = 'READ_OK'
        $task.method = 'SCHEDULE_SERVICE_COM'
        $task.readback = 'READ_OK'
    } catch {
        $task.com_probe = SchedulerReadErrorClass $_
        if ($task.readback -ne 'PARTIAL_INFO_UNAVAILABLE') {
            if ($task.com_probe -eq 'ACCESS_DENIED' -and
                $task.cmdlet_probe -eq 'ACCESS_DENIED') {
                $task.readback = 'ACCESS_DENIED'
            } else {
                $task.readback = 'UNAVAILABLE'
            }
        }
    }
}


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

# The pinned private workflow captures the SUCCESS stream and emits only a
# wrapper ACK. A *separate*, bounded public-safe information line makes the
# essential result readable from the original GitHub job log without touching
# the workflow SHA, guard PIN, Windows ACLs, or any file.
$safeCpu = 'OTHER_OR_NOT_READABLE'
if ($hostReadback.cpu_model -match '(?i)\b(i5-8500T|i7-8700T)\b') {
    $safeCpu = $Matches[1].ToUpperInvariant()
}
$safeTaskState = 'UNKNOWN'
if ($task.state -in @('Ready','Running','Disabled','Queued')) {
    $safeTaskState = $task.state
}
$safeServiceState = 'UNKNOWN'
if ($service.state -in @('Stopped','Running','Start Pending','Stop Pending','Paused')) {
    $safeServiceState = $service.state
}
$safeServiceMode = 'UNKNOWN'
if ($service.start_mode -in @('Auto','Manual','Disabled')) {
    $safeServiceMode = $service.start_mode
}
$safeSummary = [pscustomobject][ordered]@{
    kind = 'MINIPC_MAINTENANCE_SAFE_SUMMARY_V1'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    task_readback = $task.readback
    task_read_method = $task.method
    task_cmdlet_probe = $task.cmdlet_probe
    task_com_probe = $task.com_probe
    task_state = $safeTaskState
    task_enabled = $task.enabled
    task_last_run_utc = $task.last_run_utc
    task_last_result = $task.last_result
    service_readback = $service.readback
    service_state = $safeServiceState
    service_start_mode = $safeServiceMode
    service_account_matches = $service.restricted_account_matches
    host_readback = $hostReadback.readback
    host_last_boot_utc = $hostReadback.last_boot_utc
    cpu_model_known = $safeCpu
    physical_ram_gib = $hostReadback.physical_ram_gib
    reboot_markers = @($markers)
    update_pause_readback = $pause.readback
    pause_expiry_utc = $pause.expiry_utc
    post_window_safe_pause_proven = $false
    restart_or_update_authorized = $false
}
# Write-Host writes only the audited summary to the GitHub job log's host
# stream. It does not alter the workflow's one-JSON success-stream contract.
$safeLine = $safeSummary | ConvertTo-Json -Compress -Depth 4
Write-Host ('MINIPC_MAINTENANCE_SAFE_SUMMARY_V1 ' + $safeLine)

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
