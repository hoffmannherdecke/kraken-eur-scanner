# MINIPC_REVIEWED_TASK_V1
# Restricted support-runner E2E proof; does not touch Trading, tasks or credentials.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if ($identity.Name -notmatch '(?i)\\CryptoSupportSvc$') {
    throw 'MINIPC_TASK_BLOCK: wrong account'
}
if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'MINIPC_TASK_BLOCK: elevated Windows identity'
}
if ($env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'MINIPC_TASK_BLOCK: wrong runner'
}
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
$systemDisk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" -ErrorAction Stop
if ($null -eq $os -or $null -eq $systemDisk) {
    throw 'MINIPC_TASK_BLOCK: basic read-only counters missing'
}
$ram = [math]::Round(([double]$os.FreePhysicalMemory * 1024) / 1GB, 2)
$disk = [math]::Round([double]$systemDisk.FreeSpace / 1GB, 2)
if ($ram -lt 0 -or $disk -lt 0) {
    throw 'MINIPC_TASK_BLOCK: counters invalid'
}
[pscustomobject][ordered]@{
    kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
    status = 'SUCCESS'
    task = 'host_safety_probe'
    mutation_scope = 'RESTRICTED'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    restricted_runner_identity = $true
    admin_role = $false
    free_ram_gib = $ram
    c_free_gib = $disk
    project_action = 'NONE'
    local_filesystem_writes = $false
    secrets_used = $false
} | ConvertTo-Json -Compress
