param(
  [string]$TradingRoot = "",
  [switch]$Execute,
  [string]$Confirm = ""
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($TradingRoot)) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { $HOME }
  if ([string]::IsNullOrWhiteSpace($homeRoot)) { throw "Unable to resolve user home directory." }
  $TradingRoot = Join-Path $homeRoot "Trading"
}

$ExpectedConfirm="SYNC_AND_RUN_V3_NEXT_PHYSICAL_GATES"
$repo=Join-Path $TradingRoot "Repos\kraken-eur-scanner"
$bundle=Join-Path $repo "tools\run-minipc-v3-next-physical-gates.ps1"

$plan=[ordered]@{
  kind="V3_NEXT_PHYSICAL_GATES_SAFE_SYNC_V1"
  status=$(if($Execute){"READY_TO_EXECUTE"}else{"PLAN_ONLY"})
  execute=[bool]$Execute
  sync_contract=@(
    "require existing local repo",
    "require clean working tree",
    "git fetch origin main",
    "require local HEAD is ancestor of origin/main",
    "fast-forward only to origin/main",
    "invoke confirmed V3 physical-gate bundle"
  )
  destructive_git_operations=$false
  force_reset=$false
  rebase=$false
  strategy_mutation=$false
  orders=$false
  real_money_actions=$false
}
if(-not $Execute){
  $plan|ConvertTo-Json -Depth 6
  exit 0
}
if($Confirm -ne $ExpectedConfirm){
  throw "Execution blocked. Re-run with -Confirm $ExpectedConfirm"
}
if(-not(Test-Path -LiteralPath $repo)){throw "Repo missing: $repo"}

Push-Location $repo
try{
  $dirty=git status --porcelain
  if($LASTEXITCODE -ne 0){throw "git status failed"}
  if($dirty){throw "Working tree is not clean; refusing sync."}

  $before=(git rev-parse HEAD).Trim()
  if($LASTEXITCODE -ne 0){throw "git rev-parse HEAD failed"}

  git fetch origin main
  if($LASTEXITCODE -ne 0){throw "git fetch origin main failed"}

  git merge-base --is-ancestor HEAD origin/main
  if($LASTEXITCODE -ne 0){
    throw "Local HEAD is not an ancestor of origin/main; refusing non-fast-forward sync."
  }

  git merge --ff-only origin/main
  if($LASTEXITCODE -ne 0){throw "fast-forward merge failed"}

  $after=(git rev-parse HEAD).Trim()
  if($LASTEXITCODE -ne 0){throw "git rev-parse after sync failed"}

  $dirtyAfter=git status --porcelain
  if($LASTEXITCODE -ne 0 -or $dirtyAfter){throw "Repo not clean after fast-forward sync"}

  $bundle=Join-Path $repo "tools\run-minipc-v3-next-physical-gates.ps1"
  if(-not(Test-Path -LiteralPath $bundle)){throw "Physical gate bundle missing after sync: $bundle"}

  Write-Host "=== SAFE SYNC COMPLETE ==="
  Write-Host ("Before: "+$before)
  Write-Host ("After:  "+$after)
  Write-Host "Starting confirmed V3 physical gates..."

  & $bundle -TradingRoot $TradingRoot -Execute -Confirm "RUN_V3_NEXT_PHYSICAL_GATES"
  if($LASTEXITCODE -ne 0){throw "V3 physical gate bundle failed"}
} finally {
  Pop-Location
}

Write-Host "=== SAFE SYNC + V3 PHYSICAL GATES COMPLETE ==="
Write-Host "No force/reset/rebase / no strategy mutation / no orders / no real-money action"
