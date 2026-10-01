param(
    [string]$ArchivePath = "",
    [switch]$Execute,
    [string]$Confirm = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "DELETE_VERIFIED_OHLCVT_PARTS"
$ExpectedArchiveSha256 = "fc81b54cba6e12af3e9422dde9416179e6ef76af4831d48d839fbdb43018eaa4"

if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
    if (-not $env:USERPROFILE) { throw "USERPROFILE not available." }
    $ArchivePath = Join-Path $env:USERPROFILE "Trading\Historical\raw\kraken\ohlcvt\archives\Kraken_OHLCVT_Full_2026Q2.zip"
}

if (-not (Test-Path $ArchivePath)) {
    throw "Verified archive not found: $ArchivePath"
}

$actual = (Get-FileHash -Algorithm SHA256 -Path $ArchivePath).Hash.ToLowerInvariant()
if ($actual -ne $ExpectedArchiveSha256) {
    throw "Archive checksum mismatch; refusing part cleanup."
}

$dir = Split-Path -Parent $ArchivePath
$parts = @(Get-ChildItem -LiteralPath $dir -File -Filter "Kraken_OHLCVT_Full_2026Q2.zip.part??" | Sort-Object Name)
$bytes = [int64]0
foreach ($p in $parts) {
    $bytes += [int64]$p.Length
}

$result = [ordered]@{
    kind = "KRAKEN_OHLCVT_PART_CLEANUP_V1"
    status = if ($Execute) { "READY_TO_DELETE" } else { "PLAN_ONLY" }
    archive_path = $ArchivePath
    archive_sha256 = $actual
    parts_found = $parts.Count
    reclaimable_bytes = [int64]$bytes
    reclaimable_gb = [math]::Round($bytes / 1GB, 2)
    execute = [bool]$Execute
    deleted = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
}

if (-not $Execute) {
    $result | ConvertTo-Json -Depth 5
    exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
    throw "Deletion blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($p in $parts) {
    Remove-Item -LiteralPath $p.FullName -Force
}

$result.status = "PASS"
$result.deleted = $true
$result.parts_remaining = @(Get-ChildItem -LiteralPath $dir -File -Filter "Kraken_OHLCVT_Full_2026Q2.zip.part??").Count
$result | ConvertTo-Json -Depth 5
