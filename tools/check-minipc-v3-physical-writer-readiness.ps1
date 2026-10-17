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
# Read-only originalhost module SHA256 inventory, NOT a live release gate.
# No secrets, runtime state, hosted CAS or automatic task changes.
$v3ReleaseSourcePaths=@(
 'paper_evaluator\v3_paper_shared_candidate_intake_plan_v1.py',
 'paper_evaluator\v3_paper_existing_owner_source_bridge_v1.py',
 'paper_evaluator\v3_paper_intake_receipt_stage_v1.py',
 'paper_evaluator\v3_paper_signed_source_journal_stage_v1.py',
 'paper_evaluator\v3_paper_minipc_one_candidate_v1.py',
 'paper_evaluator\v3_paper_minipc_selective_tick_v1.py',
 'paper_evaluator\v3_paper_minipc_closed_1m_capture_v1.py',
 'paper_evaluator\v3_paper_wait_observer_v1.py',
 'paper_evaluator\v3_paper_minipc_followup_v1.py',
 'paper_evaluator\v3_paper_cloud_receipt_sync_v1.py',
 'tools\minipc-runtime-supervisor.ps1',
 'supabase\functions\v3-paper-evidence-relay\index.ts'
)
$v3ReleaseSourceHashes=@(
 foreach($relative in $v3ReleaseSourcePaths) {
  $file=Join-Path $repo $relative
  $digest=$null
  if(Test-Path -LiteralPath $file -PathType Leaf){
   try{$digest=([string](Get-FileHash -LiteralPath $file -Algorithm SHA256 -ErrorAction Stop).Hash).ToLowerInvariant()}
   catch{$digest=$null}
  }
  if($digest -notmatch '^[0-9a-f]{64}$oldApps=@()
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
$taskLastRunUtc=$null
$taskLastResult=$null
$taskFirstTriggerUtc=$null
$taskFinalTriggerUtc=$null
$taskActionMatchesPinnedObserver=$false
$taskScheduleReadbackStatus='NOT_VERIFIED'
try{
 $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
 if($null -ne $task){
  $taskState=[string]$task.State
  # Require exactly one original 28h Windows scheduled-task action/trigger.
  if(@($task.Actions).Count -eq 1 -and @($task.Triggers).Count -eq 1){
   $arguments=[string]$task.Actions[0].Arguments
   $runner=Join-Path $repo 'tools\minipc-v3-bounded-canary-observer-task.ps1'
   $taskActionMatchesPinnedObserver=(
     ([string]$task.Actions[0].Execute -match '(^|[\\/])powershell\.exe$') -and
     $arguments.Contains($runner) -and
     $arguments.Contains('-UntilUtc') -and
     $null -ne $plan -and $arguments.Contains([string]$plan.until_utc)
   )
   $first=[datetime]::Parse([string]$task.Triggers[0].StartBoundary).ToUniversalTime()
   $durationText=[string]$task.Triggers[0].Repetition.Duration
   $duration=[System.Xml.XmlConvert]::ToTimeSpan($durationText)
   if($duration -ne [timespan]::FromHours(28)){throw 'Unexpected Canary repetition duration'}
   $taskFirstTriggerUtc=$first.ToString('o')
   $taskFinalTriggerUtc=$first.Add($duration).ToString('o')
   $taskScheduleReadbackStatus='ONE_ORIGINAL_28H_TRIGGER_READ'
  }else{
   $taskScheduleReadbackStatus='MISSING_OR_MULTIPLE_SCHEDULE_ACTIONS_OR_TRIGGERS'
  }
  $taskInfo=$task|Get-ScheduledTaskInfo -ErrorAction Stop
  if($taskInfo.LastRunTime -gt [datetime]::MinValue){
   $taskLastRunUtc=$taskInfo.LastRunTime.ToUniversalTime().ToString('o')
  }
  $taskLastResult=[int]$taskInfo.LastTaskResult
 }
}catch{
 $taskScheduleReadbackStatus='SCHEDULE_OR_ACTION_NOT_READABLE_NO_STOP_CLAIM'
}

# Interpret existing native Task records only: pre-cutover baseline, not a stop proof.
# This policy MUST remain pure so CI can execute it without Windows/Cloud side effects.
function Test-V3OldIntakeNativeBaseline([object]$Record) {
  if($null -eq $Record){ return $false }
  $scripts=@{
    'CryptoMiniPC-V2R4PaperCandidates'='v2r4-paper-local-runtime.py'
    'CryptoMiniPC-V2R4PaperWait'='wait_launcher.py'
  }
  $name=[string]$Record.task_name
  if(-not $scripts.ContainsKey($name)){ return $false }
  return (
    [string]$Record.state -eq 'Running' -and
    $Record.principal_is_system -eq $true -and
    [int]$Record.action_count -eq 1 -and
    $Record.documented_script_basename_hint_matches -eq $true -and
    [string]$Record.action_script_basename -ceq [string]$scripts[$name] -and
    [int]$Record.trigger_count -eq 1 -and
    $Record.only_boot_trigger -eq $true -and
    [int]$Record.restart_count -eq 3 -and
    [string]$Record.restart_interval -ceq 'PT1M' -and
    [string]$Record.multiple_instances -ceq 'IgnoreNew' -and
    [string]$Record.native_scheduler_xml_status -ceq 'READ' -and
    $Record.heartbeat_fresh_for_role -eq $true
  )
}

# Pure role validation. These PIDs are only a snapshot, never a stop-list.
function Get-V3OldPaperMode([string]$Arguments) {
  $matches=[regex]::Matches($Arguments,'(?i)(?:^|\s)["'']?--mode["'']?\s+["'']?(candidates|lifecycle)["'']?(?=\s|$)')
  if($matches.Count -ne 1){return 'UNRESOLVED'}
  return $matches[0].Groups[1].Value.ToLowerInvariant()
}
function Test-V3OriginalPaperModeLineage([object[]]$Rows,[string]$CandidatesTaskMode,[string]$LifecycleTaskMode) {
  if($CandidatesTaskMode -cne 'candidates' -or $LifecycleTaskMode -cne 'lifecycle'){return $false}
  if(@($Rows).Count -ne 4){return $false}
  $pids=@($Rows | ForEach-Object { [int]$_.PID })
  if(@($pids | Select-Object -Unique).Count -ne 4 -or @($pids | Where-Object {$_ -le 0}).Count -ne 0){return $false}
  foreach($mode in @('candidates','lifecycle')){
    $pair=@($Rows | Where-Object { [string]$_.Mode -ceq $mode })
    if($pair.Count -ne 2 -or @($pair | Where-Object { $_.OriginalStage -ne $true }).Count -ne 0){return $false}
    # Require exactly one parent->child pair within each mode, not any
    # hard-coded PID. Ambiguity must fail closed.
    $child=@($pair | Where-Object { [int]$_.ParentPID -eq [int]$pair[0].PID -or [int]$_.ParentPID -eq [int]$pair[1].PID })
    if($child.Count -ne 1){return $false}
    $root=@($pair | Where-Object { [int]$_.PID -ne [int]$child[0].PID })
    if($root.Count -ne 1 -or [int]$child[0].ParentPID -ne [int]$root[0].PID){return $false}
    if([int]$root[0].ParentPID -le 0 -or @($pids | Where-Object {$_ -eq [int]$root[0].ParentPID}).Count -gt 0){return $false}
  }
  return $true
}

# The old host runtime configuration directory is NOT a physical
# Windows-task/sole-writer proof. Read only the four exact existing V2R4
# task identities; never infer a running Paper writer from JSON controls.
# Only extend the already-existing read-only V3 preflight. Never inspect or
# print raw Task arguments: they may contain bearer tokens or API keys.
# Role/script basename and action hash are DISCOVERY, not pinned-module/sole-writer proof.
$v2r4PaperTasks=@()
$v2r4OriginalRole=@{
 'CryptoMiniPC-V2R4PaperCandidates'=@{script='v2r4-paper-local-runtime.py'; heartbeat='v2r4-paper-candidate-runtime-heartbeat.json'; max_age=60}
 'CryptoMiniPC-V2R4PaperWait'=@{script='wait_launcher.py'; heartbeat='v2r4-paper-wait-runtime-heartbeat.json'; max_age=30}
 'CryptoMiniPC-V2R4PaperLifecycle'=@{script='v2r4-paper-local-runtime.py'; heartbeat='v2r4-paper-lifecycle-heartbeat.json'; max_age=180}
 'CryptoMiniPC-V2R4PaperCloudSync'=@{script='v2r4-paper-cloud-sync.py'; heartbeat='v2r4-paper-cloud-sync-heartbeat.json'; max_age=180}
}
foreach($name in @(
 'CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait',
 'CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync'
)){
 $role=$v2r4OriginalRole[$name]
 $record=[ordered]@{
   task_name=$name
   state='NOT_FOUND'
   last_run_utc=$null
   last_task_result=$null
   action_count=$null
   action_executable_basename=$null
   action_script_basename='UNREAD'
   action_sha256=$null
   paper_task_mode='UNREAD'
   documented_script_basename_hint_matches=$false
   principal_is_system=$false
   restart_count=$null
   restart_interval=$null
   multiple_instances=$null
   trigger_count=$null
   only_boot_trigger=$false
   native_scheduler_xml_status='UNREAD'
   native_precutover_baseline_pass=$false
   heartbeat_status='UNREAD'
   heartbeat_age_seconds=$null
   heartbeat_fresh_for_role=$false
   evidence='READ_ONLY_WINDOWS_TASK_NOT_ACTIVE_WRITER_FENCE_PROOF'
 }
 try{
   $oldTask=Get-ScheduledTask -TaskName $name -ErrorAction Stop
   $record.state=[string]$oldTask.State
   $oldInfo=$oldTask | Get-ScheduledTaskInfo -ErrorAction Stop
   $record.last_run_utc=$oldInfo.LastRunTime.ToUniversalTime().ToString('o')
   $record.last_task_result=[int]$oldInfo.LastTaskResult
   $record.principal_is_system=([string]$oldTask.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18'))
   $record.restart_count=[int]$oldTask.Settings.RestartCount
   $record.restart_interval=[string]$oldTask.Settings.RestartInterval
   $record.multiple_instances=[string]$oldTask.Settings.MultipleInstances
   # Existing Windows Scheduler XML is observed, never edited or printed.
   try{
     $nativeXml=[xml](Export-ScheduledTask -TaskName $name -ErrorAction Stop)
     $triggers=@($nativeXml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Triggers"]/*'))
     $record.trigger_count=$triggers.Count
     $record.only_boot_trigger=($triggers.Count -eq 1 -and $triggers[0].LocalName -eq 'BootTrigger')
     $record.native_scheduler_xml_status='READ'
   }catch{$record.native_scheduler_xml_status='UNREADABLE'}
   $actions=@($oldTask.Actions)
   $record.action_count=$actions.Count
   if($actions.Count -eq 1){
     $action=$actions[0]
     $record.action_executable_basename=[System.IO.Path]::GetFileName([string]$action.Execute)
     $argsText=[string]$action.Arguments
     if($name -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')){
       $record.paper_task_mode=Get-V3OldPaperMode -Arguments $argsText
     }
     # The actual 13/14 October PR291 WAIT Task uses wait_launcher.py,
     # not the older 07 October direct v2r4_wait_runtime.py installer.
     $scriptTokens=[regex]::Matches($argsText,'(?i)(?:wait_launcher|v2r4_wait_runtime|v2r4-paper-local-runtime|v2r4-paper-cloud-sync)\.py')
     if($scriptTokens.Count -eq 1){
       $record.action_script_basename=$scriptTokens[0].Value.ToLowerInvariant()
       $record.documented_script_basename_hint_matches=($record.action_script_basename -ceq [string]$role.script)
     }else{$record.action_script_basename='UNRESOLVED_OR_AMBIGUOUS'}
     # SHA256 of a fixed three-field action tuple; secret values never emitted.
     $actionTuple=@([string]$action.Execute,$argsText,[string]$action.WorkingDirectory) -join '|'
     $sha=[System.Security.Cryptography.SHA256]::Create()
     try{
       $bytes=[System.Text.Encoding]::UTF8.GetBytes($actionTuple)
       $record.action_sha256=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
     }finally{$sha.Dispose()}
   }
   # Read only the already-existing Supervisor heartbeat file, not secrets
   # or process command lines; status/age is not PID or source-module identity.
   $hbPath=Join-Path $state ([string]$role.heartbeat)
   if(Test-Path -LiteralPath $hbPath -PathType Leaf){
     try{
       $hb=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
       $record.heartbeat_status=[string]$hb.status
       $checked=[datetime]::Parse([string]$hb.checked_at_utc).ToUniversalTime()
       $age=[math]::Round(($now-$checked).TotalSeconds,1)
       $record.heartbeat_age_seconds=$age
       $record.heartbeat_fresh_for_role=(
         $record.state -eq 'Running' -and
         $record.heartbeat_status -eq 'HEALTHY' -and
         $age -ge -30 -and $age -le [double]$role.max_age
       )
     }catch{$record.heartbeat_status='UNREADABLE_OR_INVALID'}
   }else{$record.heartbeat_status='MISSING'}
   $record.native_precutover_baseline_pass=Test-V3OldIntakeNativeBaseline -Record ([pscustomobject]$record)
   $record.evidence='PARTIAL_TASK_ACTION_AND_HEARTBEAT_READBACK_NOT_LIVE_SOURCE_OR_REARM_PROOF'
 }catch{
   $record.evidence='NOT_FOUND_OR_TASK_INFO_UNAVAILABLE_NOT_PROVEN'
 }
 $v2r4PaperTasks+=@([pscustomobject]$record)
}
$nativeOldIntake=@($v2r4PaperTasks | Where-Object { $_.task_name -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait') })
$nativePrecutoverBaselinePass=($nativeOldIntake.Count -eq 2 -and
  @($nativeOldIntake | Where-Object { -not $_.native_precutover_baseline_pass }).Count -eq 0)
# Classify only existing original local Python source/mode. NEVER output the
# raw task arguments or Win32_Process CommandLine: they can include secrets.
# These are temporary role identities; a future stop operator MUST re-read.
$paperModeRows=@()
try{
  $procs=@(Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'" -ErrorAction Stop)
  foreach($proc in $procs){
    $command=[string]$proc.CommandLine
    if($command -notmatch '(?i)v2r4-paper-local-runtime\.py'){continue}
    $paperModeRows+=@([pscustomobject]@{
      mode=(Get-V3OldPaperMode -Arguments $command)
      pid=[int]$proc.ProcessId
      parentpid=[int]$proc.ParentProcessId
      original_stage=$command.Contains((Join-Path $runtime 'v2r4-paper-stage-d8b35a8ec2e6'))
    })
  }
}catch{
  # Missing process visibility is explicitly not a pass.
  $paperModeRows=@()
}
$modeCandidates=@($v2r4PaperTasks | Where-Object { $_.task_name -eq 'CryptoMiniPC-V2R4PaperCandidates' })
$modeLifecycle=@($v2r4PaperTasks | Where-Object { $_.task_name -eq 'CryptoMiniPC-V2R4PaperLifecycle' })
$modeRows=@($paperModeRows | ForEach-Object {
  [pscustomobject]@{Mode=$_.mode;PID=$_.pid;ParentPID=$_.parentpid;OriginalStage=$_.original_stage}
})
$nativeOldModeLineagePass=($modeCandidates.Count -eq 1 -and $modeLifecycle.Count -eq 1 -and
  (Test-V3OriginalPaperModeLineage -Rows $modeRows -CandidatesTaskMode $modeCandidates[0].paper_task_mode -LifecycleTaskMode $modeLifecycle[0].paper_task_mode))
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
# A wall-clock expiry is not a physical STOP acknowledgement. This
# diagnostic permits independent human review of the original task only.
$canarySchedulerEndCandidate=$false
if($null -ne $plan -and $taskFinalTriggerUtc){
 try{
  $deadline=[datetime]::Parse([string]$plan.until_utc).ToUniversalTime()
  $actualEnd=[datetime]::Parse($taskFinalTriggerUtc).ToUniversalTime()
  $lastRun=if($taskLastRunUtc){[datetime]::Parse($taskLastRunUtc).ToUniversalTime()}else{$null}
  $canarySchedulerEndCandidate=(
    $now -ge $deadline -and $taskState -in @('Ready','Disabled') -and
    $taskScheduleReadbackStatus -eq 'ONE_ORIGINAL_28H_TRIGGER_READ' -and
    $taskActionMatchesPinnedObserver -and
    [math]::Abs(($actualEnd-$deadline).TotalSeconds) -le 120 -and
    $null -ne $lastRun -and $lastRun -le $deadline -and
    $pinChecked -eq 9 -and $pinMismatches.Count -eq 0
  )
 }catch{$canarySchedulerEndCandidate=$false}
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
              $plan.orders -eq $false -and $pinChecked -eq 9 -and
              $pinMismatches.Count -eq 0 -and $taskState -ne 'NOT_FOUND')
$ready=($repoPresent -and $missingModules.Count -eq 0 -and $sourceSafe -and $canarySafe)
[ordered]@{
 kind='V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1'
 checked_at_utc=$now.ToString('o')
 result=if($ready){'LOCAL_INPUT_PATH_READABLE_NO_WRITER_ACTIVATED'}else{'BLOCKED_READONLY_DIAGNOSTIC'}
 repo_exists=$repoPresent
 required_v3_modules_present=($missingModules.Count -eq 0)
 future_v3_release_source_fingerprint_inventory=@($v3ReleaseSourceHashes)
 future_v3_release_source_files_all_readable=$v3ReleaseSourceHashComplete
 future_v3_release_source_hashes_compared_to_approved_release=$false
 future_v3_paper_writer_installed_by_this_check=$false
 future_v3_paper_single_writer_proven_by_this_check=$false
 missing_v3_modules=@($missingModules)
 active_v2r4_host_runtime_count=$oldApps.Count
 active_v2r4_host_runtime_count_is_config_files_not_processes=$true
 physical_v2r4_paper_task_readback=$v2r4PaperTasks
 native_old_intake_precutover_readonly_baseline_pass=$nativePrecutoverBaselinePass
 native_old_intake_baseline_does_not_prove_postcutover_rearm_fence=$true
 native_old_paper_mode_lineage_precutover_readonly_pass=$nativeOldModeLineagePass
 native_old_paper_mode_lineage_snapshot_only_no_stop_authority=$true
 native_old_paper_mode_rows=@($paperModeRows)
 physical_task_action_sha256_has_no_raw_arguments=$true
 physical_pr291_wait_launcher_basename_only_not_loaded_module_sha_proof=$true
 physical_supervisor_and_windows_rearm_fence_proven=$false
 physical_closed_old_series_followup_exit_relay_proven=$false
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
 canary_original_task_last_run_utc=$taskLastRunUtc
 canary_original_task_last_result=$taskLastResult
 canary_original_trigger_start_utc=$taskFirstTriggerUtc
 canary_original_trigger_end_utc=$taskFinalTriggerUtc
 canary_original_action_matches_manifest=$taskActionMatchesPinnedObserver
 canary_original_schedule_readback_status=$taskScheduleReadbackStatus
 canary_scheduler_end_candidate_for_independent_review=$canarySchedulerEndCandidate
 canary_physical_observer_end_ack_from_this_single_readback=$false
 canary_after_deadline_requires_independent_host_cloud_ack=$true
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
){$digest=$null}
  [pscustomobject]@{
   relative_path=$relative.Replace('\','/')
   sha256=$digest
   readable=($null -ne $digest)
  }
 }
)
$v3ReleaseSourceHashComplete=(@($v3ReleaseSourceHashes | Where-Object {
 $_.readable -ne $true
}).Count -eq 0 -and $v3ReleaseSourceHashes.Count -eq $v3ReleaseSourcePaths.Count)
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
$taskLastRunUtc=$null
$taskLastResult=$null
$taskFirstTriggerUtc=$null
$taskFinalTriggerUtc=$null
$taskActionMatchesPinnedObserver=$false
$taskScheduleReadbackStatus='NOT_VERIFIED'
try{
 $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
 if($null -ne $task){
  $taskState=[string]$task.State
  # Require exactly one original 28h Windows scheduled-task action/trigger.
  if(@($task.Actions).Count -eq 1 -and @($task.Triggers).Count -eq 1){
   $arguments=[string]$task.Actions[0].Arguments
   $runner=Join-Path $repo 'tools\minipc-v3-bounded-canary-observer-task.ps1'
   $taskActionMatchesPinnedObserver=(
     ([string]$task.Actions[0].Execute -match '(^|[\\/])powershell\.exe$') -and
     $arguments.Contains($runner) -and
     $arguments.Contains('-UntilUtc') -and
     $null -ne $plan -and $arguments.Contains([string]$plan.until_utc)
   )
   $first=[datetime]::Parse([string]$task.Triggers[0].StartBoundary).ToUniversalTime()
   $durationText=[string]$task.Triggers[0].Repetition.Duration
   $duration=[System.Xml.XmlConvert]::ToTimeSpan($durationText)
   if($duration -ne [timespan]::FromHours(28)){throw 'Unexpected Canary repetition duration'}
   $taskFirstTriggerUtc=$first.ToString('o')
   $taskFinalTriggerUtc=$first.Add($duration).ToString('o')
   $taskScheduleReadbackStatus='ONE_ORIGINAL_28H_TRIGGER_READ'
  }else{
   $taskScheduleReadbackStatus='MISSING_OR_MULTIPLE_SCHEDULE_ACTIONS_OR_TRIGGERS'
  }
  $taskInfo=$task|Get-ScheduledTaskInfo -ErrorAction Stop
  if($taskInfo.LastRunTime -gt [datetime]::MinValue){
   $taskLastRunUtc=$taskInfo.LastRunTime.ToUniversalTime().ToString('o')
  }
  $taskLastResult=[int]$taskInfo.LastTaskResult
 }
}catch{
 $taskScheduleReadbackStatus='SCHEDULE_OR_ACTION_NOT_READABLE_NO_STOP_CLAIM'
}

# Interpret existing native Task records only: pre-cutover baseline, not a stop proof.
# This policy MUST remain pure so CI can execute it without Windows/Cloud side effects.
function Test-V3OldIntakeNativeBaseline([object]$Record) {
  if($null -eq $Record){ return $false }
  $scripts=@{
    'CryptoMiniPC-V2R4PaperCandidates'='v2r4-paper-local-runtime.py'
    'CryptoMiniPC-V2R4PaperWait'='wait_launcher.py'
  }
  $name=[string]$Record.task_name
  if(-not $scripts.ContainsKey($name)){ return $false }
  return (
    [string]$Record.state -eq 'Running' -and
    $Record.principal_is_system -eq $true -and
    [int]$Record.action_count -eq 1 -and
    $Record.documented_script_basename_hint_matches -eq $true -and
    [string]$Record.action_script_basename -ceq [string]$scripts[$name] -and
    [int]$Record.trigger_count -eq 1 -and
    $Record.only_boot_trigger -eq $true -and
    [int]$Record.restart_count -eq 3 -and
    [string]$Record.restart_interval -ceq 'PT1M' -and
    [string]$Record.multiple_instances -ceq 'IgnoreNew' -and
    [string]$Record.native_scheduler_xml_status -ceq 'READ' -and
    $Record.heartbeat_fresh_for_role -eq $true
  )
}

# Pure role validation. These PIDs are only a snapshot, never a stop-list.
function Get-V3OldPaperMode([string]$Arguments) {
  $matches=[regex]::Matches($Arguments,'(?i)(?:^|\s)["'']?--mode["'']?\s+["'']?(candidates|lifecycle)["'']?(?=\s|$)')
  if($matches.Count -ne 1){return 'UNRESOLVED'}
  return $matches[0].Groups[1].Value.ToLowerInvariant()
}
function Test-V3OriginalPaperModeLineage([object[]]$Rows,[string]$CandidatesTaskMode,[string]$LifecycleTaskMode) {
  if($CandidatesTaskMode -cne 'candidates' -or $LifecycleTaskMode -cne 'lifecycle'){return $false}
  if(@($Rows).Count -ne 4){return $false}
  $pids=@($Rows | ForEach-Object { [int]$_.PID })
  if(@($pids | Select-Object -Unique).Count -ne 4 -or @($pids | Where-Object {$_ -le 0}).Count -ne 0){return $false}
  foreach($mode in @('candidates','lifecycle')){
    $pair=@($Rows | Where-Object { [string]$_.Mode -ceq $mode })
    if($pair.Count -ne 2 -or @($pair | Where-Object { $_.OriginalStage -ne $true }).Count -ne 0){return $false}
    # Require exactly one parent->child pair within each mode, not any
    # hard-coded PID. Ambiguity must fail closed.
    $child=@($pair | Where-Object { [int]$_.ParentPID -eq [int]$pair[0].PID -or [int]$_.ParentPID -eq [int]$pair[1].PID })
    if($child.Count -ne 1){return $false}
    $root=@($pair | Where-Object { [int]$_.PID -ne [int]$child[0].PID })
    if($root.Count -ne 1 -or [int]$child[0].ParentPID -ne [int]$root[0].PID){return $false}
    if([int]$root[0].ParentPID -le 0 -or @($pids | Where-Object {$_ -eq [int]$root[0].ParentPID}).Count -gt 0){return $false}
  }
  return $true
}

# The old host runtime configuration directory is NOT a physical
# Windows-task/sole-writer proof. Read only the four exact existing V2R4
# task identities; never infer a running Paper writer from JSON controls.
# Only extend the already-existing read-only V3 preflight. Never inspect or
# print raw Task arguments: they may contain bearer tokens or API keys.
# Role/script basename and action hash are DISCOVERY, not pinned-module/sole-writer proof.
$v2r4PaperTasks=@()
$v2r4OriginalRole=@{
 'CryptoMiniPC-V2R4PaperCandidates'=@{script='v2r4-paper-local-runtime.py'; heartbeat='v2r4-paper-candidate-runtime-heartbeat.json'; max_age=60}
 'CryptoMiniPC-V2R4PaperWait'=@{script='wait_launcher.py'; heartbeat='v2r4-paper-wait-runtime-heartbeat.json'; max_age=30}
 'CryptoMiniPC-V2R4PaperLifecycle'=@{script='v2r4-paper-local-runtime.py'; heartbeat='v2r4-paper-lifecycle-heartbeat.json'; max_age=180}
 'CryptoMiniPC-V2R4PaperCloudSync'=@{script='v2r4-paper-cloud-sync.py'; heartbeat='v2r4-paper-cloud-sync-heartbeat.json'; max_age=180}
}
foreach($name in @(
 'CryptoMiniPC-V2R4PaperCandidates',
 'CryptoMiniPC-V2R4PaperWait',
 'CryptoMiniPC-V2R4PaperLifecycle',
 'CryptoMiniPC-V2R4PaperCloudSync'
)){
 $role=$v2r4OriginalRole[$name]
 $record=[ordered]@{
   task_name=$name
   state='NOT_FOUND'
   last_run_utc=$null
   last_task_result=$null
   action_count=$null
   action_executable_basename=$null
   action_script_basename='UNREAD'
   action_sha256=$null
   paper_task_mode='UNREAD'
   documented_script_basename_hint_matches=$false
   principal_is_system=$false
   restart_count=$null
   restart_interval=$null
   multiple_instances=$null
   trigger_count=$null
   only_boot_trigger=$false
   native_scheduler_xml_status='UNREAD'
   native_precutover_baseline_pass=$false
   heartbeat_status='UNREAD'
   heartbeat_age_seconds=$null
   heartbeat_fresh_for_role=$false
   evidence='READ_ONLY_WINDOWS_TASK_NOT_ACTIVE_WRITER_FENCE_PROOF'
 }
 try{
   $oldTask=Get-ScheduledTask -TaskName $name -ErrorAction Stop
   $record.state=[string]$oldTask.State
   $oldInfo=$oldTask | Get-ScheduledTaskInfo -ErrorAction Stop
   $record.last_run_utc=$oldInfo.LastRunTime.ToUniversalTime().ToString('o')
   $record.last_task_result=[int]$oldInfo.LastTaskResult
   $record.principal_is_system=([string]$oldTask.Principal.UserId -in @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18'))
   $record.restart_count=[int]$oldTask.Settings.RestartCount
   $record.restart_interval=[string]$oldTask.Settings.RestartInterval
   $record.multiple_instances=[string]$oldTask.Settings.MultipleInstances
   # Existing Windows Scheduler XML is observed, never edited or printed.
   try{
     $nativeXml=[xml](Export-ScheduledTask -TaskName $name -ErrorAction Stop)
     $triggers=@($nativeXml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Triggers"]/*'))
     $record.trigger_count=$triggers.Count
     $record.only_boot_trigger=($triggers.Count -eq 1 -and $triggers[0].LocalName -eq 'BootTrigger')
     $record.native_scheduler_xml_status='READ'
   }catch{$record.native_scheduler_xml_status='UNREADABLE'}
   $actions=@($oldTask.Actions)
   $record.action_count=$actions.Count
   if($actions.Count -eq 1){
     $action=$actions[0]
     $record.action_executable_basename=[System.IO.Path]::GetFileName([string]$action.Execute)
     $argsText=[string]$action.Arguments
     if($name -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperLifecycle')){
       $record.paper_task_mode=Get-V3OldPaperMode -Arguments $argsText
     }
     # The actual 13/14 October PR291 WAIT Task uses wait_launcher.py,
     # not the older 07 October direct v2r4_wait_runtime.py installer.
     $scriptTokens=[regex]::Matches($argsText,'(?i)(?:wait_launcher|v2r4_wait_runtime|v2r4-paper-local-runtime|v2r4-paper-cloud-sync)\.py')
     if($scriptTokens.Count -eq 1){
       $record.action_script_basename=$scriptTokens[0].Value.ToLowerInvariant()
       $record.documented_script_basename_hint_matches=($record.action_script_basename -ceq [string]$role.script)
     }else{$record.action_script_basename='UNRESOLVED_OR_AMBIGUOUS'}
     # SHA256 of a fixed three-field action tuple; secret values never emitted.
     $actionTuple=@([string]$action.Execute,$argsText,[string]$action.WorkingDirectory) -join '|'
     $sha=[System.Security.Cryptography.SHA256]::Create()
     try{
       $bytes=[System.Text.Encoding]::UTF8.GetBytes($actionTuple)
       $record.action_sha256=([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
     }finally{$sha.Dispose()}
   }
   # Read only the already-existing Supervisor heartbeat file, not secrets
   # or process command lines; status/age is not PID or source-module identity.
   $hbPath=Join-Path $state ([string]$role.heartbeat)
   if(Test-Path -LiteralPath $hbPath -PathType Leaf){
     try{
       $hb=Get-Content -LiteralPath $hbPath -Raw | ConvertFrom-Json
       $record.heartbeat_status=[string]$hb.status
       $checked=[datetime]::Parse([string]$hb.checked_at_utc).ToUniversalTime()
       $age=[math]::Round(($now-$checked).TotalSeconds,1)
       $record.heartbeat_age_seconds=$age
       $record.heartbeat_fresh_for_role=(
         $record.state -eq 'Running' -and
         $record.heartbeat_status -eq 'HEALTHY' -and
         $age -ge -30 -and $age -le [double]$role.max_age
       )
     }catch{$record.heartbeat_status='UNREADABLE_OR_INVALID'}
   }else{$record.heartbeat_status='MISSING'}
   $record.native_precutover_baseline_pass=Test-V3OldIntakeNativeBaseline -Record ([pscustomobject]$record)
   $record.evidence='PARTIAL_TASK_ACTION_AND_HEARTBEAT_READBACK_NOT_LIVE_SOURCE_OR_REARM_PROOF'
 }catch{
   $record.evidence='NOT_FOUND_OR_TASK_INFO_UNAVAILABLE_NOT_PROVEN'
 }
 $v2r4PaperTasks+=@([pscustomobject]$record)
}
$nativeOldIntake=@($v2r4PaperTasks | Where-Object { $_.task_name -in @('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait') })
$nativePrecutoverBaselinePass=($nativeOldIntake.Count -eq 2 -and
  @($nativeOldIntake | Where-Object { -not $_.native_precutover_baseline_pass }).Count -eq 0)
# Classify only existing original local Python source/mode. NEVER output the
# raw task arguments or Win32_Process CommandLine: they can include secrets.
# These are temporary role identities; a future stop operator MUST re-read.
$paperModeRows=@()
try{
  $procs=@(Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'" -ErrorAction Stop)
  foreach($proc in $procs){
    $command=[string]$proc.CommandLine
    if($command -notmatch '(?i)v2r4-paper-local-runtime\.py'){continue}
    $paperModeRows+=@([pscustomobject]@{
      mode=(Get-V3OldPaperMode -Arguments $command)
      pid=[int]$proc.ProcessId
      parentpid=[int]$proc.ParentProcessId
      original_stage=$command.Contains((Join-Path $runtime 'v2r4-paper-stage-d8b35a8ec2e6'))
    })
  }
}catch{
  # Missing process visibility is explicitly not a pass.
  $paperModeRows=@()
}
$modeCandidates=@($v2r4PaperTasks | Where-Object { $_.task_name -eq 'CryptoMiniPC-V2R4PaperCandidates' })
$modeLifecycle=@($v2r4PaperTasks | Where-Object { $_.task_name -eq 'CryptoMiniPC-V2R4PaperLifecycle' })
$modeRows=@($paperModeRows | ForEach-Object {
  [pscustomobject]@{Mode=$_.mode;PID=$_.pid;ParentPID=$_.parentpid;OriginalStage=$_.original_stage}
})
$nativeOldModeLineagePass=($modeCandidates.Count -eq 1 -and $modeLifecycle.Count -eq 1 -and
  (Test-V3OriginalPaperModeLineage -Rows $modeRows -CandidatesTaskMode $modeCandidates[0].paper_task_mode -LifecycleTaskMode $modeLifecycle[0].paper_task_mode))
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
# A wall-clock expiry is not a physical STOP acknowledgement. This
# diagnostic permits independent human review of the original task only.
$canarySchedulerEndCandidate=$false
if($null -ne $plan -and $taskFinalTriggerUtc){
 try{
  $deadline=[datetime]::Parse([string]$plan.until_utc).ToUniversalTime()
  $actualEnd=[datetime]::Parse($taskFinalTriggerUtc).ToUniversalTime()
  $lastRun=if($taskLastRunUtc){[datetime]::Parse($taskLastRunUtc).ToUniversalTime()}else{$null}
  $canarySchedulerEndCandidate=(
    $now -ge $deadline -and $taskState -in @('Ready','Disabled') -and
    $taskScheduleReadbackStatus -eq 'ONE_ORIGINAL_28H_TRIGGER_READ' -and
    $taskActionMatchesPinnedObserver -and
    [math]::Abs(($actualEnd-$deadline).TotalSeconds) -le 120 -and
    $null -ne $lastRun -and $lastRun -le $deadline -and
    $pinChecked -eq 9 -and $pinMismatches.Count -eq 0
  )
 }catch{$canarySchedulerEndCandidate=$false}
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
              $plan.orders -eq $false -and $pinChecked -eq 9 -and
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
 native_old_intake_precutover_readonly_baseline_pass=$nativePrecutoverBaselinePass
 native_old_intake_baseline_does_not_prove_postcutover_rearm_fence=$true
 native_old_paper_mode_lineage_precutover_readonly_pass=$nativeOldModeLineagePass
 native_old_paper_mode_lineage_snapshot_only_no_stop_authority=$true
 native_old_paper_mode_rows=@($paperModeRows)
 physical_task_action_sha256_has_no_raw_arguments=$true
 physical_pr291_wait_launcher_basename_only_not_loaded_module_sha_proof=$true
 physical_supervisor_and_windows_rearm_fence_proven=$false
 physical_closed_old_series_followup_exit_relay_proven=$false
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
 canary_original_task_last_run_utc=$taskLastRunUtc
 canary_original_task_last_result=$taskLastResult
 canary_original_trigger_start_utc=$taskFirstTriggerUtc
 canary_original_trigger_end_utc=$taskFinalTriggerUtc
 canary_original_action_matches_manifest=$taskActionMatchesPinnedObserver
 canary_original_schedule_readback_status=$taskScheduleReadbackStatus
 canary_scheduler_end_candidate_for_independent_review=$canarySchedulerEndCandidate
 canary_physical_observer_end_ack_from_this_single_readback=$false
 canary_after_deadline_requires_independent_host_cloud_ack=$true
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
