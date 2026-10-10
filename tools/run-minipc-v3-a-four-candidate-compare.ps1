param(
  [switch]$Execute,
  [int]$WaitMinutes = 60,
  [string]$ExpectedSeriesId = 'PAPER-V2R4-20261009T110135Z',
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading')
)
# One manual finite research invocation; no scheduler, no V2R4/H3/H6 write.
# Validated source code from detached origin/main only. One immutable research
# report prevents accidentally re-running the same authorized 8-call budget.
$ErrorActionPreference = 'Stop'
$repo = Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$python = Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$runtimeRoot = Join-Path $TradingRoot 'Runtime'
$research = Join-Path $TradingRoot 'Research'
$report = Join-Path $research 'v3-a-four-candidate-input-only-20261010.json'

if ($ExpectedSeriesId -cne 'PAPER-V2R4-20261009T110135Z') {
  throw 'BLOCKED_UNREVIEWED_V2R4_SERIES'
}
if ($WaitMinutes -lt 0 -or $WaitMinutes -gt 90) { throw 'BLOCKED_UNREVIEWED_WAIT_WINDOW' }
$plan = [ordered]@{
  kind = 'V3_A_MANUAL_FOUR_CANDIDATE_INPUT_ONLY_BATCH_V1'
  status = 'PLAN_ONLY'
  max_fresh_distinct_pairs = 4
  model_http_requests_absolute_cap_including_retries = 8
  max_requests_per_candidate = 2
  waiting_window_minutes = $WaitMinutes
  cohort = 'ONLY_NEW_HANDOFFS_AFTER_MANUAL_START_UNDER_15_MINUTES_OLD'
  baseline = 'FROZEN_V2R4_EVALUATOR_SAME_TICKER_AND_STANDARD_CONTEXT'
  one_new_input = 'POINT_IN_TIME_CLOSED_1M_5M_15M_COIN_BARS_VOLUME_ATR_LOCAL_LOW'
  changes_active_paper = $false
  changes_h3_h6 = $false
  real_money_actions = $false
  live_orders = $false
  extra_scheduler = $false
  result_path = $report
  zero_trade_is_economic_pass = $false
}
if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 6
  exit 0
}
foreach ($p in @($repo,$python,$runtimeRoot)) {
  if (-not (Test-Path -LiteralPath $p)) {
    throw ('BLOCKED_MISSING_MINIPC_PREREQUISITE_' + (Split-Path -Leaf $p))
  }
}
if (Test-Path -LiteralPath $report) {
  throw 'BLOCKED_EXISTING_V3_RESEARCH_REPORT_NO_REPEATED_MODEL_BUDGET'
}
$stages = @(Get-ChildItem -LiteralPath $runtimeRoot -Directory -Filter 'v2r4-paper-stage-*' -ErrorAction SilentlyContinue |
  Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'paper_runtime_control.json') })
if ($stages.Count -ne 1) { throw 'BLOCKED_MULTIPLE_OR_MISSING_V2R4_STAGES' }
$stageControl = Get-Content -LiteralPath (Join-Path $stages[0].FullName 'paper_runtime_control.json') -Raw | ConvertFrom-Json
if ($stageControl.series_id -cne $ExpectedSeriesId -or
    $stageControl.enabled -ne $true -or
    $stageControl.paper_only -ne $true -or
    $stageControl.real_money_actions_enabled -ne $false) {
  throw 'BLOCKED_V2R4_STAGE_OR_PAPER_GUARD_MISMATCH'
}
$temp = Join-Path $env:TEMP ('v3-four-case-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$worktreeCreated = $false
try {
  & git -C $repo fetch --no-tags origin main --quiet
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_GIT_FETCH' }
  & git -C $repo worktree add --quiet --detach $temp origin/main
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_TEMPORARY_RESEARCH_WORKTREE' }
  $worktreeCreated = $true
  $probe = Join-Path $temp 'paper_evaluator\v3_bounded_four_candidate_compare.py'
  if (-not (Test-Path -LiteralPath $probe)) { throw 'BLOCKED_MISSING_REVIEWED_BATCH_SCRIPT' }
  if (-not (Test-Path -LiteralPath $research)) {
    New-Item -ItemType Directory -Path $research -Force | Out-Null
  }
  Push-Location $temp
  try {
    & $python -m paper_evaluator.v3_bounded_four_candidate_compare --trading-root $TradingRoot --code-root $temp --expected-series-id $ExpectedSeriesId --report $report --wait-minutes $WaitMinutes
    $code = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($code -ne 0) {
    Write-Output ('V3_RESEARCH_STOPPED_OR_BLOCKED_STATUS_' + $code)
    Write-Output ('RESEARCH_REPORT_IF_STARTED=' + $report)
    exit $code
  }
  Write-Output 'V3_A_MANUAL_INPUT_ONLY_FINISHED_NO_PAPER_OR_ORDER_CHANGE'
  Write-Output ('RESEARCH_REPORT=' + $report)
}
finally {
  if ($worktreeCreated) {
    & git -C $repo worktree remove --force $temp 2>$null | Out-Null
  }
  if (Test-Path -LiteralPath $temp) {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
