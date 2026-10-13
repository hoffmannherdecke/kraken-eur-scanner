param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading')
)
# READ ONLY physical V3 single-writer handoff preflight.
# Does NOT start a task, import Python, alter repository, write to disk,
# access secret bytes, sync Cloud, call OpenAI or change an active Paper series.
$ErrorActionPreference='Stop'
$now=(Get-Date).ToUniversalTime()
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$runtime=Join-Path $TradingRoot 'Runtime'
$v3=Join-Path $TradingRoot 'Research\V3Paper'
$state=Join-Path $TradingRoot 'State'
$planPath=Join-Path $state 'v3-canary-observer-28h-plan.json'
$heartbeatPath=Join-Path $state 'v3-canary-observer-28h-heartbeat.json'
$journal=Join-Path $v3 'journal'
$ackPath=Join-Path $v3 'cloud-ack.json'
$oldSeries='PAPER-V2R4-20261009T110135Z'
$taskName='CryptoMiniPC-V3CanaryObservation28h'

$repoPresent=Test-Path -LiteralPath $repo -PathType Container
$existingExperimentalGateModule=Join-Path $repo 'tools\v3_experimental_paper_technical_gate.py'
$existingExperimentalGatePresent=(Test-Path -LiteralPath $existingExperimentalGateModule -PathType Leaf)
$modules=@(
 'paper_evaluator\v3_paper_shared_candidate_intake_plan_v1.py',
 'paper_evaluator\v3_paper_existing_owner_source_bridge_v1.py',
 'paper_evaluator\v3_paper_intake_receipt_stage_v1.py',
 'paper_evaluator\v3_paper_minipc_one_candidate_v1.py',
 'paper_evaluator\v3_paper_cloud_receipt_sync_v1.py'
)
$missingModules=@($modules|Where-Object{
 -not(Test-Path -LiteralPath (Join-Path $repo $_) -PathType Leaf)
})
$oldApps=@()
if(Test-Path -LiteralPath $runtime -PathType Container){
 foreach($app in @(Get-ChildItem -LiteralPath $runtime -Directory -ErrorAction Stop)){
  $controlFile=Join-Path $app.FullName 'paper_runtime_control.json'
  if(-not(Test-Path -LiteralPath $controlFile -PathType Leaf)){continue}
  try{
   $control=Get-Content -LiteralPath $controlFile -Raw|ConvertFrom-Json
   if($control.series_id -eq $oldSeries){
    $oldApps+=@([pscustomobject]@{
     app=$app.FullName
     paper_only=($control.paper_only -eq $true)
     no_real_money=($control.real_money_actions_enabled -eq $false)
     queue=(Join-Path $app.FullName 'handoff_queue')
    })
   }
  }catch{continue}
 }
}
$handoffCount=0
$freshCount=0
$latestAgeSec=$null
$queueHealthy=$false
if($oldApps.Count -eq 1){
 $queue=$oldApps[0].queue
 $queueHealthy=(Test-Path -LiteralPath $queue -PathType Container)
 if($queueHealthy){
  $handoffs=@(Get-ChildItem -LiteralPath $queue -Filter '*.json' -File |
                 Sort-Object LastWriteTimeUtc -Descending |
                 Select-Object -First 100)
  $handoffCount=$handoffs.Count
  foreach($file in $handoffs){
   try{
    $item=Get-Content -LiteralPath $file.FullName -Raw|ConvertFrom-Json
    if($item.kind -ne 'CANONICAL_CANDIDATE_HANDOFF_V1' -or
       $item.action -ne 'REVIEW_ONLY_NOT_ORDER' -or
       -not([string]$item.pair).EndsWith('/EUR') -or
       [string]::IsNullOrWhiteSpace([string]$item.candidate_id)){continue}
    $at=[datetime]::Parse([string]$item.event_time_utc).ToUniversalTime()
    $seconds=($now-$at).TotalSeconds
    if($null -eq $latestAgeSec -or $seconds -lt $latestAgeSec){
     $latestAgeSec=[math]::Round($seconds,0)
    }
    if($seconds -ge 0 -and $seconds -le 600){$freshCount++}
   }catch{continue}
  }
 }
}
$plan=$null
if(Test-Path -LiteralPath $planPath -PathType Leaf){
 try{$plan=Get-Content -LiteralPath $planPath -Raw|ConvertFrom-Json}catch{}
}
$heartbeat=$null
if(Test-Path -LiteralPath $heartbeatPath -PathType Leaf){
 try{$heartbeat=Get-Content -LiteralPath $heartbeatPath -Raw|ConvertFrom-Json}catch{}
}
$taskState='NOT_FOUND'
try{
 $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
 if($null -ne $task){$taskState=[string]$task.State}
}catch{$taskState='UNAVAILABLE_TO_READ'}
# The old host runtime configuration directory is NOT a physical
# Windows-task/sole-writer proof. Read only the four exact existing V2R4
# task identities; never infer a running Paper writer from JSON controls.
$v2r4PaperTasks=@()
foreach($name in @(
 'CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait',
 'CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync'
)){
 $record=[ordered]@{
   task_name=$name
   state='NOT_FOUND'
   last_run_utc=$null
   last_task_result=$null
   evidence='READ_ONLY_WINDOWS_TASK_NOT_ACTIVE_WRITER_FENCE_PROOF'
 }
 try{
   $oldTask=Get-ScheduledTask -TaskName $name -ErrorAction Stop
   $record.state=[string]$oldTask.State
   $oldInfo=$oldTask | Get-ScheduledTaskInfo -ErrorAction Stop
   $record.last_run_utc=$oldInfo.LastRunTime.ToUniversalTime().ToString('o')
   $record.last_task_result=[int]$oldInfo.LastTaskResult
 }catch{
   $record.evidence='NOT_FOUND_OR_TASK_INFO_UNAVAILABLE_NOT_PROVEN'
 }
 $v2r4PaperTasks+=@([pscustomobject]$record)
}
# Task-name matching is a conservative discovery hint only, not a proof that
# an unrecognized V3 writer cannot exist under a different task name.
$v3PaperTaskNames=@()
try{
 $v3PaperTaskNames=@(Get-ScheduledTask -TaskName 'CryptoMiniPC-V3*' -ErrorAction Stop |
   Where-Object { $_.TaskName -ne $taskName -and
     $_.TaskName -match '(Paper|Writer)' } |
   Select-Object -First 20 -ExpandProperty TaskName)
}catch{}
$pinChecked=0
$pinMismatches=@()
if($null -ne $plan){
 foreach($item in @($plan.pinned_file_hashes)){
  $rel=[string]$item.relative_path
  $expected=[string]$item.sha256
  if([string]::IsNullOrWhiteSpace($rel) -or
    $rel -match '(^[\\/]|\.{2}|:)' -or
    $expected -notmatch '^[0-9a-fA-F]{64}$'){
    $pinMismatches+=@('INVALID_PIN_RECORD')
    continue
  }
  $path=Join-Path $repo $rel
  $pinChecked++
  if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
   $pinMismatches+=@($rel)
   continue
  }
  $hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if($hash -ine $expected){$pinMismatches+=@($rel)}
 }
}
$journalCount=0
if(Test-Path -LiteralPath $journal -PathType Container){
 $journalCount=@(Get-ChildItem -LiteralPath $journal -Filter '*.json' -File).Count
}
$ackedCount=$null
if(Test-Path -LiteralPath $ackPath -PathType Leaf){
 try{
  $ack=Get-Content -LiteralPath $ackPath -Raw|ConvertFrom-Json
  $ackedCount=@($ack.acked).Count
 }catch{$ackedCount='UNREADABLE'}
}
$sourceSafe=($oldApps.Count -eq 1 -and $oldApps[0].paper_only -and
             $oldApps[0].no_real_money -and $queueHealthy)
$canarySafe=($null -ne $plan -and
              $plan.kind -eq 'V3_LOCAL_READONLY_CANARY_28H_PLAN_V1' -and
              $plan.v2r4_unchanged -eq $true -and
              $plan.model_http_calls_authorized -eq 0 -and
              $plan.orders -eq $false -and $pinChecked -ge 8 -and
              $pinMismatches.Count -eq 0 -and $taskState -ne 'NOT_FOUND')
$ready=($repoPresent -and $missingModules.Count -eq 0 -and $sourceSafe -and $canarySafe)
[ordered]@{
 kind='V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1'
 checked_at_utc=$now.ToString('o')
 result=if($ready){'LOCAL_INPUT_PATH_READABLE_NO_WRITER_ACTIVATED'}else{'BLOCKED_READONLY_DIAGNOSTIC'}
 repo_exists=$repoPresent
 required_v3_modules_present=($missingModules.Count -eq 0)
 missing_v3_modules=@($missingModules)
 active_v2r4_host_runtime_count=$oldApps.Count
 active_v2r4_host_runtime_count_is_config_files_not_processes=$true
 physical_v2r4_paper_task_readback=$v2r4PaperTasks
 physical_v3_named_paper_task_hints=@($v3PaperTaskNames)
 physical_task_name_scan_cannot_prove_absence_of_other_writers=$true
 pre_cutover_expected_predecessor_series_id=$oldSeries
 physical_v2r4_intake_stop_ack_proven=$false
 physical_single_writer_cutover_dry_run_passed=$false
 cloud_expected_predecessor_cas_verified=$false
 physical_v3_writer_start_ack_proven=$false
 v2r4_runtime_readonly_authority_valid=$sourceSafe
 original_handoff_queue_readable=$queueHealthy
 original_handoff_files_sampled=$handoffCount
 fresh_10m_originals_in_sample=$freshCount
 latest_valid_original_age_seconds=$latestAgeSec
 canary_task_state=$taskState
 canary_deadline_utc=if($null -ne $plan){$plan.until_utc}else{$null}
 canary_manifest_valid_and_pinned=$canarySafe
 experimental_paper_gate_module_present=$existingExperimentalGatePresent
 experimental_paper_requires_prior_profitable_buy=$false
 experimental_paper_requires_six_real_technical_proofs=$true
 experimental_paper_technical_proofs_verified_by_this_local_readonly_check=0
 experimental_paper_release_authorized_by_this_check=$false
 experimental_paper_governance_source='tools/v3_experimental_paper_technical_gate.py'
 experimental_paper_next_gate='SIX_REAL_HOST_OR_CLOUD_E2E_ARTIFACTS_FIXED_API_CAP_SINGLE_WRITER_DRYRUN_EXPLICIT_RELEASE'
 canary_pinned_files_checked=$pinChecked
 canary_pinned_mismatch_count=$pinMismatches.Count
 last_canary_heartbeat_status=if($null -ne $heartbeat){$heartbeat.status}else{'MISSING'}
 last_canary_heartbeat_at_utc=if($null -ne $heartbeat){$heartbeat.checked_at_utc}else{$null}
 existing_v3_local_journal_receipts=$journalCount
 existing_v3_cloud_acks_local=$ackedCount
 real_owner_authentication_proven=$false
 new_v3_writer_started=$false
 new_cloud_sync_performed=$false
 model_http_calls=0
 v2r4_changed=$false
 filesystem_writes=$false
} | ConvertTo-Json -Depth 8
