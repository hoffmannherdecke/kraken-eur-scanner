# MINIPC_REVIEWED_TASK_V1
# One fixed NTFS work area: bounded write/read/delete probe and small local report.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'WORKSPACE_WRITE_BLOCK: restricted original runner required'
}
$parent = 'C:\CryptoSupport'
$root = 'C:\CryptoSupport\Workspace'
foreach ($folder in @($parent, $root)) {
    if (-not [IO.Directory]::Exists($folder)) {
        throw 'WORKSPACE_WRITE_BLOCK: required local folder missing'
    }
    $dir = New-Object IO.DirectoryInfo($folder)
    if (($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'WORKSPACE_WRITE_BLOCK: unsafe folder reparse point'
    }
}
$seen = 0
foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($root)) {
    $seen++
    if ($seen -ge 20) { throw 'WORKSPACE_WRITE_BLOCK: output count limit reached' }
    $e = [IO.FileInfo]::new($entry)
    if (($e.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'WORKSPACE_WRITE_BLOCK: existing reparse entry'
    }
}
$serial = [guid]::NewGuid().ToString('N').Substring(0,12)
$testPath = Join-Path $root ("probe-" + $serial + ".tmp")
$reportPath = Join-Path $root ("report-" +
    [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmss') + "-" +
    $serial + ".json")
$enc = [Text.UTF8Encoding]::new($false)
$probeDone = $false
try {
    # Both unique paths are CREATED, never overwritten; no input/output path arg.
    $probeBytes = $enc.GetBytes('minipc-workspace-write-read-delete-v1')
    $stream = [IO.FileStream]::new($testPath,
        [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None)
    try {
        $stream.Write($probeBytes, 0, $probeBytes.Length)
        $stream.Flush()
        $stream.Position = 0
        $copy = [byte[]]::new($probeBytes.Length)
        $read = $stream.Read($copy, 0, $copy.Length)
        if ($read -ne $copy.Length -or
            $enc.GetString($copy) -cne 'minipc-workspace-write-read-delete-v1') {
            throw 'WORKSPACE_WRITE_BLOCK: probe readback mismatch'
        }
    } finally { $stream.Dispose() }
    $probeDone = $true
} finally {
    if ([IO.File]::Exists($testPath)) { [IO.File]::Delete($testPath) }
}
if (-not $probeDone -or [IO.File]::Exists($testPath)) {
    throw 'WORKSPACE_WRITE_BLOCK: probe cleanup not proven'
}
$report = [ordered]@{
    kind = 'MINIPC_WORKSPACE_REPORT_V1'
    status = 'PASS'
    created_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    reviewed_task = 'workspace_report'
    source = 'ONE_FIXED_NONADMIN_REVIEWED_GITHUB_TASK'
    probe_write_read_delete = $true
    windows_or_trading_mutation = $false
    credentials_used = $false
}
$content = $report | ConvertTo-Json -Compress -Depth 3
$bytes = $enc.GetBytes($content)
if ($bytes.Length -gt 4096) {
    throw 'WORKSPACE_WRITE_BLOCK: report exceeds 4 KiB limit'
}
$writer = [IO.FileStream]::new($reportPath,
    [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite,
    [IO.FileShare]::None)
try {
    $writer.Write($bytes, 0, $bytes.Length)
    $writer.Flush()
    $writer.Position = 0
    $readBytes = [byte[]]::new($bytes.Length)
    $readCount = $writer.Read($readBytes, 0, $readBytes.Length)
    if ($readCount -ne $bytes.Length -or
        $enc.GetString($readBytes) -cne $content) {
        throw 'WORKSPACE_WRITE_BLOCK: stored report readback mismatch'
    }
} finally { $writer.Dispose() }
# Only safe booleans and counts in GitHub logs. No files or identifiers printed.
Write-Host ('MINIPC_WORKSPACE_SAFE_SUMMARY_V1 ' + (
    [pscustomobject][ordered]@{
        kind = 'MINIPC_WORKSPACE_SAFE_SUMMARY_V1'
        write_read_delete_probe = 'PASS'
        persistent_report_created = $true
        report_size_bytes = $bytes.Length
        directory_entries_before = $seen
        workspace_boundary = 'FIXED_SCOPED_PATH'
        no_windows_or_trading_mutation = $true
    } | ConvertTo-Json -Compress))
[pscustomobject][ordered]@{
    kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
    status = 'SUCCESS'
    task = 'workspace_report'
    mutation_scope = 'RESTRICTED'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    workspace_write_read_delete = $true
    report_created = $true
    report_size_bytes = $bytes.Length
    local_filesystem_writes = $true
    writes_outside_workspace = $false
    no_new_privileged_rights = $true
    service_or_task_mutations = $false
    secrets_used = $false
    active_runtime_release = $false
    trading_orders_permitted = $false
} | ConvertTo-Json -Compress -Depth 3
