param(
  [switch]$Execute,
  [string]$Confirm = "",
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$Branch = "",
  [int]$MaxEventAgeMinutes = 30
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ExpectedConfirm = "RUN_REAL_ALTRADY_KRAKEN_V2R4_SMOKE"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$python = Join-Path $TradingRoot "Runtime\kraken-eur-scanner-venv\Scripts\python.exe"
$keyFile = Join-Path $TradingRoot "Secrets\openai-api-key.txt"
$heartbeat = Join-Path $TradingRoot "State\kraken-canary-heartbeat.json"
$realAltradyLog = Join-Path $TradingRoot "Logs\altrady-trigger-events.jsonl"
$tempRoot = Join-Path $TradingRoot "Temp"
$helper = Join-Path $repo "tools\v2r4-real-altrady-release-smoke.py"

$plan = [ordered]@{
  kind = "MINIPC_V2R4_REAL_ALTRADY_KRAKEN_SMOKE_V1"
  status = $(if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" })
  execute = [bool]$Execute
  branch = $(if ([string]::IsNullOrWhiteSpace($Branch)) { $null } else { $Branch })
  binding_spec = "research/v2r4/paper_strategy_spec_v2r4_release_candidate.json"
  max_event_age_minutes = $MaxEventAgeMinutes
  real_altrady_log = $realAltradyLog
  isolation = "TEMP_WORKTREE_AND_TEMP_RUNTIME_ONLY"
  required_real_event = $true
  strategy_action = "FRESH_PAPER_RECHECK_ONLY"
  kraken_public_is_condition_truth = $true
  altrady_role = "WAKEUP_HINT_ONLY"
  guardrails = [ordered]@{
    active_series_mutation = $false
    live_runtime_state_mutation = $false
    private_kraken_api = $false
    order_api = $false
    real_money_actions = $false
  }
}

if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 8
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Branch)) {
  throw "Execution blocked. Supply the explicit current V2R4 release-candidate branch."
}

if ($Confirm -ne $ExpectedConfirm) {
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($p in @($repo,$python,$keyFile,$heartbeat,$realAltradyLog,$tempRoot,$helper)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

$hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
$hbTime = [datetime]$hb.checked_at_utc
$hbAge = [math]::Round(((Get-Date).ToUniversalTime() - $hbTime.ToUniversalTime()).TotalSeconds,1)
if ($hb.status -ne "HEALTHY" -or $hbAge -gt 30) {
  throw ("Kraken canary is not fresh/healthy: status=" + $hb.status + " age_sec=" + $hbAge)
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$worktree = Join-Path $tempRoot ("v2r4-real-altrady-smoke-code-" + $stamp)
$caseRoot = Join-Path $tempRoot ("v2r4-real-altrady-smoke-case-" + $stamp)
New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null

Write-Host "[REAL-ALTRADY-V2R4] 1/8 Fetch isolated current candidate branch"
Push-Location $repo
try {
  & git fetch origin $Branch
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
  $branchSha = (& git rev-parse ("origin/" + $Branch)).Trim()
  & git worktree add --detach $worktree ("origin/" + $Branch)
  if ($LASTEXITCODE -ne 0) { throw "git worktree add failed" }
} finally {
  Pop-Location
}

try {
  Push-Location $worktree
  try {
    Write-Host "[REAL-ALTRADY-V2R4] 2/8 Compile release-candidate runtime"
    $compileArgs = @(
      "-m","py_compile",
      "paper_evaluator/v2r4_trigger_contract.py",
      "paper_evaluator/v2r4_trigger_plan.py",
      "paper_evaluator/v2r4_local_recheck.py",
      "paper_evaluator/v2r4_wait_runtime.py"
    )
    & $python @compileArgs
    if ($LASTEXITCODE -ne 0) { throw "V2R4 runtime compile failed" }

    Write-Host "[REAL-ALTRADY-V2R4] 3/8 Validate latest real Altrady event and prepare isolated same-pair WAIT fixture"
    $prepareArgs = @(
      $helper,"prepare",
      "--real-log",$realAltradyLog,
      "--root",$caseRoot,
      "--code-root",$worktree,
      "--max-age-minutes","$MaxEventAgeMinutes"
    )
    $fixtureJson = & $python @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw "real Altrady fixture preparation failed" }
    $fixture = $fixtureJson | ConvertFrom-Json

    $bindingSpec = Join-Path $worktree "research\v2r4\paper_strategy_spec_v2r4_release_candidate.json"
    if (-not (Test-Path $bindingSpec)) { throw "Binding V2R4 release-candidate spec missing: $bindingSpec" }
    Copy-Item $bindingSpec (Join-Path $caseRoot "spec.json")

    Write-Host "[REAL-ALTRADY-V2R4] 4/8 Execute real transport wakeup -> fresh Kraken condition -> isolated paper recheck"
    $runArgs = @(
      "paper_evaluator/v2r4_wait_runtime.py",
      "--once",
      "--execute-recheck",
      "--decision-dir",(Join-Path $caseRoot "decisions"),
      "--recheck-dir",(Join-Path $caseRoot "rechecks"),
      "--candidate-dir",(Join-Path $caseRoot "candidates"),
      "--receipt-dir",(Join-Path $caseRoot "receipts"),
      "--state",(Join-Path $caseRoot "state\wait-runtime-state.json"),
      "--heartbeat",(Join-Path $caseRoot "state\wait-runtime-heartbeat.json"),
      "--altrady-log",(Join-Path $caseRoot "logs\altrady-trigger-events.jsonl"),
      "--spec",(Join-Path $caseRoot "spec.json"),
      "--control",(Join-Path $caseRoot "control.json"),
      "--api-key-file",$keyFile
    )
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw "real Altrady -> Kraken V2R4 smoke failed" }

    Write-Host "[REAL-ALTRADY-V2R4] 5/8 Verify real wakeup, Kraken truth and paper-only safety"
    $summaryJson = & $python $helper "verify" "--root" $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "real Altrady smoke verification failed" }
    $summary = $summaryJson | ConvertFrom-Json

    Write-Host "[REAL-ALTRADY-V2R4] 6/8 Re-run identical state"
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw "real Altrady idempotency cycle failed" }

    Write-Host "[REAL-ALTRADY-V2R4] 7/8 Verify exactly-once behavior"
    & $python $helper "verify-idempotent" "--root" $caseRoot
    if ($LASTEXITCODE -ne 0) { throw "real Altrady idempotency verification failed" }

    Write-Host "[REAL-ALTRADY-V2R4] 8/8 Summary"
    Write-Host ""
    Write-Host "=== REAL ALTRADY -> KRAKEN -> V2R4 PAPER RECHECK SMOKE ==="
    Write-Host ("Branch SHA: " + $branchSha)
    Write-Host ("Real event id: " + $fixture.real_event_id)
    Write-Host ("Real event symbol: " + $fixture.real_event_symbol)
    Write-Host ("Real event age: " + $fixture.real_event_age_minutes + " min")
    Write-Host ("Mapped Kraken pair: " + $fixture.pair + " | altname=" + $fixture.altname)
    Write-Host ("Kraken canary: " + $hb.status + " | age_sec=" + $hbAge)
    Write-Host ("Paper recheck decision: " + $summary.decision)
    Write-Host ("Trigger to recheck start: " + $summary.trigger_to_recheck_start_s + " s")
    Write-Host "Safety: TEMP-ISOLATED / PAPER ONLY / KRAKEN CONDITION TRUTH / ALTRADY WAKEUP ONLY / NO ORDER API / NO REAL-MONEY ACTION"
    Write-Host "Result: PASS"
    Write-Host "=== END ==="
  } finally {
    Pop-Location
  }
} finally {
  Push-Location $repo
  try {
    if (Test-Path $worktree) {
      & git worktree remove --force $worktree 2>$null
    }
    & git worktree prune
  } finally {
    Pop-Location
  }
  Remove-Item -LiteralPath $caseRoot -Recurse -Force -ErrorAction SilentlyContinue
}
