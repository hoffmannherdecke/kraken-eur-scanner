param(
  [switch]$Execute,
  [switch]$DiagnoseOnly,
  [int]$WaitMinutes = 90,
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading')
)
# One manual research handoff ONLY. Does not install, start or stop Windows
# services, change active V2R4, Supabase paper-series or any money order.
$ErrorActionPreference = 'Stop'
$repo = Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$python = Join-Path $TradingRoot 'Runtime\kraken-eur-scanner-venv\Scripts\python.exe'
$research = Join-Path $TradingRoot 'Research'
$report = Join-Path $research 'v3-b-shadow5-http10-20261011.json'
if ($Execute -and $DiagnoseOnly) { throw 'BLOCKED_EXCLUSIVE_RUN_MODE' }
if ($WaitMinutes -lt 0 -or $WaitMinutes -gt 90) { throw 'BLOCKED_UNAPPROVED_WAIT_WINDOW' }
$plan = [ordered]@{
  kind = 'V3_B_SHADOW5_MINIPC_MANUAL_HANDOFF_V1'
  status = 'PLAN_ONLY'
  user_approval_already_exists = 'APPROVE V3-B SHADOW-5 / HTTP-10'
  limit_candidates = 5
  absolute_model_http_attempts_including_retries = 10
  live_v2r4_changed = $false
  shadow_service_started = $false
  v3_paper_cutover = $false
  extra_windows_tasks = $false
  real_money_actions = $false
  orders = $false
  one_off_budget_file = $report
}
if (-not $Execute -and -not $DiagnoseOnly) {
  $plan | ConvertTo-Json -Depth 5
  exit 0
}
foreach ($required in @($repo,$python)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw ('BLOCKED_LOCAL_PREREQUISITE_NOT_PRESENT: ' + (Split-Path $required -Leaf))
  }
}
if ($Execute -and (Test-Path -LiteralPath $report)) {
  throw 'BLOCKED_PREEXISTING_V3B_SHADOW5_JOURNAL_NO_RETRY_NO_EXTRA_COST'
}
if ($Execute -and -not (Test-Path -LiteralPath $research)) {
  New-Item -ItemType Directory -Path $research -Force | Out-Null
}
$temp = Join-Path $env:TEMP ('v3-b-shadow5-' + [guid]::NewGuid().ToString('N').Substring(0,12))
$attached = $false
try {
  & git -C $repo fetch --no-tags origin main --quiet
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_GIT_FETCH_NO_RUNTIME_CHANGE' }
  & git -C $repo worktree add --quiet --detach $temp origin/main
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_DETACHED_WORKTREE_NO_RUNTIME_CHANGE' }
  $attached = $true
  $probe = Join-Path $temp 'paper_evaluator\v3_b_bounded_shadow_five.py'
  $receipt = Join-Path $temp 'research\v3\v3-b-shadow5-approval-20261011.json'
  if (-not (Test-Path -LiteralPath $probe) -or -not (Test-Path -LiteralPath $receipt)) {
    throw 'BLOCKED_APPROVED_V3B_SHADOW5_CODE_OR_RECEIPT_MISSING'
  }
  Push-Location $temp
  try {
    $argsForModel = @('-m','paper_evaluator.v3_b_bounded_shadow_five',
      '--trading-root',$TradingRoot,'--code-root',$temp,
      '--report',$report,'--wait-minutes',"$WaitMinutes")
    if ($DiagnoseOnly) { $argsForModel += '--diagnose-only' }
    & $python @argsForModel
    $ret = $LASTEXITCODE
  }
  finally { Pop-Location }
  if ($ret -ne 0) {
    throw ('V3_B_SHADOW5_STOPPED_DO_NOT_RETRY_BLINDLY_CODE_' + $ret)
  }
  if ($DiagnoseOnly) {
    Write-Output 'V3_B_SHADOW5_PREFLIGHT_OK_NO_MODEL_NO_PAPER_CHANGE'
  } else {
    Write-Output 'V3_B_SHADOW5_RUN_RECORDED_NO_MODEL_BUDGET_RESET'
    Write-Output ('RESEARCH_REPORT=' + $report)
  }
}
finally {
  if ($attached) {
    & git -C $repo worktree remove --force $temp 2>$null | Out-Null
  }
  if (Test-Path -LiteralPath $temp) {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
