param(
    [string]$TradingRoot = "",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
    $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if ([string]::IsNullOrWhiteSpace($homeRoot)) {
        throw "Unable to resolve user home directory."
    }
    $TradingRoot = Join-Path $homeRoot "Trading"
}

$HistoricalRoot = Join-Path $TradingRoot "Historical"
$root = [System.IO.Path]::GetPathRoot($HistoricalRoot)
if ($root -and $root.ToUpperInvariant().StartsWith("D:")) {
    throw "Drive D is blocked for historical project storage until its separate backup/repair gate is closed."
}

$dirs = @(
    (Join-Path $HistoricalRoot "raw\kraken\ohlcvt\archives"),
    (Join-Path $HistoricalRoot "raw\kraken\trades\archives"),
    (Join-Path $HistoricalRoot "staging"),
    (Join-Path $HistoricalRoot "normalized\kraken\eur"),
    (Join-Path $HistoricalRoot "catalog"),
    (Join-Path $HistoricalRoot "derived"),
    (Join-Path $HistoricalRoot "trials"),
    (Join-Path $HistoricalRoot "reports"),
    (Join-Path $HistoricalRoot "tmp")
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$manifest = Join-Path $repoRoot "research\historical\kraken-historical-manifest.json"
$preflight = Join-Path $repoRoot "tools\kraken-historical-preflight.py"

if (-not (Test-Path $manifest)) {
    throw "Historical manifest missing: $manifest"
}
if (-not (Test-Path $preflight)) {
    throw "Historical preflight tool missing: $preflight"
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

if ($Apply) {
    foreach ($dir in $dirs) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

$preflightArgs = @($preflight, "--manifest", $manifest)
if ($Apply) {
    $preflightArgs += "--probe-disk"
}

$preflightOutput = & $python @preflightArgs 2>&1
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "Historical metadata preflight failed (exit $exitCode): $($preflightOutput -join ' ')"
}

$result = [ordered]@{
    schema_version = 1
    kind = "MINIPC_HISTORICAL_RESEARCH_PREP_V1"
    status = "PASS"
    apply = [bool]$Apply
    trading_root = $TradingRoot
    historical_root = $HistoricalRoot
    directories = $dirs
    downloads_performed = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    preflight = ($preflightOutput -join [Environment]::NewLine)
}

$json = $result | ConvertTo-Json -Depth 6
Write-Output $json

if ($Apply) {
    $logs = Join-Path $TradingRoot "Logs"
    New-Item -ItemType Directory -Force -Path $logs | Out-Null
    $report = Join-Path $logs "historical-research-prep-latest.json"
    [System.IO.File]::WriteAllText($report, $json + [Environment]::NewLine)
    Write-Output "HISTORICAL_RESEARCH_PREP_REPORT $report"
}
