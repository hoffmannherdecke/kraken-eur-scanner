param(
  [switch]$Execute,
  [string]$ExpectedSeriesId = 'PAPER-V2R4-20261009T110135Z',
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading')
)
# One-shot only. No change to active Mini-PC checkout, runtime,
# Windows tasks, environment secrets, Paper state or cloud database.
$ErrorActionPreference = 'Stop'
$repo = Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$runtimeRoot = Join-Path $TradingRoot 'Runtime'
$python = Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$key = Join-Path $TradingRoot 'Secrets\openai-api-key.txt'
$plan = [ordered]@{
  kind = 'MINIPC_V3_ENTRY_ONE_SHOT_MODEL_COMPARE_V1'
  status = 'PLAN_ONLY'
  active_v2r4_change = $false
  active_h3_change = $false
  scheduled_tasks_change = $false
  orders = $false
  real_money_actions = $false
  source = 'ONLY_EXACT_PINNED_TECHNICAL_SUCCESSOR_NOT_ORIGINAL_FROZEN_APP'
  expected_series_id = $ExpectedSeriesId
  model_calls_if_eligible = 2
  compare = 'same-snapshot baseline vs baseline-plus-closed-coin-bars'
  output = 'compact stdout only; temporary Git checkout removed'
}
if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 5
  exit 0
}
if ($ExpectedSeriesId -cne 'PAPER-V2R4-20261009T110135Z') {
  throw 'BLOCKED_UNREVIEWED_SERIES_ID'
}
$activeRuntimeDirs = @(Get-ChildItem -LiteralPath $runtimeRoot -Directory -Filter 'v2r4-paper-stage-*' -ErrorAction SilentlyContinue |
  Where-Object { Test-Path (Join-Path $_.FullName 'paper_runtime_control.json') })
if ($activeRuntimeDirs.Count -ne 1) { throw 'BLOCKED_AMBIGUOUS_OR_MISSING_TECHNICAL_SUCCESSOR' }
$app = $activeRuntimeDirs[0].FullName
$c = Get-Content (Join-Path $app 'paper_runtime_control.json') -Raw | ConvertFrom-Json
if ($c.series_id -cne $ExpectedSeriesId -or $c.paper_only -ne $true -or $c.real_money_actions_enabled -ne $false) {
  throw 'BLOCKED_STAGE_SERIES_OR_PAPER_SAFETY_MISMATCH'
}
foreach ($required in @($repo,$app,$python,$key)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw ('BLOCKED_LOCAL_PREREQUISITE_NOT_AVAILABLE: ' + (Split-Path $required -Leaf))
  }
}
$temp = Join-Path $env:TEMP ('v3-one-shot-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$worktreeCreated = $false
try {
  # Existing active repo checkout stays at its exact existing HEAD.
  & git -C $repo fetch --no-tags origin main --quiet
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_EXISTING_GIT_FETCH_CREDENTIALS_OR_NETWORK' }
  & git -C $repo worktree add --quiet --detach $temp origin/main
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_INERT_TEMP_WORKTREE_CREATION' }
  $worktreeCreated = $true
  $script = Join-Path $temp 'paper_evaluator\v3_one_shot_model_compare.py'
  if (-not (Test-Path -LiteralPath $script)) { throw 'BLOCKED_MISSING_REVIEWED_PROBE_SCRIPT' }
  Push-Location $temp
  try {
    & $python -m paper_evaluator.v3_one_shot_model_compare --trading-root $TradingRoot --code-root $temp --expected-series-id $ExpectedSeriesId
    $code = $LASTEXITCODE
  }
  finally { Pop-Location }
  if ($code -ne 0) {
    throw ('V3_ONE_SHOT_BLOCKED_NO_PAPER_OR_ORDER_CHANGE: ' + $code)
  }
  Write-Output '{"kind":"MINIPC_V3_ENTRY_MODEL_COMPARE_WRAPPER","status":"FINISHED_PAPER_UNCHANGED","orders":false,"real_money_actions":false}'
}
finally {
  if ($worktreeCreated) {
    & git -C $repo worktree remove --force $temp 2>$null | Out-Null
  }
  if (Test-Path -LiteralPath $temp) {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
