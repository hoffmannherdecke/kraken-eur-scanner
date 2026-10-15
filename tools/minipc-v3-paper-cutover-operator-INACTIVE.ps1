param(
 [string]$TradingRoot=(Join-Path $env:USERPROFILE 'Trading'),
 [switch]$Execute
)
# V3 experimental Paper scoped operator: SOURCE PREPARATION ONLY.
# GitHub/CI draft; not an installed cutover, not a stop, not a rollback.
# No host, Task, PID, marker, database, secret, or Cloud writes.
$ErrorActionPreference='Stop'

# Pure readiness policy, executable by existing offline CI without running
# any host commands. These checks are only PRE-CUTOVER discovery.
function Test-V3CutoverPreparationPolicy([object]$Report,[bool]$FenceMarkerPresent,[bool]$MaintenanceMarkerPresent) {
 if($null -eq $Report -or $FenceMarkerPresent -or $MaintenanceMarkerPresent){return $false}
 if([string]$Report.kind -cne 'V3_MINIPC_SINGLE_WRITER_PHYSICAL_READONLY_PREFLIGHT_V1'){return $false}
 if([string]$Report.pre_cutover_expected_predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z'){return $false}
 if($Report.native_old_intake_precutover_readonly_baseline_pass -ne $true -or
    $Report.native_old_paper_mode_lineage_precutover_readonly_pass -ne $true -or
    $Report.native_old_paper_mode_lineage_snapshot_only_no_stop_authority -ne $true){return $false}
 if($Report.new_v3_writer_started -ne $false -or $Report.v2r4_changed -ne $false){return $false}
 $roles=@{
   'CryptoMiniPC-V2R4PaperCandidates'='v2r4-paper-local-runtime.py'
   'CryptoMiniPC-V2R4PaperWait'='wait_launcher.py'
   'CryptoMiniPC-V2R4PaperLifecycle'='v2r4-paper-local-runtime.py'
   'CryptoMiniPC-V2R4PaperCloudSync'='v2r4-paper-cloud-sync.py'
 }
 $rows=@($Report.physical_v2r4_paper_task_readback)
 if($rows.Count -ne 4){return $false}
 foreach($name in @($roles.Keys)){
   $one=@($rows | Where-Object { [string]$_.task_name -ceq $name })
   if($one.Count -ne 1){return $false}
   $item=$one[0]
   if([string]$item.state -cne 'Running' -or
      [int]$item.action_count -ne 1 -or
      [string]$item.action_script_basename -cne $roles[$name] -or
      $item.documented_script_basename_hint_matches -ne $true -or
      $item.principal_is_system -ne $true -or
      $item.heartbeat_fresh_for_role -ne $true){return $false}
 }
 # Mode lineage is validated by the original PR313 source, NOT re-created.
 # A transient PID record never becomes authority to kill a PID or task.
 return $true
}

# Pure closed-descendants guard. A two-Python-process match alone cannot show
# whether a WAIT root has an unexpected non-Python or deeper child process.
# Snapshot only: NEVER convert these PIDs into a stop list.
function Test-V3WaitCompleteReadOnlyFamily(
 [object[]]$WaitRows,
 [object[]]$AllProcesses,
 [bool]$WaitActionObserved,
 [int[]]$ProtectedRolePids
) {
 if(-not $WaitActionObserved){return $false}
 $wait=@($WaitRows)
 # Windows ProcessId 0 is the kernel Idle pseudo-process, never a WAIT descendant.
 $all=@($AllProcesses | Where-Object {[int]$_.PID -ne 0})
 if($wait.Count -ne 2 -or $all.Count -lt 2){return $false}
 $ids=@($wait | ForEach-Object {[int]$_.PID})
 if(@($ids | Where-Object {$_ -le 0}).Count -ne 0 -or
    @($ids | Select-Object -Unique).Count -ne 2){return $false}
 if(@($wait | Where-Object {$_.OriginalStage -ne $true}).Count -ne 0){return $false}
 if(@($ProtectedRolePids | Where-Object {$_ -in $ids}).Count -gt 0){return $false}
 $allIds=@($all | ForEach-Object {[int]$_.PID})
 if(@($allIds | Where-Object {$_ -le 0}).Count -gt 0 -or
    @($allIds | Select-Object -Unique).Count -ne $all.Count){return $false}
 foreach($w in $wait){
  $edge=@($all | Where-Object {[int]$_.PID -eq [int]$w.PID})
  if($edge.Count -ne 1 -or [int]$edge[0].ParentPID -ne [int]$w.ParentPID){return $false}
 }
 $children=@($wait | Where-Object {[int]$_.ParentPID -in $ids})
 if($children.Count -ne 1){return $false}
 $child=$children[0]
 $root=@($wait | Where-Object {[int]$_.PID -ne [int]$child.PID})
 if($root.Count -ne 1 -or [int]$root[0].ParentPID -le 0 -or
    [int]$root[0].ParentPID -in $ids -or
    [int]$child.ParentPID -ne [int]$root[0].PID){return $false}
 # Reject any edge pointing into the WAIT family except its verified child.
 # This covers Windows process types beyond Python and deeper descendants.
 foreach($p in $all){
   if([int]$p.ParentPID -in $ids -and [int]$p.PID -ne [int]$child.PID){return $false}
 }
 return $true
}

# Pure V3 single-writer contract: ONLY original intake Tasks may ever be changed.
# No host operations; return boolean for offline negative tests.
function Test-V3ScopedIntakeTaskSet([object[]]$Names) {
 $expected=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait' | Sort-Object)
 $got=@($Names | ForEach-Object {[string]$_} | Sort-Object)
 return ($got.Count -eq 2 -and ($got -join '|') -ceq ($expected -join '|'))
}

# Backup manifest is a PROPOSED contract. These strings/booleans are not
# evidence that files were written or that a real physical backup exists.
function Test-V3ScopedOriginalBackupContract([object]$Manifest) {
 if($null -eq $Manifest -or
    [string]$Manifest.kind -cne 'V3_OLD_INTAKE_BACKUP_PROPOSAL_V1' -or
    [string]$Manifest.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    [string]$Manifest.old_stage_release_sha -cnotmatch '^[a-f0-9]{40}$' -or
    $Manifest.paper_only -ne $true -or
    $Manifest.real_money_actions -ne $false){return $false}
 $entries=@($Manifest.task_records)
 if(-not(Test-V3ScopedIntakeTaskSet -Names @($entries | ForEach-Object {$_.task_name}))){return $false}
 foreach($entry in $entries){
  if([string]$entry.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     [string]$entry.action_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
     $entry.original_enabled -ne $true -or
     $entry.original_running -ne $true -or
     $entry.original_principal_system -ne $true -or
     $entry.one_original_boot_trigger -ne $true -or
     [int]$entry.restart_count -ne 3 -or
     [string]$entry.restart_interval -cne 'PT1M' -or
     [string]$entry.multiple_instances -cne 'IgnoreNew'){return $false}
 }
 return $true
}

# A pure decision matrix. NEVER restore an old writer after ANY CAS invocation,
# including timeout, no response or an apparently negative outcome: operator
# MUST fence and reconcile actual independent Cloud readback by hand.
# No decision returned here grants permission to execute a Windows mutation.
function Resolve-V3ScopedCutoverRecovery([object]$Receipt) {
 $resolution='HOLD_FENCE_MANUAL_RECONCILIATION'
 if($null -eq $Receipt -or
    [string]$Receipt.kind -cne 'V3_CUTOVER_RECOVERY_SIMULATION_V1' -or
    [string]$Receipt.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
    -not(Test-V3ScopedIntakeTaskSet -Names @($Receipt.task_names)) -or
    $null -eq $Receipt.cloud_cas_invoked -or
    $null -eq $Receipt.v3_writer_started -or
    $Receipt.paper_only -ne $true -or
    $Receipt.real_money_actions -ne $false){
   $resolution='BLOCK_INVALID_SCOPE_OR_RECEIPT'
 } else {
  $phase=[string]$Receipt.phase
  $outcome=[string]$Receipt.cloud_cas_outcome
  $invoked=($Receipt.cloud_cas_invoked -eq $true)
  if($outcome -notin @('NOT_INVOKED','UNKNOWN','NOT_COMMITTED','COMMITTED')){
   $resolution='HOLD_INVALID_CLOUD_OUTCOME'
  } elseif($outcome -eq 'COMMITTED' -or $phase -eq 'CLOUD_COMMITTED'){
   $resolution='HOLD_POSTCOMMIT_OLD_INTAKE_PERMANENTLY_FENCED'
  } elseif($invoked -or $outcome -ne 'NOT_INVOKED' -or $phase -eq 'CAS_INVOKED'){
   $resolution='HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
  } elseif($phase -eq 'PRE_CUTOVER'){
   $resolution='NO_ACTION_PRESERVE_ACTIVE_V2R4'
  } elseif($phase -notin @('ARMED','QUIESCED')){
   $resolution='HOLD_UNKNOWN_PHASE'
  } elseif($phase -eq 'QUIESCED' -and
      (Test-V3ScopedOriginalBackupContract -Manifest $Receipt.backup_manifest) -and
      $Receipt.backup_contract_verified -eq $true -and
      $Receipt.native_intake_tasks_disabled_ack -eq $true -and
      $Receipt.original_intake_processes_absent_ack -eq $true -and
      $Receipt.windows_supervisor_no_rearm_ack -eq $true -and
      $Receipt.protected_lifecycle_cloudsync_running_ack -eq $true -and
      $Receipt.old_cloud_single_active_readback -eq $true -and
      $Receipt.new_v3_series_absent_readback -eq $true -and
      $Receipt.v3_writer_started -eq $false){
   $resolution='PRE_CAS_MANUAL_ROLLBACK_REVIEW_CANDIDATE'
  }
 }
 return [pscustomobject]@{
  kind='V3_CUTOVER_RECOVERY_OFFLINE_DISPOSITION_V1'
  disposition=$resolution
  automatic_task_action_authorized=$false
  automatic_old_writer_rearm_allowed=$false
  operator_stop_disable_implemented=$false
  host_rollback_implemented=$false
  cloud_cas_executed=$false
  v3_release_authorized=$false
  full_v3_e2e_proofs_credited=0
 }
}


# Exact adapter for the *actual* 15-Oct host backup-manifest.json SCHEMA.
# This validates values only, not the physical existence of a backup directory,
# file SHA, Windows Task state, privileged ACL, machine identity or provenance.
# Critically it MUST NOT upcast this V1 host readback to PR316's simulated,
# more demanding V3_OLD_INTAKE_BACKUP_PROPOSAL_V1 task_records contract.
function Get-V3NativeIntakeBackupReadbackGap([object]$Readback) {
 $errors=@()
 $expected=@{
  'CryptoMiniPC-V2R4PaperCandidates'='Candidates.task.xml'
  'CryptoMiniPC-V2R4PaperWait'='WAIT.task.xml'
 }
 if($null -eq $Readback){
  $errors+=@('MISSING_READBACK')
 } else {
  if([string]$Readback.kind -cne 'V3_OLD_INTAKE_NATIVE_BACKUP_READBACK_V1'){
   $errors+=@('WRONG_NATIVE_KIND')
  }
  if([string]$Readback.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z'){
   $errors+=@('WRONG_PREDECESSOR')
  }
  if($Readback.task_or_process_changes -ne $false -or
     $Readback.cloud_changes -ne $false -or
     $Readback.actual_stop_or_rollback_tested -ne $false){
   $errors+=@('UNEXPECTED_MUTATION_OR_RESTORE_CLAIM')
  }
  $time=[datetimeoffset]::MinValue
  $timestamp=[string]$Readback.captured_at_utc
  if($timestamp -cnotmatch '(Z|\+00:00)$' -or
     -not([datetimeoffset]::TryParse($timestamp,[ref]$time))){
   $errors+=@('INVALID_UTC_CAPTURE_TIME')
  }
  $tasks=@($Readback.tasks)
  if($tasks.Count -ne 2){
   $errors+=@('WRONG_COUNT')
  } else {
   $names=@($tasks | ForEach-Object {[string]$_.task_name})
   if(-not(Test-V3ScopedIntakeTaskSet -Names $names)){
    $errors+=@('WRONG_TASK_SCOPE')
   }
   foreach($task in $tasks){
    $name=[string]$task.task_name
    if(-not $expected.ContainsKey($name)){continue}
    if([string]$task.backup_file -cne $expected[$name]){
     $errors+=@('UNEXPECTED_BACKUP_FILENAME')
    }
    if([string]$task.task_path -cne '\'){
     $errors+=@('UNEXPECTED_TASK_PATH')
    }
    if([string]$task.original_state -cne 'Running'){
     $errors+=@('NONRUNNING_OR_UNKNOWN_ORIGINAL_STATE')
    }
    if([string]$task.xml_sha256 -cnotmatch '^[a-f0-9]{64}$' -or
       [string]$task.action_sha256 -cnotmatch '^[a-f0-9]{64}$'){
     $errors+=@('INVALID_CAPTURED_HASH')
    }
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_NATIVE_BACKUP_READBACK_SCHEMA_GAP_OFFLINE_V1'
  native_host_manifest_schema_only_pass=($errors.Count -eq 0)
  schema_errors=@($errors)
  schema_is_not_physical_provenance=$true
  host_backup_physical_readback_independently_verified_here=$false
  full_task_xml_contents_and_disk_sha_recheck_needed=$true
  original_native_principal_boot_restart_settings_recheck_needed=$true
  original_runtime_stage_source_sha_needed=$true
  exact_live_task_action_xml_and_process_tree_recheck_needed=$true
  actual_restore_dryrun_completed=$false
  can_upcast_native_host_manifest_to_recovery_proposal=$false
  automatic_intake_task_action_authorized=$false
  v3_paper_release_authorized=$false
  full_v3_release_proofs_credited=0
 }
}


# Pure in-memory restoration PREVIEW of exact two original scheduled Tasks.
# Accept values collected by an independently authorized read-only host probe.
# Never registers, starts, disables, repairs or overwrites an actual Task.
# Even a PASS is not a true TaskScheduler import/restore or physical provenance.
function Test-V3NativeOriginalTaskRestorePreview([object]$Readback,[object[]]$Rows) {
 $errors=@()
 $shape=Get-V3NativeIntakeBackupReadbackGap -Readback $Readback
 if($shape.native_host_manifest_schema_only_pass -ne $true){
  $errors+=@('INVALID_ORIGINAL_MANIFEST')
 }
 $items=@($Rows)
 if($items.Count -ne 2){
  $errors+=@('NOT_EXACTLY_TWO_READONLY_ROWS')
 }else{
  $names=@($items | ForEach-Object {[string]$_.task_name})
  if(-not(Test-V3ScopedIntakeTaskSet -Names $names)){
   $errors+=@('INVALID_PREVIEW_TASK_SCOPE')
  }
 }
 if($errors.Count -eq 0){
  foreach($entry in @($Readback.tasks)){
   $n=[string]$entry.task_name
   $matches=@($items | Where-Object {[string]$_.task_name -ceq $n})
   if($matches.Count -ne 1){
    $errors+=@('MISSING_OR_DUPLICATE_ORIGINAL_TASK')
    continue
   }
   $row=$matches[0]
   $saved=[string]$row.backup_xml_text
   $current=[string]$row.current_task_xml_text
   if([string]$row.backup_file_sha256 -cne [string]$entry.xml_sha256){
    $errors+=@('BACKUP_FILE_HASH_MISMATCH')
   }
   if($saved.Length -eq 0 -or $saved -cne $current){
    $errors+=@('BACKUP_XML_NOT_EQUAL_ORIGINAL')
    continue
   }
   if($row.current_task_running -ne $true -or
      $row.native_task_enabled -ne $true){
    $errors+=@('ORIGINAL_TASK_NOT_ENABLED_RUNNING')
   }
   try{
    $xml=[System.Xml.XmlDocument]::new()
    $xml.XmlResolver=$null
    $xml.LoadXml($saved)
    if($xml.DocumentElement.LocalName -cne 'Task'){
     $errors+=@('WRONG_TASK_XML_ROOT')
     continue
    }
    $user=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Principals"]/*[local-name()="Principal"]/*[local-name()="UserId"]')
    if($null -eq $user -or
       [string]$user.InnerText -notin @('SYSTEM','NT AUTHORITY\SYSTEM','S-1-5-18')){
     $errors+=@('NON_SYSTEM_ORIGINAL_TASK')
    }
    $triggers=@($xml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Triggers"]/*'))
    if($triggers.Count -ne 1 -or $triggers[0].LocalName -cne 'BootTrigger'){
     $errors+=@('ORIGINAL_BOOT_TRIGGER_CHANGED')
    }
    $restart=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]')
    $countNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]/*[local-name()="Count"]')
    $interval=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="RestartOnFailure"]/*[local-name()="Interval"]')
    $multiple=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Settings"]/*[local-name()="MultipleInstancesPolicy"]')
    if($null -eq $restart -or $null -eq $countNode -or $null -eq $interval -or $null -eq $multiple -or
       [string]$countNode.InnerText -cne '3' -or
       [string]$interval.InnerText -cne 'PT1M' -or
       [string]$multiple.InnerText -cne 'IgnoreNew'){
     $errors+=@('ORIGINAL_RESTART_POLICY_CHANGED')
    }
    $actions=@($xml.SelectNodes('/*[local-name()="Task"]/*[local-name()="Actions"]/*'))
    if($actions.Count -ne 1 -or $actions[0].LocalName -cne 'Exec'){
     $errors+=@('ORIGINAL_ACTION_SCOPE_CHANGED')
     continue
    }
    $cmdNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="Command"]')
    $argsNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="Arguments"]')
    $workingNode=$xml.SelectSingleNode('/*[local-name()="Task"]/*[local-name()="Actions"]/*[local-name()="Exec"]/*[local-name()="WorkingDirectory"]')
    if($null -eq $cmdNode -or [string]::IsNullOrWhiteSpace([string]$cmdNode.InnerText)){
     $errors+=@('ORIGINAL_ACTION_EXEC_MISSING')
     continue
    }
    $argsValue=''
    $workingValue=''
    if($null -ne $argsNode){$argsValue=[string]$argsNode.InnerText}
    if($null -ne $workingNode){$workingValue=[string]$workingNode.InnerText}
    $expectedScript=if($n -ceq 'CryptoMiniPC-V2R4PaperCandidates'){'v2r4-paper-local-runtime.py'}else{'wait_launcher.py'}
    if($argsValue -notmatch [regex]::Escape($expectedScript)){
     $errors+=@('ORIGINAL_ACTION_NOT_BOUND_TO_EXPECTED_SCRIPT')
    }
    $actionText=@([string]$cmdNode.InnerText,$argsValue,$workingValue) -join ([string][char]10)
    $sha=[Security.Cryptography.SHA256]::Create()
    try{
     $hash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($actionText)))).Replace('-','').ToLowerInvariant()
    }finally{$sha.Dispose()}
    # Exact original 15-Oct native-backup newline-delimited serialization.
    # PR313 uses a different pipe-delimited hash: do not compare against it.
    if($hash -cne [string]$entry.action_sha256){
     $errors+=@('ORIGINAL_BACKUP_ACTION_HASH_MISMATCH')
    }
   }catch{
    $errors+=@('UNPARSABLE_ORIGINAL_TASK_XML')
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_ORIGINAL_TASK_RESTORE_PREVIEW_OFFLINE_ONLY_V1'
  preview_structure_only_pass=($errors.Count -eq 0)
  preview_errors=@($errors | Select-Object -Unique)
  full_host_source_and_task_identity_proven_here=$false
  original_host_backup_acl_proven_here=$false
  original_host_disk_bytes_proven_here=$false
  protected_lifecycle_cloudsync_runtime_proven_here=$false
  task_scheduler_import_or_restore_invoked=$false
  task_process_marker_cloud_writes=0
  actual_restore_test_passed=$false
  native_no_rearm_stop_ack_passed=$false
  v3_release_authorized=$false
  technical_release_proofs_credited=0
 }
}


# Pure physical-fence choreography preview: NEVER issues commands or authorizes
# Task/PID/marker/CAS changes. Receipt values below are SYNTHETIC UNTRUSTED
# inputs; actual Windows/CLOUD receipts and separate permits are mandatory.
function Get-V3SingleWriterFenceDryRunPlan([object]$Receipt) {
 $decision='BLOCK_MISSING_OR_INVALID_RECEIPT'
 $errors=@()
 if($null -eq $Receipt){
  $errors+=@('MISSING_INPUT')
 }else{
  if([string]$Receipt.kind -cne 'V3_SINGLE_WRITER_FENCE_DRYRUN_SIMULATION_V1' -or
     [string]$Receipt.predecessor_series_id -cne 'PAPER-V2R4-20261009T110135Z' -or
     $Receipt.paper_only -ne $true -or $Receipt.real_money_actions -ne $false -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($Receipt.intake_task_names))){
   $errors+=@('INVALID_PREDECESSOR_OR_TASK_SCOPE')
  }
  $preserved=@($Receipt.protected_task_names)
  $required=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync') | Sort-Object
  if($preserved.Count -ne 2 -or
     (@($preserved | Sort-Object) -join '|') -cne ($required -join '|') -or
     $Receipt.protected_tasks_running -ne $true){
   $errors+=@('PROTECTED_FOLLOWUP_ROLES_NOT_RUNNING')
  }
  if($Receipt.source_pins_verified -ne $true -or
     $Receipt.mode_lineage_fresh -ne $true -or
     $Receipt.wait_all_descendants_verified -ne $true -or
     $Receipt.original_cloud_only_readback -ne $true -or
     $Receipt.v3_writer_running -ne $false){
   $errors+=@('ORIGINAL_SOURCE_LINEAGE_OR_CLOUD_UNTRUSTED')
  }
  if($Receipt.backup_readback_verified -ne $true -or
     -not(Test-V3ScopedOriginalBackupContract -Manifest $Receipt.backup_proposal)){
   $errors+=@('BACKUP_CONTRACT_OR_ORIGINAL_READBACK_MISSING')
  }
  $taskRows=@($Receipt.intake_task_states)
  if($taskRows.Count -ne 2 -or
     -not(Test-V3ScopedIntakeTaskSet -Names @($taskRows | ForEach-Object {[string]$_.task_name}))){
   $errors+=@('WRONG_NATIVE_INTAKE_TASK_ROWS')
  }
  $phase=[string]$Receipt.phase
  $casOutcome=[string]$Receipt.cas_outcome
  $casWasInvoked=($Receipt.cas_invoked -eq $true)
  if($null -eq $Receipt.cas_invoked -or
     $casOutcome -notin @('NOT_INVOKED','UNKNOWN','COMMITTED','NOT_COMMITTED')){
   $errors+=@('AMBIGUOUS_CAS_OBSERVATION')
  }
  if($errors.Count -eq 0){
   $states=@($taskRows | ForEach-Object {[string]$_.state})
   $allRunning=(@($states | Where-Object {$_ -cne 'Running'}).Count -eq 0)
   $allDisabled=(@($states | Where-Object {$_ -cne 'Disabled'}).Count -eq 0)
   $marker=[string]$Receipt.fence_marker_phase
   if($casWasInvoked -or $casOutcome -ne 'NOT_INVOKED' -or $phase -in @('CAS_INVOKED','CLOUD_COMMITTED')){
    # An attempted CAS crosses the irrevocable *automatic rearm* boundary.
    if($phase -eq 'CLOUD_COMMITTED' -and $casOutcome -eq 'COMMITTED' -and $allDisabled){
     $decision='HOLD_POSTCOMMIT_OLD_INTAKE_FENCED_KEEP_AFTERCARE'
    }else{
     $decision='HOLD_CAS_ATTEMPTED_MANUAL_CLOUD_RECONCILIATION'
    }
   }elseif($phase -eq 'DISCOVERY' -and $marker -eq 'ABSENT' -and $allRunning){
    $decision='REVIEW_ARM_FENCE_SEPARATE_PHYSICAL_APPROVAL'
   }elseif($phase -eq 'ARMED' -and $marker -eq 'ARMED' -and $allRunning){
    $decision='REVIEW_DISABLE_ONLY_CANDIDATES_AND_WAIT'
   }elseif($phase -eq 'TASKS_DISABLED' -and $marker -eq 'ARMED' -and $allDisabled -and
      $Receipt.windows_and_supervisor_no_rearm_readback -eq $true){
    $decision='REVIEW_BOUNDED_OLD_INTAKE_STOP_AND_FRESH_PROCESS_READBACK'
   }elseif($phase -eq 'STOP_RECORDED' -and $marker -eq 'ARMED' -and $allDisabled -and
      $Receipt.windows_and_supervisor_no_rearm_readback -eq $true -and
      $Receipt.old_intake_process_count -is [int] -and [int]$Receipt.old_intake_process_count -eq 0){
    $decision='REVIEW_QUIESCED_FENCE_WITH_ORIGINAL_AFTERCARE'
   }elseif($phase -eq 'QUIESCED' -and $marker -eq 'QUIESCED' -and $allDisabled -and
      $Receipt.windows_and_supervisor_no_rearm_readback -eq $true -and
      $Receipt.old_intake_process_count -is [int] -and [int]$Receipt.old_intake_process_count -eq 0){
    if([int]$Receipt.authentic_technical_e2e_proofs -eq 6 -and
       $Receipt.model_budget_separately_approved -eq $true){
     $decision='REVIEW_SEPARATE_CLOUD_CAS_APPROVAL_NO_EXECUTION'
    }else{
     $decision='HOLD_SIX_E2E_AND_BUDGET_APPROVAL'
    }
   }else{
    $decision='HOLD_INCONSISTENT_FENCE_STATE_OR_NO_REARM'
   }
  }
 }
 return [pscustomobject]@{
  kind='V3_FENCE_DRYRUN_DISPOSITION_OFFLINE_ONLY_V1'
  simulated_next_review=$decision
  input_errors=@($errors)
  intended_scope_only=@('CryptoMiniPC-V2R4PaperCandidates','CryptoMiniPC-V2R4PaperWait')
  protected_tasks_must_keep_running=@('CryptoMiniPC-V2R4PaperLifecycle','CryptoMiniPC-V2R4PaperCloudSync')
  proof_is_synthetic_not_live=$true
  native_task_disable_or_stop_permitted=$false
  process_kill_permitted=$false
  marker_write_permitted=$false
  automatic_old_intake_rearm_permitted=$false
  cloud_cas_invoke_permitted=$false
  model_spend_or_real_money_permitted=$false
  physical_quiescence_verified_here=$false
  full_e2e_release_proofs_credited=0
 }
}

if($Execute){
 throw 'V3_CUTOVER_EXECUTION_LOCKED: no stop/disable, marker, CAS, or rollback is implemented or authorized in this inactive source.'
}
$repo=Join-Path $TradingRoot 'Repos\kraken-eur-scanner'
$physical=Join-Path $repo 'tools\check-minipc-v3-physical-writer-readiness.ps1'
$marker=Join-Path $TradingRoot 'State\v3-experimental-paper-old-intake-fence.json'
$oldMaintenance=Join-Path $TradingRoot 'State\v2r4-technical-cutover-maintenance.json'
if(-not(Test-Path -LiteralPath $physical -PathType Leaf)){
 throw 'V3_READONLY_PREFLIGHT_SOURCE_MISSING: PR313 original-host source pin must be separately installed and verified.'
}
$report=& $physical -TradingRoot $TradingRoot | ConvertFrom-Json
$present=Test-Path -LiteralPath $marker
$oldPresent=Test-Path -LiteralPath $oldMaintenance
$ready=Test-V3CutoverPreparationPolicy -Report $report -FenceMarkerPresent $present -MaintenanceMarkerPresent $oldPresent
$waitTask=@($report.physical_v2r4_paper_task_readback |
 Where-Object { $_.task_name -ceq 'CryptoMiniPC-V2R4PaperWait' })
$waitActionObserved=($waitTask.Count -eq 1 -and
 $waitTask[0].action_script_basename -ceq 'wait_launcher.py' -and
 [string]$waitTask[0].action_sha256 -match '^[a-f0-9]{64}$')
$allProcessEdges=@()
$waitProcessRows=@()
$waitSnapshotReadable=$false
try {
 $allProcesses=@(Get-CimInstance Win32_Process -ErrorAction Stop)
 $allProcessEdges=@($allProcesses | ForEach-Object {
  [pscustomobject]@{PID=[int]$_.ProcessId;ParentPID=[int]$_.ParentProcessId}
 })
 $oldStage=Join-Path $TradingRoot 'Runtime\v2r4-paper-stage-d8b35a8ec2e6'
 foreach($p in $allProcesses){
  if([string]$p.Name -notmatch '(?i)^pythonw?\.exe$'){continue}
  $cmd=[string]$p.CommandLine
  if($cmd -notmatch '(?i)(?:wait_launcher|v2r4_wait_runtime)\.py'){continue}
  $waitProcessRows+=@([pscustomobject]@{
   PID=[int]$p.ProcessId
   ParentPID=[int]$p.ParentProcessId
   OriginalStage=$cmd.Contains($oldStage)
  })
 }
 $waitSnapshotReadable=$true
}catch{
 $waitProcessRows=@()
 $allProcessEdges=@()
}
$protected=@($report.native_old_paper_mode_rows | ForEach-Object {[int]$_.pid})
$completeWaitSnapshot=($waitSnapshotReadable -and
 (Test-V3WaitCompleteReadOnlyFamily -WaitRows $waitProcessRows -AllProcesses $allProcessEdges -WaitActionObserved $waitActionObserved -ProtectedRolePids $protected))
[ordered]@{
 kind='V3_SCOPED_CUTOVER_OPERATOR_SOURCE_PREP_INACTIVE_V1'
 phase='READ_ONLY'
 checked_at_utc=(Get-Date).ToUniversalTime().ToString('o')
 pre_cutover_discovery_pass=$ready
 candidate_wait_only_future_quiesce_scope=@(
  'CryptoMiniPC-V2R4PaperCandidates',
  'CryptoMiniPC-V2R4PaperWait'
 )
 must_preserve_original_tasks=@(
  'CryptoMiniPC-V2R4PaperLifecycle',
  'CryptoMiniPC-V2R4PaperCloudSync'
 )
 original_role_lineage_snapshot_only=$true
 v3_host_source_deployment_independently_required=$true
 original_wait_tree_and_full_task_source_pins_separate_gate=$true
 wait_full_process_inventory_readable=$waitSnapshotReadable
 wait_closed_descendants_readonly_snapshot_pass=$completeWaitSnapshot
 wait_closed_descendants_snapshot_only_no_stop_authority=$true
 wait_seen_python_family_count=@($waitProcessRows).Count
 wait_unrecognized_descendant_failure_is_fail_closed=$true
 windows_native_disable_stop_and_no_rearm_proven=$false
 physically_quiescent_old_intake_processes_proven=$false
 historical_followup_and_exit_cloud_ack_proven=$false
 cloud_single_active_cas_proven=$false
 backup_manifest_contract_policy_only=$true
 cutover_recovery_decision_matrix_policy_only=$true
 real_task_xml_backup_not_yet_executed=$true
 exact_task_stop_disable_and_native_no_rearm_unimplemented=$true
 rollback_precommit_only_unimplemented=$true
 unknown_cloud_commit_forbids_old_writer_rearm=$true
 v3_paper_technical_e2e_proofs_accepted=0
 v3_live_release_authorized=$false
 task_process_marker_cloud_writes=0
 do_not_use_old_v2r4_technical_cutover_operator=$true
} | ConvertTo-Json -Depth 7
