param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "NORMALIZE_KRAKEN_EUR15_2026Q2"
$ExpectedCount = 648

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
    $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if ([string]::IsNullOrWhiteSpace($homeRoot)) {
        throw "Unable to resolve user home directory."
    }
    $TradingRoot = Join-Path $homeRoot "Trading"
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$HistoricalRoot = Join-Path $TradingRoot "Historical"
$SourceDir = Join-Path $HistoricalRoot "raw\kraken\ohlcvt\selected\eur\15m"
$DestinationDir = Join-Path $HistoricalRoot "normalized\kraken\eur\15m"
$CatalogDir = Join-Path $HistoricalRoot "catalog"
$ReportsDir = Join-Path $HistoricalRoot "reports"
$ExtractionCatalog = Join-Path $CatalogDir "kraken-ohlcvt-eur15-extraction.json"
$NormalizationCatalog = Join-Path $CatalogDir "kraken-eur15-normalization.json"
$ReplayReport = Join-Path $ReportsDir "kraken-eur15-real-pair-replay-smoke.json"
$Normalizer = Join-Path $RepoRoot "tools\normalize-kraken-eur15.py"
$Replay = Join-Path $RepoRoot "tools\historical-real-pair-replay-smoke.py"

$plan = [ordered]@{
    kind = "MINIPC_KRAKEN_EUR15_NORMALIZATION_PLAN_V1"
    status = if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" }
    execute = [bool]$Execute
    expected_source_files = $ExpectedCount
    source_dir = $SourceDir
    destination_dir = $DestinationDir
    extraction_catalog = $ExtractionCatalog
    normalization_catalog = $NormalizationCatalog
    replay_report = $ReplayReport
    network_used = $false
    raw_source_modified = $false
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

foreach ($required in @($SourceDir,$ExtractionCatalog,$Normalizer,$Replay)) {
    if (-not (Test-Path $required)) {
        throw "Required input/tool missing: $required"
    }
}

$sourceFiles = @(Get-ChildItem -LiteralPath $SourceDir -File -Filter "*EUR_15.csv")
if ($sourceFiles.Count -ne $ExpectedCount) {
    throw "Expected $ExpectedCount EUR15 source files, found $($sourceFiles.Count)"
}

$pythonCandidates = @(
    (Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"),
    "python",
    "python3"
)
$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -match "[\\/]") {
        if (Test-Path $candidate) {
            $python = $candidate
            break
        }
    } else {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            $python = $cmd.Source
            break
        }
    }
}
if (-not $python) {
    throw "Python runtime not found."
}

New-Item -ItemType Directory -Force -Path $DestinationDir,$CatalogDir,$ReportsDir | Out-Null

Write-Output "EUR15_NORMALIZATION starting files=$($sourceFiles.Count)"
$normalizeArgs = @(
    $Normalizer,
    $SourceDir,
    $DestinationDir,
    $NormalizationCatalog,
    "--extraction-catalog",
    $ExtractionCatalog,
    "--expected-count",
    "$ExpectedCount"
)
& $python @normalizeArgs
if ($LASTEXITCODE -ne 0) {
    throw "EUR15 normalization failed with exit code $LASTEXITCODE"
}

$norm = Get-Content -LiteralPath $NormalizationCatalog -Raw | ConvertFrom-Json
if ($norm.status -ne "PASS") {
    throw "Normalization catalog status is not PASS"
}
if ([int]$norm.file_count -ne $ExpectedCount) {
    throw "Normalization catalog file_count mismatch"
}

$preferredReplay = Join-Path $DestinationDir "XBTEUR_15.normalized.csv.gz"
if (-not (Test-Path $preferredReplay)) {
    $firstReplay = Get-ChildItem -LiteralPath $DestinationDir -File -Filter "*EUR_15.normalized.csv.gz" | Sort-Object Name | Select-Object -First 1
    if ($null -eq $firstReplay) {
        throw "No normalized EUR15 file available for replay smoke"
    }
    $preferredReplay = $firstReplay.FullName
}

Write-Output "EUR15_REAL_PAIR_REPLAY pair_file=$preferredReplay"
$replayArgs = @(
    $Replay,
    $preferredReplay,
    "--lookback-bars",
    "20",
    "--horizon-bars",
    "24",
    "--output",
    $ReplayReport
)
& $python @replayArgs
if ($LASTEXITCODE -ne 0) {
    throw "Real-pair point-in-time replay smoke failed with exit code $LASTEXITCODE"
}

$replayObj = Get-Content -LiteralPath $ReplayReport -Raw | ConvertFrom-Json
if ($replayObj.status -ne "PASS") {
    throw "Replay report status is not PASS"
}

$result = [ordered]@{
    kind = "MINIPC_KRAKEN_EUR15_NORMALIZATION_RESULT_V1"
    status = "PASS"
    normalized_files = [int]$norm.file_count
    total_rows = [int64]$norm.total_rows
    pairs_with_gaps = [int]$norm.pairs_with_gaps
    total_gap_events = [int64]$norm.total_gap_events
    total_missing_intervals_not_filled = [int64]$norm.total_missing_intervals_not_filled
    normalization_catalog = $NormalizationCatalog
    replay_pair_file = $preferredReplay
    replay_report = $ReplayReport
    replay_status = $replayObj.status
    decision_sha256 = $replayObj.decision_sha256
    network_used = $false
    raw_source_modified = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    next_gate = "record_real_pair_replay_in_trial_ledger_then_broader_historical_replay"
}

$result | ConvertTo-Json -Depth 6
