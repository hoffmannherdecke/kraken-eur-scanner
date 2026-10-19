# MINIPC_REVIEWED_TASK_V1
# One-shot existing-capability batch: no new Windows privileges, operations or scheduler.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'OPS_BATCH_BLOCK: original nonadmin GitHub runner required'
}

# Exactly these three ALREADY reviewed tasks. Never accept caller paths,
# arbitrary commands, external arguments, child scripts or runtime writes.
$capabilities = @(
    'host_safety_probe',
    'windows_maintenance_snapshot',
    'log_status_summary'
)
$readbacks = [ordered]@{}
$results = [ordered]@{
    free_ram_gib = $null
    c_free_gib = $null
    scheduler_readback = 'UNAVAILABLE'
    runner_service_state = 'UNKNOWN'
    reboot_indicator = 'UNKNOWN'
    log_sources_readback = 'UNKNOWN'
    log_files_read = $null
}
foreach ($name in $capabilities) {
    $readbacks[$name] = 'UNAVAILABLE'
    $script = Join-Path $PSScriptRoot ($name + '.ps1')
    try {
        $item = Get-Item -LiteralPath $script -ErrorAction Stop
        if ($item.PSIsContainer -or
            [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            continue
        }
        $rawResult = @(& $script)
        if ($rawResult.Count -ne 1 -or
            ([string]$rawResult[0]).Length -gt 16384) { continue }
        $ack = [string]$rawResult[0] | ConvertFrom-Json -ErrorAction Stop
        if ($ack.kind -cne 'MINIPC_REVIEWED_TASK_ACK_V1' -or
            $ack.status -cne 'SUCCESS' -or
            $ack.task -cne $name -or
            $ack.mutation_scope -cne 'RESTRICTED') { continue }

        $readbacks[$name] = 'READ_OK'
        if ($name -ceq 'host_safety_probe') {
            $results.free_ram_gib = [math]::Round([double]$ack.free_ram_gib, 2)
            $results.c_free_gib = [math]::Round([double]$ack.c_free_gib, 2)
        } elseif ($name -ceq 'windows_maintenance_snapshot') {
            if ($ack.bounded_runner_task.readback -in @('READ_OK','UNAVAILABLE','ACCESS_DENIED','PARTIAL_INFO_UNAVAILABLE')) {
                $results.scheduler_readback = [string]$ack.bounded_runner_task.readback
            }
            if ($ack.bounded_runner_service.state -in @('Running','Stopped')) {
                $results.runner_service_state = [string]$ack.bounded_runner_service.state
            }
            if (@($ack.reboot_marker_readbacks | Where-Object { $_.readback -eq 'PRESENT' }).Count -gt 0) {
                $results.reboot_indicator = 'MARKER_PRESENT'
            } elseif (@($ack.reboot_marker_readbacks | Where-Object { $_.readback -eq 'ABSENT' }).Count -eq 2) {
                $results.reboot_indicator = 'NO_TWO_MARKERS'
            }
        } elseif ($name -ceq 'log_status_summary') {
            $results.log_sources_readback = if (@($ack.source_readbacks | Where-Object {
                $_.status -in @('ACCESS_DENIED','ROOT_UNAVAILABLE','UNSAFE_ROOT','PARTIAL_ACCESS_DENIED','PARTIAL_READ_ERROR')
            }).Count -gt 0) { 'PARTIAL_OR_UNAVAILABLE' } else { 'READ_OK_OR_EMPTY' }
            $results.log_files_read = [math]::Min(10, [math]::Max(0, [int]$ack.total_files_read))
        }
    } catch {
        # Deliberately never expose error text, identity, paths or any child output.
        $readbacks[$name] = 'UNAVAILABLE'
    }
}
$overall = if (@($readbacks.Values | Where-Object { $_ -ne 'READ_OK' }).Count -eq 0) {
    'COMPLETE'
} else {
    'PARTIAL'
}
# Only whitelisted derived fields (no raw logs, file paths, process args).
$safe = [pscustomobject][ordered]@{
    kind = 'MINIPC_OPERATIONS_BATCH_SAFE_SUMMARY_V1'
    overall_readback = $overall
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    host_probe = $readbacks['host_safety_probe']
    windows_probe = $readbacks['windows_maintenance_snapshot']
    log_probe = $readbacks['log_status_summary']
    free_ram_gib = $results.free_ram_gib
    c_free_gib = $results.c_free_gib
    scheduler_readback = $results.scheduler_readback
    runner_service_state_during_run = $results.runner_service_state
    reboot_indicator = $results.reboot_indicator
    log_sources_readback = $results.log_sources_readback
    log_files_read = $results.log_files_read
    actual_cpu_or_update_release = $false
    trading_orders_authorized = $false
}
Write-Host ('MINIPC_OPERATIONS_BATCH_SAFE_SUMMARY_V1 ' + ($safe | ConvertTo-Json -Depth 4 -Compress))

[pscustomobject][ordered]@{
    kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
    status = 'SUCCESS'
    task = 'operations_readonly_bundle'
    mutation_scope = 'RESTRICTED'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    overall_readback = $overall
    existing_capability_readbacks = $readbacks
    local_filesystem_writes = $false
    service_or_task_mutations = $false
    new_permissions = $false
    active_runtime_release = $false
    trading_orders_permitted = $false
    secrets_used = $false
} | ConvertTo-Json -Depth 4 -Compress
