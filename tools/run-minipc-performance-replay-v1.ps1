param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "RUN_FROZEN_PERFORMANCE_REPLAY_V1"
$ExpectedCount = 648
$ExpectedSpecSha256 = "e8f82b9992228050188e334900b5ee35aeaa47111a526e38b1d0ae4234d33d27"

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
    $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if ([string]::IsNullOrWhiteSpace($homeRoot)) {
        throw "Unable to resolve user home directory."
    }
    $TradingRoot = Join-Path $homeRoot "Trading"
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$HistoricalRoot = Join-Path $TradingRoot "Historical"
$NormalizedDir = Join-Path $HistoricalRoot "normalized\kraken\eur\15m"
$NormalizationCatalog = Join-Path $HistoricalRoot "catalog\kraken-eur15-normalization.json"
$ReportsDir = Join-Path $HistoricalRoot "reports"
$TrialsDir = Join-Path $HistoricalRoot "trials"
$LedgerDb = Join-Path $TrialsDir "trial-ledger.sqlite3"
$Schema = Join-Path $RepoRoot "research\historical\trial-ledger-schema.json"
$Spec = Join-Path $RepoRoot "research\historical\performance-replay-spec-v1.json"
$Lock = Join-Path $RepoRoot "research\historical\performance-replay-spec-v1.lock.json"
$Validator = Join-Path $RepoRoot "tools\validate-performance-replay-spec.py"
$Engine = Join-Path $RepoRoot "tools\historical-performance-replay-v1.py"
$Recorder = Join-Path $RepoRoot "tools\record-performance-replay-trial.py"

$ResultReport = Join-Path $ReportsDir "kraken-eur15-performance-replay-v1.json"
$EventsOutput = Join-Path $ReportsDir "kraken-eur15-performance-replay-v1-events.jsonl.gz"
$TrialRecord = Join-Path $TrialsDir "performance-replay-v1-trial-record.json"

$plan = [ordered]@{
    kind = "MINIPC_FROZEN_PERFORMANCE_REPLAY_V1_PLAN"
    status = if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" }
    execute = [bool]$Execute
    expected_spec_sha256 = $ExpectedSpecSha256
    expected_normalized_files = $ExpectedCount
    normalized_dir = $NormalizedDir
    result_report = $ResultReport
    events_output = $EventsOutput
    ledger_db = $LedgerDb
    holdout_status = "LOCKED_DO_NOT_READ_IN_V1_SELECTION"
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
    threshold_optimization_performed = $false
}

if (-not $Execute) {
    $plan | ConvertTo-Json -Depth 6
    exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
    throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($required in @(
    $NormalizedDir,$NormalizationCatalog,$Schema,$Spec,$Lock,
    $Validator,$Engine,$Recorder
)) {
    if (-not (Test-Path $required)) {
        throw "Required input/tool missing: $required"
    }
}

$lockObj = Get-Content -LiteralPath $Lock -Raw | ConvertFrom-Json
if ($lockObj.status -ne "LOCKED") {
    throw "Frozen performance spec lock status is not LOCKED"
}
if ($lockObj.spec_sha256 -ne $ExpectedSpecSha256) {
    throw "Frozen performance spec lock checksum mismatch"
}

$normalizedFiles = @(Get-ChildItem -LiteralPath $NormalizedDir -File -Filter "*EUR_15.normalized.csv.gz")
if ($normalizedFiles.Count -ne $ExpectedCount) {
    throw "Expected $ExpectedCount normalized EUR15 files, found $($normalizedFiles.Count)"
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

New-Item -ItemType Directory -Force -Path $ReportsDir,$TrialsDir | Out-Null

Write-Output "PERF_V1 validating frozen spec (LF-normalized checksum)"
& $python $Validator $Spec --expected-sha256 $ExpectedSpecSha256
if ($LASTEXITCODE -ne 0) {
    throw "Frozen performance spec validation failed with exit code $LASTEXITCODE"
}

Write-Output "PERF_V1 executing pre-registered replay across $ExpectedCount normalized files"
$engineArgs = @(
    $Engine,
    $NormalizedDir,
    "--spec",$Spec,
    "--normalization-catalog",$NormalizationCatalog,
    "--output",$ResultReport,
    "--events-output",$EventsOutput,
    "--expected-count","$ExpectedCount"
)
& $python @engineArgs
if ($LASTEXITCODE -ne 0) {
    throw "Frozen performance replay V1 failed with exit code $LASTEXITCODE"
}

$result = Get-Content -LiteralPath $ResultReport -Raw | ConvertFrom-Json
if ($result.status -ne "PASS") {
    throw "Performance replay result status is not PASS"
}
if ($result.spec_sha256 -ne $ExpectedSpecSha256) {
    throw "Performance replay result spec checksum mismatch"
}
if ([bool]$result.holdout_guard.holdout_metrics_computed) {
    throw "Sealed holdout metrics were computed"
}
if ([int]$result.holdout_guard.holdout_events_generated -ne 0) {
    throw "Sealed holdout event leakage detected"
}
if ([bool]$result.guardrails.threshold_optimization_performed) {
    throw "Threshold optimization guardrail violated"
}

Write-Output "PERF_V1 recording immutable trial"
$recordArgs = @(
    $Recorder,
    "--spec",$Spec,
    "--lock",$Lock,
    "--result",$ResultReport,
    "--db",$LedgerDb,
    "--schema",$Schema,
    "--output-record",$TrialRecord,
    "--repo-root",$RepoRoot
)
$recordOutput = & $python @recordArgs
if ($LASTEXITCODE -ne 0) {
    throw "Performance replay trial record failed with exit code $LASTEXITCODE"
}
$recordOutput | ForEach-Object { Write-Output $_ }

$ledgerOutput = & $python (Join-Path $RepoRoot "tools\historical-trial-ledger.py") --db $LedgerDb --schema $Schema verify
if ($LASTEXITCODE -ne 0) {
    throw "Trial Ledger verification failed"
}
$ledgerOutput | ForEach-Object { Write-Output $_ }

$summary = [ordered]@{
    kind = "MINIPC_FROZEN_PERFORMANCE_REPLAY_V1_RESULT"
    status = "PASS"
    spec_sha256 = $result.spec_sha256
    total_event_count = [int]$result.total_event_count
    split_event_counts = $result.split_event_counts
    primary_validation_metrics = $result.primary_validation_metrics
    holdout_guard = $result.holdout_guard
    result_report = $ResultReport
    events_output = $EventsOutput
    trial_record = $TrialRecord
    ledger_db = $LedgerDb
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
    threshold_optimization_performed = $false
    holdout_opened = $false
    next_gate = "review_validation_without_opening_holdout"
}
$summary | ConvertTo-Json -Depth 10
