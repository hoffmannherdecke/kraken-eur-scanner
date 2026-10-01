param(
  [switch]$Execute,
  [string]$Confirm = "",
  [string]$TradingRoot = (Join-Path $env:USERPROFILE "Trading"),
  [string]$V2R4Branch = "prep/v2r4-refresh-20261001"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ExpectedConfirm = "SYNC_VERIFY_V2R4_READINESS"
$repo = Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$watchdogSmoke = Join-Path $repo "tools\minipc-watchdog-effectiveness-smoke.ps1"
$v2r4Preflight = Join-Path $repo "tools\minipc-v2r4-preflight-smoke.ps1"
$restoreSmoke = Join-Path $repo "tools\minipc-restore-smoke.ps1"

$plan = [ordered]@{
  kind = "MINIPC_V2R4_READINESS_SYNC_V1"
  status = $(if ($Execute) { "READY_TO_EXECUTE" } else { "PLAN_ONLY" })
  execute = [bool]$Execute
  trading_root = $TradingRoot
  repo = $repo
  required_branch = "main"
  v2r4_candidate_branch = $V2R4Branch
  steps = @(
    "verify clean main working tree",
    "fetch origin/main and fast-forward-only pull",
    "run watchdog effectiveness smoke",
    "run isolated V2R4 preflight against refreshed candidate branch",
    "run latest backup restore smoke"
  )
  guardrails = [ordered]@{
    strategy_change = $false
    paper_activation = $false
    evaluator_activation = $false
    private_kraken_api = $false
    orders = $false
    real_money_actions = $false
  }
}

if (-not $Execute) {
  $plan | ConvertTo-Json -Depth 8
  exit 0
}

if ($Confirm -ne $ExpectedConfirm) {
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}

foreach ($p in @($repo,$watchdogSmoke,$v2r4Preflight,$restoreSmoke)) {
  if (-not (Test-Path $p)) { throw "Required path missing: $p" }
}

Push-Location $repo
try {
  $branch = (& git branch --show-current).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Unable to read current git branch." }
  if ($branch -ne "main") { throw "Repository must be on main; current branch=$branch" }

  $dirty = @(& git status --porcelain)
  if ($LASTEXITCODE -ne 0) { throw "git status failed" }
  if ($dirty.Count -gt 0) {
    throw "Working tree is not clean. Stop before pulling."
  }

  $beforeHead = (& git rev-parse HEAD).Trim()

  Write-Host "[READINESS-SYNC] 1/4 Fetch + fast-forward-only pull current main"
  & git fetch origin main
  if ($LASTEXITCODE -ne 0) { throw "git fetch origin main failed" }
  $behindBefore = [int]((& git rev-list --count "HEAD..origin/main").Trim())
  & git pull --ff-only origin main
  if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed" }
  $afterHead = (& git rev-parse HEAD).Trim()

  Write-Host "[READINESS-SYNC] 2/4 Watchdog effectiveness"
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $watchdogSmoke -TradingRoot $TradingRoot
  if ($LASTEXITCODE -ne 0) { throw "Watchdog effectiveness smoke failed" }

  Write-Host "[READINESS-SYNC] 3/4 Isolated V2R4 candidate preflight"
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $v2r4Preflight -TradingRoot $TradingRoot -Branch $V2R4Branch
  if ($LASTEXITCODE -ne 0) { throw "V2R4 preflight smoke failed" }

  Write-Host "[READINESS-SYNC] 4/4 Backup restore smoke"
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $restoreSmoke -TradingRoot $TradingRoot
  if ($LASTEXITCODE -ne 0) { throw "Backup restore smoke failed" }

  $summary = [ordered]@{
    kind = "MINIPC_V2R4_READINESS_SYNC_V1"
    status = "PASS"
    before_head = $beforeHead
    after_head = $afterHead
    commits_behind_before_pull = $behindBefore
    branch = $branch
    v2r4_candidate_branch = $V2R4Branch
    watchdog_effectiveness = "PASS"
    v2r4_preflight = "PASS"
    backup_restore = "PASS"
    guardrails = $plan.guardrails
    next_gate = "WAIT_FOR_V2R3_CLEAN_SERIES_MATURITY_THEN_MANUAL_RELEASE_REVIEW"
  }

  Write-Host ""
  Write-Host "=== MINI-PC V2R4 READINESS SYNC SUMMARY ==="
  $summary | ConvertTo-Json -Depth 8
  Write-Host "=== END ==="
} finally {
  Pop-Location
}
