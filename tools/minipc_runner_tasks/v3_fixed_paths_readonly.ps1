# MINIPC_REVIEWED_TASK_V1
# Fixed, bounded read-only V3 directory/checkout/launcher discovery.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'V3_PATH_READ_BLOCK: restricted original runner required'
}
$roots = @(
    @{ key='TRADING'; path='C:\Users\ADMIN\Trading' },
    @{ key='STAGING'; path='C:\Users\ADMIN\Trading\Staging' },
    @{ key='V3STAGE'; path='C:\Users\ADMIN\Trading\V3Stage' }
)
function SafeDir([string]$path) {
    try {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if (-not $item.PSIsContainer) { return 'NOT_DIRECTORY' }
        if ([bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return 'UNSAFE_REPARSE' }
        return 'PRESENT'
    } catch [System.Management.Automation.ItemNotFoundException] { return 'MISSING' }
      catch [System.UnauthorizedAccessException] { return 'ACCESS_DENIED' }
      catch { return 'UNAVAILABLE' }
}
function SafeFile([string]$path) {
    try {
        $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if ($item.PSIsContainer -or [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return 'UNSAFE_OR_DIRECTORY' }
        return 'PRESENT'
    } catch [System.Management.Automation.ItemNotFoundException] { return 'MISSING' }
      catch [System.UnauthorizedAccessException] { return 'ACCESS_DENIED' }
      catch { return 'UNAVAILABLE' }
}
$out = @()
foreach ($root in $roots) {
    $state = SafeDir $root.path
    $git = 'NOT_CHECKED'
    $launcher = 'NOT_CHECKED'
    if ($state -eq 'PRESENT') {
        $git = SafeDir (Join-Path $root.path '.git')
        if ($git -eq 'NOT_DIRECTORY') { $git = SafeFile (Join-Path $root.path '.git') }
        $launcher = SafeFile (Join-Path $root.path 'paper_evaluator\v3_paper_minipc_native_launcher_v1.py')
    }
    $out += [pscustomobject][ordered]@{
        root_key=$root.key; root_readback=$state; git_marker=$git; v3_launcher=$launcher
    }
}
# No traversal, file content, arbitrary paths, command invocation, or path disclosure.
Write-Host ('MINIPC_V3_PATHS_SAFE_SUMMARY_V1 ' + ([pscustomobject]@{
    kind='MINIPC_V3_PATHS_SAFE_SUMMARY_V1'; roots=$out
} | ConvertTo-Json -Compress -Depth 5))
[pscustomobject][ordered]@{
    kind='MINIPC_REVIEWED_TASK_ACK_V1'
    status='SUCCESS'
    task='v3_fixed_paths_readonly'
    mutation_scope='RESTRICTED'
    roots=$out
    local_filesystem_writes=$false
    service_or_task_mutations=$false
    new_permissions=$false
    active_runtime_release=$false
    trading_orders_permitted=$false
} | ConvertTo-Json -Compress -Depth 5
