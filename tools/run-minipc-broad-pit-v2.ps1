param(
    [switch]$Execute,
    [string]$Confirm = "",
    [string]$TradingRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ExpectedConfirm = "RUN_BROAD_PIT_V2_2026Q2"
$ExpectedCount = 648
$PairCount = 12
$AnchorsPerPair = 3

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
$Catalog = Join-Path $HistoricalRoot "catalog\kraken-eur15-normalization.json"
$ReportsDir = Join-Path $HistoricalRoot "reports"
$TrialsDir = Join-Path $HistoricalRoot "trials"
$LedgerDb = Join-Path $TrialsDir "trial-ledger.sqlite3"
$Schema = Join-Path $RepoRoot "research\historical\trial-ledger-schema.json"

$ReplayV2 = Join-Path $RepoRoot "tools\historical-real-pair-replay-smoke-v2.py"
$BroadSmoke = Join-Path $RepoRoot "tools\historical-broad-pit-smoke.py"
$Recorder = Join-Path $RepoRoot "tools\record-real-pair-replay-trial.py"

$ReplayV2Report = Join-Path $ReportsDir "kraken-eur15-real-pair-replay-smoke-v2.json"
$BroadReport = Join-Path $ReportsDir "kraken-eur15-broad-pit-smoke.json"
$TrialRecord = Join-Path $TrialsDir "real-pair-replay-trial-record-v2.json"

$plan = [ordered]@{
    kind = "MINIPC_BROAD_PIT_V2_PLAN_V1"
    status = if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" }
    execute = [bool]$Execute
    expected_normalized_files = $ExpectedCount
    pair_count = $PairCount
    anchors_per_pair = $AnchorsPerPair
    normalized_dir = $NormalizedDir
    replay_v2_report = $ReplayV2Report
    broad_report = $BroadReport
    ledger_db = $LedgerDb
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    performance_backtest_started = $false
}

if (-not $Execute) {
    $plan | ConvertTo-Json -Depth 5
    exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
    throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($required in @($NormalizedDir,$Catalog,$Schema,$ReplayV2,$BroadSmoke,$Recorder)) {
    if (-not (Test-Path $required)) {
        throw "Required input/tool missing: $required"
    }
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

$preferredReplay = Join-Path $NormalizedDir "XBTEUR_15.normalized.csv.gz"
if (-not (Test-Path $preferredReplay)) {
    $firstReplay = Get-ChildItem -LiteralPath $NormalizedDir -File -Filter "*EUR_15.normalized.csv.gz" | Sort-Object Name | Select-Object -First 1
    if ($null -eq $firstReplay) {
        throw "No normalized EUR15 pair available"
    }
    $preferredReplay = $firstReplay.FullName
}

Write-Output "PIT_V2 replay_file=$preferredReplay"
$replayArgs = @(
    $ReplayV2,
    $preferredReplay,
    "--lookback-bars","20",
    "--horizon-bars","24",
    "--output",$ReplayV2Report
)
& $python @replayArgs
if ($LASTEXITCODE -ne 0) {
    throw "PIT V2 replay failed with exit code $LASTEXITCODE"
}

$replay = Get-Content -LiteralPath $ReplayV2Report -Raw | ConvertFrom-Json
if ($replay.status -ne "PASS") {
    throw "PIT V2 replay report status is not PASS"
}
if (-not [bool]$replay.decision.point_in_time_assertions.history_contiguous_15m) {
    throw "PIT V2 history contiguity guard failed"
}
if (-not [bool]$replay.label.future_contiguous_15m) {
    throw "PIT V2 future contiguity guard failed"
}

Write-Output "PIT_V2 ledger_record"
$recordArgs = @(
    $Recorder,
    "--normalization-catalog",$Catalog,
    "--replay-report",$ReplayV2Report,
    "--db",$LedgerDb,
    "--schema",$Schema,
    "--output-record",$TrialRecord,
    "--repo-root",$RepoRoot,
    "--expected-normalized-count","648"
)
$recordOutput = & $python @recordArgs
if ($LASTEXITCODE -ne 0) {
    throw "PIT V2 Trial Ledger record failed with exit code $LASTEXITCODE"
}
$recordOutput | ForEach-Object { Write-Output $_ }

Write-Output "BROAD_PIT starting pairs=$PairCount anchors_per_pair=$AnchorsPerPair"
$broadArgs = @(
    $BroadSmoke,
    $NormalizedDir,
    "--repo-root",$RepoRoot,
    "--expected-count","648",
    "--pair-count","$PairCount",
    "--anchors-per-pair","$AnchorsPerPair",
    "--lookback-bars","20",
    "--horizon-bars","24",
    "--output",$BroadReport
)
& $python @broadArgs
if ($LASTEXITCODE -ne 0) {
    throw "Broad PIT methodology smoke failed with exit code $LASTEXITCODE"
}

$broad = Get-Content -LiteralPath $BroadReport -Raw | ConvertFrom-Json
if ($broad.status -ne "PASS") {
    throw "Broad PIT report status is not PASS"
}
if ([int]$broad.integrity_summary.future_feature_leak_cases -ne 0) {
    throw "Broad PIT future leakage detected"
}
if ([int]$broad.integrity_summary.non_contiguous_history_cases -ne 0) {
    throw "Broad PIT non-contiguous history detected"
}
if ([int]$broad.integrity_summary.non_contiguous_future_cases -ne 0) {
    throw "Broad PIT non-contiguous future horizon detected"
}
if ([int]$broad.integrity_summary.labels_not_generated_after_freeze -ne 0) {
    throw "Broad PIT label-freeze invariant failed"
}

$ledgerVerifyOutput = & $python (Join-Path $RepoRoot "tools\historical-trial-ledger.py") --db $LedgerDb --schema $Schema verify
if ($LASTEXITCODE -ne 0) {
    throw "Trial Ledger verify failed"
}
$ledgerVerifyOutput | ForEach-Object { Write-Output $_ }

$result = [ordered]@{
    kind = "MINIPC_BROAD_PIT_V2_RESULT_V1"
    status = "PASS"
    replay_v2_status = $replay.status
    replay_v2_decision_sha256 = $replay.decision_sha256
    replay_v2_eligible_contiguous_windows = [int]$replay.eligible_contiguous_decision_windows
    broad_status = $broad.status
    normalized_file_count = [int]$broad.normalized_file_count
    eligible_pair_count = [int]$broad.eligible_pair_count
    skipped_pair_count = [int]$broad.skipped_pair_count
    selected_pair_count = [int]$broad.selected_pair_count
    broad_case_count = [int]$broad.case_count
    integrity_summary = $broad.integrity_summary
    replay_v2_report = $ReplayV2Report
    broad_report = $BroadReport
    trial_record = $TrialRecord
    ledger_db = $LedgerDb
    network_used = $false
    active_strategy_changed = $false
    paper_shadow_runtime_changed = $false
    performance_backtest_started = $false
    next_gate = "freeze_first_performance_oriented_historical_replay_spec"
}

$result | ConvertTo-Json -Depth 8
