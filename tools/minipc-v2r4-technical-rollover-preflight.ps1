param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading')
)
# STRICT READ-ONLY: investigate a technically impaired frozen PAPER series.
# No restart, installation, secrets read, file write, Git pull, or cloud action.
$ErrorActionPreference = 'Stop'
$repo = Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$app = Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
$h3app = Join-Path $TradingRoot 'Runtime\v3-h3-shadow-001'
$expectedSeries = 'PAPER-V2R4-20261007T184255Z'
$expectedOldRelease = '3c6729a6c548d169f56a97f07f75892f37211636'
$checks = [ordered]@{}
$details = [ordered]@{
  mode='READ_ONLY_PREFLIGHT'
  old_series=$expectedSeries
  paper_only=$null
  real_money_actions_enabled=$null
  local_repo_head=$null
  old_release_sha=$null
  old_code_sha256=$null
  new_code_sha256=$null
  strategy_fingerprint_sha256=$null
  frozen_bundle_fingerprint_sha256=$null
  h3_shadow_id=$null
  h3_baseline=$null
  h3_config_sha256=$null
  h3_local_evidence_files=0
  old_paper_decision_files=0
  old_paper_position_files=0
  candidate_task_state=$null
  h3_task_state=$null
  checks=$checks
}
try {
  $required=@(
    $repo,
    (Join-Path $app 'paper_runtime_control.json'),
    (Join-Path $app 'v2r4-paper-local-runtime.py'),
    (Join-Path $repo 'tools\v2r4-paper-local-runtime.py'),
    (Join-Path $repo 'market_data\universe.py')
  )
  $checks['expected_files_exist']=@($required | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -eq 0
  if (-not $checks['expected_files_exist']) { throw 'Missing prerequisite; no changes made' }
  $control=Get-Content (Join-Path $app 'paper_runtime_control.json') -Raw | ConvertFrom-Json
  $details.paper_only=$control.paper_only
  $details.real_money_actions_enabled=$control.real_money_actions_enabled
  $details.old_release_sha=[string]$control.release_repo_sha
  $details.strategy_fingerprint_sha256=[string]$control.strategy_fingerprint_sha256
  $details.frozen_bundle_fingerprint_sha256=[string]$control.runtime_bundle_fingerprint_sha256
  $checks['exact_frozen_series']=([string]$control.series_id -eq $expectedSeries)
  $checks['old_release_pinned']=([string]$control.release_repo_sha -eq $expectedOldRelease)
  $checks['paper_only_no_real_money']=($control.paper_only -eq $true -and $control.real_money_actions_enabled -eq $false)
  $checks['first_series_sizing']=([double]$control.scout_notional_eur -eq 50 -and [double]$control.stage2_notional_eur -eq 50)
  $checks['strategy_config_consistent']=([string]$control.strategy_revision -eq 'V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION')
  $details.old_code_sha256=(Get-FileHash (Join-Path $app 'v2r4-paper-local-runtime.py') -Algorithm SHA256).Hash.ToLowerInvariant()
  $details.new_code_sha256=(Get-FileHash (Join-Path $repo 'tools\v2r4-paper-local-runtime.py') -Algorithm SHA256).Hash.ToLowerInvariant()
  $checks['new_fix_differs']=($details.old_code_sha256 -ne $details.new_code_sha256)
  $checks['new_canonical_library_present']=Test-Path (Join-Path $repo 'market_data\universe.py')
  $details.local_repo_head=(git -C $repo rev-parse HEAD).Trim()
  $checks['repo_main']=((git -C $repo branch --show-current).Trim() -eq 'main')
  $checks['repo_clean']=(@(git -C $repo status --porcelain).Count -eq 0)
  $checks['frozen_h3_bundle_present']=Test-Path (Join-Path $h3app 'h3-control.json')
  if ($checks['frozen_h3_bundle_present']) {
    $h3=Get-Content (Join-Path $h3app 'h3-control.json') -Raw | ConvertFrom-Json
    $details.h3_shadow_id=[string]$h3.shadow_candidate_id
    $details.h3_baseline=[string]$h3.baseline_series_id
    $details.h3_config_sha256=[string]$h3.frozen_config_sha256
    $checks['h3_pinned_to_old_baseline']=([string]$h3.shadow_candidate_id -eq 'V3-H3-SHADOW-001' -and [string]$h3.baseline_series_id -eq $expectedSeries)
  } else { $checks['h3_pinned_to_old_baseline']=$false }
  $h3files=Join-Path $h3app 'evidence'
  if (Test-Path $h3files) { $details.h3_local_evidence_files=@(Get-ChildItem $h3files -Filter '*.json' -File).Count }
  $decisionDir=Join-Path $app 'paper_decisions'
  $positionDir=Join-Path $app 'paper_positions'
  if (Test-Path $decisionDir) { $details.old_paper_decision_files=@(Get-ChildItem $decisionDir -Filter '*.json' -File).Count }
  if (Test-Path $positionDir) { $details.old_paper_position_files=@(Get-ChildItem $positionDir -Filter '*.json' -File).Count }
  foreach ($name in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V3H3Shadow001')) {
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($name -eq 'CryptoMiniPC-V2R4PaperCandidates') {
      $details.candidate_task_state=if ($task) { [string]$task.State } else { 'MISSING' }
      $checks['candidate_task_targets_old_app']=($task -and (($task.Actions.Arguments -join ' ') -like ('*'+$app+'*')))
    } else {
      $details.h3_task_state=if ($task) { [string]$task.State } else { 'MISSING' }
      $checks['h3_task_exists']=($null -ne $task)
    }
  }
  $failed=@($checks.Keys | Where-Object { $checks[$_] -ne $true })
  $details['status']=if ($failed.Count -eq 0) { 'PREFLIGHT_PASS_NO_MUTATION' } else { 'PREFLIGHT_BLOCKED_NO_MUTATION' }
  $details['failed_checks']=$failed
} catch {
  $details['status']='PREFLIGHT_BLOCKED_NO_MUTATION'
  $details['failed_checks']=@('READ_ERROR')
  $details['read_error_type']=$_.Exception.GetType().Name
  $details['read_error_message']=$_.Exception.Message
}
Write-Output ($details | ConvertTo-Json -Depth 8)
