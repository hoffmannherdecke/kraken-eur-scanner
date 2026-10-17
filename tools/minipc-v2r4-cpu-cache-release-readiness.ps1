param(
  [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading')
)
# Issue353 CPU-cache SOURCE-ONLY gate. No -Execute/-Stage/-Commit mode exists.
# Pure read-only evidence: never stops, registers, starts or changes a task.
# PASS means source compatibility preconditions, NOT production release approval.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath($TradingRoot)
$source=Join-Path $root 'Staging\issue353-source-c8f37da'
$stage=Join-Path $root 'Staging\v2r4-cache-inert-c8f37da86531'
$app=Join-Path $root 'Runtime\v2r4-paper-stage-d8b35a8ec2e6'
$wait=Join-Path $root 'Staging\v2r4-wait-pr326-isolated-c660ebb87a39'
$state=Join-Path $root 'State'
$pin='c8f37da865314ac91d36c786b66d107aad4a28d1'
$release='d8b35a8ec2e6f392f219b1c36cad95f3ad629b64'
$series='PAPER-V2R4-20261009T110135Z'
$bundle='604d5d460f17c4548b2d69db8ceb2f5368e702a6d51860ce8916e2e7fbba5b30'
$strategy='55c15f6c0735e524409594ece173ab30e4d84eecafefa18b57f8dc9c48cca32c'
$files=[ordered]@{
  'candidate\v2r4-paper-local-runtime.py'='8D62BD0B73F197DCE0EBF2C8398023E46A63800D2063BD30FD2CD60355BC7C6C'
  'wait\v2r4_wait_runtime.py'='880A0BEADC7F777A96BBDD6AA7B05627FCFE16DDCFC1C5E20AFD88C5C4867713'
  'wait\wait_launcher.py'='C5E43D62976BDF2079A3A0402E57658ABA8A33D427B0CF0D56737565B84DD51D'
  'wait\v2r4_wait_watcher.py'='9EEE3F9CA8E669AD8DA690DA7A2C53E781EE618594783D08A50FCD5623F670BD'
}
$report=[ordered]@{
  kind='V2R4_CPU_CACHE_SOURCE_GATE_V1'
  status='READ_ONLY_GATE_BLOCKED'
  series_id=$series
  candidate_and_lifecycle_shared_source=$true
  pr326_wait_protected=$true
  source_sha=$pin
  mode='READ_ONLY'
  checks=[ordered]@{}
  task_mutations=$false
  runtime_mutations=$false
  production_cache_active='NOT_ESTABLISHED_BY_THIS_GATE'
  next='MANUAL_RELEASE_COORDINATION_AND_ROLLBACK_PROOF_REQUIRED'
}
function Need([bool]$Ok,[string]$Code) {
  $report.checks[$Code]=$Ok
  if(-not $Ok) { throw ('GATE_'+$Code) }
}
function SHA([string]$Path) {
  Need (Test-Path -LiteralPath $Path -PathType Leaf) 'FILE_PRESENT'
  $item=Get-Item -LiteralPath $Path -Force
  Need (-not [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) 'NO_LINKED_FILE'
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToUpperInvariant()
}
function CheckTask([string]$Name,[string]$Entrypoint,[string]$Mode) {
  $task=Get-ScheduledTask -TaskName $Name -ErrorAction Stop
  Need (@($task.Actions).Count -eq 1) 'ONE_TASK_ACTION'
  Need ([string]$task.State -eq 'Running') 'TASK_RUNNING'
  Need ([string]$task.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')) 'TASK_SYSTEM'
  $argsText=([string]$task.Actions[0].Arguments).Replace('/','\')
  Need ($argsText.IndexOf($Entrypoint,[StringComparison]::OrdinalIgnoreCase) -ge 0) 'TASK_PINNED_ENTRYPOINT'
  if($Mode) {
    $match=[regex]::Match($argsText,'(?i)--mode\W+(candidates|lifecycle)')
    Need ($match.Success -and $match.Groups[1].Value -ieq $Mode) 'TASK_EXPECTED_MODE'
    Need ([string]$task.Settings.MultipleInstances -eq 'IgnoreNew') 'TASK_IGNORE_NEW'
  }
}
try {
  Need (Test-Path -LiteralPath $root -PathType Container) 'TRADING_ROOT_EXISTS'
  Need (Test-Path -LiteralPath $source -PathType Container) 'INDEPENDENT_SOURCE_EXISTS'
  $head=@(& git -C $source rev-parse HEAD 2>$null)
  Need ($LASTEXITCODE -eq 0 -and $head.Count -eq 1 -and $head[0].Trim() -ceq $pin) 'EXACT_SOURCE_PIN'
  $changed=@(& git -C $source status --porcelain --untracked-files=normal 2>$null | Where-Object { $_ })
  Need ($LASTEXITCODE -eq 0 -and $changed.Count -eq 0) 'SOURCE_CLEAN'
  Need ((SHA (Join-Path $app 'v2r4-paper-local-runtime.py')) -ceq '8371CAB2D7D18F9651E604DBAB88768F77B2DFF5EB88565122858F6428DC50D0') 'ORIGINAL_CANDIDATE_SHA'
  Need ((SHA (Join-Path $wait 'v2r4_wait_runtime.py')) -ceq 'C84533E1042C9D89D6F6EDC31DD22DE6DD3AB3B7AAE2B202EF344495A72BA6A2') 'ORIGINAL_WAIT_SHA'
  Need ((SHA (Join-Path $wait 'wait_launcher.py')) -ceq $files['wait\wait_launcher.py']) 'ORIGINAL_LAUNCHER_SHA'
  Need ((SHA (Join-Path $wait 'v2r4_wait_watcher.py')) -ceq $files['wait\v2r4_wait_watcher.py']) 'ORIGINAL_WATCHER_SHA'

  $ctrl=Get-Content -LiteralPath (Join-Path $app 'paper_runtime_control.json') -Raw -ErrorAction Stop | ConvertFrom-Json
  Need ([string]$ctrl.series_id -ceq $series) 'ACTIVE_SERIES'
  Need ([string]$ctrl.release_repo_sha -ceq $release) 'ACTIVE_RELEASE'
  Need ([string]$ctrl.runtime_bundle_fingerprint_sha256 -ceq $bundle) 'ACTIVE_BUNDLE'
  Need ([string]$ctrl.strategy_fingerprint_sha256 -ceq $strategy) 'ACTIVE_STRATEGY'
  Need ($ctrl.enabled -eq $true -and $ctrl.paper_only -eq $true -and $ctrl.real_money_actions_enabled -eq $false -and [double]$ctrl.scout_notional_eur -eq 50 -and [double]$ctrl.stage2_notional_eur -eq 50) 'PAPER_SAFETY_FLAGS'

  $manifest=Get-Content -LiteralPath (Join-Path $stage 'cpu-cache-stage-manifest.json') -Raw -ErrorAction Stop | ConvertFrom-Json
  Need ($manifest.kind -ceq 'V2R4_CPU_CACHE_INERT_STAGE_V1' -and $manifest.status -ceq 'STAGED_INERT_NOT_EXECUTED' -and $manifest.source_git_sha -ceq $pin -and $manifest.no_control_or_keys -eq $true -and $manifest.task_mutations -eq $false -and $manifest.runtime_activated -eq $false) 'INERT_MANIFEST'
  $manifestMap=@{}
  foreach($entry in @($manifest.files)) {
    Need (-not $manifestMap.ContainsKey([string]$entry.file)) 'UNIQUE_MANIFEST_FILE'
    $manifestMap[[string]$entry.file]=[string]$entry.sha256
  }
  Need ($manifestMap.Count -eq 5) 'FIVE_PINNED_STAGE_FILES'
  foreach($relative in $files.Keys) {
    Need ($manifestMap.ContainsKey($relative) -and $manifestMap[$relative].ToUpperInvariant() -ceq $files[$relative]) 'MANIFEST_HASH_PIN'
    Need ((SHA (Join-Path $stage $relative)) -ceq $files[$relative]) 'INERT_COPY_HASH_PIN'
  }
  $budget='wait\kraken_public_budget.py'
  Need ($manifestMap.ContainsKey($budget) -and [string]$manifestMap[$budget] -match '^[a-fA-F0-9]{64}$') 'ORIGINAL_PUBLIC_BUDGET_PIN'
  Need ((SHA (Join-Path $stage $budget)) -ceq $manifestMap[$budget].ToUpperInvariant()) 'BUDGET_MANIFEST_INTEGRITY'
  Need ((SHA (Join-Path $wait 'kraken_public_budget.py')) -ceq $manifestMap[$budget].ToUpperInvariant()) 'ORIGINAL_PUBLIC_BUDGET_INTEGRITY'
  foreach($name in @('v2r4-technical-cutover-maintenance.json','v3-experimental-paper-old-intake-fence.json')) {
    Need (-not (Test-Path -LiteralPath (Join-Path $state $name))) 'NO_RELEASE_MARKER'
  }
  CheckTask 'CryptoMiniPC-V2R4PaperCandidates' (Join-Path $app 'v2r4-paper-local-runtime.py') 'candidates'
  CheckTask 'CryptoMiniPC-V2R4PaperLifecycle' (Join-Path $app 'v2r4-paper-local-runtime.py') 'lifecycle'
  CheckTask 'CryptoMiniPC-V2R4PaperWait' (Join-Path $wait 'wait_launcher.py') ''
  $sup=Get-Content -LiteralPath (Join-Path $state 'minipc-runtime-supervisor.json') -Raw -ErrorAction Stop | ConvertFrom-Json
  Need ($sup.status -eq 'HEALTHY' -and $sup.maintenance.mode -eq 'NONE' -and $sup.v3_paper_old_intake_fence.mode -eq 'NONE') 'SUPERVISOR_HEALTHY_NO_FENCE'
  $report.status='READ_ONLY_SOURCE_GATE_PASS_MANUAL_RELEASE_BLOCKED'
} catch {
  # Fail closed without printing source paths, task command lines or secrets.
  $code=[string]$_.Exception.Message
  $report.status='READ_ONLY_GATE_BLOCKED'
  $report.reason=if($code -match '^GATE_[A-Z0-9_]+$') {$code} else {'UNEXPECTED_READ_ERROR'}
}
$report | ConvertTo-Json -Depth 8
