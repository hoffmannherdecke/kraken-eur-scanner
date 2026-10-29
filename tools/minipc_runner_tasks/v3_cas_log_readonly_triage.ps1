# MINIPC_REVIEWED_TASK_V1
# Read-only, bounded CAS/UNKNOWN log TRIAGE, never historical completeness proof.
$ErrorActionPreference = 'Stop'
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p = New-Object Security.Principal.WindowsPrincipal($id)
if ($id.Name -notmatch '(?i)\\CryptoSupportSvc$' -or
    $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or
    $env:RUNNER_NAME -cne 'MINI-PC-CryptoSupport') {
    throw 'V3_CAS_LOG_TRIAGE_BLOCK: restricted originalhost runner required'
}
$roots = @(
    [pscustomobject]@{ key='trading_logs'; path='C:\Users\ADMIN\Trading\Logs' },
    [pscustomobject]@{ key='support_logs'; path='C:\CryptoSupport\Logs' }
)
$since = [DateTimeOffset]::UtcNow.AddHours(-24)
$limitFiles = 5
$limitLines = 4000
$limitBytes = 16MB
$patterns = [ordered]@{
    cas_rpc = '(?i)rotate_v2r4_to_v3_experimental_paper'
    cas_audit = '(?i)v3_cas_audit|V3CAS-AUDIT-'
    cas_unknown = '(?i)cas.{0,50}(unknown|timeout|retry|dispatch|invoke)|(?:unknown|timeout).{0,50}cas'
}
$counts = [ordered]@{cas_rpc=0;cas_audit=0;cas_unknown=0}
$sources = @()
foreach ($root in $roots) {
    $status = 'UNAVAILABLE'
    $read = 0
    $skipped = 0
    try {
        $dir = Get-Item -LiteralPath $root.path -Force -ErrorAction Stop
        if (-not $dir.PSIsContainer -or
            [bool]($dir.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            $status = 'UNSAFE_ROOT'
        } else {
            $files = @(Get-ChildItem -LiteralPath $root.path -File -Filter '*.log' -Force -ErrorAction Stop |
                Where-Object { -not [bool]($_.Attributes -band [IO.FileAttributes]::ReparsePoint) } |
                Sort-Object LastWriteTimeUtc -Descending)
            $status = 'BOUNDED_READ'
            if ($files.Count -gt $limitFiles) { $status = 'PARTIAL_FILE_LIMIT' }
            foreach ($file in @($files | Select-Object -First $limitFiles)) {
                if ($file.Length -gt $limitBytes) { $skipped++; $status = 'PARTIAL_SIZE_LIMIT'; continue }
                try {
                    $lines = @(Get-Content -LiteralPath $file.FullName -Tail $limitLines -ErrorAction Stop)
                    $read++
                    if ($lines.Count -ge $limitLines -and $status -eq 'BOUNDED_READ') {
                        $status = 'PARTIAL_TAIL_LIMIT'
                    }
                    foreach ($line in $lines) {
                        if ($line -cnotmatch '^\s*(?<ts>\d{4}-\d\d-\d\d[T ][0-9:.+-]+(?:Z)?)\b') { continue }
                        $ts = [DateTimeOffset]::MinValue
                        if (-not [DateTimeOffset]::TryParse([string]$Matches['ts'],[ref]$ts)) { continue }
                        if ($ts.ToUniversalTime() -lt $since -or
                            $ts.ToUniversalTime() -gt [DateTimeOffset]::UtcNow.AddMinutes(1)) { continue }
                        foreach ($key in @($patterns.Keys)) {
                            if ($line -match $patterns[$key]) { $counts[$key]++ }
                        }
                    }
                } catch {
                    $status = 'PARTIAL_READ_ERROR'
                }
            }
        }
    } catch [System.UnauthorizedAccessException] {
        $status = 'ACCESS_DENIED'
    } catch [System.Management.Automation.ItemNotFoundException] {
        $status = 'ROOT_MISSING'
    } catch {
        $status = 'ROOT_UNAVAILABLE'
    }
    $sources += [pscustomobject][ordered]@{
        source_key=$root.key; readback=$status; files_read=$read; skipped_files=$skipped
    }
}
# Even zero matches in both roots is never a complete historical audit.
[pscustomobject][ordered]@{
    kind='MINIPC_REVIEWED_TASK_ACK_V1'
    status='SUCCESS'
    task='v3_cas_log_readonly_triage'
    mutation_scope='RESTRICTED'
    checked_at_utc=[DateTimeOffset]::UtcNow.ToString('o')
    time_window_hours=24
    sources=$sources
    candidate_line_counts=$counts
    match_semantics='UNTRUSTED_TEXT_CANDIDATES_NOT_AUTHENTICATED_CAS_DISPATCH'
    historical_coverage='INCOMPLETE'
    independent_cloud_provenance_verified=$false
    historical_cas_never_invoked_proven=$false
    originalhost_restore_authorized=$false
    cas_dispatch_authorized=$false
    v3_paper_release_authorized=$false
    disposition='HOLD_REQUIRES_INDEPENDENT_HISTORICAL_CUSTODY'
    raw_log_lines_exposed=$false
    filenames_exposed=$false
    local_filesystem_writes=$false
    service_or_task_mutations=$false
    new_permissions=$false
    secrets_used=$false
    trading_orders_permitted=$false
    active_runtime_release=$false
} | ConvertTo-Json -Depth 6 -Compress
