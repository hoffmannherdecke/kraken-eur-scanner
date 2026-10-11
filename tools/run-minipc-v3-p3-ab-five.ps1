param(
  [switch]$Execute,
  [switch]$DiagnoseOnly,
  [int]$Minutes = 360,
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading')
)
# One approved, finite P3 research window. NEVER a paper/real-money launcher.
$ErrorActionPreference = 'Stop'
if ($Execute -and $DiagnoseOnly) { throw 'BLOCKED_EXCLUSIVE_V3_P3_AB_RUN_MODES' }
if ($Minutes -lt 0 -or $Minutes -gt 360) { throw 'BLOCKED_UNAPPROVED_V3_P3_AB_WINDOW' }
$repo = Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$python = Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$research = Join-Path $TradingRoot 'Research'
$report = Join-Path $research 'v3-p3-ab-five-http10-6h-20261011.json'
$plan = [ordered]@{
  kind = 'V3_P3_AB_FIVE_HTTP10_6H_MINIPC_HANDOFF_V1'
  mode = if ($Execute) { 'ONE_TIME_MANUAL_EXECUTE' } elseif ($DiagnoseOnly) { 'READ_ONLY_PREFLIGHT' } else { 'PLAN_ONLY' }
  user_approval = 'APPROVE V3-P3 STANDARD-EXPERIMENTAL SAME-CLOCK 5 QUALIFIED HTTP10 6H PAPER-ONLY'
  max_qualified_setups = 5
  max_model_http_attempts_including_retries = 10
  max_minutes = 360
  requested_minutes = $Minutes
  report_path = $report
  orders = $false
  real_money_actions = $false
  v2r4_runtime_changed = $false
  new_schedules = $false
  model_calls_without_execute = 0
}
if (-not $Execute -and -not $DiagnoseOnly) {
  $plan | ConvertTo-Json -Depth 4
  exit 0
}
foreach ($required in @($repo, $python, $research)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw ('BLOCKED_MINIPC_PREREQUISITE_MISSING: ' + (Split-Path $required -Leaf))
  }
}
if (Test-Path -LiteralPath $report) {
  throw 'BLOCKED_V3_P3_AB_REPORT_ALREADY_EXISTS_NO_RESTART_NO_COST_RESET'
}
$temp = Join-Path $env:TEMP ('v3-p3-ab-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$attached = $false
try {
  & git -C $repo fetch --no-tags origin main --quiet
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_GIT_FETCH_NO_RUNTIME_CHANGE' }
  & git -C $repo worktree add --quiet --detach $temp origin/main
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_V3_RESEARCH_WORKTREE' }
  $attached = $true
  $runner = Join-Path $temp 'paper_evaluator\v3_p3_ab_five_bounded_research.py'
  $approval = Join-Path $temp 'research\v3\v3-p3-ab-five-approval-20261011.json'
  if (-not (Test-Path $runner) -or -not (Test-Path $approval)) {
    throw 'BLOCKED_APPROVED_V3_P3_AB_RUNNER_OR_CONTRACT_MISSING'
  }
  Push-Location $temp
  try {
    $argsForPython = @(
      '-m','paper_evaluator.v3_p3_ab_five_bounded_research',
      '--trading-root',$TradingRoot,'--code-root',$temp,
      '--minutes',"$Minutes"
    )
    if ($DiagnoseOnly) { $argsForPython += '--diagnose-only' }
    & $python @argsForPython
    $result = $LASTEXITCODE
  }
  finally { Pop-Location }
  if ($result -ne 0) {
    throw ('V3_P3_AB_STOPPED_NO_AUTO_RETRY_EXIT_' + $result)
  }
  if ($DiagnoseOnly) {
    Write-Output 'V3_P3_AB_PREFLIGHT_COMPLETE_NO_MODEL_NO_PAPER_CHANGE'
  } else {
    Write-Output 'V3_P3_AB_FINITE_RESEARCH_RESULT_RECORDED_NO_PAPER_CHANGE'
    Write-Output ('REPORT=' + $report)
  }
}
finally {
  if ($attached) { & git -C $repo worktree remove --force $temp 2>$null | Out-Null }
  if (Test-Path -LiteralPath $temp) {
    Remove-Item -LiteralPath $temp -Force -Recurse -ErrorAction SilentlyContinue
  }
}
