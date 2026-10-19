# MINIPC_REVIEWED_TASK_V1
# General read-only status-only diagnostics. No caller-supplied code/path,
# no log lines, filenames, secrets, or raw file contents in GitHub output.
$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if ($identity.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'LOG_SUMMARY_BLOCK: restricted existing Mini-PC runner required'
}

# These are narrow, known diagnostic roots, NOT an unrestricted filesystem scan.
# Missing/inaccessible roots are explicitly reported; NEVER change Windows ACLs.
$roots = @(
    [pscustomobject]@{ id='trading_logs'; path='C:\Users\ADMIN\Trading\Logs' },
    [pscustomobject]@{ id='support_logs'; path='C:\CryptoSupport\Logs' }
)
$since = [DateTimeOffset]::UtcNow.AddHours(-24)
$timestampPattern = '^\s*(?<ts>\d{4}-\d\d-\d\d[T ][0-9:.+-]+(?:Z)?)\b'
$statusPattern = '(?i)(?:^|\s)status=(?<status>[A-Z][A-Z0-9_-]{0,24})(?=\s|$)'
$statuses = @{}
$results = New-Object System.Collections.Generic.List[object]
$totalMatched = 0
$totalFilesRead = 0
$maxFilesPerRoot = 5
$maxTailLines = 4000
$maxFileBytes = 16MB

foreach ($root in $roots) {
    $fileCount = 0
    $rootStatus = 'NO_READABLE_LOGS'
    try {
        $rootItem = Get-Item -LiteralPath $root.path -Force -ErrorAction Stop
        if (-not $rootItem.PSIsContainer -or
            [bool]($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $rootStatus = 'UNSAFE_ROOT'
        } else {
            $rootStatus = 'READABLE_NO_MATCH'
            $files = @(Get-ChildItem -LiteralPath $root.path -File -Filter '*.log' -ErrorAction Stop |
                Where-Object { -not [bool]($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
                Sort-Object LastWriteTimeUtc -Descending |
                Select-Object -First $maxFilesPerRoot)
            if ($files.Count -eq 0) { $rootStatus = 'NO_READABLE_LOGS' }
            foreach ($file in $files) {
                if ($file.Length -gt $maxFileBytes) {
                    # Skip unexpectedly big sources rather than reading arbitrary amounts.
                    continue
                }
                try {
                    # Read only the last bounded portion. NEVER print raw lines.
                    $lines = @(Get-Content -LiteralPath $file.FullName -Tail $maxTailLines -ErrorAction Stop)
                } catch [System.UnauthorizedAccessException] {
                    $rootStatus = 'PARTIAL_ACCESS_DENIED'
                    continue
                } catch {
                    $rootStatus = 'PARTIAL_READ_ERROR'
                    continue
                }
                $fileCount++
                $totalFilesRead++
                foreach ($line in $lines) {
                    if ($line -cnotmatch $timestampPattern) { continue }
                    $ts = [DateTimeOffset]::MinValue
                    if (-not [DateTimeOffset]::TryParse([string]$Matches['ts'], [ref]$ts)) { continue }
                    if ($ts.ToUniversalTime() -lt $since -or
                        $ts.ToUniversalTime() -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) { continue }
                    if ($line -notmatch $statusPattern) { continue }
                    $status = $Matches['status'].ToUpperInvariant()
                    $key = $root.id + '/' + $status
                    if (-not $statuses.ContainsKey($key)) { $statuses[$key] = 0 }
                    $statuses[$key] += 1
                    $totalMatched += 1
                    if ($rootStatus -eq 'READABLE_NO_MATCH' -or
                        $rootStatus -eq 'NO_READABLE_LOGS') { $rootStatus = 'MATCHED' }
                }
            }
        }
    } catch [System.UnauthorizedAccessException] {
        $rootStatus = 'ACCESS_DENIED'
    } catch [System.Management.Automation.ItemNotFoundException] {
        $rootStatus = 'ROOT_MISSING'
    } catch {
        $rootStatus = 'ROOT_UNAVAILABLE'
    }
    $results.Add([pscustomobject][ordered]@{
        source_id = $root.id
        status = $rootStatus
        files_read = $fileCount
    })
}

# Limit event-type output and never include source filenames, raw lines or paths.
$summary = @($statuses.Keys | Sort-Object | Select-Object -First 40 |
    ForEach-Object {
        [pscustomobject][ordered]@{
            source_and_status = [string]$_
            count = [int]$statuses[$_]
        }
    })

[pscustomobject][ordered]@{
    kind = 'MINIPC_REVIEWED_TASK_ACK_V1'
    status = 'SUCCESS'
    task = 'log_status_summary'
    mutation_scope = 'RESTRICTED'
    checked_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    time_window_hours = 24
    max_tail_lines_per_file = $maxTailLines
    total_files_read = $totalFilesRead
    matched_status_events = $totalMatched
    evidence_present = ($totalMatched -gt 0)
    source_readbacks = @($results.ToArray())
    status_counts = $summary
    raw_lines_exposed = $false
    filenames_exposed = $false
    local_filesystem_writes = $false
    secrets_used = $false
    trading_orders_permitted = $false
    active_runtime_release = $false
} | ConvertTo-Json -Depth 6 -Compress
