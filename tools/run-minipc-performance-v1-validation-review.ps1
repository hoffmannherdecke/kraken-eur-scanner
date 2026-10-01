param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "REVIEW_PERFORMANCE_V1_VALIDATION_ONLY"

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
    $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
    if ([string]::IsNullOrWhiteSpace($homeRoot)) {
        throw "Unable to resolve user home directory."
    }
    $TradingRoot = Join-Path $homeRoot "Trading"
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
$HistoricalRoot = Join-Path $TradingRoot "Historical"
$ReportsDir = Join-Path $HistoricalRoot "reports"
$Spec = Join-Path $RepoRoot "research\historical\performance-replay-spec-v1.json"
$Result = Join-Path $ReportsDir "kraken-eur15-performance-replay-v1.json"
$Events = Join-Path $ReportsDir "kraken-eur15-performance-replay-v1-events.jsonl.gz"
$Review = Join-Path $ReportsDir "kraken-eur15-performance-replay-v1-validation-review.json"
$Reviewer = Join-Path $RepoRoot "tools\review-performance-replay-v1.py"

$plan = [ordered]@{
    kind = "MINIPC_PERFORMANCE_V1_VALIDATION_REVIEW_PLAN"
    status = if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" }
    execute = [bool]$Execute
    review_scope = "VALIDATION_ONLY"
    holdout_opened = $false
    threshold_sweep_performed = $false
    horizon_sweep_performed = $false
    pair_selection_performed = $false
    month_selection_performed = $false
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
    output = $Review
}

if (-not $Execute) {
    $plan | ConvertTo-Json -Depth 6
    exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
    throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($required in @($Spec,$Result,$Events,$Reviewer)) {
    if (-not (Test-Path $required)) {
        throw "Required input/tool missing: $required"
    }
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

Write-Output "PERF_V1_REVIEW validation-only diagnostics; holdout remains sealed"

$argsList = @(
    $Reviewer,
    "--spec",$Spec,
    "--result",$Result,
    "--events",$Events,
    "--output",$Review
)
& $python @argsList
if ($LASTEXITCODE -ne 0) {
    throw "Performance V1 validation review failed with exit code $LASTEXITCODE"
}

$reviewObj = Get-Content -LiteralPath $Review -Raw | ConvertFrom-Json
if ($reviewObj.status -ne "PASS") {
    throw "Validation review status is not PASS"
}
if ([bool]$reviewObj.interpretation.holdout_opened) {
    throw "Holdout-open guardrail violated"
}
if ([bool]$reviewObj.interpretation.threshold_sweep_performed) {
    throw "Threshold-sweep guardrail violated"
}
if ([bool]$reviewObj.interpretation.horizon_sweep_performed) {
    throw "Horizon-sweep guardrail violated"
}
if ([bool]$reviewObj.interpretation.pair_selection_performed) {
    throw "Pair-selection guardrail violated"
}
if ([bool]$reviewObj.interpretation.month_selection_performed) {
    throw "Month-selection guardrail violated"
}

$summary = [ordered]@{
    kind = "MINIPC_PERFORMANCE_V1_VALIDATION_REVIEW_RESULT"
    status = "PASS"
    validation_event_count = [int]$reviewObj.validation_event_count
    primary_round_trip_cost_pct = $reviewObj.primary_round_trip_cost_pct
    gross = $reviewObj.return_summary.gross
    net_primary_cost = $reviewObj.return_summary.net_primary_cost
    mfe = $reviewObj.return_summary.mfe
    mae = $reviewObj.return_summary.mae
    peak_to_exit_giveback_pct = $reviewObj.return_summary.peak_to_exit_giveback_pct
    outcome_decomposition = $reviewObj.outcome_decomposition
    excursion_diagnostics = $reviewObj.excursion_diagnostics
    concentration_diagnostics = $reviewObj.concentration_diagnostics
    failure_flags = $reviewObj.failure_flags
    review_report = $Review
    holdout_opened = $false
    threshold_sweep_performed = $false
    horizon_sweep_performed = $false
    pair_selection_performed = $false
    month_selection_performed = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    real_money_action = $false
    next_gate = $reviewObj.next_gate
}
$summary | ConvertTo-Json -Depth 10
