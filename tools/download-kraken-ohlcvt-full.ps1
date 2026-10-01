param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = "",
    [double]$MinimumFreeGB = 80,
    [switch]$DeletePartsAfterVerified
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "DOWNLOAD_OHLCVT_FULL_2026Q2"
$ExpectedArchiveSha256 = "fc81b54cba6e12af3e9422dde9416179e6ef76af4831d48d839fbdb43018eaa4"
$PartCount = 5
$BaseUrl = "https://assets.kraken.com/marketing/institutions"
$ArchiveName = "Kraken_OHLCVT_Full_2026Q2.zip"
$ChecksumName = "OHLCVT_Full_PARTS_SHA256SUMS.txt"

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
    $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if ([string]::IsNullOrWhiteSpace($homeRoot)) {
        throw "Unable to resolve user home directory."
    }
    $TradingRoot = Join-Path $homeRoot "Trading"
}

$HistoricalRoot = Join-Path $TradingRoot "Historical"
$ArchiveDir = Join-Path $HistoricalRoot "raw\kraken\ohlcvt\archives"
$CatalogDir = Join-Path $HistoricalRoot "catalog"
$LogsDir = Join-Path $TradingRoot "Logs"

$driveRoot = [System.IO.Path]::GetPathRoot($HistoricalRoot)
if ($driveRoot -and $driveRoot.ToUpperInvariant().StartsWith("D:")) {
    throw "Drive D remains blocked for historical project storage."
}

$probePath = $HistoricalRoot
while (-not (Test-Path $probePath)) {
    $parent = Split-Path -Parent $probePath
    if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $probePath) {
        throw "Unable to resolve an existing filesystem ancestor for $HistoricalRoot"
    }
    $probePath = $parent
}

$drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($probePath).Substring(0,1))
$freeGB = [math]::Round($drive.Free / 1GB, 2)
$totalGB = [math]::Round(($drive.Free + $drive.Used) / 1GB, 2)

$partNames = 0..($PartCount-1) | ForEach-Object {
    "$ArchiveName.part$('{0:D2}' -f $_)"
}

$plan = [ordered]@{
    kind = "KRAKEN_OHLCVT_FULL_DOWNLOAD_PLAN_V1"
    status = "PLAN_ONLY"
    execute = [bool]$Execute
    source = "Kraken official public historical OHLCVT archive"
    archive_name = $ArchiveName
    archive_expected_sha256 = $ExpectedArchiveSha256
    part_count = $PartCount
    approximate_compressed_gb = 10
    free_gb_before = $freeGB
    total_gb = $totalGB
    minimum_free_gb_required = $MinimumFreeGB
    archive_dir = $ArchiveDir
    downloads_performed = $false
    extraction_performed = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
}

if (-not $Execute) {
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
    throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}
if ($freeGB -lt $MinimumFreeGB) {
    throw "Execution blocked: only $freeGB GB free; requires at least $MinimumFreeGB GB."
}

New-Item -ItemType Directory -Force -Path $ArchiveDir,$CatalogDir,$LogsDir | Out-Null

$curl = Get-Command curl.exe -ErrorAction SilentlyContinue
if (-not $curl) {
    throw "curl.exe not found."
}

$checksumPath = Join-Path $CatalogDir $ChecksumName
& $curl.Source -L --fail --retry 5 --retry-delay 5 -o $checksumPath "$BaseUrl/$ChecksumName"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to download official part checksum file."
}

$expectedParts = @{}
Get-Content $checksumPath | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^([0-9a-fA-F]{64})\s+\*?(.+)$') {
        $expectedParts[$matches[2].Trim()] = $matches[1].ToLowerInvariant()
    }
}

foreach ($partName in $partNames) {
    if (-not $expectedParts.ContainsKey($partName)) {
        throw "Official checksum file does not contain $partName"
    }
}

$downloaded = @()
foreach ($partName in $partNames) {
    $partUrl = "$BaseUrl/$partName"
    $partPath = Join-Path $ArchiveDir $partName

    Write-Output "OHLCVT_DOWNLOAD part=$partName path=$partPath"
    & $curl.Source -L --fail --retry 8 --retry-delay 5 -C - -o $partPath $partUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed for $partName"
    }

    $actual = (Get-FileHash -Algorithm SHA256 -Path $partPath).Hash.ToLowerInvariant()
    $expected = $expectedParts[$partName]
    if ($actual -ne $expected) {
        throw "Checksum mismatch for $partName expected=$expected actual=$actual"
    }
    $downloaded += [ordered]@{
        part = $partName
        bytes = (Get-Item $partPath).Length
        sha256 = $actual
        status = "VERIFIED"
    }
}

$archivePath = Join-Path $ArchiveDir $ArchiveName
$tmpArchive = "$archivePath.partial"
if (Test-Path $tmpArchive) {
    Remove-Item -Force $tmpArchive
}

$outStream = [System.IO.File]::Open(
    $tmpArchive,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None
)
try {
    foreach ($partName in $partNames) {
        $partPath = Join-Path $ArchiveDir $partName
        $inStream = [System.IO.File]::OpenRead($partPath)
        try {
            $inStream.CopyTo($outStream)
        }
        finally {
            $inStream.Dispose()
        }
    }
}
finally {
    $outStream.Dispose()
}

$archiveActual = (Get-FileHash -Algorithm SHA256 -Path $tmpArchive).Hash.ToLowerInvariant()
if ($archiveActual -ne $ExpectedArchiveSha256) {
    throw "Reassembled archive checksum mismatch expected=$ExpectedArchiveSha256 actual=$archiveActual"
}

Move-Item -Force $tmpArchive $archivePath

if ($DeletePartsAfterVerified) {
    foreach ($partName in $partNames) {
        Remove-Item -Force (Join-Path $ArchiveDir $partName)
    }
}

$driveAfter = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($archivePath).Substring(0,1))
$freeAfterGB = [math]::Round($driveAfter.Free / 1GB, 2)

$result = [ordered]@{
    kind = "KRAKEN_OHLCVT_FULL_DOWNLOAD_RESULT_V1"
    status = "PASS_ARCHIVE_VERIFIED_NO_EXTRACTION"
    source = "Kraken official public historical OHLCVT archive"
    archive_path = $archivePath
    archive_sha256 = $archiveActual
    parts = $downloaded
    parts_deleted_after_verification = [bool]$DeletePartsAfterVerified
    free_gb_before = $freeGB
    free_gb_after = $freeAfterGB
    extraction_performed = $false
    downloads_performed = $true
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    next_gate = "inspect_archive_manifest_and_selective_eur_15m_extraction"
}

$json = $result | ConvertTo-Json -Depth 8
$report = Join-Path $LogsDir "kraken-ohlcvt-full-download-latest.json"
[System.IO.File]::WriteAllText($report, $json + [Environment]::NewLine)
Write-Output $json
Write-Output "OHLCVT_DOWNLOAD_REPORT $report"
