param(
  [string]$TradingRoot = (Join-Path $env:USERPROFILE 'Trading'),
  [string]$SuccessorReleaseSha = ''
)
# READ ONLY. No network requests, task changes, cloud mutation, archive or restart.
# Do not mistake READY_TO_REVIEW for cutover/production approval.
$ErrorActionPreference = 'Stop'
$oldId='PAPER-V2R4-20261007T184255Z'
$newSha=$SuccessorReleaseSha.ToLowerInvariant()
# The 08.10 inert stage was preparation only. Never quietly use its older
# source SHA after the final isolation/rotation release was reviewed.
if($newSha -notmatch '^[0-9a-f]{40}$'){
  Write-Output ('{"kind":"V2R4_TECHNICAL_CUTOVER_READINESS_V1","mode":"READ_ONLY","status":"READ_ONLY_GATE_BLOCKED","reason":"EXPLICIT_REVIEWED_SUCCESSOR_SHA_REQUIRED"}')
  exit 2
}
$oldSha='3c6729a6c548d169f56a97f07f75892f37211636'
$oldApp=Join-Path $TradingRoot 'Runtime\v2r4-paper-app'
$stage=Join-Path $TradingRoot ('Runtime\v2r4-paper-stage-'+$newSha.Substring(0,12))
$stateDir=Join-Path $TradingRoot 'State'
$sourceFiles=@(
  'paper_evaluator\evaluate.py','paper_evaluator\v2r4_trigger_contract.py',
  'paper_evaluator\v2r4_trigger_plan.py','paper_evaluator\v2r4_wait_runtime.py',
  'paper_evaluator\v2r4_local_recheck.py','paper_position_tracker.py',
  'paper_followup.py','tools\v2r4-paper-local-runtime.py',
  'tools\v2r4-paper-cloud-sync.py','market_data\__init__.py',
  'market_data\universe.py'
)
function Fingerprint-Stage {
  $sb=[System.Text.StringBuilder]::new()
  foreach($rel in ($sourceFiles | Sort-Object)){
    $dest=if($rel.StartsWith('tools\')){$rel.Substring(6)}else{$rel}
    $path=Join-Path $stage $dest
    if(-not(Test-Path -LiteralPath $path)){throw ('Stage input missing: '+$rel)}
    $hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    [void]$sb.Append($rel.Replace('\','/')+':'+$hash+[Environment]::NewLine)
  }
  $s=[Security.Cryptography.SHA256]::Create()
  try { return ([BitConverter]::ToString($s.ComputeHash([Text.Encoding]::UTF8.GetBytes($sb.ToString())))).Replace('-','').ToLowerInvariant() }
  finally{$s.Dispose()}
}
function Add-Check([string]$Name,[bool]$Pass,[string]$Detail=''){
  $checks[$Name]=$Pass
  if($Detail){$details[$Name]=$Detail}
}
$checks=[ordered]@{}
$details=[ordered]@{}
$result=[ordered]@{
  kind='V2R4_TECHNICAL_CUTOVER_READINESS_V1'
  mode='READ_ONLY'
  checked_at_utc=[datetime]::UtcNow.ToString('o')
  status='BLOCKED'
  source_repo_sha=$newSha
  predecessor_series_id=$oldId
  old_decision_file_count=$null
  old_position_file_count=$null
  old_candidate_id_count=$null
  old_candidate_ids_sha256=$null
  prepared_bundle_sha256=$null
  staged_manifest_sha256=$null
  checks=$checks
  details=$details
}
try {
  $manifestFile=Join-Path $stage 'technical-stage-manifest.json'
  $oldControlFile=Join-Path $oldApp 'paper_runtime_control.json'
  Add-Check 'stage_and_old_control_exist' ((Test-Path $manifestFile) -and (Test-Path $oldControlFile))
  if(-not $checks['stage_and_old_control_exist']){throw 'Missing old control or inert stage manifest'}
  $manifest=Get-Content $manifestFile -Raw | ConvertFrom-Json
  $old=Get-Content $oldControlFile -Raw | ConvertFrom-Json
  Add-Check 'old_exact_series_release' ($old.series_id -eq $oldId -and $old.release_repo_sha -eq $oldSha)
  Add-Check 'old_paper_only' ($old.paper_only -eq $true -and $old.real_money_actions_enabled -eq $false)
  Add-Check 'same_strategy_50_50' ([double]$old.scout_notional_eur -eq 50 -and [double]$old.stage2_notional_eur -eq 50)
  Add-Check 'stage_sha_pinned' ($manifest.source_repo_sha -eq $newSha -and $manifest.predecessor_series_id -eq $oldId)
  Add-Check 'stage_not_activated' ($manifest.status -eq 'STAGED_INERT_NO_ACTIVATION' -and
    $manifest.cloud_activation_performed -eq $false -and $manifest.h3_rebinding_performed -eq $false -and
    -not (Test-Path (Join-Path $stage 'paper_runtime_control.json')))
  $hash=Fingerprint-Stage
  $result.prepared_bundle_sha256=$hash
  $result.staged_manifest_sha256=(Get-FileHash $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant()
  Add-Check 'staged_code_hash_matches_manifest' ($hash -eq $manifest.proposed_runtime_bundle_fingerprint_sha256)
  Add-Check 'strategy_hash_matches_stage' ([string]$manifest.strategy_fingerprint_sha256 -eq [string]$old.strategy_fingerprint_sha256)
  foreach($name in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait',
       'CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync',
       'CryptoMiniPC-V3H3Shadow001','CryptoMiniPC-RuntimeSupervisor')){
    $task=Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    Add-Check ('task_present_'+$name) ($null -ne $task) ($(if($task){[string]$task.State}else{'MISSING'}))
  }
  $decisionDir=Join-Path $oldApp 'paper_decisions'
  $positionDir=Join-Path $oldApp 'paper_positions'
  $decisions=@(Get-ChildItem $decisionDir -Filter '*.json' -File -ErrorAction Stop)
  $positions=@(Get-ChildItem $positionDir -Filter '*.json' -File -ErrorAction Stop)
  $result.old_decision_file_count=$decisions.Count
  $result.old_position_file_count=$positions.Count
  $ids=[System.Collections.Generic.List[string]]::new()
  $parseFailures=0
  foreach($file in $decisions){
    try{
      $row=Get-Content $file.FullName -Raw | ConvertFrom-Json
      if($row.series_id -eq $oldId -and -not [string]::IsNullOrWhiteSpace([string]$row.candidate_id)){
        $ids.Add([string]$row.candidate_id)
      }else{$parseFailures++}
    }catch{$parseFailures++}
  }
  [string[]]$ordered=@($ids.ToArray())
  [Array]::Sort($ordered,[StringComparer]::Ordinal)
  $unique=[System.Collections.Generic.List[string]]::new()
  foreach($item in $ordered){
    if($unique.Count -eq 0 -or
       -not [StringComparer]::Ordinal.Equals($unique[$unique.Count-1],$item)){
      $unique.Add($item)
    }
  }
  $result.old_candidate_id_count=$unique.Count
  $canonical=$unique.ToArray() -join "`n"
  $sha=[Security.Cryptography.SHA256]::Create()
  try{$result.old_candidate_ids_sha256=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-','').ToLowerInvariant()}
  finally{$sha.Dispose()}
  Add-Check 'old_local_candidate_ids_clean' ($parseFailures -eq 0 -and $ids.Count -eq $unique.Count) ("invalid_files=$parseFailures")
  $h3=Get-Content (Join-Path $TradingRoot 'Runtime\v3-h3-shadow-001\h3-control.json') -Raw | ConvertFrom-Json
  Add-Check 'h3_001_baseline_still_old' ($h3.shadow_candidate_id -eq 'V3-H3-SHADOW-001' -and $h3.baseline_series_id -eq $oldId)
  $disk=Get-Item $oldApp
  $drive=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($disk.FullName))
  Add-Check 'snapshot_free_disk_at_least_2gb' ($drive.AvailableFreeSpace -ge 2GB) ("free_bytes=$($drive.AvailableFreeSpace)")
  $result.status=if(@($checks.Keys | Where-Object{-not $checks[$_]}).Count -eq 0){'READ_ONLY_GATE_PASS_NOT_CUTOVER'}else{'READ_ONLY_GATE_BLOCKED'}
}catch{
  $result.status='READ_ONLY_GATE_BLOCKED'
  $details.read_error=$_.Exception.Message
}
$result['failed_checks']=@($checks.Keys | Where-Object{-not $checks[$_]})
Write-Output ($result | ConvertTo-Json -Depth 7)
