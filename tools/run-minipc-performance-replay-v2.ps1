param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "RUN_FROZEN_PERFORMANCE_REPLAY_V2"
$ExpectedCount = 648
$ExpectedSpecSha256 = "3920161d4912815f193d6dcc7291dfab064a794447162d9d2fe5ec1dc7da1b3f"

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
$Spec = Join-Path $RepoRoot "research\historical\performance-replay-spec-v2.json"
$Lock = Join-Path $RepoRoot "research\historical\performance-replay-spec-v2.lock.json"
$Validator = Join-Path $RepoRoot "tools\validate-performance-replay-spec-v2.py"
$Engine = Join-Path $RepoRoot "tools\historical-performance-replay-v2.py"
$Recorder = Join-Path $RepoRoot "tools\record-performance-replay-trial-v2.py"

$ResultReport = Join-Path $ReportsDir "kraken-eur15-performance-replay-v2-development.json"
$EventsOutput = Join-Path $ReportsDir "kraken-eur15-performance-replay-v2-events.jsonl.gz"
$TrialRecord = Join-Path $TrialsDir "performance-replay-v2-trial-record.json"

$plan = [ordered]@{
    kind = "MINIPC_FROZEN_PERFORMANCE_REPLAY_V2_PLAN"
    status = if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" }
    execute = [bool]$Execute
    expected_spec_sha256 = $ExpectedSpecSha256
    expected_normalized_files = $ExpectedCount
    research_role = "SECOND_LEG_CONFIRMATION_DEVELOPMENT_ONLY"
    pre2026_is_clean_validation = $false
    holdout_status = "LOCKED_DO_NOT_READ_IN_V2_DEVELOPMENT"
    holdout_opened = $false
    threshold_sweep_performed = $false
    horizon_sweep_performed = $false
    pair_subset_selection_performed = $false
    month_subset_selection_performed = $false
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
}

if (-not $Execute) {
    $plan | ConvertTo-Json -Depth 8
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
    throw "V2 spec lock status is not LOCKED"
}
if ($lockObj.spec_sha256 -ne $ExpectedSpecSha256) {
    throw "V2 lock checksum mismatch"
}
if ($lockObj.holdout_status -ne "LOCKED_DO_NOT_READ_IN_V2_DEVELOPMENT") {
    throw "V2 lock does not preserve sealed holdout"
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

Write-Output "PERF_V2 validating frozen distinct hypothesis"
& $python $Validator $Spec --expected-sha256 $ExpectedSpecSha256
if ($LASTEXITCODE -ne 0) {
    throw "Frozen V2 spec validation failed with exit code $LASTEXITCODE"
}

Write-Output "PERF_V2 executing development-only replay across $ExpectedCount normalized files"
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
    throw "Frozen V2 development replay failed with exit code $LASTEXITCODE"
}

$result = Get-Content -LiteralPath $ResultReport -Raw | ConvertFrom-Json
if ($result.status -ne "PASS") {
    throw "V2 result status is not PASS"
}
if ($result.spec_sha256 -ne $ExpectedSpecSha256) {
    throw "V2 result spec checksum mismatch"
}
if ([bool]$result.holdout_guard.holdout_metrics_computed) {
    throw "V2 sealed holdout metrics were computed"
}
if ([int]$result.holdout_guard.holdout_events_generated -ne 0) {
    throw "V2 sealed holdout event leakage detected"
}
if ([bool]$result.holdout_guard.holdout_used_for_rule_selection) {
    throw "V2 holdout was used for rule selection"
}
if ([bool]$result.guardrails.threshold_sweep_performed) {
    throw "V2 threshold-sweep guardrail violated"
}
if ([bool]$result.guardrails.horizon_sweep_performed) {
    throw "V2 horizon-sweep guardrail violated"
}

Write-Output "PERF_V2 recording immutable development trial"
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
    throw "V2 Trial Ledger record failed with exit code $LASTEXITCODE"
}
$recordOutput | ForEach-Object { Write-Output $_ }

$ledgerOutput = & $python (Join-Path $RepoRoot "tools\historical-trial-ledger.py") --db $LedgerDb --schema $Schema verify
if ($LASTEXITCODE -ne 0) {
    throw "Trial Ledger verification failed"
}
$ledgerOutput | ForEach-Object { Write-Output $_ }

$summary = [ordered]@{
    kind = "MINIPC_FROZEN_PERFORMANCE_REPLAY_V2_RESULT"
    status = "PASS"
    spec_sha256 = $result.spec_sha256
    initial_signal_count = [int]$result.initial_signal_count
    confirmed_event_count = [int]$result.confirmed_event_count
    confirmation_rate = $result.confirmation_rate
    net_primary_cost = $result.development_metrics.net_primary_cost
    gross = $result.development_metrics.gross
    unique_pairs = [int]$result.development_metrics.unique_pairs
    unique_months = [int]$result.development_metrics.unique_months
    top10_pair_event_share = $result.development_metrics.top10_pair_event_share
    development_gate = $result.preregistered_development_gate
    holdout_guard = $result.holdout_guard
    result_report = $ResultReport
    events_output = $EventsOutput
    trial_record = $TrialRecord
    ledger_db = $LedgerDb
    holdout_opened = $false
    threshold_sweep_performed = $false
    horizon_sweep_performed = $false
    pair_subset_selection_performed = $false
    month_subset_selection_performed = $false
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
    next_gate = $result.next_gate
}
$summary | ConvertTo-Json -Depth 12
